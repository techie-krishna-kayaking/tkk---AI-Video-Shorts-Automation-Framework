"""Motion detection using OpenCV for action/GoPro video analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MotionSegment:
    """A segment with significant motion activity."""
    start: float
    end: float
    intensity: float  # 0.0 to 1.0
    frame_start: int
    frame_end: int


@dataclass
class MotionAnalysis:
    """Complete motion analysis result."""
    segments: list[MotionSegment]
    avg_motion: float
    peak_motion: float
    motion_scores: list[float]  # Per-second motion scores
    fps: float
    total_frames: int


class MotionDetector:
    """Detect motion intensity using optical flow and frame differencing."""

    def __init__(
        self,
        sample_rate: int = 2,
        motion_threshold: float = 0.3,
        min_segment_duration: float = 3.0,
    ):
        """
        Args:
            sample_rate: Analyze every Nth frame for performance.
            motion_threshold: Threshold for "high motion" (0-1 normalized).
            min_segment_duration: Minimum duration for a motion segment.
        """
        self.sample_rate = sample_rate
        self.motion_threshold = motion_threshold
        self.min_segment_duration = min_segment_duration

    def analyze(self, video_path: Path) -> MotionAnalysis:
        """
        Analyze motion throughout the video.

        Uses frame differencing with Gaussian blur to detect motion.
        """
        logger.info("analyzing_motion", path=str(video_path))

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_scores: list[float] = []

        prev_gray = None
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % self.sample_rate == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)

                if prev_gray is not None:
                    # Frame difference
                    diff = cv2.absdiff(prev_gray, gray)
                    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
                    motion_score = np.count_nonzero(thresh) / thresh.size
                    frame_scores.append(motion_score)
                else:
                    frame_scores.append(0.0)

                prev_gray = gray

            frame_idx += 1

        cap.release()

        # Normalize scores
        max_score = max(frame_scores) if frame_scores else 1.0
        if max_score > 0:
            normalized_scores = [s / max_score for s in frame_scores]
        else:
            normalized_scores = frame_scores

        # Compute per-second scores
        frames_per_second = fps / self.sample_rate
        per_second_scores: list[float] = []
        chunk_size = max(1, int(frames_per_second))
        for i in range(0, len(normalized_scores), chunk_size):
            chunk = normalized_scores[i:i + chunk_size]
            per_second_scores.append(sum(chunk) / len(chunk) if chunk else 0.0)

        # Find high-motion segments
        segments = self._find_segments(per_second_scores, fps)

        avg_motion = sum(per_second_scores) / len(per_second_scores) if per_second_scores else 0.0
        peak_motion = max(per_second_scores) if per_second_scores else 0.0

        analysis = MotionAnalysis(
            segments=segments,
            avg_motion=avg_motion,
            peak_motion=peak_motion,
            motion_scores=per_second_scores,
            fps=fps,
            total_frames=total_frames,
        )

        logger.info(
            "motion_analyzed",
            total_frames=total_frames,
            high_motion_segments=len(segments),
            avg_motion=f"{avg_motion:.3f}",
            peak_motion=f"{peak_motion:.3f}",
        )

        return analysis

    def _find_segments(
        self,
        per_second_scores: list[float],
        fps: float,
    ) -> list[MotionSegment]:
        """Find continuous high-motion segments."""
        segments: list[MotionSegment] = []
        in_segment = False
        seg_start = 0
        seg_scores: list[float] = []

        for i, score in enumerate(per_second_scores):
            if score >= self.motion_threshold:
                if not in_segment:
                    seg_start = i
                    seg_scores = []
                    in_segment = True
                seg_scores.append(score)
            else:
                if in_segment:
                    duration = i - seg_start
                    if duration >= self.min_segment_duration:
                        segments.append(
                            MotionSegment(
                                start=float(seg_start),
                                end=float(i),
                                intensity=sum(seg_scores) / len(seg_scores),
                                frame_start=int(seg_start * fps),
                                frame_end=int(i * fps),
                            )
                        )
                    in_segment = False

        # Handle segment at end
        if in_segment:
            duration = len(per_second_scores) - seg_start
            if duration >= self.min_segment_duration:
                segments.append(
                    MotionSegment(
                        start=float(seg_start),
                        end=float(len(per_second_scores)),
                        intensity=sum(seg_scores) / len(seg_scores),
                        frame_start=int(seg_start * fps),
                        frame_end=int(len(per_second_scores) * fps),
                    )
                )

        return segments

    def get_excitement_score(self, motion_analysis: MotionAnalysis, start: float, end: float) -> float:
        """Get the excitement/motion score for a specific time range."""
        start_idx = int(start)
        end_idx = int(end)
        scores = motion_analysis.motion_scores[start_idx:end_idx]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)
