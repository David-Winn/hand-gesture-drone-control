# Gesture Drone

Control a drone with hand gestures using MediaPipe for hand tracking.

## How It Works

The system captures camera frames at 20Hz, detects hand landmarks with MediaPipe, and translates hand position into drone flight commands (roll, pitch, throttle).

```
Camera → Gesture Detector → Controller → Drone
           (MediaPipe)    (State Machine)  (UDP)
```

## Gesture Controls

| Gesture | Action |
|---------|--------|
| **Open Hand** | Fly - hand position controls movement |
| **Fist** | Hover - hold position |
| **Hand Out of Frame** | Land (after ~0.5s) |

### Flying

1. Show an open hand - your wrist position becomes the "neutral" reference
2. Move hand relative to neutral:
   - **Right/Left** → Roll
   - **Up/Down** → Throttle (front view) or Pitch (top-down view)
3. Make a fist to hover
4. Remove hand to land

## Setup

### Requirements

- Python 3.10+
- Webcam or ESP32-CAM

### Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic (Webcam)

```bash
python main.py
```

### With ESP-CAM and Drone

```bash
python main.py --camera esp --drone-ip udp://192.168.43.42
```

### Disable Settings UI

```bash
python main.py --no-ui
```

## CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--camera` | `webcam` | `webcam` or `esp` |
| `--perspective` | `front` | `front` or `topdown` camera angle |
| `--drone-ip` | config | Drone UDP address |
| `--cam-url` | config | ESP-CAM stream URL |
| `--no-ui` | off | Disable settings panel |
| `--debug` | off | Enable debug logging |

## Live Settings Panel

A settings window opens automatically, allowing real-time adjustment of:

- **Roll Scale** - Horizontal movement sensitivity
- **Pitch Scale** - Forward/back movement sensitivity
- **Throttle Scale** - Vertical movement sensitivity
- **Smoothing (EMA)** - Lower = smoother, Higher = more responsive

## Perspective Modes

### Front (`--perspective front`)
Standard webcam facing you.
- X movement → Roll
- Y movement → Throttle

### Top-down (`--perspective topdown`)
Camera looking down at your hand.
- X movement → Roll
- Y movement → Pitch
- Z (depth) → Throttle

## Project Structure

```
gesture_drone/
├── main.py              # Entry point
├── config.py            # Configuration constants
├── drone_config.yaml    # Tunable parameters
├── gesture/
│   ├── detector.py      # MediaPipe hand detection
│   ├── classifier.py    # Open/fist classification
│   └── controller.py    # State machine & command generation
├── drone/
│   ├── driver.py        # Abstract driver base
│   ├── udp_driver.py    # UDP drone control
│   └── esp_driver.py    # Crazyflie driver
├── stream/
│   ├── camera.py        # Abstract camera base
│   ├── webcam.py        # Local webcam
│   └── esp_cam.py       # ESP32-CAM stream
├── ui/
│   └── settings_panel.py # Live sensitivity adjustment
└── utils/
    └── logger.py
```

## Configuration

Edit `drone_config.yaml` to change default values:

```yaml
control:
  roll_scale: 45.0      # Max roll angle (degrees)
  pitch_scale: 45.0     # Max pitch angle (degrees)
  throttle_scale: 1.5   # Throttle sensitivity

stability:
  ema_alpha: 1.0        # Smoothing (0.1=smooth, 1.0=none)
  deadzone: 0.05        # Ignore small movements
```

## Troubleshooting

**No hand detected**: Ensure good lighting, keep hand clearly visible

**Not transitioning from hover to control**: with hand open, flip to back and front again (or vice versa)

**Camera won't open**: Check permissions, verify webcam isn't in use elsewhere

**Drone not responding**: Verify UDP address, check drone is armed via phone app

## License

MIT
