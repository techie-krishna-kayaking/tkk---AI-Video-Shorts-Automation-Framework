"""FFmpeg-based video renderer for generating shorts."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

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

        if self.gpu_available:
            logger.info("gpu_rendering_enabled", encoder=self.gpu_encoder)
        else:
            logger.info("cpu_rendering", encoder=self.cpu_encoder)

    @property
    def encoder(self) -> str:
        return self.gpu_encoder if self.gpu_available else self.cpu_encoder

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
            # Cleanup temp symlinks
            for link in self._temp_links:
                link.unlink(missing_ok=True)
            self._temp_links.clear()

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
        if job.overlay_path and job.overlay_path.exists():
            cmd.extend(["-i", str(job.overlay_path)])
            input_count += 1

        # Build filter complex
        filters = self._build_filter_complex(job, input_count)

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

    def _build_filter_complex(self, job: RenderJob, input_count: int) -> str:
        """Build FFmpeg filter_complex string."""
        filters: list[str] = []
        current_stream = "[0:v]"

        # For 16:9 -> 9:16 conversion
        if job.video_info and job.video_info.aspect_ratio == AspectRatio.LANDSCAPE:
            if job.crop:
                # Apply smart crop
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
        if job.overlay_path and job.overlay_path.exists():
            overlay_scale = (
                f"[{input_count - 1}:v]scale={self.output_width}:-1[ovl]"
            )
            filters.append(overlay_scale)
            overlay_filter = (
                f"{current_stream}[ovl]overlay=(W-w)/2:H-h-20[overlaid]"
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
        subtitle_paths: dict[int, Path] | None = None,
        overlay_path: Path | None = None,
        hook_text: str = "",
    ) -> list[RenderResult]:
        """
        Render multiple clips from a video.

        Args:
            video_path: Source video path.
            clips: List of clips to render.
            video_info: Video metadata.
            output_dir: Output directory for rendered clips.
            subtitle_paths: Map of clip index to subtitle file path.
            overlay_path: Social footer overlay image.
            hook_text: Default hook text for top overlay.
        """
        results: list[RenderResult] = []
        video_name = sanitize_filename(video_path.stem)
        start_number = get_next_part_number(output_dir, video_name)

        # Compute crop for landscape videos
        crop: CropRegion | None = None
        if video_info.aspect_ratio == AspectRatio.LANDSCAPE:
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

            # Per-clip smart crop for landscape
            clip_crop = crop
            if video_info.aspect_ratio == AspectRatio.LANDSCAPE:
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
