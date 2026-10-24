"""
Data structures for drone commands.

This module defines the core data types used for communicating
control inputs to the drone.
"""

from dataclasses import dataclass


@dataclass
class DroneCommand:
    """
    Represents a single drone control command.

    Attributes:
        roll: Roll angle command in degrees (positive = right).
        pitch: Pitch angle command in degrees (positive = forward).
        yaw: Yaw rate command in degrees/second (positive = clockwise).
        throttle: Throttle command as normalized value (0.0 to 1.0).
        state: Current control state (e.g., "OUT_OF_FRAME", "TRACKING", "LANDED").
    """
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    throttle: float = 0.0
    state: str = "OUT_OF_FRAME"
