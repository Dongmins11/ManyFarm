# SEC01 실제 윈도우 → 관제 인계 요청 검증

2026-10-28 KST. 사용자 “다음 작업해”에 따른 D-068 후속 작업이다. 기준 main `ea25693650a9a61d8bbcfcf6e02f6ac6889a97a1`와 직전 미커밋 통합을 유지했다. 원격 fetch/commit/push는 이번에 수행하지 않았다.

## 현재 결론

실제 HarvestTask 완료 → 제공된 Frontend의 원본 handoff_worker → 실제 DockTransfer 접수까지 연결했다. 마지막 시험에서 후진 원호는 완료했고, 벽 정렬 중 측정 속도 상한을 넘어 중단했다. **DOCK_READY, 운송 도킹, 배출, 이격, 차체 복귀 및 전체 사이클은 아직 통과하지 않았다.**

이번 실패에 Nav2 105는 없다. 최신 실패는 `DEVICE_FAILED`: 0.02m/s 전진 명령에 시뮬 바퀴 속도가 0.0250533m/s로 올라 원본 0.025m/s 감시 상한을 넘었다. 이후 정지 명령이 도착하기 전 바퀴 0.0271105m/s, 실제 차체 위치 차분 약0.0266729m/s까지 확인했다. 단순 odom 수치 튐만으로 설명할 수 없으며, 시뮬 바퀴 PI 보정의 과도응답을 우선 점검해야 한다. 월드 위치는 이 분석에만 사용했다.

실물에서도 같은 측정 속도를 넘으면 같은 감시가 동작한다. 이것만으로 실물도 같은 과속을 보인다고 결론 내릴 수는 없다. 이번에는 시뮬 전용 바퀴 보정기(kp=1, ki=4)가 원래 관절 목표 약−0.2433rad/s를 초기 약−0.6rad/s까지 보정한 기록이 있다. 원본 감시를 완화하거나 바퀴 보정 계수를 임의 조정하지 않았다.

## 시험 범위와 결과

조건: ROS_DOMAIN_ID=13, ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET, Isaac headless, CPU 물리60Hz. 실물 수확 인계 기준 `e135cdef9462276cc25d9fa336f084e2dcac72e4`의 원호·벽·속도감시 수치를 유지했다.

기존 성공 예찰 `sim/runs/sec01_16_round3_20261023_151213/SEC01_attempt_0002/result.json`의 첫 윈도우 `7621d3500623_SEC01_W001`을 사용했다. 목표는 map (−6.015,9.29252972957), yaw=−π/2, expected=1이다. 초기 배치만 목표15cm 전방 접근 위치에 두었다. 실행 중 순간이동, 완료 윈도우 조작, 정답 좌표의 제어 주입은 없다. 새 task_id로 실제 주행·팔 액션을 실행했다. 신규 예찰/SEC01 전체 성능 시험이 아니며, 과거 expected를 현재 과실 정답으로 평가하지 않았다.

| 시도 | 실제 결과 | 조치/해석 |
|---|---|---|
| 1 | 준비 중 수동 중단, Goal 전송 없음 | 생성 프로필에 status_reporting이 없어 상태 준비 대기가 계속됨. 기존 원본 상태 보고 설정 연결 |
| 2 | 윈도우 주행 성공, 팔 ARM_LINK_LOST | 초기 영상 처리 중2초 통신 감시 초과. 원본 timeout 유지 |
| 3 | HarvestTask SUCCESS, 인계 후진 중 DEVICE_FAILED | 순간 전진 측정0.0053316m/s > 원본 후진단계 전진 상한0.005m/s. TF 대기/재개 반복 관측 |
| 4 | HarvestTask SUCCESS, 후진 원호 완료, 벽 정렬 중 DEVICE_FAILED | 전진 측정0.0250533m/s > 벽 단계0.025m/s. 실제 차체 과속도 확인 |

시도3·4의 수확 액션은 expected=1, harvested=0, failed_count=0, `student_no_reachable_targets_arms_stowed`다. 카메라 측정 대상이 팔 실행 범위 밖이어서 시도 가능한 대상이 없었다. 사용자 합의대로 수량 불일치를 액션 실패로 만들지 않았고, 인계 expected_count에는 이번 실제 harvested=0을 전달했다. 따라서 유실/실수령량 성능 검증으로 확대하지 않는다.

## 이번 변경

모든 실행 코드 변경은 sim 안이다. 공통 FSM/제어기, 실물 설정, USD, 모델 가중치, Frontend 원본은 이번 작업에서 변경하지 않았다.

| 파일 | 변경과 이유 |
|---|---|
| `sim/tools/prepare_harvest_handoff.py` | 원본 status_reporting을 생성 실행 묶음에 연결. sim map_id 선택. 원본 대비 상태 보고 내용 동일 확인 |
| `sim/tools/run_handoff_window_trial.py` | 기존 성공 예찰 결과로 독립 실행 묶음 생성, CPU/Domain13 확인, 소유 프로세스만 정리, 프레임/속도 계측 |
| `sim/tools/probe_handoff_window.py` | 실제 HarvestTask 완료 후 수정하지 않은 Frontend 워커의 stdin 명령 계약으로 DockTransfer 요청. 원시 상태/feedback/result/오류 보존 |
| `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/student_session.py` | 첫 검출 초기화를 연결 준비 때 수행하고 결과는 버림. 초기 PNG 압축 강도만 낮추고 NPZ는 무압축 저장. 저장·검출 wall 시간 계측 |
| `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/ros_adapter.py` | 동일 표본 TF를 odom보다 먼저 발행. 좌표/측정시각/공통 판단 불변 |

TF 발행 순서는 서로 다른 DDS topic의 수신 순서를 보장하지 않는다. 시도4에도 TF 미래 조회 대기1회와 벽 관측 준비 대기1회가 있었다. 이를 TF 문제 완전 해결로 보고하지 않는다. 시도3의 소스 계측 추가는 아직 설치본에 반영되지 않았으므로 그 시도의 세부 INVENTORY_TIMING은 없다. 시도4는 재빌드 후 설치본 및 실제 로그에서 계측/초기화 적용을 확인했다.

## 팔 시작 지연 개선 근거

- 저장된 실제 영상으로 분리 측정: 최초 detector.predict 0.9574초, 후속0.0265/0.0240초. 생성자 준비 완료만으로 최초 추론 초기화가 끝나는 것은 아니었다.
- 기존 PNG+압축NPZ 저장0.5929초 → 낮은 PNG 압축+무압축NPZ 저장0.0871초. NPZ 약5.49MB →16.57MB. 픽셀/배열은 완전히 동일함을 확인했다. 저장 공간 증가는 의도된 비용이다.
- 실제 시험 CAMERA_INVENTORY 구간 최대 arm 처리1.5061초 →0.1306초, 최대 단일 프레임1.5906초 →0.2071초. 다른 시도 간 비교이며 평균 전체 수확 속도 개선율은 아니다.
- 시도2의 단절에는 프레임 세부 계측이 없으므로 최초 검출만이 유일한 원인이었다고 확정하지 않는다. 시도4에서는 원본 통신/팔 제한시간을 유지하고 ARM_LINK_LOST 없이 완료했다. 반복 안정성 검증은 남아 있다.

## 관제 연동의 정확한 범위

`Frontend/dashboard/backend/handoff_worker.py` 원본을 별도 시험 ledger로 실행했다. 원본 `start_dock` 명령, UUID, Action 결과 검증을 그대로 사용했고 실제 ROS 상태도 수신했다. 로봇이 보고하지 않은 DOCK_READY/DOCK_STABLE/TRANSFER_COMPLETE/TRANSPORT_CLEAR를 만들거나 대신 전송하지 않았다.

HTTP API/브라우저 화면, 관제 교통 서버 연계, 전체 TransportPickup 연쇄는 이번에 실행하지 않았다. 기존 운영 관제 ledger를 덮어쓰지 않았다. 교통 활성화는 여전히 false이며 D-068의 components+traffic 동시출력 차단을 유지한다. 기본 일반 수확 프로필도 transfer=false 그대로다.

시험 도구는 DOCK_READY까지 통과하면 명시적 취소·정지를 검사하도록 제한되어 있다. 이번에는 모두 그 전에 실패하여 이 취소 성공 경로도 미검증이다. 이것을 배출/복귀까지 검증하는 E2E 도구로 사용하면 안 된다.

## 검증 및 자료

- 시뮬 관련 기존 검사72개 PASS, 추가 subtest41개 PASS. Student32개는 Isaac Python3.11, ROS 연결/감시40개는 ROS Python3.12에서 실행했다. 초기 system Python에 torch가 없어 수집 실패한 뒤 올바른 환경에서 다시 통과했다.
- `farm_sim_devices` colcon build PASS. 최초 detector 초기화 약0.99초가 실제 Isaac 시작 로그에 기록됨.
- Frontend HTTP 검사: system Python의 fastapi 부재로 수집 실패, 미실행. 이를 워커/DDS 실행 성공과 구분한다. 새 의존성은 설치하지 않았다.
- 직전 연결 패치에 포함된 robot 파일8개는 byte 동일 확인. 원호/벽/감시·기본 프로필/장면/모델 hash 보존 자료 포함.
- 시험을 위해 시작한 프로세스 종료 확인. SIGINT 중 ROS Destroyable/KeyboardInterrupt와 SDK 종료 예외는 원시 로그에 보존했다. 최상위 launch exit0을 모든 자식의 정상 종료로 해석하지 않는다.

공유 자료: `sim/docs/test_results/20261028_handoff_window/`. summary.json, wall_overspeed_evidence.json, configuration_check.json, validation.json, 각 시도의 결과/설정/관제 원시 로그/drive 계측/팔 trace를 포함한다. 큰 원시 로그는 gzip이다. 전체 원시 자료는 `sim/runs/handoff_window_20261028/`, 팔 원본 영상은 summary.json의 isaac_session에 대응하는 `sim/runs/robotarm/student/<session>/`에 있다.

재실행(각 시도는 새로운 결과 폴더 사용):

```bash
cd ~/main
source /opt/ros/jazzy/setup.bash
source farm_project/robot/ros_ws/install/local_setup.bash
source farm_project/sim/ros_ws/install/local_setup.bash
export ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
python3 farm_project/sim/tools/run_handoff_window_trial.py \
  farm_project/sim/runs/handoff_window_recheck/attempt1 \
  --scout-result farm_project/sim/runs/sec01_16_round3_20261023_151213/SEC01_attempt_0002/result.json
```

다음 조치는 공통 감시를 유지한 시뮬 바퀴 저속 과도응답 개선이다. 변경 전후에 후진·정지·2cm/s 벽 접근의 명령/encoder/실제 차체 속도를 비교하고, 이후 DOCK_READY 및 운송 이벤트 연결을 검증해야 한다. 아직 속도보정 값을 변경하지 않았다.

이번 파일 패치: `sim/runs/handoff_window_20261028_patch.zip` (직전 통합/연결 패치 적용 상태용).

```bash
unzip -o ~/Downloads/handoff_window_20261028_patch.zip -d ~/main/farm_project
```

되돌리기: 이번 sim 두 모듈의 최초 추론/저장 방식/발행순서 변경만 되돌리고 farm_sim_devices 재빌드. 생성기 상태 보고 추가와 신규 시험 도구는 별도 제거 가능하다. 이전 인계 가상장치/공통 통합 수정은 보존한다. 이번 결과는 삭제하지 않는다. 미커밋·미푸시.
