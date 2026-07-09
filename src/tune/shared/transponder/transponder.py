"""Simplifies the function of zmq sub/pub as a single object"""

from dataclasses import dataclass
from enum import IntEnum
from queue import Empty, Full, Queue
from threading import Thread, Event
from typing import Any, Callable
from time import sleep
from logging import getLogger

import msgpack
import numpy as np
import zmq

from tune.shared.util.config_loader import (
    TopicSpec,
    get_indexed_topic_specs,
)

logger = getLogger(__name__)


class ChannelType(IntEnum):
    CONTROL = 0
    DATA = 1


class SocketType(IntEnum):
    PUB = zmq.PUB
    SUB = zmq.SUB


@dataclass
class RegistryEntry:
    topic: str
    channel_type: ChannelType
    spec: TopicSpec
    queue: Queue


class Transponder:
    _ctx: zmq.Context

    _topics: dict[SocketType, list[str]]
    _endpoints: dict[SocketType, dict[ChannelType, str]]
    _registry: dict[SocketType, dict[str, RegistryEntry]]

    _threads: list[Thread]

    _running: bool
    _shutdown_flag: Event

    def __init__(
        self,
        pubs: list[str] | None = None,
        subs: list[str] | None = None,
        pubsubs: list[str] | None = None,
        data_pub_endpoint: str = "tcp://127.0.0.1:5555",
        data_sub_endpoint: str = "tcp://127.0.0.1:5556",
        control_pub_endpoint: str = "tcp://127.0.0.1:5557",
        control_sub_endpoint: str = "tcp://127.0.0.1:5558",
    ) -> None:
        """
        Create a transponder.
        Note that all topics has to be specced out in config.yaml.

        Overlaps in arguments are handled quietly.

        Four threads, every thread its own socket.

        Every topic its own queue.

        All queues are max-size one.

        For communication between transponders, a broker must be running.

        Args:
            pubs: list of topics to publish to network
            subs: list of topics to subscribe to
            pubsubs: list of publisher/subscriber topics
        """
        logger.info("Transponder object initialized.")
        self._ctx = zmq.Context()
        self._running = False

        pubs: list[str] = pubs or []
        subs: list[str] = subs or []
        pubsubs: list[str] = pubsubs or []

        self._topics = {}
        self._topics[SocketType.PUB]: list[str] = list(set((pubs + pubsubs)))
        self._topics[SocketType.SUB]: list[str] = list(set((subs + pubsubs)))

        self._endpoints = {}
        self._endpoints[SocketType.PUB] = {
            ChannelType.CONTROL: control_pub_endpoint,
            ChannelType.DATA: data_pub_endpoint,
        }
        self._endpoints[SocketType.SUB] = {
            ChannelType.CONTROL: control_sub_endpoint,
            ChannelType.DATA: data_sub_endpoint,
        }

        self._registry: dict[SocketType, dict[str, RegistryEntry]] = {
            SocketType.PUB: {},
            SocketType.SUB: {},
        }

        self._threads = []

        self._shutdown_flag = Event()

    def start(self) -> None:
        """
        For now every transponder simply holds all four possible sockets, this is
        *slightly* wasteful, but not worth the effort to fix (for now).
        """
        logger.debug("Transponder start()")

        specs: dict[str, TopicSpec] = get_indexed_topic_specs()

        for socket_type in SocketType:
            for topic in self._topics[socket_type]:
                logger.debug(f"Setting up a {topic} {socket_type} channel")
                spec = specs[topic]
                channel_type: ChannelType = (
                    ChannelType.DATA if spec.dtype else ChannelType.CONTROL
                )
                queue: Queue = Queue(1)

                entry: RegistryEntry = RegistryEntry(
                    topic=topic,
                    channel_type=channel_type,
                    spec=spec,
                    queue=queue,
                )
                self._registry[socket_type][topic] = entry

        for channel_type in ChannelType:
            for socket_type in SocketType:
                endpoint = self._endpoints[socket_type][channel_type]
                name = f"ch{channel_type}sock{socket_type}"
                logger.debug(f"Creating thread {name}, pointed at {endpoint!r}")
                self._threads.append(
                    Thread(
                        target=self._run,
                        args=(
                            self._ctx,
                            endpoint,
                            socket_type,
                            channel_type,
                            self._registry[socket_type],
                            self._shutdown_flag,
                        ),
                        name=name,
                    )
                )

        self._running = True
        logger.debug(
            f"Transponder object starts, running in {len(self._threads)} separate threads."
        )
        for thread in self._threads:
            thread.start()
            logger.debug(f"Thread {thread.name} started.")

        logger.debug("Threads started, transponder is ready to roll.")

    def stop(self) -> None:
        """Stop the transponder.
        Terminates context, which blocks until all sockets are closed, then blocks until all threads are ended."""
        logger.debug("Transponder.stop()")
        if not self._running:
            logger.warning("stopping transponder when self._running already false.")
            return

        self._running = False

        logger.debug("Sending shutdown event")
        self._shutdown_flag.set()

        logger.debug(f"Joining {len(self._threads)} threads.")
        for thread in self._threads:
            name = thread.name
            thread.join()
            logger.debug(f"Thread '{name}' joined with main thread.")

        logger.debug("Sending term-signal to zmq Context.")
        self._ctx.term()  # blocks until all sockets are closed.

        logger.info("Transponder succesfully closed.")

    def put(self, topic: str, payload: object) -> None:
        entry = self._registry[SocketType.PUB].get(topic, None)
        if entry is None:
            logger.warning(
                f"Topic {topic} unregistered, no object given to transponder"
            )
            return
        if not isinstance(payload, entry.spec.payload_type):
            raise TypeError("Bad payload")
        if (
            entry.channel_type == ChannelType.DATA
            and isinstance(payload, np.ndarray)
            and payload.dtype != entry.spec.dtype
        ):
            logger.warning(
                f"Payload mismatch. topic: {topic}, in_dtype: {payload.dtype}, spec_dtype: {entry.spec.dtype}"
            )
            raise TypeError("Bad payload dtype")
        try:
            entry.queue.put_nowait(payload)
        except Full:
            entry.queue.get_nowait()
            entry.queue.put_nowait(payload)

    def get(self, topic: str) -> object:
        """Look in the inbox for a certain topic, this will be the latest payload received for this topic (overflow = lost packets).

        Args:
            topic: str, the topic name of the data you want. (make sure it is specced in config.yaml)

        Returns:
            payload
        """
        entry: RegistryEntry | None = self._registry[SocketType.SUB].get(topic, None)

        if entry is None:
            logger.warning(
                f"topic {topic} unregistered, no object taken from transponder"
            )
            return None
        try:
            o = entry.queue.get_nowait()
            return o
        except Empty:
            pass

    @staticmethod
    def _run(
        ctx: zmq.Context,
        endpoint: str,
        socket_type: int,
        channel_type: ChannelType,
        registry: dict[str, RegistryEntry],
        shutdown_flag: Event,
        linger: int = 0,
    ) -> None:
        """Runs in thread once.
        Sets up socket and moves on to suitable main loop.

        Args:
            ctx: zmq.Context
            endpoint: Address for the proxy
            socket_type: SUB or PUB
            channel_type: DATA or CONTROL
            registry: The registry of all topics, their types and queues.
            linger: int, how many milliseconds the socket will block socket.close()
                attempting to finish its business before closing. -1 means infinite blocking
                (which is zmq default).
                defaults to 0 in transponder, meaning immediate shutdown.
        """
        socket = ctx.socket(socket_type=int(socket_type))
        socket.connect(endpoint)
        socket.setsockopt(zmq.LINGER, linger)

        loop: Callable = (
            Transponder._sub_loop if socket_type == zmq.SUB else Transponder._pub_loop
        )

        filtered_registry: dict[str, RegistryEntry] = {
            key: value
            for key, value in registry.items()
            if value.channel_type == channel_type
        }

        loop(socket, filtered_registry, shutdown_flag=shutdown_flag)

    @staticmethod
    def _sub_loop(
        socket: zmq.Socket,
        registry: dict[str, RegistryEntry],
        shutdown_flag: Event,
        poller_timeout: int = 100,
    ) -> None:
        """Main loop for subscription sockets.
        Uses a poller and sends received data to the appropriate queues.

        Args:
            socket: This threads socket.
            registry: A registry of topics with matching channel type, with their types and queues.
        """
        for entry in registry.values():
            socket.setsockopt_string(zmq.SUBSCRIBE, entry.topic)

        poller = zmq.Poller()
        poller.register(socket, zmq.POLLIN)

        try:
            while not shutdown_flag.is_set():
                try:
                    if poller.poll(poller_timeout):
                        topic_b, header_b, payload_b = socket.recv_multipart()
                        topic = topic_b.decode()
                        entry = registry[topic]
                        if header_b:
                            header = msgpack.unpackb(header_b, raw=False)
                            shape = tuple(header["shape"])
                            dtype = np.dtype(header["dtype"])
                            payload: np.ndarray = np.frombuffer(
                                payload_b, dtype=dtype
                            ).reshape(shape)
                        else:
                            payload = msgpack.unpackb(payload_b)
                        try:
                            entry.queue.put_nowait(payload)
                        except Full:
                            entry.queue.get_nowait()
                            entry.queue.put_nowait(payload)
                except zmq.ContextTerminated:
                    break
        finally:
            socket.close()

    @staticmethod
    def _pub_loop(
        socket: zmq.Socket,
        registry: dict[str, RegistryEntry],
        shutdown_flag: Event,
    ) -> None:
        """Main loop for subsciption topics.
        Reads all registered queues, encodes any payloads into bytes and publishes.

        Args:
            socket: This threads socket.
            registry: The registry of all topics, their types and queues.

        Raises:
            TypeError: If any payload fails to abide by the specs of its topic.
        """
        try:
            while not shutdown_flag.is_set():
                try:
                    for entry in registry.values():
                        try:
                            payload: Any = entry.queue.get_nowait()
                        except Empty:
                            continue
                        b_topic: bytes = entry.topic.encode()
                        if entry.channel_type == ChannelType.DATA:
                            if not isinstance(payload, np.ndarray):
                                raise TypeError("Type mismatch.")
                            header = {
                                "shape": payload.shape,
                                "dtype": str(payload.dtype),
                            }
                            b_header: bytes = msgpack.packb(header, use_bin_type=True)
                            b_payload: bytes = payload.tobytes()
                        else:
                            b_header: bytes = b""
                            b_payload: bytes = msgpack.packb(payload, use_bin_type=True)
                        socket.send_multipart([b_topic, b_header, b_payload])
                except zmq.ContextTerminated:
                    break
                sleep(0.01)
        finally:
            socket.close()
