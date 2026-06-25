"""FFmpeg-based video renderer for generating shorts."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.clip_selector import Clip
from app.detector import AspectRatio, VideoInfo
from app.smart_crop import CropRegion, SmartCrop
from app.utils.config import get_config
from app.utils.files import check_gpu_available, get_clip_filename, get_next_part_number, probe_video, sanitize_filename
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RenderJob:
    """A single render job specification."""
    input_path: Path
    output_path: Path
    start: float
    end: float
    crop: CropRegion | None = None
    subtitle_path: Path | None = None
    overlay_path: Path | None = None
    hook_text: str = ""
    video_info: VideoInfo | None = None
    channel_type: str = "tutorial"  # tutorial | gopro — affects rendering layout


@dataclass
class RenderResult:
    """Result of a render job."""
    output_path: Path
    success: bool
    duration: float
    file_size: int
    error: str = ""


class Renderer:
    """
    FFmpeg-based video rendering engine.

    Handles:
    - Clip extraction
    - 16:9 -> 9:16 cropping/scaling
    - Subtitle burning
    - Overlay composition
    - Text rendering
    - GPU acceleration
    """

    def __init__(self):
        config = get_config()
        self.output_width = config.video.output_width
        self.output_height = config.video.output_height
        self.fps = config.video.fps
        self.video_bitrate = config.video.video_bitrate
        self.audio_bitrate = config.video.audio_bitrate
        self.preset = config.video.preset
        self.crf = config.video.crf
        self.gpu_available = check_gpu_available() and config.rendering.gpu_enabled
        self.gpu_encoder = config.rendering.gpu_encoder
        self.cpu_encoder = config.rendering.cpu_encoder
        self.smart_crop = SmartCrop()
        self._temp_links: list[Path] = []
        self._temp_files: list[Path] = []
        self._audio_stream_cache: dict[str, bool] = {}

        if self.gpu_available:
            logger.info("gpu_rendering_enabled", encoder=self.gpu_encoder)
        else:
            logger.info("cpu_rendering", encoder=self.cpu_encoder)

    @property
    def encoder(self) -> str:
        return self.gpu_encoder if self.gpu_available else self.cpu_encoder

    def _input_has_audio(self, path: Path) -> bool:
        key = str(path.resolve())
        cached = self._audio_stream_cache.get(key)
        if cached is not None:
            return cached
        info = probe_video(path)
        has_audio = any(stream.get("codec_type") == "audio" for stream in info.get("streams", []))
        self._audio_stream_cache[key] = has_audio
        return has_audio

    def _wrap_text_to_width(self, draw, text: str, font, max_width: int) -> list[str]:
        """Greedy word-wrap so each line fits within max_width."""
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            bb = draw.textbbox((0, 0), trial, font=font)
            if (bb[2] - bb[0]) <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _generate_header_image(self, text: str, hook_text: str = "", width: int = 1080, height: int = 300) -> Path:
        """Generate a transparent PNG with clip name (auto-wrapped/auto-shrunk) at top."""
        img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        font_path = Path("assets/fonts/Montserrat-Bold.ttf")
        display_text = hook_text.strip() if hook_text else ""

        if display_text:
            max_text_width = width - 80  # 40px padding each side
            lines: list[str] = [display_text]
            chosen_font = None

            # Try decreasing font sizes until the text fits in at most 2 lines.
            for font_size in (40, 36, 32, 28, 26, 24, 22):
                try:
                    font = ImageFont.truetype(str(font_path), font_size) if font_path.exists() else ImageFont.load_default()
                except Exception:
                    font = ImageFont.load_default()
                wrapped = self._wrap_text_to_width(draw, display_text, font, max_text_width)
                chosen_font = font
                lines = wrapped
                if len(wrapped) <= 2:
                    break

            if chosen_font is None:
                chosen_font = ImageFont.load_default()

            # Cap to 2 lines, adding an ellipsis if the title is extremely long.
            if len(lines) > 2:
                lines = lines[:2]
                lines[1] = lines[1].rstrip(".") + "…"

            line_heights = [draw.textbbox((0, 0), ln, font=chosen_font)[3] - draw.textbbox((0, 0), ln, font=chosen_font)[1] for ln in lines]
            gap = 8
            total_h = sum(line_heights) + gap * (len(lines) - 1)
            y = max(16, (160 - total_h) // 2)
            for i, ln in enumerate(lines):
                bb = draw.textbbox((0, 0), ln, font=chosen_font)
                tw = bb[2] - bb[0]
                x = (width - tw) // 2
                draw.text((x, y), ln, fill=(25, 25, 25, 255), font=chosen_font)
                y += line_heights[i] + gap

        # Save to temp file
        tmp_dir = Path(tempfile.gettempdir()) / "shorts_render"
        tmp_dir.mkdir(exist_ok=True)
        header_path = tmp_dir / f"header_{os.getpid()}.png"
        img.save(str(header_path))
        self._temp_files.append(header_path)
        return header_path

    def _generate_cta_image(self, width: int = 1080, height: int = 170) -> Path:
        """Generate a single-line CTA PNG: 'WATCH THE FULL VIDEO on' + YouTube logo."""
        img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        font_path = Path("assets/fonts/Montserrat-Bold.ttf")
        try:
            font = ImageFont.truetype(str(font_path), 46) if font_path.exists() else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        text = "WATCH THE FULL VIDEO on"
        tb = draw.textbbox((0, 0), text, font=font)
        tw = tb[2] - tb[0]
        th = tb[3] - tb[1]

        # Load YouTube logo to sit right after the text.
        logo_path = Path("assets/overlays/Logo_of_YouTube.png")
        logo = None
        logo_w = 0
        logo_h = 70
        if logo_path.exists():
            try:
                logo = Image.open(str(logo_path)).convert("RGBA")
                aspect = logo.width / logo.height
                logo_w = int(logo_h * aspect)
                logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
            except Exception:
                logo = None
                logo_w = 0

        gap = 18
        total_w = tw + (gap + logo_w if logo else 0)
        x = (width - total_w) // 2
        row_h = max(th, logo_h)
        row_top = (height - row_h) // 2

        y_text = row_top + (row_h - th) // 2 - tb[1]
        draw.text((x, y_text), text, fill=(255, 0, 0, 255), font=font)

        if logo:
            logo_x = x + tw + gap
            logo_y = row_top + (row_h - logo_h) // 2
            img.paste(logo, (logo_x, logo_y), logo)

        tmp_dir = Path(tempfile.gettempdir()) / "shorts_render"
        tmp_dir.mkdir(exist_ok=True)
        cta_path = tmp_dir / f"cta_{os.getpid()}.png"
        img.save(str(cta_path))
        self._temp_files.append(cta_path)
        return cta_path

    def _format_caption_from_output_filename(self, output_path: Path) -> str:
        stem = output_path.stem
        match = re.search(r"_part(\d+)$", stem, flags=re.IGNORECASE)
        if not match:
            return stem.replace("_", " ").strip().title()

        base = stem[:match.start()]
        part_num = int(match.group(1))
        pretty_base = base.replace("_", " ").strip()
        return f"{pretty_base} Part {part_num}"

    @property
    def _has_subtitle_filter(self) -> bool:
        """Check if FFmpeg has subtitle filter support (requires libass)."""
        if not hasattr(self, "_subtitle_supported"):
            result = subprocess.run(
                ["ffmpeg", "-filters"],
                capture_output=True, text=True,
            )
            self._subtitle_supported = "subtitles" in result.stdout
        return self._subtitle_supported

    @property
    def _has_drawtext_filter(self) -> bool:
        """Check if FFmpeg has drawtext filter support (requires libfreetype)."""
        if not hasattr(self, "_drawtext_supported"):
            result = subprocess.run(
                ["ffmpeg", "-filters"],
                capture_output=True, text=True,
            )
            self._drawtext_supported = "drawtext" in result.stdout
        return self._drawtext_supported

    def render_clip(self, job: RenderJob) -> RenderResult:
        """
        Render a single clip with all effects applied.

        Pipeline:
        1. Extract segment
        2. Apply crop/scale
        3. Add overlays
        4. Burn subtitles
        5. Add text
        6. Encode with optimal settings
        """
        logger.info(
            "rendering_clip",
            input=str(job.input_path),
            output=str(job.output_path),
            start=f"{job.start:.1f}s",
            end=f"{job.end:.1f}s",
        )

        job.output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            cmd = self._build_ffmpeg_command(job)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                logger.error("render_failed", error=result.stderr[-500:])
                return RenderResult(
                    output_path=job.output_path,
                    success=False,
                    duration=0,
                    file_size=0,
                    error=result.stderr[-200:],
                )

            file_size = job.output_path.stat().st_size if job.output_path.exists() else 0
            duration = job.end - job.start

            logger.info(
                "clip_rendered",
                output=str(job.output_path),
                size_mb=f"{file_size / 1024 / 1024:.1f}",
            )

            return RenderResult(
                output_path=job.output_path,
                success=True,
                duration=duration,
                file_size=file_size,
            )

        except subprocess.TimeoutExpired:
            logger.error("render_timeout", path=str(job.output_path))
            return RenderResult(
                output_path=job.output_path,
                success=False,
                duration=0,
                file_size=0,
                error="Render timed out after 300s",
            )
        except Exception as e:
            logger.error("render_exception", error=str(e))
            return RenderResult(
                output_path=job.output_path,
                success=False,
                duration=0,
                file_size=0,
                error=str(e),
            )
        finally:
            # Cleanup temp symlinks and files
            for link in self._temp_links:
                link.unlink(missing_ok=True)
            self._temp_links.clear()
            for tmp in self._temp_files:
                tmp.unlink(missing_ok=True)
            self._temp_files.clear()

    def _build_ffmpeg_command(self, job: RenderJob) -> list[str]:
        """Build the complete FFmpeg command for a render job."""
        cmd = ["ffmpeg", "-y"]

        # Hardware acceleration input
        if self.gpu_available:
            cmd.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])

        # Input with seeking
        cmd.extend([
            "-ss", str(job.start),
            "-to", str(job.end),
            "-i", str(job.input_path),
        ])

        # Add overlay input if specified
        input_count = 1
        overlay_input_idx: int | None = None
        if job.overlay_path and job.overlay_path.exists():
            cmd.extend(["-i", str(job.overlay_path)])
            overlay_input_idx = input_count
            input_count += 1

        # Add header image input for gopro mode
        header_input_idx: int | None = None
        if job.channel_type == "gopro" and job.video_info and job.video_info.aspect_ratio == AspectRatio.LANDSCAPE:
            header_path = self._generate_header_image(
                "WATCH THE FULL VIDEO on YOUTUBE ▶",
                hook_text=job.hook_text,
            )
            cmd.extend(["-i", str(header_path)])
            header_input_idx = input_count
            input_count += 1

        # Add CTA image input (text + YouTube logo) for gopro mode
        cta_input_idx: int | None = None
        if job.channel_type == "gopro" and job.video_info and job.video_info.aspect_ratio == AspectRatio.LANDSCAPE:
            cta_path = self._generate_cta_image()
            cmd.extend(["-i", str(cta_path)])
            cta_input_idx = input_count
            input_count += 1

        # Build filter complex
        filters = self._build_filter_complex(job, input_count, header_input_idx=header_input_idx, overlay_input_idx=overlay_input_idx, cta_input_idx=cta_input_idx)

        if filters:
            cmd.extend(["-filter_complex", filters])
            cmd.extend(["-map", "[vout]", "-map", "0:a?"])
        else:
            cmd.extend(["-map", "0:v", "-map", "0:a?"])

        if self._input_has_audio(job.input_path):
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

        # Encoding settings
        cmd.extend([
            "-c:v", self.encoder,
            "-preset", self.preset,
            "-c:a", "aac",
            "-b:a", self.audio_bitrate,
            "-ar", "48000",
            "-r", str(self.fps),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ])

        if self.gpu_available:
            # GPU (NVENC): high constant-quality with a generous bitrate ceiling
            cmd.extend(["-b:v", self.video_bitrate])
        else:
            # CPU (libx264): pure CRF for maximum quality. A generous maxrate
            # ceiling prevents runaway files without capping normal footage.
            cmd.extend([
                "-crf", str(self.crf),
                "-maxrate", self.video_bitrate,
                "-bufsize", "32M",
            ])

        # Subtitle burning (if provided and not in filter)
        if job.subtitle_path and job.subtitle_path.exists():
            # Subtitles are handled in filter_complex
            pass

        cmd.append(str(job.output_path))
        return cmd

    def _build_filter_complex(self, job: RenderJob, input_count: int, header_input_idx: int | None = None, overlay_input_idx: int | None = None, cta_input_idx: int | None = None) -> str:
        """Build FFmpeg filter_complex string."""
        filters: list[str] = []
        current_stream = "[0:v]"

        # For 16:9 -> 9:16 conversion
        if job.video_info and job.video_info.aspect_ratio == AspectRatio.LANDSCAPE:

            # GOPRO mode: white letterbox with video in center, text top, socials bottom
            if job.channel_type == "gopro":
                # Scale video to fit width, preserve aspect ratio
                scale_filter = (
                    f"{current_stream}scale={self.output_width}:-2[scaled]"
                )
                filters.append(scale_filter)
                current_stream = "[scaled]"

                # Pad to 9:16 with white background, video centered vertically
                pad_filter = (
                    f"{current_stream}pad={self.output_width}:{self.output_height}"
                    f":(ow-iw)/2:(oh-ih)/2:color=white[padded]"
                )
                filters.append(pad_filter)
                current_stream = "[padded]"

                # Overlay header image at top (generated with Pillow)
                if header_input_idx is not None:
                    header_scale = f"[{header_input_idx}:v]scale={self.output_width}:-1[hdr]"
                    filters.append(header_scale)
                    header_overlay = f"{current_stream}[hdr]overlay=(W-w)/2:150[headered]"
                    filters.append(header_overlay)
                    current_stream = "[headered]"

                # CTA image (text + YouTube logo) overlaid above the socials.
                if cta_input_idx is not None:
                    cta_scale = f"[{cta_input_idx}:v]scale={int(self.output_width * 0.58)}:-1[ctaimg]"
                    filters.append(cta_scale)
                    cta_overlay = f"{current_stream}[ctaimg]overlay=(W-w)/2:H-h-260[ctad]"
                    filters.append(cta_overlay)
                    current_stream = "[ctad]"

            else:
                # TUTORIAL mode: smart crop to 9:16
                if job.crop:
                    crop_filter = (
                        f"{current_stream}crop={job.crop.width}:{job.crop.height}"
                        f":{job.crop.x}:{job.crop.y}[cropped]"
                    )
                    filters.append(crop_filter)
                    current_stream = "[cropped]"

                # Scale to output resolution
                scale_filter = (
                    f"{current_stream}scale={self.output_width}:{self.output_height}"
                    f":force_original_aspect_ratio=decrease[scaled]"
                )
                filters.append(scale_filter)
                current_stream = "[scaled]"

                # Pad to exact output dimensions (letterbox if needed)
                pad_filter = (
                    f"{current_stream}pad={self.output_width}:{self.output_height}"
                    f":(ow-iw)/2:(oh-ih)/2:color=black[padded]"
                )
                filters.append(pad_filter)
                current_stream = "[padded]"

        elif job.video_info and job.video_info.aspect_ratio == AspectRatio.PORTRAIT:
            # Already 9:16, just scale
            scale_filter = (
                f"{current_stream}scale={self.output_width}:{self.output_height}[scaled]"
            )
            filters.append(scale_filter)
            current_stream = "[scaled]"
        else:
            # Unknown ratio - force scale
            scale_filter = (
                f"{current_stream}scale={self.output_width}:{self.output_height}"
                f":force_original_aspect_ratio=decrease[scaled]"
            )
            filters.append(scale_filter)
            current_stream = "[scaled]"

            pad_filter = (
                f"{current_stream}pad={self.output_width}:{self.output_height}"
                f":(ow-iw)/2:(oh-ih)/2:color=black[padded]"
            )
            filters.append(pad_filter)
            current_stream = "[padded]"

        # Add hook text overlay at top (requires libfreetype)
        if job.hook_text and self._has_drawtext_filter and job.channel_type != "gopro":
            font_file = Path("assets/fonts/Montserrat-Bold.ttf")
            font_arg = f":fontfile='{str(font_file).replace(':', '\\:')}'" if font_file.exists() else ""
            escaped_text = (
                job.hook_text
                .replace("\\", "\\\\")
                .replace("'", "\\'")
                .replace(":", "\\:")
                .replace(",", "\\,")
                .replace("%", "\\%")
            )
            if job.channel_type == "gopro":
                # Position hook text inside the top marker area used in gopro layout.
                text_filter = (
                    f"{current_stream}drawtext=text='{escaped_text}'"
                    f"{font_arg}"
                    f":fontsize=54:fontcolor=black:borderw=2:bordercolor=white"
                    f":x=(w-text_w)/2:y=190[texted]"
                )
            else:
                text_filter = (
                    f"{current_stream}drawtext=text='{escaped_text}'"
                    f"{font_arg}"
                    f":fontsize=42:fontcolor=white:borderw=3:bordercolor=black"
                    f":x=(w-text_w)/2:y=80[texted]"
                )
            filters.append(text_filter)
            current_stream = "[texted]"

        # Burn subtitles (requires FFmpeg built with --enable-libass)
        if job.subtitle_path and job.subtitle_path.exists() and self._has_subtitle_filter:
            tmp_dir = Path(tempfile.gettempdir()) / "shorts_render"
            tmp_dir.mkdir(exist_ok=True)
            tmp_sub = tmp_dir / f"sub{os.getpid()}{job.subtitle_path.suffix}"
            tmp_sub.unlink(missing_ok=True)
            tmp_sub.symlink_to(job.subtitle_path.resolve())
            self._temp_links.append(tmp_sub)
            
            sub_path_str = str(tmp_sub)
            if job.subtitle_path.suffix == ".ass":
                sub_filter = f"{current_stream}ass={sub_path_str},null[subbed]"
            else:
                sub_filter = f"{current_stream}subtitles={sub_path_str},null[subbed]"
            filters.append(sub_filter)
            current_stream = "[subbed]"

        # Add overlay image at bottom (social footer)
        if job.overlay_path and job.overlay_path.exists() and overlay_input_idx is not None:
            overlay_scale = (
                f"[{overlay_input_idx}:v]scale={int(self.output_width * 0.48)}:-1[ovl]"
            )
            filters.append(overlay_scale)
            overlay_filter = (
                f"{current_stream}[ovl]overlay=(W-w)/2:H-h-110[overlaid]"
            )
            filters.append(overlay_filter)
            current_stream = "[overlaid]"

        # Final output label
        if filters:
            # Replace the last output label with [vout]
            last_filter = filters[-1]
            last_label = current_stream  # e.g. "[subbed]" or "[padded]"
            # Replace only the trailing label
            if last_filter.endswith(last_label):
                filters[-1] = last_filter[: -len(last_label)] + "[vout]"
            else:
                # Fallback: replace last occurrence of the label text
                label_text = last_label.strip("[]")
                idx = last_filter.rfind(f"[{label_text}]")
                if idx != -1:
                    filters[-1] = last_filter[:idx] + "[vout]" + last_filter[idx + len(last_label):]

        return ";".join(filters) if filters else ""

    def render_clips(
        self,
        video_path: Path,
        clips: list[Clip],
        video_info: VideoInfo,
        output_dir: Path,
        output_name: str | None = None,
        subtitle_paths: dict[int, Path] | None = None,
        overlay_path: Path | None = None,
        hook_text: str = "",
        channel_type: str = "tutorial",
    ) -> list[RenderResult]:
        """
        Render multiple clips from a video.

        Args:
            video_path: Source video path.
            clips: List of clips to render.
            video_info: Video metadata.
            output_dir: Output directory for rendered clips.
            output_name: Optional base output name (channel-aware naming).
            subtitle_paths: Map of clip index to subtitle file path.
            overlay_path: Social footer overlay image.
            hook_text: Default hook text for top overlay.
            channel_type: Channel type (tutorial/gopro) - affects rendering layout.
        """
        results: list[RenderResult] = []
        video_name = sanitize_filename(output_name) if output_name else sanitize_filename(video_path.stem)
        start_number = get_next_part_number(output_dir, video_name)

        # Compute crop for landscape videos (only for tutorial mode)
        crop: CropRegion | None = None
        if video_info.aspect_ratio == AspectRatio.LANDSCAPE and channel_type != "gopro":
            crop = self.smart_crop.compute_crop_region(
                source_width=video_info.width,
                source_height=video_info.height,
                target_width=self.output_width,
                target_height=self.output_height,
            )

        for idx, clip in enumerate(clips):
            part_number = start_number + idx
            output_filename = get_clip_filename(video_name, part_number)
            output_path = output_dir / output_filename

            # Per-clip smart crop for landscape (tutorial only)
            clip_crop = crop
            if video_info.aspect_ratio == AspectRatio.LANDSCAPE and channel_type != "gopro":
                try:
                    clip_crop = self.smart_crop.compute_crop_for_segment(
                        video_path=video_path,
                        start_time=clip.start,
                        end_time=clip.end,
                        source_width=video_info.width,
                        source_height=video_info.height,
                    )
                except Exception:
                    clip_crop = crop  # Fallback to global crop

            sub_path = subtitle_paths.get(idx) if subtitle_paths else None

            job = RenderJob(
                input_path=video_path,
                output_path=output_path,
                start=clip.start,
                end=clip.end,
                crop=clip_crop,
                subtitle_path=sub_path,
                overlay_path=overlay_path,
                hook_text=(
                    self._format_caption_from_output_filename(output_path)
                    if channel_type == "gopro"
                    else (clip.hook_text or hook_text)
                ),
                video_info=video_info,
                channel_type=channel_type,
            )

            result = self.render_clip(job)
            results.append(result)

            # Write metadata JSON
            metadata = {
                "source": str(video_path),
                "clip_index": part_number,
                "start": clip.start,
                "end": clip.end,
                "duration": clip.duration,
                "score": clip.score,
                "hook_text": clip.hook_text,
                "transcript": clip.transcript,
                "tags": clip.tags,
                "category": video_info.category.value,
                "aspect_ratio": video_info.aspect_ratio.value,
            }
            meta_path = output_path.with_suffix(".json")
            meta_path.write_text(json.dumps(metadata, indent=2))

        successful = sum(1 for r in results if r.success)
        logger.info(
            "batch_render_complete",
            total=len(clips),
            successful=successful,
            failed=len(clips) - successful,
        )

        return results
