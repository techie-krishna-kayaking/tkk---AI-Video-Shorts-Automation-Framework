"""
Schedule YouTube uploads for all channels.

Rules:
- Shorts: 3 per day for 3 days at 3:07 PM, 5:07 PM, 7:07 PM (local time)
- Long-form: 1 every Thursday at 7:07 PM (if available)
- Sequential order by filename
- Title = filename stem (cleaned up)
- Hashtags: #krgdVlog for krgd_vlogs, #TKK for tkk_live_shorts
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.uploader import YouTubeUploader
from app.utils.config import get_config
from app.utils.logging import get_logger

logger = get_logger(__name__)

# --- Configuration ---

LOCAL_TZ = ZoneInfo("America/Los_Angeles")  # Adjust if needed

SHORTS_PER_DAY = 3
SHORTS_DAYS = 7
SHORTS_TIMES = [(13, 7), (15, 5), (17, 7)]  # 1:07 PM, 3:05 PM, 5:07 PM

LONGFORM_DAY = 3  # Thursday (0=Mon, 3=Thu)
LONGFORM_TIME = (19, 7)  # 7:07 PM

# Channel-specific hashtags
CHANNEL_HASHTAGS_SHORTS = {
    "krgd_vlogs": "#krgdVlog #shorts",
    "tkk_live_shorts": "#TKK #shorts",
}

CHANNEL_HASHTAGS_LONGFORM = {
    "krgd_vlogs": "#krgdVlog",
    "tkk_live_shorts": "#TKK",
}

# Channels to schedule (only those with output videos)
CHANNELS_TO_SCHEDULE = ["krgd_vlogs", "tkk_live_shorts"]

# Tracking file to avoid duplicate uploads
UPLOAD_HISTORY_FILE = Path("temp/upload_history.json")


def load_upload_history() -> dict:
    """Load the record of previously uploaded videos.

    Format:
    {
        "channels": {
            "krgd_vlogs": {
                "last_scheduled": "2026-06-01T19:07:00-07:00",
                "uploads": [
                    {
                        "file": "gh011244_part001.mp4",
                        "path": "output/krgd_vlogs/gh011244_part001.mp4",
                        "title": "Gh011244 Part001 #krgdVlog #shorts",
                        "type": "short",
                        "scheduled_at": "2026-05-30T13:07:00-07:00",
                        "uploaded_at": "2026-05-28T19:30:00-07:00",
                        "youtube_url": "https://www.youtube.com/watch?v=..."
                    }
                ]
            }
        }
    }
    """
    if UPLOAD_HISTORY_FILE.exists():
        try:
            data = json.loads(UPLOAD_HISTORY_FILE.read_text())
            # Migrate old format if needed
            if "channels" not in data:
                return _migrate_old_history(data)
            return data
        except (json.JSONDecodeError, OSError):
            return {"channels": {}}
    return {"channels": {}}


def _migrate_old_history(old: dict) -> dict:
    """Migrate from old flat list format to new detailed format."""
    new = {"channels": {}}
    for key, value in old.items():
        if key.endswith("_last_scheduled"):
            channel = key.replace("_last_scheduled", "")
            if channel not in new["channels"]:
                new["channels"][channel] = {"last_scheduled": None, "uploads": []}
            new["channels"][channel]["last_scheduled"] = value
        elif isinstance(value, list):
            if key not in new["channels"]:
                new["channels"][key] = {"last_scheduled": None, "uploads": []}
            for path_str in value:
                p = Path(path_str)
                new["channels"][key]["uploads"].append({
                    "file": p.name,
                    "path": path_str,
                    "title": "(migrated - title unknown)",
                    "type": "longform" if "longform" in path_str else "short",
                    "scheduled_at": "(migrated)",
                    "uploaded_at": "2026-05-28",
                    "youtube_url": "(migrated - url unknown)",
                })
    return new


def save_upload_history(history: dict) -> None:
    """Save the upload history to disk."""
    UPLOAD_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_HISTORY_FILE.write_text(json.dumps(history, indent=2))


def get_last_scheduled_date(history: dict, channel_name: str) -> datetime | None:
    """Get the last scheduled end date for a channel."""
    ch = history.get("channels", {}).get(channel_name, {})
    last = ch.get("last_scheduled")
    if last:
        return datetime.fromisoformat(last)
    return None


def set_last_scheduled_date(history: dict, channel_name: str, dt: datetime) -> None:
    """Record the last scheduled end date for a channel."""
    if channel_name not in history.get("channels", {}):
        history.setdefault("channels", {})[channel_name] = {"last_scheduled": None, "uploads": []}
    history["channels"][channel_name]["last_scheduled"] = dt.isoformat()


def is_already_uploaded(history: dict, channel_name: str, video_path: Path) -> bool:
    """Check if a video has already been uploaded for a channel."""
    ch = history.get("channels", {}).get(channel_name, {})
    uploaded_paths = [u["path"] for u in ch.get("uploads", [])]
    return str(video_path) in uploaded_paths


def mark_as_uploaded(
    history: dict,
    channel_name: str,
    video_path: Path,
    title: str = "",
    scheduled_at: str = "",
    youtube_url: str = "",
    video_type: str = "short",
) -> None:
    """Record a video as uploaded with full details."""
    if channel_name not in history.get("channels", {}):
        history.setdefault("channels", {})[channel_name] = {"last_scheduled": None, "uploads": []}
    history["channels"][channel_name]["uploads"].append({
        "file": video_path.name,
        "path": str(video_path),
        "title": title,
        "type": video_type,
        "scheduled_at": scheduled_at,
        "uploaded_at": datetime.now(LOCAL_TZ).isoformat(),
        "youtube_url": youtube_url,
    })


def clean_title(filename_stem: str) -> str:
    """Convert filename stem to a readable title."""
    import re

    title = filename_stem

    # Remove -vertical or _vertical suffix
    title = re.sub(r"[-_]vertical", "", title)
    # Remove date-time stamps like 2025-08-13_11-01-35
    title = re.sub(r"\d{4}-\d{2}-\d{2}[_-]\d{2}[_-]\d{2}[_-]\d{2}", "", title)
    # Replace underscores and hyphens with spaces
    title = title.replace("_", " ").replace("-", " ")
    # Collapse multiple spaces
    title = re.sub(r"\s+", " ", title)
    # Capitalize words
    title = title.strip().title()
    return title


def get_shorts_schedule(start_date: datetime) -> list[datetime]:
    """Generate publish times for shorts over the next N days."""
    schedule = []
    for day_offset in range(SHORTS_DAYS):
        day = start_date + timedelta(days=day_offset + 1)  # Start tomorrow
        for hour, minute in SHORTS_TIMES:
            publish_at = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
            schedule.append(publish_at)
    return schedule


def get_next_thursday(start_date: datetime) -> datetime:
    """Get the next Thursday at 7:07 PM from start_date."""
    days_ahead = LONGFORM_DAY - start_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_thu = start_date + timedelta(days=days_ahead)
    hour, minute = LONGFORM_TIME
    return next_thu.replace(hour=hour, minute=minute, second=0, microsecond=0)


def is_longform(video_path: Path) -> bool:
    """Check if a video is long-form (in the longform/ subfolder)."""
    return "longform" in video_path.parts


def schedule_channel(channel_name: str, dry_run: bool = True, history: dict | None = None) -> None:
    """Schedule uploads for a single channel."""
    config = get_config()
    channel_config = config.channels.get(channel_name)
    if not channel_config:
        print(f"  [SKIP] Channel '{channel_name}' not found in config")
        return

    if history is None:
        history = {}

    output_dir = Path(channel_config.output_folder)
    if not output_dir.exists():
        print(f"  [SKIP] Output folder not found: {output_dir}")
        return

    # Shorts are in the top-level output folder — skip already uploaded
    all_shorts = sorted(output_dir.glob("*.mp4"))
    shorts = [v for v in all_shorts if not is_already_uploaded(history, channel_name, v)]

    # Long-form videos are in the longform/ subfolder — skip already uploaded
    longform_dir = output_dir / "longform"
    all_longforms = sorted(longform_dir.glob("*.mp4")) if longform_dir.exists() else []
    longforms = [v for v in all_longforms if not is_already_uploaded(history, channel_name, v)]

    skipped_shorts = len(all_shorts) - len(shorts)
    skipped_lf = len(all_longforms) - len(longforms)

    hashtags_shorts = CHANNEL_HASHTAGS_SHORTS.get(channel_name, "")
    hashtags_longform = CHANNEL_HASHTAGS_LONGFORM.get(channel_name, "")
    default_tags = channel_config.youtube.default_tags if channel_config.youtube else []

    now = datetime.now(LOCAL_TZ)

    # Use the last scheduled end date to avoid overlaps
    # If previous run scheduled up to Jun 5, next run starts from Jun 5
    last_scheduled = get_last_scheduled_date(history, channel_name)
    if last_scheduled and last_scheduled > now:
        start_from = last_scheduled
        print(f"\n  Channel: {channel_config.name}")
        print(f"  Continuing from last scheduled date: {last_scheduled.strftime('%a %b %d, %Y')}")
    else:
        start_from = now
        print(f"\n  Channel: {channel_config.name}")

    print(f"  Shorts available: {len(shorts)} (skipped {skipped_shorts} already uploaded)")
    print(f"  Long-form available: {len(longforms)} (skipped {skipped_lf} already uploaded)")

    # --- Schedule Shorts ---
    shorts_times = get_shorts_schedule(start_from)
    shorts_to_schedule = shorts[: len(shorts_times)]  # Cap at available slots

    print(f"\n  Shorts Schedule ({len(shorts_to_schedule)} videos):")
    print(f"  {'─' * 60}")

    uploads = []
    for idx, (video, publish_at) in enumerate(zip(shorts_to_schedule, shorts_times)):
        title = f"{clean_title(video.stem)} {hashtags_shorts}"
        print(f"  {idx+1:2d}. {video.name}")
        print(f"      Title: {title}")
        print(f"      Publish: {publish_at.strftime('%a %b %d, %Y at %I:%M %p %Z')}")
        uploads.append((video, title, publish_at))

    # --- Schedule Long-form ---
    if longforms:
        next_thu = get_next_thursday(start_from)
        lf = longforms[0]
        title = f"{clean_title(lf.stem)} {hashtags_longform}"
        print(f"\n  Long-form Schedule:")
        print(f"  {'─' * 60}")
        print(f"  1. {lf.name}")
        print(f"     Title: {title}")
        print(f"     Publish: {next_thu.strftime('%a %b %d, %Y at %I:%M %p %Z')}")
        uploads.append((lf, title, next_thu))

    if dry_run:
        print(f"\n  [DRY RUN] No uploads performed. Run with --execute to upload.")
        return

    # --- Execute Uploads ---
    print(f"\n  Uploading to YouTube...")
    uploader = YouTubeUploader(channel_name)
    uploader.authenticate()

    success_count = 0
    for video, title, publish_at in uploads:
        # YouTube API requires publishAt in UTC ISO 8601 format
        publish_utc = publish_at.astimezone(ZoneInfo("UTC"))
        publish_iso = publish_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        is_lf = is_longform(video)
        hashtags = hashtags_longform if is_lf else hashtags_shorts
        print(f"  Uploading: {video.name}...", end=" ", flush=True)
        result = uploader.upload(
            video_path=video,
            title=title,
            description=f"{clean_title(video.stem)}\n\n{hashtags}",
            tags=default_tags + [h.strip("#") for h in hashtags.split()],
            privacy_status="private",
            publish_at=publish_iso,
        )
        if result.success:
            print(f"✓ ({result.url})")
            success_count += 1
            mark_as_uploaded(
                history, channel_name, video,
                title=title,
                scheduled_at=publish_at.isoformat(),
                youtube_url=result.url,
                video_type="longform" if is_lf else "short",
            )
            save_upload_history(history)
        else:
            print(f"✗ ({result.error})")

    # Record the last scheduled date (last time slot in this batch)
    if success_count > 0 and shorts_times:
        last_time = shorts_times[-1]
        set_last_scheduled_date(history, channel_name, last_time)
        save_upload_history(history)

    print(f"\n  Done! {success_count}/{len(uploads)} uploaded successfully.")


def main():
    dry_run = "--execute" not in sys.argv

    print("=" * 64)
    print(" YouTube Upload Scheduler")
    print("=" * 64)
    print(f" Mode: {'DRY RUN (preview)' if dry_run else 'EXECUTING UPLOADS'}")
    print(f" Date: {datetime.now(LOCAL_TZ).strftime('%a %b %d, %Y %I:%M %p %Z')}")
    print(f" Schedule: {SHORTS_PER_DAY} shorts/day × {SHORTS_DAYS} days")
    print(f"           Times: {', '.join(f'{h}:{m:02d}' for h, m in SHORTS_TIMES)}")
    print(f"           Long-form: Thursdays at {LONGFORM_TIME[0]}:{LONGFORM_TIME[1]:02d}")
    print(f" History:  {UPLOAD_HISTORY_FILE}")
    print("=" * 64)

    history = load_upload_history()

    for channel in CHANNELS_TO_SCHEDULE:
        schedule_channel(channel, dry_run=dry_run, history=history)

    print("\n" + "=" * 64)
    if dry_run:
        print(" To execute uploads, run:")
        print("   python3 schedule_uploads.py --execute")
        print(" To reset history (re-upload everything):")
        print("   rm temp/upload_history.json")
    print("=" * 64)


if __name__ == "__main__":
    main()
