import json
import logging
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
APP_CONFIG_PATH = ROOT / "config.json"


def _load_layout() -> dict:
    """Load analyzer layout configuration from config.json.

    Returns a dict with boolean keys for all 7 visualization options.
    """
    cfg: dict = {}
    if APP_CONFIG_PATH.is_file():
        try:
            cfg = json.loads(APP_CONFIG_PATH.read_text("utf-8"))
        except Exception:
            logger.exception("AnalyzerLayoutScreen: failed to read config.json")
            cfg = {}

    layout = cfg.get("analyzer_layout", {})
    return {
        "show_main_spectrum": bool(layout.get("show_main_spectrum", True)),
        "show_beat_scatter": bool(layout.get("show_beat_scatter", True)),
        "show_envelope": bool(layout.get("show_envelope", True)),
        "show_beat_history": bool(layout.get("show_beat_history", True)),
        "show_main_spectrogram": bool(layout.get("show_main_spectrogram", False)),
        "show_beat_spectrogram": bool(layout.get("show_beat_spectrogram", False)),
        "show_pitch_scatter": bool(layout.get("show_pitch_scatter", False)),
    }


def _save_layout(new_layout: dict) -> None:
    """Persist analyzer_layout section to config.json, preserving others.

    Also auto-detects whether beat detection should be enabled based on
    whether any beat-related visualizations are selected.
    """
    cfg: dict = {}
    if APP_CONFIG_PATH.is_file():
        try:
            cfg = json.loads(APP_CONFIG_PATH.read_text("utf-8"))
        except Exception:
            logger.exception(
                "AnalyzerLayoutScreen: failed to read config.json for saving; overwriting"
            )
            cfg = {}

    cfg["analyzer_layout"] = {
        "show_main_spectrum": bool(new_layout.get("show_main_spectrum", True)),
        "show_beat_scatter": bool(new_layout.get("show_beat_scatter", True)),
        "show_envelope": bool(new_layout.get("show_envelope", True)),
        "show_beat_history": bool(new_layout.get("show_beat_history", True)),
        "show_main_spectrogram": bool(new_layout.get("show_main_spectrogram", False)),
        "show_beat_spectrogram": bool(new_layout.get("show_beat_spectrogram", False)),
        "show_pitch_scatter": bool(new_layout.get("show_pitch_scatter", False)),
    }

    # Auto-detect beat detection: enable if any beat-related visualization is enabled
    beat_related_graphs = [
        new_layout.get("show_beat_scatter", False),
        new_layout.get("show_envelope", False),
        new_layout.get("show_beat_history", False),
        new_layout.get("show_beat_spectrogram", False),
    ]
    beat_detection_needed = any(beat_related_graphs)

    # Load or create tuning config
    tuning_config_rel = cfg.get("analyzer", {}).get(
        "config", "analyzer/tuning_config.json"
    )
    tuning_config_path = ROOT / tuning_config_rel

    tuning_cfg = {}
    if tuning_config_path.is_file():
        try:
            tuning_cfg = json.loads(tuning_config_path.read_text("utf-8"))
        except Exception:
            logger.exception("Failed to read tuning config")

    # Update beat detection setting
    tuning_cfg["beat_detection_enabled"] = beat_detection_needed

    # Save tuning config
    try:
        tuning_config_path.parent.mkdir(parents=True, exist_ok=True)
        tuning_config_path.write_text(
            json.dumps(tuning_cfg, indent=2), encoding="utf-8"
        )
        logger.info(
            "Auto-set beat_detection_enabled=%s based on selected graphs",
            beat_detection_needed,
        )
    except Exception:
        logger.exception("Failed to save tuning config")

    APP_CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    logger.info("Analyzer layout updated: %s", cfg["analyzer_layout"])


class AnalyzerLayoutScreen(ModalScreen):
    """Modal screen for choosing which graphs the analyzer shows at startup."""

    BINDINGS = [
        ("escape", "dismiss", "Cancel"),
        ("q", "dismiss", "Close"),
        ("up", "focus_previous", "Previous"),
        ("down", "focus_next", "Next"),
    ]

    def compose(self) -> ComposeResult:  # type: ignore[override]
        logger.debug("AnalyzerLayoutScreen.compose() called")
        layout = _load_layout()

        with Vertical(id="analyzer_layout_modal"):
            yield Static("Analyzer graphs (apply then restart analyzer)")

            yield Checkbox(
                "Main spectrum (always recommended)",
                value=layout["show_main_spectrum"],
                id="chk_main_spectrum",
            )
            yield Checkbox(
                "Beat scatter (freq vs depth)",
                value=layout["show_beat_scatter"],
                id="chk_beat_scatter",
            )
            yield Checkbox(
                "Envelope (bottom-left)",
                value=layout["show_envelope"],
                id="chk_envelope",
            )
            yield Checkbox(
                "Beat history (bottom-right)",
                value=layout["show_beat_history"],
                id="chk_beat_history",
            )
            yield Checkbox(
                "Main spectrogram (FFT heatmap)",
                value=layout["show_main_spectrogram"],
                id="chk_main_spectrogram",
            )
            yield Checkbox(
                "Beat spectrogram (envelope FFT)",
                value=layout["show_beat_spectrogram"],
                id="chk_beat_spectrogram",
            )
            yield Checkbox(
                "Pitch scatter (confidence vs freq)",
                value=layout["show_pitch_scatter"],
                id="chk_pitch_scatter",
            )

            yield Button("Apply", id="apply_layout")

    def action_focus_previous(self) -> None:
        """Move focus to previous widget."""
        self.focus_previous()

    def action_focus_next(self) -> None:
        """Move focus to next widget."""
        self.focus_next()

    def on_mount(self) -> None:
        """Auto-focus the first checkbox."""
        try:
            self.query_one("#chk_main_spectrum", Checkbox).focus()
        except Exception:
            logger.debug("AnalyzerLayoutScreen: failed to focus main checkbox")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        logger.debug("AnalyzerLayoutScreen.on_button_pressed: %s", event.button.id)
        if event.button.id == "apply_layout":
            try:
                main_cb = self.query_one("#chk_main_spectrum", Checkbox)
                scatter_cb = self.query_one("#chk_beat_scatter", Checkbox)
                env_cb = self.query_one("#chk_envelope", Checkbox)
                hist_cb = self.query_one("#chk_beat_history", Checkbox)
                main_spec_cb = self.query_one("#chk_main_spectrogram", Checkbox)
                beat_spec_cb = self.query_one("#chk_beat_spectrogram", Checkbox)
                pitch_scatter_cb = self.query_one("#chk_pitch_scatter", Checkbox)
            except Exception:
                logger.exception("AnalyzerLayoutScreen: failed to query checkboxes")
                self.app.pop_screen()
                return

            new_layout = {
                "show_main_spectrum": main_cb.value,
                "show_beat_scatter": scatter_cb.value,
                "show_envelope": env_cb.value,
                "show_beat_history": hist_cb.value,
                "show_main_spectrogram": main_spec_cb.value,
                "show_beat_spectrogram": beat_spec_cb.value,
                "show_pitch_scatter": pitch_scatter_cb.value,
            }
            _save_layout(new_layout)
            self.app.pop_screen()
