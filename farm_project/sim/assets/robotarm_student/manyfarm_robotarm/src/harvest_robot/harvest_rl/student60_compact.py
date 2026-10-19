"""Export audited training samples without retaining every full-resolution image.

Never deletes source data. The set runner may remove only its own scratch after
this copy and its file hashes have been verified.
"""
from pathlib import Path
import shutil
import json
from .student60_data import digest,read


def verify_compact(root):
    root=Path(root);cert=read(root/'compact_certificate.json')
    if cert.get('schema')!='student60_audited_compact_v1':raise ValueError('Unknown compact archive')
    for name,sha in cert['files'].items():
        p=root/name
        if not p.resolve().is_relative_to(root.resolve()) or digest(p)!=sha:raise ValueError('Compact archive changed: '+name)
    v=read(root/'verification.json')
    if not v['audit_passed'] or not v['final_runtime_audit_complete']:raise ValueError('Incomplete native audit')
    return cert


def export_compact(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination.exists() or destination.is_relative_to(source):raise ValueError('Require new separate compact output')
    v=read(source/'verification.json')
    if not v['audit_passed'] or not v['final_runtime_audit_complete']:raise ValueError('Audit native captures before export')
    retained=set()
    for episode in source.glob('episode_*'):
        phases={}
        for p in sorted(episode.glob('[0-9]*.json')):
            n=read(p);phases.setdefault(n['phase'],[]).append(n)
        for group in phases.values():
            n=group[len(group)//2]
            for camera in n['cameras'].values():
                path=Path(camera['raw_capture']).resolve()
                if not path.is_relative_to(source):raise ValueError('Raw capture outside this run')
                retained.add(path.relative_to(source))
    destination.mkdir(parents=True)
    files={};original_bytes=0;kept_bytes=0
    for p in source.rglob('*'):
        if not p.is_file():continue
        relative=p.relative_to(source);original_bytes+=p.stat().st_size
        if relative.parts[0]=='fruit_assets':continue
        if 'raw_captures' in relative.parts and p.suffix=='.npz' and relative not in retained:continue
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        files[str(relative)]=digest(target);kept_bytes+=target.stat().st_size
    cert=dict(schema='student60_audited_compact_v1',source=str(source),native_images_fully_audited_before_export=True,
        all_native_images_retained=False,retention='all 20Hz policy samples/labels, all native metadata, one native frame per camera/phase',
        original_bytes=original_bytes,retained_bytes=kept_bytes,files=files)
    (destination/'compact_certificate.json').write_text(json.dumps(cert,indent=2))
    verify_compact(destination)
    return cert
