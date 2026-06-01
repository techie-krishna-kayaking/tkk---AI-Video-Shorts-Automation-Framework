"""Provider-based trending audio ingestion.

This module supports automated ingestion from configurable providers and
writes local manifests consumed by the export pipeline.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.utils.config import get_config
from app.utils.files import sanitize_filename
from app.utils.logging import get_logger

logger = get_logger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


@dataclass
class IngestSummary:
    provider: str
    total_tracks: int
    instagram_tracks: int
    youtube_tracks: int
    instagram_manifest: Path
    youtube_manifest: Path


class TrendingAudioProvider:
    """Ingest trending audio metadata and tracks from configured provider."""

    def __init__(self):
        self.config = get_config()
        self.trip_config = self.config.trip
        self.provider = self.trip_config.trending_provider
        self.instagram_manifest = Path(self.trip_config.instagram_trending_manifest)
        self.youtube_manifest = Path(self.trip_config.youtube_trending_manifest)

    def is_enabled(self) -> bool:
        return bool(self.provider.enabled)

    def refresh(self, limit: int) -> IngestSummary:
        provider_type = self.provider.provider_type.strip().lower()

        if provider_type == "filesystem":
            tracks = self._ingest_from_filesystem(limit=limit)
        elif provider_type == "remote_manifest":
            tracks = self._ingest_from_remote_manifest(limit=limit)
        elif provider_type == "pixabay_audio":
            tracks = self._ingest_from_pixabay(limit=limit)
        else:
            raise ValueError(f"Unsupported provider_type: {self.provider.provider_type}")

        instagram_tracks: list[dict[str, Any]] = []
        youtube_tracks: list[dict[str, Any]] = []

        for track in tracks:
            platform = str(track.get("platform", "instagram")).lower()
            track_data = {
                "title": track.get("title", "untitled"),
                "path": str(track.get("path", "")),
            }
            if platform == "youtube":
                youtube_tracks.append(track_data)
            elif platform == "both":
                instagram_tracks.append(track_data)
                youtube_tracks.append(track_data)
            else:
                instagram_tracks.append(track_data)

        if not instagram_tracks and youtube_tracks:
            instagram_tracks = youtube_tracks[:]
        if not youtube_tracks and instagram_tracks:
            youtube_tracks = instagram_tracks[:]

        self._write_manifest(self.instagram_manifest, instagram_tracks)
        self._write_manifest(self.youtube_manifest, youtube_tracks)

        summary = IngestSummary(
            provider=provider_type,
            total_tracks=len(tracks),
            instagram_tracks=len(instagram_tracks),
            youtube_tracks=len(youtube_tracks),
            instagram_manifest=self.instagram_manifest,
            youtube_manifest=self.youtube_manifest,
        )
        logger.info(
            "trending_audio_provider_refreshed",
            provider=summary.provider,
            total_tracks=summary.total_tracks,
            instagram_tracks=summary.instagram_tracks,
            youtube_tracks=summary.youtube_tracks,
            instagram_manifest=str(summary.instagram_manifest),
            youtube_manifest=str(summary.youtube_manifest),
        )
        return summary

    def _ingest_from_filesystem(self, limit: int) -> list[dict[str, Any]]:
        source_dir = Path(self.provider.source_dir)
        if not source_dir.exists():
            logger.warning("trending_source_dir_missing", source_dir=str(source_dir))
            return []

        candidates = sorted(
            [
                p for p in source_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
            ],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        resolved: list[dict[str, Any]] = []
        for path in candidates[: max(1, limit)]:
            lower = path.name.lower()
            if "youtube" in lower or lower.endswith("_yt" + path.suffix.lower()):
                platform = "youtube"
            elif "both" in lower:
                platform = "both"
            else:
                platform = "instagram"

            resolved.append(
                {
                    "title": path.stem,
                    "platform": platform,
                    "path": str(path.resolve()),
                }
            )

        return resolved

    def _ingest_from_remote_manifest(self, limit: int) -> list[dict[str, Any]]:
        url = self.provider.source_manifest_url.strip()
        if not url:
            logger.warning("trending_manifest_url_missing")
            return []

        headers: dict[str, str] = {}
        if self.provider.auth_env_var:
            token = os.getenv(self.provider.auth_env_var)
            if token:
                headers["Authorization"] = f"Bearer {token}"

        response = httpx.get(
            url,
            headers=headers,
            timeout=max(1, int(self.provider.request_timeout_seconds)),
        )
        response.raise_for_status()
        payload = response.json()

        tracks = payload.get("tracks", []) if isinstance(payload, dict) else payload
        if not isinstance(tracks, list):
            logger.warning("trending_manifest_invalid_payload", url=url)
            return []

        download_dir = Path(self.provider.download_dir)
        download_dir.mkdir(parents=True, exist_ok=True)

        resolved: list[dict[str, Any]] = []
        for idx, item in enumerate(tracks[: max(1, limit)], 1):
            if not isinstance(item, dict):
                continue

            title = str(item.get("title") or f"track_{idx:03d}")
            platform = str(item.get("platform") or "instagram").lower()
            audio_url = str(item.get("audio_url") or "").strip()
            if not audio_url:
                continue

            ext = Path(audio_url.split("?")[0]).suffix.lower() or ".mp3"
            if ext not in AUDIO_EXTENSIONS:
                ext = ".mp3"

            file_name = f"{idx:03d}_{sanitize_filename(title)}{ext}"
            destination = (download_dir / file_name).resolve()

            with httpx.stream(
                "GET",
                audio_url,
                headers=headers,
                timeout=max(1, int(self.provider.request_timeout_seconds)),
            ) as stream:
                stream.raise_for_status()
                with open(destination, "wb") as handle:
                    for chunk in stream.iter_bytes():
                        if chunk:
                            handle.write(chunk)

            resolved.append(
                {
                    "title": title,
                    "platform": platform,
                    "path": str(destination),
                }
            )

        return resolved

    def _ingest_from_pixabay(self, limit: int) -> list[dict[str, Any]]:
        api_key = os.getenv(self.provider.pixabay_api_key_env)
        if not api_key:
            logger.warning(
                "pixabay_key_missing",
                env_var=self.provider.pixabay_api_key_env,
            )
            return []

        params = {
            "key": api_key,
            "per_page": max(3, min(200, limit)),
            "order": self.provider.pixabay_order or "popular",
            "category": self.provider.pixabay_category or "music",
        }

        response = httpx.get(
            "https://pixabay.com/api/audio/",
            params=params,
            timeout=max(1, int(self.provider.request_timeout_seconds)),
        )
        response.raise_for_status()
        payload = response.json()

        hits = payload.get("hits", []) if isinstance(payload, dict) else []
        if not isinstance(hits, list):
            logger.warning("pixabay_payload_invalid")
            return []

        download_dir = Path(self.provider.download_dir)
        download_dir.mkdir(parents=True, exist_ok=True)

        resolved: list[dict[str, Any]] = []
        for idx, item in enumerate(hits[: max(1, limit)], 1):
            if not isinstance(item, dict):
                continue

            title = str(item.get("tags") or item.get("id") or f"pixabay_{idx:03d}")
            audio_details = item.get("audio") if isinstance(item.get("audio"), dict) else {}
            audio_url = (
                audio_details.get("high")
                or audio_details.get("medium")
                or audio_details.get("low")
            )
            if not audio_url:
                continue

            file_name = f"pixabay_{idx:03d}_{sanitize_filename(title)}.mp3"
            destination = (download_dir / file_name).resolve()

            with httpx.stream(
                "GET",
                audio_url,
                timeout=max(1, int(self.provider.request_timeout_seconds)),
            ) as stream:
                stream.raise_for_status()
                with open(destination, "wb") as handle:
                    for chunk in stream.iter_bytes():
                        if chunk:
                            handle.write(chunk)

            # Pixabay is used here as a legal free source; apply to both platforms.
            resolved.append(
                {
                    "title": title,
                    "platform": "both",
                    "path": str(destination),
                }
            )

        return resolved

    @staticmethod
    def _write_manifest(path: Path, tracks: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"tracks": tracks}, indent=2), encoding="utf-8")
