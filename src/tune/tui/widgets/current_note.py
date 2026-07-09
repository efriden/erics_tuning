from textual.css.query import NoMatches
from textual.containers import Vertical
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static, Label
from textual_pyfiglet import FigletWidget
from tune.shared.types.pitch import Pitch
from tune.shared.transponder.transponder import Transponder
import numpy as np

UPDATES_PER_SECOND: int = 20


class CurrentNote(Static):
    _transponder: Transponder
    pitch = reactive(Pitch.empty())

    def __init__(self) -> None:
        super().__init__()
        self.pitch = Pitch.empty()
        self._transponder = Transponder(subs=["pitch"])

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Currently detected pitch:")
            yield FigletWidget("nan", colors=["$accent"])

    def watch_pitch(self, new_pitch: Pitch, old_pitch: Pitch) -> None:
        try:
            self.query_one(FigletWidget).update(str(new_pitch))
        except NoMatches:
            pass

    def get(self) -> None:
        raw = self._transponder.get("pitch")
        if raw is None or not isinstance(raw, np.ndarray):
            return
        self.pitch = Pitch.unpack(raw)

    def on_mount(self) -> None:
        self.start()

    def start(self) -> None:
        self._transponder.start()
        self.set_interval(1 / UPDATES_PER_SECOND, self.get)
