# 실물 스테이션 라이다 도킹 — PC 구현·검증

## 기준·승인·범위

- 기준 HEAD `e135cdef9462276cc25d9fa336f084e2dcac72e4`, 브랜치 `feat/harvest-handoff-real-20261018`. 기존 복귀·Jetson·관제 등의 미커밋 변경을 보존했다. 원격 조회/commit/push/merge 없음.
- 사용자 “ㄱㄱ”는 앞서 제시한 공통 벽 컴포넌트 확장 및 실물 복귀 연결의 PC 구현·검증 승인이다. 로봇 배포·빌드·기동·재기동·주행 명령은 제외한다.
- 인계 업무 코드/설정과 `sim/`은 이번에 수정하지 않았다. 사용자 `sim/` 수정 금지에 따라 이번 변경 이력은 이 문서와 PROJECT_STATE/DECISIONS/CODEX_HANDOFF에 기록했다.
- 기존 복귀 런치 기본 동작은 도킹 미선택이다. `docking_config` 인자를 명시할 때만 별도 서버/컴포넌트를 조립한다.

## 측정 기준

2026-10-29 사용자 완료 자세 정지 기록 `20261029_185143_427562432`를 사용했다.

| 방향 | 사용자 외곽 간격 | base_footprint 원점-벽 수직거리 | 법선 각도 |
|---|---:|---:|---:|
| 뒤 | 22cm | 0.5202428321492166m | -178.49116745010653도 |
| 왼쪽 | 25.4cm | 0.49622036468337655m | 90.02902376007826도 |
| 오른쪽 | 24.6cm | 0.4940746216006377m | -89.37846908638033도 |

벽을 직각/평행 또는 좌우 동일 간격으로 강제하지 않는다. 인계의 +2.45도 보정이나 절대 지도좌표를 목표로 복사하지 않는다. 최종 앞뒤/좌우/방향 허용치는 사용자 미확정이므로 설정에 `null`로 보존했다. 미확정 설정을 명시 선택하면 launch 조립에서 오류를 알리고 노드를 실행하지 않는다. 기존 도킹 미선택 실행에는 영향 없다.

## 컴포넌트·변경 파일

모든 소스 경로는 `robot/ros_ws/src/` 아래다.

| 파일 | 변경 책임 |
|---|---|
| `farm_navigation/farm_navigation/wall_observation.py` | 기존 WallTracker 재사용. 후방 경계 분할 영역, 선택형 벽 법선 추적 영역, 동일 scan 세 벽의 목표 자세 계산 |
| `farm_wall_controller/include/farm_wall_controller/wall_control.hpp` | 기본 OFF `station_docking` 모드. 후진 극좌표 자세 오차 P 제어와 앞뒤/좌우/방향/정지 완료 판정 |
| `farm_wall_controller/include/farm_wall_controller/wall_input.hpp` | 선택 설정과 별도 `dock_target` 관측 연결 |
| `farm_wall_controller/src/wall_plugins.cpp` | 선택 모드에서 음의 선속도 지원. 기존 실제 Nav2 footprint 예측 충돌 검사 유지 |
| `farm_common/farm_common/station_return.py` | `_mission_docked()` 결과 훅. 기존 sim=true/일반 real=false 기본 의미 유지 |
| `harvest_robot/harvest_robot/station_docking.py` (신규) | 설정·서버 조립, 최신 scan 1개 비동기 처리, PoseProvider/Nav2Client/Navigator/MotionMonitor 연결 및 출력 소유권 관리 |
| `harvest_robot/harvest_robot/station_return_states.py` | 기존 비동기 상태 구조에 DockReturnState 연결 |
| `harvest_robot/harvest_robot/station_return_mission.py` | 도킹 진입 전 태그 세션 종료, 도킹 실행 및 성공/취소/실패 정리 |
| `harvest_robot/harvest_robot/station_return_real.py` | 실물 선택 컴포넌트 연결 및 완료 결과 전달 |
| `harvest_robot/launch/station_return.launch.py` | 명시 선택 시 `/harvest_01/station_docking` 전용 controller_server/lifecycle 조립 |
| `robot/config/robots/vicpinky/station_docking.yaml` (프로젝트 기준, 신규) | 측정 기준·관측 선택 설정·미확정 허용치. 인계 설정은 공통 제어 기본값으로 읽기만 함 |

시험 파일: `farm_wall_controller/test/test_station_docking.cpp`, 해당 CMake 등록, `harvest_robot/test/test_station_docking.py`, `station_docking_nav2_trial.py`, 기존 `test_station_return_real.py`의 도킹 결과·취소·정리 실패 회귀 추가.

호출 순서: 준비 → 기존 18번 후진 복귀/정지 → DockReturnState → 세 벽 목표 갱신/FollowPath → 정지 후 같은 벽 목표 오차 확인 → cleanup → Action 결과. State.enter는 I/O를 예약하고 반환하며 Controller가 완료 큐를 받아 전환한다. 기존 인계 미션/서버는 호출하지 않는다.

세 벽 거리 차이를 법선에 투영해 하나의 2D 목표 이동량을 구하고, 기준/현재 법선의 각도 차이로 목표 방향을 구한다. 결과는 동일 시각 odom으로 변환해 PoseStamped로 전용 서버에 전달한다. 이 메시지는 벽 한 면이 아니라 도킹 목표 자세이며 기존 `wall_observation`과 토픽을 분리했다.

컨트롤러는 후진 진행 방향(yaw+pi)의 극좌표 오차로 선속도/각속도를 계산한다. 두 출력을 같은 비율로 제한해 조향 곡률을 보존하며 자동 전진 복구를 추가하지 않는다. 위치가 허용치에 들어오면 최종 방향 정렬 후 실제 정지·기존 dwell을 확인한다. 기존 인계의 시작점 기준 20cm/15도 이동 한도는 스테이션 모드에는 적용하지 않는다. 기존 관측 최신성, 실행시간, Nav2 진행·충돌 검사 및 취소/정지는 유지한다. 임의의 18번 진입 오차 문턱이나 세 벽 각각의 별도 도착 조건은 추가하지 않았다.

도킹 후보 접근은 0.02m/s·0.05rad/s 상한과 기존 P 계수를 출발점으로 삼고 목표 방향 계수 `kp_terminal=0.3`을 사용한다. 접근 최소 선속도는 0으로 두어 위치 근처에서 출력을 함께 줄인다. 실물 저속 구동/마찰/잔류 속도는 미검증이다. 기존 전진·후진 복귀·인계 속도 설정은 그대로다.

## 이번 직접 검증

- `/tmp/station_docking_install`에 farm_wall_controller PC 별도 빌드 성공. 운영 install 덮어쓰기 없음.
- CTest 2개 실행 파일 통과: 기존 wall_control 회귀 및 신규 90개 폐루프 조합(앞뒤4/9/15cm, 좌우0/±2/±4cm, 방향0/±10도, 관측 흔들림 유무), 정지·신선도·잘못된 성공 방지.
- Python 복귀/도킹 65개 + 기존 벽 관련 33개 통과.
- 실제 기록 295프레임 전체 추출, 초기 안정화4개 제외291개 목표 생성. 최대 목표 오차 앞뒤0.695mm/좌우0.297mm/각도0.0978도. 기록 자기 일관성 검증이지 실물 접근 정확도 검증이 아니다.
- 실제 Nav2 controller_server/WallController/WallGoalChecker/voxel costmap을 PC domain231·LOCALHOST·CycloneDDS에서 실행했다. ROS 센서/odom은 가상 입력이다.
- 9cm 전방·좌우+2cm 시작: 완료 약17.49초, 최종 오차 앞뒤4.95mm/좌우0.34mm/방향0.92도. 9cm 전방·좌우-4cm·방향+10도 시작: 약36.24초, 최종4.99mm/0.71mm/0.97도. **5mm/5mm/1도는 시험 fixture이며 운영 허용치가 아니다.**
- 가상 벽과 설정 footprint에 사방2cm padding을 더한 외곽의 최소 간격: 위 두 시험 약12.54cm/5.96cm. 실제 주변 물체/센서 장착 오차에 대한 보증이 아니다.
- 가상 장애물은 Nav2 충돌 오류106으로 차단, 취소는 ActionInterrupted로 종료. 각 경우 cleanup 후 최종 출력0 확인.
- 초기에 PC DDS 연결/TF 누락 및 지연으로 실패한 시험은 성공으로 계산하지 않았다. 가상 TF 구성을 보완하고 CycloneDDS/LOCALHOST를 명시했다. 관측 처리 도중 기존 유효시간이 지나면 최신 scan으로 넘기도록 연결부 수정.
- 큰 횡오차 시험에서 차체 고정 영역에 모서리가 섞여 실패한 뒤, 기존 odom 벽 법선을 따라 관측 영역을 회전하는 스테이션 선택 옵션을 추가했다. 영역 폭/직선 지지율/잔차 기준을 완화하지 않고 재시험 성공.

## 남은 항목·실행·원복

- 최종 허용치 확정과 실물 도킹 시험은 남아 있다. PC 시험은 실제 저속 구동, 캐스터, 속도 평활기, 센서 가림 및 라이다 설치 오차를 검증하지 않았다.
- 현 로봇에는 아무 파일도 배포하지 않았다. launch/프로세스/주행 명령을 보내지 않았다.
- 도킹 설정을 선택하는 PC launch 인자는 `docking_config:=<확정 설정 경로>`다. 현재 저장한 null 설정은 실행용으로 사용할 수 없다. 사용자 허용치 확정 전 임의 수치로 바꾸지 않는다.
- 기존 launch에서 `docking_config` 미지정이면 이전 복귀 그대로이며 docked=false다. 실물 도킹 선택 후 정렬·정지·cleanup까지 성공한 경우에만 docked=true, 실패·취소·정리 실패는 false다.
- PC 산출물은 `/home/eunbi/vmany_artifacts/station_docking_pc_20261030/`에 보존한다. 빌드/직접 시험 로그, 측정 재현, 시험별 JSON/trace, 변경 전 파일 사본을 포함한다.
- 원복은 이번 선택형 확장/결과 훅/실물 연결만 변경 전 사본과 대조해 되돌리고 신규 도킹 설정·모듈·시험만 제거한다. 기존 미커밋 복귀 코드 전체를 Git HEAD로 복원하지 않는다. 로봇 원복 작업은 필요 없다.


### 2026-10-30 도킹 완료 허용치 승인 반영
사용자 “오케이 일단 그렇게 해보자”에 따라 실물 도킹 선택 설정의 앞뒤/좌우 허용치를 각각 0.005m, 방향 허용치를 0.017453292519943295rad(1도)로 확정했다. 정지 속도와 0.5초 유지 조건은 기존값을 유지한다. 이전 절의 null/미확정은 당시 기록이며 현재 설정은 확정값이다. 도킹 미선택 기본 실행은 유지한다. 이번 수정은 설정·해당 시험·문서만이며 기존 인계·sim/·주행 제어 코드는 변경하지 않았다. 로봇 배포/재기동·commit/push/원격 조회 없음.

- 기준 HEAD는 e135cdef9462276cc25d9fa336f084e2dcac72e4이며 기존 미커밋 변경을 보존했다.
- 변경 파일: robot/config/robots/vicpinky/station_docking.yaml, harvest_robot/test/test_station_docking.py 및 위 상태/결정/인계 문서.
- 이번 직접 검증: ROS Jazzy와 PC workspace 환경에서 소스 경로를 우선하여 pytest test_station_docking.py 실행, 9개 통과. 승인 설정 로드, 누락 허용치 거절, 완료 오차 판정 및 기존 기하/FSM 시험 확인. 실물 주행과 Nav2 동적 시험은 이번에 재실행하지 않았다.
- 조건 비교에서 확인한 남은 문제: 도킹 관측 대기 시간을 WaitingProgressChecker에 전달하는 대기 시계 연결이 없어 진행 없음 판정에 포함될 수 있다. 도킹에서 사용하지 않는 align_exit의 설정 검사도 남아 있다. 이번 허용치 확정은 이 로직의 수정 승인이 아니므로 변경하지 않았다. 실물 저속 구동과 완료 정확도도 미검증이다.
- 원복: 이번 설정의 허용치 세 항목만 null로 되돌리면 이전 미확정 상태가 된다. 기존 미커밋 소스 전체를 되돌리지 않는다.


### 2026-10-30 확정 허용치 PC 통합 재시험
- 사용자 “그럼 테스트 돌려봐야지” 요청으로 승인 YAML을 직접 load_config로 읽는 임시 시험 스크립트를 사용했다. 로봇 배포/기동/주행 없음. PC localhost/domain231/CycloneDDS, 실제 Nav2 플러그인과 가상 센서/odom이다.
- 정상 시작(앞9cm/좌우+2cm/방향0도): 17.44초, 최종 앞뒤4.923mm/좌우0.319mm/방향0.964도, 완료 후 출력0.
- 오차 시작(앞9cm/좌우-4cm/방향+10도): 36.19초, 최종 앞뒤4.994mm/좌우0.714mm/방향0.973도, 완료 후 출력0.
- 충돌: Nav2 오류106으로 중단, 출력0. 취소: ActionInterrupted, 출력0.
- 관측 단절: 시작3초 뒤 scan 발행 중단, 마지막 비영점 명령3.436초. 이후 정지 유지했지만 14.70초에 종료(오류105, Failed to make progress). 기존에 확인한 대기 시계 연결 누락을 실제 Nav2에서 재현했다. 이는 정상 대기/복귀 성공이 아니라 알려진 결함 재현이다.
- Python 도킹/복귀 47개 통과. 기존 PC 빌드 CTest2 통과(90개 폐루프 포함). C++ 폐루프 fixture는 timeout120초여서 이 90개 모두가 운영40초 내 완료한다는 근거가 아니다. 위 실제 Nav2 두 수렴 시험은 설정의40초를 유지했다.
- 최초 실행은 샌드박스 로그 경로/네트워크 제한으로 실패하여 ROS_LOG_DIR=/tmp와 로컬 통신 허용으로 다시 실행했다. 해당 환경 실패를 제어 실패로 집계하지 않는다.
- 코드/설정은 이번 시험에서 수정하지 않았다. 임시 시험 확장과 결과는 /home/eunbi/vmany_artifacts/station_docking_pc_20261030/approved_tolerances/에 보존했다. 실물 저속 응답·도킹 정확도는 여전히 미검증이며 대기 연결 보완이 남는다. commit/push 없음.


### 2026-10-30 도킹 관측 대기 시계 연결 보완
- 승인: 사용자 “그렇게 보완해줘”. 새 정지 조건 없이 기존 관측 대기 시간 계산만 보완하는 PC 수정·검증 범위다. 기준 HEAD e135cdef9462276cc25d9fa336f084e2dcac72e4 및 기존 미커밋 변경 유지.
- 수정: harvest_robot/station_docking.py에서 기존 PauseClock을 그대로 재사용한다. 기존 controller_wait 수신과 이미 전달한 0출력의 최신성이 확인된 대기만 누적하여 도킹 namespace의 handoff_wait_clock으로 전달한다. Nav2Client에도 동일 scoped 실행 시계를 연결한다. 종료 시 대기 상태를 해제하고 타이머/구독/발행자를 정리한다.
- 최신 상태·단일 발행자·소유권 확인은 시간 공제 여부만 결정한다. 이 검사 때문에 새 정지/실패를 발생시키지 않으며 별도 0출력 명령도 추가하지 않았다. 도착 허용치/관측 유효시간/충돌/속도/정지 판정/40초 유효 제어 제한은 불변이다.
- 인계의 pause_clock.py, handoff_runtime.py 및 공통 C++ 플러그인은 이번에 수정하지 않았다. 기존 공통 계약을 실물 도킹 어댑터에서 연결했으며 sim/ 미변경, 로봇 배포/재기동 없음.
- 시험: test_station_docking.py에 대기·0출력·최신성·소유권 등에 따른 시간 공제 검사 추가. Python 도킹/복귀48개 통과. station_docking_nav2_trial.py는 승인 YAML 직접 사용 및 resume/wait_cancel 사례 추가.
- 직접 PC Nav2 시험(domain231/LOCALHOST/CycloneDDS, 가상 센서): 시작3초~18초 관측 단절 중 0출력 유지 후 같은 Goal로 재개, 총32.27초에 도킹 완료. 앞뒤4.923mm/좌우0.319mm/방향0.964도. 시험용 상위 실행 제한20초보다 벽시계 시간이 길어도 대기 공제로 완료했다. 진행 제한10초도 대기 때문에 실패하지 않았다.
- 관측 대기 중15초 시점 취소 요청: 정상 취소 및 최종 출력0(정리 포함16.21초). 정상 접근 회귀17.47초 완료. 실물 구동/센서 가림 및 정확도 검증은 미실행이다.
- 산출물: /home/eunbi/vmany_artifacts/station_docking_pc_20261030/wait_clock_fix/. 원복은 station_docking.py의 이번 시계 연결 및 해당 시험 추가만 제거한다. 인계나 이전 미커밋 코드를 통째로 되돌리지 않는다. commit/push 없음.

- 후속 회귀도 완료: 실제 Nav2 충돌 오류106 중단 및 사용자 취소 ActionInterrupted 확인, 모두 cleanup 후 최종 출력0. 위 다섯 Nav2 사례 모두 기대 결과 통과.


### 2026-10-30 실물 도킹 격리 배포·빌드
사용자 “해봐야지”로 로봇 적용·빌드 승인. 기준 HEAD e135cdef9462276cc25d9fa336f084e2dcac72e4, 기존 미커밋 보존. 로봇 Git/원격 상태를 새로 확인했다고 주장하지 않는다.

- 새 release: `/home/vic/vmany-runtime-staging/station_docking_20261030`. 기존 프로젝트/설치본/실행 release는 덮어쓰지 않았다. 기존 station_work_curvature_20261029를 underlay로 사용하여 이전 후진/원호 제어기를 유지한다.
- 로봇 기준 harvest_robot·farm_navigation·farm_common·farm_wall_controller 소스를 PC로 읽어 원본 보존 후 도킹 관련12파일만 교체/추가했다. 기존 인계·전진 소스와 설정은 유지했다. 새 도킹 config/선택 launcher/run.bash를 별도로 넣었다. manifest154파일 전수 SHA 일치.
- ARM colcon 4패키지 빌드43.5초 성공, CTest2(벽 기본 회귀·도킹90폐루프 포함) 통과. 설치 Python 모듈 경로는 모두 새 release. 설정5mm/5mm/1도·dwell0.5·기존 팔 수신 생략true 확인. 런치 --check 명령 출력과 중복 PID 없음 확인. 실제 노드 기동·운영 종료·주행은 미수행.
- 새 release 약15MB, 배포 후 여유 약2.8GB. 삭제/이동으로 기존 기록을 정리하지 않았다. 기존 collect.py 공간 기준은 변경하지 않았다. 영상 없는 도킹 전용180초 record.bash를 준비하고 PC/로봇 Bash 문법·SHA 일치 확인. 실제 기록 수집은 사용자 시험 대기다.
- PC 도구 수정: launch_corner.py에 명시 --docking-config 선택 인자만 추가(미지정 동작 불변), record_docking.bash 추가. 로봇에는 기존 도구 덮어쓰기 대신 새 release/launch.py와 record.bash로 배포했다. 기록 스크립트 SHA d25168ed8ac311072e6804db177ae8e2a8a488d15d8e9b2021eaadb8e4020768.
- PC 백업/배포 산출물: /home/eunbi/vmany_artifacts/station_docking_pc_20261030/robot_deploy/{baseline.tgz,release.tgz,manifest.json,robot_build.log}. 기존소스 백업은 로봇에 추가하지 않았다.
- 현재 별도 도킹 전용 요청은 없다. 복귀 Action은 기존18번 경로·정지 후 도킹, 성공/정리 후 docked=true. 이전 답변의 ‘도킹만 먼저’는 현재 기능으로 별도 제공되지 않음을 정정한다.

사용자 시험(아래 명령은 모두 로봇 터미널):
```bash
# 터미널 A: 기존 런치를 실행했다면 사용자가 먼저 종료한 뒤
bash /home/vic/vmany-runtime-staging/station_docking_20261030/run.bash
# 터미널 B: 실제14번·12번 반대 방향에 재배치했고 IDLE/정지인 경우에만
bash /home/vic/vmany/main/farm_project/robot/tools/terminal/dinit.bash
# 같은 B: 기록 시작, 필요한 scan/odom/tf 구독 표시 확인
bash /home/vic/vmany-runtime-staging/station_docking_20261030/record.bash
```
이후 기존 미니관제 스테이션 복귀 버튼을 한 번 누른다. 카메라는 기본 ON이며 이번에 임의로 끄지 않는다. 팔 상태 수신 생략은 유지하므로 실제 팔이 접혀 정지한 상태는 사용자 확인이 필요하다. 초기위치 입력은 실제 배치와 일치할 때만 수행하며 그래프18에 스테이션 초기화 좌표를 보내지 않는다. 완료/실패 및 실제 정지 후10초까지 기록, Ctrl+C 또는180초 자동 종료. 도킹 시 오차/성공·실제 뒤/좌/우 간격을 함께 확인한다. 별도 모션 명령을 추가하지 않는다.

원복: 사용자가 새 런치를 종료한 뒤 기존 launch_corner.bash station_work_curvature_20261029 명령을 사용한다. 기존 실행본 수정/복원 불필요. 실물 도킹·기록 수집은 미검증, commit/push/merge/스테이징 없음.


### 2026-10-30 18:53 실물 첫 시험: 도킹 목표 생성 전 실패
- 사용자 18번 도착 후 도킹 미실행 보고. 읽기 전용 프로세스/로그/종료 bag 확인, 주행·프로세스·설정 수정 없음.
- 실행은 station_docking_20261030, docking_config 명시 및 전용 controller_server 활성화 확인. launch 로그 20261030_185306_launch_778778, 기록 20261030_185328_533218918. 태그 카메라 프로세스는 code1 종료 기록이 있으나 이번 도킹은 라이다 기반이며 아래 직접 실패 원인과 구분한다.
- 18:55:23 일반 controller goal 완료 후 도킹 준비. 18:56:24.763 복귀 FAILED/RETURN_FAILED: `도킹 벽 관측 준비 대기: 단일 벽 지지율 부족: 영역 선택 확인 필요`. 도킹 FollowPath goal 수신 없음.
- 18:55:25 이후634개 scan을 PC에서 static TF·최근 odom으로 벽별 오프라인 검사: 뒤634/634, 왼쪽634/634 통과, 오른쪽0/634(단일 벽 지지율 부족). 오른쪽 기존 -120~-60도 영역의 진단용 저지지율 후보 중앙값73.9%, 설정은80%. 오른쪽 후보 거리0.47570m/방향-88.79도/RMS1.54mm는 완화한 오프라인 후보일 뿐 유효 목표로 승인하지 않는다.
- 도킹 dock_target/raw_nav/controller_wait 기록 없음, handoff_wait_clock은3576개. 즉 도킹 제어 진입 전 목표 관측 준비 실패이며 이전 보완한 주행 중 대기 시계와 다른 단계다.
- 영역만 좁히는 오프라인 탐색도 -110~-70도0/634, -105~-75도1/634, -100~-80도197/634 통과로 안정적이지 않았다. 임계값 완화·실물 설정 변경은 하지 않았다. 오른쪽 점군의 비벽점/가림·구조를 구분해 벽 선택을 보완해야 한다. 실물 도킹 성공으로 기록하지 않는다.
- PC 로그/분석: /home/eunbi/vmany_artifacts/station_docking_pc_20261030/run_1853/. 원본 로봇 기록 유지. commit/push 없음.


### 2026-10-30 뒤쪽·왼쪽 두 벽 선택 PC 수정
- 승인: 사용자가 오른쪽 벽 관측이 어려운 현장 조건을 설명하고 “ㅇㅇ 뒤쪽 + 왼쪽으로 고치자” 요청. 공통 벽 목표 계산의 선택형 확장과 실물 설정 변경 범위이며 인계/시뮬 미변경. 기준 HEAD e135cdef9462276cc25d9fa336f084e2dcac72e4 및 기존 미커밋 보존.
- farm_navigation/wall_observation.py: DockWallTracker가 observation_walls를 읽고 해당 벽만 추적·목표 계산한다. 미지정은 기존 rear/left/right. docking_target은 전달된 벽들을 기존 최소제곱/방향 계산에 사용한다. 기존 두 방향 구분(rank2) 검사 유지, 임계값 완화나 새 정지 조건 없음.
- station_docking.yaml: observation_walls=[rear,left]. 오른쪽 기준 측정값은 보존하되 자세 계산에서 제외. 기존 전체 scan costmap/footprint 충돌 검사에 오른쪽 장애물은 그대로 포함된다. 앞뒤/좌우5mm·방향1도·정지/dwell 및 속도 불변. station_docking.py는 주석만 선택 벽 표현으로 정정.
- test_station_docking.py: 두 벽으로 위치/방향 오차 복원 및 옵션 미지정 시 기존 세 벽 선택 회귀 추가. 도킹/복귀49개+기존 벽33개=82개 Python 시험 통과.
- 실물 18:53 기록 오프라인 재생: 18:55:25 이후634프레임, 초기 안정화4개 후630개 목표 생성, 관측 오류0. 목표 상대 이동 중앙값 x=-0.071177m, y=+0.016371m, yaw=+0.458309도. 실제 제어와 이동 성공의 검증은 아니다. TF는 기록 static과 가장 가까운 odom 표본 사용.
- PC 실제 Nav2/가상 센서(domain231/LOCALHOST/CycloneDDS): 앞9cm/좌우-4cm/방향10도 시작36.19초 완료, 최종4.994mm/0.714mm/0.973도. 충돌 오류106 및 최종0출력 확인. 실물 저속 응답·이동 후 두 벽 관측 유지 여부는 미검증.
- 이번 수정은 아직 로봇 실행본에 배포하지 않았다. 현재 로봇 station_docking_20261030은 이전 세 벽 선택 코드/설정이다. 운영 프로세스/주행 명령 미수행. 원복은 선택 옵션 및 이번 목표 계산 변경만 이전 형태로 돌린다. 기존 미커밋 전체를 되돌리지 않는다. commit/push 없음.

- 두 벽 선택에서도15초 관측 단절 후 정지 유지·같은Goal재개·완료 시험 통과. 관련 Nav23사례 모두 기대결과 통과. PC 산출물: /home/eunbi/vmany_artifacts/station_docking_pc_20261030/two_wall/.


### 2026-10-30 두 벽 수정본 로봇 격리 배포 완료
- 사용자 “그럼 준비해줘” 승인으로 새 `/home/vic/vmany-runtime-staging/station_docking_two_wall_20261030` 준비. 기존 세 벽 release는 보존했다. 기준 HEAD e135cdef9462276cc25d9fa336f084e2dcac72e4/기존 미커밋 유지.
- 기존 release의 src/config/사용자 실행도구를 새 경로에 복제하고, wall_observation.py·station_docking.yaml·station_docking.py(주석) 세 파일만 교체했다. 원본 대비 그 외 변경0, PC/로봇3파일 SHA 일치, manifest155파일 검증. 기존 프로젝트 소스/설치본·인계·전진·sim 미변경.
- ARM4패키지 빌드44.0초 성공. CTest2 통과. 실제 설치 모듈 경로/소스 바이트 일치, 두 벽 선택 및 세 벽 기본값 회귀, 위치·방향 기하3사례 확인. 허용치5mm/5mm/1도 유지. run.bash --check는 새 설정 경로를 선택, 중복 실행PID 없음. 실제 기동/재기동/초기위치/주행 명령은 보내지 않았다.
- 기존 팔 수신 생략 프로필·카메라 기본ON·후진/원호 underlay 유지. 로봇 여유약2.6GB, 파일 삭제없음. 기록도구는 기존 도킹용180초 record.bash를 그대로 새 release에 보존.
- PC 산출물: /home/eunbi/vmany_artifacts/station_docking_pc_20261030/two_wall_deploy/{station_two_wall_deploy.tgz,manifest.json,build.log}. 실물 두 벽 도킹 성공은 아직 미검증.

사용자 재시험 명령(로봇 터미널):
```bash
# A: 기존 런치가 있다면 사용자가 종료 후 새 런치
bash /home/vic/vmany-runtime-staging/station_docking_two_wall_20261030/run.bash
# B: 실제14번·12번 반대 방향에 배치했고 IDLE/정지일 때만 초기위치
bash /home/vic/vmany/main/farm_project/robot/tools/terminal/dinit.bash
# B: 영상 없는180초 기록. 필요한 scan/odom/tf 구독 표시 후 미니관제 복귀1회
bash /home/vic/vmany-runtime-staging/station_docking_two_wall_20261030/record.bash
```
현재18번에 그대로 있다면 dinit을 보내지 않는다. 위14번부터 시험하려면 실제 재배치가 먼저다. 팔이 실제 접혀 정지한 상태 확인. 완료/실패 후 실제정지10초 더 기록하고 Ctrl+C 또는180초 자동종료. 18번 도착후 두 벽 도킹의 동작/최종결과 및 벽간격 확인. 원복은 사용자새런치종료 후 이전 run.bash 선택으로 가능하며 기존실행본 복원 불필요. commit/push/merge 없음.


### 2026-10-30 19:38 두 벽 도킹 첫 실물 성공
- 사용자 시험 실행 후 읽기 전용 로그 확인. 실행본 station_docking_two_wall_20261030, task_id station-return-3df65c32f8d348f4b91bd13b307a477b.
- 19:38:49.372 복귀 시작 → 19:40:15.659 일반 주행 goal 완료 → 19:40:17.491 도킹 FollowPath 접수 → 19:40:33.392 도킹 goal 완료 → 19:40:34.203 정지 후 검증 accepted=true → 19:40:34.277 미니관제 최종결과 수신.
- 최종 라이다 기준 추정 오차: 앞뒤0.575875mm/좌우0.168082mm/방향0.286571도. 실제 자로 잰 외곽 간격 정확도와 구분한다. 도킹제어 약15.90초, 복귀부터 전체약104.90초.
- PC arm-audit.jsonl 결과 ros_status=4, success=true, result_code=SUCCESS, docked=true, error_code=NONE, error_message 빈값 확인. 후속 snapshot IDLE/base_stopped=true. 팔 수신 생략 시험이며 ready=false/ARM_NOT_READY는 남아 있으므로 팔 준비·수확 전체성공으로 확대하지 않는다.
- 카메라 tag_capture_session은 code1 종료 기록이 있다. 이번 성공은 라이다 두 벽 도킹이며 태그 보정 성공의 근거가 아니다.
- 로봇로그 /home/vic/vmany-terminal-logs/20261030_193734_launch_790283/console.log, 기록 runs/station_docking_trial/20261030_193831_668247392. PC 로그 사본 /home/eunbi/vmany_artifacts/station_docking_pc_20261030/run_1938/console.log. 실제 벽간격 사용자 확인 및 반복성은 별도 검증 대상이다.
- 이번 확인에서 코드/설정·프로세스·주행 명령 변경 없음. commit/push 없음.


### 2026-10-30 사용자 성공 확인 후 기준 고정
동작값/제어 코드를 변경하지 않고 컴포넌트 구조·release155파일·PC주요11파일 일치 및 PC백업검증을 완료했다. 현재 확정 기준은 [성공 기준 문서](STATION_DOCKING_SUCCESS_FREEZE_20261030.md)를 따른다. 기존 인계/sim/프로세스 미변경, 추가주행·commit/push 없음.
