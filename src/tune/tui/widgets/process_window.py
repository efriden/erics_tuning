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
        width: 8;
    }
    """
    process_name: str
    process_runner: ProcessRunner

    def __init__(self, config: ProcessConfig):
        super().__init__(id=f"{config.name}-window")
        self.process_name: str = config.name
        if config.use_async:
            self.process_runner = AsyncProcessRunner(config)
        else:
            self.process_runner = SyncProcessRunner(config)
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
        self.query_one(StatusLight).status = status
        if status == Status.RUNNING:
            button = self.query_one(Button)
            button.variant = "error"
            button.label = "Stop"
        if status == Status.OFF:
            button = self.query_one(Button)
            button.variant = "success"
            button.label = "Launch"

    def start(self) -> None:
        self._light(Status.LAUNCHING)
        start_func = self.process_runner.start
        if iscoroutinefunction(start_func):
            self.run_worker(start_func(), exclusive=True, name="starter")
        else:
            try:
                start_func()
                self._light(Status.RUNNING)
            except Exception as e:
                logger.error(
                    f"Exception when starting process {self.process_name}: {e}"
                )
                self._light(Status.FAILED)

    def stop(self) -> None:
        stop_func = self.process_runner.stop
        if iscoroutinefunction(stop_func):
            self.run_worker(stop_func(), exclusive=True, name="stopper")
            return
        try:
            stop_func()
            self._light(Status.OFF)
        except Exception as e:
            logger.error(f"Exception when stopping process {self.process_name}: {e}")
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
                self.start()
            case "Stop":
                self.stop()
