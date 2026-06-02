"""File and path utility functions."""

from __future__ import annotations

import re
import subprocess
import json
from pathlib import Path
from typing import Any

from app.utils.logging import get_logger

logger = get_logger(__name__)


def sanitize_filename(name: str) -> str:
    """Make a filename filesystem-safe."""
    # Remove extension if present
    stem = Path(name).stem
    # Replace spaces and special chars with underscores
    sanitized = re.sub(r"[^\w\-.]", "_", stem)
    # Collapse multiple underscores
    sanitized = re.sub(r"_+", "_", sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip("_")
    return sanitized.lower()


def get_output_dir(video_path: Path, output_base: str = "output") -> Path:
    """Get or create the output directory for a video."""
    video_name = sanitize_filename(video_path.stem)
    output_dir = Path(output_base) / video_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_channel_output_dir(channel_output_folder: str) -> Path:
    """Get or create the flat output directory for a channel."""
    output_dir = Path(channel_output_folder)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_channel_video_name(video_path: Path, channel_input_folder: str) -> str:
    """
    Generate output video name using parent folder + original video name.

    For a video at input/krgd_vlogs/trip_01/video1.mp4 with channel input
    folder 'input/krgd_vlogs', returns 'trip_01_video1'.

    If the video is directly in the channel folder (no subfolder),
    just returns the video stem.
    """
    channel_root = Path(channel_input_folder)

    relative: Path | None = None

    # Primary path resolution attempt.
    try:
        relative = video_path.resolve().relative_to(channel_root.resolve())
    except ValueError:
        # Keep fallback anchor behavior scoped to krgd_vlogs only.
        # Other channels retain prior behavior: plain sanitized stem.
        if "krgd_vlogs" not in channel_input_folder.lower():
            return sanitize_filename(video_path.stem)

        # Fallback for runs where cwd differs: find channel path components
        # inside the video path and derive a relative path from that anchor.
        channel_parts = channel_root.parts
        video_parts = video_path.resolve().parts

        anchor_idx = -1
        max_idx = len(video_parts) - len(channel_parts)
        for idx in range(max_idx + 1):
            if video_parts[idx: idx + len(channel_parts)] == channel_parts:
                anchor_idx = idx
                break

        if anchor_idx != -1:
            rel_parts = video_parts[anchor_idx + len(channel_parts):]
            if rel_parts:
                relative = Path(*rel_parts)

    if relative is None:
        # Video isn't inside the configured channel folder, use plain name.
        return sanitize_filename(video_path.stem)

    parts = relative.parts
    if len(parts) <= 1:
        # Video is directly in channel folder
        return sanitize_filename(video_path.stem)
    else:
        # Use parent folder(s) + video name: trip_01_video1
        parent_parts = parts[:-1]
        prefix = "_".join(sanitize_filename(p) for p in parent_parts)
        return f"{prefix}_{sanitize_filename(video_path.stem)}"


def discover_channel_videos(
    channel_input_folder: str,
    extensions: list[str] | None = None,
) -> list[Path]:
    """
    Recursively discover all videos inside a channel's input folder.

    Supports nested folders like:
        input/krgd_vlogs/trip_01/video1.mp4
        input/krgd_vlogs/trip_02/video2.mp4
    """
    if extensions is None:
        extensions = [".mp4", ".mov", ".avi", ".mkv"]

    input_dir = Path(channel_input_folder)
    if not input_dir.exists():
        return []

    videos = sorted(
        f for f in input_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in extensions
    )
    return videos


def get_clip_filename(
    video_name: str,
    part_number: int,
    extension: str = "mp4",
) -> str:
    """Generate a clip filename with zero-padded numbering."""
    safe_name = sanitize_filename(video_name)
    return f"{safe_name}_part{part_number:03d}.{extension}"


def get_next_part_number(output_dir: Path, video_name: str) -> int:
    """Get the next available part number for a video."""
    safe_name = sanitize_filename(video_name)
    existing = list(output_dir.glob(f"{safe_name}_part*.mp4"))
    if not existing:
        return 1
    numbers = []
    pattern = re.compile(rf"{re.escape(safe_name)}_part(\d+)\.mp4")
    for f in existing:
        match = pattern.match(f.name)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers) + 1 if numbers else 1


def probe_video(video_path: Path) -> dict[str, Any]:
    """Probe video file using ffprobe and return metadata."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.error("ffprobe_failed", path=str(video_path), error=str(e))
        return {}


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds."""
    info = probe_video(video_path)
    if "format" in info and "duration" in info["format"]:
        return float(info["format"]["duration"])
    # Fallback: check streams
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video" and "duration" in stream:
            return float(stream["duration"])
    return 0.0


def get_video_resolution(video_path: Path) -> tuple[int, int]:
    """Get video width and height."""
    info = probe_video(video_path)
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            return int(stream["width"]), int(stream["height"])
    return 0, 0


def get_video_fps(video_path: Path) -> float:
    """Get video frame rate."""
    info = probe_video(video_path)
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            fps_str = stream.get("r_frame_rate", "30/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                return float(num) / float(den) if float(den) > 0 else 30.0
            return float(fps_str)
    return 30.0


def check_gpu_available() -> bool:
    """Check if NVIDIA GPU with NVENC is available."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
        )
        return "h264_nvenc" in result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def ensure_ffmpeg() -> bool:
    """Verify ffmpeg is installed and accessible."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
