#!/usr/bin/env python3
"""Verify the extracted HCR delivery without importing Isaac or ROS."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    failures = []
    for entry in manifest["files"]:
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            failures.append("Missing/invalid path: " + entry["path"])
        elif path.stat().st_size != entry["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            failures.append("Hash/size mismatch: " + entry["path"])
    workspace = root / "workspace"
    urdf = workspace / "src/smartfarm_description/urdf/transport_robot.portable.urdf"
    if urdf.is_file():
        for mesh in ET.parse(urdf).getroot().iter("mesh"):
            path = (urdf.parent / mesh.get("filename")).resolve()
            if not path.is_relative_to(workspace) or not path.is_file():
                failures.append("Unresolved transport mesh: " + mesh.get("filename"))
    else:
        failures.append("Transport URDF missing")
    peppers = workspace / "src/smartfarm_description/meshes/pepper"
    for name in ("Pepper_Red.usdc", "Pepper_Yellow.usdc", "manifest.json"):
        if not (peppers / name).is_file():
            failures.append("Missing pepper asset: " + name)
    for name in ("fruit_0.jpg", "fruit_1.jpg", "fruit_2.png", "fruit_3.jpg"):
        if not (peppers / "textures" / name).is_file():
            failures.append("Missing pepper texture: " + name)
    if failures:
        print("FAILED\n" + "\n".join(failures))
        return 1
    print(f"PASS: {len(manifest['files'])} files; hashes, transport mesh references and pepper resources")
    print("This verifies delivery integrity, not farm integration or runtime success.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    sys.exit(verify(parser.parse_args().root))
