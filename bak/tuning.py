"""Textual TUI front-end for the piano tuner.

This app controls:
- frequency range (fmin, fmax)
- beat detection on/off

It writes these settings to a JSON tuning file (by default
`analyzer/tuning_config.json`) and can start/stop the Qt-based analyzer
(`analyzer/frequencyAnalysis.py`) as a subprocess.

All logging is routed to files under the `logs/` directory so that the
TUI keeps the terminal clean (no stdout/stderr noise).
"""

from __future__ import annotations


# Start threads to capture output
import threading

from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import signal
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Tuple

from textual import events
from textual.app import App, ComposeResult, SystemCommand
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static, Digits

from screens import (
    RangePresetScreen,
    PianoFrequenciesScreen,
    AudioDeviceSelectionScreen,
    LogsScreen,
    AnalyzerLayoutScreen,
    PRESETS,
)

# Import audio device info function
from audioTest import get_audio_device_info

# Paths
ROOT = Path(__file__).resolve().parent
APP_CONFIG_PATH = ROOT / "config.json"


def _load_app_paths() -> tuple[Path, Path, Path, Path]:
    """Load analyzer and logging paths from config.json (with sane defaults).

    Returns (tuning_config_path, analyzer_script_path, tui_log_path, analyzer_log_path).
    """
    config_data: dict = {}
    if APP_CONFIG_PATH.is_file():
        try:
            config_data = json.loads(APP_CONFIG_PATH.read_text("utf-8"))
        except Exception:
            # If config is invalid, fall back to built-in defaults.
            config_data = {}

    analyzer_cfg = config_data.get("analyzer", {})
    logging_cfg = config_data.get("logging", {})

    tuning_config_rel = analyzer_cfg.get("config", "analyzer/tuning_config.json")
    analyzer_script_rel = analyzer_cfg.get("script", "analyzer/frequencyAnalysis.py")
    tui_log_rel = logging_cfg.get("tui_log", "logs/tuning.log")
    analyzer_log_rel = logging_cfg.get("analyzer_log", "logs/analyzer.log")

    tuning_config_path = ROOT / tuning_config_rel
    analyzer_script_path = ROOT / analyzer_script_rel
    tui_log_path = ROOT / tui_log_rel
    analyzer_log_path = ROOT / analyzer_log_rel

    # Ensure log directories exist
    tui_log_path.parent.mkdir(parents=True, exist_ok=True)
    analyzer_log_path.parent.mkdir(parents=True, exist_ok=True)

    return tuning_config_path, analyzer_script_path, tui_log_path, analyzer_log_path


CONFIG_PATH, ANALYZER_SCRIPT, LOG_PATH, ANALYZER_LOG_PATH = _load_app_paths()

# Central logging configuration: log everything to a rotating file,
# no console/stream handlers. Other modules inherit this config.
_handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for detailed logging
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[_handler],
)
logging.captureWarnings(True)
logger = logging.getLogger(__name__)


DEFAULT_CONFIG = {
    "fmin": 20.0,
    "fmax": 5000.0,
    "beat_detection_enabled": True,
}


def load_config() -> dict:
    logger.debug(f"load_config() called, checking {CONFIG_PATH}")
    if CONFIG_PATH.is_file():
        try:
            cfg = json.loads(CONFIG_PATH.read_text("utf-8"))
            logger.info(f"Loaded config from {CONFIG_PATH}: fmin={cfg.get('fmin')}, fmax={cfg.get('fmax')}, beat_detection={cfg.get('beat_detection_enabled')}")
            return cfg
        except Exception as exc:
            logger.warning(f"Failed to load config from {CONFIG_PATH}: {exc}. Using defaults.")
            return DEFAULT_CONFIG.copy()
    logger.info(f"No config file found at {CONFIG_PATH}. Using defaults.")
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    logger.debug(f"save_config() called with: {cfg}")
    data = DEFAULT_CONFIG.copy()
    data.update(cfg)
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info(f"Saved config to {CONFIG_PATH}: fmin={data.get('fmin')}, fmax={data.get('fmax')}, beat_detection={data.get('beat_detection_enabled')}")


class TuningApp(App):
    """Main Textual TUI for controlling the tuner and launching Qt analyzer."""

    # Use external CSS stylesheet
    CSS_PATH = "static/style.tcss"

    # Only keep a single explicit key binding for quit; other actions are
    # available via on-screen buttons and the command palette.
    BINDINGS = [
        ("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        logger.info("TuningApp initializing")
        self.config = load_config()
        self.analyzer_proc: subprocess.Popen | None = None

    # ----- lifecycle -----

    def compose(self) -> ComposeResult:  # type: ignore[override]
        logger.debug("TuningApp.compose() called")
        cfg = self.config

        yield Header(show_clock=False)

        with VerticalScroll():
            with Static(id="box"):
                yield Label("Erics Tuning Controller", id="title")

                # Clock + status info at the top
                yield Digits("", id="clock")
                yield Label(self._status_text(), id="status")
                yield Label(self._range_text(), id="range_label")
                yield Label(self._analyzer_status_text(), id="analyzer_status")

                # Main controls (stacked vertically for narrow terminals)
                with Vertical(id="controls"):
                    yield Button("Range & presets…", id="open_range_modal", classes="control-btn")
                    yield Button("Toggle analyzer", id="toggle_analyzer_btn", classes="control-btn")
                    yield Button("Analyzer graphs…", id="open_analyzer_layout_btn", classes="control-btn")
                    yield Button("View logs…", id="open_logs_btn", classes="control-btn")
                    yield Button("Audio devices…", id="open_audio_devices_btn", classes="control-btn")

                # Audio device information box
                with Static(id="audio_device_box"):
                    yield Label("Audio Devices", id="audio_device_title")
                    yield Label(self._audio_device_text(), id="audio_device_info")

        yield Footer()

    # ----- helpers -----
    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        logger.debug(f"TuningApp.get_system_commands() called for screen: {screen}")
        yield from super().get_system_commands(screen)
        yield SystemCommand("Bell", "Ring the bell", self.bell)
        yield SystemCommand(
            "Range & Presets",
            "Choose the min and max frequencies for the YIN pitch detection.",
            self.action_open_range_preset_modal,
        )
        yield SystemCommand(
            "Frequencies",
            "A full list of frequencies for an equally tempered piano",
            self.action_open_piano_frequencies,
        )
        yield SystemCommand(
            "Toggle Analyzer",
            "Start or stop the Qt frequency analyzer window.",
            self.action_toggle_analyzer,
        )
        yield SystemCommand(
            "Audio Devices",
            "Choose the audio input device for analysis.",
            self.action_open_audio_devices,
        )
        yield SystemCommand(
            "Analyzer Layout",
            "Choose which graphs the analyzer shows at startup.",
            self.action_open_analyzer_layout,
        )
        yield SystemCommand(
            "Logs",
            "Open the latest entries from the TUI and analyzer logs.",
            self.action_open_logs,
        )

    def on_key(self, event: events.Key) -> None:  # type: ignore[override]
        """Allow Up/Down arrows to move between the main control buttons.

        This only activates when one of the primary control buttons has
        focus, so it does not interfere with modal dialogs or text inputs.
        """
        if event.key not in ("up", "down"):
            return

        focused = self.focused
        if not isinstance(focused, Button) or "control-btn" not in focused.classes:
            # Let the normal key handling proceed for other widgets
            return

        try:
            buttons = list(self.query("Button.control-btn"))
            if not buttons:
                return

            try:
                index = buttons.index(focused)
            except ValueError:
                index = 0

            if event.key == "down":
                index = min(len(buttons) - 1, index + 1)
            else:
                index = max(0, index - 1)

            buttons[index].focus()
            event.stop()
        except Exception:
            # Never let navigation errors break other key handling
            return

    def _status_text(self) -> str:
        status = self.config.get('beat_detection_enabled', True)
        logger.debug(f"_status_text() returning beat_detection={status}")
        return (
            f"Beat Detection: {'ON' if status else 'OFF'} (auto)"
        )

    def _range_text(self) -> str:
        fmin = self.config['fmin']
        fmax = self.config['fmax']
        logger.debug(f"_range_text() returning fmin={fmin}, fmax={fmax}")
        return f"Range: {fmin:.1f} – {fmax:.1f} Hz"

    def _analyzer_status_text(self) -> str:
        running = self.analyzer_proc is not None and self.analyzer_proc.poll() is None
        logger.debug(f"_analyzer_status_text() returning running={running}")
        return "Analyzer: RUNNING" if running else "Analyzer: STOPPED"

    def _audio_device_text(self) -> str:
        """Get audio device information as formatted text."""
        logger.debug("_audio_device_text() called")
        try:
            info = get_audio_device_info()
            if info['error']:
                logger.warning(f"Audio device error: {info['error']}")
                return f"Error: {info['error']}"
            
            lines = []
            selected_index = self.config.get("audio_device_index")
            
            # Show selected device if configured
            if selected_index is not None:
                selected_dev = next((d for d in info['devices'] if d['index'] == selected_index), None)
                if selected_dev:
                    lines.append(f"Selected: {selected_dev['name']}")
                    lines.append(f"  Index: {selected_dev['index']} | Channels: {selected_dev['channels']} | Rate: {int(selected_dev['rate'])} Hz")
                else:
                    lines.append(f"Selected device (index {selected_index}) not found!")
            elif info['default_input']:
                # Show default if no selection made
                dev = info['default_input']
                lines.append(f"Default: {dev['name']}")
                lines.append(f"  Index: {dev['index']} | Channels: {dev['channels']} | Rate: {int(dev['rate'])} Hz")
            else:
                lines.append("No default input device found")
            
            if len(info['devices']) > 1:
                lines.append(
                    f"\n{len(info['devices'])} input devices available (use 'Audio devices…' to change)"
                )

            return "\n".join(lines)
        except Exception as exc:
            logger.exception("Failed to get audio device info")
            return f"Error querying devices: {exc}"

    def _update_status_labels(self) -> None:
        logger.debug("_update_status_labels() called")
        self.query_one("#status", Label).update(self._status_text())
        self.query_one("#range_label", Label).update(self._range_text())
        self.query_one("#analyzer_status", Label).update(self._analyzer_status_text())

    def _set_range(self, fmin: float, fmax: float) -> None:
        """Validate and apply a new frequency range, updating config and status."""
        logger.debug(f"_set_range() called with fmin={fmin}, fmax={fmax}")
        if fmin < 0 or fmax <= fmin:
            logger.warning(f"Invalid range rejected: fmin={fmin}, fmax={fmax}")
            self.query_one("#status", Label).update(
                "Invalid range: require 0 <= fmin < fmax. Values unchanged."
            )
            return

        logger.info(f"Setting frequency range: {fmin:.1f} - {fmax:.1f} Hz")
        self.config["fmin"] = fmin
        self.config["fmax"] = fmax
        save_config(self.config)
        self._update_status_labels()

    # ----- Textual event handlers -----

    def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore[override]
        logger.debug(f"TuningApp.on_button_pressed: button_id={event.button.id}")
        if event.button.id == "open_range_modal":
            self.push_screen(RangePresetScreen())
        elif event.button.id == "toggle_analyzer_btn":
            self.action_toggle_analyzer()
        elif event.button.id == "open_analyzer_layout_btn":
            self.action_open_analyzer_layout()
        elif event.button.id == "open_logs_btn":
            self.action_open_logs()
        elif event.button.id == "open_audio_devices_btn":
            self.action_open_audio_devices()

    # ----- Range & preset handling from modal -----

    def handle_preset_selected(self, preset_name: str) -> None:
        logger.debug(f"handle_preset_selected() called with preset={preset_name}")
        if preset_name not in PRESETS:
            logger.warning(f"Unknown preset: {preset_name}")
            return

        fmin, fmax = PRESETS[preset_name]
        logger.debug(f"Applying preset '{preset_name}': fmin={fmin}, fmax={fmax}")
        self._set_range(fmin, fmax)

    def handle_manual_range(self, fmin_text: str, fmax_text: str) -> None:
        logger.debug(f"handle_manual_range() called with fmin_text='{fmin_text}', fmax_text='{fmax_text}'")
        try:
            fmin = float(fmin_text) if fmin_text else self.config["fmin"]
            fmax = float(fmax_text) if fmax_text else self.config["fmax"]
        except ValueError as exc:
            logger.warning(f"Invalid numeric input in handle_manual_range: {exc}")
            self.query_one("#status", Label).update(
                "Invalid numeric input. Values unchanged."
            )
            return

        self._set_range(fmin, fmax)

    def handle_audio_device_selected(self, device_index: int) -> None:
        """Handle audio device selection from modal."""
        logger.debug(f"handle_audio_device_selected() called with device_index={device_index}")
        self.config["audio_device_index"] = device_index
        logger.info(f"Audio device set to index {device_index}")
        save_config(self.config)
        # Update the audio device info display
        try:
            self.query_one("#audio_device_info", Label).update(self._audio_device_text())
        except Exception as exc:
            logger.warning(f"Failed to update audio device info label: {exc}")

    # ----- Analyzer process control -----

    def action_open_range_preset_modal(self) -> None:  # type: ignore[override]:
        """Keyboard binding to open the range+presets modal (key: 'r')."""
        logger.debug("action_open_range_preset_modal() called")
        self.push_screen(RangePresetScreen())

    def action_open_piano_frequencies(self) -> None:  # type: ignore[override]
        """Keyboard binding to open the equal-tempered piano frequency list (key: 'n')."""
        logger.debug("action_open_piano_frequencies() called")
        self.push_screen(PianoFrequenciesScreen())

    def action_open_logs(self) -> None:  # type: ignore[override]
        """Keyboard binding to open the logs viewer modal (key: 'l')."""
        logger.debug("action_open_logs() called")
        self.push_screen(LogsScreen())

    def action_open_audio_devices(self) -> None:  # type: ignore[override]
        """Keyboard binding to open the audio device selection modal (key: 'd')."""
        logger.debug("action_open_audio_devices() called")
        self.push_screen(AudioDeviceSelectionScreen())

    def action_open_analyzer_layout(self) -> None:  # type: ignore[override]
        """Open the analyzer layout configuration modal."""
        logger.debug("action_open_analyzer_layout() called")
        self.push_screen(AnalyzerLayoutScreen())

    def action_toggle_analyzer(self) -> None:  # type: ignore[override]
        logger.debug("action_toggle_analyzer() called")
        running = self.analyzer_proc is not None and self.analyzer_proc.poll() is None
        logger.debug(f"Analyzer currently running: {running}")
        if running:
            # Stop it
            logger.info("Stopping analyzer process")
            try:
                if hasattr(signal, "SIGINT"):
                    self.analyzer_proc.send_signal(signal.SIGINT)  # type: ignore[arg-type]
            except Exception as exc:
                logger.warning(f"Failed to send SIGINT to analyzer, terminating: {exc}")
                self.analyzer_proc.terminate()
            self.analyzer_proc = None
            self._update_status_labels()
            logger.info("Analyzer stopped")
            return

        cmd = [sys.executable, str(ANALYZER_SCRIPT), "--config", str(CONFIG_PATH)]
        logger.info(f"Starting analyzer: {' '.join(cmd)}")
        try:
            self.analyzer_proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
            logger.info(f"Analyzer started with PID {self.analyzer_proc.pid}")
            
            def log_output(pipe, log_func):
                for line in iter(pipe.readline, ''):
                    if line:
                        log_func(line.rstrip())
                pipe.close()
            
            threading.Thread(
                target=log_output,
                args=(self.analyzer_proc.stdout, logger.info),
                daemon=True
            ).start()
            
            threading.Thread(
                target=log_output,
                args=(self.analyzer_proc.stderr, logger.error),
                daemon=True
            ).start()
            
        except Exception as exc:
            logger.error(f"Failed to start analyzer: {exc}")
            self.query_one("#analyzer_status", Label).update(
                f"Analyzer failed to start: {exc}"
            )
            self.analyzer_proc = None
            return

        self._update_status_labels()

    async def on_shutdown_request(self) -> None:  # type: ignore[override]
        # Ensure analyzer is stopped when the TUI exits.
        logger.debug("on_shutdown_request() called")
        if self.analyzer_proc is not None and self.analyzer_proc.poll() is None:
            logger.debug("Stopping analyzer process on shutdown")
            try:
                if hasattr(signal, "SIGINT"):
                    self.analyzer_proc.send_signal(signal.SIGINT)  # type: ignore[arg-type]
            except Exception as exc:
                logger.warning(f"Failed to send SIGINT on shutdown: {exc}")
                self.analyzer_proc.terminate()


    def on_mount(self) -> None:  # type: ignore[override]
        """Log when the root application view has been mounted."""
        logger.debug("TuningApp.on_mount() called")

    def on_ready(self) -> None:  # type: ignore[override]
        """Initialize periodic clock updates when the app is ready.

        Also move focus to the top control button so arrow-key navigation
        works immediately.
        """
        logger.info("TuningApp ready")
        self._update_clock()
        self.set_interval(1, self._update_clock)

        # Give focus to the first main control button
        try:
            top_button = self.query_one("#open_range_modal", Button)
            top_button.focus()
        except Exception:
            logger.debug("Failed to set initial focus to top control button")

    def _update_clock(self) -> None:
        """Update the Digits widget with the current time."""
        try:
            clock = datetime.now().time()
            self.query_one("#clock", Digits).update(f"{clock:%H:%M:%S}")
        except Exception:
            logger.exception("Failed to update clock")
            logger.debug("Clock update failed")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting Tuning TUI application")
    logger.info("=" * 60)
    try:
        TuningApp().run()
    finally:
        logger.info("Tuning TUI application exiting")
