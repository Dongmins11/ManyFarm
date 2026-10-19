"""Load shared description scenery without changing task settings or policy inputs."""
import importlib.util
from pathlib import Path

_path=Path(__file__).resolve().parents[2]/'smartfarm_description/scripts/harvest_visual_scene.py'
_spec=importlib.util.spec_from_file_location('harvest_visual_assets',_path)
_assets=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_assets)
contract=_assets.contract
spawn=_assets.spawn
gray_ground=_assets.gray_ground


def describe(mode):
    if mode=='legacy':return dict(version='legacy',visual_only=True)
    if mode!='greenhouse_v1':raise ValueError(f'Unknown visual scene: {mode}')
    return contract()
