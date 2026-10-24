"""
Camera streaming package.

Contains modules for camera abstraction and specific
implementations for ESP-CAM and webcam.
"""

from .camera import CameraSource
from .esp_cam import ESPCamera
from .webcam import WebcamCamera
