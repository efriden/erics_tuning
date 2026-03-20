from .screens.audio_devices import AudioDeviceSelectionScreen
from .screens.piano_frequencies import PianoFrequenciesScreen
from .screens.range_preset import RangePresetScreen
from .screens.main_screen import MainScreen
from tune.shared.audio.pyaudio_handler import PyAudioHandler
from tune.shared.util.setup_logging import setup_logging, log_run_start

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Placeholder
from textual.screen import Screen

from logging import Logger, getLogger

logger: Logger = getLogger(__name__)


class TUIApp(App):
    BINDINGS: list[tuple[str, str, str]] = [
        ("q", "app.quit", "Quit"),
        ("a", "screen_devices", "Audio Devices"),
        ("f", "screen_frequencies", "List Full Piano Range"),
        ("r", "screen_range_presets", "Set Frequency Range"),
    ]

    CSS_PATH: str = "static/style.tcss"

    SCREENS: dict[str, type[Screen]] = {
        "main": MainScreen,
        "devices": AudioDeviceSelectionScreen,
        "frequencies": PianoFrequenciesScreen,
        "range": RangePresetScreen,
    }

    def __init__(self) -> None:
        logger.info("Textual tui initialized.")
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen(screen="main")

    def on_unmount(self) -> None:
        PyAudioHandler.terminate()


def main() -> None:
    setup_logging()
    log_run_start()
    app = TUIApp()
    app.run()


if __name__ == "__main__":
    main()
