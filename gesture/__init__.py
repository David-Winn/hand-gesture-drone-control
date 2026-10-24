"""
Gesture recognition package.

Contains modules for hand detection, gesture classification,
and translating gestures to drone control commands.
"""

from .detector import GestureDetector, HandResult
from .classifier import (
    fingers_extended_front,
    fingers_extended_topdown,
    classify_gesture
)
from .controller import (
    GestureController,
    hover_command,
    land_command,
    out_of_frame_command,
    scale_command,
)
