"""Upload scheduling with configurable delay and time windows."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

    def schedule_uploads(
        self,
        video_paths: list[Path],
        channel_name: str,
        title_prefix: str = "",
        description: str = "",
        tags: list[str] | None = None,
        start_time: datetime | None = None,
        interval_hours: int | None = None,
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
            interval_hours: Hours between each publish.
        """
        config = get_config()
        channel_config = config.channels.get(channel_name)

        if interval_hours is None:
            interval_hours = (
                channel_config.youtube.schedule_delay_hours
                if channel_config
                else 24
            )

        if start_time is None:
            start_time = datetime.now(timezone.utc) + timedelta(hours=interval_hours)

        scheduled: list[ScheduledUpload] = []
        current_time = start_time

        for idx, path in enumerate(video_paths):
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
            current_time += timedelta(hours=interval_hours)

        self._save_schedule()
        logger.info(
            "uploads_scheduled",
            count=len(scheduled),
            channel=channel_name,
            start=start_time.isoformat(),
            interval=f"{interval_hours}h",
        )

        return scheduled

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
