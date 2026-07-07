from pydantic import BaseModel, field_validator
from tune.shared.util.paths import CONFIG_PATH
import yaml


class ZMQSettings(BaseModel):
    pub_data_uri: str
    pub_control_uri: str
    sub_data_uri: str
    sub_control_uri: str
    sub_poller_timeout_ms: int
    pub_sleep_seconds: float


class AudioSettings(BaseModel):
    buffer_size: int
    channels: int
    samplerate: int


class AnalyzerDefaults(BaseModel):
    sleep_seconds: float


class Config(BaseModel):
    audio_settings: AudioSettings
    analyzer_defaults: AnalyzerDefaults
    zmq_settings: ZMQSettings
    range_presets: dict[str, tuple[float, float]]

    @field_validator("range_presets")
    @classmethod
    def validate_ranges(
        cls, ranges: dict[str, tuple[float, float]]
    ) -> dict[str, tuple[float, float]]:
        for name, (low, high) in ranges.items():
            if high > low:
                raise ValueError(
                    f"Badly formatted range preset in config yaml. Preset {name} has low: {low} and high: {high}"
                )
        return ranges


def _load() -> Config:
    with open(CONFIG_PATH) as file:
        data: dict = yaml.safe_load(file)
    return Config(**data)


config: Config = _load()
