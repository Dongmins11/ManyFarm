#!/usr/bin/env python3
"""Expand Xacro with relative mesh URIs (portable folder) or absolute URIs."""
import argparse
from pathlib import Path
import xacro

p = argparse.ArgumentParser()
p.add_argument('--output', type=Path)
p.add_argument('--absolute-meshes', action='store_true')
p.add_argument('--single-arm', action='store_true')
p.add_argument('--legacy-lids', action='store_true', help='Preserve the pre-CAD floor asset for legacy comparisons')
a = p.parse_args()
pkg = Path(__file__).resolve().parents[1]
out = a.output or pkg/'urdf/harvest_robot.urdf'
out = out.resolve()
import os
mesh_root = str(pkg/'meshes') if a.absolute_meshes else os.path.relpath(pkg/'meshes', out.parent)
doc = xacro.process_file(str(pkg/'urdf/harvest_robot.urdf.xacro'), mappings={
    'mesh_root': mesh_root,
    'detailed_lids': 'false' if a.legacy_lids else 'true',
    'assembly': str(pkg/'config/assembly.yaml'),
    'enable_arm_2': 'false' if a.single_arm else 'true',
})
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(doc.toprettyxml(indent='  '))
print(out)
