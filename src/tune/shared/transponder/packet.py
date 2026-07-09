"""These are the packets that will be accepted by the transponder object.
Every object holds a channel_type, a topic string and a dict header as well
as pack and unpack methods.
"""

import msgpack
from abc import abstractmethod, ABC

from typing import Self, Any, ClassVar
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
from tune.shared.transponder.transponder import ChannelType


@dataclass
class AbstractPacket(ABC):
    _registry: ClassVar[dict[str, type["AbstractPacket"]]] = {}
    channel_type: ClassVar[ChannelType]
    topic: ClassVar[str]
    header: dict[str, Any] = field(default_factory=dict)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        AbstractPacket._registry[cls.topic] = cls

    @property
    @abstractmethod
    def payload(self) -> Any:
        pass

    def pack(self) -> tuple[bytes, bytes, bytes]:
        topic_b: bytes = self.topic.encode()
        header_b: bytes = msgpack.packb(self.header, use_bin_type=True)
        payload_b: bytes = msgpack.packb(self.payload, use_bin_type=True)
        return (topic_b, header_b, payload_b)

    @classmethod
    def unpack(cls, raw_packet: tuple[bytes, bytes, bytes]) -> "AbstractPacket":
        topic: str = raw_packet[0].decode()
        packet_subclass: type["AbstractPacket"] = AbstractPacket.by_topic(topic)
        return packet_subclass._from_bytes(
            header_b=raw_packet[1], payload_b=raw_packet[2]
        )

    @classmethod
    def by_topic(cls, topic: str) -> type["AbstractPacket"]:
        subclass: type["AbstractPacket"] | None = cls._registry.get(topic)
        if subclass is None:
            raise KeyError(f"No packet subclass registered with topic {topic}")
        return subclass

    @classmethod
    @abstractmethod
    def _from_bytes(cls, header_b: bytes, payload_b: bytes) -> Self:
        pass


@dataclass
class FourierTransform(AbstractPacket):
    topic: ClassVar[str] = "fft"
    channel_type: ClassVar[ChannelType] = ChannelType.DATA
    header: dict[str, Any]
    frequency_bins: NDArray[np.float32]
    transform: NDArray[np.float32]

    def payload(self) -> NDArray[np.float32]:
        return np.stack([self.frequency_bins, self.transform])

    @classmethod
    def _from_bytes(cls, header_b: bytes, payload_b: bytes) -> Self:
        header: dict[str, Any] = msgpack.unpackb(packed=header_b, raw=False)
        shape: tuple | None = header.get("shape")
        if shape is None:
            raise ValueError("Misformatted header dict, no shape value.")
        dtype: type | None = header.get("dtype")
        if dtype is None:
            raise ValueError("Misformatted header dict, no dtype value.")
        full_array: NDArray[np.float32] = np.frombuffer(
            buffer=payload_b, dtype=dtype
        ).reshape(shape)
        return cls(header, frequency_bins=full_array[0], transform=full_array[1])


@dataclass
class ControlPacket(AbstractPacket):
    pass
