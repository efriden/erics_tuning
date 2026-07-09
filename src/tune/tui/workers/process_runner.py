from typing import Awaitable
from abc import ABC, abstractmethod
from dataclasses import dataclass
import asyncio
import subprocess

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

    def __init__(self, config: ProcessConfig) -> None:
        self.command = config.command
        self.process = None
        self.name = config.name

    @abstractmethod
    def start(self) -> None | Awaitable[None]: ...

    @abstractmethod
    def stop(self) -> None | Awaitable[None]: ...


class AsyncProcessRunner(ProcessRunner):
    process: asyncio.subprocess.Process | None

    async def start(self) -> None:
        if self.process:
            logger.warning(f"{self.name} process started when already running")
            return
        logger.info(
            f"Starting process {self.name} ({' '.join(self.command)} asynchronously."
        )

        self.process = await asyncio.create_subprocess_exec(*self.command)

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
            self.process = None


class SyncProcessRunner(ProcessRunner):
    process: subprocess.Popen | None

    def start(self) -> None:
        if self.process and self.process.poll() is None:  # if started and not stopped
            logger.warning(f"{self.name} process started when already running")
            return
        logger.info(f"Starting process {self.name} ({' '.join(self.command)}.")

        self.process = subprocess.Popen(self.command)

    def stop(self) -> None:
        if self.process is None:
            logger.warning(f"{self.name} process stopped when not running")
            return
        self.process.terminate()
        self.process = None
