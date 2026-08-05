"""Long-form video generation — merges subfolder clips into full vlog videos."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from app.utils.config import get_config
from app.utils.files import get_video_duration, probe_video
from app.utils.logging import get_logger
from app.transcriber import Transcriber, Word
from app.silence_detector import SilenceDetector, SilenceInterval

logger = get_logger(__name__)

def _branding_values() -> tuple[float, float, int, int]:
    branding = get_config().branding
    return (
        branding.overlay_width_frac,
        branding.overlay_opacity,
        branding.longform_margin,
        branding.shorts_bottom_margin,
    )


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


def _ass_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _iter_words(segments) -> list[Word]:
    words: list[Word] = []
    for seg in segments:
        words.extend(seg.words)
    return words


def _build_keep_ranges(total_duration: float, silences: Iterable[SilenceInterval], min_keep: float = 0.08) -> list[tuple[float, float]]:
    """Convert silence ranges into non-silent keep ranges."""
    keep: list[tuple[float, float]] = []
    cursor = 0.0

    for s in sorted(silences, key=lambda x: x.start):
        start = max(0.0, float(s.start))
        end = min(total_duration, float(s.end))
        if start > cursor:
            if (start - cursor) >= min_keep:
                keep.append((cursor, start))
        cursor = max(cursor, end)

    if cursor < total_duration and (total_duration - cursor) >= min_keep:
        keep.append((cursor, total_duration))

    if not keep and total_duration > 0:
        keep.append((0.0, total_duration))

    return keep


def _merge_ranges(ranges: list[tuple[float, float]], join_gap: float = 0.05) -> list[tuple[float, float]]:
    if not ranges:
        return []
    src = sorted((max(0.0, s), max(0.0, e)) for s, e in ranges if e > s)
    merged: list[tuple[float, float]] = [src[0]]
    for s, e in src[1:]:
        ps, pe = merged[-1]
        if s <= pe + join_gap:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


def _invert_ranges(total_duration: float, cuts: list[tuple[float, float]], min_keep: float = 0.08) -> list[tuple[float, float]]:
    cuts_merged = _merge_ranges(cuts)
    keep: list[tuple[float, float]] = []
    cursor = 0.0
    for s, e in cuts_merged:
        s = max(0.0, min(total_duration, s))
        e = max(0.0, min(total_duration, e))
        if s > cursor and (s - cursor) >= min_keep:
            keep.append((cursor, s))
        cursor = max(cursor, e)
    if total_duration > cursor and (total_duration - cursor) >= min_keep:
        keep.append((cursor, total_duration))
    if not keep and total_duration > 0:
        keep.append((0.0, total_duration))
    return keep


def _concat_videos_chronological(videos: list[Path], out_path: Path) -> tuple[bool, str]:
    """Merge clips in order using concat demuxer with copy, fallback to re-encode."""
    tmp_dir = out_path.parent
    tmp_dir.mkdir(parents=True, exist_ok=True)
    concat_file = tmp_dir / f"concat_{os.getpid()}.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for v in videos:
            safe = str(v.resolve()).replace("'", "'\\''")
            f.write(f"file '{safe}'\n")

    try:
        copy_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            "-movflags", "+faststart",
            str(out_path),
        ]
        copy_res = subprocess.run(copy_cmd, capture_output=True, text=True)
        if copy_res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return True, ""

        reencode_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "16",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "320k",
            "-movflags", "+faststart",
            str(out_path),
        ]
        enc_res = subprocess.run(reencode_cmd, capture_output=True, text=True)
        if enc_res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return True, ""
        return False, enc_res.stderr[-600:]
    finally:
        concat_file.unlink(missing_ok=True)


def _build_speech_ranges(words: list[Word], total_duration: float, pad: float = 0.2) -> list[tuple[float, float]]:
    raw = []
    for w in words:
        s = max(0.0, w.start - pad)
        e = min(total_duration, w.end + pad)
        if e > s:
            raw.append((s, e))
    return _merge_ranges(raw, join_gap=0.4)


def _compress_keep_ranges(
    keep_ranges: list[tuple[float, float]],
    max_total_seconds: float,
    min_slice_seconds: float = 0.35,
) -> list[tuple[float, float]]:
    """Compress keep ranges to a max total duration while preserving order and coverage."""
    total = sum(e - s for s, e in keep_ranges)
    if total <= max_total_seconds:
        return keep_ranges

    ratio = max_total_seconds / max(total, 1e-6)
    out: list[tuple[float, float]] = []
    used = 0.0

    for s, e in keep_ranges:
        if used >= max_total_seconds:
            break
        dur = e - s
        take = max(min_slice_seconds, dur * ratio)
        remaining = max_total_seconds - used
        take = min(take, remaining, dur)
        if take <= 0.02:
            continue

        # Keep the center portion of each range to retain representative action.
        start = s + max(0.0, (dur - take) / 2.0)
        end = start + take
        out.append((start, end))
        used += (end - start)

    return _merge_ranges(out, join_gap=0.02)


def _generate_camera_recording_ass(
    words: list[Word],
    ass_path: Path,
    width: int = 1080,
    height: int = 1920,
    words_per_line: int = 4,
) -> None:
    """Generate karaoke-like ASS with black bold text and yellow active word."""
    header = f"""[Script Info]
Title: Camera Longform Captions
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat,64,&H00000000,&H00000000,&H00FFFFFF,&H64000000,1,0,0,0,100,100,0,0,1,4,0,2,70,70,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: list[str] = []
    group_size = max(4, min(5, words_per_line))

    for i in range(0, len(words), group_size):
        group = words[i:i + group_size]
        if not group:
            continue

        for j, active in enumerate(group):
            start = active.start
            end = group[j + 1].start if j + 1 < len(group) else active.end
            if end <= start:
                continue

            parts: list[str] = []
            for k, w in enumerate(group):
                txt = _ass_escape(w.text)
                if k == j:
                    parts.append(r"{\b1\fs84\c&H0000FFFF&\3c&H00000000&\bord5}" + txt + r"{\rDefault}")
                else:
                    parts.append(r"{\b1\fs64\c&H00000000&\3c&H00FFFFFF&\bord4}" + txt + r"{\rDefault}")

            line = " ".join(parts)
            events.append(
                f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},Default,,0,0,0,,{line}"
            )

    ass_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def _format_ass_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


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
    overlay_opacity: float | None = None,
    overlay_scale: float | None = None,
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
    branding_overlay_scale, branding_overlay_opacity, branding_longform_margin, _ = _branding_values()
    overlay_opacity = branding_overlay_opacity if overlay_opacity is None else overlay_opacity
    overlay_scale = branding_overlay_scale if overlay_scale is None else overlay_scale

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

    # Normalize long-form outputs to the configured vertical-friendly delivery profile.
    # Requested defaults are 1080x1920 @ 30fps.
    target_width = 1080
    target_height = 1920
    target_fps = 30

    # Build FFmpeg command
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]

    # Add overlay input if provided
    overlay_input_idx = None
    if overlay_path and overlay_path.exists():
        cmd.extend(["-i", str(overlay_path)])
        overlay_input_idx = 1

    # Build filter complex
    filter_parts: list[str] = []

    smooth_zoom = "1.1+0.1*cos(2*PI*t/12)"
    filter_parts.append(
        f"[0:v]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
        f"crop={target_width}:{target_height},setsar=1,fps={target_fps}[base]"
    )
    filter_parts.append(
        f"[base]scale='trunc({target_width}*{smooth_zoom}/2)*2':'trunc({target_height}*{smooth_zoom}/2)*2':eval=frame,"
        f"crop={target_width}:{target_height}:(iw-ow)/2:(ih-oh)/2[vzoom]"
    )

    if overlay_input_idx is not None:
        overlay_w = max(120, int(target_width * overlay_scale))
        filter_parts.append(
            f"[{overlay_input_idx}:v]scale={overlay_w}:-1,format=rgba,"
            f"colorchannelmixer=aa={overlay_opacity}[watermark]"
        )
        filter_parts.append(f"[vzoom][watermark]overlay={branding_longform_margin}:{branding_longform_margin}[vout]")
    else:
        filter_parts.append("[vzoom]copy[vout]")

    cmd.extend(["-filter_complex", ";".join(filter_parts)])
    cmd.extend(["-map", "[vout]", "-map", "0:a?"])

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


def generate_camera_recording_longform(
    input_video: Path,
    output_path: Path,
    silence_threshold_db: float = -40.0,
    silence_min_duration: float = 0.003,
    words_per_line: int = 4,
    overlay_path: Path | None = None,
) -> LongformResult:
    """Render a long-form camera recording with silence cuts, zoom loop, and burned captions."""
    start_time = time.time()
    branding_overlay_width_frac, branding_overlay_opacity, branding_longform_margin, _ = _branding_values()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_video.exists():
        return LongformResult(
            output_path=output_path,
            success=False,
            input_count=1,
            input_duration=0.0,
            output_duration=0.0,
            processing_time=0.0,
            file_size=0,
            errors=[f"Input file not found: {input_video}"],
        )

    total_duration = get_video_duration(input_video)
    if total_duration <= 0:
        return LongformResult(
            output_path=output_path,
            success=False,
            input_count=1,
            input_duration=0.0,
            output_duration=0.0,
            processing_time=time.time() - start_time,
            file_size=0,
            errors=["Could not determine input duration"],
        )

    source_info = probe_video(input_video)
    has_audio = any(s.get("codec_type") == "audio" for s in source_info.get("streams", []))

    keep_ranges = [(0.0, total_duration)]
    if has_audio:
        silence = SilenceDetector(threshold_db=silence_threshold_db, min_duration=silence_min_duration).detect(input_video)
        keep_ranges = _build_keep_ranges(total_duration, silence.intervals)

    tmp_dir = Path(tempfile.gettempdir()) / "camera_longform"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ass_path = tmp_dir / f"camera_{os.getpid()}.ass"

    caption_errors: list[str] = []
    if has_audio:
        try:
            tx = Transcriber(word_timestamps=True)
            tr = tx.transcribe(input_video, language="en")
            words = _iter_words(tr.segments)
            if words:
                _generate_camera_recording_ass(
                    words=words,
                    ass_path=ass_path,
                    width=1080,
                    height=1920,
                    words_per_line=words_per_line,
                )
            else:
                caption_errors.append("No word-level timestamps available for subtitle burn-in")
        except Exception as exc:
            caption_errors.append(f"Caption transcription failed: {exc}")
    else:
        caption_errors.append("Input has no audio track; subtitle burn-in skipped")

    zoom_expr = "1.1+0.1*cos(2*PI*t/12)"
    fc: list[str] = []

    if has_audio and keep_ranges:
        for i, (s, e) in enumerate(keep_ranges):
            fc.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}]")
            fc.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]")
        concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(keep_ranges)))
        fc.append(f"{concat_inputs}concat=n={len(keep_ranges)}:v=1:a=1[vcut][acut]")
        video_in = "[vcut]"
        audio_in = "[acut]"
    else:
        video_in = "[0:v]"
        audio_in = "[0:a]" if has_audio else None

    fc.append(f"{video_in}scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30[base]")
    fc.append(
        f"[base]scale='trunc(1080*{zoom_expr}/2)*2':'trunc(1920*{zoom_expr}/2)*2':eval=frame,"
        f"crop=1080:1920:(iw-ow)/2:(ih-oh)/2[vzoom]"
    )

    vcap_label = "[vzoom]"
    if ass_path.exists():
        sub_link = tmp_dir / f"sub_{os.getpid()}.ass"
        sub_link.unlink(missing_ok=True)
        sub_link.symlink_to(ass_path.resolve())
        fc.append(f"[vzoom]ass={str(sub_link)}[vcap]")
        vcap_label = "[vcap]"

    overlay_input_idx = None
    if overlay_path and overlay_path.exists():
        overlay_input_idx = 1
        overlay_w = max(120, int(1080 * branding_overlay_width_frac))
        fc.append(
            f"[{overlay_input_idx}:v]scale={overlay_w}:-1,format=rgba,"
            f"colorchannelmixer=aa={branding_overlay_opacity}[wm]"
        )
        fc.append(f"{vcap_label}[wm]overlay={branding_longform_margin}:{branding_longform_margin}[vout]")
    else:
        fc.append(f"{vcap_label}copy[vout]")

    cmd = ["ffmpeg", "-y", "-i", str(input_video)]
    if overlay_input_idx is not None:
        cmd.extend(["-i", str(overlay_path)])
    cmd.extend(["-filter_complex", ";".join(fc), "-map", "[vout]"])
    if audio_in:
        cmd.extend(["-map", audio_in])
    else:
        cmd.append("-an")

    if audio_in:
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

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "14",
        "-maxrate", "28000k",
        "-bufsize", "56000k",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "320k",
        "-movflags", "+faststart",
        str(output_path),
    ])

    errors: list[str] = []
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600 * 6)
        if result.returncode != 0:
            errors.append(f"FFmpeg error: {result.stderr[-600:]}")
    except subprocess.TimeoutExpired:
        errors.append("FFmpeg timed out after 6 hours")
    except Exception as exc:
        errors.append(f"Unexpected render error: {exc}")

    output_duration = get_video_duration(output_path) if output_path.exists() else 0.0
    file_size = output_path.stat().st_size if output_path.exists() else 0
    processing_time = time.time() - start_time

    all_errors = errors + caption_errors
    success = output_path.exists() and file_size > 0 and not errors

    return LongformResult(
        output_path=output_path,
        success=success,
        input_count=1,
        input_duration=total_duration,
        output_duration=output_duration,
        processing_time=processing_time,
        file_size=file_size,
        skipped=[],
        errors=all_errors,
    )


def generate_cooking_recording_longform(
    input_videos: list[Path],
    output_path: Path,
    silence_threshold_db: float = -40.0,
    silence_min_duration: float = 0.003,
    no_speech_gap_seconds: float = 2.0,
    max_target_minutes: float = 15.0,
    overlay_path: Path | None = None,
) -> LongformResult:
    """Cooking long-form flow: chronological merge + silence/no-speech trimming + zoom + tuned audio."""
    start_time = time.time()
    branding_overlay_width_frac, branding_overlay_opacity, branding_longform_margin, _ = _branding_values()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    valid = [p for p in input_videos if p.exists()]
    if not valid:
        return LongformResult(
            output_path=output_path,
            success=False,
            input_count=0,
            input_duration=0.0,
            output_duration=0.0,
            processing_time=0.0,
            file_size=0,
            errors=["No valid input video files found"],
        )

    valid_sorted = sorted(valid, key=lambda p: (p.stat().st_mtime, p.name.lower()))

    tmp_dir = Path(tempfile.gettempdir()) / "cooking_longform"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    merged_input = tmp_dir / f"merged_{os.getpid()}.mp4"

    ok, merge_err = _concat_videos_chronological(valid_sorted, merged_input)
    if not ok:
        return LongformResult(
            output_path=output_path,
            success=False,
            input_count=len(valid_sorted),
            input_duration=0.0,
            output_duration=0.0,
            processing_time=time.time() - start_time,
            file_size=0,
            errors=[f"Failed to merge input clips: {merge_err}"],
        )

    total_duration = get_video_duration(merged_input)
    if total_duration <= 0:
        return LongformResult(
            output_path=output_path,
            success=False,
            input_count=len(valid_sorted),
            input_duration=0.0,
            output_duration=0.0,
            processing_time=time.time() - start_time,
            file_size=0,
            errors=["Merged input has invalid duration"],
        )

    source_info = probe_video(merged_input)
    has_audio = any(s.get("codec_type") == "audio" for s in source_info.get("streams", []))

    cut_ranges: list[tuple[float, float]] = []
    speech_words: list[Word] = []
    warnings: list[str] = []

    if has_audio:
        try:
            silence = SilenceDetector(threshold_db=silence_threshold_db, min_duration=silence_min_duration).detect(merged_input)
            cut_ranges.extend((i.start, i.end) for i in silence.intervals if i.duration >= silence_min_duration)
        except Exception as exc:
            warnings.append(f"Silence analysis failed: {exc}")

        try:
            tx = Transcriber(word_timestamps=True)
            tr = tx.transcribe(merged_input, language="en")
            speech_words = _iter_words(tr.segments)
        except Exception as exc:
            warnings.append(f"Speech analysis failed: {exc}")

        if len(speech_words) >= 20:
            speech_ranges = _build_speech_ranges(speech_words, total_duration)
            cursor = 0.0
            for s, e in speech_ranges:
                if s - cursor >= no_speech_gap_seconds:
                    cut_ranges.append((cursor, s))
                cursor = e
            if total_duration - cursor >= no_speech_gap_seconds:
                cut_ranges.append((cursor, total_duration))

    keep_ranges = _invert_ranges(total_duration, cut_ranges, min_keep=0.08) if has_audio else [(0.0, total_duration)]

    # If output is still too long, tighten by dropping tiny keeps first.
    target_seconds = max_target_minutes * 60.0
    keep_total = sum(e - s for s, e in keep_ranges)
    if keep_total > target_seconds and len(keep_ranges) > 1:
        ordered = sorted(keep_ranges, key=lambda r: (r[1] - r[0]))
        trimmed = keep_ranges[:]
        for seg in ordered:
            if keep_total <= target_seconds:
                break
            if seg in trimmed and (seg[1] - seg[0]) < 1.0:
                trimmed.remove(seg)
                keep_total -= (seg[1] - seg[0])
        keep_ranges = _merge_ranges(trimmed)

    zoom_expr = "1.1+0.1*cos(2*PI*t/12)"
    fc: list[str] = []

    if has_audio and keep_ranges:
        for i, (s, e) in enumerate(keep_ranges):
            fc.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}]")
            fc.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]")
        concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(keep_ranges)))
        fc.append(f"{concat_inputs}concat=n={len(keep_ranges)}:v=1:a=1[vcut][acut]")
        video_in = "[vcut]"
        audio_in = "[acut]"
    else:
        video_in = "[0:v]"
        audio_in = "[0:a]" if has_audio else None

    fc.append(f"{video_in}scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30[base]")
    fc.append(
        f"[base]scale='trunc(1080*{zoom_expr}/2)*2':'trunc(1920*{zoom_expr}/2)*2':eval=frame,"
        f"crop=1080:1920:(iw-ow)/2:(ih-oh)/2[vmain]"
    )

    overlay_input_idx = None
    if overlay_path and overlay_path.exists():
        overlay_input_idx = 1
        overlay_w = max(120, int(1080 * branding_overlay_width_frac))
        fc.append(
            f"[{overlay_input_idx}:v]scale={overlay_w}:-1,format=rgba,"
            f"colorchannelmixer=aa={branding_overlay_opacity}[wm]"
        )
        fc.append(f"[vmain][wm]overlay={branding_longform_margin}:{branding_longform_margin}[vout]")
    else:
        fc.append("[vmain]copy[vout]")

    cmd = ["ffmpeg", "-y", "-i", str(merged_input)]
    if overlay_input_idx is not None:
        cmd.extend(["-i", str(overlay_path)])
    cmd.extend(["-filter_complex", ";".join(fc), "-map", "[vout]"])
    if audio_in:
        cmd.extend(["-map", audio_in])
    else:
        cmd.append("-an")

    if audio_in:
        # Cooking mix: keep speech intelligible while preserving crisp kitchen transients.
        cmd.extend([
            "-af",
            "highpass=f=55,"
            "lowpass=f=15000,"
            "afftdn=nf=-18,"
            "equalizer=f=180:t=q:w=1.1:g=-1.5,"
            "equalizer=f=1800:t=q:w=1.0:g=1.8,"
            "equalizer=f=5500:t=q:w=0.9:g=2.8,"
            "equalizer=f=9000:t=q:w=0.8:g=2.2,"
            "acompressor=threshold=0.085:ratio=2.0:attack=8:release=170:makeup=2.5,"
            "loudnorm=I=-16:TP=-1.5:LRA=9,"
            "alimiter=limit=0.97",
        ])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "14",
        "-maxrate", "28000k",
        "-bufsize", "56000k",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "320k",
        "-movflags", "+faststart",
        str(output_path),
    ])

    errors: list[str] = []
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3600 * 8)
        if res.returncode != 0:
            errors.append(f"FFmpeg error: {res.stderr[-700:]}")
    except subprocess.TimeoutExpired:
        errors.append("FFmpeg timed out after 8 hours")
    except Exception as exc:
        errors.append(f"Unexpected render error: {exc}")

    output_duration = get_video_duration(output_path) if output_path.exists() else 0.0
    file_size = output_path.stat().st_size if output_path.exists() else 0

    merged_input.unlink(missing_ok=True)

    return LongformResult(
        output_path=output_path,
        success=output_path.exists() and file_size > 0 and not errors,
        input_count=len(valid_sorted),
        input_duration=total_duration,
        output_duration=output_duration,
        processing_time=time.time() - start_time,
        file_size=file_size,
        skipped=[],
        errors=errors + warnings,
    )


def generate_cooking_shortform(
    input_videos: list[Path],
    output_path: Path,
    silence_threshold_db: float = -40.0,
    silence_min_duration: float = 0.003,
    no_speech_gap_seconds: float = 2.0,
    min_target_seconds: float = 90.0,
    max_target_seconds: float = 120.0,
    overlay_path: Path | None = None,
) -> LongformResult:
    """Cooking short-form flow: chronological merge + aggressive trim + smooth zoom + crisp audio."""
    start_time = time.time()
    branding_overlay_width_frac, branding_overlay_opacity, _, branding_shortform_margin = _branding_values()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    valid = [p for p in input_videos if p.exists()]
    if not valid:
        return LongformResult(
            output_path=output_path,
            success=False,
            input_count=0,
            input_duration=0.0,
            output_duration=0.0,
            processing_time=0.0,
            file_size=0,
            errors=["No valid input video files found"],
        )

    valid_sorted = sorted(valid, key=lambda p: (p.stat().st_mtime, p.name.lower()))

    tmp_dir = Path(tempfile.gettempdir()) / "cooking_shortform"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    merged_input = tmp_dir / f"merged_{os.getpid()}.mp4"

    ok, merge_err = _concat_videos_chronological(valid_sorted, merged_input)
    if not ok:
        return LongformResult(
            output_path=output_path,
            success=False,
            input_count=len(valid_sorted),
            input_duration=0.0,
            output_duration=0.0,
            processing_time=time.time() - start_time,
            file_size=0,
            errors=[f"Failed to merge input clips: {merge_err}"],
        )

    total_duration = get_video_duration(merged_input)
    if total_duration <= 0:
        return LongformResult(
            output_path=output_path,
            success=False,
            input_count=len(valid_sorted),
            input_duration=0.0,
            output_duration=0.0,
            processing_time=time.time() - start_time,
            file_size=0,
            errors=["Merged input has invalid duration"],
        )

    source_info = probe_video(merged_input)
    has_audio = any(s.get("codec_type") == "audio" for s in source_info.get("streams", []))

    cut_ranges: list[tuple[float, float]] = []
    speech_words: list[Word] = []
    warnings: list[str] = []

    if has_audio:
        try:
            silence = SilenceDetector(threshold_db=silence_threshold_db, min_duration=silence_min_duration).detect(merged_input)
            cut_ranges.extend((i.start, i.end) for i in silence.intervals if i.duration >= silence_min_duration)
        except Exception as exc:
            warnings.append(f"Silence analysis failed: {exc}")

        try:
            tx = Transcriber(word_timestamps=True)
            tr = tx.transcribe(merged_input, language="en")
            speech_words = _iter_words(tr.segments)
        except Exception as exc:
            warnings.append(f"Speech analysis failed: {exc}")

        if len(speech_words) >= 20:
            speech_ranges = _build_speech_ranges(speech_words, total_duration)
            cursor = 0.0
            for s, e in speech_ranges:
                if s - cursor >= no_speech_gap_seconds:
                    cut_ranges.append((cursor, s))
                cursor = e
            if total_duration - cursor >= no_speech_gap_seconds:
                cut_ranges.append((cursor, total_duration))

    keep_ranges = _invert_ranges(total_duration, cut_ranges, min_keep=0.08) if has_audio else [(0.0, total_duration)]
    keep_ranges = _compress_keep_ranges(keep_ranges, max_total_seconds=max_target_seconds)

    kept_seconds = sum(e - s for s, e in keep_ranges)
    if kept_seconds < min_target_seconds:
        warnings.append(
            f"Output may be shorter than requested minimum ({kept_seconds:.1f}s < {min_target_seconds:.1f}s) after trimming"
        )

    zoom_expr = "1.1+0.1*cos(2*PI*t/12)"
    fc: list[str] = []

    if has_audio and keep_ranges:
        for i, (s, e) in enumerate(keep_ranges):
            fc.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}]")
            fc.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]")
        concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(keep_ranges)))
        fc.append(f"{concat_inputs}concat=n={len(keep_ranges)}:v=1:a=1[vcut][acut]")
        video_in = "[vcut]"
        audio_in = "[acut]"
    else:
        video_in = "[0:v]"
        audio_in = "[0:a]" if has_audio else None

    fc.append(f"{video_in}scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=30[base]")
    fc.append(
        f"[base]scale='trunc(1920*{zoom_expr}/2)*2':'trunc(1080*{zoom_expr}/2)*2':eval=frame,"
        f"crop=1920:1080:(iw-ow)/2:(ih-oh)/2[vmain]"
    )

    overlay_input_idx = None
    if overlay_path and overlay_path.exists():
        overlay_input_idx = 1
        overlay_w = max(220, int(1920 * branding_overlay_width_frac))
        fc.append(
            f"[{overlay_input_idx}:v]scale={overlay_w}:-1,format=rgba,"
            f"colorchannelmixer=aa={branding_overlay_opacity}[wm]"
        )
        fc.append(f"[vmain][wm]overlay=(W-w)/2:H-h-{branding_shortform_margin}[vout]")
    else:
        fc.append("[vmain]copy[vout]")

    cmd = ["ffmpeg", "-y", "-i", str(merged_input)]
    if overlay_input_idx is not None:
        cmd.extend(["-i", str(overlay_path)])
    cmd.extend(["-filter_complex", ";".join(fc), "-map", "[vout]"])
    if audio_in:
        cmd.extend(["-map", audio_in])
    else:
        cmd.append("-an")

    if audio_in:
        cmd.extend([
            "-af",
            "highpass=f=55,"
            "lowpass=f=15000,"
            "afftdn=nf=-18,"
            "equalizer=f=180:t=q:w=1.1:g=-1.5,"
            "equalizer=f=1800:t=q:w=1.0:g=1.8,"
            "equalizer=f=5500:t=q:w=0.9:g=2.8,"
            "equalizer=f=9000:t=q:w=0.8:g=2.2,"
            "acompressor=threshold=0.085:ratio=2.0:attack=8:release=170:makeup=2.5,"
            "loudnorm=I=-16:TP=-1.5:LRA=9,"
            "alimiter=limit=0.97",
        ])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "14",
        "-maxrate", "28000k",
        "-bufsize", "56000k",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-c:a", "aac",
        "-b:a", "320k",
        "-movflags", "+faststart",
        str(output_path),
    ])

    errors: list[str] = []
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3600 * 8)
        if res.returncode != 0:
            errors.append(f"FFmpeg error: {res.stderr[-700:]}")
    except subprocess.TimeoutExpired:
        errors.append("FFmpeg timed out after 8 hours")
    except Exception as exc:
        errors.append(f"Unexpected render error: {exc}")

    output_duration = get_video_duration(output_path) if output_path.exists() else 0.0
    file_size = output_path.stat().st_size if output_path.exists() else 0

    merged_input.unlink(missing_ok=True)

    return LongformResult(
        output_path=output_path,
        success=output_path.exists() and file_size > 0 and not errors,
        input_count=len(valid_sorted),
        input_duration=total_duration,
        output_duration=output_duration,
        processing_time=time.time() - start_time,
        file_size=file_size,
        skipped=[],
        errors=errors + warnings,
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
