# 수확 실물 로직의 공통 구조 통합 — 2026-10-18

사용자 승인: 공통 구조를 그대로 사용하고 개인 로직은 추가 설정·장치 연결로 확장한다. 별도 통합 브랜치에서 검토하며 실물 배포는 수행하지 않는다.

## 기준과 범위

- main: `2a397da842300823cec077210ac7857024a6f66a` (공통 주행 변경은 `7b0e1a4`까지, 이후 sim 변경도 유지).
- 실물 원본: `feat/apriltag-localization`의 `afdcc051bcb947c4d8e48c6a6da865ee9daf9fbf`.
- 전달 문서: `NAVIGATION_COMMON_REAL_HANDOFF_20261016.md`.
- main 기반 선택 통합이다. 실물 브랜치 전체를 merge한 것이 아니며 로봇 PC의 미커밋 파일은 확인하지 못했다.
- 공통 Nav2·미션·태그 관측 모델·시간 설정·복귀 구조를 유지한다. sim 전용 실행 코드/프로파일은 수정하지 않는다.

## 파일별 변경

경로는 `farm_project/` 기준이다.

| 파일/경로 | 변경 |
|---|---|
| `robot/config/robots/vicpinky/nav2.yaml` | shared_nav2 유지. 실물 override: 진입 lookahead/curvature 0.10m, local resolution 0.025m, footprint x±0.30/y±0.25m, padding 0.02m |
| `robot/config/harvest/harvest_real.json` | 공통 task_navigation_policy 유지. 진입 시작 허용 거리 0.20m 및 transfer 설정 추가 |
| `robot/config/localization/harvest_real.yaml` | 10/14 실물 등록 자산·bias·지도 해시 복원. 관측 모델은 동일 내용인 common_observation_model.json 공유 |
| `robot/config/localization/{reference_20261014,bias_trial_20261014}/` | 원본 실물 등록 자산과 bias 프로파일 보존 |
| `robot/config/maps/{many_farm,harvest_field_20261007}/` | 실물 브랜치 지도/그래프 원본 보존. 활성 many_farm은 순찰 실물과도 공유하므로 함께 검토 필요 |
| `robot/ros_ws/src/harvest_robot/harvest_robot/configuration.py` | 공통 설정 로더에 선택적 진입 거리 및 transfer 파라미터 변환 추가. 미지정 환경은 기존값/인계 OFF |
| `robot/ros_ws/src/harvest_robot/harvest_robot/{node,status}.py` | 공통 노드에서 선택적으로 인계 연결, 인계·적재·복귀 상태 보고 |
| `robot/ros_ws/src/harvest_robot/harvest_robot/transfer_*.py` | 원본 인계 상태기계·장치 어댑터 보존. communication만 공통 설정/작업 소유권에 연결 |
| `robot/ros_ws/src/farm_common/farm_common/action_handoff.py` | 기본 작업↔복귀 선점 유지. 인계는 유휴 상태에서만 예약하고 실행 중 선점 금지 |
| `robot/ros_ws/src/farm_interfaces/{action/DockTransfer.action,srv/TransferEvent.srv,CMakeLists.txt}` | 원본 인계 인터페이스 추가. 공통 ReturnToStation 유지 |
| `robot/ros_ws/src/harvest_robot/package.xml` | std_srvs 의존성 추가 |
| `robot/ros_ws/src/farm_bringup/launch/harvest.launch.py` | 동일 런치에서 환경별 transfer 파라미터 전달 |
| `robot/tools/tag_camera/bias_trial/trial.py` | 공통 설정 출처 추적 유지, 실물 bias 10/14 및 준비 상태 재시도 복원 |
| `robot/tools/tag_camera/harvest_graph_goal.py` | 새 그래프 실제 진입 엣지 12→14를 기본 목표 방향으로 사용 |
| 관련 `test/` | 공통 설정·실물 override·인계 배타 실행 검증. 과거 주행/영상 기록 테스트는 당시 지도/자산 fixture에 명시적으로 고정 |

## 추가 설정 위치

주행 수치: `vicpinky/nav2.yaml`의 `overrides`. 공통 정책 변경은 공유 파일에서 별도로 검토한다.

인계: `harvest_real.json`의 `transfer`에서 `enabled`, `device_services`, `capacity_count`, `loaded_count_topic`, `stage_timeout_s`, `stop_timeout_s`, 선택적 `journal_path`를 설정한다. 현재 서비스 매핑은 비어 있으므로 인계 요청은 거절된다. 장치 이름·적재량을 임의로 만들지 않았다. 미확인 인계 기록은 재시작해도 차단을 유지한다.

실물 완료 정책은 기존 이동 전용 `ARRIVAL_ONLY_NO_HARVEST`를 보존한다. 팔 수확 활성화가 필요한 경우 실제 팔 endpoint와 완료 정책을 별도로 설정해야 한다. station_config 미등록 상태의 실물 복귀도 자동 활성화하지 않는다.

## 검증 결과와 한계

- harvest_robot 전체 unittest: 104/104 통과. 실제 공통 설정 로딩, 실물/시뮬 설정 분리, 인계 정상 시퀀스·장치 미연결·예약 충돌·저널 실패·취소·시간초과/재시작 차단 포함. ROS 장치는 fake로 대체했다.
- farm_tag_localization: launch_contract 15/15, trial_configuration_snapshot 3/3, capture_session 5/5 통과.
- farm_navigation shared_configuration: 6/6 통과. 위 완료된 묶음 합계 133개.
- pixel_bias: 8개 통과, 실제 영상 solve 1개는 cv2 미설치로 실행 불가.
- 태그 전체 discovery는 성공하지 않았다. ROS launch_ros/OpenCV 및 로컬 부분 체크아웃의 sim 호환 모듈·심볼릭 링크가 없는 항목은 검증 제한이다. 이를 실제 코드 성공으로 집계하지 않는다.
- ROS/colcon 빌드, Nav2 프로세스 실행, Isaac, USB 카메라 및 실물 장치 구동은 미실행이다.

재현: 저장소에서 robot/ros_ws/src 아래 Python 패키지 디렉터리를 PYTHONPATH에 추가한 뒤 `python -m unittest discover -s <패키지>/test`를 사용한다. 선택 묶음은 `-p test_launch_contract.py` 등으로 지정한다. ROS 설치 환경에서는 `colcon build --symlink-install --packages-up-to farm_bringup harvest_robot` 후 해당 환경의 테스트와 정지 상태 장치 연결 검증이 필요하다. 새 인터페이스·공통 Nav2 플러그인도 재빌드 대상이다.

## 적용과 복원

별도 `integration/shared-real-harvest-20261018` 브랜치로 제공한다. main과 기존 실물 브랜치, 로봇 실행 상태는 변경하지 않는다. 반영 전 현재 PC의 미커밋 변경/장치 설정을 비교하고, 운용 지도 변경이 순찰 로봇에도 맞는지 확인한다. 되돌릴 때는 원래 실물 브랜치 및 실행 설정으로 복원한다. 인계 저널은 물리 상태 확인 없이 삭제하지 않는다.
