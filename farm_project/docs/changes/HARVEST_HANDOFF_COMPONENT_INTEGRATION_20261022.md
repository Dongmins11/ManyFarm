# 수확 인계 컴포넌트 운영 연결 — 2026-10-22

기준: Robot3FinalProject/main, feat/harvest-handoff-real-20261018,
4b5c5b13605216d1b8b163ea988805572a6a908a.
수정본을 별도 디렉터리에 구현했다. 사용자 PC 및 원격 저장소에는 적용하지 않았다.

## 구현

- 기존 Node/Mission/Communication/State 구조와 TransferMission 순서를 유지한다.
- 상태에서 공통 파라미터를 변경하지 않는다. 시작 시 설정한 Path/Spin 동작을 조합한 객체를 사용한다.
- 완료된 HarvestTask의 window_id/goal_pose와 진입 시 odom 기준을 보관한다. 12번·14번 노드를 운영 좌표로 사용하지 않는다.
- 진입은 후진 곡선→벽 정렬, 복귀는 후진 이탈→방향 조정→전진 복귀다.
- 전용 controller의 TransferArc/WallAlign/Retreat와 별도 저속 Spin 서버를 구성한다. 기존 StationReverse/일반 Spin 설정은 유지한다.
- 명령 gate는 현재 소유권, 선택한 출력원, 속도 제한, 센서/odom 유효성, 충돌 확인 결과에 따라 명령을 전달하거나 0으로 차단한다. gate를 없애는 설계가 아니다.
- 기존 DOCK_STABLE 대기, 배출, TRANSPORT_CLEAR 대기를 거쳐 복귀한다.
- 현재 DockTransfer 계약은 HarvestTask 완료 후 idle에서 시작한다. 실행 중 작업의 pause/resume 및 다음 window 자동 선택을 추가하지 않았다. 다음 window는 관제의 다음 목표로 받는다.

## 검증 범위

오프라인 컴포넌트/연결 64개, 기존 회귀 58개 통과. 로그는 패키지 루트에 있다.
ROS 의존성을 대체한 테스트 및 정적 컴파일이며 실제 ROS action, lifecycle, TF, 센서, 로봇 주행 검증은 미실행이다.
원본과 충돌하면 쓰기 전에 중단하는 적용 도구를 포함한다. 비교 기준이 다른 PC 변경을 임의로 덮어쓰지 않는다.

## 적용

압축을 프로젝트 밖에 푼다. 아래 프로젝트 경로는 실제 경로와 일치할 때 사용한다.

```bash
unzip ~/Downloads/harvest_handoff_integration_20261022.zip -d ~/Downloads
cd ~/Downloads/handoff_integration
python3 apply.py --project-root /home/eunbi/vmany/main/farm_project
python3 apply.py --project-root /home/eunbi/vmany/main/farm_project --apply
```

첫 명령은 비교만 한다. 두 번째 명령은 전체 비교가 통과해야 적용하며 프로젝트 옆에 handoff-backup-*를 만든다.
충돌이 나오면 해당 파일의 현재 수정과 이 패키지를 병합해야 한다. 강제 적용 옵션은 없다.
기존 워크스페이스에서 ROS 환경을 source한 뒤 기존 절차로 빌드하고 install/setup.bash를 다시 source한다.
기존 harvest.launch.py 실행 인자에 다음 인자를 추가해야 새 기능을 선택한다(기본값은 비활성).

```text
handoff_config:=robot/config/robots/vicpinky/transfer/handoff_components.json
```

real 모드와 navigation 활성화 및 transfer 활성화가 필요하다. 기존 실행과 중복 Nav2를 띄우지 않는다.
실제 launch는 관제 목표를 받을 수 있으므로 읽기 전용 도구와 구분한다.

ROS가 실행된 환경에서 아래 점검 자체는 Action Goal/속도 명령을 발행하지 않는다.

```bash
python3 /home/eunbi/vmany/main/farm_project/robot/tools/transfer/handoff_preflight.py \
  --project-root /home/eunbi/vmany/main/farm_project \
  --output ~/Downloads/handoff_preflight.json
```

## 실제 환경에서 남은 확인

1. 전용 controller/behavior lifecycle 활성화, action 및 goal checker 식별자, 저속 Spin 0.03 설정.
2. 기존 장치 서비스 연결. 기준 파일의 device_services는 빈 맵이다. 실제 PC의 override/서비스 주소를 확인해야 하며 이 패키지는 주소를 만들어 넣지 않는다.
3. odom frame/child_frame, TF, costmap·footprint·scan 유효성. child_frame이 설정 base_frame과 다르면 현재 구현은 거부한다.
4. cmd_vel_nav 발행자가 harvest_motion_server 하나인지 확인. 일반 출력과 인계 출력의 라우팅 확인.
5. 관제 window 도착 위치 허용오차, 진입/벽 정렬/복귀, 취소·타임아웃·장애물·odom 재시작 때 정지 확인.
6. 성공 후 다음 관제 목표 수행과 기존 일반 주행 회귀 확인.

읽기 전용 preflight는 1·2·4의 일부를 점검한다. 통과만으로 3·5·6 또는 실물 운용을 확정하지 않는다.
실물 시험 결과가 확보될 때 운영 확정으로 표시한다.

## 되돌리기

실행 중인 관련 노드를 종료하고 백업의 rollback.json을 확인한다. existed=true 파일은 같은 상대 경로로 복원하고 existed=false 파일은 이번 추가 파일임을 확인 후 삭제한다. 다시 빌드하고 이전 launch 인자로 시작한다. 공유 설정과 사용자 변경을 일괄 git reset하지 않는다.
