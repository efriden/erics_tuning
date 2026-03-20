from textual.containers import Vertical
from textual.widgets import Button, Placeholder, Header, Footer
from textual.screen import Screen
from textual.app import ComposeResult


class MainScreen(Screen):
    BINDINGS: list[tuple[str, str, str]] = [
        ("a", "screen_devices", "Audio Devices"),
        ("f", "screen_frequencies", "List Full Piano Range"),
        ("r", "screen_range_presets", "Set Frequency Range"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()

        with Vertical():
            yield Button()

        yield Footer()

    def action_screen_devices(self) -> None:
        self.app.push_screen(screen="devices")

    def action_screen_frequencies(self) -> None:
        self.app.push_screen(screen="frequencies")

    def action_screen_range_presets(self) -> None:
        self.app.push_screen(screen="range")
