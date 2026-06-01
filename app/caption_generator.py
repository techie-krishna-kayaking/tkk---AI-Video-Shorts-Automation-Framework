"""Caption and subtitle generation (SRT & ASS formats)."""

from __future__ import annotations

from pathlib import Path

from app.transcriber import Segment, Transcription, Word
from app.utils.config import get_config
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CaptionGenerator:
    """Generate SRT and ASS subtitle files from transcription data."""

    def __init__(self):
        config = get_config()
        self.font = config.captions.font
        self.font_size = config.captions.font_size
        self.font_color = config.captions.font_color
        self.outline_color = config.captions.outline_color
        self.outline_width = config.captions.outline_width
        self.max_words_per_line = config.captions.max_words_per_line
        self.position = config.captions.position

    def generate_srt(
        self,
        transcription: Transcription,
        output_path: Path,
        clip_start: float = 0.0,
        clip_end: float | None = None,
    ) -> Path:
        """
        Generate an SRT subtitle file.

        Args:
            transcription: The transcription data.
            output_path: Where to write the SRT file.
            clip_start: Offset start time (for clips).
            clip_end: End time limit.
        """
        output_path = output_path.with_suffix(".srt")
        lines: list[str] = []
        counter = 1

        for segment in transcription.segments:
            if clip_end and segment.start > clip_end:
                break
            if segment.end < clip_start:
                continue

            # Prefer word-level caption chunks, but fall back to segment-level text
            # when word timestamps are unavailable (e.g. fast mode).
            word_groups = self._split_into_groups(segment.words, clip_start, clip_end)

            if word_groups:
                caption_items: list[tuple[float, float, str]] = []
                for words in word_groups:
                    if not words:
                        continue
                    start_time = max(0, words[0].start - clip_start)
                    end_time = max(0, words[-1].end - clip_start)
                    text = " ".join(w.text for w in words).strip()
                    if text:
                        caption_items.append((start_time, end_time, text))
            else:
                seg_start = max(segment.start, clip_start)
                seg_end = min(segment.end, clip_end) if clip_end is not None else segment.end
                seg_text = segment.text.strip()
                caption_items = []
                if seg_end > seg_start and seg_text:
                    caption_items.append((max(0, seg_start - clip_start), max(0, seg_end - clip_start), seg_text))

            for start_time, end_time, text in caption_items:
                if end_time <= start_time:
                    continue

                lines.append(str(counter))
                lines.append(
                    f"{self._format_srt_time(start_time)} --> {self._format_srt_time(end_time)}"
                )
                lines.append(text)
                lines.append("")
                counter += 1

        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("srt_generated", path=str(output_path), entries=counter - 1)
        return output_path

    def generate_ass(
        self,
        transcription: Transcription,
        output_path: Path,
        clip_start: float = 0.0,
        clip_end: float | None = None,
        video_width: int = 1080,
        video_height: int = 1920,
    ) -> Path:
        """
        Generate an ASS (Advanced SubStation Alpha) subtitle file with styling.

        Supports:
        - Custom fonts and colors
        - Outline/shadow
        - Positioning
        - Word-level highlighting (karaoke style)
        """
        output_path = output_path.with_suffix(".ass")

        # Convert hex colors to ASS BGR format
        primary_color = self._hex_to_ass_color(self.font_color)
        outline_color = self._hex_to_ass_color(self.outline_color)

        # ASS header
        header = f"""[Script Info]
Title: Auto-generated Subtitles
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat,{self.font_size},{primary_color},&H000000FF,{outline_color},&H80000000,1,0,0,0,100,100,0,0,1,{self.outline_width},1,2,50,50,100,1
Style: Highlight,Montserrat,{self.font_size + 4},&H0000FFFF,&H000000FF,{outline_color},&H80000000,1,0,0,0,100,100,0,0,1,{self.outline_width + 1},2,2,50,50,100,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events: list[str] = []

        for segment in transcription.segments:
            if clip_end and segment.start > clip_end:
                break
            if segment.end < clip_start:
                continue

            word_groups = self._split_into_groups(segment.words, clip_start, clip_end)

            if word_groups:
                for words in word_groups:
                    if not words:
                        continue
                    start_time = max(0, words[0].start - clip_start)
                    end_time = max(0, words[-1].end - clip_start)
                    if end_time <= start_time:
                        continue

                    # Use karaoke-style word highlighting when word timings are available.
                    karaoke_text = self._build_karaoke_text(words, clip_start)

                    events.append(
                        f"Dialogue: 0,{self._format_ass_time(start_time)},"
                        f"{self._format_ass_time(end_time)},Default,,0,0,0,,"
                        f"{karaoke_text}"
                    )
            else:
                seg_start = max(segment.start, clip_start)
                seg_end = min(segment.end, clip_end) if clip_end is not None else segment.end
                seg_text = segment.text.strip()
                if seg_end <= seg_start or not seg_text:
                    continue

                events.append(
                    f"Dialogue: 0,{self._format_ass_time(max(0, seg_start - clip_start))},"
                    f"{self._format_ass_time(max(0, seg_end - clip_start))},Default,,0,0,0,,"
                    f"{seg_text}"
                )

        content = header + "\n".join(events) + "\n"
        output_path.write_text(content, encoding="utf-8")
        logger.info("ass_generated", path=str(output_path), events=len(events))
        return output_path

    def _split_into_groups(
        self,
        words: list[Word],
        clip_start: float,
        clip_end: float | None,
    ) -> list[list[Word]]:
        """Split words into display groups based on max_words_per_line."""
        filtered = [
            w for w in words
            if w.start >= clip_start and (clip_end is None or w.end <= clip_end)
        ]

        groups: list[list[Word]] = []
        for i in range(0, len(filtered), self.max_words_per_line):
            groups.append(filtered[i:i + self.max_words_per_line])

        return groups

    def _build_karaoke_text(self, words: list[Word], offset: float) -> str:
        """Build ASS karaoke-style text with word-level timing."""
        parts: list[str] = []
        for word in words:
            duration_cs = int((word.end - word.start) * 100)
            parts.append(f"{{\\kf{duration_cs}}}{word.text}")
        return " ".join(parts)

    def _format_srt_time(self, seconds: float) -> str:
        """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_ass_time(self, seconds: float) -> str:
        """Format seconds as ASS timestamp (H:MM:SS.cc)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centis = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"

    def _hex_to_ass_color(self, hex_color: str) -> str:
        """Convert hex color (#RRGGBB) to ASS color (&HBBGGRR&)."""
        hex_color = hex_color.lstrip("#")
        r = hex_color[0:2]
        g = hex_color[2:4]
        b = hex_color[4:6]
        return f"&H00{b}{g}{r}&"
