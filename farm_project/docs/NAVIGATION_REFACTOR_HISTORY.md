# 공통 주행 이관 기록

## 수정 전 보관

백업: `/home/rungmin/Documents/ChatGPT/프로젝트ROS/outputs/navigation_refactor/before_20261001_150355`

scout_robot 패키지, farm_bringup, 시뮬 장치 런치, 시뮬 설정과 robot/config를 수정 전에 복사했다. 이전에 이미 변경되어 있던 setup.py·scout_survey.launch.py와 scout_new도 백업에 포함한다. 미니관제 원본은 수정하지 않았다.

## 이전 구현

- farm_project 기존 survey_server와 scout_new는 NavigateToPose로 관측 위치를 순차 방문했다.
- scout_new는 State별 비동기 완료 구조지만 Navigator가 ScoutNode의 _nav/_odom/_tf 내부 필드를 사용했다.
- 미니관제의 수확 윈도우 이동은 preview_pose → 자체 RouteToPose → Path 보간 → execute → FollowPath였다.
- 미니관제의 노드 ID 경로 선택은 ComputeRoute → FollowPath로 별도였다.
- 전체 설명과 당시 지도·소스 사본은 ChatGPT 작업공간 docs/harvest_route_handoff에 보존돼 있다.

## 현재 변경

farm_navigation 추가, 예찰 공통 기능 연결, 기존 route/arrival import 호환 유지, 환경 선택 YAML과 통합 launch 추가. 기존 과실 계산과 베드 설정은 유지했다. 도킹·교통·실물 드라이버는 구현했다고 주장하지 않는다.

## 남은 적용 조건

시뮬 그래프에 베드 간 통로가 없어 현재 기본 모드는 navigate_to_pose를 유지한다. FollowPath 공통 실행은 연결 그래프와 일치하는 시작·목표를 준비한 환경에서 선택 가능하다. 실제 지도 연결 데이터가 확정되기 전 임의의 연결을 넣지 않는다.

실제 아이작심 이동·카메라 관측 E2E 검증은 이번 자동 검사와 별개다. E2E 후 scout_new 최종 위치 이관·중복 실행 코드 정리를 진행한다.

## 확인 결과

- 공통 그래프·경로 변환·환경 선택·중단 계약 검사 14개 통과.
- 예찰 State 흐름 검사 16개 통과. 기존 과실 수·피드백·부분 결과·늦은 응답 차단 보존.
- 기존 도착 검사 10개, 16개 베드 검사 5개, 기존 Segment 검사 13개 통과.
- 격리 도메인 198의 실제 ROS FollowPath 모의 서버: 경로/플러그인 전달, 오류 결과, Goal 거절, 늦은 승인 취소 통과. 실제 구동 장치 없음.
- 격리 도메인 197의 ScoutArea 접수·거절·취소·재접수 통과. /clock 정지 상태에서 종료 처리 확인.
- sim/real 런치 구성과 환경 혼합 거절 확인. Launch 액션 구성만 했고 장치·프로세스를 실행하지 않음.
- 시뮬 그래프 16개 구역 및 미니관제 그래프 40개 엣지 표시 검사 통과.
- 격리 빌드 /tmp/farm-navigation-build에서 farm_navigation, scout_robot, farm_bringup, farm_sim_runtime, farm_sim_config 5개 패키지 빌드 통과. 운영 install은 재빌드해야 함.

공통 테스트: robot/ros_ws/src/farm_navigation/test
예찰 상태 테스트: tests/test_scout_state_flow.py
ROS/런치 검증 스크립트: ChatGPT 작업공간 tools/verify_common_navigation_ros.py, verify_common_navigation_launch.py, verify_scout_state_ros.py

현재 공통 패키지 함수의 타입 표기와 예찰 의존 import 부재를 확인했다. 이는 실제 주행 정밀도·영상 품질·실물 안전성 검증을 대신하지 않는다.


## 실물 D435 연결 — 2026-10-01

- 로봇 bmany@192.168.0.11의 기존 `bmany_fleet_ws/run_camera_mount.sh`, `src/bmany_scout/config/bmany.yaml`, `perception_worker`를 확인했다. 원본은 변경하지 않았다.
- 새 프로젝트는 로봇 `~/manyfarm/main/farm_project`에 별도 배치했다.
- 베드 기준은 기존 MapToWorld 변환을 환산하여 경로 x=.519m, 베드 x=1.659m(법선거리1.14m), 노드2~9(3.5m)로 설정했다. 관측 노드는4·6·8이고 SEC_01/SEG_01~03을 사용한다. 자동 복귀하지 않는다.
- 실물 워커는 기존 D435 SDK/YOLO 구현을 가져와 FARM_RPC로 연결한다. 로봇 실제 입력 해상도424×240을 보존했다. 시뮬 워커는 변경하지 않았다.
- 고정 TF는 기존 장착값을 devices.json에서 로드한다. 예전 카메라 런치를 동시에 실행하지 않는다.
- 실제 노출 시각을 ROS 시각이라고 가정하지 않는다. 정지 관측 기준 TF를 저장하고 관측 구간의 위치/자세/odom 안정성을 검사한다.
- 로봇에서 실제 info/capture/YOLO 추론 성공. 당시 과실 검출은0개이므로 과실 정확도 검증은 아니다. 모터·Nav2 실행과 실기 이동 Goal은 수행하지 않았다.
- PC 회귀44개, 실물 관측 어댑터2개 통과. 로봇5개 패키지 빌드 완료. Confluence Segment별 수확목록 발행/조회 서비스 및 복귀·도킹 액션은 별도 미완료 범위다.

### 카메라 프로파일 변경
- 기존 outputs/scout_capture_wb_20260930/capture_wb.py 기록에 따라 RGB/Depth 1280×720, 6fps, 자동 화이트밸런스·자동 노출 ON, 워밍업120프레임을 적용했다. 4600K는 측정값이며 수동 고정값이 아니다.
- 새 scripts/scout_realsense_camera.py가 JSON 설정을 적용하고 기존 수신·정렬을 재사용한다. 원본 미니관제 파일은 수정하지 않았다.
