import faulthandler
import signal
import sys

import pyqtgraph as pyqtgraph
from pyqtgraph.Qt.QtWidgets import QApplication
from pyqtgraph.Qt.QtCore import QTimer

from tune.shared.transponder.transponder import Transponder
from tune.shared.util.setup_logging import setup_logging
from tune.visualizer.layout.main_window import MainWindow

from logging import Logger, getLogger

logger: Logger = getLogger(__name__)


class VisualizerApp:
    def __init__(self) -> None:
        logger.debug("__init__")
        self.app = QApplication(sys.argv)
        self.timer = QTimer()
        self._setup_transponder()
        self.window = MainWindow(self.transponder.get)

    def _setup_transponder(self) -> None:
        pubs: list[str] = []
        subs: list[str] = ["fft", "piano_string"]
        self.transponder = Transponder(pubs, subs)

    def start(self) -> None:
        logger.debug("start")
        self.window.show()
        self.transponder.start()
        timer.start(50)
        timer.timeout.connect(self.update)
        self.app.exec()  # blocks

    def stop(self) -> None:
        logger.debug("stop")
        self.transponder.stop()
        self.app.quit()

    def update(self) -> None:
        self.window.update()


if __name__ == "__main__":
    setup_logging()
    logger.info("Visualizer starting up...")
    visualizer = VisualizerApp()

    def shutdown(sig=None, frame=None) -> None:
        logger.info("shutting down")
        visualizer.stop()

    logger.debug("Setting up shutdown signals and Python signal-finder")
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Qt blocks the GIL so Python never checks signals — this timer
    # wakes Python up every 200ms to check for pending signals
    timer = QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)

    faulthandler.enable()  # without this c-errors are invisible.

    logger.debug("Starting the show...")
    try:
        visualizer.start()  # blocks
    except Exception:
        logger.exception("unhandled exception in qapp")
        shutdown()
        sys.exit(1)
    finally:
        logger.info("Visualiser closed.")
