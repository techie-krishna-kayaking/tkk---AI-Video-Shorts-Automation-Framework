"""
AI Video Shorts Automation Framework - Main CLI Entry Point.

Usage:
    python -m app.main process <video_path> [--channel <name>] [--max-clips <n>]
    python -m app.main batch <directory> [--channel <name>]
    python -m app.main watch [--channel <name>]
    python -m app.main upload <video_path> [--channel <name>] [--title <title>]
    python -m app.main schedule <directory> [--channel <name>]
    python -m app.main info <video_path>
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from app.caption_generator import CaptionGenerator
from app.clip_selector import ClipSelector
from app.detector import VideoCategory, detect_video
from app.renderer import Renderer
from app.scheduler import Scheduler
from app.uploader import YouTubeUploader
from app.utils.config import get_config, load_config
from app.utils.files import (
    discover_channel_videos,
    ensure_ffmpeg,
    get_channel_output_dir,
    get_channel_video_name,
    get_output_dir,
    sanitize_filename,
)
from app.utils.logging import console as rich_console, create_progress, get_logger, setup_logging

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
) -> None:
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
        raise typer.Exit(0)

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
    if ch_config:
        socials = ch_config.socials_file or ch_config.social_footer
        if socials:
            overlay_path = Path(socials)
        hook_text = ch_config.intro_text

    with create_progress() as progress:
        task = progress.add_task("Rendering clips...", total=len(selection.clips))
        results = []
        for idx, clip in enumerate(selection.clips):
            result = renderer.render_clips(
                video_path=video_path,
                clips=[clip],
                video_info=video_info,
                output_dir=output_dir,
                subtitle_paths={0: subtitle_paths[idx]} if idx in subtitle_paths else None,
                overlay_path=overlay_path,
                hook_text=hook_text,
            )
            results.extend(result)
            progress.advance(task)

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
            process(
                video_path=video,
                channel=channel,
                max_clips=max_clips,
                fast=fast,
                no_captions=False,
                no_upload=True,  # Don't upload during batch, schedule separately
            )
            success_count += 1
        except SystemExit:
            pass  # typer.Exit from process (e.g. no clips found)
        except Exception as e:
            rich_console.print(f"  [red]Error: {e}[/red]")
            logger.error("batch_video_failed", video=str(video), error=str(e))
            fail_count += 1
            continue

    rich_console.print(f"\n[bold green]Batch complete![/bold green]")
    rich_console.print(f"  Processed: {success_count} | Failed: {fail_count}")


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


if __name__ == "__main__":
    app()
