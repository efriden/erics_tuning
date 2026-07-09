import faulthandler
import signal
import sys
from tune.visualizer.panels.pitch_confidence import PitchConfidencePanel
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore
from tune.shared.transponder.transponder import Transponder
from tune.shared.util.setup_logging import setup_logging
from tune.visualizer.panels.base import AbstractTunePanel, PanelSettings
from tune.visualizer.panels.fourier import FourierPanel
from tune.visualizer.panels.spectrogram import SpectrogramPanel

from logging import Logger, getLogger

logger: Logger = getLogger(__name__)


class TuneVisualizer:
    app: pg.QtWidgets.QApplication
    grid: pg.GraphicsLayoutWidget
    panels: list[AbstractTunePanel]
    timer: QtCore.QTimer
    _transponder: Transponder

    def __init__(self) -> None:
        """
        Creates a Grid layout that can then be populated with plots.
        """
        logger.debug("__init__")
        self.app = pg.mkQApp("Tune Visualizer")

        self.grid = pg.GraphicsLayoutWidget(show=True)
        self.grid.setWindowTitle("Erics tuning - live visualizations")

        self.panels = []

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh)

        self._transponder = Transponder(
            subs=["fft", "pitch"]
        )  # todo - make this better

    def add_panel(
        self, panel_class: type[AbstractTunePanel], panel_settings: PanelSettings
    ) -> None:
        logger.debug(
            f"add_panel panel_class={panel_class!r}, panel_settings={panel_settings!r}"
        )
        panel = panel_class(self._transponder.get, panel_settings)
        self.panels.append(panel)
        self.grid.addItem(panel.plot_item)

    def start(self) -> None:
        logger.debug("start")
        logger.debug("starting timer")
        # todo: set this in config.yaml
        self.timer.start(200)
        logger.debug("starting transponder")
        self._transponder.start()
        logger.debug("executing qapp")
        self.app.exec()  # blocks

    def stop(self) -> None:
        self._transponder.stop()
        self.app.quit()

    def refresh(self) -> None:
        for panel in self.panels:
            panel.refresh()

    def pause(self) -> None:
        """Todo: implement a pause that stops any new data or timed update
        from hapenning, but otherwise keeps the app running.

        in theory, maybe this is just a bool flag that stops the refresh?
        probably not - need to look into.
        """
        pass

    def unpause(self) -> None:
        pass


def main() -> None:
    setup_logging(root_level=10)
    logger.info("Visualizer start")
    visualizer: TuneVisualizer = TuneVisualizer()

    def shutdown(sig=None, frame=None) -> None:
        logger.info("shutting down")
        visualizer.stop()

    logger.debug("Setting up shutdown signals and Python signal-finder")
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Qt blocks the GIL so Python never checks signals — this timer
    # wakes Python up every 200ms to check for pending signals
    timer = QtCore.QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)

    logger.debug("Initializing PanelSettings")
    # todo: this should DEFINITELY be taken from the config.yaml
    fourier_settings = PanelSettings(
        name="fourier", title="Normalized Fourier Transform"
    )

    logger.debug("Setting up layout")
    visualizer.add_panel(FourierPanel, panel_settings=fourier_settings)

    faulthandler.enable()  # without this c-errors are invisible.
    logger.debug("Starting QApplication")
    try:
        visualizer.start()
    except Exception:
        logger.exception("unhandled exception in visualizer")
        shutdown()
        sys.exit(1)
    finally:
        logger.debug("QApp closed.")


if __name__ == "__main__":
    main()
