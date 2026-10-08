# 도착 후 시뮬 팔 작업을 기다리는 공통 연결

기준 `main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd` 이후 로컬 미커밋 변경이다.

사용자는 기존의 넓은 공통 후보조회/단일 과실/Window 실행기 제안을 대신하여, “대부분의 로봇팔 구동 코드가 시뮬레이션 전용 … 공통코드에서 도착하자마자 result를 날리는 형태면, 그부분은 수정해서 sim 전용 로봇팔 동작 코드에 연결”하도록 확정했다.

공통 `harvest_robot` 변경은 다음으로 한정한다.

- `node.py`: `ARRIVAL_THEN_ARM` 설정과 내부 Action client 수명 관리. 실물 모드에서는 이번 시뮬 장치로 자동 대체하지 않는다.
- `mission.py`: 기존 Navigator의 이동/정지 확인 후 팔 요청, 완료 대기, 오류 시 팔과 주행 각각 취소 정리.
- `arm_client.py`: 기존 HarvestTask 형식 재사용, 서버 준비/응답/실행 시간 제한, 요청 ID·결과·누적 수량 검증, 자기 UUID의 취소 ACK 및 terminal 대기. 정지 미확인은 차단 상태로 전달.
- `communication.py`, `contract.py`: 장치가 확정한 누적 수량과 결과 전달, 이동/팔 오류 구분, 부분 수량 보존. 기존 `ARRIVAL_ONLY_NO_HARVEST` 설정의 이동 전용 동작 유지.

`farm_interfaces`와 외부 관제용 HarvestTask 필드는 바꾸지 않았다. 후보·좌표 정답·색상·도달 조건·Teacher·복귀·성공 판단은 `sim/`에만 있다. 실물 설정/모델, 공통 주행/비전, 기존 상태 전환 구조도 변경하지 않았다.

정상 후보 전체 처리 후 `SUCCESS`는 수확 성공 수량과 별개다. 예를 들어 2개 안착/1개 실패면 `SUCCESS, harvested_count=2, failed_count=1`이다. 예상 수량을 그대로 성과로 반환하지 않는다. 비정상 중단은 `FAILED`, 확인된 취소는 `CANCELED`, 정지 미확인은 `FAILED/CANCEL_UNCONFIRMED`와 새 작업 차단이다.

시뮬 설정은 `harvest_task.json`의 내부 endpoint `sim/harvest_arm`을 선택한다. 공통 코드는 시뮬 패키지를 import하지 않는다. 새 카메라 기반 정책/실물 장치 연결과 계약 변경은 이번 구현의 완료 범위가 아니다.

검증: client/mission/통신 단위 11개, ROS bridge 단위9개, 실제 ROS/UDP2개(누적 결과·자기 Goal 취소·센서/속도 명령 병행). harvest_robot 및 sim3패키지 빌드 통과. 실제 Isaac 정책 시험과 전체 Nav2 도착 포함 시험의 구분은 [실행 보고서](../../sim/docs/TEACHER_HARVEST_RUNTIME_20261006.md)를 따른다.

되돌림: 실행을 중지한 뒤 시뮬 `harvest_task.json`을 `ARRIVAL_ONLY_NO_HARVEST`로, 장치 `harvest.json`의 `runtime.harvest_arm.enabled`를 false로 바꾸면 팔 연결을 끌 수 있다. 소스 되돌림은 위 공통 파일의 이번 변경만 대상으로 하며 다른 작업자의 변경을 초기화하지 않는다. 물성·동적 물리의 별도 설정은 그대로 유지된다.
