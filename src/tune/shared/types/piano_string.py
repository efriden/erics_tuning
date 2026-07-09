from typing import Self
from math import sqrt
import numpy as np
from scipy.signal import find_peaks
import numpy.typing as npt
import librosa

from logging import getLogger

logger = getLogger(__name__)


class PianoString:
    """
    A model of the current state of a physical piano string.

    The important value to consider here is the Inharmonicity Coefficient B.
    This measures the physical characteristics of the string, and determines
    the frequencies of the overtones of the string. (the term 'partial' will
    be used here instead of 'harmonics' since they differ a lot from the
    harmonics of an ideal harmonic oscillator).

    The 'Railsback stretch' (Railsback, 1938) is the difference of fundamental
    frequency of piano keys from that of equal temperament. It is a byproduct
    of a compromise made by a pianotuner to make as many partials as possible
    match up with partials of other keys - often higher octaves. The definition
    of B and its matching with the partials of piano keys is due to Harvey
    Fletcher (1964).
    """

    f0: np.float32 | None
    midi: int | None
    B: np.float32 | None
    valid: bool

    def __init__(
        self,
        midi: int | None = None,
        note: str | None = None,
        f0: np.float32 | None = None,
        B: np.float32 | None = None,
    ) -> None:
        self.B = B
        self.f0 = f0
        if midi is not None and note is not None and librosa.note_to_midi(note) != midi:
            raise ValueError(
                "A String object was initialized with both a note string and a midi int, and they didnt match."
            )
        if note is not None:
            self.midi = int(librosa.note_to_midi(note, round_midi=True))
        if midi is not None:
            self.midi = midi
        self.valid = False

    @property
    def note(self) -> str:
        if self.midi is None:
            return "unknown"
        return librosa.midi_to_note(self.midi)

    @property
    def partials(self) -> npt.NDArray[np.float32]:
        """
        Calculates predicted partials from stored values of B and f_0.

        Returns:
            npt.NDArray[np.float32]:

        """
        if self.f0 is None or self.B is None:
            raise ValueError("cannot calculate partials without f0 and B.")
        n = np.arange(1, 10, dtype=np.float32)
        return n * self.f0 * np.sqrt(1 + self.B * n * n)

    def update_with_peaks(self, fs: npt.ArrayLike) -> None:
        """
        Calculate a value for fundamental frequency and the inharmonicity constant by
        finding a linear regression function on (f_0/n)^2 over n^2.

        fs: ArrayLike object with frequencies of the partials (f_1, f_2, ...) measured
        from analysis of the sound of the string being struck.

        """
        partials = np.asarray(fs, dtype=np.float32)
        if len(partials) < 3:
            logger.debug("no peaks found")
            self.valid = False
            return
        # To maintain connection to physics convention - we keep n = 0 out of this.
        n: npt.NDArray = np.arange(1, len(partials) + 1)
        X: npt.NDArray = n**2
        Y: npt.NDArray[np.float32] = (partials**2) / X
        coefficients: npt.NDArray[np.float64] = np.polyfit(X, Y, deg=1)
        k = float(coefficients[0])
        m = float(coefficients[1])

        self.f0: float = sqrt(m)
        self.B: float = k / m

        self.valid = True

    def update_with_fft(
        self,
        fft: npt.NDArray[np.float32],
        prominence: float,
        height: float,
        distance: float,
    ) -> None:
        if not fft.shape[0] == 2:
            raise RuntimeError("bad fftarray shape")

        peaks, properties = find_peaks(
            x=fft[0],
            prominence=prominence,
            height=height,
            distance=distance,
        )

        # todo: quadratic interpolation
        #

        fs = []

        for peak in peaks:
            fs.append(fft[peak])

        self.update_with_peaks(fs)

    @classmethod
    def from_fft(
        cls,
        fft: npt.NDArray[np.float32],
        prominence: float,
        height: float,
        distance: float,
    ) -> Self:
        if not fft.shape[0] == 2:
            raise RuntimeError("bad fftarray shape")

        o = cls()
        o.update_with_fft(fft, prominence=prominence, height=height, distance=distance)
        return o

    def pack(self) -> npt.NDArray[np.float32]:
        if self.f0 is None or self.B is None:
            logger.debug(
                "attempted to pack a piano_string with either B or f0 as None."
            )
            return np.array([0, 0])
        return np.array([self.f0, self.B])

    @classmethod
    def unpack(cls, package: npt.NDArray[np.float32]) -> Self:
        return cls(f0=package[0], B=package[1])
