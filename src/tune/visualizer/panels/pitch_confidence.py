from numpy.typing import NDArray
from tune.visualizer.panels.base import AbstractTunePanel, PanelSettings
from tune.shared.types.data_buffer import DataBuffer

from logging import getLogger
from typing import Callable, cast

import numpy as np

logger = getLogger(__name__)


class PitchConfidencePanel(AbstractTunePanel):
    buffer: DataBuffer[np.float32]

    def __init__(
        self, getter: Callable[[str], object], settings: PanelSettings
    ) -> None:
        logger.debug(f"__init__ getter={getter!r}, settings={settings!r}")
        super().__init__(getter, settings)
        self.buffer: DataBuffer[np.float32] = DataBuffer()
        self.plot_data_items["pitch_confidence"] = self.plot_item.plot()

    def refresh(self) -> None:
        data: object = self.get("pitch")
        if data is None:
            return
        assert (  # todo: instead of this shit - compare to spec.
            isinstance(data, np.ndarray)
        )
        cast_data: NDArray[np.float32] = cast(NDArray[np.float32], data)
        self.buffer.push(cast_data)
        buffer_mirror: list[NDArray[np.float32]] = self.buffer.get_copy()
        logger.debug(f"Buffer: {buffer_mirror}")
        x: list[np.float32] = []
        y: list[np.float32] = []
        for data_point in buffer_mirror:
            x.append(data_point[0])
            y.append(data_point[1])
        self.plot_data_items["pitch_confidence"].setData(x, y)
