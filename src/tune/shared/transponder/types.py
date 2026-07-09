"""
Enums and dataclasses used by the transponder system.
"""

from collections.abc import Iterator

from threading import Thread
from queue import Queue
from enum import IntEnum
from dataclasses import dataclass, field
import zmq

from .packet import AbstractPacket
from tune.shared.util.output_manager import output_manager as out


class ChannelType(IntEnum):
    CONTROL = 0
    DATA = 1


class SocketType(IntEnum):
    PUB = zmq.PUB
    SUB = zmq.SUB


@dataclass
class RegistryEntry:
    endpoint: str
    _queues_by_topic: dict[str, Queue[AbstractPacket]] = field(default_factory=dict)
    thread: Thread | None = None
    socket: zmq.Socket | None = None

    def topics(self) -> Iterator[str]:
        return iter(self._queues_by_topic.keys())

    def queues(self) -> Iterator[Queue]:
        return iter(self._queues_by_topic.values())

    def get_queue(self, topic: str) -> Queue:
        queue: Queue | None = self._queues_by_topic.get(topic)
        if queue is None:
            raise ValueError(f"No topic with name {topic} is registered.")
        return queue

    def add_queue(self, topic: str) -> None:
        queue: Queue | None = self._queues_by_topic.get(topic)
        if queue is not None:
            out.warning(
                f"Tried to add topic {topic}, but one by this name already exists."
            )
            return

        self._queues_by_topic[topic] = Queue(maxsize=1)

    def add_topic(self, topic: str) -> None:
        """convenience double of add_queue"""
        self.add_queue(topic)


@dataclass
class Registry:
    _data: dict[SocketType, dict[ChannelType, RegistryEntry]] = field(
        default_factory=dict
    )

    def add_entry(
        self,
        socket_type: SocketType,
        channel_type: ChannelType,
        entry: RegistryEntry,
    ) -> None:
        self._data[socket_type][channel_type] = entry

    def add_topic(
        self,
        socket_type: SocketType,
        topic: str,
    ) -> None:
        channel_type: ChannelType = AbstractPacket.by_topic(topic).channel_type
        entry: RegistryEntry = self.get_entry_by_types(socket_type, channel_type)
        entry.add_topic(topic)

    def get_entry_by_types(
        self, socket_type: SocketType, channel_type: ChannelType
    ) -> RegistryEntry:
        return self._data[socket_type][channel_type]

    def get_entry_by_topic(
        self, topic: str, socket_type: SocketType | None = None
    ) -> RegistryEntry | list[RegistryEntry]:
        entries: list[RegistryEntry] = []
        for entry, _socket_type, _ in self.entries():
            if socket_type is None or socket_type == _socket_type:
                if topic in entry.topics():
                    entries.append(entry)

        if len(entries) == 1:
            return entries[0]
        if len(entries) == 2 and socket_type is None:
            return entries
        raise RuntimeError(f"The registry is malformed. {self}")

    def get_queue(
        self,
        socket_type: SocketType,
        topic: str,
    ) -> Queue:
        entry: RegistryEntry | list[RegistryEntry] = self.get_entry_by_topic(
            topic, socket_type
        )
        if not isinstance(entry, RegistryEntry):
            raise RuntimeError(
                f"Something went very wrong when using get_queue with topic {topic}"
            )
        return entry.get_queue(topic)

    def entries(self) -> Iterator[tuple[RegistryEntry, SocketType, ChannelType]]:
        for socket_type in SocketType:
            for channel_type in ChannelType:
                yield (
                    self.get_entry_by_types(socket_type, channel_type),
                    socket_type,
                    channel_type,
                )

    def threads(self) -> Iterator[Thread]:
        for entry, _, _ in self.entries():
            thread: Thread | None = entry.thread
            if thread is None:
                continue
            yield thread
