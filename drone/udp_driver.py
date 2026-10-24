"""
Simple UDP driver for ESP-Drone communication.

Sends CRTP-format packets directly over UDP without the full cflib handshake.
This works with ESP-Drone firmware that doesn't support the cflib protocol
version negotiation.
"""

import socket
import struct
import threading
import time

from drone.driver import DroneDriver
from drone.commands import DroneCommand


class UDPDriver(DroneDriver):
    """
    Simple UDP driver for ESP-Drone.

    Sends CRTP setpoint packets directly without cflib handshake.
    """

    # CRTP port for commander (setpoint commands)
    CRTP_PORT_COMMANDER = 3
    CRTP_CHANNEL = 0

    def __init__(self, host: str = "192.168.43.42", port: int = 2390):
        """
        Initialize UDP driver.

        Args:
            host: ESP-Drone IP address.
            port: ESP-Drone UDP port.
        """
        self._host = host
        self._port = port
        self._socket = None
        self._connected = False
        self._receiver_thread = None
        self._running = False

    def connect(self) -> bool:
        """
        Open UDP socket to ESP-Drone.

        Returns:
            True if socket opened successfully.
        """
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.settimeout(0.1)
            self._socket.connect((self._host, self._port))

            # Start receiver thread to handle any responses
            self._running = True
            self._receiver_thread = threading.Thread(target=self._receiver_loop, daemon=True)
            self._receiver_thread.start()

            # Send a ping/null packet to test connection
            self._send_null_packet()
            time.sleep(0.1)

            self._connected = True
            print(f"[UDPDriver] Connected to {self._host}:{self._port}")
            print(f"[UDPDriver] NOTE: Drone must be armed via phone app for motors to spin")
            return True

        except Exception as e:
            print(f"[UDPDriver] Connection failed: {e}")
            self._connected = False
            return False

    def _receiver_loop(self):
        """Background thread to receive and discard responses."""
        while self._running:
            try:
                data = self._socket.recv(1024)
                # Just discard - we don't need responses for setpoint control
            except socket.timeout:
                pass
            except Exception:
                if self._running:
                    pass  # Ignore errors while running

    def _send_null_packet(self):
        """Send a null/ping packet."""
        # CRTP header: (port << 4) | channel
        header = (0xF << 4) | 0x0  # Null port
        packet_data = bytes([header])
        checksum = self._calc_checksum(packet_data)
        packet = packet_data + bytes([checksum])
        try:
            self._socket.send(packet)
        except Exception:
            pass

    def _make_crtp_header(self, port: int, channel: int = 0) -> int:
        """Create CRTP header byte."""
        return ((port & 0x0F) << 4) | (channel & 0x03)

    def _calc_checksum(self, data: bytes) -> int:
        """Calculate ESP-Drone packet checksum (SUM of all bytes mod 256)."""
        return sum(data) & 0xFF

    def send_command(self, cmd: DroneCommand, debug: bool = False) -> None:
        """
        Send setpoint command to ESP-Drone.

        Uses CRTP commander format:
        - Header: port 3, channel 0
        - Payload: roll (float), pitch (float), yaw (float), thrust (uint16)

        Args:
            cmd: DroneCommand with roll, pitch, yaw, throttle.
            debug: If True, print packet details.
        """
        if not self._connected or self._socket is None:
            return

        try:
            # Map throttle from [-1, 1] to thrust
            # ESP-Drone thrust range (max power for takeoff)
            # -1.0 -> 30000 (min, motors spinning)
            #  0.0 -> 50000 (hover)
            # +1.0 -> 65535 (max thrust - uint16 limit)
            #
            # Note: thrust=0 disables motors (safety)
            if cmd.state == "LANDING" or cmd.state == "OUT_OF_FRAME":
                thrust = 0  # Motors off for landing/no hand
            else:
                normalized = (cmd.throttle + 1.0) / 2.0  # [0, 1]
                thrust = int(30000 + normalized * (65535 - 30000))
                thrust = max(30000, min(65535, thrust))

            # CRTP header for commander port
            header = self._make_crtp_header(self.CRTP_PORT_COMMANDER, self.CRTP_CHANNEL)

            # Pack setpoint: roll, pitch, yaw (floats), thrust (uint16)
            # Format: <header><roll:f><pitch:f><yaw:f><thrust:H><checksum>
            payload = struct.pack('<fffH', cmd.roll, cmd.pitch, cmd.yaw, thrust)
            packet_data = bytes([header]) + payload
            checksum = self._calc_checksum(packet_data)
            packet = packet_data + bytes([checksum])

            if debug:
                print(f"[UDPDriver] Sending: roll={cmd.roll:.1f} pitch={cmd.pitch:.1f} "
                      f"yaw={cmd.yaw:.1f} thrust={thrust} state={cmd.state} cksum={checksum:02x}")

            self._socket.send(packet)

        except Exception as e:
            print(f"[UDPDriver] Send error: {e}")

    def disconnect(self) -> None:
        """Close UDP socket."""
        self._running = False
        self._connected = False

        if self._receiver_thread is not None:
            self._receiver_thread.join(timeout=1.0)
            self._receiver_thread = None

        if self._socket is not None:
            try:
                # Send stop command before closing
                self._send_stop()
                self._socket.close()
            except Exception:
                pass
            self._socket = None

        print("[UDPDriver] Disconnected")

    def _send_stop(self):
        """Send zero thrust command to stop motors."""
        header = self._make_crtp_header(self.CRTP_PORT_COMMANDER, self.CRTP_CHANNEL)
        payload = struct.pack('<fffH', 0.0, 0.0, 0.0, 0)
        packet_data = bytes([header]) + payload
        checksum = self._calc_checksum(packet_data)
        packet = packet_data + bytes([checksum])
        try:
            self._socket.send(packet)
        except Exception:
            pass

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected


def parse_udp_uri(uri: str) -> tuple[str, int]:
    """
    Parse UDP URI into host and port.

    Args:
        uri: URI like "udp://192.168.43.42:2390"

    Returns:
        Tuple of (host, port)
    """
    # Remove scheme
    if uri.startswith("udp://"):
        uri = uri[6:]

    # Split host:port
    if ":" in uri:
        host, port_str = uri.rsplit(":", 1)
        port = int(port_str)
    else:
        host = uri
        port = 2390  # Default

    return host, port


def calc_cksum_xor(data: bytes) -> int:
    """XOR checksum."""
    cksum = 0
    for b in data:
        cksum ^= b
    return cksum


def calc_cksum_sum(data: bytes) -> int:
    """Sum checksum (mod 256)."""
    return sum(data) & 0xFF


def calc_cksum_sum_complement(data: bytes) -> int:
    """Two's complement of sum."""
    return (-sum(data)) & 0xFF


def test_arming_sequences(host: str = "192.168.43.42", port: int = 2390):
    """Try different arming/initialization sequences."""
    import socket

    print("=" * 60)
    print("ESP-DRONE ARMING SEQUENCE TEST")
    print("=" * 60)
    print("\n*** WARNING: Motors may spin! Keep drone secured! ***\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)
    sock.connect((host, port))

    def send_with_cksum(data: bytes):
        """Send packet with SUM checksum."""
        cksum = sum(data) & 0xFF
        sock.send(data + bytes([cksum]))

    def send_repeated(name: str, data: bytes, count: int = 50, delay: float = 0.02):
        """Send packet repeatedly."""
        print(f"\n{name}")
        hex_str = ' '.join(f'{b:02x}' for b in data)
        print(f"  Data: {hex_str}")
        for i in range(count):
            send_with_cksum(data)
            time.sleep(delay)
        print(f"  Sent {count} packets - check motors")
        time.sleep(1)

    # Thrust value for testing
    thrust = 40000

    # CRTP Ports
    PORT_CONSOLE = 0
    PORT_PARAM = 2
    PORT_COMMANDER = 3
    PORT_MEM = 4
    PORT_LOG = 5
    PORT_LOCALIZATION = 6
    PORT_GENERIC_SETPOINT = 7
    PORT_PLATFORM = 13
    PORT_LINK = 15

    print("\n--- Phase 1: Connection/Link packets ---")

    # Try sending link/null packets first (like a handshake)
    link_header = (PORT_LINK << 4) | 0  # Port 15, channel 0
    send_repeated("Link null packet", bytes([link_header]))

    # Echo/ping on link port
    link_echo = (PORT_LINK << 4) | 1  # Port 15, channel 1 (echo)
    send_repeated("Link echo packet", bytes([link_echo, 0x01, 0x02, 0x03]))

    print("\n--- Phase 2: Platform service packets ---")

    # Platform service - request version
    platform_header = (PORT_PLATFORM << 4) | 0
    send_repeated("Platform version request", bytes([platform_header, 0x00]))

    # Platform - app layer request
    platform_app = (PORT_PLATFORM << 4) | 1
    send_repeated("Platform app channel", bytes([platform_app, 0x00]))

    print("\n--- Phase 3: Try setpoint after init ---")

    # Now try commander setpoint
    cmd_header = (PORT_COMMANDER << 4) | 0
    cmd_data = bytes([cmd_header]) + struct.pack('<fffH', 0.0, 0.0, 0.0, thrust)
    send_repeated("Commander setpoint (after init)", cmd_data, count=100, delay=0.02)

    print("\n--- Phase 4: Generic setpoint commander ---")

    # Try generic setpoint (port 7) with different types
    gen_header = (PORT_GENERIC_SETPOINT << 4) | 0

    # Type 0 = Stop
    send_repeated("Generic setpoint type=0 (stop)", bytes([gen_header, 0x00]))

    # Type 1 = velocityWorld
    vel_data = bytes([gen_header, 0x01]) + struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)
    send_repeated("Generic setpoint type=1 (velocity)", vel_data)

    # Type 5 = CPPM emulation (roll, pitch, yaw, thrust)
    cppm_data = bytes([gen_header, 0x05]) + struct.pack('<fffH', 0.0, 0.0, 0.0, thrust)
    send_repeated("Generic setpoint type=5 (CPPM)", cppm_data)

    # Now try regular commander again
    send_repeated("Commander setpoint (final)", cmd_data, count=100, delay=0.02)

    print("\n--- Phase 5: Stop ---")
    stop_data = bytes([cmd_header]) + struct.pack('<fffH', 0.0, 0.0, 0.0, 0)
    send_repeated("Stop motors", stop_data, count=20)

    sock.close()
    print("\n" + "=" * 60)
    print("TEST COMPLETE - Did motors spin at any point?")
    print("=" * 60)


def test_packet_formats(host: str = "192.168.43.42", port: int = 2390):
    """Test different packet formats and checksums for ESP-Drone."""
    import socket

    print("=" * 60)
    print("ESP-DRONE PACKET FORMAT TEST (CHECKSUM VARIANTS)")
    print("=" * 60)
    print("\n*** WARNING: Motors may spin! Keep drone secured! ***\n")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)
    sock.connect((host, port))

    def send_packet(name: str, packet: bytes):
        """Send packet and show hex dump."""
        hex_str = ' '.join(f'{b:02x}' for b in packet)
        print(f"\n{name}")
        print(f"  Packet ({len(packet)} bytes): {hex_str}")
        for _ in range(30):
            sock.send(packet)
            time.sleep(0.05)
        print("  Sent - check motors and serial output")
        time.sleep(1)

    thrust = 40000
    header = 0x30
    crtp_data = bytes([header]) + struct.pack('<fffH', 0.0, 0.0, 0.0, thrust)

    # Test 1: XOR checksum
    cksum1 = calc_cksum_xor(crtp_data)
    packet1 = crtp_data + bytes([cksum1])
    send_packet(f"Test 1: XOR checksum (0x{cksum1:02x})", packet1)

    # Test 2: Sum checksum
    cksum2 = calc_cksum_sum(crtp_data)
    packet2 = crtp_data + bytes([cksum2])
    send_packet(f"Test 2: SUM checksum (0x{cksum2:02x})", packet2)

    # Test 3: Two's complement sum
    cksum3 = calc_cksum_sum_complement(crtp_data)
    packet3 = crtp_data + bytes([cksum3])
    send_packet(f"Test 3: SUM complement checksum (0x{cksum3:02x})", packet3)

    # Test 4: Size prefix + data + XOR checksum
    size = len(crtp_data)
    full_data4 = bytes([size]) + crtp_data
    cksum4 = calc_cksum_xor(full_data4)
    packet4 = full_data4 + bytes([cksum4])
    send_packet(f"Test 4: [size]{size} + data + XOR (0x{cksum4:02x})", packet4)

    # Test 5: Size prefix + data + SUM checksum
    cksum5 = calc_cksum_sum(full_data4)
    packet5 = full_data4 + bytes([cksum5])
    send_packet(f"Test 5: [size]{size} + data + SUM (0x{cksum5:02x})", packet5)

    # Test 6: Checksum of just payload (not header)
    payload_only = struct.pack('<fffH', 0.0, 0.0, 0.0, thrust)
    cksum6 = calc_cksum_xor(payload_only)
    packet6 = bytes([header]) + payload_only + bytes([cksum6])
    send_packet(f"Test 6: header + payload + XOR(payload) (0x{cksum6:02x})", packet6)

    # Test 7: No checksum (maybe it's optional?)
    packet7 = crtp_data
    send_packet("Test 7: No checksum at all", packet7)

    # Test 8: CRSF/crossfire style - checksum includes size
    size8 = len(crtp_data) + 1  # +1 for checksum itself
    packet8_data = bytes([size8]) + crtp_data
    cksum8 = calc_cksum_xor(packet8_data)
    packet8 = packet8_data + bytes([cksum8])
    send_packet(f"Test 8: [size+1] + data + XOR", packet8)

    # Stop
    print("\nSending stop...")
    stop_data = bytes([0x30]) + struct.pack('<fffH', 0.0, 0.0, 0.0, 0)
    for cksum_fn in [calc_cksum_xor, calc_cksum_sum]:
        stop_packet = stop_data + bytes([cksum_fn(stop_data)])
        for _ in range(5):
            sock.send(stop_packet)
            time.sleep(0.05)

    sock.close()
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("Which test (if any) stopped showing 'cksum unmatched'?")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "arm":
        test_arming_sequences()
    else:
        test_packet_formats()
