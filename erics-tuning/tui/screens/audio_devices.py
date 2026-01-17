import logging
import threading
from pathlib import Path

import numpy as np
import pyaudio
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from audioTest import get_audio_device_info

logger = logging.getLogger(__name__)


class AudioDeviceSelectionScreen(ModalScreen):
    """Modal screen for selecting audio input device.

    Lists all available audio input devices with live audio level indicator
    for the highlighted device.
    """

    BINDINGS = [
        ("escape", "dismiss", "Cancel"),
        ("q", "dismiss", "Close"),
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("enter", "select_device", "Select"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.devices: list[dict] = []
        self.highlighted_index: int = 0
        self.audio_thread: threading.Thread | None = None
        self.stop_flag: threading.Event = threading.Event()
        self.current_rms: float = 0.0
        self.current_level: float = 0.0
        self.current_monitored_device: int | None = None

    def compose(self) -> ComposeResult:  # type: ignore[override]
        logger.debug("AudioDeviceSelectionScreen.compose() called")

        try:
            info = get_audio_device_info()
            if info["error"]:
                logger.warning("Audio device error in modal: %s", info["error"])
                yield Static(f"Error: {info['error']}")
                return

            if not info["devices"]:
                yield Static("No audio input devices found")
                return

            # Store devices for later use
            self.devices = info["devices"]

            # Get current selected device from app.config if available
            app = self.app
            current_device_index = None
            cfg = getattr(app, "config", None)
            if isinstance(cfg, dict):
                current_device_index = cfg.get("audio_device_index")
                # Set highlighted index to current selection
                for i, dev in enumerate(self.devices):
                    if dev["index"] == current_device_index:
                        self.highlighted_index = i
                        break

            with Vertical(id="device_modal"):
                yield Static(
                    "Select Audio Input Device (↑↓ to navigate, Enter to select, Esc to cancel)",
                    id="device_modal_title",
                )

                # Build option list
                options: list[Option] = []
                for dev in self.devices:
                    is_default = info["default_input"] and dev["index"] == info["default_input"]["index"]
                    is_selected = current_device_index is not None and dev["index"] == current_device_index

                    prefix = "★" if is_selected else "•"
                    suffix = " (default)" if is_default else ""
                    label = (
                        f"{prefix} [{dev['index']}] {dev['name']}{suffix}\n"
                        f"  {dev['channels']} ch, {int(dev['rate'])} Hz"
                    )

                    options.append(Option(label, id=str(dev["index"])))

                yield OptionList(*options, id="device_list")
                yield Static("Level: [                    ] 0.0", id="device_level_bar")
                yield Static("RMS: 0.0 (level 0.0)", id="device_level_label")

            logger.debug("AudioDeviceSelectionScreen: %d devices available", len(self.devices))

        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to get audio devices in modal")
            yield Static(f"Error: {exc}")

    def on_mount(self) -> None:  # type: ignore[override]
        """Start audio monitoring for currently highlighted device."""
        logger.debug("AudioDeviceSelectionScreen.on_mount()")
        if self.devices:
            # Set highlighted option in the list
            option_list = self.query_one("#device_list", OptionList)
            option_list.highlighted = self.highlighted_index
            # Start monitoring the highlighted device
            self._start_monitoring_device(self.highlighted_index)

    def on_unmount(self) -> None:  # type: ignore[override]
        """Stop audio monitoring thread when screen is closed."""
        logger.debug("AudioDeviceSelectionScreen.on_unmount()")
        self._stop_monitoring()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:  # type: ignore[override]
        """Switch audio monitoring to highlighted device."""
        try:
            option_list = self.query_one("#device_list", OptionList)
            new_index = option_list.highlighted
            if new_index is not None and new_index != self.highlighted_index:
                logger.debug("Device highlighted changed from %s to %s", self.highlighted_index, new_index)
                self.highlighted_index = new_index
                self._start_monitoring_device(new_index)
        except Exception as exc:
            logger.debug("Error handling highlight change: %s", exc)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:  # type: ignore[override]
        """Handle device selection."""
        device_index = int(event.option.id)
        logger.debug("Device selected: %s", device_index)
        app = self.app
        handler = getattr(app, "handle_audio_device_selected", None)
        if callable(handler):
            handler(device_index)
        self.app.pop_screen()

    def action_cursor_up(self) -> None:  # type: ignore[override]
        """Move highlight up."""
        option_list = self.query_one("#device_list", OptionList)
        option_list.action_cursor_up()

    def action_cursor_down(self) -> None:  # type: ignore[override]
        """Move highlight down."""
        option_list = self.query_one("#device_list", OptionList)
        option_list.action_cursor_down()

    def action_select_device(self) -> None:  # type: ignore[override]
        """Select currently highlighted device."""
        option_list = self.query_one("#device_list", OptionList)
        option_list.action_select()

    def action_dismiss(self) -> None:  # type: ignore[override]
        """Cancel and close modal."""
        logger.debug("AudioDeviceSelectionScreen.action_dismiss() called")
        self.app.pop_screen()

    # --- audio monitoring -------------------------------------------------

    def _start_monitoring_device(self, device_list_index: int) -> None:
        """Start or restart audio monitoring for the device at the given list index."""
        if device_list_index >= len(self.devices):
            return

        device_index = self.devices[device_list_index]["index"]

        # Stop current monitoring if any
        self._stop_monitoring()

        # Start new monitoring thread
        self.stop_flag = threading.Event()
        self.current_monitored_device = device_index

        thread = threading.Thread(
            target=self._audio_monitor_worker,
            args=(device_index, self.stop_flag),
            daemon=True,
        )
        self.audio_thread = thread
        thread.start()
        logger.debug("Started audio monitor for device %s", device_index)

    def _audio_monitor_worker(self, device_index: int, stop_flag: threading.Event) -> None:
        """Worker thread that captures audio and calculates RMS levels."""
        CHUNK = 512
        RATE = 44100
        FORMAT = pyaudio.paInt16

        p = None
        stream = None

        try:
            p = pyaudio.PyAudio()
            device_info = p.get_device_info_by_index(device_index)
            logger.debug("Monitoring device %s: %s", device_index, device_info["name"])

            try:
                stream = p.open(
                    format=FORMAT,
                    channels=1,
                    rate=RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=CHUNK,
                )
                logger.debug("Audio stream opened successfully for device %s", device_index)
            except Exception as e:
                logger.warning("Could not open device %s: %s", device_index, e)
                return

            logger.debug("Starting audio read loop for device %s", device_index)
            read_count = 0
            while not stop_flag.is_set():
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)

                    # Calculate RMS and normalize
                    rms = np.sqrt(np.mean(samples ** 2))
                    level = min(100, (rms / 3000.0) * 100)

                    read_count += 1
                    if read_count % 10 == 0:  # Log every 10 reads
                        logger.debug("Device %s: RMS=%.1f, level=%.1f", device_index, rms, level)

                    # Store latest values for UI
                    self.current_rms = float(rms)
                    self.current_level = float(level)

                    # Update UI (scheduled onto main thread)
                    self._update_level_bar()
                    self._update_level_label()

                except (OSError, IOError) as e:
                    logger.warning("Audio read error on device %s: %s", device_index, e)
                    break
                except Exception as e:  # pragma: no cover - defensive
                    logger.exception("Unexpected error reading audio on device %s: %s", device_index, e)
                    break

            logger.debug("Exited audio read loop for device %s (read %s chunks)", device_index, read_count)

        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Audio monitor error: %s", exc)
        finally:
            if stream:
                try:
                    if stream.is_active():
                        stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if p:
                try:
                    p.terminate()
                except Exception:
                    pass
            logger.debug("Audio monitor stopped for device %s", device_index)

    def _update_level_bar(self) -> None:
        """Update the simple text level bar (thread-safe, with colour)."""
        try:
            level = max(0.0, min(100.0, float(self.current_level)))
            width = 20  # characters inside the brackets
            filled = int(round((level / 100.0) * width))

            # Choose colour band
            if level < 33.0:
                colour = "green"
            elif level < 66.0:
                colour = "yellow"
            else:
                colour = "red"

            bar_core = "█" * filled + " " * (width - filled)
            # Use Textual/Rich markup for colour. We keep the brackets that
            # visually frame the bar *inside* the colour span to avoid
            # confusing the markup parser.
            bar_str = f"[{colour}][" + bar_core + f"][/{colour}]"
            text = f"Level: {bar_str} {level:4.1f}"

            def _set() -> None:
                bar = self.query_one("#device_level_bar", Static)
                bar.update(text)

            self.app.call_from_thread(_set)
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Level-bar update error: %s: %s", type(e).__name__, e)

    def _update_level_label(self) -> None:
        """Update the numeric RMS/level label (thread-safe)."""
        try:
            rms = float(self.current_rms)
            level = float(self.current_level)
            text = f"RMS: {rms:5.1f} (level {level:4.1f})"

            def _set() -> None:
                label = self.query_one("#device_level_label", Static)
                label.update(text)

            self.app.call_from_thread(_set)
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Level-label update error: %s: %s", type(e).__name__, e)

    def _stop_monitoring(self) -> None:
        """Stop the current audio monitoring thread."""
        if self.audio_thread and self.audio_thread.is_alive():
            self.stop_flag.set()
            self.audio_thread.join(timeout=1.0)
            logger.debug("Stopped audio monitoring")
        self.current_monitored_device = None
