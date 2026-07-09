from pathlib import Path

SRC_ROOT: Path = Path(__file__).parent.parent.parent
PROJECT_ROOT: Path = SRC_ROOT.parent.parent
CONFIG_PATH: Path = SRC_ROOT / "config.yaml"
VISUALIZER_PATH: Path = SRC_ROOT / "visualizer" / "app.py"
ANALYZER_PATH: Path = SRC_ROOT / "analyzer" / "analyzer.py"
LOG_PATH: Path = PROJECT_ROOT / "logs"
