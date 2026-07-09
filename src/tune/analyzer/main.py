"""Audio analyzer"""

import numpy as np
import numpy.typing as npt
from threading import Event

from tune.shared.audio.stream_handler import StreamHandler
from tune.shared.transponder.transponder import Transponder
from tune.shared.util.setup_logging import setup_logging
from tune.shared.types.settings_specs import AudioSettings
from tune.shared.types.array_buffer import ArrayBuffer

from tune.analyzer.analyzers.base import AbstractAnalyzer
from tune.analyzer.analyzers.normalized_fft import NormalizedFFT
from tune.analyzer.analyzers.peak_detection import PeakDetection

from logging import Logger, getLogger

logger: Logger = getLogger(__name__)


class AnalyzerHandler:
    """
    A handler for a set of analyzer objects.

    Each analyzer object does its own set of calculations, in its own thread.

    This handler manages datastreams in and out of these analyzers, and holds
    a transponder object for communication with the rest of the application.
    """

    _stream: StreamHandler
    _transponder: Transponder
    _analyzers: list[AbstractAnalyzer]
    _shutdown_flag: Event
    _internal_buffers: dict[str, ArrayBuffer]

    def __init__(self, stream: StreamHandler | None = None) -> None:
        logger.debug(f"__init__ stream={stream!r}")
        self._shutdown_flag = Event()
        self._stream: StreamHandler = stream if stream else StreamHandler()
        pubs: list[str] = ["fft", "piano_string"]
        subs: list[str] = ["peak_parameters"]
        pubsubs: list[str] = []
        self._transponder: Transponder = Transponder(pubs, subs, pubsubs)
        self._analyzers = []
        self._internal_buffers = {}

    def add_analyzer(self, analyzer: AbstractAnalyzer) -> None:
        logger.debug(f"add_analyzer analyzer={analyzer!r}")
        self._analyzers.append(analyzer)
        analyzer.register_in(self.get)
        analyzer.register_out(self.put)

    def add_internal_buffer(self, topic: str) -> None:
        self._internal_buffers[topic] = ArrayBuffer()

    def start(self) -> None:
        logger.debug("start")
        logger.debug("TuneAnalyzer object starting TuneStream object.")
        self._stream.start()
        logger.debug("TuneAnalyzer object starting Transponder object.")
        self._transponder.start()
        logger.debug("TuneAnalyzer object starting subanalyzers.")
        for analyzer in self._analyzers:
            analyzer.start()

    def stop(self) -> None:
        logger.debug("stop")
        self._shutdown_flag.set()
        for analyzer in self._analyzers:
            analyzer.stop()
        self._transponder.stop()
        self._stream.stop()

    def wait(self) -> None:
        logger.debug("wait")
        self._shutdown_flag.wait()

    def get(self, topic: str) -> npt.NDArray[np.float32] | None:
        if topic == "audio_chunk":
            return self.get_chunk()
        internal_buffer: ArrayBuffer | None = self._internal_buffers.get(topic)
        if internal_buffer is not None:
            data = internal_buffer.read()
            return data
        raise RuntimeError("Bad topic in analyzer.")

    def get_chunk(self) -> npt.NDArray[np.float32]:
        return self._stream.get_chunk()

    def put(self, topic, payload) -> None:
        internal_buffer: ArrayBuffer | None = self._internal_buffers.get(topic)
        if internal_buffer is not None:
            internal_buffer.update(payload)
        self._transponder.put(topic, payload)

    @property
    def audio_settings(self) -> AudioSettings:
        return self._stream.settings


def main() -> None:
    setup_logging(root_level=10)
    logger.info("Starting TuneAnalyzer app")

    logger.debug("Creating AnalyzerHandler object.")
    manager = AnalyzerHandler()

    logger.debug("Creating Analyzer objects.")
    manager.add_analyzer(NormalizedFFT(manager.audio_settings))
    manager.add_analyzer(PeakDetection(manager.audio_settings))

    logger.debug("Creating internal buffers.")
    manager.add_internal_buffer("fft")

    logger.debug("Starting TuneAnalyzer object (will also start pyaudio stream)")
    try:
        manager.start()
        manager.wait()
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop()

    logger.info("Shutting down analyzer app.")
    manager.stop()


if __name__ == "__main__":
    main()
