> 2026-10-27 커밋 준비: 실제 로봇의 `zenoh-control-without-arm.json` 전체 설정을 추가했다.
> 팔/시험 모드 제외 목록은 모두 포함돼 있다. 아래 미배포·미전환 문구는 최초 준비 당시 기록이다.
> 현재 실행 진입점/별칭은 `robot/tools/terminal/jetson_release_20261027/README.md` 참조.

> 2026-10-27 V3 후속: PC 메시지/발행/설정에서 비상정지 항목을 제거했다.
> 도메인77/TCP18449 및 브리지 설정 변경 없음. 로봇 V3 재빌드 완료, 사용자 기동 및 실제 왕복 검증은 남았다.
> 아래는 최초 PC 준비 당시 기록이며 alias는 이후 격리 설치본으로 전환되었다.

# Jetson 회신 기반 PC 준비 설정 — 미배포

근거: MANYFARM_JETSON_PINKY_REPLY_20261027.zip의 REPLY_KR.md 및 zenoh-jetson-pinky.json.

- zenoh-pinky-jetson.json: Pinky 팔 전용 peer 설정. 기존 PC 더미 peer 대신 Jetson192.168.0.29:18449 연결.
  관제 브리지에 이 allow 목록 전체를 적용하지 않는다. 기존 별칭/프로세스를 자동 전환하지 않는다.
- cyclonedds-loopback.xml: 회신 첨부 원문. 실제 환경은 Jazzy, rmw_cyclonedds_cpp,
  ROS_DOMAIN_ID=77, ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST, CYCLONEDDS_URI는 이 파일의 설치 경로.
- control-bridge-jetson-exclusions.json: **제외할 주소 목록이며 독립 실행 config가 아니다.**
  운영 관제 설정이 deny 기반이면 기존 deny 항목을 보존하며 이 주소를 합친다.
  allow 기반이면 기존 관제 주소는 유지하고 이 팔 주소가 허용되지 않도록 목록을 조정한다.
  allow/deny를 동시에 새로 붙이거나 과거 스냅샷으로 운영 설정을 덮어쓰지 않는다.
  이번 PC 작업에서는 실제 관제 설정/별칭을 변경하지 않았다.

queries_timeout: default20초, actions.send_goal/cancel_goal5초, get_result1300초.
Jetson 수확 프로필은 harvest_handoff_jetson_real이며 운영 laun의 선택은 아직 바꾸지 않았다.

이 파일만으로 실물 연결 준비가 끝난 것은 아니다. V3는 비상정지 입력을 요구하지 않으며
Jetson startup_auto_prepare=true라 최초 유효 ControlState 수신으로 팔 준비 동작이 시작될 수 있다.
이번에는 config 정적 대조만 했고 Zenoh 프로세스 기동·실제 연결 검증은 하지 않았다.
