from tune.tui.workers.log_reader import NewLogLine
from .screens.audio_devices import AudioDeviceSelectionScreen
from .screens.range_preset import RangePresetScreen
from .screens.main_screen import MainScreen
from tune.shared.audio.pyaudio_handler import PyAudioHandler
from tune.shared.util.setup_logging import setup_logging, log_run_start
from tune.tui.widgets.process_window import ProcessWindow, RegisterProcess

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label
from textual.screen import Screen

import asyncio

from logging import Logger, getLogger

logger: Logger = getLogger(__name__)


class TUIApp(App):
    _processes: list[ProcessWindow]

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
        "range": RangePresetScreen,
    }

    def __init__(self) -> None:
        logger.info("Textual tui initialized.")
        super().__init__()
        self._processes: list[ProcessWindow] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Loading main screen...")
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen(screen="main")

    def on_new_log_line(self, message: NewLogLine) -> None:
        log_line = message.log_line
        for screen in self.app.screen_stack:
            for window in screen.query(ProcessWindow):
                if (
                    window.process_name in log_line.sender
                    or window.process_name in log_line.message
                ):
                    window.add_log_line(log_line)

    def on_register_process(self, message: RegisterProcess) -> None:
        match message.action:
            case "register":
                self._processes.append(message.process)
            case "unregister":
                self._processes.remove(message.process)


async def main() -> None:
    setup_logging()
    log_run_start()
    app = TUIApp()
    try:
        await app.run_async()
    finally:
        PyAudioHandler.terminate()
        active_processes = list(app._processes)
        await asyncio.wait_for(
            asyncio.gather(*[process.stop() for process in active_processes]),
            timeout=4.0,
        )


def await_main() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    await_main()
