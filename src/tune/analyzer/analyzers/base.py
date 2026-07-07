from numpy.typing import NDArray
from typing import Callable
from abc import ABC, abstractmethod
from threading import Thread, Event

from tune.shared.util.output_manager import output_manager as out
from tune.shared.util.config import config, AudioSettings
from tune.shared.transponder.packet import AbstractPacket


class AbstractAnalyzer(ABC):
    packet: AbstractPacket
    _putter: Callable[[AbstractPacket], None]
    _getter: Callable[[], AbstractPacket | NDArray]
    thread: Thread
    shutdown_flag: Event
    sleep_time: float
    audio_settings: AudioSettings

    def __init__(
        self,
        audio_settings: AudioSettings | None = None,
        sleep_time: float | None = None,
    ) -> None:
        self.sleep_time: float = (
            sleep_time
            if sleep_time is not None
            else config.analyzer_defaults.sleep_seconds
        )
        self.audio_settings: AudioSettings = (
            audio_settings if audio_settings is not None else config.audio_settings
        )
        self.shutdown_flag = Event()

    def register_out(self, f: Callable[[AbstractPacket], None]) -> None:
        out.debug(f"register_out f={f!r}")
        self._putter = f

    def register_in(self, f: Callable[[], AbstractPacket | NDArray]) -> None:
        out.debug(f"register_in f={f!r}")
        self._getter = f

    def start(self) -> None:
        out.debug("start")
        self.thread = Thread(
            target=self._run,
            name=f"{self.packet.topic}-analyzer",
        )

        self.thread.start()

    def stop(self) -> None:
        out.debug("stop")
        self.shutdown_flag.set()

        self.thread.join()

    @abstractmethod
    def _run(
        self,
    ) -> None:
        pass
