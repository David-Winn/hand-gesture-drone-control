"""
Live settings adjustment panel.

Provides a simple tkinter UI to adjust perception sensitivity
and hand-to-drone movement mapping in real-time.
"""

import tkinter as tk
from tkinter import ttk
import threading


class SettingsPanel:
    """
    Simple UI panel for adjusting control sensitivity settings live.

    Must run on the main thread (macOS requirement).
    """

    def __init__(self, config_store, on_close_callback=None):
        """
        Initialize the settings panel.

        Args:
            config_store: Mutable config object with get/set methods.
            on_close_callback: Function to call when window is closed.
        """
        self._config = config_store
        self._on_close_callback = on_close_callback
        self._root = None
        self._running = False
        self._tooltip = None

    def setup(self):
        """Set up the tkinter window (call from main thread)."""
        self._root = tk.Tk()
        self._root.title("Drone Sensitivity Settings")
        self._root.geometry("400x350")
        self._root.resizable(False, False)

        # Style
        style = ttk.Style()
        style.configure("TLabel", padding=5)
        style.configure("TScale", padding=5)

        # Main frame
        main_frame = ttk.Frame(self._root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(main_frame, text="Perception Sensitivity", font=("Helvetica", 14, "bold"))
        title.pack(pady=(0, 10))

        # Create sliders
        self._create_slider(
            main_frame,
            "Roll Scale",
            "roll_scale",
            5.0, 90.0,
            "How much horizontal hand movement affects roll"
        )

        self._create_slider(
            main_frame,
            "Pitch Scale",
            "pitch_scale",
            5.0, 90.0,
            "How much forward/back hand movement affects pitch"
        )

        self._create_slider(
            main_frame,
            "Throttle Scale",
            "throttle_scale",
            0.2, 3.0,
            "How much vertical hand movement affects throttle"
        )

        self._create_slider(
            main_frame,
            "Smoothing (EMA)",
            "ema_alpha",
            0.1, 1.0,
            "Lower = smoother but slower, Higher = faster but jittery"
        )

        # Info label
        info = ttk.Label(
            main_frame,
            text="Changes apply immediately. Close window or press 'q' in camera to quit.",
            font=("Helvetica", 9, "italic"),
            foreground="gray",
            wraplength=350
        )
        info.pack(pady=(15, 0))

        # Handle window close
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._running = True

    def update_once(self) -> bool:
        """
        Process pending tkinter events (non-blocking).

        Returns:
            True if still running, False if closed.
        """
        if not self._running or self._root is None:
            return False
        try:
            self._root.update()
            return self._running
        except tk.TclError:
            return False

    def stop(self):
        """Stop and destroy the panel."""
        self._running = False
        if self._root is not None:
            try:
                self._root.destroy()
            except Exception:
                pass
            self._root = None

    def is_running(self) -> bool:
        """Check if panel is still running."""
        return self._running

    def _create_slider(self, parent, label: str, key: str, min_val: float, max_val: float, tooltip: str):
        """Create a labeled slider for a config value."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=5)

        # Label with current value
        current_val = self._config.get(key)
        label_var = tk.StringVar(value=f"{label}: {current_val:.2f}")
        lbl = ttk.Label(frame, textvariable=label_var, width=25, anchor="w")
        lbl.pack(side=tk.LEFT)

        # Slider
        slider = ttk.Scale(
            frame,
            from_=min_val,
            to=max_val,
            orient=tk.HORIZONTAL,
            length=180
        )
        slider.set(current_val)
        slider.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Update callback
        def on_change(val):
            float_val = float(val)
            self._config.set(key, float_val)
            label_var.set(f"{label}: {float_val:.2f}")

        slider.configure(command=on_change)

        # Tooltip (simple hover text)
        lbl.bind("<Enter>", lambda e: self._show_tooltip(e, tooltip))
        lbl.bind("<Leave>", lambda e: self._hide_tooltip())

    def _show_tooltip(self, event, text):
        """Show tooltip near cursor."""
        if self._tooltip:
            self._tooltip.destroy()

        self._tooltip = tk.Toplevel(self._root)
        self._tooltip.wm_overrideredirect(True)
        self._tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

        label = ttk.Label(self._tooltip, text=text, background="lightyellow", padding=3)
        label.pack()

    def _hide_tooltip(self):
        """Hide tooltip."""
        if self._tooltip:
            self._tooltip.destroy()
            self._tooltip = None

    def _on_close(self):
        """Handle window close."""
        self._running = False
        if self._on_close_callback:
            self._on_close_callback()
        if self._root:
            self._root.destroy()
            self._root = None


class ConfigStore:
    """
    Thread-safe mutable configuration store.

    Provides get/set access to config values that can be modified
    at runtime by the settings UI.
    """

    def __init__(self):
        """Initialize with default values from config module."""
        import config as cfg

        self._lock = threading.Lock()
        self._values = {
            "roll_scale": cfg.ROLL_SCALE,
            "pitch_scale": cfg.PITCH_SCALE,
            "throttle_scale": cfg.THROTTLE_SCALE,
            "throttle_z_scale": cfg.THROTTLE_Z_SCALE,
            "ema_alpha": cfg.EMA_ALPHA,
            "deadzone": cfg.DEADZONE,
        }

    def get(self, key: str) -> float:
        """Get a config value."""
        with self._lock:
            return self._values.get(key, 0.0)

    def set(self, key: str, value: float) -> None:
        """Set a config value."""
        with self._lock:
            self._values[key] = value

    def get_all(self) -> dict:
        """Get all config values."""
        with self._lock:
            return self._values.copy()


# Global config store instance
_config_store = None


def get_config_store() -> ConfigStore:
    """Get the global config store instance."""
    global _config_store
    if _config_store is None:
        _config_store = ConfigStore()
    return _config_store
