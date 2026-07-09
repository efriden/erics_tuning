from typing import Callable
from pyaudio import PyAudio, Stream, paFloat32

from tune.shared.util.config import config, AudioSettings
from tune.shared.util.output_manager import output_manager as out
from tune.shared.audio.device_info import DeviceInfo


class PyAudioHandler:
    """
    Singleton manager for the pyaudio instance.
    """

    _instance: PyAudio | None = None
    _devices: list[DeviceInfo] = []
    _default_device_index: int

    @classmethod
    def get_instance(cls) -> PyAudio:
        """Getter that ensures the pyaudio instance remains a singleton.

        Returns:
            PyAudio: The current pyaudio instance

        """
        if cls._instance is not None:
            out.debug("PyAudioHandler returns an existing pyaudio instance")
            return cls._instance
        out.debug("Setting up a new pyaudio instance")
        try:
            cls._instance = PyAudio()
            cls._enumerate_devices()
        except Exception as e:
            raise RuntimeError(f"Failure to initialize pyaudio. e: {e}")
        return cls._instance

    @classmethod
    def get_stream(
        cls,
        callback: Callable | None = None,
        device: DeviceInfo | None = None,
        settings: AudioSettings = config.audio_settings,
        format: int = paFloat32,
    ) -> Stream:
        """
        Classmethod that initializes and returns a pyaudio stream.
        If a callback method is supplied, the stream will be set up as non-blocking and threadsafe.
        If it is not, the stream will be blocking and stopping at every stream.read().
        """
        out.debug(
            f"Streamfactory is setting up a new {'non-blocking' if callback else 'blocking'} pyaudiostream"
        )

        p: PyAudio = cls.get_instance()

        device_system_index: int = (
            device.system_index if device else cls.get_default_device().system_index
        )

        try:
            stream: Stream = p.open(
                input_device_index=device_system_index,
                format=format,
                channels=settings.channels,
                rate=settings.sample_rate,
                input=True,
                frames_per_buffer=settings.buffer_size,
                stream_callback=callback,
            )
        except Exception as e:
            out.error(f"PyAudio failed to create a stream. e: {e}")
            raise RuntimeError(f"PyAudio failed to create a stream. e: {e}")

        return stream

    @classmethod
    def terminate(cls) -> None:
        out.debug("Terminating PyAudio instance.")
        if cls._instance:
            cls._instance.terminate()
            return
        out.warning("PyAudioHandler.terminate called with no open pyaudio instance")

    @classmethod
    def restart(cls) -> None:
        out.debug("Restarting Pyaudio instance")
        if cls._instance:
            cls.terminate()
            cls._instance = PyAudio()
            return
        out.warning("PyAudioHandler.restart called with no open pyaudio instance")

    @classmethod
    def _enumerate_devices(cls) -> None:
        p: PyAudio = cls.get_instance()
        device_count: int = p.get_device_count()
        if device_count < 1:
            raise RuntimeError("pyaudio found no audio devices.")
        devices: list[DeviceInfo] = []
        default_device_name: str = p.get_default_input_device_info()["name"]
        for device_index in range(device_count):
            info: dict = p.get_device_info_by_index(device_index)
            device_info: DeviceInfo = DeviceInfo.from_pyaudio(info)
            if device_info.max_input_channels <= 0:
                continue
            devices.append(device_info)
            if default_device_name == device_info.name:
                cls._default_device_index = device_index
        cls._devices: list[DeviceInfo] = devices
        out.info(f"Enumerated {device_count} devices.")

    @classmethod
    def get_default_device(cls) -> DeviceInfo:
        cls.get_instance()
        device: DeviceInfo = cls._devices[cls._default_device_index]
        return device

    @classmethod
    def get_devices(cls) -> list[DeviceInfo]:
        cls.get_instance()
        return cls._devices

    @classmethod
    def get_device_by_index(cls, i: int) -> DeviceInfo:
        """Note that this is index in the internal list of this PyAudioHandler
        NOT the index used by the system, PyAudio instance or the C layer.

        i: index

        Returns:
            DeviceInfo: Device at that index

        """
        cls.get_instance()
        return cls._devices[i]

    @classmethod
    def get_index_of_device(cls, device: DeviceInfo) -> int:
        cls.get_instance()
        return cls._devices.index(device)
