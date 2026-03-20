from tune.shared.util.config_loader import AudioSettings, get_audio_settings
from tune.shared.audio.stream_buffer import StreamBuffer
from tune.shared.audio.pyaudio_handler import PyAudioHandler
from tune.shared.audio.device_info import DeviceInfo
from typing import Any


import pyaudio
import numpy as np
import numpy.typing as npt

from logging import getLogger

logger = getLogger(__name__)


class StreamHandler:
    """
    Wrapper for a non-blocking input-only pyaudio stream.

    Also comes with a threadsafe and non-destructive buffer.
    """

    device: DeviceInfo
    settings: AudioSettings
    _stream: pyaudio.Stream
    _stream_buffer: StreamBuffer

    def __init__(
        self, settings: AudioSettings | None = None, device: DeviceInfo | None = None
    ) -> None:
        logger.debug(f"__init__ settings={settings!r}, device={device!r}")
        self.settings: AudioSettings = settings if settings else get_audio_settings()
        logger.debug(f"AudioSettings: {self.settings}")
        self.device: DeviceInfo = (
            device if device else PyAudioHandler.get_default_device()
        )
        self._stream: pyaudio.Stream = PyAudioHandler.get_stream(
            self.settings, callback=self._callback
        )
        self._stream_buffer: StreamBuffer = StreamBuffer()
        logger.info("TuneStream initialized")

    def start(self) -> None:
        logger.debug("start")
        self._stream.start_stream()

    def stop(self) -> None:
        logger.debug("stop")
        self._stream.stop_stream()
        self._stream.close()

    def swap_device(self, new_device: DeviceInfo) -> None:
        logger.debug(f"swap_device new_device={new_device!r}")
        self.stop()
        new_stream: pyaudio.Stream = PyAudioHandler.get_stream(
            self.settings, callback=self._callback, device=new_device
        )
        self._stream = new_stream
        self.device = new_device
        self.start()

    def get_chunk(self) -> npt.NDArray[np.float32]:
        """Threadsafe getter for audio chunk.

        Returns:
            npt.NDArray[np.float32]: The latest chunk of audio_data. The data is not deleted, so another thread calling this function might get the same chunk.

        """
        logger.debug("get_chunk")
        chunk = self._stream_buffer.read()
        if chunk is None:
            logger.warning("empty stream_buffer")
            return np.array([])
        return chunk

    def get_level(self) -> int:
        chunk = self.get_chunk()
        if chunk.size == 0:
            return 0
        root_mean_square: float = np.sqrt(np.mean(chunk**2))
        if root_mean_square < 1e-10:
            return 0
        decibel_from_full_scale: float = 20 * np.log10(root_mean_square)
        level_f: float = (decibel_from_full_scale + 60) / 60 * 100
        level: int = int(np.clip(level_f, 0, 100))
        logger.debug(level)
        return level

    def _callback(self, in_data, frame_count, time_info, status) -> tuple[Any, Any]:
        audio_data: npt.NDArray[np.float32] = self._convert(
            in_data, self.settings.pyaudio_format
        )

        self._stream_buffer.update(audio_data)

        # in input-only streams, the first value of return tuple is ignored
        return (None, pyaudio.paContinue)

    def _convert(self, in_data: bytes, in_format: int) -> npt.NDArray[np.float32]:
        """
        converts bytes in whatever format used by pyaudio (from user settings) into a normalized float32 numpy array.
        """
        FORMAT_TO_DTYPE_MAP: dict[int, type[np.generic]] = {
            pyaudio.paFloat32: np.float32,
            pyaudio.paInt32: np.int32,
            pyaudio.paInt16: np.int16,
        }

        DIVISORS: dict[int, float] = {
            pyaudio.paFloat32: 1.0,
            pyaudio.paInt32: 2147483648.0,
            pyaudio.paInt16: 32768.0,
        }

        if in_format not in FORMAT_TO_DTYPE_MAP:
            raise RuntimeError(f"Unknown pyaudio format: {in_format}")

        np_format: type[np.generic] = FORMAT_TO_DTYPE_MAP[in_format]
        divisor: float = DIVISORS[in_format]

        raw_audio: npt.NDArray[np.generic] = np.frombuffer(in_data, dtype=np_format)
        converted_audio: npt.NDArray[np.float32] = raw_audio.astype(np.float32)
        normalized_audio: npt.NDArray[np.float32] = converted_audio / divisor

        max_val: float = float(normalized_audio.max())
        min_val: float = float(normalized_audio.min())

        if max_val > 1.01 or min_val < -1.01:
            raise RuntimeError(
                f"Audio normalization failed: min={min_val}, max={max_val}"
            )

        return normalized_audio
