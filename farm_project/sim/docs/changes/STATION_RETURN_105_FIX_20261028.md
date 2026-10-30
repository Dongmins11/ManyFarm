# 스테이션 최종 회전 105 수정

기준 `18d0e00`, 2026-10-28. 사용자 “마지막 회전 105 해결” 요청. 시뮬 운송 설정만 변경하며 실물/공통 주행 코드는 수정하지 않는다.

## 원인과 기존 동작의 관계

`TransportStateController.station_return_mode=navigation_only`는 마커 도킹을 건너뛰지만, `NavigationMoveState → Navigator.navigate(request.xy, request.yaw) → RPP FollowPath`의 목표 방향 맞추기와 도착/정지 검사는 수행한다. 최종 목표는 (2, 13.25), 방향 −π/2다. 북향으로 도착하면 거의 180°를 돌아야 한다.

기존 `SimpleProgressChecker`는 XY가 0.1m 이동해야 진행으로 인정하고, 10초간 이 조건을 충족하지 못하면 실패시킨다. 회전명령 0.3rad/s에서 180° 회전은 이상적으로도 10.47초이며, 실제 가감속과 추종에는 시간이 더 필요하다. 앞선 attempt15는 실제로 회전하면서도 이 검사로 `error_code=105`가 발생했다.

이 플러그인·0.1m·10초·회전속도는 `ea25693`부터 동일하다. 최근 AMCL 수정이 진행 검사 값을 바꾼 것은 아니다. 기존 복귀 성공 사례와 이번 운송의 도착 방향/회전량이 같다는 증거는 없으므로, 모든 기존 복귀에 문제가 있었다고 일반화하지 않는다. 이번 오류는 마커 인식 실패가 아니다.

## 최소 변경

- `sim/ros_ws/src/farm_sim_config/config/nav2_transport.yaml`: `SimpleProgressChecker → PoseProgressChecker`, `required_movement_angle=0.5rad`(Nav2 기본값)를 명시한다. 10cm 이동 **또는** 약28.65° 회전을 진행으로 인정한다.
- 병진 임계값 0.1m/정체 제한10초/회전속도0.3rad/s/목표 위치·방향 허용치/최종 정지 검사는 유지한다. 이번 실행과 attempt15 생성 Nav2 파일 차이는 플러그인·각도 항목 둘뿐이다.
- `run_sorter_cycle_trial.py`: 원본 실물 설정 대비 검사기/각도 차이를 fixture에 기록한다. 실물 설정을 동일하게 변경했다고 보고하지 않는다.
- 새 검사기도 목표를 향한 각도 감소 자체를 판정하지는 않는다. 충분한 회전을 운동으로 인정하며, 기존 전체 실행 제한과 도착 검사가 계속 적용된다.

근거: [Nav2 Jazzy PoseProgressChecker](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_controller/plugins/pose_progress_checker.cpp), [SimpleProgressChecker](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_controller/plugins/simple_progress_checker.cpp). 실제 설치된 `/opt/ros/jazzy/lib/libpose_progress_checker.so`로 아래 검사를 수행했다.

## 검사

설치된 실제 플러그인에 시뮬 시각을 지정한 C++ 검사 7개 통과:

- XY 고정·15초 연속 회전에서 기존 검사는 실패, 새 검사는 통과(±π 경계 포함).
- reset 시 기준 재설정, 10초 넘는 완전 정지 실패.
- 5mm/0.05rad 미세 흔들림으로 정체를 숨기지 못함.
- 정상 직진 통과, 직진 후 정지 실패.

최초 임시 검사 빌드는 라이브러리 검색 경로 누락으로 링크 실패했다. 설치 경로를 find_library로 지정한 후 빌드·실행 통과. 런타임 제어 코드 문제는 아니며 빌드 로그는 raw에 남긴다. 기존 지도/씬 검사 5개, Python 문법 검사와 diff 검사도 통과했다.

공유 자료: `sim/docs/test_results/20261028_station_return_105/`. C++ 재실행:

```bash
source /opt/ros/jazzy/setup.bash
cmake -S sim/docs/test_results/20261028_station_return_105 -B /tmp/station-progress-build
cmake --build /tmp/station-progress-build -j2
ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET ROS_LOG_DIR=/tmp/station-progress-logs \
  /tmp/station-progress-build/check_progress
```

## 실제 시험

Domain13/SUBNET, CPU60Hz/render30Hz, 앞선 attempt15와 같은 농장 도킹→기존 과실 투입→선별→ReturnToStation 분리 시험. 원시 로그 `sim/runs/station_return_105_20261028/attempt01/`. 예찰·수확·운송 인계를 처음부터 수행하는 전체 사이클 시험은 아니다.

실제 attempt01 결과:

- `BucketUnload SUCCESS → SortBatch SUCCESS → ReturnToStation SUCCESS / NONE / docked=true`. 전체 runner exit0. 업무 저널에 `STATION_PARKED / marker_stage=SKIPPED_SIM_POLICY` 기록. 마커 도킹을 수행한 것이 아니라 기존 시뮬 주차 완료 의미다.
- 마지막 회전 명령 구간은 시뮬246.77~259.17초, **12.40초**였다. 이전의10초 병진 검사 제한을 넘어서도 회전 진행으로 인정하여 완료했다. 실제105 및 `Failed to make progress` 기록 없음.
- 도킹 요청부터 복귀 결과까지 실제260.56초, 복귀 요청부터159.84초. 예찰·수확·인계는 포함하지 않은 분리 시험이다.
- 마지막 발행 map pose 목표 오차1.91cm/3.85°. 결과 시각에7.4ms 이내로 대응한 실제 시뮬 차체는 목표 오차약3.89cm/8.74°다. **105 해결과 실제 최종 방향 정밀도는 별개**다. 회전명령 종료 후 차체가 추가 회전한 잔차와 추정 차이가 남아 있으므로, 정확한 자세 복귀까지 해결됐다고 보고하지 않는다. 정답 좌표는 평가에만 사용했다.
- AMCL425표본 평균3.70cm/최대7.06cm. 빨강1개 선별, 노랑1개 미검출 잔류는 이전과 동일하고 이번 수정 범위 밖이다.
- 실행 프로세스 모두 종료 확인. probe/transport/Isaac/adapter/sorter exit0. 전체 종료 SIGINT 때 precision은 KeyboardInterrupt로−2, gate는 이미 종료된 ROS context에서 zero publish를 시도해1로 종료했다. **액션 성공 이후 정리 오류**이며 업무 실패와 구분하여 로그 보존한다. 모든 프로세스가 정상 exit0였다고 보고하지 않는다.

이번 실제 시험1회에서 해당105 해결 확인. 전체 예찰→수확→인계→선별→양측복귀 연속 검증은 아직 미실행. 변경은 미커밋·미푸시다.

## 복원

운송 YAML의 검사기를 `SimpleProgressChecker`로 되돌리고 각도 항목을 제거한다. AMCL·지도 수정은 유지한다. 단, 긴 제자리 회전에서 기존 105가 재발할 수 있다.

## 변경 파일 전달

[변경 파일 ZIP](../../runs/station_return_105_20261028_changes.zip). 기준18d0e00 위에 적용하는 현재 파일 스냅샷이며 원본입력/무관한파일/원시전체로그는 포함하지 않는다.

```bash
cd /home/ysy/main/farm_project
unzip -o sim/runs/station_return_105_20261028_changes.zip -d .
```
