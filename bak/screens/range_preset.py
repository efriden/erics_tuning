import json
import logging
from pathlib import Path
from typing import Iterable

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
APP_CONFIG_PATH = ROOT / "config.json"

# Fallback presets used if config.json is missing or invalid
_FALLBACK_PRESETS: dict[str, tuple[float, float]] = {
    "Full Range": (20.0, 5000.0),
    "Piano Full": (25.0, 4500.0),
    "Bass Register": (25.0, 300.0),
    "Middle Register": (120.0, 1200.0),
    "Treble Register": (400.0, 5000.0),
    "A440 Focus": (420.0, 460.0),
    "Temperament": (200.0, 800.0),
    "Beat Detection": (100.0, 1000.0),
    "Unison Tuning": (80.0, 2000.0),
    "Cello": (57.0, 240.0),
    "Guitar": (75.0, 350.0),
}


def _load_presets() -> dict[str, tuple[float, float]]:
    """Load presets from config.json, falling back to built-in defaults.

    The config format is::

        {
          "presets": {
            "Name": [fmin, fmax],
            ...
          }
        }
    """
    presets: dict[str, tuple[float, float]] = {}

    if APP_CONFIG_PATH.is_file():
        try:
            cfg = json.loads(APP_CONFIG_PATH.read_text("utf-8"))
            raw = cfg.get("presets", {})
            if isinstance(raw, dict):
                for name, pair in raw.items():
                    if (
                        isinstance(pair, (list, tuple))
                        and len(pair) == 2
                    ):
                        try:
                            fmin = float(pair[0])
                            fmax = float(pair[1])
                        except (TypeError, ValueError):
                            continue
                        presets[str(name)] = (fmin, fmax)
        except Exception:
            logger.exception("Failed to load presets from config.json; using fallbacks")

    if not presets:
        logger.debug("RangePresetScreen: no presets in config.json; using fallbacks")
        presets = _FALLBACK_PRESETS.copy()

    logger.debug("RangePresetScreen: loaded %d presets", len(presets))
    return presets


# Preset frequency ranges used by the tuning controller and range dialog.
PRESETS: dict[str, tuple[float, float]] = _load_presets()


class RangePresetScreen(ModalScreen):
    """Modal screen for setting range via presets or manual values.

    - Top: preset list using OptionList (auto-focused)
    - Bottom: manual min/max frequency inputs with an Apply button

    Esc or `q` close without changes; selecting a preset or applying
    manual values will update the main app's config via the duck-typed
    ``handle_manual_range`` / ``handle_preset_selected`` callbacks on
    ``self.app``.
    """

    BINDINGS = [
        ("escape", "dismiss", "Cancel"),
        ("q", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:  # type: ignore[override]
        logger.debug("RangePresetScreen.compose() called")

        # Get current values from the hosting app if available
        app = self.app
        current_fmin = 20.0
        current_fmax = 5000.0
        cfg = getattr(app, "config", None)
        if isinstance(cfg, dict):
            try:
                current_fmin = float(cfg.get("fmin", current_fmin))
                current_fmax = float(cfg.get("fmax", current_fmax))
            except Exception:
                logger.debug("Failed to parse current fmin/fmax from app.config")
        logger.debug("RangePresetScreen showing fmin=%s, fmax=%s", current_fmin, current_fmax)

        with Vertical(id="range_preset_modal"):
            yield Static("Choose a preset or enter a custom range (Esc/q to cancel)")

            # Preset list at the top
            yield Static("Presets:")
            options: list[Option] = []
            for name, (fmin, fmax) in PRESETS.items():
                label = f"{name} ({int(fmin)}-{int(fmax)} Hz)"
                options.append(Option(label, id=name))
            yield OptionList(*options, id="preset_list")

            # Manual range inputs at the bottom
            yield Static("Manual range:")
            yield Label("Min Freq (Hz):")
            yield Input(str(current_fmin), id="modal_min", placeholder="e.g. 20.0")
            yield Label("Max Freq (Hz):")
            yield Input(str(current_fmax), id="modal_max", placeholder="e.g. 5000.0")
            yield Button("Apply manual range", id="apply_manual_range")

    def action_dismiss(self) -> None:  # type: ignore[override]
        """Close the modal without applying changes."""
        self.app.pop_screen()

    def on_mount(self) -> None:  # type: ignore[override]
        """Auto-focus the presets list when the modal opens."""
        try:
            self.query_one("#preset_list", OptionList).focus()
        except Exception:
            logger.debug("RangePresetScreen: failed to focus preset list")

    def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore[override]
        logger.debug("RangePresetScreen.on_button_pressed: button_id=%s", event.button.id)
        if event.button.id == "apply_manual_range":
            app = self.app
            try:
                min_input = self.query_one("#modal_min", Input)
                max_input = self.query_one("#modal_max", Input)
            except Exception:
                logger.exception("RangePresetScreen: failed to query min/max inputs")
                self.app.pop_screen()
                return

            logger.debug("Applying manual range: min=%s, max=%s", min_input.value, max_input.value)
            handler = getattr(app, "handle_manual_range", None)
            if callable(handler):
                handler(min_input.value, max_input.value)
            self.app.pop_screen()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:  # type: ignore[override]
        preset_name = event.option.id
        logger.debug("RangePresetScreen: preset selected: %s", preset_name)
        app = self.app
        handler = getattr(app, "handle_preset_selected", None)
        if callable(handler):
            handler(str(preset_name))
        self.app.pop_screen()
