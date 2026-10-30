# 스테이션 복귀·도킹 성공본 원본 이식 — 2026-10-30

사용자 “그럼 성공본을 원래 코드에 이식해야지 그냥 두면 어케” 요청으로 성공 구현을 원래 프로젝트에 반영했다. 성공 기준은 STATION_DOCKING_SUCCESS_FREEZE_20261030.md이며 이번 통합에서 제어값/완료/충돌 조건은 바꾸지 않았다.

## 기준과 변경 범위

- PC: /home/eunbi/vmany/main/farm_project, Git HEAD e135cdef9462276cc25d9fa336f084e2dcac72e4, branch feat/harvest-handoff-real-20261018 위 기존 미커밋 유지.
- 로봇 원본: /home/vic/vmany/main/farm_project, 정식 workspace robot/ros_ws의 src/build/install 사용.
- 성공 구현: station_docking_two_wall_20261030 및 후진·원호 underlay station_work_curvature_20261029. 기존 성공 release는 수정하지 않고 원복 기준으로 보존.
- 로봇 원본은 Jetson 이전 버전이어서 성공본이 사용하는 arm_client/mission/node/Jetson 연결과 인터페이스도 함께 이식해야 했다. PC의 실행 코드는 성공본과 일치했으며 임의 다른 후보를 되살리지 않았다.
- 총48파일 선별 이식. 패키지는 harvest_robot, farm_navigation, farm_common, farm_wall_controller, farm_arc_controller, farm_nav2_controller, jetson_harvest_interfaces. 설정은 Jetson/스테이션 환경2개, Jetson harvest JSON, station_return/station_docking YAML. 원본 terminal.py 및 record_docking.bash 연결도 반영했다. 시험 파일 포함 정확한 목록·해시는 PC final_manifest.json에 보존.
- PC 실행 로직은 기존 성공본 그대로. 원본 terminal.py의 launch만 station_return.launch.py+원본 환경/도킹 설정으로 변경했고 나머지 init/zenoh/dummy-zenoh 동작은 변경하지 않았다. record_docking.bash는 원본 환경만 source한다. harvest_robot/package.xml에 farm_nav2_controller/farm_wall_controller 실행 의존성을 명시했다.
- 기존 인계 전용 코드·설정, 전진 주행 설정, sim/ 및 다른 담당자 코드를 수정하지 않았다. 프로젝트 전체 복사/삭제, 로봇 git init/clone, 별칭 변경은 하지 않았다.

## 직접 검증

1. 수정 전 관련 원본을 PC robot_original.tgz에 보존. 원본 C++ 대상 install 라이브러리가 실행 프로세스에 매핑되지 않았음을 확인 후 빌드했다. 운영 프로세스 종료/재기동 없음.
2. 원본 workspace에서7패키지 colcon 빌드2분49초 완료. 동일 workspace를 source한 상태의 underlay override 경고는 있었으나 빌드 실패 없음. 의존성 선언 후 harvest_robot 추가 빌드 성공.
3. release를 source하지 않은 원본 environment.bash 환경에서7패키지 prefix가 모두 robot/ros_ws/install 아래임을 확인. 주요 Python 소스·설치 바이트 일치 및 뒤+왼쪽 설정·기존 ControlState V3 필드 확인.
4. 원본 CTest7개(벽2/원호3/후진2) 통과. Python49개 통과. 첫 Python 실행은 비교용 harvest_handoff_jetson_real.yaml이 원본에 없어1개 실패했고, PC 기준 파일 복원 후49개 모두 통과했다.
5. 최종48개 PC/로봇 파일 SHA 일치(기록 도구의 마지막 source 제거도 별도 SHA 확인). 성공 release와 원본 실행 소스 대조: harvest57/farm_navigation27/farm_common6/wall5/arc2/nav2_controller4파일 일치. 시험·패키지 선언 등과 실행 코드를 구분했다.
6. 원본 run.bash launch --check가 원본 환경/도킹 설정을 선택함을 확인. 기존 실행 프로세스 충돌PID가 표시됐으며 새 런치를 기동하지 않았다. 원본 환경으로 재기동한 실물 주행은 아직 미검증이다.

## 확정 실행 명령

모두 로봇 터미널에서 사용한다. 기존 런치는 사용자가 먼저 종료해야 한다.

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/terminal/run.bash launch
# 별도 로봇 터미널에서 기록
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/record_docking.bash
```

기존 laun/zen/dzen 별칭은 이번에 변경하지 않았다. 원본 이식본 실행은 위 완전한 명령을 사용한다. 기존 별칭을 원본 실행으로 바꿨다고 오인하지 않는다. 초기위치는 실제 배치에 맞게 사용자만 입력하며 현재18번에14번 초기좌표를 보내지 않는다. 팔 수신 생략true는 성공 시험 조건 그대로이며 정상 운영 자동 승인으로 확대하지 않는다.

## 기록·원복

PC /home/eunbi/vmany_artifacts/station_docking_pc_20261030/source_integration/:
- robot_original.tgz: 이식 전 원본 소스·설정·도구(로봇에 백업공간 추가 없음).
- final_source_changes.tgz / final_manifest.json: 최종 선별48파일·해시.
- station_original_build.log / station_original_harvest_build.log: 빌드 근거.

원본 설치를 옛 버전으로 돌려야 하면 사용자 프로세스 종료 후 백업에서 해당 변경 파일만 복원하고 대상 패키지를 재빌드한다. 신규파일 목록은 manifest와 백업 존재 여부로 구분한다. Git HEAD로 전체를 되돌리지 않는다. 격리 성공 release의 소스/설치본은 보존되지만 일반 프로젝트 install도 underlay이므로 과거 환경 전체가 독립 snapshot인 것은 아니다. 실물 설정 백업과 underlay 의존성은 성공 고정 문서를 함께 참조한다. 저널·상태를 임의로 복원하지 않는다.

원격 Git 조회·staging/commit/push/merge 및 운영 재기동·추가 주행은 하지 않았다.


## 후속 승인: 기존 별칭 전환 및 실제 관제 연결 확인

2026-10-30 사용자 “원래 하던대로 실행할 수 있도록 별칭도 바꿔줘 … 실제 관제 웹에서 스테이션 복귀” 요청으로 적용했다. 위 ‘별칭 변경 없음’은 이식 당시 기록이며 현재 laun은 원본 실행으로 전환됐다.

- PC 원본 `robot/tools/terminal/aliases.bash` 추가, 로봇 동일 경로에 복사. 로봇 `.bashrc`가 읽는 `/home/vic/Downloads/manyfarm_terminal_20261024/aliases.bash`는 laun 한 줄만 변경했다. PC 원본과 바이트 일치 확인.
- laun → 원본 `robot/tools/terminal/run.bash launch`. zen/dzen/vinit/vstat/mf_env/dinit은 기존 값 유지. zen은 제어 관제192.168.0.20:7447, dzen은 실제 Jetson192.168.0.29:18449 연결이다. 원본 terminal.py의 과거 통신 명령으로 치환하지 않았다. 통신 release 및 수정 바이너리 의존성은 여전히 Git 밖에 남는다.
- 별칭 source 검사와 원본 launch --check 통과. 실제 기동은 없으며 기존 실행 PID가 표시됐다. 기존 터미널은 `source /home/vic/Downloads/manyfarm_terminal_20261024/aliases.bash`로 별칭만 갱신한다. 다음 사용자 재기동부터 laun이 원본 설치본을 사용한다.
- 실제 관제 `/real`의 배포 JS `index-BuYKMB9-.js`를 읽었다. ‘수확 스테이션 복귀’는 `POST /api/control/commands?environment=real`에 command.op=harvest_return을 보낸다. 요청은 직접 보내지 않았다.
- 실제 `GET /api/control?environment=real` 확인: domain77, map_id=farm_map_v1, harvest_robot_id=harvest_01, harvest_return_action=/harvest_01/return_to_station, harvest_station_id=STATION_HARVEST_01. ready.harvest_return=true, harvest_return_eligibility.allowed=true, 전체/수확복귀 차단 사유 빈 문자열, harvest_01 UNKNOWN 작업0개. 이 시점 수확 복귀 웹 작업 이력은 없었다.
- 로봇은 farm_map_v1 별칭을 내부 지도에 대응시키고 STATION_HARVEST_01의18번으로 복귀한다. 제어용 Zenoh deny에 return_to_station은 없고 Jetson 전용 브리지와 분리되어 있다. 그래프 도착 후 두 벽 도킹 완료에만 Mission.docked=true, 정상 정리 후 Action SUCCESS/docked=true가 된다.
- GitHub Frontend 기본 브랜치 control_core.py 조회 blob SHA71c2f4766e71da7deb1f8763efe42bd3a6ceb083: 복귀 결과 ID 일치, ROS4/SUCCESS, docked=true/error_code=NONE 요구. 로봇 결과 계약과 일치한다. 이 원격 백엔드 소스와 실제 서버 배포 파일의 동일성은 직접 확인하지 못했으며 실제 배포 프런트/API와 구분한다.
- 이번 검증은 별칭·파일·통신 설정·실제 웹 읽기 전용 상태 확인이다. 웹 버튼→실물 주행→웹 성공 표시는 미실행. 현재 연결된 서버는 아직 기존 성공 release 프로세스이며 원본 재기동 후 동일 ready/allowed 및 실제 결과 확인이 남는다.

별칭 변경 전 PC 백업: `/home/eunbi/vmany_artifacts/station_docking_pc_20261030/alias_control_check/aliases.before.bash`. 되돌릴 때 해당 파일을 로봇 Downloads의 aliases.bash로 복사하고 해당 터미널에서 source한다. 실행 프로세스는 이 작업으로 변경되지 않는다. 제어 코드·인계·시뮬 및 관제 코드는 수정하지 않았다. 빌드 대상 변경 없음, commit/push 없음.


## 원본 웹 복귀 성공 재확인·PC 대조·로그 정리

2026-10-30 사용자 “복귀 확인했어. PC쪽에 코드 동일한지 … 필요없는 파일들은 백업해서 지워줘” 승인으로 수행했다. 기준 HEAD/브랜치는 위와 동일하며 기존 미커밋 변경을 보존했다.

### 현재 실행과 직접 확인

- 현재 launch PID802245, harvest_node PID802292는 `/home/vic/vmany/main/farm_project/robot/ros_ws/install` 원본 설치본을 사용한다. zen PID802807/dzen PID802865 유지. 재기동·주행 명령을 보내지 않았다.
- 실제 관제 GET 결과: task_id RETURN_3e875504cd584bd6bdfa3e8875289889, 2026-10-30 20:18:43 KST, SUCCEEDED, ros_status4, result_code SUCCESS, docked=true, error_code NONE. 사용자 복귀 확인과 별개로 이번 직접 읽기 결과다. 웹→원본 로봇 복귀·도킹→웹 성공 표시까지 확인되어 앞 절의 미검증 상태를 갱신한다. 팔 상태 생략 시험 조건은 유지된다.
- 현재 launch 로그 `20261030_200943_launch_802224/console.log`의 마지막 STATION_DOCKING accepted=true. 측정 잔차 전후4.1205mm/좌우-1.2169mm/방향-0.1983도. 이는 라이다 기반 추정 잔차이며 실제 줄자 정밀도 검증을 뜻하지 않는다.
- 수확/주행/공통/벽/원호/후진/Jetson인터페이스 소스, robot/config 및 실행 도구 대조241파일 일치. 추가 bringup/vision/real_devices/farm_interfaces48파일 일치, 총289파일 SHA256 일치. 주요 harvest_robot/farm_navigation/farm_common Python 설치본도 원본 소스와 일치한다. 기존 laun 별칭 파일 두 경로 SHA도 동일하다.
- 차이4파일: 예찰용 scout_real.yaml·burger/nav2.yaml은 다른 담당자 범위로 유지. launch_corner.py는 현재 laun에서 사용하지 않는 옛 격리 시험 도구이며 로봇에 docking-config 선택 인자가 없는 이전 버전이었다. PC의 이후 버전을 과거 것으로 되돌리지 않았다. station_return/README.md는 PC의 최신 기록이다. 로봇에만 있는 이전 .bak6개와 인계 test8개도 실행 코드가 아니므로 PC 운영 코드로 가져오지 않았다. 정확한 차이와 소스 사본은 백업 comparison.json/source.tar에 보존한다. 저장소 전체가 같다는 뜻이 아니라 현재 수확 복귀·도킹 실행 코드·설정이 일치한다는 의미다.
- 따라서 이번에 실행 코드 수정·재빌드는 필요하지 않았으며 PC 완료 상태 문서를 현재 실물 결과에 맞췄다. 기존 인계·전진·시뮬·예찰 소스는 변경하지 않았다.

### 백업 후 정리

PC 백업: `/home/eunbi/vmany_artifacts/robot_backups/station_verified_20261030/`.

- `/proc` 열린 파일·cwd·cmdline으로 현재 사용 중인 로그3디렉터리를 제외했다.
- 종료된131디렉터리/172파일, 원본 총2,220,079,798바이트를 `closed_terminal_logs.tar.gz`로 PC에 직접 전송했다. 압축260,030,564바이트. 로봇에 새 백업 공간을 만들지 않았다.
- 원본 파일별 SHA256와 압축 내부 모든 일반 파일의 해시가 일치함을 확인했다. 삭제 직전 재해시·전체 파일 목록·현재 프로세스 참조를 재검사한 후 명시 목록만 삭제했다. logs_manifest.json/VERIFIED.json/deleted.json 보존.
- 디스크 가용2.5G→4.5G, 사용률92%→84%. terminal logs2.1G→33M. 현재 로그3개와 운영 PID4개 유지 확인.
- 이전 인계/도킹 성공 로그도 폐기하지 않고 이 압축에 보존했다. 과거 문서의 로봇 로그 경로가 없으면 PC 압축에서 같은 디렉터리명을 찾는다. 복구: `tar -xzf closed_terminal_logs.tar.gz -C <복원할_로그_폴더>` (PC 임의 새 폴더 우선). 실행 중 로그에 덮어쓰지 않는다.
- workspace src/build/install, 드라이버, 운영 Zenoh 바이너리·Downloads 의존성, 성공 release, 실행 중 로그, 저널은 삭제하지 않았다. VS Code 서버와 시스템 파일도 이번 정리 대상이 아니다.
- source.tar/dependencies.tar는 로봇 대조 시점 사본, comparison.json/dependencies.json은 해시 대조, web_return_results.json은 토큰을 제외한 실제 관제 결과다.

문서 갱신만 했으며 원격 조회·staging/commit/push/merge 없음. 실행 코드를 바꾸지 않았으므로 회귀시험을 새로 실행한 것으로 기록하지 않는다.
