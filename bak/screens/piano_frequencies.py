import logging

import librosa
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

logger = logging.getLogger(__name__)


class PianoFrequenciesScreen(ModalScreen):
    """Modal screen listing equal-tempered piano note frequencies (A0–C8).

    Data is generated via librosa.midi_to_hz / midi_to_note with A4=440 Hz.
    """

    def compose(self) -> ComposeResult:  # type: ignore[override]
        logger.debug("PianoFrequenciesScreen.compose() called")
        yield Static("Equal-tempered piano A0–C8 (Esc to close)")
        options: list[Option] = []
        # MIDI 21 = A0, 108 = C8 (inclusive) -> 88 keys
        for midi in range(21, 109):
            freq = float(librosa.midi_to_hz(midi))
            note = librosa.midi_to_note(midi, octave=True, cents=False)
            label = f"{midi:3d}  {note:4s}  {freq:8.3f} Hz"
            options.append(Option(label, id=str(midi)))
        logger.debug("PianoFrequenciesScreen generated %d piano frequencies", len(options))
        yield OptionList(*options, id="piano_freqs")

    def on_mount(self) -> None:  # type: ignore[override]
        """Log when the screen is mounted."""
        logger.debug("PianoFrequenciesScreen.on_mount()")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:  # type: ignore[override]
        # Purely informational for now; just close on selection
        logger.debug("PianoFrequenciesScreen: selected MIDI note %s", event.option.id)
        self.app.pop_screen()
