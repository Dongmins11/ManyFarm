# 수확 구동 진단 패치

cmd_vel=0.12m/s인데 바퀴 odom≈0으로 보고된 상황을 진단한다. Nav2 설정을 완화하거나 바퀴 게인을 추측으로 변경하지 않는다. 정확한 원인은 아직 미확정이다.

## 적용

실행 중인 전체 launch를 종료하고 프로젝트 루트에서 실행한다.

```bash
mkdir -p sim/runs/patch_backups
cp sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/run_fleet.py sim/runs/patch_backups/run_fleet_before_drive_diag.py
unzip -o ~/Downloads/farm_harvest_drive_diagnostics_20261006.zip -d .
cat sim/docs/changes/DRIVE-DIAG-20261006-012.md >> sim/docs/CHANGELOG.md
(cd sim/ros_ws && colcon build --symlink-install --packages-select farm_sim_runtime)
source scripts/env.sh sim
ros2 launch farm_sim_runtime all.launch.py project_root:="$PWD" isaac_python:="$HOME/isaac/env_isaaclab/bin/python" harvest:=true device:=0
```

이전 main 호출 누락 수정도 포함한다. 이전 TF 어댑터 수정은 유지해야 한다. 예찰과 수확 코드/실물 설정은 변경하지 않는다.

## 시험 및 전달

이전과 동일한 첫 window HarvestTask를 한 번 전송한다. 성공/실패까지 기다린 뒤 아래로 로그를 묶어 전달한다. 관절 명령을 직접 발행하지 않는다.

```bash
tar -czf sim/runs/harvest_drive_diagnostics.tar.gz -C sim/runs drive_diagnostics
```

터미널에도 [drive_diag]가 초당 로봇별 한 번 출력된다. 파일에는 실제 pose도 기록한다. 센서 로그 전체를 수집할 필요는 없다.

- transport.received=0: 명령이 Isaac 수신 코드에 도달하지 않음. ROS 구독/UDP를 확인.
- received 증가, accepted=0: session/순서/유효시간 검사 등 gate 거절을 확인.
- accepted 증가, applied_cmd=0: 마지막 수락 시각과 명령 유효시간을 확인.
- applied_cmd≈[0.12,0], target_joint_velocity≈[-1.46,-1.46], measured_joint_velocity≈0: 관절 명령 전달 이후 Isaac 제어·관절·물리 제약을 조사.
- 관절은 회전하지만 실제 T_world_base가 고정: 접촉·미끄러짐·차체 고정 등을 조사.

target_joint_velocity는 제어 함수 입력에서 계산한 값이다. PhysX 내부에 저장된 target의 직접 조회가 아니다. setup JSON의 drive 설정은 실제 실행 stage의 관절 속성이다.

오프라인으로 계측 함수와 제공 USD를 검증했다. 실제 Isaac 주행은 미검증이다.
