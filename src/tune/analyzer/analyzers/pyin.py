from tune.analyzer.analyzers.base import AbstractAnalyzer
from tune.shared.util.config_loader import AudioSettings
from time import sleep

from librosa import pyin
import numpy as np

from tune.shared.types.pitch import Pitch

from logging import getLogger

logger = getLogger(__name__)

# todo: move this to config.yaml
PYIN_HOPS_PER_CHUNK = 4


class PitchDetection(AbstractAnalyzer):
    def __init__(self, audio_settings: AudioSettings) -> None:
        super().__init__(audio_settings)
        self.topic = "pitch"

    def _run(self) -> None:
        while not self.shutdown_flag.is_set():
            sleep(self.sleep_time)
            audio_chunk: np.ndarray = self._getter()
            pitch: Pitch | None = Pitch.from_pyin(
                pyin(
                    y=audio_chunk,
                    fmin=100,
                    fmax=4186,
                    sr=self.audio_settings.samplerate,
                    frame_length=self.audio_settings.buffer_size,
                    hop_length=round(
                        self.audio_settings.buffer_size / PYIN_HOPS_PER_CHUNK
                    ),
                )
            )
            if pitch is None:
                continue
            self._putter(pitch.pack())
