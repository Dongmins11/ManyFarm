# 일반 주행 충돌 예측 재시도 후보 — 2026-10-26

사용자 요청: 정지 조건 완화 또는 여러 번 재시도. 물리 충돌 검사를 끄지 않고, 종료 확인된 일시 충돌 예측의 작업 즉시 실패를 줄이는 별도 후보로 구현. 운영 적용·재기동·이동 없음. 기존 align 성공/후보 운영 소스 불변.

실제 로봇 sensor_hold_robot_20261024/src/farm_navigation에서 nav2_client/navigation_types/tf_recovery/navigator를 읽어 runs/navigation_retry_candidate_20261026/operating_baseline.tar.gz에 백업했다. 실제 execute는 TF_ERROR만 재시도하며 일반 충돌(NO_VALID_CONTROL)은 RuntimeError로 상위 전달한다. 이번 14:23:59 일반 controller collision ahead abort는 align 단계와 다르다.

후보 변경3파일: collision_recovery.py 신규, nav2_client.py 명시적 충돌 오류 분류 및 재시도 연결, navigation_types.py collision_retry_count 선택 설정(기본0). 후보 권장값5, 최소 정지2초/재시도, 정지·TF 회복 대기30초. 총 goal_timeout은 기존대로 적용되어 먼저 만료될 수 있으며 이번 후보가 전체 FSM 무기한 유지를 보장하지 않는다. 같은 경로를 재요청하고 최신 costmap 충돌 검사는 Nav2가 수행한다. 새로운 우회 경로나 costmap 지우기·안전거리 감소는 하지 않는다.

조건: FollowPath terminal ABORTED + NO_VALID_CONTROL + 결과 error_msg에 collision ahead 명시. 다른 오류·CANCELED·미확정 goal은 재시도하지 않음. 이전 goal 종료 이후에만 기존 stop 출력/TF·정지 probe 사용. 취소 check는 대기 중 계속 검사. 모든 로봇 기본값0, 활성화는 tf_recovery_enabled가 켜진 FollowPath로 제한. 설정 적용은 아직 하지 않았으며 인계 전용 설정에 전파하지 않도록 적용 전에 실제 조합 확인 필요.

PC 오프라인17개 통과: 즉시성공/2·5회 재시도/상한/취소/정지TF미회복/다른오류/설정거절/실제 _execute_once 메서드의 결과 분류와 goal clear 확인. 입력·Action handle 대역, 운영 ROS 서버 시험 아님. test.log 및 candidate.patch, manifest.json 보존. 현재 현장 로그에는 controller 로그만 확인했으므로 실제 action error_msg 일치 확인 및 상위 FSM/전체 timeout 통합검증이 남아 있다. 로봇 빌드/운영 적용 준비 완료로 간주하지 않음.

공통 코드 후보는 runs에만 작성. 실물/시뮬 운영 소스와 설정 불변. 필요시 후보를 사용하지 않으면 되며 운영 원복 대상 없음. Git commit/push 없음.


## Action/FSM 통합검증 및 후보 보완 (운영 미적용)

사용자 승인 범위: 실제 오류 분류·상위 FSM 제한시간 통합검증, 기존 성공코드/안전보호 유지, 운영적용/재기동 전 안내, 이동 없음. 로봇은 소스·설정·패키지 버전 조회만 수행. PC에서만 domain193/loopback/전용 namespace 격리 시험 프로세스를 실행하고 종료했다. 운영 브리지에 연결하지 않음.

### 발견과 수정

1. 실제 PC Nav2 controller_server+RPP에 합성 costmap 장애물을 공급해 FollowPath 요청. 반환은 status6/NO_VALID_CONTROL106/error_msg 빈 문자열. 기존 후보의 문구 조건은 이 결과를 놓쳤다. 빈 문구106을 원인 미상 제어 불가로 분류해 제한 재시도, 충돌 확정으로 기록하지 않음. 문구 있는 다른 오류는 그대로 실패. 실제 로봇 Action 결과를 과거 로그에서 복원한 것은 아니다.
2. 후보의 총 goal_timeout에 충돌 대기가 포함되던 문제 수정. 같은 실행 시계로 대기 시작/끝을 기록하고 대기분만 제외한다. 실제 실행시간 제한·시계 역행 검사·취소는 유지. TF 복구는 별도 기존 정책이며 TF 대기 제외로 확대하지 않음.
3. 운영 navigation_policy는 goal_timeout_s300, tf_recovery_enabled=false. HandoffRuntime은 TF복구 활성화를 단일 출력 계약 위반으로 거절하므로 이전 후보 활성화 전제가 실제 조합과 맞지 않았다. TF설정 유지, collision_retry_count 독립 처리, Navigator가 정지/TF probe 연결, Nav2Client는 기존 출력 소유자 정지 콜백을 사용하도록 수정.
4. HarvestNode의 별도 `navigation_collision_retry_count`(제안5, 기본0)를 일반 진입/작업/이탈 FollowPath에만 선택. 기본 settings는 0으로 두어 인계 profiles/StationReturn에 전파하지 않음. HandoffRuntime.stop_navigation_recovery는 work 소유권·취소·인계 비활성·blocked/stopping/error 검사를 통과한 경우 기존 publisher로 zero만 출력. 새 속도 publisher를 만들지 않음. shared profile에 직접 collision_retry_count를 넣는 수확 조합은 거절.

현재 변경6파일: farm_navigation/{collision_recovery,nav2_client,navigation_types,navigator}.py, harvest_robot/{node,handoff_runtime}.py. 운영 소스는 불변이며 실제 운영본 백업에서 후보를 만들었다. 이전 align 변경이 포함된 runtime을 기준으로 수정했으므로 이를 과거 버전으로 덮어쓰지 않음. activation_proposal.json은 설명용 제안이고 실행 설정이 아니다.

### 제한시간/실패 전파 확인

실제 HarvestCommunication은 controller.done.wait()로 기다리며 별도 일반 주행 deadline 없음. HarvestStateController의 worker가 HarvestMission.run을 실행하고 종료시 TerminalState 전환. Mission은 Navigator 예외 시 자신의 goal 취소/정지 정리를 확인. StagedNavigation은 각 단계의 navigator 호출이며 별도 task deadline 없음. Nav2Client의 전체 goal_timeout300초와 응답/취소 제한은 유지한다. 인계/팔의 별도 stage timeout은 일반주행 재시도 중 실행되지 않는다. 관제 서버의 자체 작업 timeout 정책은 이번 범위에서 검증/변경하지 않았다.

### 이번 실행 결과

- PC 단위18개 및 실제 runtime 정지 메서드 소유권2개 통과. 7가지 소유권/취소/오류 차단 조건 포함.
- 실제 PC Nav21.3.13 controller/RPP 오류 반환1건 확인(합성 TF/odom/costmap). 로봇 Nav2는1.3.11이며 버전차이 존재. 실제 로봇 controller에 goal 보내지 않음.
- 실제 ROS DDS FollowPath 대역서버 + 실제 후보 Nav2Client + 기존 HarvestMission/HarvestStateController 연결5시나리오 통과. 대역서버는 앞 단계에서 확인한 빈 문구106을 반환. 실제 Nav2와 이 FSM 검사는 서로 분리된 검사이며 전체 실기 E2E가 아님.
  - 2회 abort→3번째 성공: 4.168초, goal_timeout1초. 두 번의 2초 대기가 제외되고 상위 FSM은 유지. 수신 zero84건, active goal없음.
  - 대기 중 취소: goal1회만 전송, MissionCanceled, zero7건, 다음 goal없음.
  - 재시도상한: 설정1회에서 총2goal 후 종료, zero43건.
  - 다른오류107: 재시도없이1goal 종료.
  - 실제실행시간초과: goal_timeout0.3초, 약0.325초후 취소/종료 확인, blocked=false/active goal없음.
- 최종통합은 tf_recovery_enabled=false, client._stop_publishers 빈 목록을 확인한 상태에서 수행. 정지 콜백은 격리 시험 출력 소유자이며 운영 runtime의 소유권 로직은 별도2개 검사로 검증.
- 최초 격리 YAML namespace 미적용으로 DWB configure 실패, 이후 실제 빈 Action 문구로 첫 assertion 실패를 확인하고 각각 정정. 실패로그 보존. 운영 YAML 변경 없음.

로그: runs/navigation_retry_candidate_20261026/{test.log,output_owner.log,ros_validation/}. real_result.json, action_fsm_results.json, controller.log, 이전실패/TF활성 비교로그 포함. 후보 diff/manifest 갱신, Python AST 확인.

남음: 로봇1.3.11 격리 Action검증, 후보 ARM빌드/로드, 수확 전체노드 조립기동(일반/인계/복귀 설정선택), 실제 최신costmap 회복 후 재주행. 자동재계획은 포함하지 않으며 동일경로가 계속막히면5회후실패. 최소2초/회, 정지TF회복30초/회 제한 유지. ROS 목표 수락만으로 동작완료로 보지 않음. 운영 적용/재기동/물리이동/commit/push 없음.


## 로봇 ARM 빌드·Nav2 1.3.11 격리 검증 완료 (운영 미적용)

사용자 승인: 기존 성공코드/백업 유지, 로봇용 빌드/로드 및 해당버전 격리검증. 새 경로 `/home/vic/Downloads/navigation_retry_build_20261026`에서만 작업. 운영 대상 원본5개와 신규 collision_recovery 부재를 소스·설치본 양측에서 확인하고 현재 운영 패키지2개 src/install/config_candidate 전체를 operating_backup.tar.gz로 보존했다. harvest.before.json으로 활성화 대상 설정도 추가 보존했다.

별도 src/build/install에서 farm_navigation·harvest_robot 2패키지 ARM 빌드 성공. 변경6개 포함 모듈11개 설치 경로와 변경해시 확인, harvest_node entrypoint 로드 확인. 노드 생성/main 호출 없음. colcon underlay override 및 byte-compiling 생략 경고는 build.log에 보존.

로봇 Nav2 controller/RPP 패키지 버전1.3.11. domain193/loopback/전용 namespace에서 합성 TF·odom·costmap으로 실제 Nav2 controller_server를 configure/activate하고 FollowPath의 충돌 예측 ABORTED(status6), NO_VALID_CONTROL106, 빈 error_msg 확인. 운영 controller/센서/모터로 명령을 전송하지 않음. 운영 도메인77·더미177과 분리. 시험 controller는 새 격리 프로세스이며 운영 재기동이 아니다.

검증 결과:
- 후보 단위18·출력 소유권2개 통과(후보소스 메서드, 설치본 해시일치).
- 실제 후보 설치본 client/HarvestMission/FSM과 격리 ROS 대역 Action서버 통합5시나리오 통과. TF복구off/추가 client속도publisher 없음.
- 2회 abort 후3번째성공4.165초(goal_timeout1초), 대기중취소goal1회, retry상한1회에서총2goal, 다른오류107재시도없음, 실제실행0.3초제한 후 약0.322초취소종료확인.
- 실제 Nav2 결과분류 시험과 대역서버 FSM 시험을 구분. 로봇 장비물리동작/전체수확node조립/실제최신costmap회복후재주행은 미검증.
- 종료후 격리 controller/검사 프로세스 없음, 기존 운영 소스/설치본 해시 불변·신규파일 운영미존재 확인. 이번 조회 시 운영 launch/harvest/bridge도 실행목록에 없었으며 에이전트가 종료하지 않았다.

결과/백업 PC 보존: runs/navigation_retry_candidate_20261026/robot_verification_bundle.tar.gz 및 robot_verification/. SHA256 `c17279039c7749a3c9f8265e34e8c2009a7b3af52918adf1a3f8fcd643a30783` 원격일치. module_load.json, build.log, unit/owner 및 ROS검사로그, actual Action/FSM JSON 포함.

### 실제 적용 전에 할 절차

사용자 명시승인 및 사용자 종료 확인 후에만 교체한다. 적용 직전 운영 해시/신규파일 부재/프로세스 부재를 재확인하고 최신본 추가백업. 변경6소스·대응6설치모듈을 같은 종료구간에 적용한다(기존5+신규1). 설정은 `/home/vic/Downloads/pc_dummy_fsm_candidate_20261023/harvest.json`에 `navigation_collision_retry_count:5`만 추가한 harvest.candidate.json을 제안. navigation_policy의 tf_recovery_enabled=false, goal_timeout300, 충돌검사/footprint/전용인계설정은 변경하지 않는다. activation_manifest.json에 원본/후보해시와 단일 의미변경 기록. 아직 적용하지 않음.

원복: 관련 프로세스 종료 확인 후 operating_backup과 harvest.before.json에서 교체한 기존5소스/설치모듈 및 설정만 복원, 신규 collision_recovery 소스/설치본은 후보해시일치 확인 후 제거, 관련pyc무효화·모듈/해시검증. 기존성공로그·복구저널·전체설정을 과거로 되돌리지 않는다. 백업 전체를 일괄 덮어쓰지 않는다. 실제 교체 후 운영 경로 import·전체노드기동검증은 별도이며 사용자에게 먼저 안내한다.

운영 적용·재기동·실제 이동·Git commit/push 없음.


## 2026-10-26 14:47 재시도 후보 운영 적용 완료 (재기동 미실시)

사용자 명시 승인 후 SSH 조회와 적용 직전 /proc 검사에서 운영 관련 잔존프로세스 없음 확인. 운영 소스/설치본 기준해시 및 신규파일 부재, harvest 설정 원본해시 일치 확인. 추가백업 `/home/vic/Downloads/navigation_retry_build_20261026/apply_backup_20261026_144750/originals.tar.gz`에 교체전 파일·캐시·인계설정·공통주행설정·복구저널 보존. 기존 백업/성공실패기록 유지.

운영 sensor_hold_robot_20261024의 소스6개/설치모듈6개(기존5+신규collision_recovery각1)와 pc_dummy_fsm_candidate_20261023/harvest.json을 적용. harvest 설정의 유일한 의미변경은 navigation_collision_retry_count=5. 관련 pyc5개 백업 후 무효화. 다른 핫픽스/인계설정/공통주행설정/복구저널 해시 전후동일.

운영 설치경로 모듈11개·harvest_node 진입점 import 성공, 변경모듈6개 후보해시 일치. 실제 환경로더→수확설정로더 확인 결과 수확retry5/공통NavigationSettings retry0/tf_recovery_enabled=false/goal_timeout300초. 진입 전용 settings 선택에도 retry5 유지 확인. 노드 생성/main 실행/재기동/초기위치/이동 없음. 실제 기동시 전체조합·실기주행은 여전히 미검증.

PC 보존 runs/navigation_retry_candidate_20261026/applied_verification.tar.gz 및 applied_verification/. SHA256 `76e4f39582e110f928a0034ebf5368bf4407a1052399ecdc20ffb949da632754` 원격과 일치. apply_result.json의 대상13파일해시/신규파일/불변파일, operating_load.json의11모듈경로/설정확인, 추가백업 포함.

원복은 종료확인 후 추가백업의 기존5소스/설치본·harvest설정만 복원하고 신규collision_recovery2개는 적용해시일치 확인 후 제거·관련캐시무효화·원본해시/import 확인. 다른설정/저널을 백업시점으로 되돌리지 않는다. 코드 Git commit/push 없음.
