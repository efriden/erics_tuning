import pyqtgraph as pg
import numpy as np
import numpy.typing as npt
from typing import Callable, cast
from logging import getLogger

from tune.visualizer.panels.base import AbstractTunePanel, PanelSettings

logger = getLogger(__name__)


class FourierPanel(AbstractTunePanel):
    def __init__(
        self, getter: Callable[[str], object], settings: PanelSettings
    ) -> None:
        logger.debug(f"__init__ getter={getter!r}, settings={settings!r}")
        super().__init__(getter, settings)
        transform = self.plot_item.plot(fillLever=0, fillOutline=True, brush="y")
        self.plot_data_items["transform"] = transform

    def refresh(self) -> None:
        data: object = self.get("fft")
        if data is None:
            return
        # todo: these type shenanigans should be replaced by something that checks against spec
        assert isinstance(data, np.ndarray) and data.shape[0] == 2
        xy = cast(npt.NDArray[np.float32], data)
        self.plot_data_items["transform"].setData(xy[0], xy[1])

