# 예찰 작업본 Git 반영 — 2026-10-28

## 범위와 승인
사용자 요청: 예찰 포함 워크스페이스 커밋·푸시, 메시지 `fix : scout로직 변경 및 에러 수정`. 게시 브랜치 feature_dongmin. scout_integration_20261027/farm_project의 소스·설정 차이 113개를 게시 저장소에 반영했다. 원본 작업 폴더는 유지한다. 기존 미커밋 운송 지도 복원도 포함한다.

## 포함 내용
- 예찰 카메라 장착 URDF/메시, 워밍업·오프라인 모델 로딩·워커 재사용, MJPEG/RViz.
- 관측 4→8→9, 그래프 기반 수확 목표, 윈도우 중첩 완화, TF 재수신·주행 시작 처리.
- 예찰 작업본에 포함된 공통 주행/태그 및 traffic 인터페이스와 Nav2 controller 패치(출처·라이선스 포함).
- ID 기본 정책은 거리 일대일 연결 및 중앙값 갱신 유지. fruit_association은 별도 후보 모듈이며 자동 활성화하지 않는다.
- 운송 환경·장치·목적지 map_id=farm_map_v1 및 transport_real 지도 복원.
- scout_scripts에 기존 예찰 실행 스크립트를 보관한다. 환경 의존사항은 해당 README 참조.
- sim 전용 파일과 수확·운송 패키지 업무 소스는 이번 복사에서 변경하지 않았다. 공통 코드 변경의 시뮬 영향까지 검증 완료했다는 의미는 아니다.
- 실행 데이터·백업·빌드·설치 산출물 및 비밀키는 커밋하지 않는다.

## 이번 검증
- 게시 소스 기준 PC colcon 18개 패키지 빌드 성공(58.2초).
- scripts/test.sh 운송·수확 및 통합 회귀 99개 통과.
- 예찰·공통·태그 시험 파일별 독립 실행: 310 통과, 49 실패. 전체 시험 통과 아님.
- 실패: sim depth_tolerance 기본값 차이 1개, sim multi-tag 비활성 설정에 대한 시험 가정 차이 8개, sim traffic_zones.yaml 부재 21개, 테스트 더블의 worker 속성 누락 4개, launch 더블 handoff_config 누락 13개, Nav2 더블 global_costmap 누락 2개. 시험 통과만을 위해 운영 설정 또는 sim 파일을 변경하지 않았다.
- 초기 일괄 수집은 가짜 ROS 모듈 충돌 및 미로드 인터페이스로 실패했으며, 빌드 인터페이스 로드 후 파일별 실행으로 위 결과를 확인했다.
- 실물 재배포·브링업·주행은 이번 작업에서 수행하지 않았다.

## 추적
로컬 백업: backups/before_scout_publish_20261028_173543. 변경 목록과 상세 시험 출력은 로컬 reports/scout_publish_manifest.json 및 scout_publish_tests.json. 로그는 /tmp/scout_publish_build.log, /tmp/scout_publish_transport_tests.log. 이 산출물은 Git 제외.
