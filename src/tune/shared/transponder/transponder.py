"""Simplifies the function of zmq sub/pub as a single object with get and put methods"""

from queue import Empty, Full, Queue
from threading import Thread, Event
from typing import Callable
from time import sleep
from zmq import Context, Socket, LINGER, SUBSCRIBE, Poller, POLLIN, ContextTerminated

from tune.shared.transponder.packet import AbstractPacket
from tune.shared.util.config import config
from tune.shared.util.output_manager import output_manager as out
from tune.shared.transponder.types import (
    SocketType,
    ChannelType,
    Registry,
    RegistryEntry,
)


class Transponder:
    _context: Context
    _registry: Registry
    _shutdown_flag: Event

    def __init__(
        self,
        pubs: list[str] | None = None,
        subs: list[str] | None = None,
    ) -> None:
        """
        Create a transponder.

        Four threads, every thread its own socket.

        Every topic its own queue.

        All queues are max-size one.

        For communication between transponders, a broker must be running.

        Args:
            pubs: list of topics to publish to network
            subs: list of topics to subscribe to
        """
        out.info("Transponder object initialized.")
        self._context: Context = Context()

        pubs: list[str] = [] if pubs is None else pubs
        subs: list[str] = [] if subs is None else subs

        self._setup_registry(pubs, subs)

        self._shutdown_flag = Event()

    def _setup_registry(self, pubs: list[str], subs: list[str]) -> None:
        self._registry = Registry()

        self._registry.add_entry(
            socket_type=SocketType.PUB,
            channel_type=ChannelType.DATA,
            entry=RegistryEntry(
                endpoint=config.zmq_settings.pub_data_uri,
            ),
        )
        self._registry.add_entry(
            socket_type=SocketType.PUB,
            channel_type=ChannelType.CONTROL,
            entry=RegistryEntry(
                endpoint=config.zmq_settings.pub_control_uri,
            ),
        )

        for topic in pubs:
            self._registry.add_topic(socket_type=SocketType.PUB, topic=topic)

        self._registry.add_entry(
            socket_type=SocketType.SUB,
            channel_type=ChannelType.DATA,
            entry=RegistryEntry(
                endpoint=config.zmq_settings.sub_data_uri,
            ),
        )
        self._registry.add_entry(
            socket_type=SocketType.SUB,
            channel_type=ChannelType.CONTROL,
            entry=RegistryEntry(
                endpoint=config.zmq_settings.sub_control_uri,
            ),
        )

        for topic in subs:
            self._registry.add_topic(socket_type=SocketType.SUB, topic=topic)

    def start(self) -> None:
        """
        For now every transponder simply holds all four possible sockets, this is
        *slightly* wasteful, but not worth the effort to fix (for now).
        """
        out.debug("Transponder start")

        for entry, socket_type, channel_type in self._registry.entries():
            name = f"ch{channel_type}sock{socket_type}"
            out.debug(m=f"Creating thread {name}")
            entry.thread = Thread(
                target=self._run,
                name=name,
                kwargs={
                    "context": self._context,
                    "registry_entry": entry,
                    "socket_type": socket_type,
                    "channel_type": channel_type,
                    "shutdown_flag": self._shutdown_flag,
                },
            )

        for thread in self._registry.threads():
            thread.start()
            out.debug(f"Thread {thread.name} started.")

        out.debug("Threads started, transponder is ready to roll.")

    def stop(self) -> None:
        """Stop the transponder.
        Terminates context, which blocks until all sockets are closed, then blocks until all threads are ended."""
        out.debug("Transponder stop")

        out.debug("Raising shutdown flag")
        self._shutdown_flag.set()

        out.debug("Joining threads.")
        for thread in self._registry.threads():
            thread.join()
            out.debug(f"Thread '{thread.name}' joined with main thread.")

        out.debug("Sending term-signal to zmq Context.")
        self._context.term()  # blocks until all sockets are closed.

        out.info("Transponder succesfully closed.")

    def put(self, packet: AbstractPacket) -> None:
        """
        The main interaction point from any object wishing to send from the transponder.

        Packets given here will be put into a queue and sent to the zmq network.

        Args:
            packet: an instance of a subclass of AbstractPacket.
        """
        topic: str = packet.topic
        socket_type: SocketType = SocketType.PUB
        queue: Queue[AbstractPacket] = self._registry.get_queue(socket_type, topic)

        try:
            queue.put_nowait(item=packet)
        except Full:
            queue.get_nowait()
            queue.put_nowait(item=packet)

    def get(self, topic: str) -> AbstractPacket | None:
        """Look in the inbox for a certain topic, this will be the latest payload received for this topic (overflow = lost packets).

        Args:
            topic: str, the topic name of the data you want. (make sure it is specced in config.yaml)

        Returns:
            payload
        """
        queue: Queue = self._registry.get_queue(socket_type=SocketType.SUB, topic=topic)
        try:
            packet: AbstractPacket = queue.get_nowait()
            return packet
        except Empty:
            pass

    @staticmethod
    def _run(
        context: Context,
        socket_type: SocketType,
        channel_type: ChannelType,
        registry_entry: RegistryEntry,
        shutdown_flag: Event,
        linger: int = 0,
    ) -> None:
        """Runs in thread once.
        Sets up socket and moves on to suitable main loop.

        Args:
            context: zmq.Context
            endpoint: Address for the proxy
            socket_type: SUB or PUB
            channel_type: DATA or CONTROL
            registry: The registry of all topics, their types and queues.
            linger: int, how many milliseconds the socket will block socket.close()
                attempting to finish its business before closing. -1 means infinite blocking
                (which is zmq default).
                defaults to 0 in transponder, meaning immediate shutdown.
        """
        socket: Socket = context.socket(
            socket_type=int(socket_type)
        )  # casting to int to please sensitive c layer.
        socket.connect(addr=registry_entry.endpoint)
        socket.setsockopt(option=LINGER, value=linger)

        registry_entry.socket = socket

        loop: Callable = (
            Transponder._sub_loop
            if socket_type == SocketType.SUB
            else Transponder._pub_loop
        )

        loop(registry_entry, shutdown_flag=shutdown_flag)

    @staticmethod
    def _sub_loop(
        registry_entry: RegistryEntry,
        shutdown_flag: Event,
    ) -> None:
        """Main loop for subscription sockets.
        Uses a poller and sends received data to the appropriate queues.
        """

        if registry_entry.socket is None:
            out.warning(
                m="Registry entry in transponder started its loop without active socket"
            )
            return

        for topic in registry_entry.topics():
            registry_entry.socket.setsockopt_string(option=SUBSCRIBE, optval=topic)

        poller = Poller()
        poller.register(registry_entry.socket, flags=POLLIN)
        poller_timeout: int = config.zmq_settings.sub_poller_timeout_ms

        try:
            while not shutdown_flag.is_set():
                try:
                    if poller.poll(poller_timeout):
                        raw_packet: tuple[bytes, ...] = tuple(
                            registry_entry.socket.recv_multipart()
                        )
                        if len(raw_packet) != 3:
                            raise ValueError(
                                "Misshaped data from socket.recv_multipart()"
                            )
                        packet: AbstractPacket = AbstractPacket.unpack(raw_packet)
                        queue: Queue[AbstractPacket] = registry_entry.get_queue(
                            packet.topic
                        )
                        try:
                            queue.put_nowait(item=packet)
                        except Full:
                            queue.get_nowait()
                            queue.put_nowait(item=packet)
                except ContextTerminated:
                    break
        finally:
            registry_entry.socket.close()

    @staticmethod
    def _pub_loop(
        registry_entry: RegistryEntry,
        shutdown_flag: Event,
    ) -> None:
        """Main loop for publication topics.
        Reads all registered queues, encodes into bytes and publishes.
        """
        if registry_entry.socket is None:
            out.warning(
                m="Registry entry in transponder started its loop without active socket"
            )
            return

        sleep_seconds: float = config.zmq_settings.pub_sleep_seconds

        try:
            while not shutdown_flag.is_set():
                try:
                    for queue in registry_entry.queues():
                        try:
                            packet: AbstractPacket = queue.get_nowait()
                        except Empty:
                            continue
                        packed_packet: tuple[bytes, bytes, bytes] = packet.pack()
                        registry_entry.socket.send_multipart(
                            msg_parts=packed_packet, use_bin_type=True
                        )
                except ContextTerminated:
                    break
                sleep(sleep_seconds)
        finally:
            registry_entry.socket.close()
