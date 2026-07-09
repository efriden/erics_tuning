from numpy.typing import NDArray
import numpy as np
from .base import AbstractTunePanel, PanelSettings
from typing import Callable, cast
import pyqtgraph as pg

from logging import getLogger

logger = getLogger(__name__)


class SpectrogramPanel(AbstractTunePanel):
    image_item: pg.ImageItem
    colormap: pg.ColorMap
    spectrogram_data: NDArray[np.float32] | None
    history: int

    def __init__(
        self, getter: Callable[[str], object], settings: PanelSettings
    ) -> None:
        super().__init__(getter, settings)
        self.image_item = pg.ImageItem()
        self.plot_item.addItem(self.image_item)
        self.colormap = pg.colormap.get("inferno")
        self.image_item.setColorMap(self.colormap)
        self.image_item.setLevels([0, 1])
        self.history = 50
        self.spectrogram_data = None

    def refresh(self) -> None:
        data: object = self.get("fft")
        if data is None:
            return

        cast_data = cast(NDArray[np.float32], data)

        if self.spectrogram_data is None:
            logger.debug("Lazyloading the spectrogram_data array")
            self.spectrogram_data = np.zeros(
                (self.history, cast_data.shape[1]), dtype=np.float32
            )

        x, y = np.unstack(cast_data)

        self.spectrogram_data = np.roll(self.spectrogram_data, -1, axis=0)
        self.spectrogram_data[-1] = np.log(y)
        self.image_item.setImage(self.spectrogram_data, autoLevels=True)
