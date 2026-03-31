from typing import Callable
from dataclasses import dataclass, field
from time import sleep
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
from tune.shared.transponder.transponder import Transponder
from tune.shared.util.setup_logging import setup_logging
from tune.visualizer.panels.base import AbstractTunePanel, PanelSettings
from tune.visualizer.panels.fourier import FourierPanel

import numpy.typing as npt
import numpy as np

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
        self.app = pg.mkQApp("Tune Visualizer")

        self.grid = pg.GraphicsLayoutWidget(show=True)
        self.grid.setWindowTitle("Erics tuning - live visualizations")

        self.panels = []

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh)

        self._transponder = Transponder(subs=["fft"])

    def add_panel(
        self, panel_class: type[AbstractTunePanel], panel_settings: PanelSettings
    ) -> None:
        panel = panel_class(self._transponder.get, panel_settings)
        self.panels.append(panel)
        self.grid.addItem(panel.plot_item)

    def start(self) -> None:
        logger.debug("start")
        logger.debug("starting timer")
        # todo: set this in config.yaml
        self.timer.start(50)
        logger.debug("starting transponder")
        self._transponder.start()
        logger.debug("executing qapp")
        self.app.exec()  # blocks

    def stop(self) -> None:
        self._transponder.stop()

    def refresh(self) -> None:
        for panel in self.panels:
            panel.refresh()


def main() -> None:
    setup_logging(root_level=10)

    logger.info("Visualizer start")
    visualizer: TuneVisualizer = TuneVisualizer()

    logger.debug("Initiating settings")
    fourier_settings = PanelSettings(
        name="fourier",
        title="Normalized Fourier Transform",
    )

    logger.debug("Adding plots to visualizer")
    visualizer.add_panel(FourierPanel, panel_settings=fourier_settings)

    logger.debug("Starting QApplication")
    try:
        visualizer.start()
    except KeyboardInterrupt:
        pass
    finally:
        visualizer.stop()

    logger.debug("Qapp closed.")


if __name__ == "__main__":
    main()
