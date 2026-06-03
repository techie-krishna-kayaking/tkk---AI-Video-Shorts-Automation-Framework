"""FFmpeg-based video renderer for generating shorts."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.clip_selector import Clip
from app.detector import AspectRatio, VideoInfo
from app.smart_crop import CropRegion, SmartCrop
from app.utils.config import get_config
from app.utils.files import check_gpu_available, get_clip_filename, get_next_part_number, sanitize_filename
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

        if self.gpu_available:
            logger.info("gpu_rendering_enabled", encoder=self.gpu_encoder)
        else:
            logger.info("cpu_rendering", encoder=self.cpu_encoder)

    @property
    def encoder(self) -> str:
        return self.gpu_encoder if self.gpu_available else self.cpu_encoder

    def _generate_header_image(self, text: str, width: int = 1080, height: int = 420) -> Path:
        """Generate a transparent PNG with large red text + YouTube logo for gopro header."""
        img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        # Try to use Montserrat font, fall back to default
        font_path = Path("assets/fonts/Montserrat-Bold.ttf")
        try:
            font = ImageFont.truetype(str(font_path), 56) if font_path.exists() else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        # Line 1: "WATCH THE FULL VIDEO"
        line1 = "WATCH THE FULL VIDEO"
        bbox1 = draw.textbbox((0, 0), line1, font=font)
        w1 = bbox1[2] - bbox1[0]
        h1 = bbox1[3] - bbox1[1]

        # Line 2: "on" + YouTube logo (logo replaces the word YOUTUBE)
        line2_text = "on"
        bbox2 = draw.textbbox((0, 0), line2_text, font=font)
        w2 = bbox2[2] - bbox2[0]
        h2 = bbox2[3] - bbox2[1]

        # Load YouTube logo - sized prominently
        yt_logo_path = Path("assets/overlays/Logo_of_YouTube.png")
        yt_logo_w = 0
        yt_logo = None
        logo_h = 120  # fixed prominent size
        if yt_logo_path.exists():
            yt_logo = Image.open(str(yt_logo_path)).convert("RGBA")
            logo_aspect = yt_logo.width / yt_logo.height
            yt_logo_w = int(logo_h * logo_aspect)
            yt_logo = yt_logo.resize((yt_logo_w, logo_h), Image.LANCZOS)

        # Calculate total width of line2 (text + gap + logo)
        gap = 20
        line2_total_w = w2 + gap + yt_logo_w if yt_logo else w2

        # Vertical spacing - use larger gap to accommodate logo height
        line_gap = 25
        line2_row_h = max(h2, logo_h)
        total_h = h1 + line_gap + line2_row_h
        y_start = (height - total_h) // 2

        # Draw line 1 centered
        x1 = (width - w1) // 2
        draw.text((x1, y_start), line1, fill=(255, 0, 0, 255), font=font)

        # Draw line 2: "on" + logo, centered together
        # The row starts after line1 + gap
        y2_row = y_start + h1 + line_gap
        x2 = (width - line2_total_w) // 2
        # Vertically center "on" text within the row
        y2_text = y2_row + (line2_row_h - h2) // 2
        draw.text((x2, y2_text), line2_text, fill=(255, 0, 0, 255), font=font)

        # Paste YouTube logo next to "on", vertically centered in row
        if yt_logo:
            logo_x = x2 + w2 + gap
            logo_y = y2_row + (line2_row_h - logo_h) // 2
            img.paste(yt_logo, (logo_x, logo_y), yt_logo)

        # Save to temp file
        tmp_dir = Path(tempfile.gettempdir()) / "shorts_render"
        tmp_dir.mkdir(exist_ok=True)
        header_path = tmp_dir / f"header_{os.getpid()}.png"
        img.save(str(header_path))
        self._temp_files.append(header_path)
        return header_path

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
            header_path = self._generate_header_image("WATCH THE FULL VIDEO on YOUTUBE ▶")
            cmd.extend(["-i", str(header_path)])
            header_input_idx = input_count
            input_count += 1

        # Build filter complex
        filters = self._build_filter_complex(job, input_count, header_input_idx=header_input_idx, overlay_input_idx=overlay_input_idx)

        if filters:
            cmd.extend(["-filter_complex", filters])
            cmd.extend(["-map", "[vout]", "-map", "0:a?"])
        else:
            cmd.extend(["-map", "0:v", "-map", "0:a?"])

        # Encoding settings
        cmd.extend([
            "-c:v", self.encoder,
            "-preset", self.preset,
            "-b:v", self.video_bitrate,
            "-c:a", "aac",
            "-b:a", self.audio_bitrate,
            "-ar", "44100",
            "-r", str(self.fps),
            "-movflags", "+faststart",
        ])

        # CRF for CPU encoding
        if not self.gpu_available:
            cmd.extend(["-crf", str(self.crf)])

        # Subtitle burning (if provided and not in filter)
        if job.subtitle_path and job.subtitle_path.exists():
            # Subtitles are handled in filter_complex
            pass

        cmd.append(str(job.output_path))
        return cmd

    def _build_filter_complex(self, job: RenderJob, input_count: int, header_input_idx: int | None = None, overlay_input_idx: int | None = None) -> str:
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
                    header_overlay = f"{current_stream}[hdr]overlay=(W-w)/2:300[headered]"
                    filters.append(header_overlay)
                    current_stream = "[headered]"

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
        if job.hook_text and self._has_drawtext_filter:
            escaped_text = job.hook_text.replace("'", "\\'").replace(":", "\\:")
            text_filter = (
                f"{current_stream}drawtext=text='{escaped_text}'"
                f":fontsize=42:fontcolor=white:borderw=3:bordercolor=black"
                f":x=(w-text_w)/2:y=80:font=Montserrat[texted]"
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
                f"[{overlay_input_idx}:v]scale={self.output_width}:-1[ovl]"
            )
            filters.append(overlay_scale)
            overlay_filter = (
                f"{current_stream}[ovl]overlay=(W-w)/2:H-h-350[overlaid]"
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
                hook_text=clip.hook_text or hook_text,
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
