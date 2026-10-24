"""
Webcam camera implementation.

Simple wrapper around OpenCV VideoCapture for local webcam input.
"""

import cv2
import numpy as np

from stream.camera import CameraSource


class WebcamCamera(CameraSource):
    """
    Local webcam camera using OpenCV.
    """

    def __init__(self, device_id: int = 0):
        """
        Initialize webcam camera.

        Args:
            device_id: OpenCV camera device index (default 0).
        """
        self._device_id = device_id
        self._capture: cv2.VideoCapture | None = None

    def open(self) -> bool:
        """
        Open the webcam.

        Returns:
            True if successful, False otherwise.
        """
        try:
            self._capture = cv2.VideoCapture(self._device_id)
            if self._capture is not None and self._capture.isOpened():
                print(f"[WebcamCamera] Opened device {self._device_id}")
                return True
            else:
                print(f"[WebcamCamera] Failed to open device {self._device_id}")
                return False
        except Exception as e:
            print(f"[WebcamCamera] Exception: {e}")
            return False

    def read_frame(self) -> np.ndarray | None:
        """
        Read a frame from the webcam.

        Returns:
            BGR numpy array if successful, None on failure.
        """
        if self._capture is None:
            return None
        try:
            ret, frame = self._capture.read()
            if ret and frame is not None:
                return frame
            return None
        except Exception:
            return None

    def close(self) -> None:
        """Close the webcam and release resources."""
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None
        print("[WebcamCamera] Closed")

    def is_open(self) -> bool:
        """Check if webcam is open."""
        return self._capture is not None and self._capture.isOpened()
