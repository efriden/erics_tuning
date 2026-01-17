#!/bin/bash
# Launcher script for frequency analyzer

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment and run Textual TUI controller
source "$DIR/venv/bin/activate"
python "$DIR/tuning.py"
