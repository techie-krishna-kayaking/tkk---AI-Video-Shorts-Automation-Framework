"""Vlog pipeline: mixed-media long-form creation and platform-specific exports."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ExifTags

from app.utils.config import get_config
from app.utils.files import get_video_duration, probe_video, sanitize_filename
from app.utils.logging import get_logger

logger = get_logger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}

EXIF_DATETIME_TAGS = {
    "DateTimeOriginal",
    "DateTimeDigitized",
    "DateTime",
}


@dataclass
class MediaItem:
    path: Path
    kind: str  # video | photo
    timestamp: datetime
    timestamp_source: str
    order_index: int


@dataclass
class TripLongformResult:
    output_path: Path
    timeline: list[MediaItem]
    success: bool
    errors: list[str]


@dataclass
class PlatformExportResult:
    youtube_exports: list[Path]
    instagram_exports: list[Path]
    source_shorts: list[Path]
    mixed_tracks: list[dict[str, Any]]


# Backward-compatible result alias.
VlogLongformResult = TripLongformResult


def _parse_dt(value: str) -> datetime | None:
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _get_image_capture_time(path: Path) -> datetime | None:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            for tag_id, raw_value in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, "")
                if tag_name not in EXIF_DATETIME_TAGS:
                    continue
                if not isinstance(raw_value, str):
                    continue
                parsed = _parse_dt(raw_value.strip())
                if parsed:
                    return parsed
    except Exception:
        return None
    return None


def _get_video_capture_time(path: Path) -> datetime | None:
    info = probe_video(path)
    tags = info.get("format", {}).get("tags", {})

    creation_time = tags.get("creation_time") or tags.get("com.apple.quicktime.creationdate")
    if isinstance(creation_time, str):
        cleaned = creation_time.replace("Z", "").split("+")[0].strip()
        # Handle QuickTime format like 2026-05-15T09:12:44.000000
        cleaned = cleaned.split(".")[0]
        parsed = _parse_dt(cleaned)
        if parsed:
            return parsed

    for stream in info.get("streams", []):
        st_tags = stream.get("tags", {})
        creation_time = st_tags.get("creation_time")
        if not isinstance(creation_time, str):
            continue
        cleaned = creation_time.replace("Z", "").split("+")[0].strip().split(".")[0]
        parsed = _parse_dt(cleaned)
        if parsed:
            return parsed

    return None


def _get_stat_times(path: Path) -> tuple[datetime | None, datetime | None]:
    try:
        st = path.stat()
    except OSError:
        return None, None

    created_ts = getattr(st, "st_birthtime", None)
    created = datetime.fromtimestamp(created_ts) if created_ts else datetime.fromtimestamp(st.st_ctime)
    modified = datetime.fromtimestamp(st.st_mtime)
    return created, modified


def _resolve_media_timestamp(path: Path, kind: str) -> tuple[datetime, str]:
    captured: datetime | None = None
    if kind == "photo":
        captured = _get_image_capture_time(path)
        if captured:
            return captured, "metadata_exif"
    else:
        captured = _get_video_capture_time(path)
        if captured:
            return captured, "metadata_video"

    created, modified = _get_stat_times(path)
    if created:
        return created, "file_created"
    if modified:
        return modified, "file_modified"

    return datetime.fromtimestamp(0), "fallback_epoch"


def discover_trip_media(folder: Path) -> list[MediaItem]:
    if not folder.exists():
        return []

    media_files: list[Path] = []
    for file_path in sorted(folder.rglob("*")):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        if suffix in VIDEO_EXTENSIONS or suffix in PHOTO_EXTENSIONS:
            media_files.append(file_path)

    timeline: list[MediaItem] = []
    for idx, path in enumerate(media_files):
        kind = "video" if path.suffix.lower() in VIDEO_EXTENSIONS else "photo"
        timestamp, source = _resolve_media_timestamp(path, kind)
        timeline.append(
            MediaItem(
                path=path,
                kind=kind,
                timestamp=timestamp,
                timestamp_source=source,
                order_index=idx,
            )
        )

    timeline.sort(key=lambda item: (item.timestamp, item.order_index))

    for pos, item in enumerate(timeline, 1):
        logger.info(
            "trip_timeline_item",
            order=pos,
            file=str(item.path),
            kind=item.kind,
            timestamp=item.timestamp.isoformat(sep=" "),
            timestamp_source=item.timestamp_source,
        )

    return timeline


def discover_vlog_media(folder: Path) -> list[MediaItem]:
    """Discover and timestamp-sort mixed media for any vlog folder."""
    return discover_trip_media(folder)


def _has_audio_stream(video_path: Path) -> bool:
    info = probe_video(video_path)
    return any(stream.get("codec_type") == "audio" for stream in info.get("streams", []))


def _normalize_video_segment(
    item: MediaItem,
    output_path: Path,
    width: int,
    height: int,
    fps: int,
    blur_bg: bool,
    overlay_path: Path | None = None,
) -> None:
    filter_complex = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase"
        + (",boxblur=40:20" if blur_bg else "")
        + f",crop={width}:{height}[bg];"
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[vbase]"
    )

    cmd = ["ffmpeg", "-y", "-i", str(item.path)]
    has_overlay = overlay_path is not None and overlay_path.exists()
    if has_overlay:
        cmd.extend(["-i", str(overlay_path)])
        overlay_w = max(120, int(width * 0.22))
        filter_complex += (
            f";[1:v]scale={overlay_w}:-1,format=rgba,colorchannelmixer=aa=0.72[wm]"
            f";[vbase][wm]overlay=40:40[vout]"
        )
    else:
        filter_complex += ";[vbase]copy[vout]"

    if _has_audio_stream(item.path):
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "0:a",
        ])
    else:
        cmd.extend([
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "1:a",
            "-shortest",
        ])

    cmd.extend([
        "-r", str(fps),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        "-movflags", "+faststart",
        str(output_path),
    ])

    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _normalize_photo_segment(
    item: MediaItem,
    output_path: Path,
    width: int,
    height: int,
    fps: int,
    duration: float,
    blur_bg: bool,
    ken_burns_enabled: bool,
    overlay_path: Path | None = None,
) -> None:
    if ken_burns_enabled:
        overlay_expr = (
            "overlay="
            f"x='(W-w)/2 + 16*sin(2*PI*t/{max(duration, 0.1):.4f})':"
            f"y='(H-h)/2 + 10*cos(2*PI*t/{max(duration, 0.1):.4f})'"
        )
    else:
        overlay_expr = "overlay=(W-w)/2:(H-h)/2"

    filter_complex = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase"
        + (",boxblur=40:20" if blur_bg else "")
        + f",crop={width}:{height}[bg];"
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]{overlay_expr}[vbase]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-t", str(duration),
        "-i", str(item.path),
        "-f", "lavfi",
        "-t", str(duration),
        "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
    ]

    has_overlay = overlay_path is not None and overlay_path.exists()
    if has_overlay:
        cmd.extend(["-i", str(overlay_path)])
        overlay_w = max(120, int(width * 0.22))
        filter_complex += (
            f";[2:v]scale={overlay_w}:-1,format=rgba,colorchannelmixer=aa=0.72[wm]"
            f";[vbase][wm]overlay=40:40[vout]"
        )
    else:
        filter_complex += ";[vbase]copy[vout]"

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "1:a",
        "-r", str(fps),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ])

    subprocess.run(cmd, check=True, capture_output=True, text=True)


def create_trip_longform(
    trip_folder: Path,
    output_path: Path,
    overlay_path: Path | None = None,
) -> TripLongformResult:
    config = get_config()
    timeline = discover_trip_media(trip_folder)

    if not timeline:
        return TripLongformResult(output_path=output_path, timeline=[], success=False, errors=["No media found in trip folder"])

    output_path.parent.mkdir(parents=True, exist_ok=True)

    width = config.trip.output_width
    height = config.trip.output_height
    fps = config.video.fps

    tmp_root = Path(tempfile.gettempdir()) / f"trip_timeline_{os.getpid()}_{sanitize_filename(trip_folder.name)}"
    tmp_root.mkdir(parents=True, exist_ok=True)

    segment_files: dict[int, Path] = {}
    errors: list[str] = []

    max_workers = max(1, int(getattr(config.processing, "max_workers", 4)))

    def _render_segment(idx: int, item: MediaItem) -> tuple[int, Path | None, str | None]:
        segment_path = tmp_root / f"segment_{idx:04d}.mp4"
        logger.info(
            "trip_longform_add_media",
            order=idx,
            file=str(item.path),
            kind=item.kind,
            timestamp=item.timestamp.isoformat(sep=" "),
        )

        try:
            if item.kind == "video":
                _normalize_video_segment(
                    item=item,
                    output_path=segment_path,
                    width=width,
                    height=height,
                    fps=fps,
                    blur_bg=config.trip.blur_background_enabled,
                    overlay_path=overlay_path,
                )
            else:
                _normalize_photo_segment(
                    item=item,
                    output_path=segment_path,
                    width=width,
                    height=height,
                    fps=fps,
                    duration=max(0.5, float(config.trip.photo_duration)),
                    blur_bg=config.trip.blur_background_enabled,
                    ken_burns_enabled=config.trip.ken_burns_enabled,
                    overlay_path=overlay_path,
                )
            return idx, segment_path, None
        except subprocess.CalledProcessError as exc:
            logger.error("trip_longform_segment_failed", file=str(item.path), error=str(exc))
            err = f"{item.path.name}: {exc.stderr[-300:] if exc.stderr else str(exc)}"
            return idx, None, err

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(_render_segment, idx, item): idx
                for idx, item in enumerate(timeline, 1)
            }

            for future in as_completed(future_map):
                idx, segment_path, err = future.result()
                if err:
                    errors.append(err)
                    continue
                if segment_path:
                    segment_files[idx] = segment_path

        if not segment_files:
            return TripLongformResult(output_path=output_path, timeline=timeline, success=False, errors=errors or ["No media segments were rendered"])

        ordered_segments = [segment_files[idx] for idx in sorted(segment_files)]

        concat_file = tmp_root / "concat.txt"
        with open(concat_file, "w", encoding="utf-8") as handle:
            for segment in ordered_segments:
                safe_path = str(segment.resolve()).replace("'", "'\\''")
                handle.write(f"file '{safe_path}'\n")

        concat_cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            "-movflags", "+faststart",
            str(output_path),
        ]
        try:
            subprocess.run(concat_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            # Fallback keeps the workflow resilient if any segment-level stream params drift.
            logger.warning(
                "trip_longform_concat_copy_failed",
                output=str(output_path),
                error=exc.stderr[-300:] if exc.stderr else str(exc),
            )
            concat_fallback_cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-ac", "2",
                "-movflags", "+faststart",
                str(output_path),
            ]
            subprocess.run(concat_fallback_cmd, check=True, capture_output=True, text=True)

        logger.info(
            "trip_longform_generated",
            output=str(output_path),
            items=len(timeline),
            duration=f"{get_video_duration(output_path):.1f}s",
        )

        return TripLongformResult(output_path=output_path, timeline=timeline, success=True, errors=errors)
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr[-500:] if exc.stderr else str(exc)
        logger.error("trip_longform_failed", output=str(output_path), error=msg)
        errors.append(msg)
        return TripLongformResult(output_path=output_path, timeline=timeline, success=False, errors=errors)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def create_vlog_longform(
    vlog_folder: Path,
    output_path: Path,
    overlay_path: Path | None = None,
) -> VlogLongformResult:
    """Create chronological long-form video from mixed vlog media."""
    return create_trip_longform(
        trip_folder=vlog_folder,
        output_path=output_path,
        overlay_path=overlay_path,
    )


def _copy_as_platform_variant(source: Path, suffix: str) -> Path:
    destination = source.with_name(f"{source.stem}_{suffix}.mp4")
    shutil.copy2(source, destination)
    return destination


def create_platform_exports(short_clips: list[Path], output_dir: Path) -> PlatformExportResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    yt_exports: list[Path] = []
    insta_exports: list[Path] = []
    mixed_tracks: list[dict[str, Any]] = []

    for short_clip in short_clips:
        yt_out = _copy_as_platform_variant(short_clip, "yt")
        yt_exports.append(yt_out)

        # Keep Instagram variant generation without platform-specific audio mixing.
        insta_out = short_clip.with_name(f"{short_clip.stem}_insta.mp4")
        shutil.copy2(yt_out, insta_out)
        insta_exports.append(insta_out)

    logger.info(
        "platform_exports_complete",
        youtube_count=len(yt_exports),
        instagram_count=len(insta_exports),
        output=str(output_dir),
    )

    return PlatformExportResult(
        youtube_exports=yt_exports,
        instagram_exports=insta_exports,
        source_shorts=short_clips,
        mixed_tracks=mixed_tracks,
    )
