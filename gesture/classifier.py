"""
Gesture classification module.

This module analyzes hand landmark positions to classify
discrete gestures like open hand, fist, and transition states.

Supports two camera perspectives:
- "front": Camera facing the user (standard webcam setup)
- "topdown": Camera looking down at the hand from above
"""

import math
from config import WRIST_SPREAD_OPEN_THRESHOLD, WRIST_SPREAD_FIST_THRESHOLD


def fingers_extended_front(landmarks) -> list[bool]:
    """
    Determine which fingers are extended from a front-facing camera view.

    Uses landmark y-coordinates to check finger extension. In MediaPipe's
    coordinate system, y=0 is the top of the frame, so extended fingers
    have lower y values than curled fingers.

    Landmark indices used:
    - Thumb: tip (4) vs IP joint (2) - checks x-coordinate
    - Index: tip (8) vs PIP joint (6)
    - Middle: tip (12) vs PIP joint (10)
    - Ring: tip (16) vs PIP joint (14)
    - Pinky: tip (20) vs PIP joint (18)

    Args:
        landmarks: List of MediaPipe NormalizedLandmark objects (21 landmarks).

    Returns:
        List of 5 booleans [thumb, index, middle, ring, pinky] indicating
        whether each finger is extended.
    """
    extended = []

    # Thumb: extended if tip x < base x (assumes right hand, thumb points left)
    # For right hand viewed from front, extended thumb tip is to the left (lower x)
    thumb_extended = landmarks[4].x < landmarks[2].x
    extended.append(thumb_extended)

    # Index, Middle, Ring, Pinky: extended if tip y < base y (higher in frame)
    finger_tips = [8, 12, 16, 20]
    finger_bases = [6, 10, 14, 18]

    for tip_idx, base_idx in zip(finger_tips, finger_bases):
        finger_extended = landmarks[tip_idx].y < landmarks[base_idx].y
        extended.append(finger_extended)

    return extended


def fingers_extended_topdown(landmarks) -> list[bool | None]:
    """
    Determine finger extension from a top-down camera view.

    Computes the mean distance from fingertips to the wrist landmark.
    When fingers are extended, tips are far from wrist; when curled (fist),
    tips are close to wrist.

    Args:
        landmarks: List of MediaPipe NormalizedLandmark objects (21 landmarks).

    Returns:
        List of 5 values for [thumb, index, middle, ring, pinky]:
        - [True, True, True, True, True] if mean distance > open threshold (open hand)
        - [False, False, False, False, False] if mean distance < fist threshold (fist)
        - [None, None, None, None, None] if in between (transition/ambiguous)
    """
    wrist = landmarks[0]
    fingertip_indices = [8, 12, 16, 20]  # Index, Middle, Ring, Pinky tips

    # Calculate distances from each fingertip to wrist
    distances = []
    for tip_idx in fingertip_indices:
        tip = landmarks[tip_idx]
        distance = math.sqrt(
            (tip.x - wrist.x) ** 2 + (tip.y - wrist.y) ** 2
        )
        distances.append(distance)

    mean_distance = sum(distances) / len(distances)

    # Classify based on thresholds
    if mean_distance > WRIST_SPREAD_OPEN_THRESHOLD:
        # All fingers extended (open hand)
        return [True, True, True, True, True]
    elif mean_distance < WRIST_SPREAD_FIST_THRESHOLD:
        # All fingers curled (fist)
        return [False, False, False, False, False]
    else:
        # Ambiguous state (transition)
        return [None, None, None, None, None]


def classify_gesture(landmarks, perspective: str) -> str:
    """
    Classify the hand gesture based on finger extension states.

    Args:
        landmarks: List of MediaPipe NormalizedLandmark objects (21 landmarks).
        perspective: Camera perspective, either "front" or "topdown".

    Returns:
        Gesture classification string:
        - "OPEN": All fingers extended
        - "FIST": No fingers extended
        - "TRANSITION": Ambiguous or partial extension state
    """
    # Get finger extension states based on perspective
    if perspective == "front":
        extended = fingers_extended_front(landmarks)
    elif perspective == "topdown":
        extended = fingers_extended_topdown(landmarks)
    else:
        raise ValueError(f"Unknown perspective: {perspective}. Use 'front' or 'topdown'.")

    # Check for ambiguous state (None values from topdown)
    if any(e is None for e in extended):
        return "TRANSITION"

    # Classify based on extension pattern
    if not any(extended):
        return "FIST"
    elif all(extended):
        return "OPEN"
    else:
        return "TRANSITION"


if __name__ == "__main__":
    # Mock landmark class to simulate MediaPipe landmarks
    class MockLandmark:
        """Simple mock of MediaPipe NormalizedLandmark."""
        def __init__(self, x: float, y: float, z: float = 0.0):
            self.x = x
            self.y = y
            self.z = z

    # Create mock landmarks for an OPEN hand (front view)
    # Simulating a right hand with all fingers extended upward
    # Wrist at center-bottom, fingertips spread upward
    open_hand_front = [
        # Wrist (0)
        MockLandmark(0.5, 0.9),
        # Thumb: CMC(1), MCP(2), IP(3), TIP(4)
        MockLandmark(0.35, 0.8),   # 1
        MockLandmark(0.25, 0.7),   # 2 - thumb base for comparison
        MockLandmark(0.18, 0.6),   # 3
        MockLandmark(0.12, 0.5),   # 4 - thumb tip (x < base x = extended)
        # Index: MCP(5), PIP(6), DIP(7), TIP(8)
        MockLandmark(0.38, 0.65),  # 5
        MockLandmark(0.38, 0.5),   # 6 - index base
        MockLandmark(0.38, 0.35),  # 7
        MockLandmark(0.38, 0.2),   # 8 - index tip (y < base y = extended)
        # Middle: MCP(9), PIP(10), DIP(11), TIP(12)
        MockLandmark(0.5, 0.62),   # 9
        MockLandmark(0.5, 0.47),   # 10 - middle base
        MockLandmark(0.5, 0.32),   # 11
        MockLandmark(0.5, 0.15),   # 12 - middle tip
        # Ring: MCP(13), PIP(14), DIP(15), TIP(16)
        MockLandmark(0.62, 0.65),  # 13
        MockLandmark(0.62, 0.5),   # 14 - ring base
        MockLandmark(0.62, 0.35),  # 15
        MockLandmark(0.62, 0.2),   # 16 - ring tip
        # Pinky: MCP(17), PIP(18), DIP(19), TIP(20)
        MockLandmark(0.74, 0.7),   # 17
        MockLandmark(0.74, 0.58),  # 18 - pinky base
        MockLandmark(0.74, 0.45),  # 19
        MockLandmark(0.74, 0.32),  # 20 - pinky tip
    ]

    # Create mock landmarks for a FIST (front view)
    # All fingertips curled down below their bases
    fist_front = [
        # Wrist (0)
        MockLandmark(0.5, 0.9),
        # Thumb: curled across palm (tip x > base x)
        MockLandmark(0.4, 0.75),   # 1
        MockLandmark(0.35, 0.7),   # 2 - thumb base
        MockLandmark(0.4, 0.68),   # 3
        MockLandmark(0.45, 0.65),  # 4 - thumb tip (x > base x = curled)
        # Index: curled (tip y > base y)
        MockLandmark(0.42, 0.7),   # 5
        MockLandmark(0.42, 0.6),   # 6 - index base
        MockLandmark(0.43, 0.65),  # 7
        MockLandmark(0.44, 0.72),  # 8 - index tip (y > base y = curled)
        # Middle: curled
        MockLandmark(0.5, 0.68),   # 9
        MockLandmark(0.5, 0.58),   # 10 - middle base
        MockLandmark(0.51, 0.63),  # 11
        MockLandmark(0.52, 0.7),   # 12 - middle tip
        # Ring: curled
        MockLandmark(0.58, 0.7),   # 13
        MockLandmark(0.58, 0.6),   # 14 - ring base
        MockLandmark(0.57, 0.65),  # 15
        MockLandmark(0.56, 0.72),  # 16 - ring tip
        # Pinky: curled
        MockLandmark(0.65, 0.73),  # 17
        MockLandmark(0.65, 0.65),  # 18 - pinky base
        MockLandmark(0.64, 0.7),   # 19
        MockLandmark(0.63, 0.75),  # 20 - pinky tip
    ]

    # Create mock landmarks for OPEN hand (topdown view)
    # Fingertips spread far from wrist (distance > 0.35)
    open_hand_topdown = [
        MockLandmark(0.5, 0.5),    # 0 - Wrist at center
        MockLandmark(0.3, 0.45),   # 1
        MockLandmark(0.15, 0.4),   # 2
        MockLandmark(0.08, 0.35),  # 3
        MockLandmark(0.02, 0.3),   # 4 - Thumb tip
        MockLandmark(0.35, 0.35),  # 5
        MockLandmark(0.28, 0.2),   # 6
        MockLandmark(0.25, 0.1),   # 7
        MockLandmark(0.22, 0.0),   # 8 - Index tip (far from wrist)
        MockLandmark(0.5, 0.32),   # 9
        MockLandmark(0.5, 0.18),   # 10
        MockLandmark(0.5, 0.08),   # 11
        MockLandmark(0.5, -0.05),  # 12 - Middle tip (far from wrist)
        MockLandmark(0.65, 0.35),  # 13
        MockLandmark(0.72, 0.2),   # 14
        MockLandmark(0.75, 0.1),   # 15
        MockLandmark(0.78, 0.0),   # 16 - Ring tip (far from wrist)
        MockLandmark(0.78, 0.42),  # 17
        MockLandmark(0.88, 0.35),  # 18
        MockLandmark(0.92, 0.28),  # 19
        MockLandmark(0.95, 0.2),   # 20 - Pinky tip (far from wrist)
    ]

    # Create mock landmarks for FIST (topdown view)
    # Fingertips close to wrist (distance < 0.20)
    fist_topdown = [
        MockLandmark(0.5, 0.5),    # 0 - Wrist
        MockLandmark(0.45, 0.48),  # 1
        MockLandmark(0.42, 0.47),  # 2
        MockLandmark(0.4, 0.46),   # 3
        MockLandmark(0.42, 0.5),   # 4 - Thumb tip (curled)
        MockLandmark(0.48, 0.45),  # 5
        MockLandmark(0.46, 0.42),  # 6
        MockLandmark(0.45, 0.44),  # 7
        MockLandmark(0.47, 0.48),  # 8 - Index tip (close to wrist)
        MockLandmark(0.5, 0.44),   # 9
        MockLandmark(0.5, 0.4),    # 10
        MockLandmark(0.5, 0.42),   # 11
        MockLandmark(0.5, 0.46),   # 12 - Middle tip (close to wrist)
        MockLandmark(0.52, 0.45),  # 13
        MockLandmark(0.54, 0.42),  # 14
        MockLandmark(0.55, 0.44),  # 15
        MockLandmark(0.53, 0.48),  # 16 - Ring tip (close to wrist)
        MockLandmark(0.55, 0.47),  # 17
        MockLandmark(0.58, 0.46),  # 18
        MockLandmark(0.57, 0.48),  # 19
        MockLandmark(0.55, 0.5),   # 20 - Pinky tip (close to wrist)
    ]

    # Test all combinations
    print("=" * 60)
    print("GESTURE CLASSIFIER TEST")
    print("=" * 60)

    print("\n--- FRONT PERSPECTIVE ---")

    print("\nOpen hand (front):")
    extended = fingers_extended_front(open_hand_front)
    print(f"  Fingers extended: {extended}")
    print(f"  [Thumb, Index, Middle, Ring, Pinky]")
    gesture = classify_gesture(open_hand_front, "front")
    print(f"  Gesture: {gesture}")

    print("\nFist (front):")
    extended = fingers_extended_front(fist_front)
    print(f"  Fingers extended: {extended}")
    print(f"  [Thumb, Index, Middle, Ring, Pinky]")
    gesture = classify_gesture(fist_front, "front")
    print(f"  Gesture: {gesture}")

    print("\n--- TOPDOWN PERSPECTIVE ---")

    print("\nOpen hand (topdown):")
    extended = fingers_extended_topdown(open_hand_topdown)
    print(f"  Fingers extended: {extended}")
    gesture = classify_gesture(open_hand_topdown, "topdown")
    print(f"  Gesture: {gesture}")

    print("\nFist (topdown):")
    extended = fingers_extended_topdown(fist_topdown)
    print(f"  Fingers extended: {extended}")
    gesture = classify_gesture(fist_topdown, "topdown")
    print(f"  Gesture: {gesture}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
