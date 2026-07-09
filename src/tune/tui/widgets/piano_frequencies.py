import logging
import librosa
from textual.app import ComposeResult
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

logger = logging.getLogger(__name__)


class PianoFrequencies(Static):
    """Modal screen listing equal-tempered piano note frequencies (A0–C8).

    Data is generated via librosa.midi_to_hz / midi_to_note with A4=440 Hz.
    """

    def compose(self) -> ComposeResult:
        yield Static("Equal-tempered piano A0–C8 (Esc to close)")
        options: list[Option] = []
        # MIDI 21 = A0, 108 = C8 (inclusive) -> 88 keys
        for midi in range(21, 109):
            note = librosa.midi_to_note(midi)
            freq = librosa.midi_to_hz(midi)
            label = f"{midi:3d}  {note:4s}  {freq:8.3f} Hz"
            options.append(Option(label, id=str(midi)))
        yield OptionList(*options, id="piano_freqs")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        pass
