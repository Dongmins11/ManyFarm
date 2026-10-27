# 회전 검사 대기·재개 후보 — 2026-10-26

사용자 승인: 회전 영역 밖 costmap 변경과 일시 장애물·정지 자세 변화의 즉시 실패를 보완하되 충돌·취소·정지 보호 유지. 후보 작성·오프라인 검증만 승인된 범위이며 운영 적용·재기동·이동은 하지 않았다. commit/push 없음.

## 기준과 백업

실제 로봇 `/home/vic/Downloads/sensor_hold_robot_20261024`의 src/harvest_robot, src/farm_navigation, config_candidate를 읽어 PC `runs/align_recovery_candidate_20261026/operating_source_backup.tar.gz`에 보존했다. baseline은 원본, candidate는 별도 수정본이다. baseline_sha256.json의 130개 파일은 원본 해시와 일치한다. 마지막 SSH 조회에서 변경 대상 원본 4개와 설정 2개의 해시가 백업과 일치했다. PC 저장소 원본으로 로봇을 덮어쓰지 않았다. 과거 성공과 실패 모두에 사용된 현장 수정본을 보존한 것이며 새 후보의 실기 성공을 뜻하지 않는다.

## 변경

| 후보 파일 | 변경 이유와 동작 |
|---|---|
| farm_navigation/arc_clearance.py | 실제 장애물·unknown 접촉만 ObstacleBlocked(RuntimeError 하위형)로 구분. 계산 실패·경계 이탈·잘못된 입력은 계속 오류. 기존 일반 주행 호출부의 RuntimeError 처리는 유지. |
| harvest_robot/handoff_clearance.py | 장애물 접촉 결과는 성공이 아닌 pending으로 반환하고 다시 계산. worker 고장·계산 오류는 계속 실패. |
| harvest_robot/handoff_runtime.py | align에만 고정된 허용 이동 영역과 차체 외접 반경을 포함한 사각 영역의 셀 키를 사용. 바깥 셀 변화로 기하 검사 결과가 무효화되지 않음. 영역 내부 lethal/unknown 및 지도 원점·해상도·형상 변화는 무효화. 실제 충돌 계산은 전체 지도 사용. |
| 동일 runtime | 정지 중 범위 이탈은 0 출력·재관측 대기. 이동 중 이탈·비유한값은 실패. 위치·각도·제한 수치 기록. 앞선 pending을 최종 검사에서 덮어쓰지 않음. |
| harvest_robot/handoff_planning.py | align 시작·monitor의 정지 자세 대기를 runtime에 연결. 대기 후 최신 방향으로 상대 회전각을 다시 계산. 저장 목표와 재진입 범위는 유지. |

1cm 위치 범위와 16도 실행 중 방향 범위를 확대하지 않았다. 범위 밖에 계속 머무르면 계속 정지 대기하며 자동 위치 보정이나 기준 재저장은 하지 않는다. 정상 위치로 회복되어도 최신 입력·충돌 검사·출력 소유권 검사를 통과해야 한다. 기존 무기한 센서 대기 설정과 _retry/출력 epoch/취소·정지 보호를 사용한다. 설정값 변경 없음. 이 후보는 align 범위이며 모든 경로의 오류를 대기로 바꾸지 않는다.

## 이번 직접 실행한 검증

운영 ROS 그래프와 연결하지 않는 PC 오프라인 검사 총 **91개 통과**.

- 실제 후보 runtime 메서드·gate 연결 28개: 정상 갱신, 센서 지연, 취소·정지·세션 변경 및 출력 보호.
- 새 회귀 18개: 영역 안/밖 변경, unknown, 지도 기하 변경, 허용 영역의 회전 꼭짓점 포함, 실제 장애물 충돌, 정지 자세 회복, 이동 중 이탈, pending 유지, 최신 costmap 변경, 취소, planner 상대각 재계산·monitor 연결.
- 별도 multiprocessing worker 1개: 장애물 pending → 장애물 해제 후 계산 성공 → 스레드·프로세스 종료 확인. 실제 ROS 서버 시험이 아님.
- 기존 복귀 20개, 충돌 계산 12개, 회전 12개.
- 변경 Python AST 확인. 백업 130개 파일 해시 확인.

로그: runs/align_recovery_candidate_20261026/{integration,recovery,worker,restore,arc,rotation}.log. 상세 diff candidate.patch, 변경 전후 해시 changes.json. 기존 회귀는 candidate 소스를 PYTHONPATH 선두에 두고 실행했다. mock 입력 검사와 실제 계산 프로세스 검사를 구분한다.

## 미검증·다음 단계

로봇용 빌드, 운영 플러그인/모듈 로드, 실제 ROS 부하에서 장시간 대기 후 재개, 운송 로봇 인접 시 실제 복귀는 미검증이다. 일반 주행/타 로봇 전체 E2E도 미실행. 과거 TRANSPORT_CLEAR 뒤 95.57초 대기의 원인을 이번 후보로 실증한 것은 아니다. 기존 실패의 자세 초과 수치가 없어 거리/각도 어느 분기인지 확정할 수 없다.

운영 적용 전 원본 해시 재확인과 별도 설치 경로 빌드가 필요하다. 운영 실행 경로는 아직 변경되지 않아 지금 원복할 작업은 없다. 향후 교체 시 백업의 해당 파일만 복원하고 일치 버전으로 재빌드해야 하며 프로젝트 전체를 과거 소스로 되돌리지 않는다. 후보·검사 파일은 runs 아래 보존하여 운영 코드와 분리한다.


## 2026-10-26 로봇 후보 빌드·모듈 로드 (운영 미적용)

사용자 승인으로 `/home/vic/Downloads/align_recovery_build_20261026`에 후보를 전송하고 별도 build/install에 farm_navigation·harvest_robot 2패키지 빌드 완료. ARM64/Python3.12. 운영 sensor_hold_robot_20261024와 프로젝트 설치본은 교체하지 않음. 운영 노드 기동·종료·재기동·이동·복구 저널 조작 없음. 빌드 및 오프라인 검사 프로세스만 실행·종료됨.

설치본 모듈 9개(변경 대상4개, node/factory/cycle/transfer_sequence/transfer_restore5개)의 실제 경로 확인. 변경 모듈4개 후보 SHA256 일치. harvest_node console entrypoint 로드 성공. rclpy.init/노드 생성/main 호출 없이 import만 검증했다. 이번 변경은 Python 패키지이므로 C++ 플러그인 교체나 새 pluginlib 시험 대상은 없다.

로봇 오프라인 91개 통과: 핵심28+새회귀18+별도worker1은 후보 소스 메서드 기반(설치본과 변경 파일 해시 일치), 복귀20+충돌12+회전12는 후보 설치본 기반. 초기 검사에는 로봇 테스트 누락, PC 상대경로 고정, fixture 누락/경로 오류가 있었고 테스트 복사본의 경로/의존성만 보정하여 재실행했다. 최초 실패 로그도 보존했다. 운영 코드는 이 과정에서 수정하지 않았다.

**이전 PC 기록 정정:** PC 충돌 회귀12개는 테스트가 소스를 상대경로로 직접 로드하므로 PYTHONPATH 지정만으로 후보 검증이 되지 않았다. 이번 로봇 검사에서는 복사본을 설치본 import로 수정하여 후보12개 통과를 확인했다. 이전 PC 회전 fixture도 직접 소스 로드가 포함되어 후보 전체 통합 검증으로 일반화하지 않는다. 이번에는 설치본 transfer_communication 경로로 명시해 검증했다.

colcon은 동일 이름 underlay 패키지 override 경고와 PYTHONDONTWRITEBYTECODE로 인한 byte-compiling 생략 경고를 출력했다. 2패키지 모두 빌드 성공, 후보 import 및 검사가 통과했으며 경고 로그도 보존한다.

백업 추가: 로봇 후보 폴더 operating_files_backup.tar.gz / operating_files_manifest.json에 운영 소스4+설치본4+설정2를 보존. 원본 설치본4개는 소스와 해시가 같고, 원본·설정은 이전 baseline 해시와 동일. 기존 launch PID41789/41824 및 수확 PID41851의 시작 시각·명령도 유지 확인. 원본 소스 전체130파일 PC백업도 유지.

PC 결과 보존: runs/align_recovery_candidate_20261026/robot_verification_results.tar.gz 및 robot_verification/. 전송 SHA256 `4aaa63801db8ab256824b96498f8351df10f6108ef9d49ed5efd0b830cd868f3` 원격과 일치. 설치본 로드 경로 module_load.json, build.log, 개별 회귀 로그와 초기 실패 로그 포함.

### 적용 준비와 원복 경계

- 아직 운영 교체하지 않는다. 사용자가 종료할 시점에 별도 안내하고 launch/수확 노드 종료 확인 후에만 적용한다.
- 실제 적용 시 원본10파일 해시와 최신 핫픽스를 다시 대조한다. 달라졌으면 중단하고 병합 검토한다.
- 후보 변경은 소스4개 및 대응 설치 모듈4개다. 두 패키지 버전이 섞이지 않도록 같은 종료 구간에 함께 적용하고, 운영 경로에서 다시 import·해시 검사한다. 설정2개·C++ 플러그인·controller 목록·bashrc/launch는 변경 대상이 아니다.
- 승인된 교체 후 문제가 있으면 operating_files_backup.tar.gz의 해당 소스/설치본8개만 복원·해시 확인한다. 전체 프로젝트/저널/설정을 과거본으로 덮어쓰지 않는다. 재기동은 사용자 수행.
- 실제 센서 부하·대기 후 회전 재개·전체 복귀·다른 로봇 E2E는 미검증. 빌드/모듈 로드를 실기 성공으로 보지 않는다. commit/push 없음.


## 2026-10-26 10:10 운영 경로 적용 완료

사용자가 laun/zen/dzen 종료 후 적용을 명시 승인했다. SSH 프로세스 조회 및 적용 직전 /proc 검사에서 관련 운영 프로세스 부재 확인. 원본 소스4·설치본4·설정2 해시를 적용 준비 manifest와 대조하여 모두 일치한 경우에만 진행했다.

추가 백업 `/home/vic/Downloads/align_recovery_build_20261026/apply_backup_20261026_101021/originals.tar.gz`에 원본10파일·기존 해당 pyc4개·마지막 launch console.log를 보존했다. 이전 백업과 시험 기록도 유지했다. 승인된 소스4개/설치본4개만 후보 해시로 교체하고 해당 pyc4개를 백업 후 무효화했다. 설정·controller·C++플러그인·bashrc·런치·복구 저널은 변경하지 않았다.

운영 sensor_hold_robot_20261024/install 경로에서 변경4개+연결5개 모듈의 실제 로드 경로 확인, 변경4개 해시 일치 및 harvest_node 진입점 callable 확인. 노드 생성/main 실행 없음. 운영 설치본으로 복귀20·충돌12·회전12=44개 오프라인 회귀 재실행 통과. 재기동·ROS 실기·이동 미실시. 이전 실패/복구 표시를 이번 적용으로 해제하지 않았다.

PC 추가 보존 `runs/align_recovery_candidate_20261026/applied_verification.tar.gz`와 압축 해제 폴더. SHA256 `db8ecb9254cdcefa5073efc2dcd05557a8072c7cc85808febdaab5b09b3623f9` 원격과 일치. apply_result.json에 대상8파일과 해시, operating_module_load.json에 운영 로드 경로, 개별 검사 로그 포함.

원복 시 관련 노드를 사용자가 종료한 상태에서 위 백업의 승인 대상 소스/설치본8개만 복원하고 캐시 무효화·원본 해시 및 import 확인 후 사용자가 재기동한다. 기록·설정·프로젝트 전체를 복원하지 않는다. 이번 변경 commit/push 없음.


## 스테이션 재배치 후 로봇 복구 기록 처리

사용자가 기존 스테이션 위치·방향 재배치를 확인하고 복구 표시 해제를 승인했다. 기존 robot_agent reconcile 도구를 사용해 프로세스 부재·저널 SHA 확인 후 DOCK_TEST_ec1de1850afa49fea1ca5b30c56fd037의 active/recovery_required를 해제했다. 실패 결과는 성공으로 바꾸지 않고 previous_record와 원본 백업으로 보존. 복구 근거는 사용자 채팅 재배치 확인으로 기록. 백업: /home/vic/.local/state/manyfarm/harvest_01/console-backup-1792991865409806005. PC 전후 조회/검증: runs/align_recovery_candidate_20261026/station_recovery. 다른 기록 동일·복구표시 없음·프로세스 없음 확인. 코드/설정/PC더미/관제 변경, 노드 기동·초기위치 발행·이동 없음. 아직 실행 중 IDLE 확인은 하지 않았으며 사용자 laun 기동 후 확인 필요. vstat는 프로세스 목록이며 IDLE 판정 도구가 아님.
