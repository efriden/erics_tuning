from textual.widgets import Button, Label, Header, Footer
from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll


class LauncherScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with Horizontal(id="process-container"):
            with VerticalScroll(classes="process-scroll"):
                yield Label("Analyzer", classes="process-label")
                yield Button("Launch analyzer", id="analyzer-button")
            with VerticalScroll(classes="process-scroll"):
                yield Label("Visualizer", classes="process-label")
                yield Button("Launch visualizer", id="visualizer-button")
            with VerticalScroll(classes="process-scroll"):
                yield Label("Broker", classes="process-label")
                yield Button("Launch broker", id="broker-button")

    def on_button_pressed(self, message: Button.Pressed) -> None:
        button: Button = message.button
        match button.id:
            case 'analyzer-button':
                
