# OpenCR 값 갱신 — 2026-10-27

사용자 제공 20261023/20261027 zip을 파일별 비교했다. 동작 변경은 통합/시험 스케치 LID_DEF.stime_ms=1500→1350ms 한 가지. 덮개 개폐 전체 약4.4→4.0초. 주행, 앞문, 틸트, 통신 프로토콜 불변.

ROS 브리지는 설명과 주석만 갱신하며 lid_timeout=10초 유지. DONE 응답을 기다리므로 운송 FSM·관제 계약 변경 불필요. 시뮬·URDF·도킹·티칭 불변.

로봇 UART ping/dump 직접 확인: PONG, lid=1350ms, gate=1200ms, tilt up/wait/down=8000/2000/9000ms, IDLE. 기구 동작 명령 없음. 현재 실행값 일치 확인이며 전원 재기동 후 영속값 검증은 아님. PC Arduino 환경 없음; 펌웨어 재빌드/플래시 미실행. 기존 보드 바이너리를 교체하지 않았다.

통합 소스: robot/firmware/opencr/oc_tb3_actuator. 원문 README 보관. 시험용 스케치와 바이너리는 운영 경로에서 제외. 소스 복사로 보드 플래시가 바뀌지 않는다. 향후 컴파일은 주행 포함 oc_tb3_actuator 사용.

검증: Python 모듈 설명 제거 후 AST 동일, YAML 주석 제외 내용 동일. 두 공유 스케치 actuator.cpp 동일. 구버전은 원본20261023 zip 및 outputs/firmware_review_20261023에 보존.
