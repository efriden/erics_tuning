import pyaudio
from typing import Callable

from tune.shared.util.config_loader import AudioSettings
from tune.shared.audio.device_info import DeviceInfo

from logging import getLogger

logger = getLogger(__name__)


class PyAudioHandler:
    """
    Singleton manager for the pyaudio instance.
    """

    _instance: pyaudio.PyAudio | None = None
    _devices: list[DeviceInfo] = []
    _default_device_index: int

    @classmethod
    def get_instance(cls) -> pyaudio.PyAudio:
        """Getter that ensures the pyaudio instance remains a singleton.

        Returns:
            pyaudio.PyAudio: The current pyaudio instance

        """
        if cls._instance:
            logger.debug("PyAudioHandler returns an existing pyaudio instance")
            return cls._instance
        logger.debug("Setting up a new pyaudio instance")
        try:
            cls._instance = pyaudio.PyAudio()
            cls._enumerate_devices()
        except Exception as e:
            raise RuntimeError(f"Failure to initialize pyaudio. e: {e}")
        return cls._instance

    @classmethod
    def get_stream(
        cls,
        settings: AudioSettings,
        callback: Callable | None = None,
        device: DeviceInfo | None = None,
    ) -> pyaudio.Stream:
        """
        Classmethod that initializes and returns a pyaudio stream.
        If a callback method is supplied, the stream will be set up as non-blocking and threadsafe.
        If it is not, the stream will be blocking and stopping at every stream.read().
        """
        logger.debug(
            f"Streamfactory is setting up a new {'non-blocking' if callback else 'blocking'} pyaudiostream"
        )

        p: pyaudio.PyAudio = cls.get_instance()

        device_system_index: int = (
            device.system_index if device else cls.get_default_device().system_index
        )

        try:
            stream: pyaudio.Stream = p.open(
                input_device_index=device_system_index,
                format=settings.pyaudio_format,
                channels=settings.n_channels,
                rate=settings.samplerate,
                input=True,
                frames_per_buffer=settings.buffer_size,
                stream_callback=callback,
            )
        except Exception as e:
            logger.error(f"PyAudio failed to create a stream. e: {e}")
            raise RuntimeError(f"PyAudio failed to create a stream. e: {e}")

        return stream

    @classmethod
    def terminate(cls) -> None:
        logger.debug("Terminating PyAudio instance.")
        if cls._instance:
            cls._instance.terminate()
            return
        logger.warning("PyAudioHandler.terminate called with no open pyaudio instance")

    @classmethod
    def restart(cls) -> None:
        logger.debug("Restarting Pyaudio instance")
        if cls._instance:
            cls.terminate()
            cls._instance = pyaudio.PyAudio()
            return
        logger.warning("PyAudioHandler.restart called with no open pyaudio instance")

    @classmethod
    def _enumerate_devices(cls) -> None:
        p: pyaudio.PyAudio = cls.get_instance()
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
        cls._devices = devices
        logger.info(f"Enumerated {device_count} devices.")

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
        NOT the index used by the system or the PyAudio instance.

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
