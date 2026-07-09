from numpy.typing import NDArray
import numpy as np
from typing import Callable, Any, cast
from .layout import Ui_MainWindow

from pyqtgraph.Qt.QtWidgets import QMainWindow

from logging import Logger, getLogger

logger: Logger = getLogger(__name__)


class MainWindow(QMainWindow, Ui_MainWindow):
    """
    todo: set and display fps.
    """

    getter: Callable

    def __init__(self, getter: Callable[[str], Any]) -> None:
        super().__init__()
        self.setupUi(self)
        self._fft_plot_initialized = False
        self._connect_sliders()
        self.getter = getter

    def update(self) -> None:
        self._update_fft()

    def _update_fft(self) -> None:
        data = self.getter("fft")
        if data is None:
            return

        # i should really just check against spec instead of this bullshit.
        assert isinstance(data, np.ndarray) and data.shape[0] == 2
        np_data = cast(NDArray[np.float32], data)
        freqs: NDArray[np.float32] = np_data[0]
        magnitudes: NDArray[np.float32] = np_data[1]

        if not self._fft_plot_initialized:
            self._setup_fft_plot(freqs)
            self._fft_plot_initialized = True

        self.fft_curve.setData(freqs, magnitudes)

    def _setup_fft_plot(self, freqs: NDArray[np.float32]) -> None:
        logger.debug(f"_setup_fft_plot freqs={freqs!r}")
        nyquist: float = freqs[-1]
        self.fftplot.setXRange(20, nyquist)
        self.fftplot.setYRange(0.0001, 1.2)
        self.fftplot.setLogMode(x=False, y=False)
        self.fftplot.enableAutoRange()
        self.fftplot.enableAutoRange(False)
        self.fftplot.setMouseEnabled(x=False, y=False)
        self.fftplot.setLabel("bottom", "Frequency", units="Hz")
        self.fftplot.setLabel("left", "Amplitude")
        self.fftplot.showGrid(x=True, y=True)
        self.fft_curve = self.fftplot.plot(pen="y")

    def _connect_sliders(self) -> None:
        # Prominence  (slider 0–100  →  float 0.0–1.0)
        self.prominence_slider.valueChanged.connect(
            lambda v: self._s2f(self.prominence_spinbox, v, scale=100)
        )
        self.prominence_spinbox.editingFinished.connect(
            lambda: self._f2s(
                self.prominence_slider, self.prominence_spinbox.value(), scale=100
            )
        )
        # Height  (slider 0–100  →  float 0.0–100.0 percent)
        self.height_slider.valueChanged.connect(
            lambda v: self._s2f(self.height_spinbox, v, scale=1)
        )
        self.height_spinbox.editingFinished.connect(
            lambda: self._f2s(self.height_slider, self.height_spinbox.value(), scale=1)
        )
        # Distance  (slider 0–200  →  int bins, 1:1)
        self.distance_slider.valueChanged.connect(
            lambda v: self._s2f(self.distance_spinbox, v, scale=1)
        )
        self.distance_spinbox.editingFinished.connect(
            lambda: self._f2s(
                self.distance_slider, self.distance_spinbox.value(), scale=1
            )
        )

    def _s2f(self, spinbox, int_val, scale):
        spinbox.blockSignals(True)
        spinbox.setValue(int_val / scale)
        spinbox.blockSignals(False)

    def _f2s(self, slider, float_val, scale):
        slider.blockSignals(True)
        slider.setValue(int(float_val * scale))
        slider.blockSignals(False)

    def get_peak_params(self):
        return {
            "prominence": self.prominence_spinbox.value(),
            "height": self.height_spinbox.value() / 100.0,
            "distance": int(self.distance_spinbox.value()),
        }
