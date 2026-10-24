"""
Hand detection module using MediaPipe.

This module wraps MediaPipe HandLandmarker to detect and track
hand landmarks from camera frames. Uses the Tasks API (mediapipe >= 0.10).
"""

import os
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from config import MIN_DETECTION_CONFIDENCE, MIN_TRACKING_CONFIDENCE


# Model download URL and path
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
MODEL_PATH = Path(__file__).parent.parent / "models" / "hand_landmarker.task"


@dataclass
class HandResult:
    """
    Result of hand detection on a single frame.

    Attributes:
        landmarks: List of landmark objects with x, y, z attributes (21 per hand).
        handedness: String indicating "Left" or "Right" hand.
        found: Boolean indicating whether a hand was detected.
    """
    landmarks: list = field(default_factory=list)
    handedness: str = ""
    found: bool = False


def _ensure_model_exists() -> Path:
    """
    Ensure the hand landmarker model is downloaded.

    Downloads the model if it doesn't exist locally.

    Returns:
        Path to the model file.
    """
    if MODEL_PATH.exists():
        return MODEL_PATH

    # Create models directory
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"[GestureDetector] Downloading hand landmarker model...")
    print(f"[GestureDetector] URL: {MODEL_URL}")
    print(f"[GestureDetector] Destination: {MODEL_PATH}")

    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print(f"[GestureDetector] Model downloaded successfully")
    except Exception as e:
        print(f"[GestureDetector] Failed to download model: {e}")
        raise

    return MODEL_PATH


class GestureDetector:
    """
    Detects and tracks hand landmarks using MediaPipe HandLandmarker.

    Provides a simple interface for processing video frames and
    extracting hand landmark data for gesture classification.
    Uses the MediaPipe Tasks API.
    """

    def __init__(
        self,
        min_detection_confidence: float = MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence: float = MIN_TRACKING_CONFIDENCE
    ):
        """
        Initialize the gesture detector with MediaPipe HandLandmarker.

        Args:
            min_detection_confidence: Minimum confidence threshold for
                initial hand detection (0.0 to 1.0).
            min_tracking_confidence: Minimum confidence threshold for
                landmark tracking between frames (0.0 to 1.0).
        """
        # Ensure model is downloaded
        model_path = _ensure_model_exists()

        # Create HandLandmarker options
        base_options = python.BaseOptions(model_asset_path=str(model_path))

        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_tracking_confidence,
            min_tracking_confidence=min_tracking_confidence
        )

        self._landmarker = vision.HandLandmarker.create_from_options(options)

    def process_frame(self, frame: np.ndarray) -> HandResult:
        """
        Process a single video frame and detect hand landmarks.

        Converts the input BGR frame to RGB, runs MediaPipe hand detection,
        and returns the results packaged in a HandResult object.

        Args:
            frame: Input image as a numpy array in BGR format (OpenCV standard).

        Returns:
            HandResult containing landmarks, handedness, and detection status.
            If no hand is detected, returns HandResult with found=False.
        """
        # Convert BGR (OpenCV) to RGB (MediaPipe)
        rgb_frame = frame[:, :, ::-1].copy()

        # Create MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Process the frame
        result = self._landmarker.detect(mp_image)

        # Check if any hands were detected
        if result.hand_landmarks and result.handedness:
            # Get the first hand
            landmarks = result.hand_landmarks[0]
            handedness = result.handedness[0][0].category_name

            return HandResult(
                landmarks=list(landmarks),
                handedness=handedness,
                found=True
            )

        # No hand detected
        return HandResult(landmarks=[], handedness="", found=False)

    def close(self) -> None:
        """
        Release MediaPipe resources.

        Should be called when the detector is no longer needed to
        free up memory and processing resources.
        """
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None


if __name__ == "__main__":
    import cv2

    # Quick test with webcam
    print("Testing GestureDetector with webcam...")
    print("Press 'q' to quit\n")

    detector = GestureDetector()
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Could not open webcam, testing with synthetic frame")
        # Create a black frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.process_frame(frame)
        print(f"Result on black frame: found={result.found}")
    else:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            result = detector.process_frame(frame)

            if result.found:
                print(f"Hand detected: {result.handedness}, "
                      f"Landmarks: {len(result.landmarks)}")
            else:
                print("No hand detected")

            cv2.imshow("Test", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    detector.close()
    print("Test complete.")
