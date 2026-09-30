"""Open with runpy.run_path() inside the Isaac Sim 5.1 Script Editor."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"sim/tools"))
from scout_dataset.panel import show_panel

show_panel(ROOT)
