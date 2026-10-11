

<!-- HARVEST_RUNTIME_TOOLS_20261011 -->
## 2026-10-11 실행 중복 방지 및 진단 수집 정정

- 승인: 사용자 “바로잡고와 그럼”. 원본은 16:17 진단 첨부의 trial.bash(SHA256 c0cfc6a609f99c43e18d8c41761bab3a58f340e20dbd22f07695272c281e448b). 이전 도메인156 전달본도 적용 시 해시를 확인한다. 현재 Git HEAD/원격 상태는 조회하지 못했다.
- 근거: 16:13:13 실행 PID가 남아 있는 동안 16:13:41에 재실행했다. 후속 실행에서 DDS SHM 초기화 오류, 모터 초기화 실패, 라이다 종료, 카메라 시작 실패를 확인했다. 이는 최초 14시 TF 장애의 원인 확정이 아니다.
- trial.bash: 새 시험 폴더/marker 생성 전에 flock으로 동시 실행을 차단하고 launch_guard.py로 기존 수확 namespace·장치 프로세스를 검사한다. 기존 프로세스는 자동 종료하지 않는다. guard는 실행 시 한 번만 검사하며 상시 감시 프로세스를 추가하지 않는다.
- diagnose.py: 기본 30초, ROS 구독 기본 OFF. 모든 프로세스 CPU 카운터를 1초 간격으로 기록하고 카메라·검출 포함 상세 정보는 10초 간격으로 기록한다. SC_CLK_TCK와 실제 PID 시작 시각을 해석할 자료를 저장한다. PID 인자의 environment_config/params/capture_directory를 따라 실행 설정·로그를 보관한다. 최신 marker를 현재 실행본으로 사용하지 않는다.
- 반복 횟수 대신 monotonic 마감 시각을 사용한다. 선택적 --ros 자식은 종료 유예 후 TERM/KILL하며 마지막 단계(init/subscribe/receive/graph/destroy/shutdown)를 기록한다. 외부 조회 명령에는 각각 2초 제한을 둔다. OS 자체 I/O 정지까지 절대 종료 시간을 보장하지는 않는다.
- 주행 코드, TF 복구 기능, 카메라 FPS·해상도, ROS 인터페이스, DDS 설정, 지도·위치 허용치는 바꾸지 않는다. 소스 도구 3개만 추가/수정한다. 기존 tf_recovery_enabled=false는 그대로 둔다. 실물 도구 범위로 시뮬 동작 영향 없음.
- 검증: 오프라인 5개 PASS(남은 장치 검사, 다른 namespace 보존, 동시 launch 거절/marker 보존, 실행 PID 설정 연결, 카메라 포함 CPU 기록, TERM 무시 자식 KILL 포함). ROS 없는 환경에서 기본 진단 실행·압축 완료, Bash/Python 구문 검사. 상세 정확한 항목은 verify.py. 실제 Jazzy/arm64 장치·부하·TF 회복은 미검증. 패키지 무결성·설치 거절/재적용 검사 결과는 VALIDATION.md.
- 전달 파일만 생성. 사용자 PC/로봇 적용·실행·commit/push는 미수행. 사용자의 기존 수정 보존을 위해 해시 불일치 시 적용을 중단한다.
- 복원: 실행을 종료한 뒤 설치 출력 backup의 trial.bash를 원래 경로에 복사한다. 신규 launch_guard.py/diagnose.py는 실행되지 않으므로 남겨도 되며, 삭제 시 restore_manifest의 신규 파일만 대상으로 한다. 기존 /tmp/harvest_tf_diagnose.py는 이 패키지로 수정하지 않는다.
