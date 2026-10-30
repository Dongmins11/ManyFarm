# 새 예찰 전체 사이클 실패 원인 분석

기준: main `18d0e00` 및 기존 미커밋 변경. 2026-10-30 사용자 요청: 시험을 유지하면서 실패마다 원인 분석 수행. 운영 코드·성공 기준·물리 설정은 이번 분석에서 변경하지 않았다.

## 확인한 실패

시험: `sim/runs/fresh_full_cycle_20261030/`. 1~5차 실패, 분석 시작 후 6차 진행 중. 전체 성공 미확인. 각 시도는 요청대로 새 시뮬·새 예찰부터 다시 시작한다.

| 시도 | 실패 단계 | 직접 원인 |
|---|---|---|
| 1 | 인계 성공 후 원호 복원 | Nav2 106, `arc deviation exceeded` |
| 2·3 | 인계 자세 진입 원호 | Nav2 106, `arc deviation exceeded` |
| 4 | 인계 성공 후 원호 재진입 방향 정렬 | Spin SUCCESS 뒤 정지 검사에서 1.0543° > 1° |
| 5 | 인계 자세 진입 원호 끝점 | `곡선 경로 위치 오차 초과` |

106은 설치된 `nav2_msgs/action/FollowPath.action`의 `NO_VALID_CONTROL`이다. 이번 로그의 구체 원인은 충돌이나 일반 주행105가 아니라 원호 위치·방향 정합 오차다. 5차는 같은 종류의 원호 오차를 Python 감시에서 검출했으므로 106으로 합산하지 않는다.

## 1~3차: costmap 수신 지연 → 정지 → 원호 오차 증가

공통 `harvest_robot/handoff_runtime.py::_read`는 입력의 ROS 시각 나이와 마지막 수신 이후 실제 경과시간을 각각 0.5초와 비교한다. `_pause_output`은 만료 시 0속도를 발행한다. 실제 로그는 `receive_expired=true`, `header_invalid=false`였다.

| 시도 | 인계 시작 후 costmap 수신 간격 > 0.5초 | 최대 실제 간격 | 최초 초과 구간의 메시지 시각 간격 |
|---|---:|---:|---:|
| 1 | 23 | 0.6980초 | 0.2167초 |
| 2 | 1 | 0.5115초 | 0.2167초 |
| 3 | 1 | 0.5031초 | 0.2333초 |
| 4 | 17 | 0.6016초 | 0.2167초 |
| 5 | 2 | 0.5980초 | 0.2167초 |

이는 느린 시뮬에서 실제시간 감시가 정지를 유발한 직접 증거다. 통신 감시를 무조건 ROS 시간으로 바꿔도 된다는 결론은 아니다. 마지막 수신 이후 시간은 실제 노드 정지 검출 역할도 있으므로 별도 검토가 필요하다. 인계 설정은 기본 local_costmap 갱신 10Hz, 발행 5Hz를 가져온다. 이번에는 실행 중 파라미터를 변경하지 않았다.

2차의 원호 출발 기준 근사 재구성:

| 시뮬 시각 | 적용 명령 v / w | 측정 v / w | odom 정합 오차 | 실제 차체 정합 오차 |
|---:|---|---|---:|---:|
| 1564.567 | -0.010 / +0.126 | -0.0117 / +0.0908 | 4.52mm | 4.65mm |
| 1565.117 | 0 / 0 | -0.0064 / +0.0144 | 6.60mm | 6.79mm |
| 1565.650 | 0 / 0 | -0.0041 / -0.0174 | 10.04mm | 10.22mm |

3차도 정지 후 odom 약10.32mm/실제 약10.43mm로 같은 패턴이다. 차체는 계속 후진하지만 회전은 먼저 줄거나 반대로 움직여 원호가 요구하는 위치·방향 관계가 무너진다. 이 두 건은 AMCL map 위치의 수 cm 점프 없이 실제 차체 운동만으로 재현된다.

주의: 여기서 오차는 곡선과의 최단 수직거리가 아니라 **현재 방향각에 해당하는 원호의 기대 위치까지 거리**다. 2차 1565.650초의 원 중심 기준 반경 오차는 약0.98mm지만 방향각을 함께 검사한 오차는 약10.04mm다. 판정식 자체는 공통 코드이며 sim 전용 판정이 아니다.

1차 복원에서도 costmap 만료 뒤 0명령, 잔여 전진/반대 회전, odom 정합 오차 1cm 초과 순서가 확인된다. 이 건의 실제/odom 원호 재구성은 누적 차이가 있으므로 2·3차처럼 동일하다고 확대하지 않는다.

관련 구현:

- `robot/ros_ws/src/farm_arc_controller/include/farm_arc_controller/arc_math.hpp`: 현재 방향에 해당하는 기대 위치와 거리 검사.
- `robot/ros_ws/src/farm_arc_controller/src/arc_controller.cpp`: 1cm 한계 전달, 예외를 NoValidControl로 변환.
- `robot/ros_ws/src/farm_navigation/farm_navigation/transfer_arc.py`: Python 감시에서도 같은 방향 기반 위치 검사.
- `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/wheel_servo.py`: 전체 0명령에서는 PI 적분을 비우고 관절 velocity target=0, 물리 drive가 제동한다.
- `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/base_sim.py`: 관절 명령 적용과 실제 바퀴 회전량 측정.

확정 범위는 '정지 시 차체 감속 응답이 원호 정합 오차를 키움'까지다. 물리 감쇠·좌우 구동 응답·부하 중 각 기여도는 분리 시험이 필요하다. 현재 통합시험을 방해하는 별도 Isaac 인스턴스는 띄우지 않았다.

과거 `WHEEL_STOP_DIAGNOSIS_20261028.md`의 축소 물리 시험에서는 감쇠10배가 개선하지 못했고 속도 solver 반복4→16이 잔여 회전을 약59~62% 줄였다. 당시 운영 반영은 하지 않았다. 이번 과실 적재·원호 정지 조건과 동일하지 않으므로 이번 실패가 해결된 증거로 재사용하지 않는다. 후속 물리 대조 후보는 감쇠 무작정 증대보다 이 기존 solver 비교를 우선한다.

## 4차: Spin 완료 후 잔여 회전

`harvest.log` 1434~1438 인근: Spin 시작, 약0.03rad 회전 요청, Spin SUCCESS. 이후 `check_reentry`가 위치0.000237m/한계0.01m, 방향0.018401rad/한계0.017453rad로 거절한다.

진단 표본에서 원호 출발 대비 방향은 1585.950초 89.484°(회전 명령0.03rad/s), 1586.533초 90.757°(0명령, 실측0.0261rad/s), 1587.133초 91.078°(0명령)다. 목표90°를 통과한 뒤에도 정지까지 추가 회전한다. 1초 주기 표본 기반이므로 최종 검사 시각의 정확한1.0543°와 표본1.078°를 혼동하지 않는다.

이것은 과거 벽 정렬0.5°/0.8° 조건과 다른 단계다. `handoff_planning.py`의 재진입 방향 기준1°와 `handoff_navigation.py::_align`의 정지 후 검증에 걸린다. 기준 완화는 하지 않았다.

## 5차: 끝점 정지 후 위치 오차 증가

2회 costmap 만료를 거친 후 끝점에 도달했다. 1256.517초에는 0명령, odom 정합 오차8.74mm지만 실측 후진속도는 약6.3mm/s다. 1257.050초에 오차10.62mm, 이후 약13.45mm까지 늘었다. 원호 종료·정지 경계에서 오차가 커지는 점을 확인했으며, 정확한 Nav2 성공 시점과 Python 감시 실패 시점을 더 비교해야 한다.

## 지속 분석과 산출물

`sim/tools/analyze_cycle_failures.py`는 10초마다 시험 status를 읽어 새로 완료된 실패 시도를 분석한다. 로봇/ROS 명령은 보내지 않는다. 이미 처리한 시도는 반복 파싱하지 않으며 시험 SUCCEEDED/STOPPED에서 종료한다. 분류되지 않은 실패는 `unclassified`로 남겨 원인 확정을 가장하지 않는다.

실행:

```bash
cd /home/ysy/main/farm_project
python3 -u sim/tools/analyze_cycle_failures.py sim/runs/fresh_full_cycle_20261030 --watch
```

저장 위치:

- `sim/runs/fresh_full_cycle_20261030/failure_analysis/attempt_NNN/diagnosis.json`: 실패 분류·원문·단계·odom/실제 위치 근사 재구성.
- 같은 폴더 `evidence.md`: 원인과 원본 로그 행 번호.
- 같은 폴더 `drive_handoff.jsonl`: 인계 이후 구동 원본 표본.
- `failure_analysis/watch_status.json`: 분석기 갱신 시각·처리한 시도 목록.
- `failure_analysis/costmap_gaps.json`: 이번 수동 정밀 분석의 1~5차 costmap 간격.

재구성 원점은 capture 직전 구동 표본이다. controller가 사용한 정확한 TF 원점이 아니며 진단 주기는 약1실시간초다. 원호 이외의 wall/retreat 구간 값을 원호 실패 증거로 사용하지 않는다. 원시 로그는 보존했다.

검증: 기존 완료 실패5건에 실제 도구 실행, 1·2·3·5차 arc_deviation/4차 reentry_heading 분류 및 근거 파일 생성 확인, Python 문법 검사. 새 동작·실물 시험 없음. 다음 우선순위는 costmap의 정상적인 시뮬 발행과 수신 감시 조건 정합, 0명령 이후 차체 제동 응답 검증이다. 공통 변경은 적용 전에 별도 검토·승인이 필요하다. 커밋/푸시하지 않았다.
