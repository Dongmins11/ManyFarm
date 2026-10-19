"""Verify every packaged file before relocating caches; no simulation or robot motion."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
manifest=json.loads((ROOT/'handoff/MANIFEST.json').read_text())
errors=[]
for item in manifest['files']:
    p=ROOT/item['path']
    if not p.is_file():errors.append('Missing: '+item['path']);continue
    if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:errors.append('Hash mismatch: '+item['path'])
if errors:raise SystemExit('\n'.join(errors))
print('Verified',len(manifest['files']),'files; source commit',manifest['base_commit'])
