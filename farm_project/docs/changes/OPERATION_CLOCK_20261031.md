# 공통 동작 시계 정합 (2026-10-31)

사용자 승인: 시뮬 실행 시 공통 코드가 시뮬 시간을 사용하도록 구현하고 커밋·푸시.

## 동작

`farm_navigation.operation_clock.operation_time(node)`는 활성 ROS 시뮬 시계를 사용하고, 실물은 기존 단조 실제시간을 유지한다. 시간 한도·허용오차는 그대로다. 독립 테스트의 node=None은 기존 단조 시계 계약을 유지한다. 운송 센서 수신과 만료, 도킹 서버·클라이언트·lease, 예찰 RPC, 수확 인계의 입력/동작 대기 생산자·소비자를 함께 변경했다. 실제시간 sleep/Condition polling은 CPU 양보 용도이며 동작 마감 판단에는 사용하지 않는다.

노드 생성 시 use_sim_time을 올바르게 설정해야 한다. 운행 중 시계 종류를 변경하는 것은 지원하지 않는다. clock=0은 실제시간 fallback하지 않는다. 시뮬 pause 중 취소 요청은 계속 처리되지만, 정지 결과 자체가 도착하지 않으면 시뮬 시간 재개까지 기다릴 수 있다. 이는 요청된 정책이며 OS 종료 정리 시간은 별도로 유지한다.

## 검증과 한계

- 작업 트리 126 tests passed. sim pause/실제시간 지연, 시뮬 한도 만료, 실물 단조 시계, 취소, lease reset/오래된 cache 거절, Nav2/Spin·인계·배출 회귀 포함.
- farm_navigation, farm_common, farm_docking, harvest_robot, transport_robot, scout_robot 빌드 성공.
- 커밋할 변경만 별도 HEAD 복사본에 구성한 회귀검사118PASS. 기존 미커밋 스테이션 방향 선택·TF 무제한 대기·Nav2 lifecycle 준비·예찰 RPC timeout 설정은 로컬에 보존하고 이 커밋에는 포함하지 않는다.
- 실제 시뮬 통합/촬영 ON/OFF 비교는 아직 하지 않았다. 실행 중 프로세스는 기존 코드이며 다음 노드 시작부터 적용된다.
- sim UDP/clock relay/world command watchdog 및 시험 도구는 후속 대상이다. 공통 정합만으로 영상 저장 지연의 모든 실패가 제거됐다고 주장하지 않는다.
- 모든 프로세스를 유지한 채 시계를 되감는 reset 복구는 보장하지 않는다. 기존 시험기의 reset은 해당 ROS 노드도 재시작한다.

## 되돌리기

이 커밋을 revert하고 위6패키지를 재빌드한다. 진행 시험의 로그와 기존 미커밋 변경은 삭제하지 않는다.
