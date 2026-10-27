## 2026-10-27 후속 — 배출 시험 모드 로봇 반영·재빌드 완료

사용자 “시험용 상태 전환 기능 로봇에 반영하고 재빌드 … 백업 PC … 프로세스 직접” 승인.
로봇 격리 경로 jetson_reply_20261027_1741의 jetson_connection.py, 관련 ROS 시험,
config/zenoh-control-without-arm.json 3파일만 갱신. 기존 관제 deny 보존 후 시험 서비스/토픽 제외 추가.
PC 백업 /home/eunbi/vmany_artifacts/robot_backups/transfer_test_20261027_194653/before.tar.gz,
manifest.json(해시) 및 verification.json(설치/프로세스 검증). 로봇에는 백업을 생성하지 않았다.
첫 빌드 후 이전 설치 Python 복사본이 남은 것을 해시 검사로 발견했고 소스 수정시각 갱신 후 재빌드했다.
최종 harvest_robot 빌드 성공(5.92초), 설치 import 경로/소스 동일, 기존 V3 6필드/SetBool import 확인.
소스·설정88파일 해시 대조로 지정한3파일 외 보존 확인. 실제 운영 노드/브리지 PID161238/161273/161722/161786 유지.
ROS 노드·명령·초기위치·이동/프로세스 기동·종료·저널 변경 없음. 실제 시험 서비스 왕복은 사용자 전환 후 필요.
다음: 사용자 laun/zen 재시작, PC 미니관제 서버 재시작과 웹 새로고침/시험 연결.
dzen 설정 변경 없음. 아래 로봇 미배포 기록은 이전 상태. commit/push/staging 없음.

## 2026-10-27 백업 보관 위치 변경

사용자 요청으로 이번 V3 백업을 PC /home/eunbi/vmany_artifacts/robot_backups/control_state_v3_20261027_184225/before.tar.gz로 이전했다.
SHA256 e7f056489d44f6bae15a777e669bb0ce7a48a6daeb8a9e2586317a268a77feac 일치 및 tar473항목 읽기 검증 후
로봇 /home/vic/vmany-runtime-backups/control_state_v3_20261027_184225의 백업 파일과 빈 디렉터리를 삭제했다.
아래 해당 로봇 백업 경로는 생성 당시 기록이며 복원 시 PC 보관본을 사용한다.
이전부터 있던 다른 백업은 이번 작업에서 삭제하지 않았다. 앞으로 백업은 PC Git 외부에 보관한다.
실행본·프로세스·저널 변경 없음.

## 2026-10-27 후속 — 로봇 ControlState V3 재빌드 완료

사용자 “재빌드해줘” 요청으로 로봇 격리 경로
/home/vic/vmany-runtime-staging/jetson_reply_20261027_1741의 V3 대상7파일만 갱신했다.
설정의 기존 차이는 estop 두 항목뿐임을 확인하고 원본 src/install/config/manifest를
/home/vic/vmany-runtime-backups/control_state_v3_20261027_184225/before.tar.gz에 백업했다.
jetson_harvest_interfaces/harvest_robot 빌드 성공(15.4초). 설치본 6필드/CDR/설정,
PC→로봇7파일 해시 및 설치 Python2모듈 일치 확인. launch/팔 브리지 --check 통과(충돌 PID 없음).
운영 ROS/브리지 기동·종료·이동·초기위치·저널 변경 없음. 기존 alias 경로 유지.
다음 사용자 기동부터 V3 설치본 사용. 실제 Jetson 왕복/팔 동작 검증은 아직 남았다.
로봇 로그 build_control_v3.log, log_control_v3/, manifest_control_v3.json;
PC 증거 /tmp/manyfarm_control_v3/robot_verify.log. 원래 manifest.json은 이전 배치 기록으로 보존.
원복은 관련 프로세스 종료 확인 후 백업에서 필요한 소스·설정·설치본을 대조 복원하며 저널은 복원하지 않는다.
아래 “로봇 미배포”는 이번 재빌드 전 상태다. commit/push/staging 없음.

# Jetson 회신 버전 로봇 격리 설치 — 2026-10-27

## 승인·현재 상태

사용자 “비상정지 제외하고 나머지부터 진행” 승인으로 로봇에 격리 배치·빌드했다.
기존 합의대로 프로세스 기동/종료 및 웹 작업 시작은 사용자가 수행한다.
현재 **설치 준비 완료, 운영 전환 전**이다. 비상정지 처리/고정 false는 변경하지 않았다.

로봇 경로: `/home/vic/vmany-runtime-staging/jetson_reply_20261027_1741/`.
PC 준비본: `/tmp/jetson_reply_deploy_20261027/` (임시).
기준 성공 커밋48d2d1c, 이번 코드는 PC 미커밋 상태이며 commit/push/staging하지 않았다.

## 실제 수행과 보존

- 17:41 KST 읽기 전용 확인: 성공 launch PID95587, 수확 노드95616,
  관제 Zenoh96083, PC 더미 연결 Zenoh96145가 계속 실행 중이었다. IDLE/실제 위치는 확인하지 않았다.
- 로봇 소스102파일의 해시를 PC와 대조했다. 실행 Python 차이는 이번 node/mission/arm_client 및 package.xml 범위였다.
  로봇 전용 bak·시험 차이는 원본에 병합/삭제하지 않았다.
- 별도 디렉터리에 harvest_robot/jetson_harvest_interfaces와 필요한 설정만 배치.
  manifest.json으로 전송90파일 해시 확인. 두 패키지 격리 colcon 빌드 통과(1분17초).
- 기존 운영 project_root와 성공 Nav2/지도/인계 설정을 참조한다. 새 환경 YAML의 harvest_config 경로만 격리 JSON 절대경로로 연결.
- 로봇 현재 관제 deny 설정을 읽어 기존 항목을 모두 보존하고 팔 주소 제외만 추가한 별도 config 작성.
  기존 관제·더미 config 및 terminal.py를 original_reference/에 보관하고 원본 불변 확인.
- 기존 terminal.py 실행 방식/로그/flock/중복 감지를 복사한 격리 진입점 준비.
  경로와 두 팔 브리지(기존/신규) 충돌 식별만 조정. init은 제공하지 않음.
  기존 laun/zen/dzen 별칭은 기존 운영본을 계속 가리킨다.
- 격리 설치 node/mission/arm_client/jetson_state/jetson_connection import 경로와 소스 일치,
  ControlState/RuntimeStatus CDR 직렬화 왕복, 환경/수확 설정 해석 통과.
  rclpy.init·ROS 노드·Action·서비스·초기위치·속도 명령을 실행하지 않았다.
- launch/zenoh/dummy-zenoh --check 통과 및 기존 실행 충돌 확인.
  로봇 사용 중인 수정 Zenoh binary는1.10.1. 새 config의 실제 Zenoh 로딩/ROS 왕복은 미실행.
- Pinky에서 Jetson192.168.0.29:18449 TCP 접속 성공(약215ms), 즉시 닫음.
  application payload/ControlState 전송 없음. TCP 도달성과 ROS 통신 성공은 구분한다.
- 로봇 NTP=yes, NTPSynchronized=yes 확인. Jetson과 실제 시계 오차는 아직 미측정.

## 사용자 전환 명령

현재 위치/작업 상태를 확인하고 기존 로봇 launch·zen·dzen 터미널을 사용자가 종료한 뒤에만 실행한다.
PC 더미를 새로 시작할 필요는 없다. 아래 dummy-zenoh 모드 이름은 기존 실행 도우미에서 유지한 이름이며
이 격리 경로에서는 **실제 Jetson192.168.0.29**에 연결한다.
Jetson startup_auto_prepare=true라 상태 연결 시 팔이 준비 동작을 할 수 있으므로 실물 시험 시간에 전환한다.
비상정지 입력 계약 미확정으로 실제 수확 준비 완료를 보장하지 않는다.

로봇 터미널1 — 새 수확 launch:

```bash
bash /home/vic/vmany-runtime-staging/jetson_reply_20261027_1741/run.bash launch
```

로봇 터미널2 — 기존 관제 연결, 팔 주소 제외:

```bash
bash /home/vic/vmany-runtime-staging/jetson_reply_20261027_1741/run.bash zenoh
```

로봇 터미널3 — Jetson 팔 전용 연결:

```bash
bash /home/vic/vmany-runtime-staging/jetson_reply_20261027_1741/run.bash dummy-zenoh
```

동작 없이 명령·충돌 목록만 확인하려면 각 명령 뒤에 `--check`를 붙인다.
초기위치 발행/이동 명령은 이 전환 절차에 포함하지 않는다.

## 남은 확인·원복

실제 브리지 전환·ROS 상태 왕복·양측 시계 오차·팔 준비/수확·취소/재접속 검증은 아직 남았다.
실제 Discharge Goal은 Jetson 회신상 거절 상태이며 전체 물리 인계 검증 완료로 표현하지 않는다.

기존 운영본/별칭/설치본/저널은 그대로이므로 현재 원복은 필요 없다.
추후 격리 버전을 사용했다면 사용자가 해당 프로세스를 종료한 후 기존 laun/zen/dzen으로 되돌릴 수 있다.
저널을 과거 값으로 복원하지 않는다. 새 실행 로그는 기존처럼 /home/vic/vmany-terminal-logs에 생성된다.
격리 빌드 로그는 build.log 및 build_log/에 보존했다.


### 2026-10-27 17:50 KST 후속 — 사용자 요청 alias 전환 완료
사용자 “laun, zen, dzen으로 새 버전 실행되게 alias 변경, 기존 설정 백업, 프로세스 직접 재시작” 승인.
로봇 /home/vic/Downloads/manyfarm_terminal_20261024/aliases.bash의 세 alias만
/home/vic/vmany-runtime-staging/jetson_reply_20261027_1741/run.bash의 launch/zenoh/dummy-zenoh로 변경했다.
vinit/vstat 및 .bashrc source 경로는 유지했다. 기존 alias와 .bashrc 백업:
/home/vic/vmany-runtime-backups/jetson_alias_20261027_175002/ (manifest.json에 전후 SHA256).
문법 검사, 새 bash의 type 및 세 명령 --check 통과. 기존 실행 PID95587/95616/96083/96145 유지 확인.
프로세스 기동·종료·초기위치·이동 없음. 기존 열린 셸은 `source ~/.bashrc` 후 변경 alias를 사용한다.
원복은 사용자가 프로세스 종료 후 백업 aliases.bash를 원래 aliases.bash 경로로 복사하고 source ~/.bashrc.
저널 복원 없음. 이전 절의 “alias 미변경”은 이 변경 이전 상태다. Git staging/commit/push 없음.
