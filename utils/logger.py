"""
Logging utility module.

This module provides logging setup and helper classes for the
gesture drone application.
"""

import logging
from drone.commands import DroneCommand


def setup_logger(name: str, debug: bool = False) -> logging.Logger:
    """
    Set up and return a configured logger.

    Creates a logger with console output using a standard format
    including timestamp, level, logger name, and message.

    Args:
        name: Logger name (typically module or component name).
        debug: If True, set level to DEBUG; otherwise INFO.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    # Set level
    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)

    # Create console handler
    handler = logging.StreamHandler()
    handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(handler)

    return logger


class StateTransitionLogger:
    """
    Helper class for logging state transitions and commands.

    Tracks the previous state and only logs transitions when
    the state actually changes, reducing log noise.
    """

    def __init__(self, logger: logging.Logger):
        """
        Initialize the state transition logger.

        Args:
            logger: The logging.Logger instance to use for output.
        """
        self._logger = logger
        self._last_state: str | None = None

    def log_transition(self, old_state: str, new_state: str) -> None:
        """
        Log a state transition if the state has changed.

        Only logs at INFO level when old_state != new_state.

        Args:
            old_state: The previous state.
            new_state: The new state.
        """
        if old_state != new_state:
            self._logger.info(f"State: {old_state} → {new_state}")

    def log_command(self, cmd: DroneCommand) -> None:
        """
        Log command details at DEBUG level.

        Logs roll, pitch, throttle, and state values.

        Args:
            cmd: The DroneCommand to log.
        """
        self._logger.debug(
            f"Command: roll={cmd.roll:+6.2f}, pitch={cmd.pitch:+6.2f}, "
            f"throttle={cmd.throttle:+5.2f}, state={cmd.state}"
        )


if __name__ == "__main__":
    from drone.commands import DroneCommand

    print("=" * 60)
    print("LOGGER TEST")
    print("=" * 60)

    # Test setup_logger
    print("\n--- Testing setup_logger (INFO level) ---")
    logger = setup_logger("test", debug=False)
    logger.info("This INFO message should appear")
    logger.debug("This DEBUG message should NOT appear")

    print("\n--- Testing setup_logger (DEBUG level) ---")
    debug_logger = setup_logger("test_debug", debug=True)
    debug_logger.info("This INFO message should appear")
    debug_logger.debug("This DEBUG message should appear")

    # Test StateTransitionLogger
    print("\n--- Testing StateTransitionLogger ---")
    transition_logger = StateTransitionLogger(logger)

    print("\nSame state (should not log):")
    transition_logger.log_transition("HOVER", "HOVER")

    print("\nDifferent state (should log):")
    transition_logger.log_transition("HOVER", "CONTROL")
    transition_logger.log_transition("CONTROL", "LANDING")

    print("\n--- Testing log_command (DEBUG level) ---")
    cmd = DroneCommand(roll=5.5, pitch=-3.2, throttle=0.75, state="CONTROL")

    # This won't show with INFO logger
    transition_logger.log_command(cmd)
    print("(No output above is expected - INFO level logger)")

    # Use debug logger
    debug_transition = StateTransitionLogger(debug_logger)
    debug_transition.log_command(cmd)

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
