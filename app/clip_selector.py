"""Clip selection and scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.detector import VideoCategory, VideoInfo
from app.motion_detector import MotionAnalysis, MotionDetector
from app.scene_detector import SceneAnalysis, SceneDetector
from app.silence_detector import SilenceAnalysis, SilenceDetector
from app.transcriber import Transcription, Transcriber
from app.utils.config import get_config
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Hook keywords for tutorial content
TUTORIAL_HOOK_KEYWORDS = [
    "how to", "mistake", "shortcut", "tip", "secret",
    "important", "never", "always", "why", "best",
    "trick", "hack", "easy", "simple", "fast",
    "problem", "solution", "fix", "avoid", "stop",
]


@dataclass
class Clip:
    """A candidate clip with scoring information."""
    start: float
    end: float
    duration: float
    score: float = 0.0
    speech_score: float = 0.0
    motion_score: float = 0.0
    hook_score: float = 0.0
    scene_score: float = 0.0
    has_speech: bool = True
    hook_text: str = ""
    transcript: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class ClipSelection:
    """Result of clip selection process."""
    clips: list[Clip]
    total_candidates: int
    selected_count: int
    video_info: VideoInfo


class ClipSelector:
    """
    Intelligent clip selection based on content analysis.

    Combines multiple signals:
    - Speech activity and hooks
    - Motion intensity
    - Scene transitions
    - Silence boundaries
    """

    def __init__(self, fast: bool = False):
        config = get_config()
        self.min_duration = config.shorts.min_duration
        self.max_duration = config.shorts.max_duration
        self.target_duration = config.shorts.target_duration
        # Fast mode uses 'tiny' model (~6x faster) and skips word timestamps
        model = "tiny" if fast else None
        self.transcriber = Transcriber(model_name=model, word_timestamps=not fast)
        self.silence_detector = SilenceDetector()
        self.scene_detector = SceneDetector()
        self.motion_detector = MotionDetector()

    def select_clips(
        self,
        video_path: Path,
        video_info: VideoInfo,
        max_clips: int | None = None,
    ) -> ClipSelection:
        """
        Analyze video and select the best clips for shorts.

        Strategy depends on video category:
        - Tutorial: prioritize speech, hooks, tips
        - GoPro: prioritize motion, excitement, scene transitions
        - Vertical: split at silence/sentence boundaries
        """
        logger.info(
            "selecting_clips",
            category=video_info.category.value,
            duration=f"{video_info.duration:.1f}s",
        )

        if video_info.category == VideoCategory.VERTICAL:
            return self._select_vertical_clips(video_path, video_info)
        elif video_info.category == VideoCategory.GOPRO:
            # GoPro/vlog shorts are simple back-to-back fixed-length segments
            # (0-30, 30-60, ...). No motion/scene detection is performed.
            return self._select_fixed_segments(video_info, max_clips=max_clips)
        else:
            return self._select_tutorial_clips(video_path, video_info, max_clips)

    def _select_fixed_segments(
        self,
        video_info: VideoInfo,
        segment_seconds: float = 30.0,
        min_tail: float = 10.0,
        max_clips: int | None = None,
    ) -> ClipSelection:
        """Cut the source into consecutive fixed-length segments.

        Starting at 0:00 the video is sliced into back-to-back
        ``segment_seconds`` clips (0-30, 30-60, ...). No motion, scene, speech,
        or silence detection is performed. A trailing partial clip is kept only
        when it is at least ``min_tail`` seconds long.
        """
        duration = float(video_info.duration)
        clips: list[Clip] = []
        start = 0.0
        while start < duration - 0.05:
            end = min(start + segment_seconds, duration)
            length = end - start
            # Drop a too-short tail, but always keep at least one clip.
            if length < min_tail and clips:
                break
            clips.append(
                Clip(
                    start=round(start, 3),
                    end=round(end, 3),
                    duration=round(length, 3),
                    has_speech=False,
                    tags=["fixed-segment"],
                )
            )
            start = end

        if max_clips:
            clips = clips[:max_clips]

        logger.info(
            "fixed_segments_selected",
            count=len(clips),
            segment_seconds=segment_seconds,
            duration=f"{duration:.1f}s",
        )

        return ClipSelection(
            clips=clips,
            total_candidates=len(clips),
            selected_count=len(clips),
            video_info=video_info,
        )

    def _select_tutorial_clips(
        self,
        video_path: Path,
        video_info: VideoInfo,
        max_clips: int | None = None,
    ) -> ClipSelection:
        """Select clips from tutorial videos using speech and hook analysis."""
        # Transcribe the video (cached for reuse in caption generation)
        self._last_transcription = self.transcriber.transcribe(video_path)
        transcription = self._last_transcription

        # Detect silence for boundary finding
        silence = self.silence_detector.detect(video_path)

        # Detect scenes
        scenes = self.scene_detector.detect(video_path)

        # Generate candidate clips
        candidates = self._generate_tutorial_candidates(
            transcription, silence, scenes, video_info.duration
        )

        # Score and rank
        scored = self._score_tutorial_clips(candidates, transcription)

        # Sort by score descending
        scored.sort(key=lambda c: c.score, reverse=True)

        # Limit clips
        if max_clips:
            scored = scored[:max_clips]

        # Sort by time for sequential output
        scored.sort(key=lambda c: c.start)

        return ClipSelection(
            clips=scored,
            total_candidates=len(candidates),
            selected_count=len(scored),
            video_info=video_info,
        )

    def _select_gopro_clips(
        self,
        video_path: Path,
        video_info: VideoInfo,
    ) -> ClipSelection:
        """Select clips from GoPro/action videos using motion analysis."""
        # Analyze motion
        motion = self.motion_detector.analyze(video_path)

        # Detect scenes
        scenes = self.scene_detector.detect(video_path)

        # Generate candidates from high-motion segments
        candidates = self._generate_gopro_candidates(motion, scenes, video_info.duration)

        # Score based on motion intensity
        for clip in candidates:
            clip.motion_score = self.motion_detector.get_excitement_score(
                motion, clip.start, clip.end
            )
            clip.score = clip.motion_score * 0.7 + clip.scene_score * 0.3

        # Sort by score
        candidates.sort(key=lambda c: c.score, reverse=True)

        # Remove overlapping clips
        selected = self._remove_overlaps(candidates)

        # Sort by time
        selected.sort(key=lambda c: c.start)

        return ClipSelection(
            clips=selected,
            total_candidates=len(candidates),
            selected_count=len(selected),
            video_info=video_info,
        )

    def _select_vertical_clips(
        self,
        video_path: Path,
        video_info: VideoInfo,
    ) -> ClipSelection:
        """Select clips from vertical videos - split at silence boundaries."""
        split_points = self.silence_detector.find_split_points(
            video_path,
            min_clip_duration=self.min_duration,
            max_clip_duration=self.max_duration,
        )

        clips: list[Clip] = []
        prev = 0.0
        for split_time in split_points:
            duration = split_time - prev
            if duration >= self.min_duration:
                clips.append(
                    Clip(
                        start=prev,
                        end=split_time,
                        duration=duration,
                        score=1.0,
                        has_speech=True,
                    )
                )
            prev = split_time

        # Handle remaining
        remaining = video_info.duration - prev
        if remaining >= self.min_duration:
            clips.append(
                Clip(
                    start=prev,
                    end=video_info.duration,
                    duration=remaining,
                    score=1.0,
                    has_speech=True,
                )
            )

        return ClipSelection(
            clips=clips,
            total_candidates=len(clips),
            selected_count=len(clips),
            video_info=video_info,
        )

    def _generate_tutorial_candidates(
        self,
        transcription: Transcription,
        silence: SilenceAnalysis,
        scenes: SceneAnalysis,
        total_duration: float,
    ) -> list[Clip]:
        """Generate clip candidates from tutorial content."""
        candidates: list[Clip] = []

        # Strategy 1: Use silence boundaries as split points
        silence_splits = []
        for interval in silence.intervals:
            mid = (interval.start + interval.end) / 2
            silence_splits.append(mid)

        # Strategy 2: Find segments with hook keywords
        for seg in transcription.segments:
            text_lower = seg.text.lower()
            for keyword in TUTORIAL_HOOK_KEYWORDS:
                if keyword in text_lower:
                    # Create a clip starting slightly before this segment
                    clip_start = max(0, seg.start - 2.0)
                    # Find a good end point
                    clip_end = self._find_clip_end(
                        clip_start, silence_splits, total_duration
                    )
                    duration = clip_end - clip_start
                    if self.min_duration <= duration <= self.max_duration:
                        candidates.append(
                            Clip(
                                start=clip_start,
                                end=clip_end,
                                duration=duration,
                                hook_text=seg.text,
                                has_speech=True,
                                tags=[keyword],
                            )
                        )
                    break

        # Strategy 3: Sliding window with speech density
        window_size = self.target_duration
        step = window_size / 2
        pos = 0.0
        while pos + self.min_duration <= total_duration:
            end = min(pos + window_size, total_duration)
            # Check if there's speech in this window
            speech_in_window = any(
                seg.start >= pos and seg.end <= end
                for seg in transcription.segments
            )
            if speech_in_window:
                candidates.append(
                    Clip(
                        start=pos,
                        end=end,
                        duration=end - pos,
                        has_speech=True,
                    )
                )
            pos += step

        return candidates

    def _generate_gopro_candidates(
        self,
        motion: MotionAnalysis,
        scenes: SceneAnalysis,
        total_duration: float,
    ) -> list[Clip]:
        """Generate clip candidates from GoPro motion data."""
        candidates: list[Clip] = []

        # Use high-motion segments
        for segment in motion.segments:
            # Extend to target duration if possible
            duration = segment.end - segment.start
            if duration < self.min_duration:
                # Extend equally on both sides
                deficit = self.min_duration - duration
                start = max(0, segment.start - deficit / 2)
                end = min(total_duration, segment.end + deficit / 2)
            elif duration > self.max_duration:
                # Trim to max duration, keeping the peak
                start = segment.start
                end = start + self.max_duration
            else:
                start = segment.start
                end = segment.end

            candidates.append(
                Clip(
                    start=start,
                    end=end,
                    duration=end - start,
                    motion_score=segment.intensity,
                    has_speech=False,
                )
            )

        # Also consider scene transitions as exciting moments
        for scene in scenes.scenes:
            if self.min_duration <= scene.duration <= self.max_duration:
                candidates.append(
                    Clip(
                        start=scene.start,
                        end=scene.end,
                        duration=scene.duration,
                        scene_score=0.5,
                        has_speech=False,
                    )
                )

        return candidates

    def _score_tutorial_clips(
        self,
        candidates: list[Clip],
        transcription: Transcription,
    ) -> list[Clip]:
        """Score tutorial clips based on speech content."""
        for clip in candidates:
            # Speech density score
            words_in_clip = sum(
                1 for seg in transcription.segments
                for word in seg.words
                if clip.start <= word.start <= clip.end
            )
            speech_density = words_in_clip / max(clip.duration, 1.0)
            clip.speech_score = min(speech_density / 3.0, 1.0)  # Normalize

            # Hook score
            clip_text = " ".join(
                seg.text for seg in transcription.segments
                if seg.start >= clip.start and seg.end <= clip.end
            ).lower()
            clip.transcript = clip_text

            hook_count = sum(
                1 for kw in TUTORIAL_HOOK_KEYWORDS if kw in clip_text
            )
            clip.hook_score = min(hook_count / 3.0, 1.0)

            # Combined score
            clip.score = (
                clip.speech_score * 0.3
                + clip.hook_score * 0.5
                + (0.2 if clip.has_speech else 0.0)
            )

        return candidates

    def _find_clip_end(
        self,
        start: float,
        silence_splits: list[float],
        total_duration: float,
    ) -> float:
        """Find the best end point for a clip starting at `start`."""
        target_end = start + self.target_duration
        max_end = start + self.max_duration

        # Find silence boundary closest to target
        best_end = target_end
        for split in silence_splits:
            if start + self.min_duration <= split <= max_end:
                if abs(split - target_end) < abs(best_end - target_end):
                    best_end = split

        return min(best_end, total_duration)

    def _remove_overlaps(self, clips: list[Clip], min_gap: float = 2.0) -> list[Clip]:
        """Remove overlapping clips, keeping higher-scored ones."""
        if not clips:
            return []

        selected: list[Clip] = [clips[0]]
        for clip in clips[1:]:
            last = selected[-1]
            if clip.start >= last.end + min_gap:
                selected.append(clip)

        return selected
