from threading import Lock
import numpy as np
import numpy.typing as npt

from logging import getLogger

logger = getLogger(__name__)


class StreamBuffer:
    """
    Holds the latest chunk of data from a TuneStream in a threadsafe way.

    Reading is non-destructive, so readers always get the latest chunk of
    audio data.
    """

    _chunk: npt.NDArray[np.float32] | None
    _lock: Lock

    def __init__(self) -> None:
        logger.debug("__init__")
        self._chunk = None
        self._lock: Lock = Lock()

    def update(self, chunk: npt.NDArray[np.float32]) -> None:
        with self._lock:
            self._chunk: npt.NDArray[np.float32] = chunk

    def read(self) -> npt.NDArray[np.float32] | None:
        with self._lock:
            return self._chunk
