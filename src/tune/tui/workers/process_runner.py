from textual.app import App
from typing import Awaitable
from abc import ABC, abstractmethod
from dataclasses import dataclass
import asyncio
import subprocess
import threading
from tune.tui.workers.log_reader import StreamType, pipe_stream_to_log
from logging import getLogger

logger = getLogger(__name__)


@dataclass
class ProcessConfig:
    command: list[str]
    name: str
    use_async: bool = False


class ProcessRunner(ABC):
    command: list[str]
    name: str
    process: asyncio.subprocess.Process | subprocess.Popen | None
    app: App

    def __init__(self, config: ProcessConfig, app: App) -> None:
        self.command = config.command
        self.process = None
        self.name = config.name
        self.app = app

    @abstractmethod
    def start(self) -> None | Awaitable[None]: ...

    @abstractmethod
    def stop(self) -> None | Awaitable[None]: ...


class AsyncProcessRunner(ProcessRunner):
    process: asyncio.subprocess.Process | None
    _log_tasks: list[asyncio.Task]

    def __init__(self, config: ProcessConfig, app: App) -> None:
        super().__init__(config, app)
        self._log_tasks = []

    async def start(self) -> None:
        if self.process:
            logger.warning(f"{self.name} process started when already running")
            return
        logger.info(
            f"Starting process {self.name} ({' '.join(self.command)}) asynchronously."
        )
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert self.process.stdout and self.process.stderr
        self._log_tasks = [
            asyncio.create_task(
                pipe_stream_to_log(
                    self.app, self.process.stdout, self.name, StreamType.STDOUT
                )
            ),
            asyncio.create_task(
                pipe_stream_to_log(
                    self.app, self.process.stderr, self.name, StreamType.STDERR
                )
            ),
        ]

    async def stop(self) -> None:
        if self.process is None:
            logger.warning(f"{self.name} process stopped when not running")
            return
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(f"{self.name} failed to terminate. Killing now.")
            self.process.kill()
        finally:
            for task in self._log_tasks:
                task.cancel()
            self._log_tasks = []
            self.process = None


class SyncProcessRunner(ProcessRunner):
    process: subprocess.Popen | None
    _log_threads: list[threading.Thread]

    def __init__(self, config: ProcessConfig, app: App) -> None:
        super().__init__(config, app)
        self._log_threads = []

    def _pipe_stream(self, stream, level: str) -> None:
        log = logger.info if level == "stdout" else logger.error
        for line in stream:
            log(f"[{self.name}] {line.decode().rstrip()}")

    def start(self) -> None:
        if self.process and self.process.poll() is None:
            logger.warning(f"{self.name} process started when already running")
            return
        logger.info(f"Starting process {self.name} ({' '.join(self.command)}).")
        self.process = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._log_threads = [
            threading.Thread(
                target=self._pipe_stream,
                args=(self.process.stdout, "stdout"),
                daemon=True,
            ),
            threading.Thread(
                target=self._pipe_stream,
                args=(self.process.stderr, "stderr"),
                daemon=True,
            ),
        ]
        for t in self._log_threads:
            t.start()

    def stop(self) -> None:
        if self.process is None:
            logger.warning(f"{self.name} process stopped when not running")
            return
        self.process.terminate()
        self.process = None
