"""
ESP-based drone driver implementation using Crazyflie.

This module provides a driver for communicating with Crazyflie drones
via the Crazyradio PA USB dongle. Uses the cflib library for
low-level communication.

Note: cflib must be installed separately: pip install cflib
The import is done inside method bodies to allow the rest of the
project to run in simulation mode without cflib installed.
"""

from drone.driver import DroneDriver
from drone.commands import DroneCommand
from config import ESP_DRONE_UDP


class ESPDriver(DroneDriver):
    """
    Driver for Crazyflie drone control.

    Communicates with a Crazyflie drone via Crazyradio USB dongle.
    Requires cflib to be installed (not included in base requirements
    to allow simulation-only usage).

    The driver maps normalized throttle values [-1, 1] to the
    Crazyflie thrust range [10001, 60000].
    """

    def __init__(self, uri: str = ESP_DRONE_UDP):
        """
        Initialize the ESP/Crazyflie drone driver.

        Args:
            uri: Crazyflie URI string for radio connection.
                 Default from config.ESP_DRONE_UDP.
                 Example: "radio://0/80/2M/E7E7E7E7E7"
        """
        self._uri = uri
        self._cf = None
        self._connected = False

    def connect(self) -> bool:
        """
        Establish connection to the Crazyflie drone.

        Initializes CRTP drivers and opens a link to the drone
        at the configured URI. Logs all connection events.

        Returns:
            True if connection successful, False on any error.

        Note:
            cflib must be installed: pip install cflib
        """
        try:
            # Import cflib inside method to allow sim-only usage
            import cflib.crtp
            from cflib.crazyflie import Crazyflie
            from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

            print(f"[ESPDriver] Initializing CRTP drivers...")
            cflib.crtp.init_drivers()

            print(f"[ESPDriver] Connecting to {self._uri}...")
            self._cf = Crazyflie(rw_cache='./cache')

            # Set up connection callbacks
            self._cf.connected.add_callback(self._on_connected)
            self._cf.disconnected.add_callback(self._on_disconnected)
            self._cf.connection_failed.add_callback(self._on_connection_failed)
            self._cf.connection_lost.add_callback(self._on_connection_lost)

            # Open the link
            self._cf.open_link(self._uri)

            # Wait briefly for connection
            import time
            timeout = 5.0
            start = time.time()
            while not self._connected and (time.time() - start) < timeout:
                time.sleep(0.1)

            if self._connected:
                print(f"[ESPDriver] Successfully connected to {self._uri}")
                return True
            else:
                print(f"[ESPDriver] Connection timeout after {timeout}s")
                return False

        except ImportError:
            print("[ESPDriver] ERROR: cflib not installed!")
            print("[ESPDriver] Install with: pip install cflib")
            return False
        except Exception as e:
            print(f"[ESPDriver] Connection error: {e}")
            self._connected = False
            return False

    def _on_connected(self, link_uri: str) -> None:
        """Callback when connection is established."""
        print(f"[ESPDriver] Connected to {link_uri}")
        self._connected = True

    def _on_disconnected(self, link_uri: str) -> None:
        """Callback when disconnected."""
        print(f"[ESPDriver] Disconnected from {link_uri}")
        self._connected = False

    def _on_connection_failed(self, link_uri: str, msg: str) -> None:
        """Callback when connection fails."""
        print(f"[ESPDriver] Connection to {link_uri} failed: {msg}")
        self._connected = False

    def _on_connection_lost(self, link_uri: str, msg: str) -> None:
        """Callback when connection is lost."""
        print(f"[ESPDriver] Connection to {link_uri} lost: {msg}")
        self._connected = False

    def send_command(self, cmd: DroneCommand) -> None:
        """
        Send control command to the Crazyflie.

        Maps throttle from [-1, 1] to thrust [10001, 60000] and
        sends the setpoint via the commander interface.

        Args:
            cmd: DroneCommand with roll, pitch, yaw, throttle values.
        """
        if not self._connected or self._cf is None:
            return

        try:
            # Map throttle from [-1, 1] to thrust [10001, 60000]
            # -1 -> 10001 (minimum thrust)
            #  0 -> 35000 (hover, approximately)
            # +1 -> 60000 (maximum thrust)
            normalized = (cmd.throttle + 1.0) / 2.0  # [0, 1]
            thrust = int(10001 + normalized * (60000 - 10001))
            thrust = max(10001, min(60000, thrust))  # Clamp for safety

            # Send setpoint: roll, pitch, yaw_rate, thrust
            self._cf.commander.send_setpoint(
                cmd.roll,    # Roll angle in degrees
                cmd.pitch,   # Pitch angle in degrees
                cmd.yaw,     # Yaw rate in degrees/second
                thrust       # Thrust as integer [10001, 60000]
            )

        except Exception as e:
            print(f"[ESPDriver] Error sending command: {e}")
            # Don't raise - just log and continue

    def disconnect(self) -> None:
        """
        Safely disconnect from the Crazyflie.

        Sends zero setpoint before closing the link to ensure
        the drone stops. Safe to call multiple times.
        """
        if self._cf is not None:
            try:
                if self._connected:
                    # Send zero setpoint to stop motors
                    print("[ESPDriver] Sending stop command...")
                    self._cf.commander.send_setpoint(0, 0, 0, 0)

                print("[ESPDriver] Closing link...")
                self._cf.close_link()

            except Exception as e:
                print(f"[ESPDriver] Error during disconnect: {e}")

            self._cf = None

        self._connected = False
        print("[ESPDriver] Disconnected")

    def is_connected(self) -> bool:
        """
        Check if connected to Crazyflie.

        Returns:
            True if link is open and connected, False otherwise.
        """
        if self._cf is None:
            return False

        return self._connected and self._cf.is_connected()


if __name__ == "__main__":
    print("=" * 60)
    print("ESP DRIVER TEST")
    print("=" * 60)
    print("\nNote: This test requires:")
    print("  1. cflib installed (pip install cflib)")
    print("  2. Crazyradio PA USB dongle connected")
    print("  3. Crazyflie drone powered on")
    print("\nAttempting connection (will likely fail without hardware)...\n")

    driver = ESPDriver()

    success = driver.connect()
    print(f"\nConnection result: {success}")
    print(f"is_connected: {driver.is_connected()}")

    if success:
        print("\nSending test hover command...")
        cmd = DroneCommand(roll=0, pitch=0, yaw=0, throttle=0, state="HOVER")
        driver.send_command(cmd)

    driver.disconnect()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
