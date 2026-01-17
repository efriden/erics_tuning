import json
import logging
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
APP_CONFIG_PATH = ROOT / "config.json"


def _load_log_paths() -> tuple[Path, Path]:
    """Load TUI and analyzer log paths from config.json with safe defaults."""
    cfg: dict = {}
    if APP_CONFIG_PATH.is_file():
        try:
            cfg = json.loads(APP_CONFIG_PATH.read_text("utf-8"))
        except Exception:
            cfg = {}

    logging_cfg = cfg.get("logging", {})
    tui_log_rel = logging_cfg.get("tui_log", "logs/tuning.log")
    analyzer_log_rel = logging_cfg.get("analyzer_log", "logs/analyzer.log")

    tui_log_path = ROOT / tui_log_rel
    analyzer_log_path = ROOT / analyzer_log_rel

    # Ensure directory exists so rotating handlers elsewhere work
    tui_log_path.parent.mkdir(parents=True, exist_ok=True)
    analyzer_log_path.parent.mkdir(parents=True, exist_ok=True)

    return tui_log_path, analyzer_log_path


LOG_PATH, ANALYZER_LOG_PATH = _load_log_paths()


class LogsScreen(ModalScreen):
    """Modal screen showing the last lines from TUI and analyzer logs."""

    MAX_LINES = 200

    # Allow quick dismissal via Esc or q
    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:  # type: ignore[override]
        """Build an empty shell; fill in content on mount.

        This keeps compose cheap and avoids doing log I/O twice if the
        layout is recalculated.
        """
        logger.debug("LogsScreen.compose() called")
        yield Static("Logs (newest at bottom, Esc/q to close)", id="log_title")
        yield Static("(loading logs…)", id="log_view")

    def action_dismiss(self) -> None:  # type: ignore[override]
        """Close the modal."""
        self.app.pop_screen()

    def on_mount(self) -> None:  # type: ignore[override]
        """Load log contents once the screen is mounted."""
        logger.debug("LogsScreen.on_mount() reading last %s lines", self.MAX_LINES)
        lines: list[str] = []
        for label, path in (("tui", LOG_PATH), ("analyzer", ANALYZER_LOG_PATH)):
            if path.is_file():
                try:
                    file_lines = path.read_text("utf-8").splitlines()[-self.MAX_LINES :]
                    logger.debug("LogsScreen: read %d lines from %s log", len(file_lines), label)
                    lines.append(f"== {label} log: {path.name} ==")
                    lines.extend(file_lines)
                    lines.append("")
                except Exception as exc:  # pragma: no cover - log read failures are rare
                    logger.warning("LogsScreen: failed to read %s log: %s", label, exc)
                    lines.append(f"!! failed to read {label} log: {exc}")
                    lines.append("")
            else:
                logger.debug("LogsScreen: %s log file not found at %s", label, path)
                lines.append(f"== {label} log: (no file yet) ==")
                lines.append("")

        text = "\n".join(lines) if lines else "(no logs yet)"
        self.query_one("#log_view", Static).update(text)
