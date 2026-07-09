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
from tune.analyzer.analyzers.peak_detection import PeakDetection



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
        self._shutdown_flag = Event()
        self._stream: StreamHandler = stream if stream else StreamHandler()
        self._transponder: Transponder = Transponder(pubs=["fft"], subs=[])
        self._analyzers: list[AbstractAnalyzer] = []
        self._internal_buffers = {}

    def add_analyzer(self, analyzer: AbstractAnalyzer) -> None:
        out.debug(f"add_analyzer analyzer={analyzer!r}")
        self._analyzers.append(analyzer)
        analyzer.register_in(self.get)
        analyzer.register_out(self.put)

    def add_internal_buffer(self, topic: str) -> None:
        self._internal_buffers[topic] = ArrayBuffer()

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
    out.info("Starting Analyzer app")

    out.debug("Creating AnalyzerHandler object.")
    analyzer_handler = AnalyzerHandler()

    out.debug("Creating subanalyzer objects.")
    analyzer_handler.add_analyzer(analyzer=NormalizedFFT())

    manager.add_internal_buffer("fft")

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
