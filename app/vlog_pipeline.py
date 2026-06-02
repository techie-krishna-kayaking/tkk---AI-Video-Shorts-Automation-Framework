"""Generic vlog pipeline API.

This module re-exports the mixed-media workflow from trip_pipeline for
backward compatibility while providing vlog-first naming.
"""

from __future__ import annotations

from app.trip_pipeline import (
    MediaItem,
    PlatformExportResult,
    VlogLongformResult,
    create_platform_exports,
    create_vlog_longform,
    discover_vlog_media,
)

__all__ = [
    "MediaItem",
    "PlatformExportResult",
    "VlogLongformResult",
    "discover_vlog_media",
    "create_vlog_longform",
    "create_platform_exports",
]
