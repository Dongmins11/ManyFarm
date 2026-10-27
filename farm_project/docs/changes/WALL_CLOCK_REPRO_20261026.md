# 2026-10-26 벽 정렬 Clock reversed 오프라인 재현

사용자 승인 범위: 실제 코드·로그 추적 및 오프라인 재현. 수정/재시작 전 안내 요구. 운영 소스·설정·프로세스·안전 조건 변경, 이동/Action/초기위치 발행 없음. 기존 미커밋 변경 유지.

## 실기 근거

07:52:18.324 후진곡선 완료, 07:52:19.865 벽관측 대기, 07:52:22.669 벽정렬goal 수신, 07:52:22.790 대기 재개, 07:52:23.279 Clock reversed/abort. controller4615는 sensor_hold_robot_20261024/install/farm_wall_controller/lib/libwall_controller.so 로딩. 바이너리SHA47499187296f97b672dafb73bcfd1e511007efe05733e8ea9839e3b8904c87fa. 후보원본 wall_control.hpp는 PC 이전 후보와 SHA2b530e570be6e74a3a9bab6f812164049f791283e4758f130584e258a94631c2로 동일. 소스와 로딩 경로 확인이며 이번 바이너리의 빌드 재현은 수행하지 않음.

실제 설정 wait_until_fresh=true/observation_age=.45/sequential_alignment=true. 수정된 대기→재개는 작동했다. 이번 직접 오류는 만료/대기시간초과가 아닌 Clock reversed다.

## 재현된 결함

WallController.computeVelocityCommands는 wait_.take()를 호출해 credit_wait에 반영한 뒤 WallInput.read 잠금·처리와 now 조회를 거쳐 step을 호출한다. WaitClock.take의 dt는 steady clock으로 두 take 사이를 측정한다. Control 시작시각 start_는 첫 step 또는 wait의 ROS now이고, credit_wait는 start_에 외부 대기 누계를 더한다. 실제 시작시각과 제한시간 보정의 기준을 같은 변수로 사용한다.

시간축이 정상 증가하는 다음 입력으로 원본 헤더 그대로 C++ 재현:
- 첫 take=100.000, 입력처리/스케줄링30ms 뒤 step now=100.030 → start=100.030.
- 다음 take=100.050, 유효 동일세션 누계증가 .050 및 dt=.050 → credit=.050 (상한.2 이내).
- 다음 입력처리1ms 뒤 step now=100.051. wall stamp도100.020→100.040 증가, freshness 정상.
- start는100.080이 되어 now보다29ms 미래. 이전now 대비 역행도, wall stamp 역행도 없지만 `now<start_`가 Clock reversed를 발생시킨다.

보정 없음 대조군은 통과. 같은 입력에서 보정 추가 시 실패. wait→fresh 전환에서도 재현. 두 호출의 처리지연이 같은 대조군은 통과. 이는 clock 역행을 요구하지 않는 보정 코드의 오판 경로가 존재함을 증명한다. 재현 시간값은 호출 계약에 맞춘 합성값이며 실기 측정값이 아니다.

## 실기 원인 귀속의 한계

실패 전후7초 Python trace1183개를 thread별 monotonic 순서로 비교: ROS시각 역행 표본0. 그러나 C++ now/start/last/credit 및 실제 수신 wall stamp가 기록되지 않아 이번 실기가 세 Clock reversed 조건 중 어느 분기인지 확정할 수 없다. Python 관측 worker는 같은 tracker에서 증가한 scan stamp만 발행하지만 이것만으로 C++ 수신/goal 경계 역행을 완전히 배제할 수 없다.

따라서 `대기 보정에 실제 결함 있음`은 오프라인 재현으로 확정, `이번 실기도 이 결함으로 실패`는 유력한 후보이나 분기별 수치 부재로 미확정이다. 이전 test_wall_wait.cpp의 보정 시험은 credit10/시간경과10과 같이 동일 간격만 다뤄 take→step 지연 변화 경계를 검사하지 않았다.

## 다음 변경 제안 — 미적용

실제 시각 단조성 검사와 대기 제외 실행시간 누계를 분리한다. 실행시간 보정은 같은 측정 구간 내에서 제한하고 내부 관측 대기와 외부 누계를 중복 차감하지 않게 한다. Clock reversed 자체 삭제나 센서 freshness/공간한계/충돌/정지/취소 보호 완화는 하지 않는다. 오류는 실제now역행/표본역행/보정계산 문제를 수치와 함께 구분하도록 제안한다. 대상은 wall_control.hpp, wait_clock.hpp 및 wall_plugins.cpp의 시간 전달 계약과 경계시험이다. 공통 코드 수정은 사용자 확인 전 미수행.

자료: runs/wall_alignment_diagnosis_20261026의 launch.log, transfer.json, 실제 헤더/플러그인 복사본, trace_window.jsonl, trace_summary.json, reproduce.cpp/reproduce.log. `g++ -std=c++17 -Wall -Wextra -O0 reproduce.cpp`로 운영 헤더 복사본을 그대로 검사. 운영 배포·재시작·실기 재시험 미수행, commit/push 없음.

## 사용자 승인 후 수정 후보 및 오프라인 검증

사용자가 실제시각/대기제외 계산 분리 후보와 오류별 수치 및 오프라인 검증 승인. 운영 적용/재기동 전 안내 조건 유지. runs/wall_clock_candidate_20261026에 baseline과 별도 candidate, 최종patch/해시 보존. PC 운영소스·로봇 실행본·설정·프로세스 변경 없음.

실제 start는 고정, 매 호출 시간차를 active/excluded에 나눠 적산. 외부credit은 현재 구간에 clamp하고 남는 양은 폐기. 내부 관측대기 구간을 전체 제외하면 같은 구간 외부credit은 추가 차감하지 않음. 실제 now 역행 및 새 관측stamp 역행/미래 검사를 별도 오류명으로 유지. 공간·완료·취소·충돌보호 및 WaitClock 검증은 유지. GoalChecker의 오류도 throttle 경고로 남기고 관측읽기 후 동일now를 대기/step판정에 사용.

파일: candidate의 include/farm_wall_controller/wall_control.hpp와 src/wall_plugins.cpp만 변경. 오류에 실제 now/previous/start/stamp/last/age/구간·보정량/누계/시간·거리·방향제한 수치 포함. 미래start 비교라는 오판은 삭제했으나 실제시각 단조성 검사는 유지. 초과보정은 이월하지 않아 추후 정상구간 timeout을 부당하게 연장하지 않음.

검증:19개 신규 경계시나리오(원래문제2종, 초과이월방지, 중복제외방지, 장기정지, 실제clock/stamp역행, 미래, 만료, 공간한계, legacy대기제한, 잘못된credit, reset, 중복stamp완료거절, 정상dwell, 실제이동중완료거절, 부분보정timeout), 기존대기10시나리오 및 패키지CTest1/1통과. ASan/UBSan통과; LeakSanitizer는sandbox ptrace환경제약으로비활성(메모리누수검사통과라고표현하지않음). PC ROS Jazzy 플러그인빌드통과, 로봇ARM빌드/동적로드/실기미실시. 빌드와 실기성공을 구분한다. 상세 README와 로그는 후보폴더.

## 2026-10-26 로봇 ARM 빌드·플러그인 검증 완료, 운영 미적용
사용자 별도 로봇용 빌드·로드검증 승인, 운영프로세스 임의 기동/종료 및 이동 금지. 로봇 /home/vic/Downloads/wall_clock_candidate_20261026 신규폴더에서만 빌드. 원본 sensor_hold.../src/farm_wall_controller 전체 해시가 PCbaseline과 일치. 운영install/farm_wall_controller 전체·config_candidate·terminal run.bash를 operating-backup에 추가 보존, 기존백업 불변.

ARM aarch64 libwall_controller.so SHA93761a5469dedaa12da56b36659249c6a9f2942ce683bb74545447cf168946b7. colcon빌드 성공(2분37초), 로봇상 신규19·기존10시나리오 및 CTest1/1 통과. 노드 미생성 pluginlib probe로 WallController/WallGoalChecker/WaitingProgressChecker/WaitingSpin 네 플러그인 생성·소멸 성공. /proc/self/maps에서 모두 새후보 경로 확인. ROSinit/node/configure/activate/Goal 미실행, 실기성공으로해석금지. 일회성검증프로세스 잔존0. 기존controller4615 유지, 운영lib SHA47499187... 동일 및 운영패키지/설정 백업대조동일.

빌드부하 기록 정정: CMAKE_BUILD_PARALLEL_LEVEL=1/패키지순차 실행을 지정했으나 실제colcon cmake명령에 -j4 -l4가 포함되어 Make병렬도1이 강제되지는 않았음. probe빌드는 -j1. 빌드기동은 사용자승인범위이며 운영프로세스조작없음.

자료: PC runs/wall_clock_candidate_20261026/robot_validation에 빌드/시험/로드/해시/불변검사로그, DEPLOYMENT.md. 새후보루트는 운영run.bash/alias에 연결하지 않았음. 적용/원복은 사용자종료 확인 후 before/after해시 검증하여 대상패키지만 교체하는 별도 단계로 준비. 현재실패복구기록/초기위치/이동/브리지 변경 없음. commit/push 없음.

## 2026-10-26 운영 경로 적용 완료 — 재기동 미실시
사용자 zen/dzen/laun 종료 후 적용 승인. robot_agent잔존0 및 추가장치/카메라/라이브러리 매핑 검사 통과. 변경전해시/후보해시 전부일치. sensor_hold_robot_20261024/wall-clock-backup-1792970677370575912에 운영src/install farm_wall_controller 전체,config_candidate,run.bash,transfer.before.json 추가백업. 기존성공백업보존.

운영sensor_hold 루트의 src/wall_plugins.cpp, src/.../wall_control.hpp, install/.../wall_control.hpp, install/.../libwall_controller.so 4개만 교체. 최종lib SHA93761a5469dedaa12da56b36659249c6a9f2942ce683bb74545447cf168946b7. 운영환경만 source한 일회성probe로4종LOAD_OK 및운영경로매핑/DESTROY_OK 확인(ROSinit/node/Goal없음). 설정/run스크립트/인계저널SHA불변 및 운영잔존0 최종검증.

복구표시는승인범위아니므로유지: DOCK_TEST_9bfeb40a097746428acddda96250233f activefalse/recoverytrue. 재기동/초기위치/이동미실시. 실제재배치확인후별도복구처리가필요하며곧바로vinit가능상태로안내하지않는다.

receipt/전후상태/운영로드로그/적용스크립트/원복스크립트: PC runs/wall_clock_deploy_20261026. 로봇 wall_clock_candidate_20261026/deployment_receipt.json 및 rollback_operating.py(보관만,미실행). 원복은운영종료/after해시동일 확인뒤4파일만복원,기록은되돌리지않음. Gitcommit/push없음.
