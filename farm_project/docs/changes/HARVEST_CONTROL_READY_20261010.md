

<!-- HARVEST_CONTROL_READY_20261010 -->
## 관제 좌표 수신 정합 수정 — 2026-10-10

사용자 “좌표받아서 갈수있도록 코드 분석해서 준비” 승인 범위. 준비본·미커밋이며 PC/로봇 설치와 실주행은 별도다.
기준 Git: main feat/apriltag-localization 25cdf88 / Frontend main 5909f0d.

이 기록은 앞서 HARVEST_CONTROL_LINK_20261010.md의 Domain156 및 예찰에 many_farm_v1/SEC_01을 보내라는 안내를 정정한다.
현재 통신 Domain은77(사용자 변경 완료 보고), 카메라 별도 환경은 유지한다.
관제/예찰 통신은 farm_map_v1/SEC01 그대로다. 예찰과 수확 환경 YAML은 같은 maps/many_farm/many_farm.yaml 및 graph.geojson을 참조한다.
수확 내부 many_farm_v1/SEC_01과 태그 기준은 보존하고 harvest_real.json control_aliases에 위 두 ID의 명시적 대응을 추가한다.
contract.py에서 지도/구역을 검사하고 mission.py에서 구역을 해석한다. 원본 Goal·좌표·yaw·작업 ID는 변경하지 않는다.
등록되지 않은 지도/구역 거절 유지. 별칭 설정 없는 시뮬 등은 기존 계약 유지.
Frontend control_core.py와 HarvestTask.action의 section_id 전송을 맞춘다. Control 키보드 관제 패치도 포함하나 웹은 Frontend 패치가 필요하다.
각 저장소에 패치 적용 및 인터페이스 재빌드/프로세스 재시작이 필요하다. 이전 패키지의 project 문서4개 적용만으로 관제 수정이 완료된 것이 아니다.
예찰 scout_new·지도·그래프·태그 보상·Nav2·footprint·제어기·모터 설정은 수정하지 않는다.
수확의 현재 SUCCESS는 도착/정지 성공이며 실제 수확량은0이다. 물리적20cm 유지 및 카메라 종료 문제는 동결 기록의 후속 과제다.
직접 검사 및 미실행 범위는 전달물 VALIDATION.md, 배포/실행/로그는 RUN.md를 따른다.
복원: PC /home/eunbi/vmany_backups의 이번 파일만 비교 복구하고 harvest_robot 재빌드. 관제 인터페이스를 되돌리면 의존 노드도 함께 재빌드한다. commit/push 자동 수행 없음.

### 공유 DM의 통신 문서 대조 및 Status 추가

공통11796484(v18), 수확4358169(v37), 인계16908315(v10)를 직접 읽었다.
/harvest_01/status RobotStatus를 실물 이동 전용 정책에서1초마다 발행한다. boot_id는 프로세스마다 새 UUID, sequence는 발행마다 증가한다.
관제 map_id=farm_map_v1, 실제 최신 map→base TF, 현재 task_id, IDLE/NAVIGATION_MOVE/ERROR와 ready를 보고한다.
ready는 작업/종료/정지 미확정 여부, 유효 TF, FollowPath 서버 발견을 반영하며 실제 Goal의 기존 preflight 검사를 대체하지 않는다.
이동 전용 단계에서는 transfer_required=false, loaded_count=0으로 보고한다. 이는 수확/적재 기능이 없는 현재 운용 값이며 실제 적재 센서 검증 완료를 의미하지 않는다.
문서 규약상 수확 인계가 필요하면 true를 유지하고 인계 완료+적재 해소 확인 후 false로 바꿔야 한다. 실제 dock_transfer/transfer_event/배출장치/FSM은 이번에 구현하지 않았으며 가짜 완료 신호를 발행하지 않는다.
배터리 입력은 설정 battery_topic의 sensor_msgs/BatteryState.percentage(0–1)를 사용한다. 현재 실제 드라이버의 topic/percentage 제공 여부는 확인되지 않았다.
미수신/NaN/5초 만료 시 battery_percent=0.0은 미측정 자리값이며 error_code/error_message에 BATTERY_UNAVAILABLE을 명시한다. 이 값으로 잔량0%를 표시하거나 저전압 동작을 트리거하면 안 된다. 프로토콜에 unknown 필드가 없다는 한계가 남아 있다.
위치 미확인도 POSE_UNAVAILABLE+ready=false로 보고한다. 상태 발행 실패/태그 누락을 새 주행 중단 조건으로 연결하지 않는다.
인계 문서의 harvester_01 표기는 최신 수확 문서 및 Git의 harvest_01과 다르므로 현재 endpoint는 harvest_01을 유지한다.
수확 프로토콜 문서에는 section_id가 빠져 있고 현재 수확 Git은 요구한다. 이번 전달물은 Git의 확장 필드를 유지하며 Frontend도 맞추는 방안이다. 문서와 완전히 일치한다고 주장하지 않으며 인터페이스 변경 사항을 관제 담당자에게 전달해야 한다.
