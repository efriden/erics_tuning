from textual.containers import VerticalScroll
from textual.widgets import Button, Header, Footer, TabbedContent, TabPane
from textual.screen import Screen
from textual.app import ComposeResult

from tune.tui.widgets.process_window import ProcessWindow, ProcessConfig
from tune.tui.widgets.piano_frequencies import PianoFrequencies
from tune.tui.widgets.current_note import CurrentNote

from logging import getLogger

logger = getLogger(__name__)

# todo - move this to config.yaml
PROCESS_CONFIGS: list[ProcessConfig] = [
    ProcessConfig(name="analyzer", command=["analyzer"], use_async=True),
    ProcessConfig(name="broker", command=["broker"], use_async=True),
    ProcessConfig(name="visualizer", command=["visualizer"], use_async=False),
]


class MainScreen(Screen):
    BINDINGS: list[tuple[str, str, str]] = [
        ("a", "screen_devices", "Audio Devices"),
        ("f", "screen_frequencies", "List Full Piano Range"),
        ("r", "screen_range_presets", "Set Frequency Range"),
    ]

    def compose(self) -> ComposeResult:
        logger.debug("compose")
        yield Header()

        with TabbedContent():
            with TabPane("Main Dash"):
                yield CurrentNote()
                yield Button("Select Device")
            with TabPane("Process Screen"):
                with VerticalScroll(id="process-container"):
                    for config in PROCESS_CONFIGS:
                        yield ProcessWindow(config)
            with TabPane("Piano Key Frequencies"):
                yield PianoFrequencies()

        yield Footer()

    def action_screen_devices(self) -> None:
        self.app.push_screen(screen="devices")

    def action_screen_frequencies(self) -> None:
        self.app.push_screen(screen="frequencies")

    def action_screen_range_presets(self) -> None:
        self.app.push_screen(screen="range")
