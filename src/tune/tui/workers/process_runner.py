from dataclasses import dataclass
import asyncio


@dataclass
class ProcessConfig:
    command: list[str]


class ProcessRunner:
    def __init__(self, config: ProcessConfig) -> None:
        pass

    def terminate(self) -> None:
        pass

    async def _run(self) -> None:
        pass
