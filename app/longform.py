"""Long-form video generation — merges subfolder clips into full vlog videos."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.utils.files import get_video_duration, probe_video
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LongformResult:
    """Result of a long-form video merge."""
    output_path: Path
    success: bool
    input_count: int
    input_duration: float  # total input seconds
    output_duration: float  # final output seconds
    processing_time: float  # seconds to render
    file_size: int  # bytes
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def sort_gopro_chronological(videos: list[Path]) -> list[Path]:
    """
    Sort GoPro videos in chronological order.

    GoPro naming: GHxxyyyy.MP4 where xx=chapter, yyyy=video_number.
    Sort by video_number first, then chapter, so chapters play in sequence.
    Falls back to file modification time for non-GoPro filenames.
    """
    gopro_pattern = re.compile(r"^GH(\d{2})(\d{4})\.", re.IGNORECASE)

    def sort_key(path: Path) -> tuple:
        match = gopro_pattern.match(path.name)
        if match:
            chapter = int(match.group(1))
            video_num = int(match.group(2))
            return (0, video_num, chapter)
        # Fallback: sort by modification time
        return (1, os.path.getmtime(path), 0)

    return sorted(videos, key=sort_key)


def generate_longform(
    videos: list[Path],
    output_path: Path,
    overlay_path: Path | None = None,
    overlay_opacity: float = 0.6,
    overlay_scale: float = 0.15,
) -> LongformResult:
    """
    Merge multiple video files into one long-form 16:9 video.

    Args:
        videos: List of input video paths (will be sorted chronologically).
        output_path: Path for the merged output file.
        overlay_path: Optional social branding image for top-left watermark.
        overlay_opacity: Opacity of the watermark (0.0-1.0).
        overlay_scale: Scale of overlay relative to video width.

    Returns:
        LongformResult with details of the merge.
    """
    start_time = time.time()
    sorted_videos = sort_gopro_chronological(videos)

    # Validate inputs and compute durations
    valid_videos: list[Path] = []
    skipped: list[str] = []
    total_input_duration = 0.0

    for v in sorted_videos:
        if not v.exists():
            skipped.append(f"{v.name}: file not found")
            continue
        dur = get_video_duration(v)
        if dur <= 0:
            skipped.append(f"{v.name}: could not determine duration")
            continue
        valid_videos.append(v)
        total_input_duration += dur

    if not valid_videos:
        return LongformResult(
            output_path=output_path,
            success=False,
            input_count=len(videos),
            input_duration=0,
            output_duration=0,
            processing_time=time.time() - start_time,
            file_size=0,
            skipped=skipped,
            errors=["No valid input videos found"],
        )

    # Create output directory
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build FFmpeg concat file
    tmp_dir = Path(tempfile.gettempdir()) / "shorts_longform"
    tmp_dir.mkdir(exist_ok=True)
    concat_file = tmp_dir / f"concat_{os.getpid()}.txt"

    with open(concat_file, "w") as f:
        for v in valid_videos:
            # Escape single quotes in paths for FFmpeg concat format
            safe_path = str(v.resolve()).replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

    source_has_audio = False
    for v in valid_videos:
        info = probe_video(v)
        if any(stream.get("codec_type") == "audio" for stream in info.get("streams", [])):
            source_has_audio = True
            break

    # Build FFmpeg command
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]

    # Add overlay input if provided
    overlay_input_idx = None
    if overlay_path and overlay_path.exists():
        cmd.extend(["-i", str(overlay_path)])
        overlay_input_idx = 1

    # Build filter complex
    filter_parts: list[str] = []

    if overlay_input_idx is not None:
        # Scale overlay to percentage of video width, position top-left with padding
        filter_parts.append(
            f"[{overlay_input_idx}:v]"
            f"scale=iw*{overlay_scale}/(iw/1920):-1,"
            f"format=rgba,"
            f"colorchannelmixer=aa={overlay_opacity}[watermark]"
        )
        filter_parts.append(
            "[0:v][watermark]overlay=30:30[vout]"
        )
        cmd.extend(["-filter_complex", ";".join(filter_parts)])
        cmd.extend(["-map", "[vout]", "-map", "0:a?"])
    else:
        cmd.extend(["-c", "copy"])

    if source_has_audio:
        cmd.extend([
            "-af",
            "highpass=f=80,"
            "lowpass=f=9000,"
            "afftdn=nf=-20,"
            "equalizer=f=220:t=q:w=1.1:g=-2,"
            "equalizer=f=2800:t=q:w=1.0:g=2,"
            "acompressor=threshold=0.09:ratio=2.2:attack=15:release=220:makeup=3,"
            "alimiter=limit=0.96",
        ])

    # Output settings — high quality for long-form (YouTube optimized 1080p)
    if overlay_input_idx is not None:
        # Re-encode needed when applying overlay
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "slower",
            "-crf", "14",
            "-maxrate", "40000k",
            "-bufsize", "80000k",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "320k",
            "-movflags", "+faststart",
        ])
    else:
        # Re-encode anyway for quality consistency (no stream copy)
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "slower",
            "-crf", "14",
            "-maxrate", "40000k",
            "-bufsize", "80000k",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "320k",
            "-movflags", "+faststart",
        ])

    cmd.append(str(output_path))

    logger.info(
        "longform_rendering",
        input_count=len(valid_videos),
        total_duration=f"{total_input_duration:.1f}s",
        output=str(output_path),
    )

    # Execute
    errors: list[str] = []
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600 * 4,  # 4 hour timeout for very long videos
        )
        if result.returncode != 0:
            errors.append(f"FFmpeg error: {result.stderr[-500:]}")
            logger.error("longform_ffmpeg_failed", stderr=result.stderr[-300:])
    except subprocess.TimeoutExpired:
        errors.append("FFmpeg timed out after 4 hours")
    except Exception as e:
        errors.append(f"Unexpected error: {e}")
    finally:
        # Clean up concat file
        concat_file.unlink(missing_ok=True)

    # Get output info
    output_duration = 0.0
    file_size = 0
    if output_path.exists():
        output_duration = get_video_duration(output_path)
        file_size = output_path.stat().st_size

    processing_time = time.time() - start_time

    success = output_path.exists() and file_size > 0 and not errors

    if success:
        logger.info(
            "longform_complete",
            output=str(output_path),
            duration=f"{output_duration:.1f}s",
            size_mb=f"{file_size / 1024 / 1024:.1f}",
            time=f"{processing_time:.1f}s",
        )

    return LongformResult(
        output_path=output_path,
        success=success,
        input_count=len(valid_videos),
        input_duration=total_input_duration,
        output_duration=output_duration,
        processing_time=processing_time,
        file_size=file_size,
        skipped=skipped,
        errors=errors,
    )


def discover_subfolders(channel_input_folder: str, extensions: list[str] | None = None) -> dict[str, list[Path]]:
    """
    Discover subfolders and their videos for long-form generation.

    Returns a dict mapping subfolder name -> sorted list of video paths.
    """
    if extensions is None:
        extensions = [".mp4", ".mov", ".avi", ".mkv"]

    input_dir = Path(channel_input_folder)
    if not input_dir.exists():
        return {}

    subfolders: dict[str, list[Path]] = {}

    for item in sorted(input_dir.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith("."):
            continue
        videos = sorted(
            f for f in item.iterdir()
            if f.is_file() and f.suffix.lower() in extensions
        )
        if videos:
            subfolders[item.name] = videos

    return subfolders
