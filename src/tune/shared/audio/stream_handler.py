from tune.shared.util.config import config, AudioSettings
from tune.shared.util.output_manager import output_manager as out
from tune.shared.audio.stream_buffer import StreamBuffer
from tune.shared.audio.pyaudio_handler import PyAudioHandler
from tune.shared.audio.device_info import DeviceInfo
from typing import Any
from pyaudio import Stream, paContinue

import numpy as np
from numpy.typing import NDArray


class StreamHandler:
    """
    Wrapper for a non-blocking input-only pyaudio stream.

    Also comes with a threadsafe and non-destructive buffer.
    """

    device: DeviceInfo
    settings: AudioSettings
    _stream: Stream
    _stream_buffer: ArrayBuffer

    def __init__(
        self, settings: AudioSettings | None = None, device: DeviceInfo | None = None
    ) -> None:
        out.debug(f"__init__ settings={settings!r}, device={device!r}")
        self.settings: AudioSettings = settings if settings else config.audio_settings
        out.debug(f"AudioSettings: {self.settings}")
        self.device: DeviceInfo = (
            device if device else PyAudioHandler.get_default_device()
        )
        self._stream: Stream = PyAudioHandler.get_stream(callback=self._callback)
        self._stream_buffer: ArrayBuffer = ArrayBuffer()

    def start(self) -> None:
        out.debug("start")
        self._stream.start_stream()

    def stop(self) -> None:
        out.debug("stop")
        self._stream.stop_stream()
        self._stream.close()

    def swap_device(self, new_device: DeviceInfo) -> None:
        out.debug(f"swap_device new_device={new_device!r}")
        self.stop()
        new_stream: Stream = PyAudioHandler.get_stream(
            callback=self._callback, device=new_device
        )
        self._stream: Stream = new_stream
        self.device: DeviceInfo = new_device
        self.start()

    def get_chunk(self) -> NDArray[np.float32]:
        """Threadsafe getter for audio chunk.

        Returns:
            NDArray[np.float32]: The latest chunk of audio_data. The data is not deleted, so another thread calling this function might get the same chunk.

        """
        chunk: NDArray[np.float32] | None = self._stream_buffer.read()
        if chunk is None:
            out.warning("empty stream_buffer")
            return np.array([])
        return chunk

    def get_level(self) -> int:
        """
        Returns the current audio level as an int between 0 and 100,
        based on a logarithmic scale of the root mean square of the
        audio amplitude.
        """
        chunk: NDArray[np.float32] = self.get_chunk()
        if chunk.size == 0:
            return 0
        root_mean_square: float = np.sqrt(np.mean(chunk**2))
        if root_mean_square < 1e-10:
            return 0
        decibel_from_full_scale: float = 20 * np.log10(root_mean_square)
        level_f: float = (decibel_from_full_scale + 60) / 60 * 100
        level: int = int(np.clip(level_f, 0, 100))
        return level

    def _callback(self, in_data, frame_count, time_info, status) -> tuple[Any, Any]:
        """
        Callback function for the PyAudio instance. Weird typing is because of
        the limitations of interaction with the C layer.
        """
        chunk: NDArray[np.float32] = np.frombuffer(buffer=in_data, dtype=np.float32)

        max_val: float = float(chunk.max())
        min_val: float = float(chunk.min())

        if (
            max_val > 1.2 or min_val < -1.2
        ):  # Wide gap, because this happens surprisingly often.
            raise RuntimeError(
                f"Audio normalization failed: min={min_val}, max={max_val}"
            )

        self._stream_buffer.update(chunk)

        # in input-only streams, the first value of return tuple is ignored
        return (None, paContinue)
