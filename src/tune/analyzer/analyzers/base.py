from typing import Callable, Any
from abc import ABC, abstractmethod
import numpy as np
import numpy.typing as npt
from threading import Thread, Event

from logging import getLogger
from tune.shared.util.config_loader import AudioSettings


# todo: move to config.yaml
DEFAULT_ANALYZER_SLEEP_SECONDS: float = 0.02


logger = getLogger((__name__))


class AbstractAnalyzer(ABC):
    topic: str
    _putter: Callable[[npt.NDArray], None]
    _getter: Callable[[], npt.NDArray[np.float32]]
    thread: Thread
    shutdown_flag: Event
    sleep_time: float
    audio_settings: AudioSettings

    def __init__(self, audio_settings: AudioSettings) -> None:
        self.sleep_time = DEFAULT_ANALYZER_SLEEP_SECONDS
        self.shutdown_flag = Event()
        self.audio_settings = audio_settings

    def register_out(self, f: Callable[[str, Any], None]) -> None:
        logger.debug(f"register_out f={f!r}")
        self._putter = lambda o: f(self.topic, o)

    def register_in(self, f: Callable[[], npt.NDArray[np.float32]]) -> None:
        logger.debug(f"register_in f={f!r}")
        self._getter = f

    def start(self) -> None:
        logger.debug("start")
        self.thread = Thread(
            target=self._run,
            name=f"{self.topic}-analyzer",
        )

        self.thread.start()

    def stop(self) -> None:
        logger.debug("stop")
        self.shutdown_flag.set()

        self.thread.join()

    @abstractmethod
    def _run(
        self,
    ) -> None:
        pass
