"""Silence detection using FFmpeg audio filters."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.utils.config import get_config
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SilenceInterval:
    """A detected silence interval."""
    start: float
    end: float
    duration: float


@dataclass
class SilenceAnalysis:
    """Complete silence analysis result."""
    intervals: list[SilenceInterval]
    total_silence: float
    total_duration: float
    silence_ratio: float


class SilenceDetector:
    """Detect silence in audio using FFmpeg's silencedetect filter."""

    def __init__(
        self,
        threshold_db: float | None = None,
        min_duration: float | None = None,
    ):
        config = get_config()
        self.threshold_db = threshold_db or config.shorts.silence_threshold
        self.min_duration = min_duration or config.shorts.silence_min_duration

    def detect(self, video_path: Path) -> SilenceAnalysis:
        """
        Detect silence intervals in a video/audio file.

        Uses FFmpeg's silencedetect audio filter to find quiet sections.
        """
        logger.info(
            "detecting_silence",
            path=str(video_path),
            threshold=self.threshold_db,
            min_duration=self.min_duration,
        )

        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-af", f"silencedetect=noise={self.threshold_db}dB:d={self.min_duration}",
            "-f", "null",
            "-",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        # Parse silence intervals from stderr
        intervals = self._parse_output(result.stderr)

        # Get total duration
        total_duration = self._get_duration(video_path)
        total_silence = sum(i.duration for i in intervals)
        silence_ratio = total_silence / total_duration if total_duration > 0 else 0.0

        analysis = SilenceAnalysis(
            intervals=intervals,
            total_silence=total_silence,
            total_duration=total_duration,
            silence_ratio=silence_ratio,
        )

        logger.info(
            "silence_detected",
            intervals=len(intervals),
            total_silence=f"{total_silence:.1f}s",
            ratio=f"{silence_ratio:.1%}",
        )

        return analysis

    def _parse_output(self, stderr: str) -> list[SilenceInterval]:
        """Parse FFmpeg silencedetect output."""
        intervals: list[SilenceInterval] = []

        # Match silence_start and silence_end pairs
        start_pattern = re.compile(
            r"silence_start:\s*([\d.]+)"
        )
        end_pattern = re.compile(
            r"silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)"
        )

        starts: list[float] = []
        for line in stderr.split("\n"):
            start_match = start_pattern.search(line)
            if start_match:
                starts.append(float(start_match.group(1)))

            end_match = end_pattern.search(line)
            if end_match:
                end_time = float(end_match.group(1))
                duration = float(end_match.group(2))
                start_time = starts.pop(0) if starts else end_time - duration
                intervals.append(
                    SilenceInterval(
                        start=start_time,
                        end=end_time,
                        duration=duration,
                    )
                )

        return intervals

    def _get_duration(self, video_path: Path) -> float:
        """Get video duration using ffprobe."""
        from app.utils.files import get_video_duration
        return get_video_duration(video_path)

    def find_split_points(
        self,
        video_path: Path,
        min_clip_duration: float = 15.0,
        max_clip_duration: float = 60.0,
    ) -> list[float]:
        """
        Find optimal split points based on silence.

        Returns a list of timestamps where clips should be split.
        Ensures clips are between min and max duration.
        """
        analysis = self.detect(video_path)
        total_duration = analysis.total_duration

        split_points: list[float] = []
        last_split = 0.0

        for interval in analysis.intervals:
            # Use the middle of silence as split point
            split_time = (interval.start + interval.end) / 2
            time_since_last = split_time - last_split

            if time_since_last >= min_clip_duration:
                if time_since_last <= max_clip_duration:
                    split_points.append(split_time)
                    last_split = split_time
                elif time_since_last > max_clip_duration:
                    # Force split at max duration
                    forced_split = last_split + max_clip_duration
                    split_points.append(forced_split)
                    last_split = forced_split
                    # Also add the silence point if it's far enough
                    if split_time - last_split >= min_clip_duration:
                        split_points.append(split_time)
                        last_split = split_time

        # Handle remaining duration
        remaining = total_duration - last_split
        if remaining > max_clip_duration:
            # Add forced splits
            while total_duration - last_split > max_clip_duration:
                last_split += max_clip_duration
                split_points.append(last_split)

        logger.info("split_points_found", count=len(split_points))
        return sorted(set(split_points))
