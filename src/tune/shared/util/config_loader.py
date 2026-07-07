from typing import Any
from pyaudio import paFloat32, paInt16, paInt32
import yaml
import numpy as np

from tune.shared.util.paths import CONFIG_PATH
from tune.shared.util.type_registry import (
    resolve_builtin_type,
    resolve_numpy_dtype,
    resolve_pyaudio_format,
    NumpyScalarType,
    PyAudioFormat,
)

from dataclasses import dataclass
from logging import getLogger, Logger

logger: Logger = getLogger(name=__name__)


@dataclass
class AudioSettings:
    buffer_size: int
    pyaudio_format: int
    n_channels: int
    samplerate: int


@dataclass(frozen=True)
class TopicSpec:
    label: str
    payload_type: type
    dtype: NumpyScalarType | None = None
    ndim: int | None = None
    max_shape: tuple | None = None


def get_settings(header: str | None = None) -> dict:
    logger.debug("Loading settings toml")
    try:
        with open(CONFIG_PATH, "r") as file:
            full_data = yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Failed to load from config yaml. Exception: {e}")
        return {}

    if not header:
        return full_data

    filtered_data: dict[str, Any] | None = full_data.get(header)
    if not filtered_data:
        logger.error(f"Faulty header '{header}' supplied.")
        return {}

    return filtered_data


def get_indexed_topic_specs() -> dict[str, TopicSpec]:
    specs = get_topic_specs()
    return {spec.label: spec for spec in specs}


def get_topic_specs() -> list[TopicSpec]:
    settings: dict = get_settings("topics")
    specs: list[TopicSpec] = []
    for label, data in settings.items():
        s_payload_type: str | None = data["payload_type"]
        if s_payload_type == "ndarray":
            s_dtype = data.get("dtype", None)
            payload_type: type = np.ndarray
            dtype: NumpyScalarType | None = resolve_numpy_dtype(s_dtype)
            if not dtype:
                raise ValueError(
                    f"Topic {label}. Topics specced as ndarray needs to also specify a valid dtype."
                )
            ndim: int = data["ndim"]
            specs.append(
                TopicSpec(
                    label=label,
                    payload_type=payload_type,
                    dtype=dtype,
                    ndim=ndim,
                )
            )
            continue
        payload_type: type | None = resolve_builtin_type(s_payload_type)
        if not payload_type:
            raise ValueError(f"Type {s_payload_type} not recognized by type registry")
        specs.append(TopicSpec(label=label, payload_type=payload_type))

    return specs


def get_audio_settings() -> AudioSettings:
    settings: dict = get_settings("audio_settings")

    settings["pyaudio_format"] = resolve_pyaudio_format(settings["pyaudio_format"])

    return AudioSettings(**settings)


def get_range_presets() -> dict[str, tuple[float, float]]:
    data: dict[str, list[float]] = get_settings("range_presets")

    range_presets: dict[str, tuple[float, float]] = {
        key: tuple(values) for key, values in data.items()
    }

    return range_presets


def get_zmq_settings() -> dict:
    settings: dict = get_settings("zmq")
    return settings
