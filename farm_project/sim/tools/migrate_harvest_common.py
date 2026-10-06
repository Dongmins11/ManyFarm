"""이전 sim 수확 서버 파일만 백업 후 제거합니다. 공통 서버와 평가 노드는 보존합니다."""
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    if not (root/'robot/ros_ws/src/harvest_robot/harvest_robot/node.py').is_file():
        raise RuntimeError('새 공통 harvest_robot 소스를 먼저 적용하세요.')
    package = Path('sim/ros_ws/src/farm_sim_harvest/farm_sim_harvest')
    targets = [package/(name+'.py') for name in ('node','communication','mission','state_controller','contract')]
    targets.append(Path('sim/ros_ws/install/farm_sim_harvest/lib/farm_sim_harvest/harvest_node'))
    targets.append(Path('sim/ros_ws/install/lib/farm_sim_harvest/harvest_node'))
    existing = [p for p in targets if (root/p).exists() or (root/p).is_symlink()]
    if not existing:
        print('이전 sim 수확 서버 파일 없음. 정리 완료.');return
    backup = root/'sim/runs/patch_backups'/('old_sim_harvest_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.zip')
    backup.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(backup,'w',ZIP_DEFLATED) as archive:
        for relative in existing:
            path = root/relative
            if path.is_symlink():
                archive.writestr(str(relative)+'.symlink',str(path.readlink()))
            else:
                archive.write(path,str(relative))
    for relative in existing:(root/relative).unlink()
    print(f'이전 서버 {len(existing)}개 제거. 백업: {backup}')


if __name__=='__main__':main()
