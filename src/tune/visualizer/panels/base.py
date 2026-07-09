from abc import ABC, abstractmethod
from typing import Callable
import pyqtgraph as pg

from tune.shared.types.settings_specs import PanelSettings

from logging import getLogger

logger = getLogger(__name__)


class AbstractTunePanel(ABC):
    name: str
    get: Callable[[str], object]
    plot_item: pg.PlotItem
    # not all panels will have plotdataitems, this should probably change.
    plot_data_items: dict[str, pg.PlotDataItem]

    def __init__(
        self, getter: Callable[[str], object], settings: PanelSettings
    ) -> None:
        logger.debug(f"__init__ getter={getter!r}, settings={settings!r}")
        self.name = settings.name
        self.get = getter
        self.plot_item = pg.PlotItem(
            name=settings.name, labels=settings.labels, title=settings.title
        )

        self.plot_item.showGrid(settings.show_x_grid, y=settings.show_y_grid)

        if settings.x_range:
            self.plot_item.getViewBox().setXRange(*settings.x_range)
        if settings.y_range:
            self.plot_item.getViewBox().setYRange(*settings.y_range)

        self.plot_data_items = {}

    @abstractmethod
    def refresh(self) -> None:
        pass
