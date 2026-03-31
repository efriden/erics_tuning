from tune.shared.audio.pyaudio_handler import PyAudioHandler
from tune.shared.audio.stream_handler import StreamHandler
from tune.shared.audio.device_info import DeviceInfo
from tune.shared.util.config_loader import AudioSettings

from textual.widgets import Static
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive

from rich.text import Text

import pyaudio
import numpy as np

from threading import Thread, Event

# todo: move this to config.yaml
MONITOR_AUDIO_SETTINGS: AudioSettings = AudioSettings(
    buffer_size=512,
    pyaudio_format=pyaudio.paInt16,
    samplerate=44100,
    n_channels=1,
)

MONITOR_UPDATES_PER_CYCLE: int = 30

# todo: add a 'sticky' max indicator.


class Monitor(Static):
    _stream: StreamHandler | None
    # the bar is 20 characters wide, defaulting to empty.
    level_bar: reactive[Text] = reactive(Text("[                    ] 0"))
    updates_per_seconds: int

    def __init__(self, ups: int | None = None, id: str | None = None) -> None:
        super().__init__(id=id)
        self.updates_per_seconds = ups if ups else MONITOR_UPDATES_PER_CYCLE
        self._stream = None

    def compose(self) -> ComposeResult:
        with Vertical(id="monitor_container"):
            yield Static(
                content=Text("Device level monitor:", style="bold"), id="monitor_lable"
            )
            yield Static(
                content=Text(text="[                    ] 0"), id="monitor_level_bar"
            )

    def on_mount(self) -> None:
        self.set_interval(1 / self.updates_per_seconds, self._update)

    def on_unmount(self) -> None:
        self.stop()

    def start(self, new_device: DeviceInfo) -> None:
        if self._stream is not None:
            if self._stream.device.system_index == new_device.system_index:
                return
            self._stream.swap_device(new_device)
            return
        self._stream = StreamHandler(device=new_device, settings=MONITOR_AUDIO_SETTINGS)
        self._stream.start()

    def stop(self) -> None:
        if self._stream is None:
            return
        self._stream.stop()

    def _update(self) -> None:
        if self._stream is None:
            return
        level: int = self._stream.get_level()
        filled = int(round(level / 100 * 20))  # the number of filled spaces

        if filled < 7:
            color = "green"
        elif filled < 14:
            color = "yellow"
        else:
            color = "red"

        bar: str = "█" * filled + " " * (20 - filled)
        bar_text: Text = Text(f"[{bar}] {level}", style=color)
        self.query_one("#monitor_level_bar", Static).update(bar_text)
