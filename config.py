"""
Configuration constants for the gesture-controlled drone system.

This module loads configuration from drone_config.yaml if available,
falling back to default values if the file is missing or has errors.
"""

import os
from pathlib import Path

# Try to load YAML configuration
_config = {}
_config_path = Path(__file__).parent / "drone_config.yaml"

try:
    import yaml
    if _config_path.exists():
        with open(_config_path, 'r') as f:
            _config = yaml.safe_load(f) or {}
        print(f"Loaded configuration from {_config_path}")
except ImportError:
    print("Warning: PyYAML not installed. Using default configuration.")
except Exception as e:
    print(f"Warning: Failed to load config file: {e}. Using defaults.")


def _get(section: str, key: str, default):
    """Helper to get nested config values with fallback."""
    try:
        parts = section.split('.')
        value = _config
        for part in parts:
            value = value[part]
        return value.get(key, default)
    except (KeyError, TypeError, AttributeError):
        return default


# =============================================================================
# NETWORK ENDPOINTS
# =============================================================================
ESP_CAM_URL = _get('network', 'esp_cam_url', "http://192.168.4.1:81/stream")
ESP_DRONE_UDP = _get('network', 'esp_drone_udp', "udp://192.168.43.42")

# =============================================================================
# MOTOR POWER LIMITS
# =============================================================================
# Crazyflie motor limits
CRAZYFLIE_MIN_THRUST = _get('motor.crazyflie', 'min_thrust', 10001)
CRAZYFLIE_MAX_THRUST = _get('motor.crazyflie', 'max_thrust', 60000)
CRAZYFLIE_HOVER_THRUST = _get('motor.crazyflie', 'hover_thrust', 35000)

# ESP-Drone motor limits
ESP_DRONE_MIN_THRUST = _get('motor.esp_drone', 'min_thrust', 30000)
ESP_DRONE_MAX_THRUST = _get('motor.esp_drone', 'max_thrust', 65535)
ESP_DRONE_HOVER_THRUST = _get('motor.esp_drone', 'hover_thrust', 45000)

# Throttle input mapping
THROTTLE_MIN_INPUT = _get('motor.throttle', 'min_input', -1.0)
THROTTLE_MAX_INPUT = _get('motor.throttle', 'max_input', 1.0)
THROTTLE_DEADBAND = _get('motor.throttle', 'deadband', 0.05)

# =============================================================================
# STABILITY TUNING
# =============================================================================
# EMA smoothing
EMA_ALPHA = _get('stability', 'ema_alpha', 0.3)

# Deadzone
DEADZONE = _get('stability', 'deadzone', 0.05)

# Rate limits
MAX_ROLL_RATE = _get('stability.rate_limits', 'max_roll_rate', 100.0)
MAX_PITCH_RATE = _get('stability.rate_limits', 'max_pitch_rate', 100.0)
MAX_YAW_RATE = _get('stability.rate_limits', 'max_yaw_rate', 100.0)
MAX_THROTTLE_RATE = _get('stability.rate_limits', 'max_throttle_rate', 2.0)

# PID gains (for future implementation)
PID_ROLL_P = _get('stability.pid.roll', 'p', 1.0)
PID_ROLL_I = _get('stability.pid.roll', 'i', 0.0)
PID_ROLL_D = _get('stability.pid.roll', 'd', 0.0)

PID_PITCH_P = _get('stability.pid.pitch', 'p', 1.0)
PID_PITCH_I = _get('stability.pid.pitch', 'i', 0.0)
PID_PITCH_D = _get('stability.pid.pitch', 'd', 0.0)

PID_YAW_P = _get('stability.pid.yaw', 'p', 1.0)
PID_YAW_I = _get('stability.pid.yaw', 'i', 0.0)
PID_YAW_D = _get('stability.pid.yaw', 'd', 0.0)

PID_ALT_P = _get('stability.pid.altitude', 'p', 1.0)
PID_ALT_I = _get('stability.pid.altitude', 'i', 0.0)
PID_ALT_D = _get('stability.pid.altitude', 'd', 0.0)

# =============================================================================
# CONTROL SENSITIVITY
# =============================================================================
ROLL_SCALE = _get('control', 'roll_scale', 30.0)
PITCH_SCALE = _get('control', 'pitch_scale', 30.0)
THROTTLE_SCALE = _get('control', 'throttle_scale', 1.0)
THROTTLE_Z_SCALE = _get('control', 'throttle_z_scale', 0.6)
YAW_SCALE = _get('control', 'yaw_scale', 30.0)

# Control timing
COMMAND_RATE_HZ = _get('control', 'command_rate_hz', 20)
DEAD_FRAME_LIMIT = _get('control', 'dead_frame_limit', 10)

# =============================================================================
# GESTURE RECOGNITION
# =============================================================================
MIN_DETECTION_CONFIDENCE = _get('gesture', 'min_detection_confidence', 0.7)
MIN_TRACKING_CONFIDENCE = _get('gesture', 'min_tracking_confidence', 0.5)
WRIST_SPREAD_OPEN_THRESHOLD = _get('gesture', 'wrist_spread_open', 0.35)
WRIST_SPREAD_FIST_THRESHOLD = _get('gesture', 'wrist_spread_fist', 0.20)

def reload_config():
    """Reload configuration from the YAML file."""
    global _config
    try:
        import yaml
        if _config_path.exists():
            with open(_config_path, 'r') as f:
                _config = yaml.safe_load(f) or {}
            print(f"Reloaded configuration from {_config_path}")
            return True
    except Exception as e:
        print(f"Failed to reload config: {e}")
    return False


def get_motor_thrust_range(driver_type: str) -> tuple:
    """Get the min/max thrust range for a specific driver type.

    Args:
        driver_type: One of 'crazyflie' or 'esp_drone'

    Returns:
        Tuple of (min_thrust, max_thrust, hover_thrust)
    """
    if driver_type == 'crazyflie':
        return (CRAZYFLIE_MIN_THRUST, CRAZYFLIE_MAX_THRUST, CRAZYFLIE_HOVER_THRUST)
    else:  # esp_drone
        return (ESP_DRONE_MIN_THRUST, ESP_DRONE_MAX_THRUST, ESP_DRONE_HOVER_THRUST)


def get_pid_gains(axis: str) -> tuple:
    """Get PID gains for a specific axis.

    Args:
        axis: One of 'roll', 'pitch', 'yaw', or 'altitude'

    Returns:
        Tuple of (P, I, D) gains
    """
    gains = {
        'roll': (PID_ROLL_P, PID_ROLL_I, PID_ROLL_D),
        'pitch': (PID_PITCH_P, PID_PITCH_I, PID_PITCH_D),
        'yaw': (PID_YAW_P, PID_YAW_I, PID_YAW_D),
        'altitude': (PID_ALT_P, PID_ALT_I, PID_ALT_D),
    }
    return gains.get(axis, (1.0, 0.0, 0.0))
