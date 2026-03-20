import zmq
import threading

from tune.shared.util.setup_logging import setup_logging, log_run_start
from logging import getLogger

logger = getLogger(__name__)


class Broker:
    """
    ZeroMQ PUB/SUB broker using XSUB/XPUB proxy pattern.

    Two threads will be running in the zmq c-layer, for data and control.

    Publishers connect to `pub_endpoint`.
    Subscribers connect to `sub_endpoint`.
    """

    _ctx: zmq.Context

    _data_pub_endpoint: str
    _data_sub_endpoint: str
    _control_pub_endpoint: str
    _control_sub_endpoint: str

    _data_thread: threading.Thread | None = None
    _control_thread: threading.Thread | None = None
    _running: bool

    def __init__(
        self,
        data_pub_endpoint: str = "tcp://*:5555",
        data_sub_endpoint: str = "tcp://*:5556",
        control_pub_endpoint: str = "tcp://*:5557",
        control_sub_endpoint: str = "tcp://*:5558",
    ) -> None:
        """Initializes a broker instance. Run start() to make it go.

        data_pub_endpoint:
        data_sub_endpoint:
        control_pub_endpoint:
        control_sub_endpoint:

        """
        logger.debug(
            f"__init__ data_pub_endpoint={data_pub_endpoint!r}, data_sub_endpoint={data_sub_endpoint!r}, control_pub_endpoint={control_pub_endpoint!r}, control_sub_endpoint={control_sub_endpoint!r}"
        )
        self._ctx = zmq.Context()
        self._data_pub_endpoint = data_pub_endpoint
        self._data_sub_endpoint = data_sub_endpoint
        self._control_pub_endpoint = control_pub_endpoint
        self._control_sub_endpoint = control_sub_endpoint

        self._running = False

    def start(self) -> None:
        """Start two broker worker threads."""
        logger.debug("start")
        if self._running:
            logger.warning("attempted to start an already running broker.")
            return

        self._running = True

        self._data_thread = threading.Thread(
            target=self._run,
            args=(self._ctx, self._data_pub_endpoint, self._data_sub_endpoint),
        )
        self._control_thread = threading.Thread(
            target=self._run,
            args=(self._ctx, self._control_pub_endpoint, self._control_sub_endpoint),
        )

        self._data_thread.start()
        self._control_thread.start()

    @staticmethod
    def _run(ctx: zmq.Context, pub_endpoint: str, sub_endpoint: str) -> None:
        """Main loop. Owns the sockets.

        ctx:zmq Context
        pub_endpoint:
        sub_endpoint:

        """
        logger.debug(
            f"_run ctx={ctx!r}, pub_endpoint={pub_endpoint!r}, sub_endpoint={sub_endpoint!r}"
        )
        frontend: zmq.Socket = ctx.socket(zmq.XSUB)
        frontend.bind(pub_endpoint)

        backend: zmq.Socket = ctx.socket(zmq.XPUB)
        backend.bind(sub_endpoint)

        try:
            zmq.proxy(frontend, backend)  # blocks, loops internally
        except zmq.ContextTerminated:
            pass  # expected, exits gracefully when main thread terminates context.
        finally:
            frontend.close()
            backend.close()

    def stop(self) -> None:
        """Clean shutdown."""
        logger.debug("stop")
        if not self._running:
            logger.warning("attempted to stop a not-running broker")
            return

        self._running = False

        self._ctx.term()  # blocks until all sockets are closed.

        if self._data_thread:
            self._data_thread.join()
        if self._control_thread:
            self._control_thread.join()


def main() -> None:
    setup_logging(root_level=10)
    log_run_start()
    broker = Broker()
    broker.start()
    input("press key to shutdown broker")
    broker.stop()
    logger.info("Broker stopped.")


if __name__ == "__main__":
    main()
