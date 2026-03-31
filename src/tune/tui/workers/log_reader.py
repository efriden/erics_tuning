import asyncio
from pathlib import Path
from textual.app import App
from textual.message import Message
from dataclasses import dataclass

from tune.shared.util.paths import LOG_PATH


@dataclass
class LogLine:
    timestamp: str
    level: str
    sender: str
    message: str

    def __init__(self, line: str):
        super().__init__()
        self.timestamp, self.level, self.sender, self.message = map(
            str.strip, line.split("|")
        )

    @property
    def rich_timestamp(self) -> str:
        return f"[dim]{self.timestamp.strip().split(' ')[-1]}[/]"

    @property
    def rich_level(self) -> str:
        color: str = {
            "DEBUG": "bright_black",
            "INFO": "white",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red",
        }.get(self.level, "white")

        return f"[{color}]{self.level}[/]"

    @property
    def rich_sender(self) -> str:
        return f"[bright_black]{self.sender}[/]"

    @property
    def rich_message(self) -> str:
        return f"{self.message}"

    @property
    def rich_line(self) -> str:
        return f"{self.rich_timestamp} {self.rich_level} ({self.rich_sender}): {self.message}"


class NewLogLine(Message):
    log_line: LogLine

    def __init__(self, line: str):
        super().__init__()
        self.log_line = LogLine(line)


async def tail_log(app: App, log_path: Path = LOG_PATH / "app.log"):
    with open(log_path, "r") as f:
        f.seek(0, 2)  # seek to end — don't replay old logs on startup
        while True:
            line = f.readline()
            if line:
                app.post_message(NewLogLine(line.strip()))
            else:
                await asyncio.sleep(0.3)
