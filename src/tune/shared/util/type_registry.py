import pyaudio as pa
import numpy as np

from logging import getLogger

logger = getLogger(__name__)

NumpyScalarType = type[np.generic]
PyAudioFormat = int


BUILTIN_TYPE_REGISTRY: dict[str, type] = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "builtins.int": int,
    "builtins.float": float,
    "builtins.str": str,
    "ndarray": np.ndarray,
    "np.ndarray": np.ndarray,
}

NUMPY_DTYPE_REGISTRY: dict[str, NumpyScalarType] = {
    "np.float32": np.float32,
    "np.int16": np.int16,
    "np.int32": np.int32,
    "numpy.float32": np.float32,
    "float32": np.float32,
}

PYAUDIO_FORMAT_REGISTRY: dict[str, PyAudioFormat] = {
    # PyAudio (if available)
    "pyaudio.paFloat32": pa.paFloat32,
    "paFloat32": pa.paFloat32,
    "pyaudio.paInt16": pa.paInt16,
}


def resolve_builtin_type(s: str) -> type | None:
    t = BUILTIN_TYPE_REGISTRY.get(s, None)
    logger.debug(f"Resolving {s} to builtin type {t}.")
    return t


def resolve_numpy_dtype(s: str) -> NumpyScalarType | None:
    t = NUMPY_DTYPE_REGISTRY.get(s, None)
    logger.debug(f"Resolving {s} to numpy dtype {t}.")
    return t


def resolve_pyaudio_format(s: str) -> PyAudioFormat | None:
    t = PYAUDIO_FORMAT_REGISTRY.get(s, None)
    logger.debug(f"Resolving {s} to pyaudio format {t}.")
    return t
