from tune.tui.workers.log_reader import NewLogLine
from .screens.audio_devices import AudioDeviceSelectionScreen
from .screens.piano_frequencies import PianoFrequenciesScreen
from .screens.range_preset import RangePresetScreen
from .screens.main_screen import MainScreen
from tune.shared.audio.pyaudio_handler import PyAudioHandler
from tune.shared.util.setup_logging import setup_logging, log_run_start
from tune.tui.widgets.process_window import ProcessWindow

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
        for process in self.query(ProcessWindow):
            process.stop()  # todo: this will run a worker with async processes - maybe it wont be allowed to finish.

    def on_new_log_line(self, message: NewLogLine) -> None:
        log_line = message.log_line
        for screen in self.app.screen_stack:
            for window in screen.query(ProcessWindow):
                if window.process_name in log_line.sender:
                    window.add_log_line(log_line)


def main() -> None:
    setup_logging()
    log_run_start()
    app = TUIApp()
    app.run()


if __name__ == "__main__":
    main()
