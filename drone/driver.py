"""
Abstract base class for drone drivers.

This module defines the interface that all drone driver implementations
must follow, enabling seamless switching between simulation and hardware.
"""

from abc import ABC, abstractmethod
from drone.commands import DroneCommand


class DroneDriver(ABC):
    """
    Abstract base class for drone communication drivers.

    Provides a common interface for sending commands to either
    a simulated drone or real hardware (e.g., Crazyflie via ESP).
    All implementations must be thread-safe for concurrent access.
    """

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the drone.

        Initializes communication with the drone hardware or simulation.
        Should handle all necessary setup including driver initialization,
        link establishment, and initial handshake.

        Returns:
            True if connection was established successfully,
            False if connection failed.
        """
        pass

    @abstractmethod
    def send_command(self, cmd: DroneCommand) -> None:
        """
        Send a control command to the drone.

        Transmits roll, pitch, yaw, and throttle values to the drone.
        Implementations should handle command translation to the
        appropriate protocol format.

        Args:
            cmd: DroneCommand containing control values and state.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Close connection to the drone and clean up resources.

        Should safely shut down the drone (e.g., zero throttle)
        before closing the communication link. Safe to call
        multiple times.
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if the driver is currently connected to a drone.

        Returns:
            True if connected and ready to send commands,
            False otherwise.
        """
        pass
