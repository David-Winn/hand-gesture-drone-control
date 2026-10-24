"""
Main entry point for the gesture-controlled drone application.

This module initializes and runs the main control loop, coordinating
between camera input, gesture detection, and drone command output.

Usage:
    python main.py --camera webcam --perspective front
    python main.py --camera esp --drone-ip udp://192.168.43.42
"""

import argparse
import queue
import threading
import time
import sys

import cv2

import config
from gesture.detector import GestureDetector, HandResult
from gesture.controller import GestureController, land_command
from drone.commands import DroneCommand
from drone.udp_driver import UDPDriver, parse_udp_uri
from stream.webcam import WebcamCamera
from stream.esp_cam import ESPCamera
from ui.settings_panel import SettingsPanel, get_config_store
from utils.logger import setup_logger, StateTransitionLogger


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Namespace with parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Gesture-controlled drone system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Local webcam control:
    python main.py --camera webcam

  ESP-Drone with ESP-CAM:
    python main.py --camera esp --drone-ip udp://192.168.43.42
        """
    )

    parser.add_argument(
        "--camera",
        choices=["webcam", "esp"],
        default="webcam",
        help="Camera source (default: webcam)"
    )

    parser.add_argument(
        "--perspective",
        choices=["front", "topdown"],
        default="front",
        help="Camera perspective for gesture mapping (default: front)"
    )

    parser.add_argument(
        "--drone-ip",
        type=str,
        default=None,
        help="Drone UDP address (e.g., udp://192.168.43.42)"
    )

    parser.add_argument(
        "--cam-url",
        type=str,
        default=None,
        help="ESP-CAM URL (e.g., http://192.168.4.1:81/stream)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Disable settings UI panel"
    )

    return parser.parse_args()


def create_camera(args, logger):
    """
    Create camera instance based on arguments.

    Args:
        args: Parsed command-line arguments.
        logger: Logger instance.

    Returns:
        CameraSource instance.
    """
    if args.camera == "esp":
        url = args.cam_url if args.cam_url else config.ESP_CAM_URL
        logger.info(f"Creating ESP camera: {url}")
        return ESPCamera(url=url)
    else:
        logger.info("Creating webcam camera")
        return WebcamCamera()


def create_drone_driver(args, logger):
    """
    Create drone driver instance based on arguments.

    Args:
        args: Parsed command-line arguments.
        logger: Logger instance.

    Returns:
        DroneDriver instance.
    """
    uri = args.drone_ip if args.drone_ip else config.ESP_DRONE_UDP
    host, port = parse_udp_uri(uri)
    logger.info(f"Creating UDP drone driver: {host}:{port}")
    return UDPDriver(host=host, port=port)


def annotate_frame(frame, state: str, cmd: DroneCommand, hand_result: HandResult):
    """
    Annotate frame with state info and landmarks.

    Args:
        frame: BGR image to annotate.
        state: Current control state string.
        cmd: Current DroneCommand.
        hand_result: HandResult from detector.

    Returns:
        Annotated frame.
    """
    # Make a copy to avoid modifying original
    annotated = frame.copy()

    # Colors for different states
    state_colors = {
        "CONTROL": (0, 255, 0),    # Green
        "HOVER": (255, 255, 0),    # Cyan
        "LANDING": (0, 165, 255),  # Orange
        "OUT_OF_FRAME": (0, 0, 255),  # Red
    }
    color = state_colors.get(state, (255, 255, 255))

    # Font settings
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thickness = 2

    # Draw state
    cv2.putText(annotated, f"State: {state}", (10, 30),
                font, font_scale, color, thickness)

    # Draw command values
    cmd_text = f"Roll: {cmd.roll:+6.2f}  Pitch: {cmd.pitch:+6.2f}  Throttle: {cmd.throttle:+5.2f}"
    cv2.putText(annotated, cmd_text, (10, 60),
                font, 0.5, (255, 255, 255), 1)

    # Draw MediaPipe landmarks if hand found
    if hand_result.found and hand_result.landmarks:
        h, w = annotated.shape[:2]
        landmarks = hand_result.landmarks

        # Hand connections (landmark index pairs)
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),       # Thumb
            (0, 5), (5, 6), (6, 7), (7, 8),       # Index
            (0, 9), (9, 10), (10, 11), (11, 12),  # Middle
            (0, 13), (13, 14), (14, 15), (15, 16),  # Ring
            (0, 17), (17, 18), (18, 19), (19, 20),  # Pinky
            (5, 9), (9, 13), (13, 17)             # Palm
        ]

        # Draw connections
        for start_idx, end_idx in connections:
            if start_idx < len(landmarks) and end_idx < len(landmarks):
                start = landmarks[start_idx]
                end = landmarks[end_idx]
                pt1 = (int(start.x * w), int(start.y * h))
                pt2 = (int(end.x * w), int(end.y * h))
                cv2.line(annotated, pt1, pt2, (0, 255, 0), 2)

        # Draw landmark points
        for lm in landmarks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(annotated, (cx, cy), 4, (255, 0, 0), -1)

        # Show handedness
        cv2.putText(annotated, f"Hand: {hand_result.handedness}", (10, 90),
                    font, 0.5, (255, 255, 255), 1)

    return annotated


class ControlLoop:
    """
    Encapsulates the main control loop logic.

    Runs in a background thread and passes frames via queue.
    """

    def __init__(self, args, logger, transition_logger, camera, drone_driver,
                 detector, controller, frame_queue):
        self.args = args
        self.logger = logger
        self.transition_logger = transition_logger
        self.camera = camera
        self.drone_driver = drone_driver
        self.detector = detector
        self.controller = controller
        self.frame_queue = frame_queue

        self._running = True
        self._last_state = "OUT_OF_FRAME"
        self._debug_count = 0

    def stop(self):
        """Signal the control loop to stop."""
        self._running = False

    def is_running(self) -> bool:
        """Check if control loop is running."""
        return self._running

    def run(self):
        """
        Run the main control loop.

        Processes frames at COMMAND_RATE_HZ, detecting gestures
        and sending commands to the drone.
        """
        frame_interval = 1.0 / config.COMMAND_RATE_HZ
        last_frame_time = time.time()

        try:
            while self._running:
                # Time-based pacing
                current_time = time.time()
                elapsed = current_time - last_frame_time

                if elapsed < frame_interval:
                    time.sleep(0.001)
                    continue

                last_frame_time = current_time

                # Read frame
                frame = self.camera.read_frame()
                if frame is None:
                    continue

                # Process gesture
                hand_result = self.detector.process_frame(frame)

                # Generate command
                cmd = self.controller.update(hand_result)

                # Log state transition
                self.transition_logger.log_transition(self._last_state, cmd.state)
                self.transition_logger.log_command(cmd)
                self._last_state = cmd.state

                # Send command to drone
                self.drone_driver.send_command(cmd)

                # Debug output every 20 frames
                self._debug_count += 1
                if self._debug_count % 20 == 0 and cmd.state == "CONTROL":
                    print(f"[DEBUG] throttle={cmd.throttle:+.2f} roll={cmd.roll:+.1f} state={cmd.state}")

                # Annotate and put frame in queue for main thread
                annotated = annotate_frame(frame, cmd.state, cmd, hand_result)
                try:
                    self.frame_queue.put_nowait(annotated)
                except queue.Full:
                    pass  # Drop frame if queue full

        except Exception as e:
            self.logger.error(f"Error in control loop: {e}")
            self._running = False
            raise


def main():
    """
    Main entry point: initialize components and run control loop.
    """
    # Parse arguments
    args = parse_args()

    # Setup logger
    logger = setup_logger("gesture_drone", debug=args.debug)
    transition_logger = StateTransitionLogger(logger)

    # Override config values if provided
    if args.drone_ip:
        config.ESP_DRONE_UDP = args.drone_ip
    if args.cam_url:
        config.ESP_CAM_URL = args.cam_url

    # Components to clean up
    camera = None
    drone_driver = None
    detector = None
    control_loop = None
    control_thread = None
    settings_panel = None

    try:
        # Initialize camera
        camera = create_camera(args, logger)
        if not camera.open():
            logger.error("Failed to open camera")
            sys.exit(1)

        # Initialize drone driver
        drone_driver = create_drone_driver(args, logger)
        if not drone_driver.connect():
            logger.error("Failed to connect to drone")
            sys.exit(1)

        # Initialize gesture detection
        detector = GestureDetector()
        controller = GestureController(perspective=args.perspective)

        # Log startup summary
        logger.info("=" * 50)
        logger.info("Gesture Drone Started")
        logger.info(f"  Camera: {args.camera}")
        logger.info(f"  Perspective: {args.perspective}")
        logger.info(f"  Drone: {args.drone_ip or config.ESP_DRONE_UDP}")
        if args.camera == "esp":
            logger.info(f"  Camera URL: {args.cam_url or config.ESP_CAM_URL}")
        logger.info("=" * 50)
        logger.info("Press 'q' to quit")

        # Frame queue for passing frames from control thread to main thread
        frame_queue = queue.Queue(maxsize=2)

        # Create control loop
        control_loop = ControlLoop(
            args=args,
            logger=logger,
            transition_logger=transition_logger,
            camera=camera,
            drone_driver=drone_driver,
            detector=detector,
            controller=controller,
            frame_queue=frame_queue,
        )

        # Run control loop in background thread
        control_thread = threading.Thread(target=control_loop.run, daemon=True)
        control_thread.start()

        # Initialize settings UI on main thread (if not disabled)
        if not args.no_ui:
            config_store = get_config_store()
            settings_panel = SettingsPanel(config_store, on_close_callback=control_loop.stop)
            settings_panel.setup()
            logger.info("Settings UI panel started")

        # Main thread loop: handle OpenCV display and tkinter
        while control_loop.is_running():
            # Display frames from queue
            try:
                frame = frame_queue.get_nowait()
                cv2.imshow("gesture_drone", frame)
            except queue.Empty:
                pass

            # Check for quit key
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                logger.info("Quit requested")
                control_loop.stop()
                break

            # Update settings panel (non-blocking)
            if settings_panel is not None:
                if not settings_panel.update_once():
                    # Panel was closed
                    control_loop.stop()
                    break

        # Wait for control thread
        control_thread.join(timeout=2.0)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    except Exception as e:
        logger.error(f"Error: {e}")
        raise

    finally:
        # Shutdown sequence
        logger.info("Shutting down...")

        # Stop control loop if running
        if control_loop is not None:
            control_loop.stop()

        # Wait for control thread
        if control_thread is not None and control_thread.is_alive():
            control_thread.join(timeout=2.0)

        # Stop settings panel
        if settings_panel is not None:
            settings_panel.stop()

        # Send land command
        if drone_driver is not None and drone_driver.is_connected():
            logger.info("Sending land command")
            drone_driver.send_command(land_command())
            time.sleep(0.1)

        # Disconnect drone
        if drone_driver is not None:
            drone_driver.disconnect()

        # Close camera
        if camera is not None:
            camera.close()

        # Close detector
        if detector is not None:
            detector.close()

        # Close OpenCV windows
        cv2.destroyAllWindows()

        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
