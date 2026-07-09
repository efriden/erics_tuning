from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray
from typing import Self
import librosa


@dataclass
class Pitch:
    """
    A detected pitch.
    Stored as a frequency in hz and a standard uncertainty in cents.
    both are nan if considered unvoiced.

    The main constructor is 'from_pyin' - that assumes the direct output from
    librosa.pyin.

    Since librosa.pyin divides the audio chunk into frames the from_pyin constructor
    actually constructs a weighted geometric mean over the entire chunk. Every
    frame in the pyin result also comes with a probability - this is used as weights
    and for construction of an uncertainty.

    stores a reference_frequency, but is currently unused, and 440 is assumed.
    """

    _f: float
    _u: float
    reference_frequency: float

    def __init__(self, f: float, u: float, reference_frequency: float = 440.0) -> None:
        self._f: float = f
        self._u: float = u
        self.reference_frequency: float = reference_frequency

    def __str__(self) -> str:
        return f"{self._f:.2f} Hz ± {self._u:.1f}¢"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(hz={self._f!r}, cents={self._u!r})"

    @classmethod
    def from_pyin(
        cls, raw: tuple[NDArray[np.float32], NDArray[np.bool_], NDArray[np.float32]]
    ) -> Self | None:
        f0s, voiced, confidences = raw

        mask = voiced & np.isfinite(f0s)
        if not mask.any():
            return None

        fs = f0s[mask]
        ps = confidences[mask]

        ln_fs: NDArray[np.float32] = np.log(fs)
        ln_weighted_mean: float = np.average(ln_fs, weights=ps)

        ln_spread: float = np.sqrt(
            np.average((ln_fs - ln_weighted_mean) ** 2, weights=ps)
        )

        weighted_geometric_mean_hz: float = np.exp(ln_weighted_mean)
        spread_cents: float = 1200 * ln_spread

        return cls(weighted_geometric_mean_hz, spread_cents)

    @classmethod
    def empty(cls) -> Self:
        return cls(float("nan"), float("nan"))

    def as_hz(self) -> float:
        return self._f

    def as_note(self) -> str:
        return librosa.hz_to_note(self._f, cents=True)

    @property
    def frequency(self) -> float:
        return self._f

    def pack(self) -> np.ndarray:
        return np.array([self._f, self._u], dtype=np.float32)

    @classmethod
    def unpack(cls, array: np.ndarray) -> Self:
        return cls(float(array[0]), float(array[1]))
