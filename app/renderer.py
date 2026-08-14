"""FFmpeg-based video renderer for generating shorts."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import uuid
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

# Voice-cleanup audio chain applied to spoken shorts content (reused across the
# standard and tutorial render paths).
SHORTS_AUDIO_FILTER = (
    "highpass=f=80,"
    "lowpass=f=9000,"
    "afftdn=nf=-20,"
    "equalizer=f=220:t=q:w=1.1:g=-2,"
    "equalizer=f=2800:t=q:w=1.0:g=2,"
    "acompressor=threshold=0.09:ratio=2.2:attack=15:release=220:makeup=3,"
    "alimiter=limit=0.96"
)


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
    gopro_layout: str = "classic"   # classic | orange_70_15_15 (legacy id kept for style-2)


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
        self.branding_overlay_width_frac = config.branding.overlay_width_frac
        self.branding_overlay_opacity = config.branding.overlay_opacity
        self.branding_shorts_bottom_margin = config.branding.shorts_bottom_margin

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

    def _generate_header_image(self, text: str, hook_text: str = "", width: int = 1080, height: int = 380) -> Path:
        """Generate a transparent PNG with clip name (auto-wrapped/auto-shrunk) at top."""
        img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        font_path = Path("assets/fonts/Montserrat-Bold.ttf")
        # Title is shown in ALL CAPS, larger, across up to 3 lines.
        display_text = hook_text.strip().upper() if hook_text else ""

        if display_text:
            max_text_width = width - 60  # 30px padding each side
            lines: list[str] = [display_text]
            chosen_font = None

            # Try decreasing font sizes until the text fits in at most 3 lines.
            for font_size in (72, 66, 60, 54, 50, 46, 42, 38):
                try:
                    font = ImageFont.truetype(str(font_path), font_size) if font_path.exists() else ImageFont.load_default()
                except Exception:
                    font = ImageFont.load_default()
                wrapped = self._wrap_text_to_width(draw, display_text, font, max_text_width)
                chosen_font = font
                lines = wrapped
                if len(wrapped) <= 3:
                    break

            if chosen_font is None:
                chosen_font = ImageFont.load_default()

            # Cap to 3 lines, adding an ellipsis if the title is extremely long.
            if len(lines) > 3:
                lines = lines[:3]
                lines[2] = lines[2].rstrip(".") + "…"

            line_heights = [draw.textbbox((0, 0), ln, font=chosen_font)[3] - draw.textbbox((0, 0), ln, font=chosen_font)[1] for ln in lines]
            gap = 12
            total_h = sum(line_heights) + gap * (len(lines) - 1)
            y = max(16, (height - total_h) // 2)
            for i, ln in enumerate(lines):
                bb = draw.textbbox((0, 0), ln, font=chosen_font)
                tw = bb[2] - bb[0]
                x = (width - tw) // 2
                draw.text((x, y), ln, fill=(25, 25, 25, 255), font=chosen_font)
                y += line_heights[i] + gap

        # Save to temp file with UUID for uniqueness
        tmp_dir = Path(tempfile.gettempdir()) / "shorts_render"
        tmp_dir.mkdir(exist_ok=True)
        header_path = tmp_dir / f"header_{uuid.uuid4().hex}.png"
        img.save(str(header_path))
        self._temp_files.append(header_path)
        return header_path

    def _generate_cta_image(self, width: int = 1080, height: int = 270) -> Path:
        """Generate a 2-line CTA PNG: 'WATCH THE FULL VIDEO' / 'on' + YouTube logo (large)."""
        img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        font_path = Path("assets/fonts/Montserrat-Bold.ttf")
        try:
            font = ImageFont.truetype(str(font_path), 76) if font_path.exists() else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        line1 = "WATCH THE FULL VIDEO"
        line2_text = "on"

        b1 = draw.textbbox((0, 0), line1, font=font)
        l1w, l1h = b1[2] - b1[0], b1[3] - b1[1]
        b2 = draw.textbbox((0, 0), line2_text, font=font)
        l2tw, l2th = b2[2] - b2[0], b2[3] - b2[1]

        # Load YouTube logo (larger) to sit right after the 'on' on line 2.
        logo_path = Path("assets/overlays/Logo_of_YouTube.png")
        logo = None
        logo_w = 0
        logo_h = 118
        if logo_path.exists():
            try:
                logo = Image.open(str(logo_path)).convert("RGBA")
                aspect = logo.width / logo.height
                logo_w = int(logo_h * aspect)
                logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
            except Exception:
                logo = None
                logo_w = 0

        gap = 22
        row_gap = 16
        line2_h = max(l2th, logo_h)
        total_h = l1h + row_gap + line2_h
        y = (height - total_h) // 2

        # Line 1 centered.
        x1 = (width - l1w) // 2
        draw.text((x1, y - b1[1]), line1, fill=(255, 0, 0, 255), font=font)

        # Line 2 centered: 'on' text + YouTube logo.
        y2 = y + l1h + row_gap
        total_w2 = l2tw + (gap + logo_w if logo else 0)
        x2 = (width - total_w2) // 2
        y_text2 = y2 + (line2_h - l2th) // 2 - b2[1]
        draw.text((x2, y_text2), line2_text, fill=(255, 0, 0, 255), font=font)
        if logo:
            logo_x = x2 + l2tw + gap
            logo_y = y2 + (line2_h - logo_h) // 2
            img.paste(logo, (logo_x, logo_y), logo)

        tmp_dir = Path(tempfile.gettempdir()) / "shorts_render"
        tmp_dir.mkdir(exist_ok=True)
        cta_path = tmp_dir / f"cta_{uuid.uuid4().hex}.png"
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

    def _format_caption_from_source_folder(self, input_path: Path) -> str:
        """Build GoPro short caption from the parent folder name."""
        folder_name = input_path.parent.name.strip()
        if not folder_name:
            return sanitize_filename(input_path.stem).replace("_", " ").strip().title()
        # Preserve the folder label but make separators human-readable.
        return folder_name.replace("_", " ").replace("-", " ").strip()

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
            cmd = (
                self._build_tutorial_ffmpeg_command(job)
                if job.channel_type == "tutorial"
                else self._build_ffmpeg_command(job)
            )
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
        is_gopro_layout2 = (job.channel_type == "gopro" and job.gopro_layout == "orange_70_15_15")
        if job.channel_type == "gopro" and (
            is_gopro_layout2
            or (job.video_info and job.video_info.aspect_ratio == AspectRatio.LANDSCAPE)
        ):
            header_path = self._generate_header_image(
                "WATCH THE FULL VIDEO on YOUTUBE ▶",
                hook_text=job.hook_text,
                height=288 if is_gopro_layout2 else 380,
            )
            cmd.extend(["-i", str(header_path)])
            header_input_idx = input_count
            input_count += 1

        # Add CTA image input (text + YouTube logo) for gopro mode
        cta_input_idx: int | None = None
        if job.channel_type == "gopro" and (
            is_gopro_layout2
            or (job.video_info and job.video_info.aspect_ratio == AspectRatio.LANDSCAPE)
        ):
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
            cmd.extend(["-af", SHORTS_AUDIO_FILTER])

        # Encoding settings (shared with the tutorial render path)
        cmd.extend(self._encode_args())

        # Subtitle burning (if provided and not in filter)
        if job.subtitle_path and job.subtitle_path.exists():
            # Subtitles are handled in filter_complex
            pass

        cmd.append(str(job.output_path))
        return cmd

    def _encode_args(self) -> list[str]:
        """Shared video/audio encode arguments for the shorts render paths."""
        args = [
            "-c:v", self.encoder,
            "-preset", self.preset,
            "-c:a", "aac",
            "-b:a", self.audio_bitrate,
            "-ar", "48000",
            "-r", str(self.fps),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ]
        if self.gpu_available:
            # GPU (NVENC): high constant-quality with a generous bitrate ceiling.
            args.extend(["-b:v", self.video_bitrate])
        else:
            # CPU (libx264): pure CRF with a generous maxrate ceiling.
            args.extend(["-crf", str(self.crf), "-maxrate", self.video_bitrate, "-bufsize", "32M"])
        return args

    def _build_tutorial_ffmpeg_command(self, job: RenderJob) -> list[str]:
        """Build the FFmpeg command for a tutorial-style short.

        The source is a 9:16 recording (slides on top, face-cam on bottom).
        Overlay positions come from ``config.shorts_overlay`` so nothing is
        hardcoded and nothing covers the speaker's face:
          - Website banner centered on the slide/face boundary (a divider).
          - Social icons + Topmate stacked in the upper-left of the face area.
          - Subtitles burned on the content only.
          - The outro clip is concatenated after the content segment.
        """
        cfg = get_config().shorts_overlay
        W, H, fps = self.output_width, self.output_height, self.fps

        # px values are authored for a 1080-wide frame; scale for other widths.
        scale_px = W / 1080.0
        safe = round(cfg.safe_margin * scale_px)
        pad = round(cfg.overlay_padding * scale_px)
        boundary_y = round(cfg.boundary_fraction * H)

        cmd = ["ffmpeg", "-y", "-ss", str(job.start), "-to", str(job.end), "-i", str(job.input_path)]

        def _existing(item) -> Path | None:
            p = Path(item.image)
            return p if item.image and p.exists() else None

        social_p = _existing(cfg.social_icons)
        topmate_p = _existing(cfg.topmate)
        website_p = _existing(cfg.website)
        outro_p = Path(cfg.outro_path) if cfg.outro_path and Path(cfg.outro_path).exists() else None

        input_idx = 1
        social_idx = topmate_idx = website_idx = outro_idx = None
        if social_p is not None:
            cmd += ["-i", str(social_p)]; social_idx = input_idx; input_idx += 1
        if topmate_p is not None:
            cmd += ["-i", str(topmate_p)]; topmate_idx = input_idx; input_idx += 1
        if website_p is not None:
            cmd += ["-i", str(website_p)]; website_idx = input_idx; input_idx += 1
        if outro_p is not None:
            cmd += ["-i", str(outro_p)]; outro_idx = input_idx; input_idx += 1

        has_audio = self._input_has_audio(job.input_path)
        silence_idx = None
        if not has_audio:
            seg_len = max(0.1, float(job.end) - float(job.start))
            cmd += ["-f", "lavfi", "-t", f"{seg_len:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
            silence_idx = input_idx; input_idx += 1

        fc: list[str] = []
        # Fit the 9:16 source into the output frame (letterbox if not exactly 9:16).
        fc.append(
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[base]"
        )
        cur = "[base]"
        step = 0

        def _stack(img_idx: int, width_frac: float, x_expr: str, y: int) -> None:
            """Scale an overlay image to a fraction of frame width and place it."""
            nonlocal cur, step
            w = max(2, round(width_frac * W))
            fc.append(f"[{img_idx}:v]scale={w}:-1[ovin{step}]")
            fc.append(f"{cur}[ovin{step}]overlay={x_expr}:{y}[ovl{step}]")
            cur = f"[ovl{step}]"
            step += 1

        # Website banner: horizontally centered, straddling the boundary line so
        # it reads as a divider between the slide area and the face-cam area.
        web_bottom = boundary_y
        if website_idx is not None:
            web_w = max(2, round(cfg.website.width_frac * W))
            web_h = round(web_w * (300 / 2400))  # tkk-website.png is 2400x300
            web_y = boundary_y - web_h // 2
            _stack(website_idx, cfg.website.width_frac, "(W-w)/2", web_y)
            web_bottom = web_y + web_h

        # Social icons: upper-left of the face-cam area, just under the divider.
        social_y = max(boundary_y + safe, web_bottom + pad)
        social_h = 0
        if social_idx is not None:
            social_w = max(2, round(cfg.social_icons.width_frac * W))
            social_h = round(social_w * (200 / 1000))  # tkk_socials.png is 1000x200
            _stack(social_idx, cfg.social_icons.width_frac, str(safe), social_y)

        # Topmate banner: directly below the social icons, left-aligned.
        if topmate_idx is not None:
            topmate_y = social_y + social_h + round(cfg.topmate.margin_top * scale_px)
            _stack(topmate_idx, cfg.topmate.width_frac, str(safe), topmate_y)

        # Burn subtitles onto the content only (before the outro is appended).
        if job.subtitle_path and job.subtitle_path.exists() and self._has_subtitle_filter:
            tmp_dir = Path(tempfile.gettempdir()) / "shorts_render"
            tmp_dir.mkdir(exist_ok=True)
            tmp_sub = tmp_dir / f"sub{os.getpid()}_{step}{job.subtitle_path.suffix}"
            tmp_sub.unlink(missing_ok=True)
            tmp_sub.symlink_to(job.subtitle_path.resolve())
            self._temp_links.append(tmp_sub)
            sub = str(tmp_sub)
            sub_filter = f"ass={sub}" if job.subtitle_path.suffix == ".ass" else f"subtitles={sub}"
            fc.append(f"{cur}{sub_filter}[cv]")
            cur = "[cv]"

        # Content audio: voice cleanup (or generated silence), normalized for concat.
        if has_audio:
            fc.append(
                f"[0:a]{SHORTS_AUDIO_FILTER},aresample=48000,"
                f"aformat=sample_fmts=fltp:channel_layouts=stereo[ca]"
            )
        else:
            fc.append(f"[{silence_idx}:a]aformat=sample_fmts=fltp:channel_layouts=stereo[ca]")

        # Append the outro (scaled to match) via concat, else output content alone.
        if outro_idx is not None:
            fc.append(
                f"[{outro_idx}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[ov]"
            )
            fc.append(
                f"[{outro_idx}:a]aresample=48000,"
                f"aformat=sample_fmts=fltp:channel_layouts=stereo[oa]"
            )
            fc.append(f"{cur}[ca][ov][oa]concat=n=2:v=1:a=1[vout][aout]")
        else:
            fc.append(f"{cur}null[vout]")
            fc.append("[ca]anull[aout]")

        cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]"]
        cmd += self._encode_args()
        cmd.append(str(job.output_path))
        return cmd

    def _build_filter_complex(self, job: RenderJob, input_count: int, header_input_idx: int | None = None, overlay_input_idx: int | None = None, cta_input_idx: int | None = None) -> str:
        """Build FFmpeg filter_complex string."""
        filters: list[str] = []
        current_stream = "[0:v]"

        # Alternate vlog/gopro layout: orange top/bottom bands (20% each),
        # center video occupying 60% height, top caption, and bottom CTA+socials.
        if job.channel_type == "gopro" and job.gopro_layout == "orange_70_15_15":
            top_h = int(self.output_height * 0.20)
            middle_h = int(self.output_height * 0.60)
            bottom_h = self.output_height - top_h - middle_h
            smooth_zoom = "1.1+0.1*cos(2*PI*t/12)"

            filters.append(f"color=c=#FFB347:s={self.output_width}x{self.output_height}:r={self.fps}[bg]")
            filters.append(
                f"{current_stream}scale={self.output_width}:{middle_h}:force_original_aspect_ratio=increase[fitmid]"
            )
            filters.append(
                f"[fitmid]scale='trunc(iw*{smooth_zoom}/2)*2':'trunc(ih*{smooth_zoom}/2)*2':eval=frame,"
                f"crop={self.output_width}:{middle_h}:(iw-ow)/2:(ih-oh)/2,setsar=1[mid]"
            )
            filters.append(f"[bg][mid]overlay=0:{top_h}[midbg]")
            current_stream = "[midbg]"

            if header_input_idx is not None:
                filters.append(f"[{header_input_idx}:v]scale={self.output_width}:-1[hdr]")
                filters.append(f"{current_stream}[hdr]overlay=(W-w)/2:0[headed]")
                current_stream = "[headed]"

            if cta_input_idx is not None:
                cta_w = int(self.output_width * 0.62)
                cta_y = top_h + middle_h + max(4, int(bottom_h * 0.04))
                filters.append(f"[{cta_input_idx}:v]scale={cta_w}:-1[ctaimg]")
                filters.append(f"{current_stream}[ctaimg]overlay=(W-w)/2:{cta_y}[ctaed]")
                current_stream = "[ctaed]"

            if job.overlay_path and job.overlay_path.exists() and overlay_input_idx is not None:
                socials_w = max(320, int(self.output_width * max(self.branding_overlay_width_frac, 0.30)))
                filters.append(
                    f"[{overlay_input_idx}:v]scale={socials_w}:-1,format=rgba,"
                    f"colorchannelmixer=aa={self.branding_overlay_opacity}[ovl]"
                )
                filters.append(
                    f"{current_stream}[ovl]overlay=(W-w)/2:H-h-{self.branding_shorts_bottom_margin}[overlaid]"
                )
                current_stream = "[overlaid]"

            if filters:
                last_filter = filters[-1]
                if last_filter.endswith(current_stream):
                    filters[-1] = last_filter[: -len(current_stream)] + "[vout]"
                else:
                    label_text = current_stream.strip("[]")
                    idx = last_filter.rfind(f"[{label_text}]")
                    if idx != -1:
                        filters[-1] = last_filter[:idx] + "[vout]" + last_filter[idx + len(current_stream):]
            return ";".join(filters)

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
                    f":(ow-iw)/2:(oh-ih)/2:color=#FFB347[padded]"
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
                    cta_scale = f"[{cta_input_idx}:v]scale={int(self.output_width * 0.76)}:-1[ctaimg]"
                    filters.append(cta_scale)
                    cta_overlay = f"{current_stream}[ctaimg]overlay=(W-w)/2:H-h-350[ctad]"
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
            overlay_w = max(320, int(self.output_width * max(self.branding_overlay_width_frac, 0.30))) if job.channel_type == "gopro" else max(120, int(self.output_width * self.branding_overlay_width_frac))
            overlay_scale = (
                f"[{overlay_input_idx}:v]scale={overlay_w}:-1,"
                f"format=rgba,colorchannelmixer=aa={self.branding_overlay_opacity}[ovl]"
            )
            filters.append(overlay_scale)
            overlay_filter = (
                f"{current_stream}[ovl]overlay=(W-w)/2:H-h-{self.branding_shorts_bottom_margin}[overlaid]"
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
        gopro_layout: str = "classic",
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
            gopro_layout: gopro layout mode (classic/orange_70_15_15).
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
                    self._format_caption_from_source_folder(video_path)
                    if channel_type == "gopro"
                    else (clip.hook_text or hook_text)
                ),
                video_info=video_info,
                channel_type=channel_type,
                gopro_layout=gopro_layout,
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
