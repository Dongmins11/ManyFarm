#!/usr/bin/env python3
"""Download official reference CAD into sorting outputs; not a joint model."""

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
DEST = ROOT / "outputs/sorting_station/hcr_sim/source_cad"
SOURCES = {
    "hcr3a": "https://hanwharobotics.com/bbs/download?bbsSeq=133&attachSeq=115",
    "controller": "https://hanwharobotics.com/bbs/download?bbsSeq=133&attachSeq=118",
}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, url in SOURCES.items():
        path = DEST / (name + ".zip")
        if not path.exists():
            with urlopen(url, timeout=60) as response:
                path.write_bytes(response.read())
        folder = DEST / name
        folder.mkdir(exist_ok=True)
        with ZipFile(path) as archive:
            for item in archive.infolist():
                target = (folder / item.filename).resolve()
                if not target.is_relative_to(folder.resolve()):
                    raise ValueError("Unsafe archive path")
            archive.extractall(folder)
        manifest[name] = dict(
            url=url,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            files=[str(p.relative_to(DEST)) for p in folder.rglob("*") if p.is_file()],
        )
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(DEST)


if __name__ == "__main__":
    main()
