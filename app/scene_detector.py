"""Scene detection using PySceneDetect."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scenedetect import ContentDetector, SceneManager, open_video

from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Scene:
    """A detected scene with start/end times."""
    start: float
    end: float
    duration: float
    index: int


@dataclass
class SceneAnalysis:
    """Complete scene detection result."""
    scenes: list[Scene]
    total_scenes: int
    avg_scene_duration: float


class SceneDetector:
    """Detect scene changes using PySceneDetect's ContentDetector."""

    def __init__(self, threshold: float = 27.0, min_scene_len: int = 15):
        """
        Args:
            threshold: Content detection threshold (lower = more sensitive).
            min_scene_len: Minimum scene length in frames.
        """
        self.threshold = threshold
        self.min_scene_len = min_scene_len

    def detect(self, video_path: Path) -> SceneAnalysis:
        """
        Detect scene boundaries in a video.

        Returns list of scenes with timing information.
        """
        logger.info(
            "detecting_scenes",
            path=str(video_path),
            threshold=self.threshold,
        )

        video = open_video(str(video_path))
        scene_manager = SceneManager()
        scene_manager.add_detector(
            ContentDetector(
                threshold=self.threshold,
                min_scene_len=self.min_scene_len,
            )
        )

        scene_manager.detect_scenes(video, show_progress=False)
        scene_list = scene_manager.get_scene_list()

        scenes: list[Scene] = []
        for idx, (start, end) in enumerate(scene_list):
            start_sec = start.get_seconds()
            end_sec = end.get_seconds()
            scenes.append(
                Scene(
                    start=start_sec,
                    end=end_sec,
                    duration=end_sec - start_sec,
                    index=idx,
                )
            )

        avg_duration = (
            sum(s.duration for s in scenes) / len(scenes) if scenes else 0.0
        )

        analysis = SceneAnalysis(
            scenes=scenes,
            total_scenes=len(scenes),
            avg_scene_duration=avg_duration,
        )

        logger.info(
            "scenes_detected",
            total=len(scenes),
            avg_duration=f"{avg_duration:.1f}s",
        )

        return analysis

    def get_scene_at_time(self, scenes: list[Scene], time: float) -> Scene | None:
        """Find which scene a given timestamp falls into."""
        for scene in scenes:
            if scene.start <= time <= scene.end:
                return scene
        return None

    def find_scene_boundaries_near(
        self,
        scenes: list[Scene],
        target_time: float,
        tolerance: float = 5.0,
    ) -> float | None:
        """Find the nearest scene boundary to a target time."""
        boundaries: list[float] = []
        for scene in scenes:
            boundaries.append(scene.start)
            boundaries.append(scene.end)

        nearest = None
        min_distance = tolerance
        for boundary in boundaries:
            distance = abs(boundary - target_time)
            if distance < min_distance:
                min_distance = distance
                nearest = boundary

        return nearest
