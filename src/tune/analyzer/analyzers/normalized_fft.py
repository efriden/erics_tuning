from .base import AbstractAnalyzer
import numpy as np
from scipy.fft import fft, fftfreq
from time import sleep

from tune.shared.util.config_loader import AudioSettings

from logging import getLogger

logger = getLogger(__name__)


class NormalizedFFT(AbstractAnalyzer):
    def __init__(self, audio_settings: AudioSettings) -> None:
        logger.debug(f"__init__ audio_settings={audio_settings!r}")
        super().__init__(audio_settings)
        self.topic = "fft"

    def _run(
        self,
    ) -> None:
        logger.debug("_run")
        while not self.shutdown_flag.is_set():
            sleep(self.sleep_time)
            audio_chunk: np.ndarray | None = self._getter("audio_chunk")
            if audio_chunk is None:
                continue
            chunk_size: int = audio_chunk.size
            if chunk_size == 0:
                logger.warning("received empty audio chunk")
                continue
            if chunk_size != self.audio_settings.buffer_size:
                logger.warning(
                    f"chunk_size {chunk_size} not equal to settings buffer size: {self.audio_settings.buffer_size}"
                )

            # applying a hanning window trades away some frequency resolution for reduced leakage.
            # definitely worth it for visualization, but keep in mind when processing further.
            hanning_window: np.ndarray = np.hanning(chunk_size)
            hanninged_audio: np.ndarray = audio_chunk * hanning_window
            complex_transform: np.ndarray = fft(hanninged_audio)
            frequency_bins: np.ndarray = fftfreq(
                chunk_size, 1 / self.audio_settings.samplerate
            )
            nyquist_frequency: int = chunk_size // 2
            # every complex fft value up to the nyquist_frequency is a negative mirror, so we ignore those.
            # (unless we somehow recorded and passed complex-valued audio, but that might be a bigger issue...)
            positive_frequency_bins: np.ndarray = frequency_bins[:nyquist_frequency]
            positive_complex_transform: np.ndarray = complex_transform[
                :nyquist_frequency
            ]
            real_transform = np.abs(positive_complex_transform)
            # normalize using the hanning sum
            normalized_real_transform = real_transform / hanning_window.sum()
            full_analysis: np.ndarray = np.stack(
                [
                    positive_frequency_bins.astype(np.float32),
                    normalized_real_transform.astype(np.float32),
                ]
            )
            self._putter(full_analysis)
