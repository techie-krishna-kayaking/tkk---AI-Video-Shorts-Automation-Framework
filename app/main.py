"""
AI Video Shorts Automation Framework - Main CLI Entry Point.

Usage:
    python -m app.main process <video_path> [--channel <name>] [--max-clips <n>]
    python -m app.main vlog <vlog_folder> --channel <name>
    python -m app.main batch <directory> [--channel <name>]
    python -m app.main watch [--channel <name>]
    python -m app.main upload <video_path> [--channel <name>] [--title <title>]
    python -m app.main schedule <directory> [--channel <name>]
    python -m app.main reset-schedule [--all]
    python -m app.main info <video_path>
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from app.caption_generator import CaptionGenerator
from app.clip_selector import ClipSelector
from app.cleanup import move_files_to_trash
from app.detector import VideoCategory, detect_video
from app.longform import LongformResult, discover_subfolders, generate_longform, sort_gopro_chronological
from app.renderer import Renderer
from app.scheduler import Scheduler
from app.transcriber import Transcriber
from app.uploader import YouTubeUploader
from app.utils.config import get_config, load_config
from app.utils.files import (
    discover_channel_videos,
    ensure_ffmpeg,
    get_channel_output_dir,
    get_channel_video_name,
    get_output_dir,
    get_video_duration,
    sanitize_filename,
)
from app.utils.logging import console as rich_console, create_progress, get_logger, setup_logging
from app.trending_audio_provider import TrendingAudioProvider
from app.vlog_pipeline import create_platform_exports, create_vlog_longform, discover_vlog_media

app = typer.Typer(
    name="shorts-ai",
    help="AI Video Shorts Automation Framework",
    rich_markup_mode="rich",
)
logger = get_logger(__name__)


def _init() -> None:
    """Initialize the application."""
    config = get_config()
    setup_logging(log_dir="logs", level="INFO")

    if not ensure_ffmpeg():
        rich_console.print("[bold red]FFmpeg not found! Please install FFmpeg.[/bold red]")
        raise typer.Exit(1)


@app.command()
def process(
    video_path: Path = typer.Argument(..., help="Path to the input video file."),
    channel: Optional[str] = typer.Option(None, "--channel", "-c", help="Channel name from config."),
    max_clips: Optional[int] = typer.Option(None, "--max-clips", "-n", help="Maximum clips to generate."),
    fast: bool = typer.Option(False, "--fast", "-f", help="Fast mode: use tiny model, skip word timestamps."),
    no_captions: bool = typer.Option(False, "--no-captions", help="Skip caption generation."),
    no_upload: bool = typer.Option(False, "--no-upload", help="Skip upload even if enabled."),
) -> list[Path]:
    """Process a single video and generate shorts/reels."""
    _init()
    config = get_config()

    if not video_path.exists():
        rich_console.print(f"[bold red]Video not found: {video_path}[/bold red]")
        raise typer.Exit(1)

    # Resolve channel config
    ch_config = config.channels.get(channel) if channel else None

    # Determine output directory and video name prefix
    if ch_config and ch_config.output_folder:
        output_dir = get_channel_output_dir(ch_config.output_folder)
        video_name = get_channel_video_name(video_path, ch_config.input_folder)
    else:
        output_dir = get_output_dir(video_path, config.output.base_dir)
        video_name = sanitize_filename(video_path.stem)

    rich_console.print(f"\n[bold cyan]Processing:[/bold cyan] {video_path.name}")
    if ch_config:
        rich_console.print(f"  Channel: {ch_config.name}")
    rich_console.print(f"  Output name: {video_name}")
    rich_console.print("=" * 60)

    # Step 1: Detect video properties
    rich_console.print("\n[bold]Step 1:[/bold] Analyzing video...")
    video_info = detect_video(video_path)

    # Prefer channel-configured type over path/aspect-ratio heuristics.
    # Treat vlog channels as gopro for clip-selection/render behavior.
    category_map = {
        "tutorial": VideoCategory.TUTORIAL,
        "vertical": VideoCategory.VERTICAL,
        "gopro": VideoCategory.GOPRO,
        "vlog": VideoCategory.GOPRO,
    }
    if ch_config and ch_config.type in category_map:
        configured_category = category_map[ch_config.type]
        if video_info.category != configured_category:
            logger.info(
                "video_category_overridden",
                detected=video_info.category.value,
                configured=configured_category.value,
                channel=channel,
                path=str(video_path),
            )
            video_info = replace(video_info, category=configured_category)

    rich_console.print(f"  Resolution: {video_info.width}x{video_info.height}")
    rich_console.print(f"  Duration: {video_info.duration:.1f}s ({video_info.duration / 60:.1f} min)")
    rich_console.print(f"  FPS: {video_info.fps}")
    rich_console.print(f"  Aspect Ratio: {video_info.aspect_ratio.value}")
    rich_console.print(f"  Category: {video_info.category.value}")

    # Step 2: Select clips
    rich_console.print("\n[bold]Step 2:[/bold] Selecting clips...")
    selector = ClipSelector(fast=fast)
    selection = selector.select_clips(video_path, video_info, max_clips=max_clips)

    rich_console.print(f"  Candidates analyzed: {selection.total_candidates}")
    rich_console.print(f"  Clips selected: {selection.selected_count}")

    if not selection.clips:
        rich_console.print("[yellow]No suitable clips found.[/yellow]")
        return []

    # Step 3: Generate captions
    subtitle_paths: dict[int, Path] = {}

    if not no_captions and config.captions.enabled:
        rich_console.print("\n[bold]Step 3:[/bold] Generating captions...")
        caption_gen = CaptionGenerator()

        # Reuse transcription from clip selection (avoid re-transcribing entire video)
        transcription = getattr(selector, '_last_transcription', None)
        if transcription is None:
            transcription = selector.transcriber.transcribe(video_path)

        for idx, clip in enumerate(selection.clips):
            sub_path = output_dir / f"{video_name}_part{idx + 1:03d}"
            srt_path = caption_gen.generate_srt(
                transcription, sub_path,
                clip_start=clip.start, clip_end=clip.end,
            )
            caption_gen.generate_ass(
                transcription, sub_path,
                clip_start=clip.start, clip_end=clip.end,
            )
            subtitle_paths[idx] = srt_path

        rich_console.print(f"  Generated {len(subtitle_paths)} subtitle files")

    # Step 4: Render clips
    rich_console.print("\n[bold]Step 4:[/bold] Rendering clips...")
    renderer = Renderer()

    # Get overlay/socials from channel config
    overlay_path: Path | None = None
    hook_text = ""
    channel_type = "tutorial"
    if ch_config:
        socials = ch_config.socials_file or ch_config.social_footer
        if socials:
            overlay_path = Path(socials)
        hook_text = ch_config.intro_text
        # Renderer currently supports tutorial/gopro layouts; map vlog -> gopro.
        channel_type = "gopro" if ch_config.type == "vlog" else ch_config.type

    max_workers = max(1, int(getattr(config.processing, "max_workers", 4)))

    with create_progress() as progress:
        task = progress.add_task("Rendering clips...", total=len(selection.clips))
        results_map: dict[int, list] = {}

        def _render_single(idx: int, clip):
            local_renderer = Renderer()
            return local_renderer.render_clips(
                video_path=video_path,
                clips=[clip],
                video_info=video_info,
                output_dir=output_dir,
                subtitle_paths={0: subtitle_paths[idx]} if idx in subtitle_paths else None,
                overlay_path=overlay_path,
                hook_text=hook_text,
                channel_type=channel_type,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(_render_single, idx, clip): idx
                for idx, clip in enumerate(selection.clips)
            }

            for future in as_completed(future_map):
                idx = future_map[future]
                results_map[idx] = future.result()
                progress.advance(task)

        results = []
        for idx in range(len(selection.clips)):
            results.extend(results_map.get(idx, []))

    # Summary
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    rich_console.print(f"\n[bold green]Complete![/bold green]")
    rich_console.print(f"  Output: {output_dir}/")
    rich_console.print(f"  Clips: {successful} rendered, {failed} failed")

    # Step 5: Upload (if enabled)
    if not no_upload and channel:
        if ch_config and ch_config.upload_enabled:
            rich_console.print("\n[bold]Step 5:[/bold] Scheduling uploads...")
            scheduler = Scheduler()
            video_files = [r.output_path for r in results if r.success]
            scheduler.schedule_uploads(
                video_paths=video_files,
                channel_name=channel,
                title_prefix=video_name,
            )
            rich_console.print(f"  Scheduled {len(video_files)} uploads")

    return [r.output_path for r in results if r.success]


def _run_vlog_workflow(
    vlog_folder: Path,
    channel: str,
    max_clips: Optional[int],
    fast: bool,
    no_upload: bool,
) -> None:
    """
    Full vlog workflow:
    1) Discover timeline metadata for mixed media.
    2) Start long-form generation and short-form generation in parallel.
    3) Generate long-form captions when long-form is ready.
    4) Export platform variants using standard audio workflow.
    5) Upload YouTube exports and move generated files to trash only after successful upload.
    """
    _init()
    config = get_config()

    if not vlog_folder.exists() or not vlog_folder.is_dir():
        rich_console.print(f"[bold red]Vlog folder not found: {vlog_folder}[/bold red]")
        raise typer.Exit(1)

    ch_config = config.channels.get(channel)
    if not ch_config:
        rich_console.print(f"[bold red]Channel not found: {channel}[/bold red]")
        rich_console.print(f"  Available: {', '.join(config.channels.keys())}")
        raise typer.Exit(1)

    output_dir = get_channel_output_dir(ch_config.output_folder)
    longform_dir = output_dir / "longform"
    longform_dir.mkdir(parents=True, exist_ok=True)

    longform_name = f"{sanitize_filename(vlog_folder.name)}_vlog_longform.mp4"
    longform_path = longform_dir / longform_name

    longform_overlay_path: Path | None = None
    socials = ch_config.socials_file or ch_config.social_footer
    if socials:
        candidate = Path(socials)
        if candidate.exists():
            longform_overlay_path = candidate

    rich_console.print("\n[bold cyan]Vlog Workflow[/bold cyan]")
    rich_console.print(f"  Vlog folder: {vlog_folder}")
    rich_console.print(f"  Channel:     {ch_config.name} ({channel})")
    rich_console.print(f"  Long-form:   {longform_path}")
    rich_console.print("=" * 60)

    # Discover timeline metadata once; use it for both long-form and short-form flows.
    timeline_items = discover_vlog_media(vlog_folder)
    if not timeline_items:
        rich_console.print("[bold red]No media files found in vlog folder.[/bold red]")
        raise typer.Exit(1)

    source_videos = [item.path for item in timeline_items if item.kind == "video"]
    if not source_videos:
        rich_console.print("[bold red]No video files found for shorts generation.[/bold red]")
        raise typer.Exit(1)

    rich_console.print(f"\n[bold]Step 1:[/bold] Timeline discovered ({len(timeline_items)} items)")
    rich_console.print(f"  Videos for shorts: {len(source_videos)}")

    # Step 2: Run long-form and short-form pipelines independently in parallel.
    rich_console.print("\n[bold]Step 2:[/bold] Running long-form and short-form pipelines in parallel...")

    def _build_longform():
        return create_vlog_longform(
            vlog_folder=vlog_folder,
            output_path=longform_path,
            overlay_path=longform_overlay_path,
        )

    def _process_source_video(video_path: Path) -> list[Path]:
        return process(
            video_path=video_path,
            channel=channel,
            max_clips=max_clips,
            fast=fast,
            no_captions=False,
            no_upload=True,
        )

    short_clips: list[Path] = []
    short_errors = 0
    max_workers = max(1, int(getattr(config.processing, "max_workers", 4)))

    with ThreadPoolExecutor(max_workers=max_workers + 1) as executor:
        longform_future = executor.submit(_build_longform)
        short_futures = [
            executor.submit(_process_source_video, video_path)
            for video_path in source_videos
        ]

        for future in as_completed(short_futures):
            try:
                short_clips.extend(future.result())
            except Exception as exc:
                short_errors += 1
                logger.error("vlog_short_video_failed", folder=str(vlog_folder), error=str(exc))

        longform_result = longform_future.result()

    if not longform_result.success:
        rich_console.print("[bold red]Long-form generation failed.[/bold red]")
        for err in longform_result.errors:
            rich_console.print(f"  - {err}")
        raise typer.Exit(1)

    rich_console.print(
        f"  [green]Long-form ready:[/green] {longform_result.output_path.name} "
        f"({len(longform_result.timeline)} timeline items)"
    )
    rich_console.print(
        f"  [green]Shorts from source videos:[/green] {len(short_clips)} clips"
        + (f" ({short_errors} source video(s) failed)" if short_errors else "")
    )

    # Step 3: Generate captions for long-form output
    rich_console.print("\n[bold]Step 3:[/bold] Generating long-form captions...")
    try:
        longform_transcriber = Transcriber(
            model_name=("tiny" if fast else None),
            word_timestamps=not fast,
        )
        longform_transcription = longform_transcriber.transcribe(longform_result.output_path)

        longform_caption_base = longform_result.output_path.with_suffix("")
        longform_caption_gen = CaptionGenerator()
        srt_path = longform_caption_gen.generate_srt(
            longform_transcription,
            longform_caption_base,
        )
        ass_path = longform_caption_gen.generate_ass(
            longform_transcription,
            longform_caption_base,
            video_width=config.trip.output_width,
            video_height=config.trip.output_height,
        )
        rich_console.print(f"  Captions: {srt_path.name}, {ass_path.name}")
    except Exception as exc:
        logger.warning(
            "longform_caption_generation_failed",
            channel=channel,
            longform=str(longform_result.output_path),
            error=str(exc),
        )
        rich_console.print(f"  [yellow]Long-form captions skipped:[/yellow] {exc}")

    if not short_clips:
        rich_console.print("[yellow]No shorts generated from source videos.[/yellow]")
        raise typer.Exit(0)

    # Step 4: Platform-specific exports
    rich_console.print("\n[bold]Step 4:[/bold] Creating platform exports...")
    exports = create_platform_exports(short_clips=short_clips, output_dir=output_dir)

    rich_console.print(f"  YouTube exports:   {len(exports.youtube_exports)}")
    rich_console.print(f"  Instagram exports: {len(exports.instagram_exports)}")

    if exports.mixed_tracks:
        rich_console.print("  Audio mix details:")
        for item in exports.mixed_tracks:
            rich_console.print(f"    - {Path(item['clip']).name}")

    logger.info(
        "vlog_shorts_generation_complete",
        shorts_count=len(exports.source_shorts),
        youtube_count=len(exports.youtube_exports),
        instagram_count=len(exports.instagram_exports),
        output=str(output_dir),
    )

    # Step 5: Optional upload + cleanup
    if no_upload:
        rich_console.print("\n[bold yellow]Upload skipped due to --no-upload.[/bold yellow]")
        return

    if not ch_config.upload_enabled:
        rich_console.print("\n[bold yellow]Upload skipped (upload_enabled=false for channel).[/bold yellow]")
        return

    rich_console.print("\n[bold]Step 5:[/bold] Uploading YouTube exports...")
    logger.info("upload_started", channel=channel, count=len(exports.youtube_exports))

    uploader = YouTubeUploader(channel)
    try:
        uploader.authenticate()
    except Exception as exc:
        logger.error("upload_failed", channel=channel, error=str(exc))
        rich_console.print(f"[bold red]Upload authentication failed:[/bold red] {exc}")
        raise typer.Exit(1)

    upload_results = []
    for video_file in exports.youtube_exports:
        result = uploader.upload(
            video_path=video_file,
            title=video_file.stem,
            description="",
            privacy_status=ch_config.youtube.privacy_status,
        )
        upload_results.append(result)

    success_count = sum(1 for r in upload_results if r.success)
    fail_count = len(upload_results) - success_count

    if fail_count == 0:
        logger.info("upload_completed", channel=channel, uploaded=success_count)
        rich_console.print(f"  [green]Uploaded:[/green] {success_count}/{len(upload_results)}")

        if config.trip.cleanup_after_upload:
            rich_console.print("\n[bold]Step 6:[/bold] Moving generated files to trash...")
            generated_files = [
                longform_result.output_path,
                *exports.source_shorts,
                *exports.youtube_exports,
                *exports.instagram_exports,
            ]
            moved, errors = move_files_to_trash(generated_files)
            rich_console.print(f"  Moved to trash: {len(moved)}")
            if errors:
                rich_console.print(f"  [yellow]Trash move errors: {len(errors)}[/yellow]")
            logger.info("cleanup_complete", moved=len(moved), errors=len(errors))
        else:
            logger.info("cleanup_skipped", reason="cleanup_after_upload_disabled")
            rich_console.print("[yellow]Cleanup skipped (cleanup_after_upload=false).[/yellow]")
    else:
        logger.error("upload_failed", channel=channel, uploaded=success_count, failed=fail_count)
        logger.info("cleanup_skipped", reason="upload_failure")
        rich_console.print(
            f"[bold red]Upload incomplete:[/bold red] {success_count} succeeded, {fail_count} failed. "
            "Cleanup skipped to preserve generated assets for retry."
        )


@app.command(name="vlog")
def vlog(
    vlog_folder: Path = typer.Argument(..., help="Vlog folder containing mixed media files."),
    channel: str = typer.Option(..., "--channel", "-c", help="Channel name from config."),
    max_clips: Optional[int] = typer.Option(None, "--max-clips", "-n", help="Maximum clips to generate from long-form."),
    fast: bool = typer.Option(False, "--fast", "-f", help="Fast mode for shorts generation."),
    no_upload: bool = typer.Option(False, "--no-upload", help="Skip YouTube uploads."),
) -> None:
    """Process any vlog folder containing phone videos/photos and other mixed media."""
    _run_vlog_workflow(
        vlog_folder=vlog_folder,
        channel=channel,
        max_clips=max_clips,
        fast=fast,
        no_upload=no_upload,
    )


@app.command(name="trip")
def trip(
    trip_folder: Path = typer.Argument(..., help="Deprecated alias for vlog folder containing mixed media files."),
    channel: str = typer.Option(..., "--channel", "-c", help="Channel name from config."),
    max_clips: Optional[int] = typer.Option(None, "--max-clips", "-n", help="Maximum clips to generate from long-form."),
    fast: bool = typer.Option(False, "--fast", "-f", help="Fast mode for shorts generation."),
    no_upload: bool = typer.Option(False, "--no-upload", help="Skip YouTube uploads."),
) -> None:
    """Backward-compatible alias for the vlog command."""
    rich_console.print("[yellow]Note: Use 'vlog' command; 'trip' remains as a backward-compatible alias.[/yellow]")
    _run_vlog_workflow(
        vlog_folder=trip_folder,
        channel=channel,
        max_clips=max_clips,
        fast=fast,
        no_upload=no_upload,
    )


@app.command(name="refresh-trending-audio")
def refresh_trending_audio(
    limit: int = typer.Option(25, "--limit", "-n", help="Number of audio tracks to ingest."),
) -> None:
    """Refresh local trending audio manifests from the configured provider."""
    _init()
    provider = TrendingAudioProvider()

    if not provider.is_enabled():
        rich_console.print("[yellow]Trending provider is disabled in configs/app.yaml[/yellow]")
        raise typer.Exit(0)

    summary = provider.refresh(limit=max(1, limit))
    rich_console.print("[bold green]Trending audio refreshed[/bold green]")
    rich_console.print(f"  Provider:  {summary.provider}")
    rich_console.print(f"  Total:     {summary.total_tracks}")
    rich_console.print(f"  Instagram: {summary.instagram_tracks}")
    rich_console.print(f"  YouTube:   {summary.youtube_tracks}")
    rich_console.print(f"  Manifest:  {summary.instagram_manifest}")
    rich_console.print(f"  Manifest:  {summary.youtube_manifest}")


@app.command()
def batch(
    directory: Path = typer.Argument(None, help="Directory containing videos to process."),
    channel: Optional[str] = typer.Option(None, "--channel", "-c", help="Channel name (auto-discovers videos from channel input folder)."),
    max_clips: Optional[int] = typer.Option(None, "--max-clips", "-n", help="Max clips per video."),
    fast: bool = typer.Option(False, "--fast", "-f", help="Fast mode: use tiny model, skip word timestamps."),
    extensions: str = typer.Option("mp4,mov,avi,mkv", "--ext", help="Video extensions to process."),
) -> None:
    """
    Batch process all videos in a directory or channel.

    If --channel is specified, recursively discovers all videos in the channel's
    input folder (supports nested subfolders like trip_01/, trip_02/).

    Output is flat per channel:
        output/krgd_vlogs/trip_01_video1_part001.mp4
    """
    _init()
    config = get_config()

    ext_list = [f".{e.strip()}" for e in extensions.split(",")]

    # Determine video list
    if channel:
        ch_config = config.channels.get(channel)
        if not ch_config:
            rich_console.print(f"[bold red]Channel not found: {channel}[/bold red]")
            rich_console.print(f"  Available: {', '.join(config.channels.keys())}")
            raise typer.Exit(1)

        # For vlog channels, batch mode must be longform-first, then shorts.
        if ch_config.type == "vlog":
            input_path = Path(ch_config.input_folder)
            subfolders = sorted([d for d in input_path.iterdir() if d.is_dir()]) if input_path.exists() else []

            if not subfolders:
                rich_console.print(f"[yellow]No vlog subfolders found in {ch_config.input_folder}/[/yellow]")
                raise typer.Exit(0)

            rich_console.print(f"\n[bold cyan]Channel:[/bold cyan] {ch_config.name}")
            rich_console.print(f"[bold cyan]Input:[/bold cyan]   {ch_config.input_folder}/")
            rich_console.print(f"[bold cyan]Output:[/bold cyan]  {ch_config.output_folder}/")
            rich_console.print(f"[bold cyan]Mode:[/bold cyan]    vlog longform -> shorts")
            rich_console.print(f"[bold cyan]Folders:[/bold cyan] {len(subfolders)} found")
            rich_console.print("=" * 60)

            success_count = 0
            fail_count = 0
            for idx, subfolder in enumerate(subfolders, 1):
                rich_console.print(f"\n[bold]({idx}/{len(subfolders)})[/bold] {subfolder.name}")
                try:
                    _run_vlog_workflow(
                        vlog_folder=subfolder,
                        channel=channel,
                        max_clips=max_clips,
                        fast=fast,
                        no_upload=True,
                    )
                    success_count += 1
                except SystemExit:
                    pass
                except Exception as e:
                    rich_console.print(f"  [red]Error: {e}[/red]")
                    logger.error("batch_vlog_failed", channel=channel, folder=str(subfolder), error=str(e))
                    fail_count += 1

            rich_console.print(f"\n[bold green]Batch complete![/bold green]")
            rich_console.print(f"  Vlog folders — Processed: {success_count} | Failed: {fail_count}")
            return

        videos = discover_channel_videos(ch_config.input_folder, ext_list)
        if not videos:
            rich_console.print(f"[yellow]No videos found in {ch_config.input_folder}/[/yellow]")
            raise typer.Exit(0)

        rich_console.print(f"\n[bold cyan]Channel:[/bold cyan] {ch_config.name}")
        rich_console.print(f"[bold cyan]Input:[/bold cyan]   {ch_config.input_folder}/")
        rich_console.print(f"[bold cyan]Output:[/bold cyan]  {ch_config.output_folder}/")
        rich_console.print(f"[bold cyan]Socials:[/bold cyan] {ch_config.socials_file}")
        rich_console.print(f"[bold cyan]Videos:[/bold cyan]  {len(videos)} found")
        rich_console.print("=" * 60)

    elif directory:
        if not directory.exists():
            rich_console.print(f"[bold red]Directory not found: {directory}[/bold red]")
            raise typer.Exit(1)

        videos = sorted(
            f for f in directory.rglob("*")
            if f.is_file() and f.suffix.lower() in ext_list
        )
        if not videos:
            rich_console.print(f"[yellow]No video files found in {directory}[/yellow]")
            raise typer.Exit(0)

        rich_console.print(f"\n[bold cyan]Batch Processing:[/bold cyan] {len(videos)} videos")
        rich_console.print("=" * 60)
    else:
        rich_console.print("[bold red]Specify either a directory or --channel[/bold red]")
        raise typer.Exit(1)

    success_count = 0
    fail_count = 0

    for idx, video in enumerate(videos, 1):
        rich_console.print(f"\n[bold]({idx}/{len(videos)})[/bold] {video.name}")
        try:
            rendered = process(
                video_path=video,
                channel=channel,
                max_clips=max_clips,
                fast=fast,
                no_captions=False,
                no_upload=True,  # Don't upload during batch, schedule separately
            )
            if rendered:
                success_count += 1
        except SystemExit:
            pass  # typer.Exit from process (e.g. no clips found)
        except Exception as e:
            rich_console.print(f"  [red]Error: {e}[/red]")
            logger.error("batch_video_failed", video=str(video), error=str(e))
            fail_count += 1
            continue

    rich_console.print(f"\n[bold green]Batch complete![/bold green]")
    rich_console.print(f"  Shorts — Processed: {success_count} | Failed: {fail_count}")

    # Auto-generate long-form videos for gopro channels
    if channel and ch_config and ch_config.type == "gopro":
        rich_console.print(f"\n[bold cyan]Generating long-form videos for {channel}...[/bold cyan]")
        try:
            longform(channel=channel, subfolder=None, no_overlay=False)
        except SystemExit:
            pass
        except Exception as e:
            rich_console.print(f"  [red]Long-form error: {e}[/red]")


@app.command(name="batch-all")
def batch_all(
    max_clips: Optional[int] = typer.Option(None, "--max-clips", "-n", help="Max clips per video."),
    fast: bool = typer.Option(False, "--fast", "-f", help="Fast mode: use tiny model, skip word timestamps."),
    extensions: str = typer.Option("mp4,mov,avi,mkv", "--ext", help="Video extensions to process."),
) -> None:
    """
    Batch process ALL channels with smart routing:
    - type='vlog': Process mixed-media subfolders (long-form first, then shorts)
    - type='gopro': Process individual videos, auto-generate long-form per subfolder
    - type='tutorial'|other: Process individual videos (shorts only)
    """
    _init()
    config = get_config()

    if not config.channels:
        rich_console.print("[yellow]No channels configured in channels.yaml[/yellow]")
        raise typer.Exit(0)

    rich_console.print(f"\n[bold cyan]Batch All — Smart processing {len(config.channels)} channels[/bold cyan]")
    rich_console.print("=" * 60)

    vlog_success = 0
    vlog_fail = 0
    shorts_success = 0
    shorts_fail = 0

    for ch_id, ch_config in config.channels.items():
        if not ch_config.input_folder:
            rich_console.print(f"\n[dim]Channel: {ch_id} — no input folder configured, skipping[/dim]")
            continue

        input_path = Path(ch_config.input_folder)
        if not input_path.exists():
            rich_console.print(f"\n[dim]Channel: {ch_id} — input folder not found, skipping[/dim]")
            continue

        # ==================== VLOG WORKFLOW ====================
        if ch_config.type == "vlog":
            # Discover all subfolders as mixed-media vlog folders
            subfolders = sorted([d for d in input_path.iterdir() if d.is_dir()])
            if not subfolders:
                rich_console.print(f"\n[dim]Channel: {ch_id} (vlog) — no subfolders found, skipping[/dim]")
                continue

            rich_console.print(f"\n[bold magenta]{'─' * 60}[/bold magenta]")
            rich_console.print(f"[bold magenta]Channel: {ch_config.name} ({ch_id}) [TYPE: VLOG][/bold magenta]")
            rich_console.print(f"  Input:     {ch_config.input_folder}/")
            rich_console.print(f"  Subfolders: {len(subfolders)}")
            rich_console.print(f"[bold magenta]{'─' * 60}[/bold magenta]")

            for idx, subfolder in enumerate(subfolders, 1):
                rich_console.print(f"\n  [bold]({idx}/{len(subfolders)})[/bold] {subfolder.name}")
                try:
                    _run_vlog_workflow(
                        vlog_folder=subfolder,
                        channel=ch_id,
                        max_clips=max_clips,
                        fast=fast,
                        no_upload=True,
                    )
                    vlog_success += 1
                except SystemExit:
                    pass
                except Exception as e:
                    rich_console.print(f"    [red]Error: {e}[/red]")
                    logger.error("batch_all_vlog_failed", channel=ch_id, folder=str(subfolder), error=str(e))
                    vlog_fail += 1
                    continue

        # ==================== REGULAR WORKFLOW (gopro | tutorial | other) ====================
        else:
            ext_list = [f".{e.strip()}" for e in extensions.split(",")]
            videos = discover_channel_videos(ch_config.input_folder, ext_list)

            if not videos:
                rich_console.print(f"\n[dim]Channel: {ch_id} ({ch_config.type}) — no videos found, skipping[/dim]")
                continue

            rich_console.print(f"\n[bold magenta]{'─' * 60}[/bold magenta]")
            rich_console.print(f"[bold magenta]Channel: {ch_config.name} ({ch_id}) [TYPE: {ch_config.type.upper()}][/bold magenta]")
            rich_console.print(f"  Input:  {ch_config.input_folder}/")
            rich_console.print(f"  Videos: {len(videos)}")
            rich_console.print(f"[bold magenta]{'─' * 60}[/bold magenta]")

            for idx, video in enumerate(videos, 1):
                rich_console.print(f"\n  [bold]({idx}/{len(videos)})[/bold] {video.name}")
                try:
                    rendered = process(
                        video_path=video,
                        channel=ch_id,
                        max_clips=max_clips,
                        fast=fast,
                        no_captions=False,
                        no_upload=True,
                    )
                    if rendered:
                        shorts_success += 1
                except SystemExit:
                    pass
                except Exception as e:
                    rich_console.print(f"    [red]Error: {e}[/red]")
                    logger.error("batch_all_shorts_failed", channel=ch_id, video=str(video), error=str(e))
                    shorts_fail += 1
                    continue

    # ==================== SUMMARY ====================
    rich_console.print(f"\n[bold green]{'=' * 60}[/bold green]")
    rich_console.print(f"[bold green]All channels done![/bold green]")
    if vlog_success + vlog_fail > 0:
        rich_console.print(f"  Vlogs  — Processed: {vlog_success} | Failed: {vlog_fail}")
    if shorts_success + shorts_fail > 0:
        rich_console.print(f"  Shorts — Processed: {shorts_success} | Failed: {shorts_fail}")

    # Auto-generate long-form videos for gopro channels
    longform_channels = [
        (ch_id, ch) for ch_id, ch in config.channels.items()
        if ch.type == "gopro" and ch.input_folder
    ]
    if longform_channels:
        rich_console.print(f"\n[bold cyan]{'─' * 60}[/bold cyan]")
        rich_console.print(f"[bold cyan]Generating long-form videos for {len(longform_channels)} gopro channel(s)...[/bold cyan]")
        for ch_id, _ in longform_channels:
            try:
                longform(channel=ch_id, subfolder=None, no_overlay=False)
            except SystemExit:
                pass
            except Exception as e:
                rich_console.print(f"  [red]Long-form error ({ch_id}): {e}[/red]")


@app.command()
def watch(
    channel: Optional[str] = typer.Option(None, "--channel", "-c", help="Channel name."),
    directory: Optional[Path] = typer.Option(None, "--dir", "-d", help="Directory to watch."),
    fast: bool = typer.Option(False, "--fast", "-f", help="Fast mode."),
) -> None:
    """Watch a directory for new videos and process them automatically."""
    _init()
    config = get_config()

    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    # Determine watch directory from channel or explicit path
    if channel:
        ch_config = config.channels.get(channel)
        if ch_config and ch_config.input_folder:
            watch_dir = Path(ch_config.input_folder)
        else:
            watch_dir = Path(config.input.base_dir)
    else:
        watch_dir = directory or Path(config.input.base_dir)

    if not watch_dir.exists():
        watch_dir.mkdir(parents=True, exist_ok=True)

    rich_console.print(f"[bold cyan]Watching:[/bold cyan] {watch_dir}")
    if channel:
        rich_console.print(f"[bold cyan]Channel:[/bold cyan] {channel}")
    rich_console.print("Press Ctrl+C to stop.\n")

    class VideoHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            path = Path(event.src_path)
            if path.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv"):
                rich_console.print(f"[bold green]New video detected:[/bold green] {path.name}")
                try:
                    process(
                        video_path=path,
                        channel=channel,
                        max_clips=None,
                        fast=fast,
                        no_captions=False,
                        no_upload=False,
                    )
                except Exception as e:
                    rich_console.print(f"[red]Processing failed: {e}[/red]")

    observer = Observer()
    observer.schedule(VideoHandler(), str(watch_dir), recursive=config.watcher.recursive)
    observer.start()

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        rich_console.print("\n[bold]Watcher stopped.[/bold]")

    observer.join()


@app.command()
def upload(
    video_path: Path = typer.Argument(..., help="Path to the video to upload."),
    channel: str = typer.Option(..., "--channel", "-c", help="Channel name."),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Video title."),
    description: Optional[str] = typer.Option("", "--description", "-d", help="Video description."),
    privacy: str = typer.Option("private", "--privacy", "-p", help="Privacy status."),
) -> None:
    """Upload a single video to YouTube."""
    _init()

    if not video_path.exists():
        rich_console.print(f"[bold red]Video not found: {video_path}[/bold red]")
        raise typer.Exit(1)

    rich_console.print(f"[bold cyan]Uploading:[/bold cyan] {video_path.name}")

    uploader = YouTubeUploader(channel)
    uploader.authenticate()

    result = uploader.upload(
        video_path=video_path,
        title=title or video_path.stem,
        description=description or "",
        privacy_status=privacy,
    )

    if result.success:
        rich_console.print(f"[bold green]Uploaded![/bold green] {result.url}")
    else:
        rich_console.print(f"[bold red]Upload failed:[/bold red] {result.error}")
        raise typer.Exit(1)


@app.command()
def schedule(
    directory: Path = typer.Argument(..., help="Directory with clips to schedule."),
    channel: str = typer.Option(..., "--channel", "-c", help="Channel name."),
    interval: int = typer.Option(24, "--interval", "-i", help="Hours between uploads."),
    title_prefix: Optional[str] = typer.Option(None, "--prefix", help="Title prefix."),
) -> None:
    """Schedule uploads for all clips in a directory."""
    _init()

    if not directory.exists():
        rich_console.print(f"[bold red]Directory not found: {directory}[/bold red]")
        raise typer.Exit(1)

    videos = sorted(directory.glob("*.mp4"))
    if not videos:
        rich_console.print("[yellow]No MP4 files found.[/yellow]")
        raise typer.Exit(0)

    scheduler = Scheduler()
    scheduled = scheduler.schedule_uploads(
        video_paths=videos,
        channel_name=channel,
        title_prefix=title_prefix or directory.name,
        interval_hours=interval,
    )

    table = Table(title="Scheduled Uploads")
    table.add_column("File", style="cyan")
    table.add_column("Publish At", style="green")
    table.add_column("Status", style="yellow")

    for s in scheduled:
        table.add_row(
            s.video_path.name,
            s.publish_at.strftime("%Y-%m-%d %H:%M UTC"),
            s.status,
        )

    rich_console.print(table)


@app.command()
def info(
    video_path: Path = typer.Argument(..., help="Path to the video file."),
) -> None:
    """Display detailed information about a video file."""
    _init()

    if not video_path.exists():
        rich_console.print(f"[bold red]Video not found: {video_path}[/bold red]")
        raise typer.Exit(1)

    video_info = detect_video(video_path)

    table = Table(title=f"Video Info: {video_path.name}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Path", str(video_info.path))
    table.add_row("Resolution", f"{video_info.width}x{video_info.height}")
    table.add_row("FPS", f"{video_info.fps:.2f}")
    table.add_row("Duration", f"{video_info.duration:.1f}s ({video_info.duration / 60:.1f} min)")
    table.add_row("Aspect Ratio", video_info.aspect_ratio.value)
    table.add_row("Category", video_info.category.value)
    table.add_row("Video Codec", video_info.codec)
    table.add_row("Audio Codec", video_info.audio_codec)
    table.add_row("Bitrate", f"{video_info.bitrate / 1000:.0f} kbps")
    table.add_row("File Size", f"{video_info.file_size / 1024 / 1024:.1f} MB")

    rich_console.print(table)


@app.command()
def execute_schedule() -> None:
    """Execute all pending scheduled uploads."""
    _init()

    scheduler = Scheduler()
    pending = scheduler.get_pending_count()

    if pending == 0:
        rich_console.print("[yellow]No pending uploads.[/yellow]")
        raise typer.Exit(0)

    rich_console.print(f"[bold]Executing {pending} pending uploads...[/bold]")
    results = scheduler.execute_pending()

    successful = sum(1 for r in results if r.success)
    rich_console.print(f"\n[bold green]Done![/bold green] {successful}/{len(results)} uploaded successfully.")


@app.command(name="reset-schedule")
def reset_schedule(
    all: bool = typer.Option(
        False,
        "--all",
        help="Also clear upload history (temp/upload_history.json).",
    ),
) -> None:
    """Clear all scheduled uploads (and optionally upload history)."""
    _init()

    scheduler = Scheduler()
    removed = len(scheduler.schedule.uploads)
    scheduler.schedule.uploads = []
    scheduler._save_schedule()

    rich_console.print(
        f"[bold green]Schedule reset complete.[/bold green] Removed {removed} scheduled upload(s)."
    )

    if all:
        channels = scheduler.upload_history.get("channels", {})
        history_count = 0
        for channel_data in channels.values():
            history_count += len(channel_data.get("uploads", []))

        scheduler.upload_history = {"channels": {}}
        scheduler._save_upload_history()
        rich_console.print(
            f"[bold green]Upload history cleared.[/bold green] Removed {history_count} history record(s)."
        )


@app.command(name="channels")
def list_channels() -> None:
    """List all configured channels and their video counts."""
    _init()
    config = get_config()

    if not config.channels:
        rich_console.print("[yellow]No channels configured.[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Configured Channels")
    table.add_column("#", style="dim")
    table.add_column("Channel ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Type", style="yellow")
    table.add_column("Input Folder", style="green")
    table.add_column("Videos", style="magenta", justify="right")
    table.add_column("Socials", style="dim")

    for idx, (ch_id, ch) in enumerate(config.channels.items(), 1):
        videos = discover_channel_videos(ch.input_folder) if ch.input_folder else []
        socials_status = "✓" if ch.socials_file and Path(ch.socials_file).exists() else "✗"
        table.add_row(
            str(idx),
            ch_id,
            ch.name,
            ch.type,
            ch.input_folder,
            str(len(videos)),
            socials_status,
        )

    rich_console.print(table)
    rich_console.print(
        "\n[dim]Usage: python -m app.main batch --channel <channel_id> --fast --max-clips 5[/dim]"
    )


@app.command()
def longform(
    channel: str = typer.Option("krgd_vlogs", "--channel", "-c", help="Channel name (must be gopro type)."),
    subfolder: Optional[str] = typer.Option(None, "--subfolder", "-s", help="Process only a specific subfolder."),
    no_overlay: bool = typer.Option(False, "--no-overlay", help="Skip social watermark overlay."),
) -> None:
    """
    Generate long-form vlog videos by merging all clips in each subfolder.

    For each subfolder in the channel's input directory, all videos are merged
    into one continuous 16:9 landscape video in chronological order with a
    social branding watermark in the top-left corner.
    """
    _init()
    config = get_config()
    import time as _time

    ch_config = config.channels.get(channel)
    if not ch_config:
        rich_console.print(f"[bold red]Channel not found: {channel}[/bold red]")
        rich_console.print(f"  Available: {', '.join(config.channels.keys())}")
        raise typer.Exit(1)

    if not ch_config.input_folder:
        rich_console.print(f"[bold red]Channel {channel} has no input_folder configured[/bold red]")
        raise typer.Exit(1)

    # Discover subfolders
    subfolders = discover_subfolders(ch_config.input_folder)
    if subfolder:
        if subfolder not in subfolders:
            rich_console.print(f"[bold red]Subfolder not found: {subfolder}[/bold red]")
            rich_console.print(f"  Available: {', '.join(subfolders.keys())}")
            raise typer.Exit(1)
        subfolders = {subfolder: subfolders[subfolder]}

    if not subfolders:
        rich_console.print(f"[yellow]No subfolders with videos found in {ch_config.input_folder}/[/yellow]")
        raise typer.Exit(0)

    # Overlay setup
    overlay_path: Path | None = None
    if not no_overlay and ch_config.socials_file:
        overlay_path = Path(ch_config.socials_file)
        if not overlay_path.exists():
            rich_console.print(f"[yellow]Warning: Socials file not found: {overlay_path}[/yellow]")
            overlay_path = None

    # Output directory
    output_base = Path(ch_config.output_folder) / "longform"
    output_base.mkdir(parents=True, exist_ok=True)

    rich_console.print(f"\n[bold cyan]Long-form Video Generation[/bold cyan]")
    rich_console.print(f"  Channel:    {ch_config.name} ({channel})")
    rich_console.print(f"  Input:      {ch_config.input_folder}/")
    rich_console.print(f"  Output:     {output_base}/")
    rich_console.print(f"  Subfolders: {len(subfolders)}")
    rich_console.print(f"  Overlay:    {'Yes' if overlay_path else 'No'}")
    rich_console.print("=" * 60)

    # Process each subfolder
    total_start = _time.time()
    results: list[tuple[str, LongformResult]] = []
    total_input_videos = 0
    total_skipped: list[str] = []
    duplicates: list[str] = []
    shorts_created = 0

    for folder_name, videos in subfolders.items():
        rich_console.print(f"\n[bold magenta]Subfolder: {folder_name}[/bold magenta]")
        rich_console.print(f"  Videos: {len(videos)}")

        # Check for duplicates (same file size + name pattern)
        seen_sizes: dict[int, str] = {}
        for v in videos:
            sz = v.stat().st_size
            if sz in seen_sizes and sz > 1024 * 1024:  # >1MB with same size
                duplicates.append(f"{v.name} ≈ {seen_sizes[sz]}")
            seen_sizes[sz] = v.name

        total_input_videos += len(videos)
        output_file = output_base / f"{folder_name}_full.mp4"

        rich_console.print(f"  Output: {output_file.name}")
        rich_console.print(f"  Sorting chronologically...")

        sorted_vids = sort_gopro_chronological(videos)
        for idx, v in enumerate(sorted_vids, 1):
            rich_console.print(f"    {idx:2d}. {v.name}")

        rich_console.print(f"  Rendering long-form video...")
        result = generate_longform(
            videos=videos,
            output_path=output_file,
            overlay_path=overlay_path,
        )
        results.append((folder_name, result))

        if result.success:
            rich_console.print(
                f"  [green]✓ Done![/green] "
                f"{result.output_duration / 60:.1f} min, "
                f"{result.file_size / 1024 / 1024:.0f} MB, "
                f"took {result.processing_time:.0f}s"
            )
        else:
            rich_console.print(f"  [red]✗ Failed![/red]")
            for err in result.errors:
                rich_console.print(f"    {err}")

        total_skipped.extend(result.skipped)

    total_time = _time.time() - total_start

    # Count existing shorts in output folder
    shorts_dir = Path(ch_config.output_folder)
    if shorts_dir.exists():
        shorts_created = len(list(shorts_dir.glob("*_part*.mp4")))

    # ─── DETAILED REPORT ─────────────────────────────────────────
    _print_longform_report(
        channel_name=ch_config.name,
        channel_id=channel,
        total_input_videos=total_input_videos,
        results=results,
        total_skipped=total_skipped,
        duplicates=duplicates,
        shorts_created=shorts_created,
        total_time=total_time,
        output_base=output_base,
    )


def _print_longform_report(
    channel_name: str,
    channel_id: str,
    total_input_videos: int,
    results: list[tuple[str, LongformResult]],
    total_skipped: list[str],
    duplicates: list[str],
    shorts_created: int,
    total_time: float,
    output_base: Path,
) -> None:
    """Print detailed processing report to terminal."""
    successful = [r for _, r in results if r.success]
    failed = [r for _, r in results if not r.success]

    total_input_dur = sum(r.input_duration for _, r in results)
    total_output_dur = sum(r.output_duration for _, r in results if r.success)
    total_size = sum(r.file_size for _, r in results if r.success)

    rich_console.print("\n")
    rich_console.print("[bold cyan]" + "═" * 60 + "[/bold cyan]")
    rich_console.print("[bold cyan]           PROCESSING REPORT[/bold cyan]")
    rich_console.print("[bold cyan]" + "═" * 60 + "[/bold cyan]")

    # Channel info
    rich_console.print(f"\n  [bold]Channel:[/bold]               {channel_name} ({channel_id})")

    # Input stats
    rich_console.print(f"\n  [bold]── Input ──[/bold]")
    rich_console.print(f"  Videos detected:         {total_input_videos}")
    rich_console.print(f"  Videos processed:        {sum(r.input_count for _, r in results)}")
    rich_console.print(f"  Skipped/failed files:    {len(total_skipped)}")
    rich_console.print(f"  Duplicates detected:     {len(duplicates)}")
    rich_console.print(f"  Total input duration:    {total_input_dur / 60:.1f} min ({total_input_dur / 3600:.2f} hrs)")

    # Output stats
    rich_console.print(f"\n  [bold]── Output ──[/bold]")
    rich_console.print(f"  Short-form videos:       {shorts_created}")
    rich_console.print(f"  Long-form videos:        {len(successful)} created, {len(failed)} failed")
    rich_console.print(f"  Total output duration:   {total_output_dur / 60:.1f} min ({total_output_dur / 3600:.2f} hrs)")
    rich_console.print(f"  Total output size:       {total_size / 1024 / 1024:.0f} MB ({total_size / 1024 / 1024 / 1024:.2f} GB)")

    # Processing stats
    rich_console.print(f"\n  [bold]── Performance ──[/bold]")
    rich_console.print(f"  Total processing time:   {total_time:.0f}s ({total_time / 60:.1f} min)")
    if total_input_dur > 0:
        speed = total_input_dur / total_time
        rich_console.print(f"  Processing speed:        {speed:.1f}x realtime")

    # Output files
    rich_console.print(f"\n  [bold]── Output Files ──[/bold]")
    for folder_name, result in results:
        status = "[green]✓[/green]" if result.success else "[red]✗[/red]"
        rich_console.print(f"  {status} {result.output_path}")
        if result.success:
            rich_console.print(f"      Duration: {result.output_duration / 60:.1f} min | Size: {result.file_size / 1024 / 1024:.0f} MB")

    # Warnings
    if total_skipped or duplicates:
        rich_console.print(f"\n  [bold]── Warnings ──[/bold]")
        for s in total_skipped:
            rich_console.print(f"  [yellow]⚠ Skipped: {s}[/yellow]")
        for d in duplicates:
            rich_console.print(f"  [yellow]⚠ Possible duplicate: {d}[/yellow]")

    # Errors
    all_errors = []
    for _, r in results:
        all_errors.extend(r.errors)
    if all_errors:
        rich_console.print(f"\n  [bold]── Errors ──[/bold]")
        for e in all_errors:
            rich_console.print(f"  [red]✗ {e}[/red]")

    rich_console.print("\n[bold cyan]" + "═" * 60 + "[/bold cyan]")


if __name__ == "__main__":
    app()
