import logging

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from tune.shared.util.config_loader import get_range_presets

logger = logging.getLogger(__name__)


# Preset frequency ranges used by the tuning controller and range dialog.
PRESETS: dict[str, tuple[float, float]] = get_range_presets()


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
        ("escape", "pop", "Cancel"),
        ("q", "pop", "Close"),
    ]

    def compose(self) -> ComposeResult:
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
        logger.debug(
            "RangePresetScreen showing fmin=%s, fmax=%s", current_fmin, current_fmax
        )

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

    def action_pop(self) -> None:
        """Close the modal without applying changes."""
        self.app.pop_screen()

    def on_mount(self) -> None:
        """Auto-focus the presets list when the modal opens."""
        try:
            self.query_one("#preset_list", OptionList).focus()
        except Exception:
            logger.debug("RangePresetScreen: failed to focus preset list")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        logger.debug(
            "RangePresetScreen.on_button_pressed: button_id=%s", event.button.id
        )
        if event.button.id == "apply_manual_range":
            app = self.app
            try:
                min_input = self.query_one("#modal_min", Input)
                max_input = self.query_one("#modal_max", Input)
            except Exception:
                logger.exception("RangePresetScreen: failed to query min/max inputs")
                self.app.pop_screen()
                return

            logger.debug(
                "Applying manual range: min=%s, max=%s",
                min_input.value,
                max_input.value,
            )
            handler = getattr(app, "handle_manual_range", None)
            if callable(handler):
                handler(min_input.value, max_input.value)
            self.app.pop_screen()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        preset_name = event.option.id
        logger.debug("RangePresetScreen: preset selected: %s", preset_name)
        app = self.app
        handler = getattr(app, "handle_preset_selected", None)
        if callable(handler):
            handler(str(preset_name))
        self.app.pop_screen()
