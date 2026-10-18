# 실물 local costmap 해상도 비교 시험

## 실물 성공 보존 — 2026-10-18 18:56 KST

- 사용자 보존 승인. 실물 local costmap resolution=0.02m를 이번 성공 기준으로 보존한다. 공통 코드·시뮬 설정은 추가 변경하지 않는다.
- 기록: runs/tag_bias_trial/20261018_185412_684309_on, 전달 원본 harvest_resolution002_trial.tar.gz.
- 목표 14번 (3.576, -0.035, yaw=0), graph_test_c7a18b04f61f4de6ababec0a4d547375. 18:55:17 수락 후 18:56:57 SUCCESS / SUCCEEDED / NONE. 코너 통과 후 목표 도착.
- 실제 bag costmap 해상도 0.02m 확인. costmap 419개, published_footprint 1068개 기록. 태그 관측 70회, 보정 요청/적용 각 7회.
- 이전 실패 기록 20261018_183455_478769_on과 비교 가능한 저장 입력은 real nav2.yaml local resolution 0.025→0.02만 다르다. footprint/padding·지도·태그·주행 설정 보존.
- 이번 검증은 공통 코드 기반 실물 주행·태그 보정 1회 성공이다. 반복 안정성·팔 수확·인계 물리 동작 완료로 확대 해석하지 않는다. 이전 코너 실패의 단일 원인이 해상도라고 확정하지 않는다.
- 복구 기준은 이번 백업의 코드와 설정을 대조하여 선택 적용한다. 과거 0.025m 성공본과 통합 전 로봇 전체 백업도 삭제하지 않는다.
- 문서 패치 제공 상태이며 사용자 PC 적용/백업 완료는 출력으로 확인한다. 자동 commit/push 없음. 커밋은 사용자 VS Code에서 진행한다.

## REAL-LOCAL-RESOLUTION-TRIAL-20261018 — 실물 코너 정지 비교 시험

- 사용자 승인: local costmap 0.025→0.02m 시험. 기존 성공값 0.025m를 새 성공값으로 대체 확정한 것은 아니다.
- 대상: robot/config/robots/vicpinky/nav2.yaml의 local resolution만 변경. 공통 정책, global costmap, 지도, footprint/padding, 속도, 태그, CycloneDDS/Zenoh 설정은 유지한다. 시뮬 동작 변경 없음.
- trial.py에는 local costmap/costmap 및 published_footprint 기록만 추가한다. 목표 생성·주행 순서는 유지한다.
- 사용자 제공 결과: 공통 코드 로봇 빌드 10개 패키지 성공, 관제 연결 및 PoseProgressChecker/scan 구독 확인. 18:37 주행은 코너에서 Nav2 106으로 실패했다. launch.log에 collision ahead 기록. 실행 local resolution은 0.025m였으므로 기존 해상도 누락은 아니다.
- 실패 기록: runs/tag_bias_trial/20261018_183455_478769_on. 정지 후 costmap은 실패 순간 자료가 아니므로 원인을 확정하지 않는다.
- 오프라인 검증: 설정 로더 병합·기존 보존 수치·목표 생성 검사, 기록 토픽 추가/파이썬 구문 검사, 패치 적용 검사. 0.02m 실제 주행 결과는 대기.
- 다음: 런치 재시작 후 resolution=0.02 확인, 실제 원래 출발 위치로 복귀한 뒤 올바른 초기 위치 설정, 기존 성공 순서로 Zenoh 연결, 동일 경로 1회 비교. 설정 변경만으로 해결을 보장하지 않는다.
- 복원: local resolution을 0.025로 복구 후 런치 재시작. 기록 토픽은 유지 가능. 커밋은 사용자 VS Code에서 수행하며 원격 반영하지 않았다.
