# 실물 성공 보존본 대조 및 적용 전 수정 — 2026-10-18

사용자 승인: “수정해줘”. PC 작업 브랜치의 단계1~5 변경을 보존하고 아래 두 실행 입력만 수정한다. 커밋은 사용자가 VS Code에서 수행한다.

## 기준과 이유

- 작업 기준: feat/harvest-handoff-real-20261018 / 8466ac1 + 단계1~5 및 인수인계 문서. 이 패치는 기존 미커밋 작업을 초기화하지 않는다.
- 10/13 c4d96a9: 실측 footprint x±0.30/y±0.25m, padding 0.02m 성공 상태 보존.
- 후속 2fcdebf: 진입 lookahead/curvature 0.10m, local resolution 0.025m. 현재 override와 동일하다.
- 10/14 새 지도 및 최신 실물 브랜치 afdcc05: 12→14 목표 방향. 13번 노드가 없는 현행 그래프에서 PC trial.py의 13 지정은 목표 생성 오류를 일으킨다. 12로 복원한다.
- Jazzy costmap은 로봇 namespace 아래 local_costmap/global_costmap namespace를 사용한다. 상대 scan_filtered를 기존 실물 절대 /scan_filtered로 덮어써 기존 launch의 /harvest_01/scan_filtered remap을 유지한다. AMCL bindings.scan_topic은 변경하지 않는다.
- 사용자 합의에 따라 공통 PoseProgressChecker(0.1m 또는0.1rad /20초)를 유지하여 실물에서 비교한다. Simple override는 추가하지 않는다.

## 영향과 검증

운영 변경은 robot/tools/tag_camera/bias_trial/trial.py와 robot/config/robots/vicpinky/nav2.yaml 두 파일이다. 공통 구현·시뮬 설정·지도·태그 모델·통신 환경은 수정하지 않는다. 새 장치 endpoint도 추가하지 않는다.

verify_field_fix.py는 ROS를 시작하지 않고 실제 설정 로더로 병합값, 센서 연결값, Pose 및 현장 수치, trial의 인자와 실제 목표 생성기의 지도 엣지/방향을 검사한다. 패치 적용 검사·Python 구문 검사도 수행한다. 이는 ROS 구독 연결이나 실물 주행 성공 검증이 아니다.

로봇 적용 후 별도 확인: 빌드, 두 costmap의 실제 /harvest_01/scan_filtered 구독, Nav2 active, 초기 위치, Zenoh와 관제 표시. 이동 Goal은 별도 요청에서 실행한다. 기존 경로 시험에서 도착·회전·오류105 및 반복 회전을 관찰한다.

## 복원

이번 패치만 git apply --reverse --check 후 역적용한다. 이후 변경으로 검사 실패 시 강제로 되돌리지 않는다. 로봇 전체 백업은 PC /home/eunbi/harvest_robot_before_common_20261018_MpRA3u에 보존돼 있다. 이 작업은 로봇 복사·빌드·실행·커밋·푸시를 수행하지 않는다.

이번 직접 검증: verify_field_fix.py 세 그룹 PASS (실제 설정 병합 및 기존 목표 생성기 실행). 원본 운영 두 파일은 사용자가 올린 비교 보고서 PC SHA256과 일치 확인.
