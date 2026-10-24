"""
Abstract base class for camera sources.

This module defines the interface that all camera implementations
must follow for consistent frame capture behavior across different
hardware and simulation sources.
"""

from abc import ABC, abstractmethod
import numpy as np


class CameraSource(ABC):
    """
    Abstract base class for camera input sources.

    Provides a common interface for capturing frames from various
    camera sources including hardware cameras, network streams,
    and synthetic test generators.
    """

    @abstractmethod
    def open(self) -> bool:
        """
        Open the camera source and prepare for frame capture.

        Initializes the underlying capture mechanism. May involve
        hardware initialization, network connection, or resource
        allocation depending on implementation.

        Returns:
            True if the camera was opened successfully, False otherwise.
        """
        pass

    @abstractmethod
    def read_frame(self) -> np.ndarray | None:
        """
        Read a single frame from the camera source.

        Captures and returns the next available frame. Implementations
        should handle errors gracefully and return None on failure
        rather than raising exceptions.

        Returns:
            BGR image as numpy array with shape (height, width, 3),
            or None if frame capture failed.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close the camera source and release resources.

        Releases any hardware resources, closes network connections,
        and cleans up internal state. Safe to call multiple times.
        """
        pass

    @abstractmethod
    def is_open(self) -> bool:
        """
        Check if the camera source is currently open and ready.

        Returns:
            True if the camera is open and ready to capture frames,
            False otherwise.
        """
        pass
