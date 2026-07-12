"""Hourly Telegram status reporter for long-running batch jobs.

This module is purely additive: it observes progress that batch commands feed
into a shared, thread-safe :class:`StatusTracker` and, on every top-of-hour
(HH:00 local time), sends a concise Telegram message describing:

  * which channel is being processed
  * folders completed / total
  * long videos completed
  * short videos processed / completed
  * expected time to complete (ETA)

It never affects video processing. All network/errors are swallowed and logged.

Configuration (two values) lives in ``configs/app.yaml`` under ``notifications``
(``telegram_bot_token`` and ``telegram_chat_id``). Environment variables
``TELEGRAM_BOT_TOKEN`` / ``TELEGRAM_CHAT_ID`` override the YAML values.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta

import httpx

from app.utils.config import NotificationsConfig, get_config
from app.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------
class StatusTracker:
    """Thread-safe container for the current run's progress."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.active: bool = False
            self.channel_name: str = ""
            self.unit_label: str = "Folders"
            self.units_total: int = 0
            self.units_completed: int = 0
            self.long_completed: int = 0
            self.shorts_completed: int = 0
            self._channel_start: float | None = None
            self.finished: bool = False

    def begin_channel(self, channel_name: str, units_total: int, unit_label: str = "Folders") -> None:
        """Start tracking a new channel (resets per-channel counters)."""
        with self._lock:
            self.active = True
            self.finished = False
            self.channel_name = channel_name
            self.unit_label = unit_label
            self.units_total = max(int(units_total), 0)
            self.units_completed = 0
            self.long_completed = 0
            self.shorts_completed = 0
            self._channel_start = time.time()

    def unit_done(self, long_added: int = 0, shorts_added: int = 0) -> None:
        """Mark one folder/video as processed and add its long/short counts."""
        with self._lock:
            self.units_completed += 1
            self.long_completed += max(int(long_added), 0)
            self.shorts_completed += max(int(shorts_added), 0)

    def finish(self) -> None:
        with self._lock:
            self.finished = True

    def snapshot(self) -> dict:
        """Return an immutable view of the current state, including ETA seconds."""
        with self._lock:
            eta_seconds: float | None = None
            remaining = self.units_total - self.units_completed
            if self._channel_start and self.units_completed > 0 and remaining > 0:
                elapsed = time.time() - self._channel_start
                per_unit = elapsed / self.units_completed
                eta_seconds = per_unit * remaining
            elif remaining <= 0:
                eta_seconds = 0.0
            return {
                "active": self.active,
                "channel_name": self.channel_name,
                "unit_label": self.unit_label,
                "units_total": self.units_total,
                "units_completed": self.units_completed,
                "long_completed": self.long_completed,
                "shorts_completed": self.shorts_completed,
                "eta_seconds": eta_seconds,
                "finished": self.finished,
            }


_tracker = StatusTracker()


def get_tracker() -> StatusTracker:
    """Return the process-wide status tracker singleton."""
    return _tracker


# ---------------------------------------------------------------------------
# Notifications config resolution
# ---------------------------------------------------------------------------
def get_notifications_config() -> NotificationsConfig:
    """Resolve Telegram settings from app.yaml, overridden by env vars."""
    try:
        cfg = get_config().notifications
    except Exception:
        cfg = NotificationsConfig()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or (cfg.telegram_bot_token or "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip() or (cfg.telegram_chat_id or "").strip()
    return NotificationsConfig(
        enabled=cfg.enabled,
        telegram_bot_token=token,
        telegram_chat_id=chat_id,
    )


def send_telegram_message(token: str, chat_id: str, text: str, timeout: float = 15.0) -> bool:
    """Send a plain-text Telegram message. Returns True on success."""
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = httpx.post(
            url,
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=timeout,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:  # never let notification errors bubble up
        logger.warning("telegram_send_failed", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------
def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "calculating..."
    seconds = int(max(seconds, 0))
    if seconds < 60:
        return f"{seconds}s"
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours > 0:
        return f"~{hours}h {minutes}m"
    return f"~{minutes}m"


def build_status_message(snapshot: dict, *, header: str = "Status update") -> str:
    channel = snapshot.get("channel_name") or "—"
    label = snapshot.get("unit_label", "Folders")
    total = snapshot.get("units_total", 0)
    done = snapshot.get("units_completed", 0)
    long_done = snapshot.get("long_completed", 0)
    shorts_done = snapshot.get("shorts_completed", 0)
    finished = snapshot.get("finished", False)

    now = datetime.now().strftime("%I:%M %p").lstrip("0")

    if finished:
        eta_line = "✅ ETA: done"
    elif total and done >= total:
        eta_line = "✅ ETA: wrapping up"
    else:
        eta_line = f"⏳ ETA: {_format_duration(snapshot.get('eta_seconds'))}"

    lines = [
        f"📊 TKK Video Automation — {header}",
        f"🎬 Channel: {channel}",
        f"📁 {label}: {done}/{total} completed",
        f"🎞️ Long videos: {long_done} completed",
        f"✂️ Shorts: {shorts_done} processed",
        eta_line,
        f"🕐 {now}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Background hourly reporter thread
# ---------------------------------------------------------------------------
class HourlyReporter(threading.Thread):
    """Daemon thread that emits a status message at every top-of-hour."""

    def __init__(self, tracker: StatusTracker, cfg: NotificationsConfig) -> None:
        super().__init__(daemon=True, name="hourly-status-reporter")
        self._tracker = tracker
        self._cfg = cfg
        self._stop = threading.Event()

    @staticmethod
    def _seconds_to_next_hour() -> float:
        now = datetime.now()
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        return max((next_hour - now).total_seconds(), 1.0)

    def _send(self, header: str) -> None:
        snapshot = self._tracker.snapshot()
        if not snapshot.get("active"):
            return
        text = build_status_message(snapshot, header=header)
        send_telegram_message(self._cfg.telegram_bot_token, self._cfg.telegram_chat_id, text)

    def run(self) -> None:
        while not self._stop.is_set():
            wait = self._seconds_to_next_hour()
            if self._stop.wait(timeout=wait):
                break
            self._send(header="Hourly status")

    def stop(self) -> None:
        self._stop.set()

    def send_final(self) -> None:
        self._send(header="Run complete")


_reporter: HourlyReporter | None = None
_reporter_lock = threading.Lock()


def start_status_reporter() -> HourlyReporter | None:
    """Start the hourly reporter if Telegram is configured. Idempotent."""
    global _reporter
    cfg = get_notifications_config()
    if not cfg.enabled or not cfg.telegram_bot_token or not cfg.telegram_chat_id:
        logger.info("status_reporter_disabled")
        return None
    with _reporter_lock:
        if _reporter is not None:
            return _reporter
        _reporter = HourlyReporter(get_tracker(), cfg)
        _reporter.start()
        logger.info("status_reporter_started")
        return _reporter


def stop_status_reporter(send_final: bool = True) -> None:
    """Stop the hourly reporter and optionally send a final completion message."""
    global _reporter
    with _reporter_lock:
        reporter = _reporter
        _reporter = None
    if reporter is None:
        return
    get_tracker().finish()
    if send_final:
        try:
            reporter.send_final()
        except Exception as exc:
            logger.warning("status_reporter_final_failed", error=str(exc))
    reporter.stop()
