"""Vlog pipeline: mixed-media long-form creation and platform-specific exports."""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ExifTags, ImageDraw, ImageFont

from app.utils.config import get_config
from app.utils.files import get_video_duration, probe_video, sanitize_filename
from app.utils.logging import get_logger
from app.motion_detector import MotionDetector
from app.scene_detector import SceneDetector

logger = get_logger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}

EXIF_DATETIME_TAGS = {
    "DateTimeOriginal",
    "DateTimeDigitized",
    "DateTime",
}

VOICE_AUDIO_CHAIN = (
    "aformat=sample_fmts=fltp:channel_layouts=stereo,"
    "aresample=48000,"
    "highpass=f=150,"
    "lowpass=f=8000,"
    "afftdn=nf=-28:tr=1:om=o,"
    "equalizer=f=200:t=q:w=0.9:g=-4,"
    "equalizer=f=1200:t=q:w=1.2:g=3.5,"
    "equalizer=f=3500:t=q:w=1.1:g=2,"
    "acompressor=threshold=0.06:ratio=3.5:attack=10:release=150:makeup=5,"
    "alimiter=limit=0.95"
)

BG_AUDIO_CHAIN = (
    "aformat=sample_fmts=fltp:channel_layouts=stereo,"
    "aresample=48000,"
    "highpass=f=200,"
    "lowpass=f=5500,"
    "afftdn=nf=-22"
)


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


@dataclass
class ScenicClipCandidate:
    video_path: Path
    start: float
    end: float
    score: float


def _create_trip_title_overlay(title_text: str, output_path: Path, width: int = 900, height: int = 180) -> Path:
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        [(0, 0), (width - 1, height - 1)],
        radius=28,
        outline=(255, 54, 26, 255),
        width=5,
        fill=(255, 255, 255, 230),
    )

    font_path = Path("assets/fonts/Montserrat-Bold.ttf")
    try:
        font = ImageFont.truetype(str(font_path), 56) if font_path.exists() else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    text = " ".join((title_text or "").split())
    words = text.split()
    if len(words) > 8:
        text = " ".join(words[:8])
        words = text.split()

    lines = [text] if text else ["Trip Highlight"]
    if len(words) >= 6:
        mid = len(words) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]

    heights: list[int] = []
    widths: list[int] = []
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        widths.append(bb[2] - bb[0])
        heights.append(bb[3] - bb[1])

    total_h = sum(heights) + (10 if len(lines) > 1 else 0)
    y = (height - total_h) // 2
    for idx, line in enumerate(lines):
        x = (width - widths[idx]) // 2
        draw.text((x, y), line, fill=(20, 20, 20, 255), font=font)
        y += heights[idx] + (10 if idx < len(lines) - 1 else 0)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return output_path


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


def _get_video_dimensions(video_path: Path) -> tuple[int, int]:
    """Return the (width, height) of the first video stream, or (0, 0)."""
    info = probe_video(video_path)
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            return int(stream.get("width") or 0), int(stream.get("height") or 0)
    return 0, 0


def _normalize_video_segment(
    item: MediaItem,
    output_path: Path,
    width: int,
    height: int,
    fps: int,
    blur_bg: bool,
    overlay_path: Path | None = None,
) -> None:
    src_w, src_h = _get_video_dimensions(item.path)
    target_ar = (width / height) if height else 0.0
    src_ar = (src_w / src_h) if src_h else target_ar
    # Skip the blurred-background pillarbox when the source already matches the
    # output aspect ratio (e.g. 16:9 GoPro footage -> 16:9 4K). A plain
    # scale-to-fit preserves the raw frame and avoids two extra scales + boxblur.
    aspect_matches = target_ar > 0 and abs(src_ar - target_ar) <= 0.02

    if aspect_matches:
        filter_complex = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1[vbase]"
        )
    else:
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
        # Socials watermark sits in the TOP-RIGHT corner (40px margin).
        filter_complex += (
            f";[1:v]scale={overlay_w}:-1,format=rgba,colorchannelmixer=aa=0.88[wm]"
            f";[wm]split=2[wm_main][wm_glow_src]"
            f";[wm_glow_src]gblur=sigma=10,colorchannelmixer=aa=0.55[wm_glow]"
            f";[vbase][wm_glow]overlay=W-w-40:40[vtmp]"
            f";[vtmp][wm_main]overlay=W-w-40:40[vout]"
        )
    else:
        filter_complex += ";[vbase]copy[vout]"

    has_audio = _has_audio_stream(item.path)

    if has_audio:
        filter_complex += f";[0:a]{VOICE_AUDIO_CHAIN}[aout]"
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
        ])
    else:
        # Silent source: append an anullsrc track. Its input index depends on
        # whether the overlay image already occupies input slot 1.
        anull_idx = 2 if has_overlay else 1
        cmd.extend([
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", f"{anull_idx}:a",
            "-shortest",
        ])

    cmd.extend([
        "-r", str(fps),
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "16",
        "-c:a", "aac",
        "-b:a", "320k",
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
            f";[2:v]scale={overlay_w}:-1,format=rgba,colorchannelmixer=aa=0.88[wm]"
            f";[wm]split=2[wm_main][wm_glow_src]"
            f";[wm_glow_src]gblur=sigma=10,colorchannelmixer=aa=0.55[wm_glow]"
            f";[vbase][wm_glow]overlay=W-w-40:40[vtmp]"
            f";[vtmp][wm_main]overlay=W-w-40:40[vout]"
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
                "-preset", "slow",
                "-crf", "16",
                "-c:a", "aac",
                "-b:a", "320k",
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


def _select_scenic_candidates(
    video_path: Path,
    clip_duration: float,
    max_per_video: int,
) -> list[ScenicClipCandidate]:
    scene_detector = SceneDetector(threshold=24.0, min_scene_len=12)
    motion_detector = MotionDetector(sample_rate=3, motion_threshold=0.25, min_segment_duration=2.0)

    try:
        scene_analysis = scene_detector.detect(video_path)
    except Exception as exc:
        logger.warning("scenic_scene_detect_failed", video=str(video_path), error=str(exc))
        return []

    try:
        motion_analysis = motion_detector.analyze(video_path)
    except Exception as exc:
        logger.warning("scenic_motion_detect_failed", video=str(video_path), error=str(exc))
        motion_analysis = None

    candidates: list[ScenicClipCandidate] = []
    for scene in scene_analysis.scenes:
        if scene.duration < clip_duration:
            continue

        # Scenic views are usually stable or moderately dynamic.
        motion_score = 0.5
        if motion_analysis:
            motion_score = motion_detector.get_excitement_score(motion_analysis, scene.start, scene.end)
        scenic_motion_score = 1.0 - min(abs(motion_score - 0.28) / 0.28, 1.0)
        duration_score = min(scene.duration / 12.0, 1.0)
        score = (scenic_motion_score * 0.7) + (duration_score * 0.3)

        start = scene.start + max(0.0, (scene.duration - clip_duration) / 2.0)
        end = min(start + clip_duration, scene.end)
        if end - start < clip_duration:
            start = max(scene.start, end - clip_duration)

        candidates.append(
            ScenicClipCandidate(
                video_path=video_path,
                start=start,
                end=end,
                score=score,
            )
        )

    candidates.sort(key=lambda item: item.score, reverse=True)

    if not candidates:
        # Fallback: evenly sample scenic windows so every trip can produce a reel.
        duration = get_video_duration(video_path)
        if duration > clip_duration:
            usable = max(0.0, duration - clip_duration)
            slots = max(1, max_per_video)
            step = usable / slots if slots > 0 else usable
            for i in range(slots):
                start = min(usable, i * step)
                end = start + clip_duration
                candidates.append(
                    ScenicClipCandidate(
                        video_path=video_path,
                        start=start,
                        end=end,
                        score=0.35,
                    )
                )

    selected = candidates[:max_per_video]
    selected.sort(key=lambda item: item.start)
    return selected


def create_trip_scenic_highlight(
    trip_folder: Path,
    ordered_videos: list[Path],
    output_path: Path,
    clip_duration: float = 4.0,
    max_total_clips: int = 10,
    max_per_video: int = 5,
    socials_overlay_path: Path | None = None,
    title_text: str | None = None,
    include_source_audio: bool = False,
    bgm_subdir: str | None = None,
) -> Path | None:
    """Build a scenic highlight by stitching 4s scenic clips with fade transitions."""
    if not ordered_videos:
        return None

    all_candidates: list[ScenicClipCandidate] = []
    for video_path in ordered_videos:
        all_candidates.extend(_select_scenic_candidates(video_path, clip_duration=clip_duration, max_per_video=max_per_video))

    if not all_candidates:
        logger.warning("scenic_highlight_skipped", trip=str(trip_folder), reason="no_candidates")
        return None

    # Keep highest quality candidates, then restore timeline order for natural storytelling.
    all_candidates.sort(key=lambda item: item.score, reverse=True)
    selected = all_candidates[:max_total_clips]
    selected.sort(key=lambda item: (str(item.video_path), item.start))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_video = output_path.with_name(f"{output_path.stem}_tmp_noaudio.mp4")

    cmd = ["ffmpeg", "-y"]
    for clip in selected:
        cmd.extend([
            "-ss", f"{clip.start:.3f}",
            "-t", f"{clip_duration:.3f}",
            "-i", str(clip.video_path),
        ])

    tmp_title_overlay = output_path.with_name(f"{output_path.stem}_title_overlay.png")
    has_title = False
    if title_text:
        _create_trip_title_overlay(title_text=title_text, output_path=tmp_title_overlay)
        if tmp_title_overlay.exists():
            cmd.extend(["-i", str(tmp_title_overlay)])
            has_title = True

    has_socials = socials_overlay_path is not None and socials_overlay_path.exists()
    if has_socials:
        cmd.extend(["-i", str(socials_overlay_path)])

    # Use parameter-controlled audio inclusion for special clips; auto-detect for standard scenic
    use_audio = include_source_audio and all(_has_audio_stream(clip.video_path) for clip in selected)

    filter_parts: list[str] = []
    for idx, _clip in enumerate(selected):
        fade_out_start = max(0.0, clip_duration - 0.35)
        filter_parts.append(
            f"[{idx}:v]"
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "boxblur=40:20,"
            f"crop=1080:1920[bg{idx}]"
        )
        filter_parts.append(
            f"[{idx}:v]"
            f"scale=1080:1920:force_original_aspect_ratio=decrease[fg{idx}]"
        )
        filter_parts.append(
            f"[bg{idx}][fg{idx}]overlay=(W-w)/2:(H-h)/2,"
            "fps=30,"
            "format=yuv420p,"
            "fade=t=in:st=0:d=0.35,"
            f"fade=t=out:st={fade_out_start:.2f}:d=0.35,"
            f"setpts=PTS-STARTPTS[v{idx}]"
        )
        if use_audio:
            filter_parts.append(
                f"[{idx}:a]"
                f"{VOICE_AUDIO_CHAIN},"
                "afade=t=in:st=0:d=0.22,"
                f"afade=t=out:st={fade_out_start:.2f}:d=0.22,"
                f"asetpts=PTS-STARTPTS[a{idx}]"
            )

    concat_inputs = "".join([f"[v{idx}]" for idx in range(len(selected))])
    if use_audio:
        concat_av_inputs = "".join([f"[v{idx}][a{idx}]" for idx in range(len(selected))])
        filter_parts.append(f"{concat_av_inputs}concat=n={len(selected)}:v=1:a=1[vcat][acat]")
    else:
        filter_parts.append(f"{concat_inputs}concat=n={len(selected)}:v=1:a=0[vcat]")

    current = "[vcat]"
    input_idx = len(selected)

    if has_title:
        filter_parts.append(f"[{input_idx}:v]format=rgba[trip_title]")
        filter_parts.append(f"{current}[trip_title]overlay=(W-w)/2:70[vtitle]")
        current = "[vtitle]"
        input_idx += 1

    if has_socials:
        filter_parts.append(f"[{input_idx}:v]scale=750:-1,format=rgba,colorchannelmixer=aa=0.92[soc]")
        filter_parts.append("[soc]split=2[soc_main][soc_glow_src]")
        filter_parts.append("[soc_glow_src]gblur=sigma=10,colorchannelmixer=aa=0.25[soc_glow]")
        filter_parts.append(f"{current}[soc_glow]overlay=(W-w)/2:H-h-240[vsocglow]")
        filter_parts.append("[vsocglow][soc_main]overlay=(W-w)/2:H-h-250[vout]")
    else:
        filter_parts.append(f"{current}copy[vout]")

    cmd.extend(["-filter_complex", ";".join(filter_parts), "-map", "[vout]"])
    if use_audio:
        cmd.extend(["-map", "[acat]"])
    else:
        cmd.append("-an")
    cmd.extend([
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "16",
        "-c:a", "aac",
        "-b:a", "320k",
        "-movflags", "+faststart",
        str(tmp_video),
    ])

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        bg_tracks = _discover_bgm_tracks(bgm_subdir)
        if bg_tracks:
            bg_track = bg_tracks[0]  # Use first track consistently
            audio_cmd = [
                "ffmpeg",
                "-y",
                "-i", str(tmp_video),
                "-stream_loop", "-1",
                "-i", str(bg_track),
                "-filter_complex",
                "[1:a]aformat=sample_fmts=fltp:channel_layouts=stereo,aresample=48000,"
                "highpass=f=40,volume=0.50,alimiter=limit=0.95[aout]",
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "256k",
                "-shortest",
                "-movflags", "+faststart",
                str(output_path),
            ]
            subprocess.run(audio_cmd, check=True, capture_output=True, text=True)
            tmp_video.unlink(missing_ok=True)
        else:
            tmp_video.replace(output_path)

        logger.info(
            "scenic_highlight_generated",
            trip=str(trip_folder),
            output=str(output_path),
            clips=len(selected),
            duration=f"{len(selected) * clip_duration:.1f}s",
        )
        return output_path
    except subprocess.CalledProcessError as exc:
        logger.error(
            "scenic_highlight_failed",
            trip=str(trip_folder),
            error=exc.stderr[-300:] if exc.stderr else str(exc),
        )
        tmp_video.unlink(missing_ok=True)
        tmp_title_overlay.unlink(missing_ok=True)
        return None
    finally:
        tmp_title_overlay.unlink(missing_ok=True)


def _copy_as_platform_variant(source: Path, suffix: str) -> Path:
    destination = source.with_name(f"{source.stem}_{suffix}.mp4")
    shutil.copy2(source, destination)
    return destination


def _discover_bgm_tracks(subdir: str | None = None) -> list[Path]:
    """Discover background-music tracks.

    - With ``subdir`` (e.g. "yt" or "insta"): use tracks from
      ``assets/bgmusic/<subdir>`` (recursively). Falls back to the root pool
      if that subfolder has no tracks yet.
    - Without ``subdir``: only top-level files in ``assets/bgmusic`` so the
      ``yt``/``insta`` subfolders stay isolated from the default flow.
    """
    base = Path("assets") / "bgmusic"
    extensions = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}

    def _collect(folder: Path, recursive: bool) -> list[Path]:
        if not folder.exists():
            return []
        entries = folder.rglob("*") if recursive else folder.glob("*")
        return [
            p for p in sorted(entries)
            if p.is_file() and p.suffix.lower() in extensions
        ]

    if subdir:
        tracks = _collect(base / subdir, recursive=True)
        if tracks:
            return tracks
        # Subfolder missing/empty -> fall back to the general root pool.
        return _collect(base, recursive=False)

    return _collect(base, recursive=False)


def _add_background_music(
    source_clip: Path,
    destination_clip: Path,
    bg_track: Path,
    bg_volume: float,
    bg_offset_seconds: float = 0.0,
) -> tuple[bool, str | None]:
    bg_gain = max(0.0, min(float(bg_volume), 1.0))
    bg_seek = max(0.0, float(bg_offset_seconds))

    # Instagram reels are music-forward: replace the clip's audio entirely with
    # the background song so it is clearly audible (no buried original voice).
    # The clean music track only needs a gentle highpass + limiter, not the
    # ambient noise-reduction chain used for spoken bike audio.
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(source_clip),
        "-stream_loop", "-1",
        "-ss", f"{bg_seek:.3f}",
        "-i", str(bg_track),
        "-filter_complex",
        f"[1:a]aformat=sample_fmts=fltp:channel_layouts=stereo,aresample=48000,"
        f"highpass=f=40,volume={bg_gain:.3f},alimiter=limit=0.95[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "256k",
        "-shortest",
        "-movflags", "+faststart",
        str(destination_clip),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True, None
    except subprocess.CalledProcessError as exc:
        # Retry with video re-encode for clips/codecs that cannot stream-copy cleanly.
        retry_cmd = list(cmd)
        if "copy" in retry_cmd:
            copy_idx = retry_cmd.index("copy")
            retry_cmd[copy_idx] = "libx264"
            retry_cmd.extend(["-preset", "slow", "-crf", "16"])
        try:
            subprocess.run(retry_cmd, check=True, capture_output=True, text=True)
            return True, None
        except subprocess.CalledProcessError as retry_exc:
            return False, (retry_exc.stderr[-300:] if retry_exc.stderr else str(retry_exc))


def apply_music_only_audio(
    video_path: Path,
    bgm_subdir: str,
    bg_volume: float = 0.5,
) -> bool:
    """Replace a video's audio entirely with a background-music track.

    Used by the music-only vlog workflow (e.g. long-form). Returns True when the
    audio was successfully swapped, False if no track was available or the mux
    failed (in which case the original file is left untouched).
    """
    tracks = _discover_bgm_tracks(bgm_subdir)
    if not tracks:
        logger.warning("music_only_no_tracks", video=str(video_path), subdir=bgm_subdir)
        return False

    tmp_path = video_path.with_name(f"{video_path.stem}_musiconly_tmp.mp4")
    ok, error = _add_background_music(
        source_clip=video_path,
        destination_clip=tmp_path,
        bg_track=tracks[0],
        bg_volume=bg_volume,
        bg_offset_seconds=0.0,
    )
    if ok and tmp_path.exists():
        tmp_path.replace(video_path)
        return True

    tmp_path.unlink(missing_ok=True)
    logger.warning("music_only_mux_failed", video=str(video_path), error=error)
    return False


def create_platform_exports(
    short_clips: list[Path],
    output_dir: Path,
    music_only: bool = False,
) -> PlatformExportResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    yt_dir = output_dir / "YT"
    insta_dir = output_dir / "insta"
    yt_dir.mkdir(parents=True, exist_ok=True)
    insta_dir.mkdir(parents=True, exist_ok=True)

    config = get_config()
    # Instagram always replaces audio with music; in music-only mode YouTube does too.
    insta_bg_tracks = _discover_bgm_tracks("insta") if music_only else _discover_bgm_tracks()
    yt_bg_tracks = _discover_bgm_tracks("yt") if music_only else []
    bg_volume = 0.55  # Subtle but clearly audible music-only volume

    yt_exports: list[Path] = []
    insta_exports: list[Path] = []
    mixed_tracks: list[dict[str, Any]] = []

    for idx, short_clip in enumerate(short_clips):
        yt_out = yt_dir / f"{short_clip.stem}.mp4"
        bg_offset_seconds = float(idx * 30)

        if music_only and yt_bg_tracks:
            # YouTube short: drop raw audio, use the YT music pool.
            yt_track = yt_bg_tracks[idx % len(yt_bg_tracks)] if len(yt_bg_tracks) > 1 else yt_bg_tracks[0]
            ok, error = _add_background_music(
                source_clip=short_clip,
                destination_clip=yt_out,
                bg_track=yt_track,
                bg_volume=bg_volume,
                bg_offset_seconds=bg_offset_seconds,
            )
            if ok:
                mixed_tracks.append(
                    {
                        "clip": str(yt_out),
                        "platform": "youtube",
                        "bg_track": str(yt_track),
                        "bg_volume": bg_volume,
                        "bg_offset_seconds": bg_offset_seconds,
                    }
                )
            else:
                logger.warning("yt_bgm_mix_failed", clip=str(yt_out), error=error)
                shutil.copy2(short_clip, yt_out)
        else:
            # Default: keep the rendered short's (raw) audio for YouTube.
            shutil.copy2(short_clip, yt_out)
        yt_exports.append(yt_out)

        insta_out = insta_dir / f"{short_clip.stem}.mp4"
        if insta_bg_tracks:
            bg_track = insta_bg_tracks[idx % len(insta_bg_tracks)] if len(insta_bg_tracks) > 1 else insta_bg_tracks[0]
            ok, error = _add_background_music(
                source_clip=yt_out,
                destination_clip=insta_out,
                bg_track=bg_track,
                bg_volume=bg_volume,
                bg_offset_seconds=bg_offset_seconds,
            )
            if ok:
                mixed_tracks.append(
                    {
                        "clip": str(insta_out),
                        "platform": "instagram",
                        "bg_track": str(bg_track),
                        "bg_volume": bg_volume,
                        "bg_offset_seconds": bg_offset_seconds,
                    }
                )
            else:
                logger.warning(
                    "insta_bgm_mix_failed",
                    clip=str(insta_out),
                    error=error,
                )
                # Fallback: copy without audio, then add BGM via simple mix
                shutil.copy2(yt_out, insta_out)
                mixed_tracks.append(
                    {
                        "clip": str(insta_out),
                        "platform": "instagram",
                        "bg_track": str(bg_track),
                        "bg_volume": bg_volume,
                        "bg_offset_seconds": bg_offset_seconds,
                        "warning": f"mix_failed_fallback: {error}",
                    }
                )
        else:
            logger.warning("no_bgm_tracks_found", output=str(output_dir))
            shutil.copy2(yt_out, insta_out)
            mixed_tracks.append(
                {
                    "clip": str(insta_out),
                    "platform": "instagram",
                    "bg_track": "none_found",
                }
            )
        insta_exports.append(insta_out)

        # Keep only platform variants in dedicated folders; remove raw root mp4 clip.
        try:
            short_clip.unlink(missing_ok=True)
        except OSError:
            logger.warning("raw_short_cleanup_failed", clip=str(short_clip))

    # Migrate legacy root platform files into dedicated folders.
    for legacy in output_dir.glob("*_yt.mp4"):
        try:
            target = yt_dir / legacy.name.replace("_yt.mp4", ".mp4")
            shutil.move(str(legacy), str(target))
        except OSError:
            logger.warning("legacy_yt_migration_failed", file=str(legacy))

    for legacy in output_dir.glob("*_insta.mp4"):
        try:
            target = insta_dir / legacy.name.replace("_insta.mp4", ".mp4")
            shutil.move(str(legacy), str(target))
        except OSError:
            logger.warning("legacy_insta_migration_failed", file=str(legacy))

    # Keep root output clean: retain platform folders and remove root raw short videos.
    root_raw_patterns = [
        "*_part*.mp4",
        "*_part*.mov",
        "*_part*.mkv",
        "*_part*.srt",
        "*_part*.ass",
        "*_part*.json",
    ]
    for pattern in root_raw_patterns:
        for root_file in output_dir.glob(pattern):
            if not root_file.is_file():
                continue
            try:
                root_file.unlink(missing_ok=True)
            except OSError:
                logger.warning("root_raw_clip_cleanup_failed", clip=str(root_file))

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
