from dataclasses import dataclass, field
from tune.shared.util.type_registry import NumpyScalarType


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


@dataclass
class PanelSettings:
    name: str
    title: str = "untitled"
    y_range: tuple[int, int] | None = None
    x_range: tuple[int, int] | None = None
    labels: dict[str, str] = field(default_factory=dict)
    show_x_grid: bool = True
    show_y_grid: bool = True
    line: str | None = None
