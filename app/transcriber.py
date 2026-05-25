"""Audio transcription using OpenAI Whisper with word-level timestamps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
import whisper

from app.utils.config import get_config
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Word:
    """A single transcribed word with timing."""
    text: str
    start: float
    end: float
    confidence: float = 1.0


@dataclass
class Segment:
    """A transcription segment (sentence/phrase)."""
    text: str
    start: float
    end: float
    words: list[Word] = field(default_factory=list)


@dataclass
class Transcription:
    """Complete transcription result."""
    text: str
    language: str
    segments: list[Segment] = field(default_factory=list)
    duration: float = 0.0


class Transcriber:
    """Whisper-based audio transcription engine."""

    def __init__(self, model_name: str | None = None, device: str | None = None):
        config = get_config()
        self.model_name = model_name or config.transcription.model
        self.device = device or self._detect_device(config.transcription.device)
        self._model: whisper.Whisper | None = None
        logger.info(
            "transcriber_init",
            model=self.model_name,
            device=self.device,
        )

    def _detect_device(self, device_setting: str) -> str:
        """Detect the best available device."""
        if device_setting != "auto":
            return device_setting
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    @property
    def model(self) -> whisper.Whisper:
        """Lazy-load the Whisper model."""
        if self._model is None:
            logger.info("loading_whisper_model", model=self.model_name, device=self.device)
            self._model = whisper.load_model(self.model_name, device=self.device)
            logger.info("whisper_model_loaded")
        return self._model

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcription:
        """
        Transcribe an audio/video file.

        Args:
            audio_path: Path to the audio or video file.
            language: Language code (e.g., 'en'). None for auto-detect.

        Returns:
            Complete transcription with word-level timestamps.
        """
        config = get_config()
        lang = language or config.transcription.language

        logger.info("transcribing", path=str(audio_path), language=lang)

        result = self.model.transcribe(
            str(audio_path),
            language=lang,
            word_timestamps=config.transcription.word_timestamps,
            verbose=False,
        )

        transcription = self._parse_result(result)
        logger.info(
            "transcription_complete",
            segments=len(transcription.segments),
            duration=f"{transcription.duration:.1f}s",
        )
        return transcription

    def _parse_result(self, result: dict[str, Any]) -> Transcription:
        """Parse Whisper result into structured Transcription."""
        segments: list[Segment] = []

        for seg_data in result.get("segments", []):
            words: list[Word] = []
            for word_data in seg_data.get("words", []):
                words.append(
                    Word(
                        text=word_data["word"].strip(),
                        start=word_data["start"],
                        end=word_data["end"],
                        confidence=word_data.get("probability", 1.0),
                    )
                )

            segments.append(
                Segment(
                    text=seg_data["text"].strip(),
                    start=seg_data["start"],
                    end=seg_data["end"],
                    words=words,
                )
            )

        duration = segments[-1].end if segments else 0.0

        return Transcription(
            text=result.get("text", "").strip(),
            language=result.get("language", "en"),
            segments=segments,
            duration=duration,
        )

    def transcribe_segment(
        self,
        audio_path: Path,
        start: float,
        end: float,
    ) -> Transcription:
        """Transcribe a specific segment of audio using ffmpeg extraction."""
        import subprocess
        import tempfile

        # Extract segment to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-ss", str(start),
            "-to", str(end),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(tmp_path),
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            result = self.transcribe(tmp_path)
            # Offset timestamps
            for seg in result.segments:
                seg.start += start
                seg.end += start
                for word in seg.words:
                    word.start += start
                    word.end += start
            return result
        finally:
            tmp_path.unlink(missing_ok=True)
