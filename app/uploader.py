"""YouTube upload module using YouTube Data API v3."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httplib2
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.utils.config import ChannelConfig, get_config
from app.utils.logging import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
MAX_RETRIES = 10


@dataclass
class UploadResult:
    """Result of a YouTube upload."""
    video_id: str
    title: str
    url: str
    success: bool
    error: str = ""


class YouTubeUploader:
    """
    YouTube video uploader with OAuth2 authentication.

    Features:
    - OAuth2 flow
    - Resumable uploads
    - Schedule publishing
    - Multi-channel support
    - Retry handling
    """

    def __init__(self, channel_name: str | None = None):
        config = get_config()
        self.channel_name = channel_name
        self.channel_config: ChannelConfig | None = None

        if channel_name and channel_name in config.channels:
            self.channel_config = config.channels[channel_name]

        self._service = None

    def authenticate(self, client_secrets_path: Path | None = None, credentials_path: Path | None = None) -> None:
        """
        Authenticate with YouTube API using OAuth2.

        First tries to load saved credentials, then initiates OAuth flow.
        """
        if client_secrets_path is None and self.channel_config:
            client_secrets_path = Path(self.channel_config.youtube.client_secrets)
        if credentials_path is None and self.channel_config:
            credentials_path = Path(self.channel_config.youtube.credentials)

        if client_secrets_path is None:
            raise ValueError("No client secrets path provided")

        credentials = None

        # Try loading saved credentials
        if credentials_path and credentials_path.exists():
            try:
                credentials = Credentials.from_authorized_user_file(
                    str(credentials_path), SCOPES
                )
                if credentials.valid:
                    logger.info("credentials_loaded", path=str(credentials_path))
                else:
                    credentials = None
            except Exception:
                credentials = None

        # Run OAuth flow if needed
        if credentials is None:
            if not client_secrets_path.exists():
                raise FileNotFoundError(
                    f"Client secrets not found: {client_secrets_path}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path), SCOPES
            )
            credentials = flow.run_local_server(port=0)

            # Save credentials
            if credentials_path:
                credentials_path.parent.mkdir(parents=True, exist_ok=True)
                credentials_path.write_text(credentials.to_json())
                logger.info("credentials_saved", path=str(credentials_path))

        self._service = build(
            API_SERVICE_NAME,
            API_VERSION,
            credentials=credentials,
        )
        logger.info("youtube_authenticated")

    @property
    def service(self):
        """Get authenticated YouTube service."""
        if self._service is None:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        return self._service

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        category_id: str = "22",
        privacy_status: str = "private",
        publish_at: str | None = None,
        thumbnail_path: Path | None = None,
    ) -> UploadResult:
        """
        Upload a video to YouTube.

        Args:
            video_path: Path to the video file.
            title: Video title.
            description: Video description.
            tags: List of tags.
            category_id: YouTube category ID.
            privacy_status: 'private', 'public', or 'unlisted'.
            publish_at: ISO 8601 datetime for scheduled publishing.
            thumbnail_path: Path to custom thumbnail image.
        """
        if not video_path.exists():
            return UploadResult(
                video_id="",
                title=title,
                url="",
                success=False,
                error=f"Video file not found: {video_path}",
            )

        # Apply channel defaults
        if self.channel_config:
            yt_config = self.channel_config.youtube
            if not tags:
                tags = yt_config.default_tags
            category_id = category_id or yt_config.default_category
            privacy_status = privacy_status or yt_config.privacy_status

        body: dict[str, Any] = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        # Schedule publishing
        if publish_at and privacy_status == "private":
            body["status"]["privacyStatus"] = "private"
            body["status"]["publishAt"] = publish_at

        logger.info(
            "uploading_video",
            path=str(video_path),
            title=title,
            privacy=privacy_status,
        )

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=10 * 1024 * 1024,  # 10MB chunks
        )

        request = self.service.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        # Resumable upload with retry
        response = self._resumable_upload(request)

        if response:
            video_id = response["id"]
            url = f"https://www.youtube.com/watch?v={video_id}"

            # Set thumbnail if provided
            if thumbnail_path and thumbnail_path.exists():
                self._set_thumbnail(video_id, thumbnail_path)

            logger.info("upload_complete", video_id=video_id, url=url)
            return UploadResult(
                video_id=video_id,
                title=title,
                url=url,
                success=True,
            )

        return UploadResult(
            video_id="",
            title=title,
            url="",
            success=False,
            error="Upload failed after retries",
        )

    def _resumable_upload(self, request) -> dict[str, Any] | None:
        """Execute resumable upload with exponential backoff retry."""
        response = None
        retry = 0

        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    logger.info("upload_progress", progress=f"{status.progress() * 100:.1f}%")
            except httplib2.HttpLib2Error as e:
                if retry >= MAX_RETRIES:
                    logger.error("upload_max_retries", error=str(e))
                    return None
                retry += 1
                sleep_time = min(2**retry, 64)
                logger.warning("upload_retry", attempt=retry, sleep=sleep_time)
                time.sleep(sleep_time)
            except Exception as e:
                error_content = getattr(e, "content", str(e))
                logger.error("upload_error", error=str(error_content))
                return None

        return response

    def _set_thumbnail(self, video_id: str, thumbnail_path: Path) -> bool:
        """Set a custom thumbnail for an uploaded video."""
        try:
            self.service.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path)),
            ).execute()
            logger.info("thumbnail_set", video_id=video_id)
            return True
        except Exception as e:
            logger.warning("thumbnail_failed", error=str(e))
            return False

    def upload_batch(
        self,
        video_paths: list[Path],
        title_prefix: str = "",
        description: str = "",
        delay_between: int = 60,
    ) -> list[UploadResult]:
        """Upload multiple videos with delay between uploads."""
        results: list[UploadResult] = []

        for idx, path in enumerate(video_paths):
            title = f"{title_prefix} Part {idx + 1}" if title_prefix else path.stem
            result = self.upload(
                video_path=path,
                title=title,
                description=description,
            )
            results.append(result)

            # Rate limiting
            if idx < len(video_paths) - 1:
                logger.info("upload_delay", seconds=delay_between)
                time.sleep(delay_between)

        return results
