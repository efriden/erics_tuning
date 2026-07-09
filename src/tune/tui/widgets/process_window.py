from __future__ import annotations
from textual.message import Message
from rich.text import Text
from textual.worker import Worker, WorkerState
from tune.tui.workers.process_runner import (
    ProcessRunner,
    ProcessConfig,
    AsyncProcessRunner,
    SyncProcessRunner,
)
from tune.tui.widgets.status_light import StatusLight, Status
from tune.tui.workers.log_reader import tail_log
from textual.app import ComposeResult
from textual.containers import VerticalScroll, HorizontalGroup, Horizontal
from textual.widgets import RichLog, Label, Static, Button

from tune.tui.workers.log_reader import LogLine

from inspect import iscoroutinefunction

from logging import getLogger

logger = getLogger(__name__)


class RegisterProcess(Message):
    process: ProcessWindow
    action: str

    def __init__(self, process: ProcessWindow, action: str) -> None:
        super().__init__()
        self.process = process
        self.action = action


class ProcessWindow(Static):
    DEFAULT_CSS = """
    ProcessWindow {
        border: solid $accent;
        height: 1fr;
    }
    .log {
        height: 1fr;
    }
    .launcher {
        height: 100%;
        width: 4;
    }
    """
    process_name: str
    process_runner: ProcessRunner

    def __init__(self, config: ProcessConfig):
        """
        This right now pulls double duty - it acts as a wrapper for a process runner,
        and is a textual widget with a log view.
        Those concerns should probably be separated.

        config:

        """
        super().__init__(id=f"{config.name}-window")
        self.process_name: str = config.name
        if config.use_async:
            self.process_runner = AsyncProcessRunner(config, self.app)
        else:
            self.process_runner = SyncProcessRunner(config, self.app)
        self.run_worker(tail_log(self.app))

    def compose(self) -> ComposeResult:
        with HorizontalGroup():
            yield StatusLight(id=f"{self.process_name}-light")
            yield Label(Text(self.process_name.title(), style="bold $primary"))
        with Horizontal():
            yield Button(
                label="Launch",
                id=f"{self.process_name}-button",
                classes="launcher",
                variant="success",
            )
            with VerticalScroll():
                yield RichLog(markup=True, classes="log")

    def add_log_line(self, log_line: LogLine) -> None:
        log: RichLog = self.query_one(".log", RichLog)
        log.write(log_line.rich_line)

    def _light(self, status: Status) -> None:
        if not self.is_attached:
            return
        self.query_one(StatusLight).status = status
        if status == Status.RUNNING:
            button = self.query_one(Button)
            button.variant = "error"
            button.label = "Stop"
        if status == Status.OFF:
            button = self.query_one(Button)
            button.variant = "success"
            button.label = "Launch"

    async def start(self) -> None:
        self._light(Status.LAUNCHING)
        start_func = self.process_runner.start
        if iscoroutinefunction(start_func):
            try:
                await start_func()
                self._light(Status.RUNNING)
                self.post_message(RegisterProcess(process=self, action="register"))
            except Exception as e:
                logger.error(
                    f"Exception when starting process {self.process_name}: {e}"
                )
                self._light(Status.FAILED)
        else:
            try:
                start_func()
                self._light(Status.RUNNING)
                self.post_message(RegisterProcess(process=self, action="register"))
            except Exception as e:
                logger.error(
                    f"Exception when starting process {self.process_name}: {e}"
                )
                self._light(Status.FAILED)

    async def stop(self) -> None:
        """
        Stop the bound process.
        This is async so it can be awaited when TUI shuts down.

        """
        stop_func = self.process_runner.stop
        if iscoroutinefunction(stop_func):
            try:
                await stop_func()
                self._light(Status.OFF)
                self.post_message(RegisterProcess(process=self, action="unregister"))
            except Exception as e:
                logger.error(
                    f"Exception when stopping process {self.process_name}: {e}"
                )
                self._light(Status.FAILED)
        else:
            try:
                stop_func()
                self._light(Status.OFF)
                self.post_message(RegisterProcess(process=self, action="unregister"))
            except Exception as e:
                logger.error(
                    f"Exception when stopping process {self.process_name}: {e}"
                )
                self._light(Status.FAILED)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name == "starter" or event.worker.name == "stopper":
            match event.state:
                case WorkerState.ERROR:
                    self._light(Status.FAILED)
                    return
                case WorkerState.SUCCESS:
                    if event.worker.name == "starter":
                        self._light(Status.RUNNING)
                        return
                    self._light(Status.OFF)
                    return
                case _:
                    return

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.label:
            case "Launch":
                self.run_worker(self.start())
            case "Stop":
                self.run_worker(self.stop())
