"""Upload scheduling with configurable delay and time windows."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.uploader import UploadResult, YouTubeUploader
from app.utils.config import get_config
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ScheduledUpload:
    """A scheduled upload job."""
    video_path: Path
    title: str
    description: str
    tags: list[str]
    channel_name: str
    publish_at: datetime
    status: str = "pending"  # pending, uploading, completed, failed
    result: UploadResult | None = None


@dataclass
class UploadSchedule:
    """A collection of scheduled uploads."""
    uploads: list[ScheduledUpload] = field(default_factory=list)


class Scheduler:
    """
    Upload scheduler for distributing uploads across time.

    Features:
    - Configurable delay between uploads
    - Time window restrictions
    - Multi-channel support
    - Persistent schedule (JSON)
    - Schedule publishing with YouTube API
    """

    def __init__(self, schedule_file: Path | None = None):
        self.schedule_file = schedule_file or Path("temp/upload_schedule.json")
        self.schedule = self._load_schedule()
        self.history_file = Path("temp/upload_history.json")
        self.upload_history = self._load_upload_history()

    def _load_schedule(self) -> UploadSchedule:
        """Load schedule from disk."""
        if self.schedule_file.exists():
            try:
                data = json.loads(self.schedule_file.read_text())
                uploads = []
                for item in data.get("uploads", []):
                    uploads.append(
                        ScheduledUpload(
                            video_path=Path(item["video_path"]),
                            title=item["title"],
                            description=item.get("description", ""),
                            tags=item.get("tags", []),
                            channel_name=item["channel_name"],
                            publish_at=datetime.fromisoformat(item["publish_at"]),
                            status=item.get("status", "pending"),
                        )
                    )
                return UploadSchedule(uploads=uploads)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("schedule_load_failed", error=str(e))
        return UploadSchedule()

    def _save_schedule(self) -> None:
        """Persist schedule to disk."""
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "uploads": [
                {
                    "video_path": str(u.video_path),
                    "title": u.title,
                    "description": u.description,
                    "tags": u.tags,
                    "channel_name": u.channel_name,
                    "publish_at": u.publish_at.isoformat(),
                    "status": u.status,
                }
                for u in self.schedule.uploads
            ]
        }
        self.schedule_file.write_text(json.dumps(data, indent=2))

    def _load_upload_history(self) -> dict[str, Any]:
        """Load upload history JSON from disk."""
        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text())
                if isinstance(data, dict):
                    data.setdefault("channels", {})
                    return data
            except json.JSONDecodeError as e:
                logger.warning("history_load_failed", error=str(e))
        return {"channels": {}}

    def _save_upload_history(self) -> None:
        """Persist upload history JSON to disk."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history_file.write_text(json.dumps(self.upload_history, indent=2))

    def _get_uploaded_dir(self, channel_name: str) -> Path:
        """Get channel uploaded directory under output/<channel>/uploaded."""
        config = get_config()
        channel_config = config.channels.get(channel_name)
        if channel_config and channel_config.output_folder:
            uploaded_dir = Path(channel_config.output_folder) / "uploaded"
        else:
            uploaded_dir = Path("output") / channel_name / "uploaded"
        uploaded_dir.mkdir(parents=True, exist_ok=True)
        return uploaded_dir

    def _move_uploaded_video(self, upload: ScheduledUpload) -> Path | None:
        """Move uploaded video into output/<channel>/uploaded and return new path."""
        source = upload.video_path
        if not source.exists():
            logger.warning("uploaded_file_missing", path=str(source))
            return None

        target_dir = self._get_uploaded_dir(upload.channel_name)
        target = target_dir / source.name

        # Avoid overwriting existing files in uploaded dir.
        if target.exists():
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            target = target_dir / f"{source.stem}_{timestamp}{source.suffix}"

        try:
            shutil.move(str(source), str(target))
            logger.info("uploaded_video_moved", source=str(source), target=str(target))
            return target
        except Exception as e:
            logger.warning("uploaded_video_move_failed", source=str(source), error=str(e))
            return None

    def _record_upload_history(
        self,
        upload: ScheduledUpload,
        result: UploadResult,
        moved_path: Path | None,
    ) -> None:
        """Append successful upload details to temp/upload_history.json."""
        channels = self.upload_history.setdefault("channels", {})
        channel_history = channels.setdefault(upload.channel_name, {})
        channel_history["last_scheduled"] = upload.publish_at.isoformat()
        uploads = channel_history.setdefault("uploads", [])

        uploads.append(
            {
                "file": (moved_path.name if moved_path else upload.video_path.name),
                "path": str(moved_path if moved_path else upload.video_path),
                "title": upload.title,
                "type": "short" if "part" in upload.video_path.stem.lower() else "longform",
                "scheduled_at": upload.publish_at.isoformat(),
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "youtube_url": result.url,
                "video_id": result.video_id,
                "channel": upload.channel_name,
            }
        )
        self._save_upload_history()

    def _get_next_upload_time(
        self,
        channel_config: Any,
        current_time: datetime,
    ) -> datetime:
        """
        Get next upload time based on configured daily times.
        If current time is past today's last upload time, move to tomorrow.
        """
        schedule_times = channel_config.youtube.schedule_times
        if not schedule_times:
            schedule_times = ["13:07", "15:06", "17:07", "21:07"]

        times = []
        for time_str in sorted(schedule_times):
            h, m = map(int, time_str.split(":"))
            times.append((h, m))

        # Create datetime objects for today's upload times
        today_times = [
            current_time.replace(hour=h, minute=m, second=0, microsecond=0)
            for h, m in times
        ]

        # Find the next upload time
        for upload_time in today_times:
            if upload_time > current_time:
                return upload_time

        # If no time left today, use first time tomorrow
        h, m = times[0]
        tomorrow = (current_time + timedelta(days=1)).replace(
            hour=h, minute=m, second=0, microsecond=0
        )
        return tomorrow

    def schedule_uploads(
        self,
        video_paths: list[Path],
        channel_name: str,
        title_prefix: str = "",
        description: str = "",
        tags: list[str] | None = None,
        start_time: datetime | None = None,
        interval_hours: int | None = None,
        use_daily_times: bool = True,
    ) -> list[ScheduledUpload]:
        """
        Schedule multiple videos for upload.

        Args:
            video_paths: Videos to upload.
            channel_name: Target channel.
            title_prefix: Prefix for auto-generated titles.
            description: Video description.
            tags: Tags for all videos.
            start_time: When to start publishing (default: now + delay).
            interval_hours: Hours between each publish (if use_daily_times=False).
            use_daily_times: If True, use configured daily times; else use interval_hours.
        """
        config = get_config()
        channel_config = config.channels.get(channel_name)

        # Check for continuation from last schedule
        if start_time is None and use_daily_times:
            last_upload = self._get_last_upload(channel_name)
            if last_upload and last_upload.status == "completed":
                # Continue from the last upload time
                start_time = last_upload.publish_at + timedelta(minutes=1)
            else:
                # Start from now
                start_time = datetime.now(timezone.utc)
        elif start_time is None:
            if interval_hours is None:
                interval_hours = (
                    channel_config.youtube.schedule_delay_hours
                    if channel_config
                    else 24
                )
            start_time = datetime.now(timezone.utc) + timedelta(hours=interval_hours)

        scheduled: list[ScheduledUpload] = []
        current_time = start_time
        max_days = channel_config.youtube.schedule_duration_days if channel_config else 7
        end_time = start_time + timedelta(days=max_days)

        for idx, path in enumerate(video_paths):
            # Stop scheduling if we've exceeded max duration
            if current_time > end_time:
                logger.warning(
                    "schedule_duration_exceeded",
                    max_days=max_days,
                    channel=channel_name,
                )
                break

            # Get next upload time
            if use_daily_times and channel_config:
                current_time = self._get_next_upload_time(channel_config, current_time)
            else:
                if idx > 0:
                    current_time += timedelta(hours=interval_hours)

            title = f"{title_prefix} Part {idx + 1}" if title_prefix else path.stem

            upload = ScheduledUpload(
                video_path=path,
                title=title,
                description=description,
                tags=tags or [],
                channel_name=channel_name,
                publish_at=current_time,
            )
            scheduled.append(upload)
            self.schedule.uploads.append(upload)

            # Move to next slot (move past current time to next upload window)
            current_time += timedelta(minutes=1)

        self._save_schedule()
        logger.info(
            "uploads_scheduled",
            count=len(scheduled),
            channel=channel_name,
            start=start_time.isoformat(),
            mode="daily_times" if use_daily_times else f"{interval_hours}h",
        )

        return scheduled

    def _get_last_upload(self, channel_name: str) -> ScheduledUpload | None:
        """Get the last scheduled/completed upload for a channel."""
        channel_uploads = [
            u for u in self.schedule.uploads
            if u.channel_name == channel_name
        ]
        if not channel_uploads:
            return None
        # Return the one with latest publish_at
        return max(channel_uploads, key=lambda u: u.publish_at)

    def execute_pending(self) -> list[UploadResult]:
        """Execute all pending scheduled uploads."""
        config = get_config()
        results: list[UploadResult] = []

        pending = [u for u in self.schedule.uploads if u.status == "pending"]
        if not pending:
            logger.info("no_pending_uploads")
            return results

        # Group by channel
        by_channel: dict[str, list[ScheduledUpload]] = {}
        for upload in pending:
            by_channel.setdefault(upload.channel_name, []).append(upload)

        for channel_name, uploads in by_channel.items():
            channel_config = config.channels.get(channel_name)
            if not channel_config or not channel_config.upload_enabled:
                logger.warning("upload_disabled", channel=channel_name)
                continue

            uploader = YouTubeUploader(channel_name)
            try:
                uploader.authenticate()
            except Exception as e:
                logger.error("auth_failed", channel=channel_name, error=str(e))
                continue

            for upload in uploads:
                upload.status = "uploading"
                self._save_schedule()

                try:
                    result = uploader.upload(
                        video_path=upload.video_path,
                        title=upload.title,
                        description=upload.description,
                        tags=upload.tags,
                        publish_at=upload.publish_at.isoformat(),
                    )
                    upload.result = result
                    upload.status = "completed" if result.success else "failed"
                    if result.success:
                        moved_path = self._move_uploaded_video(upload)
                        self._record_upload_history(upload, result, moved_path)
                    results.append(result)
                except Exception as e:
                    upload.status = "failed"
                    logger.error("upload_failed", title=upload.title, error=str(e))

                self._save_schedule()

        return results

    def get_pending_count(self) -> int:
        """Get number of pending uploads."""
        return sum(1 for u in self.schedule.uploads if u.status == "pending")

    def clear_completed(self) -> int:
        """Remove completed uploads from schedule."""
        before = len(self.schedule.uploads)
        self.schedule.uploads = [
            u for u in self.schedule.uploads if u.status != "completed"
        ]
        removed = before - len(self.schedule.uploads)
        self._save_schedule()
        return removed
