"""선택형 시험 설정 생성. 기존 설정/BT는 보존하고 최종 실행 입력을 기록한다."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
import yaml
from .transfer_arc import add_profile

BT_KEYS = ('default_nav_to_pose_bt_xml', 'default_nav_through_poses_bt_xml')

def explicit_checkers(xml, controller):
    tree = ET.fromstring(xml, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    for node in tree.iter('FollowPath'):
        for attr, key in [('progress_checker_id', 'progress_checker_plugins'),
                          ('goal_checker_id', 'goal_checker_plugins')]:
            value = node.get(attr, '')
            ids = controller[key]
            if not value:
                if len(ids) != 1:
                    raise ValueError(f'{attr}: 기존 기본 판정기를 하나로 결정할 수 없습니다.')
                node.set(attr, ids[0])
            elif not value.startswith('{') and value not in ids:
                raise ValueError(f'{attr}: 등록되지 않은 기존 판정기 {value}')
    return ET.tostring(tree, encoding='unicode')

def write_profile(original, folder):
    folder = Path(folder)
    output = add_profile(original)
    baseline = original['controller_server']['ros__parameters']
    bt = output.get('bt_navigator', {}).get('ros__parameters', {})
    generated = []
    for key in BT_KEYS:
        if not bt.get(key):
            raise ValueError(f'{key}: 설치 기본 BT를 추측하지 않습니다. 명시적 BT가 필요합니다.')
        source = Path(bt[key])
        dest = folder / (key + '.xml')
        if source.resolve() == dest.resolve():
            raise ValueError('기존 BT 파일을 덮어쓸 수 없습니다.')
        text = explicit_checkers(source.read_text(), baseline)
        with dest.open('x') as f:
            f.write(text + '\n')
        bt[key] = str(dest.resolve())
        generated.append(dest)
    # 추가한 ID와 시험 BT 경로 외에는 모든 기존 설정이 동일해야 한다.
    restored = deepcopy(output)
    cp = restored['controller_server']['ros__parameters']
    for key, name in [('controller_plugins','TransferArc'),
                      ('goal_checker_plugins','transfer_arc_goal'),
                      ('progress_checker_plugins','transfer_arc_progress')]:
        cp[key].remove(name)
        del cp[name]
    for key in BT_KEYS:
        restored['bt_navigator']['ros__parameters'][key] = original['bt_navigator']['ros__parameters'][key]
    if restored != original:
        raise ValueError('기존 주행 설정 보존 검사 실패')
    nav = folder / 'arc_nav2.yaml'
    with nav.open('x') as f:
        yaml.safe_dump(output, f, sort_keys=False)
    return nav, generated + [nav]

def finalize_manifest(folder, files):
    folder = Path(folder)
    path = folder/'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['arc_execution_inputs'] = {}
    for item in files:
        item = Path(item)
        data = item.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        snapshot = folder/'arc_final_inputs'/item.name
        snapshot.parent.mkdir(exist_ok=True)
        with snapshot.open('xb') as f:
            f.write(data)
        manifest['arc_execution_inputs'][str(item)] = {
            'sha256': digest, 'snapshot': str(snapshot.relative_to(folder))}
        # 기존 prepare가 남긴 environment 기록도 최종 실행 내용으로 맞춘다.
        for key in list(manifest.get('files', {})):
            if key == str(item) or str(item).endswith('/'+key):
                manifest['files'][key] = digest
                old_snapshot = manifest.get('snapshots', {}).get(key)
                if old_snapshot:
                    (folder/old_snapshot).write_bytes(data)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
