"""Audio analyzer handler. Often -- but not always -- a singleton. Holds a set of analyzers, an audio stream, a transponder and handles threads."""

import numpy as np
from numpy.typing import NDArray
from threading import Event

from tune.shared.audio.stream_handler import StreamHandler
from tune.shared.transponder.transponder import Transponder
from tune.shared.transponder.packet import AbstractPacket
from tune.shared.util.output_manager import output_manager as out
from tune.analyzer.analyzers.base import AbstractAnalyzer
from tune.analyzer.analyzers.normalized_fft import NormalizedFFT


class AnalyzerHandler:
    _stream: StreamHandler
    _transponder: Transponder
    _analyzers: list[AbstractAnalyzer]
    _shutdown_flag: Event

    def __init__(self, stream: StreamHandler | None = None) -> None:
        out.debug(f"__init__ stream={stream!r}")
        self._shutdown_flag = Event()
        self._stream: StreamHandler = stream if stream else StreamHandler()
        self._transponder: Transponder = Transponder(pubs=["fft"], subs=[])
        self._analyzers: list[AbstractAnalyzer] = []

    def add_analyzer(self, analyzer: AbstractAnalyzer) -> None:
        out.debug(f"add_analyzer analyzer={analyzer!r}")
        self._analyzers.append(analyzer)
        analyzer.register_in(self._stream.get_chunk)
        analyzer.register_out(self.put)

    def start(self) -> None:
        out.debug("start")
        out.debug("TuneAnalyzer object starting TuneStream object.")
        self._stream.start()
        out.debug("TuneAnalyzer object starting Transponder object.")
        self._transponder.start()
        out.debug("TuneAnalyzer object starting subanalyzers.")
        for analyzer in self._analyzers:
            analyzer.start()

    def stop(self) -> None:
        out.debug("stop")
        self._shutdown_flag.set()
        for analyzer in self._analyzers:
            analyzer.stop()
        self._transponder.stop()
        self._stream.stop()

    def wait(self) -> None:
        out.debug("wait")
        self._shutdown_flag.wait()

    def put(self, packet: AbstractPacket) -> None:
        self._transponder.put(packet)


def main() -> None:
    out.info("Starting Analyzer app")

    out.debug("Creating AnalyzerHandler object.")
    analyzer_handler = AnalyzerHandler()

    out.debug("Creating subanalyzer objects.")
    analyzer_handler.add_analyzer(analyzer=NormalizedFFT())

    out.debug("Starting TuneAnalyzer object (will also start pyaudio stream)")
    try:
        analyzer_handler.start()
        analyzer_handler.wait()
    except KeyboardInterrupt:
        pass
    finally:
        analyzer_handler.stop()

    out.info("Shutting down analyzer app.")
    analyzer_handler.stop()


if __name__ == "__main__":
    main()
