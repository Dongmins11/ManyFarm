# 2026-10-27 Jetson 연결 실행본 보존

로봇 `vic@192.168.0.12`의 현재 실행 진입점 원문이다. 이번 수집은 PC 저장소 보존만 하며 로봇 실행 경로·alias를 바꾸지 않는다.

- 원본 release: `/home/vic/vmany-runtime-staging/jetson_reply_20261027_1741`
- `run.bash`, `terminal.py`: release 루트에서 가져온 원문.
- `aliases.bash`: `/home/vic/Downloads/manyfarm_terminal_20261024/aliases.bash` 원문. source하면 별칭만 정의한다.
- 현재 alias는 로봇 release를 계속 참조한다. 이 저장소 폴더에서 run.bash를 직접 실행하는 용도가 아니다.

## 배치 관계

기존 release의 `src/harvest_robot`, `src/jetson_harvest_interfaces`는 저장소 `robot/ros_ws/src/`의 동명 패키지와 동일하다.
release에 두 패키지를 빌드한 `install/`이 있어야 한다. 빌드·설치 산출물은 Git에 넣지 않는다.

release `config/`에 배치된 파일의 저장소 원본:

- `harvest_handoff_jetson_real.yaml`: `robot/config/environments/`의 동명 파일. 배치 시 harvest_config만 release/config의 JSON 절대경로로 치환했다.
- `harvest_handoff_jetson_real.json`: `robot/config/harvest/`의 동명 파일.
- `zenoh-pinky-jetson.json`, `zenoh-control-without-arm.json`: `robot/config/robots/vicpinky/communication/`의 동명 파일.
- `control-bridge-jetson-exclusions.json`은 합성 참고 목록이며 실행 config가 아니다. 로봇의 옛 목록보다 PC 목록이 최신이다. 실제 관제 전체 config에는 시험 모드 제외가 반영돼 있다.

## 외부 의존성

`run.bash`는 로봇 프로젝트의 `robot/tools/terminal/environment.bash`와 release 설치본을 source한다.
terminal.py는 기존 프로젝트의 Nav2·지도·인계 설정 및 설치된 farm_bringup을 사용한다.
팔 전용 브리지는 `/home/vic/Downloads/zenoh_callback_candidate_20261023/candidate/zenoh-bridge-ros2dds`, 관제는 `/usr/bin/zenoh-bridge-ros2dds`를 사용한다.
`mf_env`, `vinit`, `vstat`의 Downloads 의존성은 alias 원문대로 남아 있다. clone만으로 현장 전체 환경이 재현되지는 않는다.

이 파일들은 운영 당시 실행 구조를 보존한 것이며, 새 배포·alias 변경·기동은 별도 사용자 요청 때 수행한다.
