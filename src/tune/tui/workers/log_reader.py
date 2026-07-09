import asyncio
from pathlib import Path
from textual.app import App
from textual.message import Message
from dataclasses import dataclass
from enum import IntEnum
from tune.shared.util.paths import LOG_PATH

import logging

logger = logging.getLogger(__name__)


@dataclass
class LogLine:
    timestamp: str
    level: str
    sender: str
    message: str

    def __init__(self, raw: str) -> None:
        super().__init__()
        self.timestamp, self.level, self.sender, self.message = self.preprocess(raw)

    def preprocess(self, raw: str) -> tuple[str, str, str, str]:
        split: list[str] = raw.split("|")
        stripped: list[str] = [string.strip() for string in split]
        if len(stripped) != 4:
            return ("---", "WARNING", "none", "FAILED TO PARSE LOG LINE")
        a, b, c, d = tuple(
            stripped
        )  # the shenanigans here is for typechecker enforcement of four elements.
        return a, b, c, d

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


async def tail_log(app: App, log_path: Path = LOG_PATH / "app.log") -> None:
    with open(log_path, "r") as f:
        f.seek(0, 2)  # seek to end — don't replay old logs on startup
        while True:
            line = f.readline()
            if line:
                app.post_message(NewLogLine(line.strip()))
            else:
                await asyncio.sleep(0.3)


class StreamType(IntEnum):
    STDOUT = 0
    STDERR = 1


async def pipe_stream_to_log(
    app: App, stream: asyncio.StreamReader, process_name: str, stream_type: StreamType
) -> None:
    async for line in stream:
        log_string: str = f"---|{'INFO' if stream_type == StreamType.STDOUT else 'ERROR'}|{process_name} (outputstream)|{line}"
        app.post_message(NewLogLine(log_string))
