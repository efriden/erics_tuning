"""This file is a little bit of a mess - needs to be cleaned up."""

import logging
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from tune.shared.audio.pyaudio_handler import PyAudioHandler
from tune.shared.audio.device_info import DeviceInfo

from tune.tui.widgets.monitor import Monitor

logger = logging.getLogger(__name__)


class AudioDeviceSelectionScreen(ModalScreen):
    """Modal screen for selecting audio input device.

    Lists all available audio input devices with live audio level indicator
    for the highlighted device.
    """

    BINDINGS: list[tuple[str, str, str]] = [
        ("escape", "dismiss", "Cancel"),
        ("q", "dismiss", "Close"),
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("enter", "select_device", "Select"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.highlighted_index: int = 0

    def compose(self) -> ComposeResult:
        logger.debug("compose")

        devices: list[DeviceInfo] = PyAudioHandler.get_devices()

        if not devices:
            yield Static("No audio input devices found")
            return

        with Vertical(id="device_modal"):
            yield Static(
                "Select Audio Input Device (↑↓ to navigate, Enter to select, Esc to cancel)",
                id="device_modal_title",
            )

            options: list[Option] = []
            for i, device in enumerate(devices):
                label = (
                    f"{device.name}\n"
                    f"{device.max_input_channels} ch, {int(device.default_sample_rate)} Hz \n"
                    f"expected latency: from {device.default_low_input_latency:.3f} ms to {device.default_high_input_latency:.3f} ms."
                )

                options.append(Option(label, id=f"device-{i}"))

            yield OptionList(*options, id="device_list")

            yield Monitor(id="device_monitor")

    def on_mount(self) -> None:
        first_device: DeviceInfo = PyAudioHandler.get_device_by_index(0)
        self.query_one(Monitor).start(first_device)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Switch audio monitoring to highlighted device."""
        new_device: DeviceInfo = PyAudioHandler.get_device_by_index(event.option_index)
        self.query_one(Monitor).start(new_device)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle device selection."""
        device_index = event.option_index
        app = self.app
        handler = getattr(app, "handle_audio_device_selected", None)
        if callable(handler):
            handler(device_index)
        self.app.pop_screen()
