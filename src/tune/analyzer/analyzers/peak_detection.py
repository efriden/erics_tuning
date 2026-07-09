from .base import AbstractAnalyzer

from tune.shared.types.settings_specs import AudioSettings
from tune.shared.types.piano_string import PianoString

from time import sleep

import logging

logger = logging.getLogger(__name__)


class PeakDetection(AbstractAnalyzer):
    """
    Use the fft from the fft analyzer and perform PeakDetection on it.

    Listen to transponder for peakdetection parameters.

    Publish on the 'peaks' topic, and/or send to analyzer that creates and sends
    a PianoString object.
    """

    def __init__(self, audio_settings: AudioSettings) -> None:
        logger.debug(f"__init__ audio_settings={audio_settings!r}")
        super().__init__(audio_settings)
        self.topic = "piano_string"

    def _run(
        self,
    ) -> None:
        while not self.shutdown_flag.is_set():
            sleep(self.sleep_time)
            fft = self._getter("fft")
            if fft is None:
                continue

            # todo: get these values from interface.
            try:
                piano_string = PianoString.from_fft(
                    fft, prominence=0.05, height=0.1, distance=10
                )
            except Exception as e:
                logger.exception(e)
                continue

            if piano_string.valid:
                self._putter(piano_string.pack())
