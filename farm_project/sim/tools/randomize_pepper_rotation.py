"""Run via runpy.run_path() in Isaac Sim Script Editor, with the farm open."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"sim/tools"))
from scout_dataset.stage import load_fruit_rotation_settings, randomize_current_stage_and_save

# Same seed reproduces the offsets; change seed for a different arrangement.
# Original rotations are preserved and repeated calls never accumulate offsets.
randomize_current_stage_and_save(**load_fruit_rotation_settings(ROOT))
