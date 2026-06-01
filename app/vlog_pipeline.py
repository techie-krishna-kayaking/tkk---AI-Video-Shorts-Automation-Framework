"""Generic vlog pipeline API.

This module re-exports the mixed-media workflow from trip_pipeline for
backward compatibility while providing vlog-first naming.
"""

from __future__ import annotations

from app.trip_pipeline import (
    MediaItem,
    PlatformExportResult,
    TrendingAudioTrack,
    VlogLongformResult,
    create_platform_exports,
    create_vlog_longform,
    discover_trending_audio,
    discover_vlog_media,
)

__all__ = [
    "MediaItem",
    "PlatformExportResult",
    "TrendingAudioTrack",
    "VlogLongformResult",
    "discover_vlog_media",
    "create_vlog_longform",
    "discover_trending_audio",
    "create_platform_exports",
]
