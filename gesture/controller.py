"""
Gesture to drone command translation module.

This module maps detected hand position and gestures to drone control commands.
Implements a state machine for safe control transitions and applies smoothing
filters for stable flight control.

States:
- OUT_OF_FRAME: No hand detected, waiting for user
- LANDING: Hand lost for too long, initiating landing
- HOVER: Hand detected but closed fist, holding position
- CONTROL: Open hand, actively controlling drone
"""

from drone.commands import DroneCommand
from gesture.detector import HandResult
from gesture.classifier import classify_gesture
from config import DEAD_FRAME_LIMIT
from ui.settings_panel import get_config_store


# --- Factory Functions ---

def hover_command() -> DroneCommand:
    """
    Create a hover command with all control values zeroed.

    Returns:
        DroneCommand with state="HOVER" and all axes at 0.0.
    """
    return DroneCommand(roll=0.0, pitch=0.0, yaw=0.0, throttle=0.0, state="HOVER")


def land_command() -> DroneCommand:
    """
    Create a landing command to safely descend the drone.

    Returns:
        DroneCommand with state="LANDING" and all axes at 0.0.
    """
    return DroneCommand(roll=0.0, pitch=0.0, yaw=0.0, throttle=0.0, state="LANDING")


def out_of_frame_command() -> DroneCommand:
    """
    Create an out-of-frame command indicating no valid hand input.

    Returns:
        DroneCommand with state="OUT_OF_FRAME" and all axes at 0.0.
    """
    return DroneCommand(roll=0.0, pitch=0.0, yaw=0.0, throttle=0.0, state="OUT_OF_FRAME")


# --- Helper Functions ---

def scale_command(value: float, scale: float, deadzone: float) -> float:
    """
    Apply deadzone, normalize, clamp, and scale a control value.

    The deadzone prevents small unintentional movements from affecting control.
    After deadzone, the value is normalized to use the full range, clamped to
    [-1.0, 1.0], then multiplied by the scale factor.

    Args:
        value: Raw input value (typically -1.0 to 1.0 range).
        scale: Multiplier for the final output.
        deadzone: Minimum movement threshold.

    Returns:
        Scaled command value with deadzone applied.
    """
    # Apply deadzone
    if abs(value) < deadzone:
        return 0.0

    # Normalize: remove deadzone and rescale to full range
    sign = 1.0 if value > 0 else -1.0
    normalized = sign * (abs(value) - deadzone) / (1.0 - deadzone)

    # Clamp to [-1.0, 1.0]
    clamped = max(-1.0, min(1.0, normalized))

    # Apply scale
    return clamped * scale


# --- Controller Class ---

class GestureController:
    """
    Translates hand gestures and position to drone control commands.

    Implements a state machine that manages safe transitions between
    control modes based on gesture recognition results.

    Attributes:
        perspective: Camera view type ("front" or "topdown").
        state: Current control state (OUT_OF_FRAME, LANDING, HOVER, CONTROL).
        neutral: Reference wrist position captured when entering CONTROL.
        dead_frames: Count of consecutive frames without hand detection.
        filtered_z: EMA-filtered z-axis value for topdown throttle control.
        last_command: Most recent valid control command for hold behavior.
    """

    def __init__(self, perspective: str):
        """
        Initialize the gesture controller.

        Args:
            perspective: Camera perspective, either "front" or "topdown".
                - "front": Standard webcam facing user, uses x/y for roll/throttle
                - "topdown": Camera above looking down, uses x/y/z for roll/pitch/throttle
        """
        if perspective not in ("front", "topdown"):
            raise ValueError(f"perspective must be 'front' or 'topdown', got '{perspective}'")

        self.perspective = perspective
        self.state = "OUT_OF_FRAME"
        self.neutral = None
        self.dead_frames = 0
        self.filtered_z = 0.0
        self.filtered_roll = 0.0
        self.filtered_throttle = 0.0
        self.filtered_pitch = 0.0
        self.last_command = out_of_frame_command()
        self._config = get_config_store()

    def update(self, hand_result: HandResult) -> DroneCommand:
        """
        Process a hand detection result and generate a drone command.

        This is the main method called every frame. It handles hand loss
        detection, gesture classification, and state machine transitions.

        Args:
            hand_result: HandResult from GestureDetector containing landmarks
                and detection status.

        Returns:
            DroneCommand appropriate for current state and gesture.
        """
        if not hand_result.found:
            # No hand detected
            self.dead_frames += 1

            if self.dead_frames >= DEAD_FRAME_LIMIT:
                # Too many frames without hand — initiate landing
                self.state = "LANDING"
                self.neutral = None
                return land_command()
            else:
                # Brief occlusion — hold position
                return hover_command()

        # Hand detected — reset dead frame counter
        self.dead_frames = 0

        # Classify the gesture
        gesture = classify_gesture(hand_result.landmarks, self.perspective)

        # Handle based on current state
        return self._handle_found(gesture, hand_result.landmarks)

    def _handle_found(self, gesture: str, landmarks) -> DroneCommand:
        """
        Handle state transitions when a hand is detected.

        Implements the state machine logic for transitioning between
        OUT_OF_FRAME, LANDING, HOVER, and CONTROL states based on gesture.

        Args:
            gesture: Classified gesture ("OPEN", "FIST", or "TRANSITION").
            landmarks: List of hand landmarks for position calculation.

        Returns:
            DroneCommand based on state transition logic.
        """
        if self.state in ("OUT_OF_FRAME", "LANDING"):
            # Waiting for user to establish control
            if gesture == "OPEN":
                self.state = "CONTROL"
                self._capture_neutral(landmarks)
                return hover_command()
            elif gesture == "FIST":
                self.state = "HOVER"
                return hover_command()
            else:  # TRANSITION
                return out_of_frame_command()

        elif self.state == "HOVER":
            # Holding position with fist, waiting for open hand
            if gesture == "OPEN":
                self.state = "CONTROL"
                self._capture_neutral(landmarks)
                return hover_command()
            else:  # FIST or TRANSITION
                return hover_command()

        elif self.state == "CONTROL":
            # Actively controlling with open hand
            if gesture == "FIST":
                self.state = "HOVER"
                self.neutral = None
                return hover_command()
            elif gesture == "TRANSITION":
                # Hold last valid command during transition
                return self.last_command
            else:  # OPEN
                command = self._compute_command(landmarks)
                self.last_command = command
                return command

        # Fallback (should never reach)
        return out_of_frame_command()

    def _capture_neutral(self, landmarks) -> None:
        """
        Capture the current wrist position as the neutral reference point.

        All subsequent control commands will be computed as offsets from
        this neutral position, allowing relative control.

        Args:
            landmarks: List of hand landmarks (uses index 0 for wrist).
        """
        wrist = landmarks[0]
        self.neutral = (wrist.x, wrist.y, wrist.z)
        # Reset all EMA filters
        self.filtered_z = 0.0
        self.filtered_roll = 0.0
        self.filtered_throttle = 0.0
        self.filtered_pitch = 0.0

    def _compute_command(self, landmarks) -> DroneCommand:
        """
        Compute drone control command from current hand position.

        Calculates the offset from neutral position and maps it to
        roll, pitch, and throttle based on camera perspective.

        Args:
            landmarks: List of hand landmarks (uses index 0 for wrist).

        Returns:
            DroneCommand with computed control values and state="CONTROL".
        """
        wrist = landmarks[0]

        # Compute deltas from neutral position
        dx = wrist.x - self.neutral[0]
        dy = wrist.y - self.neutral[1]
        dz = wrist.z - self.neutral[2]

        # Get live config values
        roll_scale = self._config.get("roll_scale")
        pitch_scale = self._config.get("pitch_scale")
        throttle_scale = self._config.get("throttle_scale")
        throttle_z_scale = self._config.get("throttle_z_scale")
        ema_alpha = self._config.get("ema_alpha")
        deadzone = self._config.get("deadzone")

        if self.perspective == "front":
            # Front-facing camera: x = roll, y = throttle (inverted)
            # Note: webcam mirrors the image, so invert dx for intuitive control
            raw_roll = scale_command(-dx, roll_scale, deadzone)  # Inverted for mirrored webcam
            raw_throttle = scale_command(-dy, throttle_scale, deadzone)  # y is inverted (up = negative y)
            pitch = 0.0

            # Apply EMA smoothing to reduce jitter from noisy webcam
            self.filtered_roll = ema_alpha * raw_roll + (1.0 - ema_alpha) * self.filtered_roll
            self.filtered_throttle = ema_alpha * raw_throttle + (1.0 - ema_alpha) * self.filtered_throttle

            roll = self.filtered_roll
            throttle = self.filtered_throttle

        else:  # topdown
            # Top-down camera: x = roll, y = pitch, z = throttle
            # Apply EMA filter for smooth control
            self.filtered_z = ema_alpha * dz + (1.0 - ema_alpha) * self.filtered_z

            raw_roll = scale_command(dx, roll_scale, deadzone)
            raw_pitch = scale_command(dy, pitch_scale, deadzone)

            self.filtered_roll = ema_alpha * raw_roll + (1.0 - ema_alpha) * self.filtered_roll
            self.filtered_pitch = ema_alpha * raw_pitch + (1.0 - ema_alpha) * self.filtered_pitch

            roll = self.filtered_roll
            pitch = self.filtered_pitch
            throttle = scale_command(-self.filtered_z, throttle_z_scale, deadzone)  # z inverted

        return DroneCommand(
            roll=roll,
            pitch=pitch,
            yaw=0.0,
            throttle=throttle,
            state="CONTROL"
        )

    def reset(self) -> None:
        """
        Reset controller to initial state.

        Clears all state including neutral position, dead frame counter,
        and EMA filters. Use when restarting control session.
        """
        self.state = "OUT_OF_FRAME"
        self.neutral = None
        self.dead_frames = 0
        self.filtered_z = 0.0
        self.filtered_roll = 0.0
        self.filtered_throttle = 0.0
        self.filtered_pitch = 0.0
        self.last_command = out_of_frame_command()


if __name__ == "__main__":
    # Mock landmark class for testing
    class MockLandmark:
        """Simple mock of MediaPipe NormalizedLandmark."""
        def __init__(self, x: float, y: float, z: float = 0.0):
            self.x = x
            self.y = y
            self.z = z

    def create_mock_landmarks(wrist_x: float, wrist_y: float, wrist_z: float = 0.0,
                               gesture: str = "OPEN") -> list:
        """
        Create 21 mock landmarks with specified wrist position and gesture.

        Args:
            wrist_x, wrist_y, wrist_z: Wrist position (landmark 0).
            gesture: "OPEN" or "FIST" to set fingertip positions accordingly.
        """
        landmarks = [MockLandmark(wrist_x, wrist_y, wrist_z)]  # Wrist (0)

        if gesture == "OPEN":
            # Thumb extended (tip.x < base.x for right hand)
            landmarks.extend([
                MockLandmark(wrist_x - 0.15, wrist_y - 0.1),  # 1
                MockLandmark(wrist_x - 0.20, wrist_y - 0.15),  # 2 - base
                MockLandmark(wrist_x - 0.28, wrist_y - 0.2),   # 3
                MockLandmark(wrist_x - 0.35, wrist_y - 0.25),  # 4 - tip
            ])
            # Other fingers extended (tip.y < base.y)
            for i in range(4):  # Index, Middle, Ring, Pinky
                offset = i * 0.08
                landmarks.extend([
                    MockLandmark(wrist_x - 0.08 + offset, wrist_y - 0.2),   # MCP
                    MockLandmark(wrist_x - 0.08 + offset, wrist_y - 0.35),  # PIP (base)
                    MockLandmark(wrist_x - 0.08 + offset, wrist_y - 0.5),   # DIP
                    MockLandmark(wrist_x - 0.08 + offset, wrist_y - 0.65),  # TIP
                ])
        else:  # FIST
            # Thumb curled (tip.x > base.x)
            landmarks.extend([
                MockLandmark(wrist_x - 0.05, wrist_y - 0.05),  # 1
                MockLandmark(wrist_x - 0.08, wrist_y - 0.08),  # 2 - base
                MockLandmark(wrist_x - 0.02, wrist_y - 0.06),  # 3
                MockLandmark(wrist_x + 0.02, wrist_y - 0.04),  # 4 - tip (x > base.x)
            ])
            # Other fingers curled (tip.y > base.y)
            for i in range(4):
                offset = i * 0.04
                landmarks.extend([
                    MockLandmark(wrist_x - 0.02 + offset, wrist_y - 0.08),  # MCP
                    MockLandmark(wrist_x - 0.02 + offset, wrist_y - 0.15),  # PIP (base)
                    MockLandmark(wrist_x - 0.02 + offset, wrist_y - 0.10),  # DIP
                    MockLandmark(wrist_x - 0.02 + offset, wrist_y - 0.05),  # TIP (y > base.y)
                ])

        return landmarks

    def run_test_sequence(perspective: str):
        """Run a test sequence for the given perspective."""
        print(f"\n{'=' * 70}")
        print(f"TESTING PERSPECTIVE: {perspective.upper()}")
        print('=' * 70)

        controller = GestureController(perspective)

        # Define test sequence
        test_steps = [
            # (description, hand_result)
            ("No hand frame 1", HandResult(landmarks=[], handedness="", found=False)),
            ("No hand frame 2", HandResult(landmarks=[], handedness="", found=False)),
            ("No hand frame 3", HandResult(landmarks=[], handedness="", found=False)),
            ("No hand frame 4", HandResult(landmarks=[], handedness="", found=False)),
            ("No hand frame 5", HandResult(landmarks=[], handedness="", found=False)),
            ("No hand frame 6", HandResult(landmarks=[], handedness="", found=False)),
            ("No hand frame 7", HandResult(landmarks=[], handedness="", found=False)),
            ("No hand frame 8", HandResult(landmarks=[], handedness="", found=False)),
            ("No hand frame 9", HandResult(landmarks=[], handedness="", found=False)),
            ("No hand frame 10 (LANDING)", HandResult(landmarks=[], handedness="", found=False)),
            ("Fist appears", HandResult(
                landmarks=create_mock_landmarks(0.5, 0.5, 0.0, "FIST"),
                handedness="Right", found=True)),
            ("Open hand (enter CONTROL)", HandResult(
                landmarks=create_mock_landmarks(0.5, 0.5, 0.0, "OPEN"),
                handedness="Right", found=True)),
            ("Move wrist RIGHT (+dx)", HandResult(
                landmarks=create_mock_landmarks(0.7, 0.5, 0.0, "OPEN"),
                handedness="Right", found=True)),
            ("Move wrist UP (-dy)", HandResult(
                landmarks=create_mock_landmarks(0.5, 0.3, 0.0, "OPEN"),
                handedness="Right", found=True)),
            ("Move wrist DOWN (+dy)", HandResult(
                landmarks=create_mock_landmarks(0.5, 0.7, 0.0, "OPEN"),
                handedness="Right", found=True)),
            ("Move wrist FORWARD (-dz, topdown)", HandResult(
                landmarks=create_mock_landmarks(0.5, 0.5, -0.2, "OPEN"),
                handedness="Right", found=True)),
            ("Fist (enter HOVER)", HandResult(
                landmarks=create_mock_landmarks(0.5, 0.5, 0.0, "FIST"),
                handedness="Right", found=True)),
        ]

        for description, hand_result in test_steps:
            command = controller.update(hand_result)
            print(f"\n{description}")
            print(f"  State: {controller.state}")
            print(f"  Command: roll={command.roll:+6.2f}, pitch={command.pitch:+6.2f}, "
                  f"throttle={command.throttle:+6.2f}, state={command.state}")

    # Run tests for both perspectives
    run_test_sequence("front")
    run_test_sequence("topdown")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
