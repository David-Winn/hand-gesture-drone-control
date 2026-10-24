"""
ESP-CAM stream implementation.

This module provides camera capture from an ESP32-CAM
streaming over HTTP MJPEG protocol.
"""

import time
import cv2
import numpy as np

from stream.camera import CameraSource
from config import ESP_CAM_URL


class ESPCamera(CameraSource):
    """
    Camera stream from ESP32-CAM over HTTP.

    Connects to ESP-CAM's MJPEG stream endpoint and decodes
    frames for processing. Includes retry logic for unreliable
    network connections.
    """

    def __init__(self, url: str = ESP_CAM_URL):
        """
        Initialize ESP camera stream.

        Args:
            url: URL to ESP-CAM MJPEG stream endpoint.
                 Defaults to ESP_CAM_URL from config.
        """
        self._url = url
        self._capture: cv2.VideoCapture | None = None

    def open(self) -> bool:
        """
        Open HTTP connection to ESP-CAM stream with retry logic.

        Attempts to connect up to 3 times with a 2-second delay
        between attempts. Logs each attempt for debugging.

        Returns:
            True if connection successful, False if all attempts fail.
        """
        max_attempts = 3
        retry_delay = 2.0

        for attempt in range(1, max_attempts + 1):
            print(f"[ESPCamera] Connection attempt {attempt}/{max_attempts} to {self._url}")

            try:
                self._capture = cv2.VideoCapture(self._url)

                if self._capture is not None and self._capture.isOpened():
                    # Try to read a test frame to verify connection
                    ret, _ = self._capture.read()
                    if ret:
                        print(f"[ESPCamera] Successfully connected on attempt {attempt}")
                        return True
                    else:
                        print(f"[ESPCamera] Connected but failed to read frame")
                        self._capture.release()
                        self._capture = None
                else:
                    print(f"[ESPCamera] Failed to open capture")

            except Exception as e:
                print(f"[ESPCamera] Exception on attempt {attempt}: {e}")
                if self._capture is not None:
                    self._capture.release()
                    self._capture = None

            # Wait before retry (unless this was the last attempt)
            if attempt < max_attempts:
                print(f"[ESPCamera] Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)

        print(f"[ESPCamera] All {max_attempts} connection attempts failed")
        return False

    def read_frame(self) -> np.ndarray | None:
        """
        Read next frame from ESP-CAM stream.

        Decodes the next MJPEG frame from the HTTP stream.
        Does not raise exceptions on failure.

        Returns:
            BGR numpy array if successful, None on failure.
        """
        if self._capture is None or not self._capture.isOpened():
            return None

        try:
            ret, frame = self._capture.read()
            if ret and frame is not None:
                return frame
            return None
        except Exception:
            return None

    def close(self) -> None:
        """
        Close HTTP connection and release resources.

        Safe to call multiple times.
        """
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None
        print("[ESPCamera] Connection closed")

    def is_open(self) -> bool:
        """
        Check if HTTP stream is connected and ready.

        Returns:
            True if connected and capture is open, False otherwise.
        """
        return self._capture is not None and self._capture.isOpened()


if __name__ == "__main__":
    print("=" * 60)
    print("ESP CAMERA TEST")
    print("=" * 60)
    print(f"\nAttempting to connect to: {ESP_CAM_URL}")
    print("(This will likely fail without actual ESP-CAM hardware)\n")

    camera = ESPCamera()
    success = camera.open()

    if success:
        print("\nReading frames...")
        for i in range(3):
            frame = camera.read_frame()
            if frame is not None:
                print(f"  Frame {i + 1}: shape={frame.shape}")
            else:
                print(f"  Frame {i + 1}: None")

    camera.close()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
