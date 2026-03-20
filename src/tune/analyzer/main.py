"""Audio analyzer"""

import aubio
import numpy as np
import numpy.typing as npt
import time
from threading import Event

from tune.shared.audio.stream_handler import StreamHandler
from tune.shared.transponder.transponder import Transponder
from tune.shared.util.setup_logging import setup_logging, log_run_start

from tune.analyzer.analyzers.base import AbstractAnalyzer
from tune.analyzer.analyzers.normalized_fft import NormalizedFFT

from logging import Logger, getLogger

logger: Logger = getLogger(__name__)


class TuneAnalyzerHandler:
    _stream: StreamHandler
    _transponder: Transponder
    _analyzers: list[AbstractAnalyzer]
    _shutdown_flag: Event

    def __init__(self, stream: StreamHandler | None = None) -> None:
        logger.debug(f"__init__ stream={stream!r}")
        self._shutdown_flag = Event()
        self._stream: StreamHandler = stream if stream else StreamHandler()
        pubs: list[str] = ["fft"]
        subs: list[str] = []
        pubsubs: list[str] = ["string"]
        self._transponder: Transponder = Transponder(pubs, subs, pubsubs)
        self._analyzers = []

    def add_analyzer(self, analyzer: AbstractAnalyzer) -> None:
        logger.debug(f"add_analyzer analyzer={analyzer!r}")
        self._analyzers.append(analyzer)
        analyzer.register_in(self.get_chunk)
        analyzer.register_out(self.put)

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

    def get_chunk(self) -> npt.NDArray[np.float32]:
        return self._stream.get_chunk()

    def put(self, topic, payload) -> None:
        self._transponder.put(topic, payload)


def main() -> None:
    setup_logging(root_level=10)
    log_run_start()
    logger.info("Starting TuneAnalyzer app")

    logger.debug("Creating TuneAnalyzer object.")
    analyzer = TuneAnalyzerHandler()

    logger.debug("Creating Analyzer objects.")
    analyzer.add_analyzer(NormalizedFFT(analyzer._stream.settings))

    logger.debug("Starting TuneAnalyzer object (will also start pyaudio stream)")
    try:
        analyzer.start()
        analyzer.wait()
    except KeyboardInterrupt:
        pass
    finally:
        analyzer.stop()

    logger.info("Shutting down analyzer app.")
    analyzer.stop()


if __name__ == "__main__":
    main()
