"""Smart cropping with face detection for 16:9 to 9:16 conversion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CropRegion:
    """A crop region definition."""
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0


@dataclass
class FaceRegion:
    """Detected face region."""
    x: int
    y: int
    width: int
    height: int
    frame_idx: int


class SmartCrop:
    """
    Smart cropping engine that uses face detection to determine
    optimal crop regions for 16:9 -> 9:16 conversion.
    """

    def __init__(self, sample_interval: float = 1.0):
        """
        Args:
            sample_interval: How often to sample frames for face detection (seconds).
        """
        self.sample_interval = sample_interval
        self._face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    def analyze_faces(self, video_path: Path, duration: float | None = None) -> list[FaceRegion]:
        """
        Detect faces throughout the video.

        Returns a list of face regions with frame indices.
        """
        logger.info("analyzing_faces", path=str(video_path))

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_interval = int(fps * self.sample_interval)

        faces: list[FaceRegion] = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                detected = self._face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(50, 50),
                )

                for (x, y, w, h) in detected:
                    faces.append(
                        FaceRegion(
                            x=int(x),
                            y=int(y),
                            width=int(w),
                            height=int(h),
                            frame_idx=frame_idx,
                        )
                    )

            frame_idx += 1

        cap.release()
        logger.info("faces_detected", count=len(faces), frames_sampled=frame_idx // frame_interval)
        return faces

    def compute_crop_region(
        self,
        source_width: int,
        source_height: int,
        target_width: int = 1080,
        target_height: int = 1920,
        faces: list[FaceRegion] | None = None,
    ) -> CropRegion:
        """
        Compute the optimal crop region for 16:9 -> 9:16 conversion.

        If faces are detected, centers the crop on the face cluster.
        Otherwise, centers the crop on the frame.
        """
        # Calculate crop dimensions (maintain target aspect ratio within source)
        target_ratio = target_width / target_height  # 0.5625 for 9:16
        source_ratio = source_width / source_height

        if source_ratio > target_ratio:
            # Source is wider - crop width
            crop_height = source_height
            crop_width = int(crop_height * target_ratio)
        else:
            # Source is taller - crop height
            crop_width = source_width
            crop_height = int(crop_width / target_ratio)

        # Default: center crop
        x = (source_width - crop_width) // 2
        y = (source_height - crop_height) // 2

        # If faces detected, shift crop to center on face cluster
        if faces:
            avg_face_x = int(np.mean([f.x + f.width // 2 for f in faces]))
            avg_face_y = int(np.mean([f.y + f.height // 2 for f in faces]))

            # Center crop on face cluster (horizontal only for landscape->portrait)
            x = max(0, min(avg_face_x - crop_width // 2, source_width - crop_width))

            confidence = min(len(faces) / 10.0, 1.0)
        else:
            confidence = 0.5

        return CropRegion(
            x=x,
            y=y,
            width=crop_width,
            height=crop_height,
            confidence=confidence,
        )

    def compute_crop_for_segment(
        self,
        video_path: Path,
        start_time: float,
        end_time: float,
        source_width: int,
        source_height: int,
        target_width: int = 1080,
        target_height: int = 1920,
    ) -> CropRegion:
        """
        Compute crop region for a specific video segment.

        Analyzes faces in the segment and returns optimal crop.
        """
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)

        start_frame = int(start_time * fps)
        end_frame = int(end_time * fps)
        frame_interval = max(1, int(fps * self.sample_interval))

        faces: list[FaceRegion] = []
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        frame_idx = start_frame

        while frame_idx < end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            if (frame_idx - start_frame) % frame_interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                detected = self._face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(50, 50),
                )
                for (x, y, w, h) in detected:
                    faces.append(
                        FaceRegion(x=int(x), y=int(y), width=int(w), height=int(h), frame_idx=frame_idx)
                    )

            frame_idx += 1

        cap.release()

        return self.compute_crop_region(
            source_width=source_width,
            source_height=source_height,
            target_width=target_width,
            target_height=target_height,
            faces=faces if faces else None,
        )

    def get_ffmpeg_crop_filter(self, crop: CropRegion) -> str:
        """Generate FFmpeg crop filter string."""
        return f"crop={crop.width}:{crop.height}:{crop.x}:{crop.y}"
