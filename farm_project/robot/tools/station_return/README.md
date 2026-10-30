## 2026-10-30 별칭 전환

로봇 새 터미널의 `laun`은 원본 workspace 실행이다. 이미 열린 터미널에서는 먼저 다음 명령으로 별칭만 갱신한다. 기존 런치 종료·재기동은 사용자가 수행하며 중복 실행하지 않는다.

```bash
source /home/vic/Downloads/manyfarm_terminal_20261024/aliases.bash
# 기존 런치를 종료한 뒤 사용자 실행
laun
```

`zen`/`dzen`은 기존 관제/실제 Jetson 연결을 유지한다. 실행 중이면 다시 띄우지 않는다. 실제 관제 웹 `/real#control`의 ‘수확 스테이션 복귀’ 요청 연결을 읽기 전용으로 확인했다. 실제 웹 요청 주행은 별도 확인 대상이다.

## 2026-10-30 원본 통합 후 실행

성공 코드는 원래 workspace에 이식·빌드됐다. 기존 격리본은 원복/비교용으로 보존한다. 현재 원본 명령:

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/terminal/run.bash launch
# 별도 로봇 터미널
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/record_docking.bash
```

기존 런치는 사용자가 종료하고 실행한다. laun 별칭은 이번에 변경하지 않았다. [원본 통합 범위](../../../docs/changes/STATION_DOCKING_SOURCE_INTEGRATION_20261030.md) 참조.

## 2026-10-30 현재 성공 실행본

두 벽 도킹 성공 기준은 `station_docking_two_wall_20261030`이다. 이전 세 벽 설정/미확정 상태는 과거 기록이다. 현재 컴포넌트 구조와 재현·원복 근거는 [성공 확정 문서](../../../docs/changes/STATION_DOCKING_SUCCESS_FREEZE_20261030.md)를 따른다.

```bash
bash /home/vic/vmany-runtime-staging/station_docking_two_wall_20261030/run.bash
# 별도 로봇 터미널
bash /home/vic/vmany-runtime-staging/station_docking_two_wall_20261030/record.bash
```

# 실물 스테이션 복귀 비교 기록

사용자가 로봇의 별도 터미널에서 실행하는 구독 전용 도구다. 기존 forward_transition_capture_20261026/collect.py를 기반으로 한다. launch, 초기위치, 주행, 팔 명령을 보내지 않으며 종료 신호는 자신이 만든 recorder에만 보낸다.

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/collect.bash --seconds 300
```

`CAPTURE_READY`를 확인한 뒤 사용자가 복귀 명령을 보낸다. 복귀 종료 후 이 기록 터미널에서 Ctrl+C를 누르거나 300초 종료를 기다린다. 결과는 출력된 `CAPTURE_DIRECTORY`의 bag/metadata.yaml과 result.json으로 확인한다. 기록 시작 전에 laun과 실제 자세에 맞는 초기위치 설정이 필요하다. 기존 시험의14번을 사용할 경우 실제14번·12번 반대 방향에서만 dinit을 사용한다.

수집: TF/정적TF, odom, AMCL 자세, 레이저 원본·필터, 속도 명령, local costmap/footprint, 경로 및 RPP 진단 토픽, 작업/태그 상태, Action feedback/status, rosout. 종료 시 해당 태그 세션의 보정 전후 좌표·잔차·픽셀 편향 events.jsonl, detections.jsonl와 런치 로그를 읽기 복사한다. 원본 카메라 영상은 추가 구독하지 않는다.

`received_global_plan` 등은 제어기가 발행한 메시지가 있는 경우에만 실제 경로 증거다. 특히 후진 제어기는 일부 RPP 진단 출력을 하지 않으므로 publisher 존재나 CAPTURE_READY만으로 경로·lookahead 기록을 보장하지 않는다. 종료 후 bag 토픽별 메시지 수를 확인하고, 경로가 없으면 그래프 재계산을 실제 전송 경로와 구분한다. 필요한 핵심 odom/TF/AMCL/레이저/속도 구독 연결만 READY 조건으로 삼는다. 실제 벽 간격은 레이저와 센서 TF 및 차체 외곽 기준을 함께 적용해 분석한다.

로봇 여유 공간을 보존하기 위해 기본5분, 최대10분/256MiB, 여유3.1GiB 미만에서 기록만 종료한다. 로봇 주행을 중단하지 않는다. 입력 --seconds 단위는 초(30~600). CLI 종료코드0은 기록 종료 성공이며 주행 성공이 아니다. 자동 삭제 없음. 시험 후 PC로 해시 검증하여 자료를 옮긴다.

2026-10-29 검증: PC/로봇 Python·Bash 문법/help 및 Jazzy rosbag 옵션 확인. 운영 기록기는 아직 시작하지 않았으며 실제 전체 토픽 수신·bag 완성은 다음 사용자 시험에서 확인해야 한다.

## 태그 보정 모델 오프라인 비교

PC에서 자체 생성한 `wall_input.pkl`과 태그 `events.jsonl`이 있는 분석 폴더를 대상으로 한다. 외부에서 받은 pickle은 입력하지 않는다. 기존 `farm_navigation.wall_reference.fit_wall`을 재사용하며 원시/방향만/거리만/전체 보정의 같은 벽 위치·방향 일관성을 비교한다. 운영 설정을 변경하지 않는다.

```bash
cd /home/eunbi/vmany/main/farm_project
PYTHONPATH="$PWD/robot/ros_ws/src/farm_navigation${PYTHONPATH:+:$PYTHONPATH}" python3 robot/tools/station_return/review_tag_bias.py /home/eunbi/vmany_artifacts/station_return_analysis_20261029/run_0400 --start 1793214000 --end 1793214035
```

결과의 벽 위치 직선 적합 잔차는 상대 일관성이며 절대 위치 정확도/실제 주행 개선율이 아니다. 촬영시각과 최근접 scan의 차이 및 제외 표본을 함께 남긴다.

## 2026-10-29 원호 복귀 설치본 시험 순서

배포 위치: `/home/vic/vmany-runtime-staging/station_corner_20261029_045549`.
기존 `laun`은 원복용 이전 실행을 유지한다. **이번 시험은 아래 새 명령을 사용한다.**
기존 실행 release 위에 새 harvest_robot/farm_arc_controller만 올린다. 인계 기본속도·시뮬은 유지하고 복귀 원호만5cm/s다. 팔 상태 수신 생략은 기존 시험 프로필의 true를 유지한다.

1. 사용자가 기존 **로봇 런치 터미널에서 Ctrl+C**를 누르고 종료 완료를 확인한다. 브리지/미니관제는 기존 실행을 유지해도 된다. 이 도구가 프로세스를 임의로 종료하지 않는다.
2. 로봇을 실제 그래프14번 위치, **12번을 등지는 방향(yaw0도)**에 배치한다. 실제 팔 접힘·정지와 이동 공간을 확인한다. 초기위치 발행은 로봇을 물리적으로 옮기지 않는다.
3. **로봇 터미널 A**에서 새 런치 실행:

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/launch_corner.bash \
  /home/vic/vmany-runtime-staging/station_corner_20261029_045549
```

PC에서 여는 터미널이면 먼저 `ssh -t vic@192.168.0.12`로 접속한다. 이후의 경로는 모두 로봇 기준이다.
런치는 기존 카메라·태그 구성을 포함하므로 별도 카메라를 실행하지 않는다.
새 런치의 기존 중복 검사에 걸리면 이전 런치 종료 상태를 확인한다. `laun`을 추가로 실행하지 않는다.

4. **로봇 터미널 B**에서 서버 준비 후 초기위치 설정:

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/terminal/dinit.bash
```

실제14번·yaw0도·IDLE·정지일 때만 실행한다. 출력 기준은 x=3.576m/y=-0.035m/yaw0도다. 정지/IDLE 검사 실패를 우회하지 않는다. 14번에서 `vinit`을 실행하지 않는다.

5. 같은 **로봇 터미널 B**에서 기록을 시작한다:

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/collect.bash --seconds 180
```

`CAPTURE_DIRECTORY=...`와 **`CAPTURE_READY`**가 나올 때까지 기다린다. 새 원호 서버의 raw_nav, 충돌 예측, costmap/footprint, FollowPath feedback/status도 포함한다. 시작 여유3.25GiB, 실행 중3.1GiB/256MiB 한도는 기존대로다. 기록기 종료는 차체 정지가 아니다.

6. **PC 미니관제** `http://127.0.0.1:8091`에서 `로봇 시험 연결` → 복귀 서버 발견 확인 → 차체 후진 확인란 → `스테이션 복귀`를 **한 번** 누른다. 목표18번, station_id=STATION_HARVEST_01, wire map=farm_map_v1이다. 이번에 PC 앱 변경은 없어 이미 실행 중이면 재시작할 필요가 없다. 팔 prepare/수확/배출 명령은 필요 없다. 미니관제는 SSH로 로봇 시험 클라이언트를 연결하므로 이 복귀 시험만을 위해 zen/dzen을 새로 켤 필요는 없다. 기존 브리지는 중복 실행하지 않는다.
7. 수락/진행과 최종 결과를 구분한다. **SUCCESS, docked=false**는18번 도착 성공이며 최종 도킹 성공이 아니다. 코너 자체는 PC 기준 약6.2초지만 진입/정지/마지막 직선은 별도다. 이번 실물 시험에서는 직선 벽 간격, 코너 이격/흔들림, 원호 시작·종료 자세를 관찰한다.
8. 최종 결과와 실제 정지를 확인한 뒤5초 정도 더 기록하고 **기록 터미널 B에서 Ctrl+C**한다. `CAPTURE_FINISHED` 경로와 bag/metadata.yaml 생성 여부를 확인한다. 필요 시 아래 명령에서 실제 출력된 기록 경로를 지정한다.

```bash
source /home/vic/vmany/main/farm_project/robot/tools/terminal/environment.bash
ros2 bag info /home/vic/vmany/main/farm_project/runs/station_return_capture/실제_기록폴더/bag
```

반복 비교는18번 도착 이후 새 기록을 먼저 시작하고, 미니관제 `시험 위치로 이동`으로14번 이동 SUCCESS·정지를 확인한 뒤 `스테이션 복귀`를 누른다. 이 경우 전진/후진이 같은 기록에 남는다. 주행으로14번에 도착했을 때 dinit을 반복 발행하지 않는다. 시간이 부족하면 새 수집에 `--seconds 300`을 사용한다.

문제 발생 시 미니관제 `내 복귀 요청 취소`를 사용하고 최종 취소/실제 정지를 확인한다. 팔 stop 버튼은 차체 복귀 취소 버튼이 아니다. 오류가 남으면 강제IDLE/저널 초기화 없이 기록을 먼저 확인한다.

되돌리기는 새 런치를 사용자가 종료한 뒤 기존 `laun`을 실행한다. 기존 source/install/별칭은 보존되어 있다. 두 런치를 동시에 실행하지 않는다.


### 2026-10-29 05:16 연결부 수정 배포

실측 위치와 그래프 사이 연결부의 가짜 코너 오류를 수정했다. 기존 런치를 사용자가 Ctrl+C로 종료한 후 다음 명령을 사용한다. 기존 laun 별칭은 변경하지 않았다.

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/launch_corner.bash /home/vic/vmany-runtime-staging/station_corner_20261029_0516
```

실제로14번/12번 반대 방향에 정지한 경우만 별도 로봇 터미널에서 dinit.bash를 실행한다. 그 뒤 collect.bash --seconds 180, CAPTURE_READY 확인, 미니관제 스테이션 복귀 순서다. 재기동과 주행은 사용자 담당이다. 상세 명령은 앞 절과 같고 overlay 인자만 위 경로로 바뀐다.


### 2026-10-29 접근·방향 분리 최신 배포 (0555)

아래 경로가0516을 대체하는 최신 시험본이다. 원호 전 위치 완료와 방향 정렬을 분리하며 인계/기본 laun은 변경하지 않는다. 실물 주행은 사용자 확인 대상이다.

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/launch_corner.bash /home/vic/vmany-runtime-staging/station_approach_20261029_0555
```

실제로14번에서12번 반대방향을 바라보고 정지한 경우에만 별도 로봇 터미널에서:

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/terminal/dinit.bash
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/collect.bash --seconds 180
```

CAPTURE_READY 후 미니관제 스테이션 복귀 요청. 이전 실패 위치가 코너라면 먼저 실제14번으로 재배치해야 한다. 팔 상태 생략은 유지한다. 기록3개는 PC run_0400/run_0508/run_0519에 보존되어 있다.

## 2026-10-29 동일 회차 전진/후진 비교 기록 점검

주행 코드/설정과 기록기 코드는 변경하지 않았다. PC/로봇 collect.py SHA256=4b68c504009406434176b263f65edaf50eb04307c6bcb9d3b9542ba86df3316c, collect.bash=e72432837b968ad14885ca5c0746f32472da1adbf238e68491f0d2319cb2add0 일치. 직전06:00 bag에서odom3672/TF6734/scan·scan_filtered각1226/AMCL89/태그보정9개/정적TF1개 수신을 확인했다. 이번 새 실행의 수신 완료를 뜻하지 않는다.

필수 비교자료는 기존 기록기로 수집: 지도/그래프·실행파라미터 사본, TF/odom/AMCL, 라이다 원본/필터, 출력 단계별속도, 태그control/correction/events 및 종료시detections/events/camera_info/settings 파일사본. 태그 시각·화면u·보정전후는JSONL에서 확인한다. 후진의실제FollowPath입력Path와내부carrot은제어기가발행하지않으므로토픽을목록에넣어도기록되지않는다. 원호points_odom은런치로그에남지만전부의전송Path를대체하지않는다. trial/navigate_to_pose와Spin Action자체feedback/status는기존목록에없으며전진요청/최종결과는PC미니관제arm-audit.jsonl와NAVIGATION_TRIAL런치로그를함께사용한다. 이번목적의추정/벽거리비교는가능하지만매주기컨트롤러완전재연은아니다.

점검시수확/컨트롤러프로세스미확인. 기록기를실행하지않았다. 로봇여유3.083GiB라기존시작3.25GiB미달이었다. 이전공간확보승인범위로종료태그5세션및06:00capture총199파일을PC사본과전수SHA/크기/목록검증·열린FD없음확인후로봇사본만정리,3.432GiB확보. 태그원본은 /home/eunbi/vmany_artifacts/robot_backups/recording_compare_20261029/closed_tag_sessions.tar, 목록tag_manifest.json/move_manifest.json.06:00원본은station_return_analysis_20261029/run_0600/20261029_060011_557687. 자동삭제규칙/수집공간기준변경없음.

### 준비

정상위치추정이살아있는실제18번IDLE정지상태라면초기화없이본시험부터진행한다. 새로기동할경우최신0555런치사용. 기존스테이션초기화는(.104,-1.105,87.79도)로18번목표(.046,-1.12,90도)와다르므로'18번도착했으니vinit'으로사용하지않는다. 물리기준을확인하지못한18번위치에서임의초기화를하지않는다.

기존14번초기화로준비하는방법(새초기화코드/설정추가없음): 실제14번·12번등짐방향에배치→아래런치→별도터미널dinit→미니관제스테이션복귀→SUCCESS/docked=false및실제정지확인. 여기까지준비주행이며아래18→14→18비교기록과구분한다. 초기화기준스테이션에정확히재배치할수있다면기존가드있는run.bash init도사용가능하지만18번목표와동일좌표라고가정하지않는다.

로봇 터미널 A (PC 터미널에서라면 먼저 ssh -t vic@192.168.0.12):

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/launch_corner.bash /home/vic/vmany-runtime-staging/station_approach_20261029_0555
```

별도 로봇 터미널 B, 위14번실제배치가맞을때만:

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/terminal/dinit.bash
```

### 본시험: 한기록에18→14→18

18번에서실제정지/IDLE,미니관제로봇시험연결준비. 터미널B:

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/collect.bash --seconds 300
```

CAPTURE_DIRECTORY와CAPTURE_READY확인→18번정지10초기록→PC http://127.0.0.1:8091 의'팔 없이 시험 위치로 이동'에서확인란/목표14확인후'시험 위치로 이동'1회→SUCCESS/실제정지후10초기록→차체후진확인란체크후'스테이션 복귀'1회→SUCCESS/docked=false/실제정지후10초기록→기록터미널에서Ctrl+C→CAPTURE_FINISHED확인. 전진/후진사이에dinit/vinit/수동재배치/런치재기동/태그설정변경없음. 기록은300초또는256MiB/여유3.1GiB에서먼저끝날수있다. 복귀누르기전기록기가아직실행중인지확인한다. 기록종료는차체정지가아니다. 전진실패시후진을연속실행하지말고결과/기록을보존한다. 이동취소는'내 이동 요청 취소',복귀취소는'내 복귀 요청 취소'.

종료확인,같은로봇터미널:

```bash
source /home/vic/vmany/main/farm_project/robot/tools/terminal/environment.bash
capture_dir=$(find /home/vic/vmany/main/farm_project/runs/station_return_capture -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)
printf '%s\n' "$capture_dir"
cat "$capture_dir/result.json"
ros2 bag info "$capture_dir/bag"
```

표시된경로가이번CAPTURE_DIRECTORY와같은지확인한다. ready=true,metadata_saved=true및핵심토픽메시지수가양수인지확인한다. result의exit_code는기록기결과이며주행성공아님. 분석시전진/후진각각의태그세션·보정횟수와최종결과를분리하고,경로토픽0개를주행실패나경로가없었다는뜻으로해석하지않는다.

### 2026-10-29 카메라 미기동 비교 준비 — PC 변경, 로봇 미적용

`launch_corner.bash <overlay> --without-camera`는 해당 시험 실행에서만
`tag_camera:=false tag_correction:=false`를 전달한다. 기본 실행은 그대로다.
촬영 세션과 보정 노드를 생성하지 않으며, 기존 launch의 선택 계약에 따라
태그 scan-sync 연결도 해제된다. 따라서 촬영 부하만 분리한 실험이 아니라
태그 파이프라인 전체 OFF 비교다. 기존 인계 운영 launch를 변경하지 않는다.
이 시험 실행에서 인계/수확 태그 보정은 사용할 수 없다.

수집기는 `timing.jsonl`에 odom과 각 TF 연결의 원본 stamp, ROS 수신 시각,
monotonic 수신 시각, 원본/수신 간격(ms)을 기록한다. 5초마다 관련 프로세스
목록도 남긴다. age는 원본 시각부터 수신까지의 차이이며 순수 네트워크 지연이
아니다. AMCL의 미래 TF stamp는 음수 age가 될 수 있으므로 odom 및
map→odom/odom→base를 분리해 분석한다. 누락/중복 stamp도 원문 그대로 보존한다.
과거 bag은 bag 수신 시각-stamp로 비교할 수 있지만 새 sidecar 콜백 시각과
동일 계측은 아니다. 동일 계측 비교에는 같은 기록기를 양 조건에서 사용한다.

PC Domain231 합성 20Hz TF/odom 각53표본 수신·정상 종료 확인.
실물 실행·카메라 프로세스 부재·실물 지연 개선은 아직 검증하지 않았다.
원호 접근 변경의 공통 코드 승인은 별도 대기 중이므로 아직 통합 시험을 시작하지 않는다.

### 2026-10-29 승인 후 로봇 적용 완료 — 사용자 재기동

기존 런치는 사용자가 종료한다. 새 로봇 터미널:
```bash
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/launch_corner.bash /home/vic/vmany-runtime-staging/station_no_camera_20261029 --without-camera
```
로봇이 실제14번, 12번 반대방향이며 IDLE·정지인 경우에만 다른 로봇 터미널:
```bash
bash /home/vic/vmany/main/farm_project/robot/tools/terminal/dinit.bash
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/collect.bash --seconds 300
```
18번에 있을 때 dinit을 사용하지 않는다. 기존스테이션 보정점과 graph18이 다르므로
18번이라는 이유만으로 vinit을 보내지 않는다.
CAPTURE_READY 이후 정지상태10초 기록 → 미니관제18번복귀1회 → 최종결과·정지후10초
기록 → 기록기만Ctrl+C. timing.jsonl 및 process목록/기존bag을 함께 분석한다.
이번 카메라OFF 실행에서는 인계/수확 태그보정 시험을 하지 않는다.
속도·충돌·최종 허용치와 인계/sim 설정은 불변. 실물 주행 성공은 아직 미검증.


### 2026-10-29 전진 ON → 후진 OFF 단계 비교 준비

사용자 “첫번째부터 테스트하고 두번째도 테스트” 승인. 기준 HEAD
`e135cdef9462276cc25d9fa336f084e2dcac72e4`, 기존 미커밋 변경 보존.
1차는 기존 `station_approach_20261029_0555` 주행 그대로, 전진은 카메라/태그 ON,
14번 도착·실제 정지 후 카메라 세션 관리자에 SIGINT, 자식/adapter 종료 뒤 후진한다.
`--without-camera`는 전진까지 꺼지므로 이번 비교에서 사용하지 않는다.
AMCL/scan-sync 구현은 재기동하지 않고 그대로 유지하되 새로운 태그 보정 입력이 없다.
이미 적용된 전진 태그의 위치 추정 효과까지 지우는 시험은 아니다.

추가 파일 `robot/tools/station_return/camera_phase.py`는 기존 process_agent의 조회 기능을
재사용한다. 기본 조회, --stop은 harvest_01 세션 관리자 1개에만 SIGINT를 보내며,
기존 시작 시각으로 자식 잔존과 5초간 세션 부재를 확인한다. 직접 강제 종료하지 않는다.
기존 관리자 내부 종료 정책은 유지된다. 주행/인계/시뮬 소스·설정 변경 없음.
PC 문법/help 및 합성 세션 실제 SIGINT 종료·5초 부재 확인 통과. 로봇 도구 복사/help/해시
일치 확인. 로봇 운영 종료·재기동·주행 미수행, 실물 카메라 종료는 사용자 시험 대기.

현재 조회 당시 0555 런치 실행 중이나 카메라는 capture exit=1로 이미 종료되어 있었다.
전진 ON 비교에는 사용자 런치 재시작과 실제 자세에 맞는 초기위치 확인이 필요하다.
1차 결과를 확인한 뒤 2차 HarvestWork 계산 비교를 준비한다. 2차 코드 변경/배포는 아직 없다.

공간: 지난16:11 capture30파일277920373바이트는 PC run_1611 사본과 전수SHA/크기 및
열린FD 없음 확인 후 로봇 사본 제거. 종료된10/28 12:52 런치2파일173496000바이트는
`/home/eunbi/vmany_artifacts/robot_backups/camera_phase_20261029/`에 복사·검증 후 로봇만 제거.
당시 여유3725045760바이트(약3.47GiB). 실행 중 로그/성공기준15:15 로그는 보존.
전진·후진은 각각180초 기록으로 나누고 사이에 위치 초기화/물리 재배치하지 않는다.
되돌리기: 사용자 런치 재시작으로 기존 카메라 ON 복원. 도구는 자동실행되지 않는다.
commit/push/스테이징 없음.


### 2026-10-29 카메라 단계 도구 배포 누락 수정
사용자 실행 시 process_agent.py 누락으로 FileNotFoundError 발생. 이전 로봇 검증은
--help만 실행하여 실제 import 누락을 발견하지 못했다. 기존 PC 모듈을 수정 없이
로봇 robot/tools/trial_console/process_agent.py에 추가 배포했다(기존 경로 없음 확인).
SHA256 c1b69ba9f3787ea3f39d831e30e1e8e69383732d5da2eadfb390a18592862d68 일치.
로봇에서 camera_phase.py 기본 조회 직접 실행, exit0/CAMERA_ON 및 카메라·검출·보정
자식 확인. --stop 미실행, 종료·재기동·주행 명령 없음. 주행/인계/sim 변경 없음.
기준 HEAD e135cdef9462276cc25d9fa336f084e2dcac72e4, 기존 변경 보존, commit/push 없음.
되돌리기는 새 배포 모듈만 제거하면 되지만 camera_phase 의존성이므로 함께 관리한다.
실물 종료 기능은 여전히 사용자 시험 대기다.


### 2026-10-29 2차 시험 overlay

사용자 기존런치 종료 후 다음 명령. 전진 카메라ON은 유지한다.
```bash
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/launch_corner.bash /home/vic/vmany-runtime-staging/station_work_curvature_20261029
```
실제 기존스테이션초기화기준점에 정확히 재배치·IDLE정지한 경우에만:
```bash
bash /home/vic/vmany/main/farm_project/robot/tools/terminal/run.bash init
```
그래프18번목표와 위초기화기준점은 다르다. 전진기록→14이동성공정지→기록Ctrl+C:
```bash
python3 /home/vic/vmany/main/farm_project/robot/tools/station_return/camera_phase.py
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/collect.bash --seconds 180
```
14번에서 사용자가 카메라종료 후 새후진기록:
```bash
python3 /home/vic/vmany/main/farm_project/robot/tools/station_return/camera_phase.py --stop
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/collect.bash --seconds 180
```
CAMERA_OFF_CONFIRMED와CAPTURE_READY를 각각확인한후미니관제18복귀.
결과·실제정지후10초기록후Ctrl+C. 전후진사이에초기화/재배치/런치재기동하지않는다.
전진태그세션거절결함은미수정이므로CAMERA_ON을보정적용성공으로해석하지않는다.
기존0555가원복본. 이번변경은후진접근계산만이며실기검증전이다.


### 2026-10-29 도킹 완료 자세 정지 측정 준비

사용자 “준비해줘” 요청으로 도킹 기준 측정용 `robot/tools/station_return/dock_reference.bash` 추가 및 로봇 동일 경로 설치.
기준 HEAD e135cdef9462276cc25d9fa336f084e2dcac72e4, feat/harvest-handoff-real-20261018의 기존 미커밋 변경 보존.
기존 주행 기록기는 로봇 여유 약3.1GiB에서 시작 여유3.25GiB 조건에 걸리므로, 새 도구는 영상/지도 없이 30초 라이다 원본·필터/TF/static/odom/AMCL/속도만 기록한다.
사용자가 원하는 최종 주차 자세에 정지한 뒤 별도 로봇 터미널에서 실행한다:
```bash
bash /home/vic/vmany/main/farm_project/robot/tools/station_return/dock_reference.bash
```
저장: runs/station_docking_reference/<시각>/bag, recorder.log, result.json. 종료 후 핵심 토픽 실제 메시지 수와 metadata 확인, DOCK_REFERENCE_SAVED 출력. 이 표시는 정지/도킹 성공 판정이 아니다.
이번 측정에는 주행 명령·vinit/dinit 불필요. 현재 라이다/수확 프로세스 실행 확인했지만 실제 IDLE/정지는 사용자 확인 필요.
측정 동안 실제 도킹 자세 유지. 차체 뒤끝-뒤벽, 좌우 외곽-각 벽 간격(cm)을 함께 기록하고 가능하면 측면 앞/뒤 두 지점 간격과 측정 지점도 남긴다.
기준 자세의 실제 벽/목표 거리/방향/허용치는 아직 미확정. 이전 도착 기록을 목표값으로 사용하지 않는다.
PC/로봇 Bash 문법, --help, 로봇 timeout/PyYAML 및 배포 SHA256 확인. 실물 기록은 사용자 실행 대기.
스크립트 SHA256: 5c5678a955501c49d1ff19b57e196c6961137a92d15a984d479710f3f9f8c659.
주행·인계·시뮬·공통 코드/설정 미변경. 프로세스 기동/종료/재기동, 명령 발행, 빌드, commit/push 없음.
원복: 새 기록 스크립트만 제거. 이미 수집한 기록은 보존. 도킹 구현 및 docked=true 연결은 후속 작업.


### 2026-10-29 도킹 기록기 터미널 정지 수정
사용자 실행 후 30초 종료 불가 보고. 18:42:50 기록 PID458353은 T(stopped), timeout은 별도 PGID458352, 운영 터미널 전경 스크립트 PGID458328. recorder.log 경고 한 줄, bag 디렉터리 없음: 이번 측정 데이터 미수집.
timeout 별도 그룹에서 rosbag 키보드 입력의 job-control 정지가 원인에 부합. 도구에 timeout --foreground 및 rosbag --disable-keyboard-controls 적용·로봇 반영. 기본 30초·기록 토픽 유지.
PC/로봇 Bash 문법과 옵션 지원 확인. 새 SHA256 ade23a63a93ed7cc730c6b087a6598a80188f237069be4d29bc8cf64ac03fffd. 실제 터미널 재실행 종료는 사용자 확인 대기. 이전 문법 검증을 자동 종료 실기 검증으로 보지 않는다.
기존 기록기 종료는 사용자에게 해당 PID TERM 후 CONT 명령 안내. assistant 프로세스 종료/기동 없음. 운영·인계·sim 미변경, commit/push 없음.


### 2026-10-30 도킹 PC 구현 상태

기존 벽 컴포넌트 확장과 실물 도킹 연결은 PC에서 구현·검증했다. 로봇 배포/재기동은 하지 않았다.
`station_docking.yaml`에는 측정 기준만 확정돼 있고 최종 앞뒤/좌우/방향 허용치는 null이다.
기존 실행 명령은 그대로 도킹 미선택이며, 허용치 확정 전 실물 도킹 명령을 안내하지 않는다.
선택형 구성·검증·원복은 `docs/changes/STATION_DOCKING_PC_20261030.md` 참조.
사용자 시험 대기다.
- PC 도구 수정: launch_corner.py에 명시 --docking-config 선택 인자만 추가(미지정 동작 불변), record_docking.bash 추가. 로봇에는 기존 도구 덮어쓰기 대신 새 release/launch.py와 record.bash로 배포했다. 기록 스크립트 SHA d25168ed8ac311072e6804db177ae8e2a8a488d15d8e9b2021eaadb8e4020768.
- PC 백업/배포 산출물: /home/eunbi/vmany_artifacts/station_docking_pc_20261030/robot_deploy/{baseline.tgz,release.tgz,manifest.json,robot_build.log}. 기존소스 백업은 로봇에 추가하지 않았다.
- 현재 별도 도킹 전용 요청은 없다. 복귀 Action은 기존18번 경로·정지 후 도킹, 성공/정리 후 docked=true. 이전 답변의 ‘도킹만 먼저’는 현재 기능으로 별도 제공되지 않음을 정정한다.

사용자 시험(아래 명령은 모두 로봇 터미널):
```bash
# 터미널 A: 기존 런치를 실행했다면 사용자가 먼저 종료한 뒤
bash /home/vic/vmany-runtime-staging/station_docking_20261030/run.bash
# 터미널 B: 실제14번·12번 반대 방향에 재배치했고 IDLE/정지인 경우에만
bash /home/vic/vmany/main/farm_project/robot/tools/terminal/dinit.bash
# 같은 B: 기록 시작, 필요한 scan/odom/tf 구독 표시 확인
bash /home/vic/vmany-runtime-staging/station_docking_20261030/record.bash
```
이후 기존 미니관제 스테이션 복귀 버튼을 한 번 누른다. 카메라는 기본 ON이며 이번에 임의로 끄지 않는다. 팔 상태 수신 생략은 유지하므로 실제 팔이 접혀 정지한 상태는 사용자 확인이 필요하다. 초기위치 입력은 실제 배치와 일치할 때만 수행하며 그래프18에 스테이션 초기화 좌표를 보내지 않는다. 완료/실패 및 실제 정지 후10초까지 기록, Ctrl+C 또는180초 자동 종료. 도킹 시 오차/성공·실제 뒤/좌/우 간격을 함께 확인한다. 별도 모션 명령을 추가하지 않는다.

원복: 사용자가 새 런치를 종료한 뒤 기존 launch_corner.bash station_work_curvature_20261029 명령을 사용한다. 기존 실행본 수정/복원 불필요. 실물 도킹·기록 수집은 미검증, commit/push/merge/스테이징 없음.


### 2026-10-30 두 벽 수정본 로봇 격리 배포 완료
- 사용자 “그럼 준비해줘” 승인으로 새 `/home/vic/vmany-runtime-staging/station_docking_two_wall_20261030` 준비. 기존 세 벽 release는 보존했다. 기준 HEAD e135cdef9462276cc25d9fa336f084e2dcac72e4/기존 미커밋 유지.
- 기존 release의 src/config/사용자 실행도구를 새 경로에 복제하고, wall_observation.py·station_docking.yaml·station_docking.py(주석) 세 파일만 교체했다. 원본 대비 그 외 변경0, PC/로봇3파일 SHA 일치, manifest155파일 검증. 기존 프로젝트 소스/설치본·인계·전진·sim 미변경.
- ARM4패키지 빌드44.0초 성공. CTest2 통과. 실제 설치 모듈 경로/소스 바이트 일치, 두 벽 선택 및 세 벽 기본값 회귀, 위치·방향 기하3사례 확인. 허용치5mm/5mm/1도 유지. run.bash --check는 새 설정 경로를 선택, 중복 실행PID 없음. 실제 기동/재기동/초기위치/주행 명령은 보내지 않았다.
- 기존 팔 수신 생략 프로필·카메라 기본ON·후진/원호 underlay 유지. 로봇 여유약2.6GB, 파일 삭제없음. 기록도구는 기존 도킹용180초 record.bash를 그대로 새 release에 보존.
- PC 산출물: /home/eunbi/vmany_artifacts/station_docking_pc_20261030/two_wall_deploy/{station_two_wall_deploy.tgz,manifest.json,build.log}. 실물 두 벽 도킹 성공은 아직 미검증.

사용자 재시험 명령(로봇 터미널):
```bash
# A: 기존 런치가 있다면 사용자가 종료 후 새 런치
bash /home/vic/vmany-runtime-staging/station_docking_two_wall_20261030/run.bash
# B: 실제14번·12번 반대 방향에 배치했고 IDLE/정지일 때만 초기위치
bash /home/vic/vmany/main/farm_project/robot/tools/terminal/dinit.bash
# B: 영상 없는180초 기록. 필요한 scan/odom/tf 구독 표시 후 미니관제 복귀1회
bash /home/vic/vmany-runtime-staging/station_docking_two_wall_20261030/record.bash
```
현재18번에 그대로 있다면 dinit을 보내지 않는다. 위14번부터 시험하려면 실제 재배치가 먼저다. 팔이 실제 접혀 정지한 상태 확인. 완료/실패 후 실제정지10초 더 기록하고 Ctrl+C 또는180초 자동종료. 18번 도착후 두 벽 도킹의 동작/최종결과 및 벽간격 확인. 원복은 사용자새런치종료 후 이전 run.bash 선택으로 가능하며 기존실행본 복원 불필요. commit/push/merge 없음.
