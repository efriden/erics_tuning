from enum import IntEnum
from textual.widgets import Label
from textual.reactive import reactive
from rich.text import Text
from rich.style import Style


class Status(IntEnum):
    OFF = 0
    LAUNCHING = 1
    RUNNING = 2
    FAILED = 3


class StatusLight(Label):
    status = reactive(Status.OFF)

    STYLES: list[Style] = [
        Style(color="bright_black"),
        Style(color="yellow"),
        Style(color="green"),
        Style(color="red"),
    ]

    def on_mount(self) -> None:
        self.content = Text("◉", style=self._status_to_style(Status.OFF))

    def watch_status(self, old_status: Status, new_status: Status) -> None:
        self.content = Text("◉", style=self._status_to_style(new_status))

    def _status_to_style(self, status: Status) -> Style:
        return self.STYLES[status]
