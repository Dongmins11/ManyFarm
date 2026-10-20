# Vic Pinky 후진 곡선 성공 기준 보존

작성일: 2026-10-19 KST. 사용자 요청: 이번 성공을 빠짐없이 보존한 뒤 다음 단계로 이동한다.

## 1. 이번에 성공한 것

- 기존 주행 런치로 그래프 12번까지 이동한 뒤, 별도 controller_server에서 반경 0.10m 후진 곡선을 실행했다.
- 차체 중심이 뒤·오른쪽으로 빠지면서 차체는 왼쪽으로 약 90도 회전한다.
- 사용자 확인: 생각했던 자세와 동작 모두 맞았다. 비상정지를 사용해 다시 시험했을 때도 같은 동작으로 잘 됐다.
- 첫 번째 시험은 아래 실행 출력으로 성공·정지·기존 파라미터 불변을 확인했다. 두 번째는 사용자 관찰 성공이며 두 번째 수치/로그는 아직 분석하지 않았다.
- 비상정지를 사용한 재시험을 자동 복귀 성공, 비상정지 기능 자체의 검증, 자동 재시작 안전성 검증으로 해석하지 않는다. 원래 자세로 되돌린 구체적인 방법은 추가 확인하지 않았다.

## 2. 첫 번째 성공의 정확한 기록

- 실행 폴더: `/home/vic/vmany/main/farm_project/runs/transfer_arc_isolated/1792412813879038846`
- 상세 JSON: 위 폴더의 `1792412818586192707_arc.json`
- 독립 namespace: `/harvest_01/arc_trial_519d1b16`
- baseline_hash: `d8862537fee3da6d4bbf9e4283a12376d15f9f7cf4fcc77f8451a59c9cb51362`
- radius: 0.1m
- origin(odom): x=1.2777409275309795m, y=-2.2143101086138484m, yaw=-1.516397962390173rad
- preflight_clearance_m: 0.004496558729669028m
- measurement.angle: 1.570112331630147rad (약89.96도)
- measurement.deviation: 0.0005593627646498265m
- measurement.endpoint_error: 0.0005928424015422307m
- measurement.yaw_error: 0.0006839951647494222rad (약0.039도)
- phase=SUCCEEDED, ok=true, execute=true, cleanup_stopped=true
- supervisor: ok=true, mode=execute, configured=true, baseline_unchanged=true
- scan_topic=/harvest_01/scan_filtered
- isolated_velocity_topic=/harvest_01/arc_trial_519d1b16/raw_cmd_vel

수치 해석: 위치/각도 오차는 odom 기준이다. 외부 측정으로 확인한 절대 위치 정확도나 벽과의 실제 간격이 아니다. preflight 여유 약4.5mm는 해당 계획 검사 시점의 costmap 계산값이며 물리 측정 간격/주행 중 최소 간격이 아니다. 작은 odom 오차를 다음 수확 좌표 도달 정확도나 태그 비가시 구간 안정성으로 확대하지 않는다.

## 3. 왜 이 구조를 사용했는가

기존 제자리 Spin은 왼쪽 회전 도중 충돌 판정(code703)으로 멈췄다. 로봇 외곽/footprint가 실제 치수와 맞고 화단 인접 공간이 협소했다. 사용자 구상은 후진 곡선으로 벽과 거리를 벌리며 회전한 후 필요하면 정밀 접근하고, 인계 후 반대 경로로 원래 주행 자세에 돌아오는 것이다.

곡선 플러그인을 기존 controller_server에 추가한 시험 런치에서는 12번 접근 중 RPP collision ahead/106이 발생했다. 기존 런치에서는 다시 성공했고 회전·전진 반복도 기록에서 확인됐다. 기존 주행 제어의 수집된 명시 파라미터는 같았지만 원인은 미확정이다. baseline local costmap 파라미터가 빈 값으로 수집된 한계도 있다. 별도 서버 성공은 앞선 106의 근본 원인을 규명했다는 의미가 아니다.

채택한 성공 구성: 기존 런치와 서버는 그대로 유지하고, 정차 후 곡선만 별도 프로세스로 실행한다. 이전 `arc_trial.bash launch`를 성공 기준의 시작 명령으로 사용하지 않는다.

## 4. 코드 구성과 책임

경로는 farm_project 기준이다.

- `robot/tools/tag_camera/bias_trial/trial.bash`: 기존 장치·주행·수확·태그 런치. 이번 격리 패치에서 수정하지 않았다.
- `robot/tools/transfer/arc_isolated.bash`: 필요한 source 및 현장 통신 환경을 적용하고 감독 도구 호출.
- `robot/tools/transfer/arc_isolated.py`: 기존 controller/local costmap/smoother의 실제 전체 파라미터 조회, 실제 scan 구독 주소 확인, 별도 namespace 생성, controller configure/activate/종료, 기존 파라미터 전후 비교, 기록 저장.
- `robot/tools/transfer/arc_trial.py`: 기본 계획 전용. 선택적 독립 서버 주소로 공통 Nav2Client 연결. odom·costmap·footprint·액션 상태 확인, 경로 생성, 계획 기준 대조, 실행 및 정지 확인.
- `robot/ros_ws/src/farm_navigation/farm_navigation/arc_isolation.py`: 독립 설정 생성과 속도 전달 gate. 기존 설정 입력을 수정하지 않는다.
- 같은 패키지 `transfer_arc.py`: ArcSpec·후진 곡선 계산·오차 판정·trial_profile.
- 같은 패키지 `arc_clearance.py`: costmap 셀 면적과 footprint 기반 사전 검사. 충돌 검사를 끄거나 외곽을 축소하지 않는다.
- `robot/ros_ws/src/farm_arc_controller/`: 공통 Nav2 ArcController 플러그인. 기존 RPP의 TF·costmap·충돌 검사 경로 재사용, 곡선 수학은 arc_math.hpp.
- `arc_profile.py`: 앞선 통합 시험 프로파일 생성 모듈. 현재 독립 감독 도구는 이를 이용해 기존 서버 설정을 교체하지 않는다.
- 기존 `Nav2Client`, `NavigationSettings`, velocity_smoother, 실제 드라이버를 재사용한다. 실물 전용으로 공통 미션/주행 로직을 복제하지 않는다.

주요 실행 수치: desired_linear_vel=0.01m/s, 곡선 lookahead=0.04m, reversing=true, rotate_to_heading=false, collision detection=true, 충돌 예측2초. ArcSpec 기본90도/샘플간격0.002m/경로이탈0.01m/완료위치0.008m/완료yaw0.05rad/제한시간60초. 독립 goal checker xy0.005m/yaw0.04rad, progress checker 이동0.01m/회전0.04rad/10초. 정확한 전체 값은 보존한 코드와 성공 실행 parameters.yaml을 함께 기준으로 한다.

기존 local costmap 기준 resolution=0.02m, footprint x±0.30m/y±0.25m, padding=0.02m. 독립 서버는 실행 중 설정을 읽어 연결한다. 별도 costmap은 별도로 갱신되므로 기존 costmap과 셀별 상태가 동일하다는 의미는 아니다.

## 5. 명령 전달과 검증 경계

- 독립 서버 속도 출력은 임의 namespace의 raw_cmd_vel에만 연결한다.
- check: configure 및 출력 분리·파라미터 보존 확인. 이동 없음.
- plan: 독립 costmap 활성화 후 최신 자료로 경로 검사. Goal/로봇 속도 발행 없음.
- execute: --exclusive 및 성공한 --reference PLAN.json 필수. 기존 설정 hash와 출발 자세 차이(5mm/0.02rad)를 재검사하고 현재 costmap으로 다시 검사한다.
- 계획 사용 후 .used 표시로 같은 계획 재실행을 막는다. 반복 시험은 현재 자세에서 새 plan이 필요하다.
- gate는 실행 중에만 기존 /harvest_01/cmd_vel_nav로 전달한다. 기존 smoother와 드라이버를 사용한다.
- 다른 작업 액션 활성, 센서/TF 자료 문제, odom 경로/속도 범위 이탈, 명령 범위 위반, 명령 수신 간격0.3초 초과 시 실패 처리. 최초 명령 전 응답 대기는5초.
- 종료 시 gate 차단·0 명령·자기 Goal 취소/정지 확인, 독립 서버 종료. 기존 서버 파라미터와 lifecycle은 변경하지 않는다.
- 시험용 --exclusive는 관제/다른 터미널의 동시 요청 금지를 전제로 한다. 정식 운영 ActionHandoff 연결이나 임의 수동 속도 발행자와의 완전한 중재 구현을 대신하지 않는다.

## 6. 현장 실행 기준

ROS2 Jazzy, PC eunbi=/home/eunbi/vmany/main/farm_project, 로봇 vic@192.168.0.12=/home/vic/vmany/main/farm_project, 기본 ws=/home/vic/vicpinky_ws.

CycloneDDS, Domain77, ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST. CYCLONEDDS_URI/ROS_STATIC_PEERS/ROS_DISCOVERY_SERVER/ROS_LOCALHOST_ONLY/FASTRTPS_DEFAULT_PROFILES_FILE/FASTDDS_DEFAULT_PROFILES_FILE 해제. 터미널별 적용. 재부팅 후 lo multicast 활성화.

전체 재시작 시 현장 성공 순서: 기존 주행 런치 → AMCL 초기 위치 → 로봇 Zenoh → 관제 표시. 초기 위치 x0.104/y-1.105/yaw87.79도는 당시 실제 스테이션 자세일 때만 사용한다. /tmp/init_station_newmap.py 존재 확인. 브리지 endpoint tcp/192.168.0.20:7447, domain77, ros-localhost-only, no-multicast-scouting. 관제 수신 브리지도 필요하다. 이 순서를 일반적인 Zenoh 필수 순서로 단정하지 않는다.

기존 런치로 12번 정상 도착한 상태에서 독립 check → plan → execute를 사용했다. 곡선 때문에 전체 런치를 다시 켜거나 현재 위치에서 스테이션 초기 위치를 재발행하지 않는다. 기록된 odom origin을 AMCL 초기 위치로 사용하지 않는다.

## 7. 검증 이력

- 초기 공통 곡선 수학/설정18개 및 C++ 수학, PC·로봇 빌드 통과(이전 사용자 출력).
- PC 독립 plugin configure/inactive 로딩 통과(이전 사용자 출력).
- 독립 연결 변경 후 오프라인18개+기존곡선18개=36개 통과. 패치 적용/내용 대조, Python/Bash 구문, 제공 runtime costmap63개 항목의 수치 보존 대조 통과.
- 현재 최초 실물 execute 출력: configured=true, 기존 파라미터 불변, 실제 곡선 SUCCEEDED/정지 확인.
- 사용자: 의도한 동작·자세 확인, 재시험에서도 동일 성공.
- 두 번째 원본 로그, 설치 바이너리, 현재 PC/로봇의 전체 파일은 아래 백업 스크립트 실행 후 보존되며 이 문서 작성만으로 원격 백업 완료를 주장하지 않는다.

## 8. 보존 대상과 복구 원칙

전달 ZIP `harvest_arc_isolated_20261019.zip` 및 그 패치/README/검증 도구를 함께 보존한다. PC Git branch/HEAD/status/diff와 미커밋·미추적 코드, 로봇 src/config/tools/model, 설치본과 vicpinky_ws src/install, 완료된 독립 시험 전체(plan/check/execute), 기존 bias trial 입력·로그, OS/ROS 패키지 버전, 설치 .so 해시를 묶는다.

백업은 PC의 별도 고유 폴더에 저장한다. 로봇은 Git 저장소가 아니다. 전체 덮어쓰기·reset·clean·자동 commit/push·파라미터 변경·재빌드·런치/이동은 하지 않는다. 커밋은 사용자 VS Code에서 진행한다. 복구할 때도 현재 상태와 비교해 필요한 파일만 선택 적용하고 성공 기준을 임의로 이전 시험 프로파일로 되돌리지 않는다.

## 9. 아직 하지 않은 것 — 다음 단계 보류

반대 경로 전진 곡선 복귀, 원래 map 위치/방향 복원, 화단 정밀 접근/이격, 운송로봇 ArUco 도킹, Jetson 배출, 실제 인계 FSM 연결, 태그 비가시 구간 복귀 후 다음 수확 이동은 아직 검증 전이다. 성공 후진 곡선 자체를 변경하지 않은 상태에서 후속 작업을 별도 진행한다. 이번 보존이 확인되기 전에는 다음 단계로 넘어가지 않는다.
