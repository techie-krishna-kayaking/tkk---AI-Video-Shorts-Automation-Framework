"""Video detector - automatically detects video properties and categorizes content."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.utils.files import get_video_duration, get_video_fps, get_video_resolution, probe_video
from app.utils.logging import get_logger

logger = get_logger(__name__)


class VideoCategory(str, Enum):
    TUTORIAL = "tutorial"
    GOPRO = "gopro"
    VERTICAL = "vertical"
    UNKNOWN = "unknown"


class AspectRatio(str, Enum):
    LANDSCAPE = "16:9"
    PORTRAIT = "9:16"
    SQUARE = "1:1"
    OTHER = "other"


@dataclass
class VideoInfo:
    """Complete video metadata."""
    path: Path
    width: int
    height: int
    fps: float
    duration: float
    aspect_ratio: AspectRatio
    category: VideoCategory
    codec: str
    audio_codec: str
    bitrate: int
    file_size: int


def detect_aspect_ratio(width: int, height: int) -> AspectRatio:
    """Detect aspect ratio from dimensions."""
    if width == 0 or height == 0:
        return AspectRatio.OTHER

    ratio = width / height

    if 1.7 <= ratio <= 1.8:  # ~16:9
        return AspectRatio.LANDSCAPE
    elif 0.55 <= ratio <= 0.58:  # ~9:16
        return AspectRatio.PORTRAIT
    elif 0.95 <= ratio <= 1.05:  # ~1:1
        return AspectRatio.SQUARE
    else:
        return AspectRatio.OTHER


def detect_category(video_path: Path, aspect_ratio: AspectRatio) -> VideoCategory:
    """
    Detect video category based on path, aspect ratio, and metadata.

    Heuristics:
    - If in tutorials/ folder -> TUTORIAL
    - If in gopro/ folder -> GOPRO
    - If in vertical/ folder -> VERTICAL
    - If 9:16 aspect ratio -> VERTICAL
    - If filename contains gopro/hero/action -> GOPRO
    - Default to TUTORIAL for 16:9
    """
    path_str = str(video_path).lower()

    # Check parent directory
    if "tutorials" in path_str or "tutorial" in path_str:
        return VideoCategory.TUTORIAL
    if "gopro" in path_str or "action" in path_str:
        return VideoCategory.GOPRO
    if "vertical" in path_str:
        return VideoCategory.VERTICAL

    # Check filename
    filename = video_path.stem.lower()
    gopro_keywords = ["gopro", "hero", "action", "adventure", "outdoor"]
    if any(kw in filename for kw in gopro_keywords):
        return VideoCategory.GOPRO

    # Fall back to aspect ratio
    if aspect_ratio == AspectRatio.PORTRAIT:
        return VideoCategory.VERTICAL
    if aspect_ratio == AspectRatio.LANDSCAPE:
        return VideoCategory.TUTORIAL

    return VideoCategory.UNKNOWN


def detect_video(video_path: Path) -> VideoInfo:
    """Analyze a video file and return complete metadata."""
    logger.info("detecting_video", path=str(video_path))

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    width, height = get_video_resolution(video_path)
    fps = get_video_fps(video_path)
    duration = get_video_duration(video_path)
    aspect_ratio = detect_aspect_ratio(width, height)
    category = detect_category(video_path, aspect_ratio)

    # Get additional info from probe
    probe_data = probe_video(video_path)
    codec = ""
    audio_codec = ""
    bitrate = 0

    for stream in probe_data.get("streams", []):
        if stream.get("codec_type") == "video" and not codec:
            codec = stream.get("codec_name", "")
        elif stream.get("codec_type") == "audio" and not audio_codec:
            audio_codec = stream.get("codec_name", "")

    if "format" in probe_data:
        bitrate = int(probe_data["format"].get("bit_rate", 0))

    file_size = video_path.stat().st_size

    info = VideoInfo(
        path=video_path,
        width=width,
        height=height,
        fps=fps,
        duration=duration,
        aspect_ratio=aspect_ratio,
        category=category,
        codec=codec,
        audio_codec=audio_codec,
        bitrate=bitrate,
        file_size=file_size,
    )

    logger.info(
        "video_detected",
        resolution=f"{width}x{height}",
        fps=fps,
        duration=f"{duration:.1f}s",
        aspect_ratio=aspect_ratio.value,
        category=category.value,
    )

    return info
