"""Configuration management using Pydantic models and YAML."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class VideoConfig(BaseModel):
    output_width: int = 1080
    output_height: int = 1920
    fps: int = 30
    codec: str = "h264"
    audio_codec: str = "aac"
    audio_bitrate: str = "256k"
    video_bitrate: str = "16M"
    preset: str = "slow"
    crf: int = 16


class ShortsConfig(BaseModel):
    min_duration: float = 15.0
    max_duration: float = 60.0
    target_duration: float = 45.0
    silence_threshold: float = -40.0
    silence_min_duration: float = 2.0
    overlap_seconds: float = 0.5


class TranscriptionConfig(BaseModel):
    model: str = "base"
    language: str = "en"
    word_timestamps: bool = True
    device: str = "auto"


class CaptionsConfig(BaseModel):
    enabled: bool = True
    style: str = "modern"
    font: str = "assets/fonts/Montserrat-Bold.ttf"
    font_size: int = 48
    font_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline_width: int = 3
    position: str = "center"
    max_words_per_line: int = 6


class RenderingConfig(BaseModel):
    gpu_enabled: bool = True
    gpu_encoder: str = "h264_nvenc"
    cpu_encoder: str = "libx264"
    threads: int = 0
    hwaccel: str = "cuda"


class ProcessingConfig(BaseModel):
    batch_size: int = 5
    max_workers: int = 4
    retry_attempts: int = 3
    retry_delay: int = 5


class WatcherConfig(BaseModel):
    enabled: bool = False
    poll_interval: int = 10
    recursive: bool = True


class OutputConfig(BaseModel):
    base_dir: str = "output"
    format: str = "mp4"
    naming_pattern: str = "{video_name}_part{number:03d}"


class InputConfig(BaseModel):
    base_dir: str = "input"


class AssetsConfig(BaseModel):
    social_dir: str = "assets/social"
    fonts_dir: str = "assets/fonts"
    overlays_dir: str = "assets/overlays"


class TrendingProviderConfig(BaseModel):
    enabled: bool = False
    provider_type: str = "filesystem"  # filesystem | remote_manifest | pixabay_audio
    source_dir: str = "assets/audio/trending"
    source_manifest_url: str = ""
    auth_env_var: str = ""
    download_dir: str = "assets/audio/ingested"
    request_timeout_seconds: int = 30
    pixabay_api_key_env: str = "PIXABAY_API_KEY"
    pixabay_category: str = "music"
    pixabay_order: str = "popular"


class TripConfig(BaseModel):
    photo_duration: float = 4.0
    ken_burns_enabled: bool = True
    blur_background_enabled: bool = True
    instagram_music_volume: float = 0.2
    trending_audio_count: int = 100
    cleanup_after_upload: bool = True
    output_width: int = 3840
    output_height: int = 2160
    instagram_trending_manifest: str = "configs/trending_audio_instagram.json"
    youtube_trending_manifest: str = "configs/trending_audio_youtube.json"
    trending_provider: TrendingProviderConfig = Field(default_factory=TrendingProviderConfig)


class YouTubeChannelConfig(BaseModel):
    client_secrets: str = ""
    credentials: str = ""
    default_tags: list[str] = Field(default_factory=list)
    default_category: str = "22"
    privacy_status: str = "private"
    schedule_delay_hours: int = 24
    schedule_times: list[str] = Field(default_factory=lambda: ["13:07", "15:07", "17:07", "21:07"])  # HH:MM format, 4x/day default
    schedule_timezone: str = "UTC"  # IANA timezone name, e.g. Asia/Kolkata
    schedule_duration_days: int = 7
    auto_upload_captions: bool = True
    monetization_enabled: bool = False
    made_for_kids: bool = False
    license_type: str = "creativeCommon"  # creativeCommon or youtube


class ChannelConfig(BaseModel):
    type: str = "tutorial"
    name: str = ""
    youtube_url: str = ""
    input_folder: str = ""
    output_folder: str = ""
    socials_file: str = ""
    social_footer: str = ""  # legacy compat
    intro_text: str = ""
    hook_keywords: list[str] = Field(default_factory=list)
    upload_enabled: bool = False
    youtube: YouTubeChannelConfig = Field(default_factory=YouTubeChannelConfig)


class AppConfig(BaseModel):
    """Main application configuration."""

    video: VideoConfig = Field(default_factory=VideoConfig)
    shorts: ShortsConfig = Field(default_factory=ShortsConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    captions: CaptionsConfig = Field(default_factory=CaptionsConfig)
    rendering: RenderingConfig = Field(default_factory=RenderingConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    watcher: WatcherConfig = Field(default_factory=WatcherConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    input: InputConfig = Field(default_factory=InputConfig)
    assets: AssetsConfig = Field(default_factory=AssetsConfig)
    trip: TripConfig = Field(default_factory=TripConfig)
    channels: dict[str, ChannelConfig] = Field(default_factory=dict)


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file safely."""
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def load_config(
    app_config_path: Path | None = None,
    channels_config_path: Path | None = None,
) -> AppConfig:
    """Load and merge application and channel configs."""
    project_root = Path(__file__).parent.parent.parent

    if app_config_path is None:
        app_config_path = project_root / "configs" / "app.yaml"
    if channels_config_path is None:
        channels_config_path = project_root / "configs" / "channels.yaml"

    app_data: dict[str, Any] = {}
    if app_config_path.exists():
        raw = load_yaml(app_config_path)
        # Flatten nested 'app' key if present
        if "app" in raw:
            raw.pop("app")
        app_data = raw

    channels_data: dict[str, ChannelConfig] = {}
    if channels_config_path.exists():
        raw_channels = load_yaml(channels_config_path)
        if "channels" in raw_channels:
            for name, channel_dict in raw_channels["channels"].items():
                channels_data[name] = ChannelConfig(**channel_dict)

    config = AppConfig(**app_data, channels=channels_data)
    return config


# Singleton-like config access
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset config for testing."""
    global _config
    _config = None
