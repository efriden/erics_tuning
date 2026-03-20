from __future__ import annotations
from dataclasses import dataclass


@dataclass
class DeviceInfo:
    """
    Represents a PyAudio audio device as a dataclass, constructed from the
    pyaudio standard dictionary.

    pyaudio values:
    Latency values are in seconds. 'low' latency is optimistic (best case),
    'high' latency is conservative (safe default for most use cases).
    Input/output channel counts of 0 indicate the device does not support
    that direction. Sample rate is the device default in Hz.

    index renamed to system_index to represent that this will not be used by
        the tune system.
    """

    system_index: int
    name: str
    host_api: int
    max_input_channels: int
    max_output_channels: int
    default_low_input_latency: float
    default_low_output_latency: float
    default_high_input_latency: float
    default_high_output_latency: float
    default_sample_rate: float
    struct_version: int

    @classmethod
    def from_pyaudio(cls, d: dict) -> DeviceInfo:
        """Create a DeviceInfo object from a pyaudio device dictionary.

        d: pyaudio device info as dictionary.

        Returns:
            DeviceInfo: the same info packaged into a DeviceInfo object.

        """
        return cls(
            system_index=d["index"],
            name=d["name"],
            host_api=d["hostApi"],
            max_input_channels=d["maxInputChannels"],
            max_output_channels=d["maxOutputChannels"],
            default_low_input_latency=d["defaultLowInputLatency"],
            default_low_output_latency=d["defaultLowOutputLatency"],
            default_high_input_latency=d["defaultHighInputLatency"],
            default_high_output_latency=d["defaultHighOutputLatency"],
            default_sample_rate=d["defaultSampleRate"],
            struct_version=d["structVersion"],
        )
