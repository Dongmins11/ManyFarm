# 수확로봇 AprilTag 위치 보정 — 구현·실물 검증 및 인계 기준

<!-- MOTOR_INSTALLED_20261010_1751 -->
> **모터 영구 설정 설치 확인 — 2026-10-10 17:51 KST**
> 사용자 로봇 출력: udev 규칙 검사 Success 1 / Fail 0,
> serial=BG02QM7Y, latency_timer=1, rule_installed=True,
> CHECK_OK 및 INSTALL_OK 확인.
> 아래의 설치 미실행 표기는 설치 전 기록이며 이 확인으로 갱신한다.
> 재부팅·USB 재연결 후 지속성 확인은 아직 미실행이다.


> **고정 상태: AprilTag 위치 보정 연결 및 실제 AMCL 적용 검증 완료. 물리적 차체 옆면–벽 20cm 유지 성능은 후속 개선.**
>
> 2026-10-10 은비 확인: 출발 간격은 약 20cm로 비슷하게 맞췄으며, 처음에는 괜찮다가 주행하면서 벽에서 조금씩 멀어지는 현상이 남았다. 현재 보정 기능과 한계를 기록하고 추가 반복 주행 없이 다음 작업으로 넘어가기로 했다.
>
> 이 문서는 당시 구현·시험의 기준 기록이다. 보정의 일반화 성능, 전체 시스템 통합, 수확 동작 또는 20cm 유지 완료를 선언하지 않는다.

## 1. 목표와 완료 범위

수확 좌표를 받아 FollowPath로 이동하면서 AprilTag로 위치추정을 보조하고, 차체 옆면–화단 벽 간격 약 20cm를 유지하는 것이 최종 목표다. 좌표 도착 때마다 큰 회전으로 정렬하는 동작은 지양한다. 20cm는 로봇 중심 또는 base 기준점의 거리가 아니다.

| 항목 | 현재 상태 | 근거·한계 |
| --- | --- | --- |
| 태그 보정 전달·수신 | 이번 ON 실물 주행에서 정상 수행 | 요청 10 / queued 10 / applied 10. 수신 dropped·rejected 없음 |
| 실제 AMCL 적용 | 확인 | 10개 요청과 적용의 sequence·token·source_stamp·전달 pose 일치. 라이다 시각으로 이송된 aligned_pose는 전달 pose와 구분 |
| 화면 위치 편향 보상 | 시험 ON에서 관측 오차 감소 확인 | 이전 녹화로 만든 모델을 새 주행에 그대로 적용. 기준은 라이다 벽 평면이며 독립 실측 절대 정답 아님 |
| 목표 도착 | 14번 SUCCESS | 도착 판정은 추정 pose 기준. 실제 수확은 수행하지 않은 ARRIVAL_ONLY_NO_HARVEST |
| 실제 20cm 유지 | 미완료·후속 개선 | 사용자 관찰상 주행하며 벽에서 점차 멀어짐 |
| 카메라 정상 종료 | 미해결 | detector/rectify -11, capture 실패. 주행 중 보정 적용 실패와 별개 |

이번 문서 작성 과정에서 수행한 것은 코드·설정 조회와 녹화 로그의 오프라인 재분석이다. 새 로봇 주행은 실행하지 않았다.

## 2. 환경과 버전 기준

| 구분 | 기준 |
| --- | --- |
| PC 프로젝트 | /home/eunbi/vmany/main/farm_project |
| 로봇 | vic@192.168.0.12 |
| 로봇 프로젝트 | /home/vic/vmany/main/farm_project |
| 기존 드라이버 워크스페이스 | /home/vic/vicpinky_ws |
| ROS | ROS 2 Jazzy |
| 주행 DDS 환경 | ROS_DOMAIN_ID=156, ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET, RMW_IMPLEMENTATION=rmw_fastrtps_cpp, ROS_LOCALHOST_ONLY 해제 |
| 카메라 환경 | capture_session에서 별도로 관리 |
| 작업 브랜치 | feat/apriltag-localization |
| 원격 HEAD | 2026-10-10 직접 조회: 7689f3648007c643f01a2dcaee160ae6fcbefcdd |
| 로컬 상태 | 사용자가 제공한 PC status/head 및 17:45:03 작업본 묶음 확인: PC HEAD는 위 원격과 동일, 최신 작업은 미커밋. 로봇 HEAD는 미확인 |
| 실제 시험 코드 기준 | ON 로그 inputs/ 스냅샷 + 패치 묶음 + manifest 해시. 원격 HEAD만으로 최신 시험 구현을 재현할 수 있다고 보지 않음 |
| 지도 | map_id=many_farm_v1, robot/config/maps/many_farm |

과거 /home/vic/apriltag_ws 및 /home/vic/manyfarm_experiments는 사용자 인계 기준 삭제된 상태이며 현재 실행은 Git 이식본을 사용한다. /dev/motor는 /dev/ttyUSB0에 연결된다. 시험 FTDI latency_timer는 1이며 재부팅 후 16으로 돌아간 사례가 있다. 모터 전원 OFF로 odom TF가 없던 문제는 해결된 이력이다.

### 변경·운영 원칙

- 예찰 코드는 수정하지 않는다. 참고 기준은 scout_new다.
- 다른 작업자의 변경을 보존한다. 기존 파일을 비교하지 않고 덮어쓰지 않는다.
- 태그 누락·관측 거절·보상 범위 밖은 해당 보정만 생략하며 새 주행 중단 조건으로 연결하지 않는다.
- 충돌 검사·footprint를 임의로 줄이거나 비활성화하지 않는다.
- 백업은 PC /home/eunbi/vmany_backups 아래에만 둔다. 저장소 내부·로봇에 백업을 쌓지 않는다.
- commit/push는 은비가 VS Code에서 수행한다. 이번 문서 작성으로 저장소 변경·배포·commit/push는 발생하지 않았다.
- 실제 실행, 오프라인 검사, 과거 기록, 사용자 관찰을 구분한다.

## 3. 현재 주행 구조

공통 RouteGraph의 선분 투영·다익스트라로 경로를 생성하고 FollowPath로 이동한다. **현재 실물 설정은 Route Server를 사용하지 않는다.** 과거 ComputeRoute 구조와 구분한다.

| 단계 | 동작 | 제어기 |
| --- | --- | --- |
| SECTION_APPROACH | 10번 부근에서 11번으로 진입, 도착·정지 확인 | HarvestApproach |
| WINDOW_MOVE | 11번 이후 작업 좌표까지 경로를 생성해 FollowPath | HarvestWork |
| SECTION_EXIT | 이탈 | RPP |

시험 section은 SEC_01, 11번은 (1.188, -1.02), 14번은 (1.188, -4.02), 목표 yaw는 -π/2다. 진입·작업 끝점의 큰 회전은 이전보다 줄어든 상태이나 모든 조건의 정렬 성능을 보장하지 않는다.

harvest.launch.py 하나가 장치·Nav2·카메라·태그 어댑터를 실행한다. 별도 bringup/navigation을 중복 실행하지 않는다.

## 4. 태그 보정 구현

처리 순서:

1. 카메라 촬영 시각의 태그 관측으로 map 기준 base pose를 계산한다.
2. 시험 ON이면 화면 가로 위치 기반 벽 법선 위치·yaw 편향을 보상한다.
3. 기존 odom 시각 이송과 잔차 제한을 적용한다.
4. 작업 token·sequence·source_stamp·pose 시각 정보를 scan_sync 수신부에 전달한다.
5. farm_tag_amcl이 라이다 시각에 맞춰 적용하고 실제 적용 이벤트를 기록한다.

AMCL이 map→odom TF를 담당한다. 태그 보정은 모터 명령을 직접 발행하는 기능이 아니다.

기존 /initialpose 방식은 AMCL 처리 시점 최신 odom TF 요구와 관련한 시간 경고가 반복됐다. 현재는 scan_sync_v1을 사용하며 이번 기록에서 보정 요청 10개가 모두 실제 적용됐다. 수동 2D Pose Estimate 초기화 경고와 주행 중 태그 보정 경고는 분리한다.

### 관련 경로

모든 상대 경로는 farm_project/ 기준이다.

| 경로 | 역할 |
| --- | --- |
| robot/ros_ws/src/farm_tag_amcl/ | 라이다 시각 동기 보정 수신·적용 |
| robot/ros_ws/src/farm_tag_localization/ | 카메라 세션·태그 관측·보정 어댑터 |
| robot/ros_ws/src/farm_tag_localization/farm_tag_localization/node.py | 보상·시각 이송·전송 연결 |
| robot/ros_ws/src/farm_tag_localization/farm_tag_localization/pixel_bias.py | 선택적 화면 위치 편향 보상 |
| robot/config/localization/harvest_real.yaml | 기본 보정 설정 |
| robot/config/localization/reference_20261007/ | 태그 자산·관측 모델 |
| robot/config/localization/bias_trial_20261010/ | 모델 프로파일·학습 관측·재현 fixture |
| robot/tools/tag_camera/bias_trial/trial.py 및 trial.bash | ON/OFF 실행·Goal·로그 수집 |
| robot/config/robots/vicpinky/harvest_tag.rviz | PC RViz 설정 |

### 선택적 화면 위치 편향 보상

- 모델 ID: sec01-pixel-bias-trial-20261010-v1
- 기본 설정 OFF. 시험에서는 명시적으로 `trial.bash launch on`을 사용한다.
- `launch off`는 **화면 위치 편향 보상만 OFF**이며 태그 보정 자체는 유지한다.
- 프로파일은 이전 20261010_162411 녹화의 관측 74개로 작성했다. 이번 ON 주행 자료로 재학습하지 않았다.
- 검증 대상 tag36h11 ID 100–105, 가로 중심 388.04473876953125–889.77978515625px.
- 프로파일의 원본 heading 허용 범위는 -105°~-75°다.
- 현재 태그 검은 테두리 크기는 0.05m다. 과거 10cm 설명을 사용하지 않는다.
- 범위 밖 관측은 pixel_bias_skip으로 해당 보정만 생략한다.
- 공분산을 줄이지 않았다. 원본 캘리브레이션·장착값·지도·제어기·costmap을 변경한 패치가 아니다.

```text
n = (u - 640) / 640
거리 편향[m] = 0.02316284358688556 + 0.04866276347063953 * n
yaw 편향[rad] = 0.04603614825476121 - 0.07805139861644357 * n

벽 법선 = map +x
x_adjusted = x_raw + 거리 편향
y_adjusted = y_raw
yaw_adjusted = yaw_raw - yaw 편향
```

보상은 촬영 시각 pose에 먼저 적용하고 그 뒤 odom 시각 이송을 수행한다. 단일 환경에서 만든 시험 모델이며 범용 캘리브레이션 또는 운영 기본 ON으로 확정하지 않았다.

## 5. 최신 ON 실물 주행과 검증 결과

| 항목 | 값 |
| --- | --- |
| task_id | graph_test_8b717a0279ea4171ba3dcf8dbae696f0 |
| 시험 폴더 | runs/tag_bias_trial/20261010_172610_984950_on/ |
| 태그 세션 | runs/harvest_tag/20261010_172613_8njuaqou/ |
| 캡처 하위 | 20261010_172614_mra_uq1_ |
| 작업 구간 UTC | 2026-10-10 08:27:18.386535 ~ 08:28:05.779627 |
| 작업 구간 KST | 2026-10-10 17:27:18.386535 ~ 17:28:05.779627 |
| 결과 | 14번 SUCCESS / SUCCEEDED, 보상 ON |
| 요청 / queued / applied | 10 / 10 / 10 |
| 수신 dropped / rejected | 없음 |
| timing_skip / pixel_bias_skip | 각 1회 |
| 최종 추정 pose | x=1.214505307754741, y=-3.997689326406232, yaw=-1.60412323091493 |
| 최종 추정 목표 오차 | 위치 3.46cm, 방향 1.91° |

원시 events.jsonl과 rosbag 재검토에서 10개 요청의 number↔sequence, task_token↔token, source_stamp_ns, requested↔pose가 일치했다. 수신부 aligned_pose는 라이다 시각으로 이송된 값이므로 전달 pose와 값이 조금 다른 것이 정상이다.

### 원본 인계 분석 수치 — 그대로 보존

아래 수치는 이전 분석 결과를 사용자 인계 내용으로 보존한 것이다. 다음 절의 이번 재계산과 추출 방법이 다르므로 한 통계로 합치지 않는다.

| 평가 표본 | 거리 RMS 전→후 | 방향 RMS 전→후 |
| --- | --- | --- |
| 실제 적용 요청 10개 | 2.529 → 0.479cm | 3.063 → 0.803° |
| 보상 범위 내 유효 관측 71개 | 2.305 → 0.636cm | 3.206 → 0.774° |

이전 분석의 작업 구간 라이다 평면 475개: base–벽 거리 시작 3초 중앙값 41.4567cm → 끝 3초 43.2065cm, 약 1.75cm 증가. 중간 약 40.7~43.7cm. 평면 적합 RMS 중앙값 약 2.51mm. 중앙 라이다 점 거리에서도 유사 추세였다. 라이다 대비 AMCL 거리 추정 차이는 시작 약 5.2cm → 끝 약 0.7cm로 감소했다. 이 평가는 독립 실측 절대 정확도와 구분한다.

### 이번 문서 준비 중 직접 재계산 — 별도 방법

첨부 MCAP을 rosbags로 읽었다. laser 각도 -135°~-45°, 유효 거리 1m 미만을 선택하고, 녹화된 TF의 laser 회전 π 및 base 기준 전방 오프셋 0.185m를 반영했다. SVD 직선 적합과 1.5cm 잔차 제외를 3회 수행했다. 관측 촬영 시각에는 스캔별 거리·yaw를 선형 보간했다.

| 평가 항목 | 이번 재계산 |
| --- | --- |
| 작업 구간 스캔 | 475개 |
| 실제 적용 요청 10개 거리 RMS | 2.63 → 0.37cm |
| 실제 적용 요청 10개 방향 RMS | 3.28 → 0.97° |
| 작업 시작/끝 3초 base–벽 거리 | 약 41.37 → 43.10cm |
| 적합 RMS 중앙값 | 약 2.06mm |

벽 추출 범위·적합 방식 차이로 원본 분석과 수치가 조금 다르지만, 관측 오차 감소와 작업 중 벽 간격 증가의 방향은 일치했다. 71개 전체 수치는 이번 재계산에서 재산출하지 않았다.

### 구간을 나누어 확인한 변화

| 구간 | base–벽 거리 중앙값 |
| --- | --- |
| Goal 전 정지 구간 | 약 44.0cm |
| 10→11번 진입 마지막 3초 | 약 41.5cm |
| 11→14번 작업 마지막 3초 | 약 43.1cm |

이번 기록에서는 첫 태그 보정 요청이 작업 시작 후에 발생했다. 따라서 **10→11번 진입 중 벽에 가까워진 변화는 첫 보정 전에 이미 발생한 것**이다. 작업 시작의 41.5cm를 출발 시 차체 옆면 20cm와 직접 동일시하지 않는다.

첫 요청 x: 보정 전 AMCL 1.18548 / 시각 이송된 태그 추정 1.23976 / 보정 요청 1.21262. 태그는 기존 AMCL보다 실제 위치가 벽 쪽이라고 추정했고, 이후 제어기가 경로 x=1.188 쪽으로 가면서 벽에서 멀어졌을 가능성과 부합한다. 원인 확정 또는 보정의 단독 인과 효과로 해석하지 않는다.

### 기존 오프라인 검사 이력

패치 VALIDATION.md에는 기존·신규 59개 검사 PASS, OFF 동일성, 보상 부호·단위·시각 이송 순서, 범위 밖 skip, production _solve/_send 대역 검사, 해시 불일치 시 적용 중단 및 재적용 무변경 검사가 기록돼 있다. OpenCV 4.6/5 환경 검사 이력도 있다.

이는 패치 제작 당시 기록이며 이번 문서 작성에서 59개 전체를 다시 실행한 것은 아니다. ROS I/O 대역 검사는 실물 DDS 시험과 구분한다.

## 6. 남은 문제와 원인 후보

### 6.1 사용자 관찰

2026-10-10 사용자 확인: 출발 시 차체 옆면–벽을 약 20cm로 비슷하게 맞췄다. 처음에는 괜찮다가 주행하면서 벽에서 조금씩 멀어지는 현상은 여전히 있었다. 정밀하게 앞·뒤 각각 20.000cm를 실측한 것으로 기록하지 않는다.

### 6.2 벽·경로·차체 기준의 미정합

| 기준 | 값 | 해석 |
| --- | --- | --- |
| 현재 그래프 x | 1.188m | base 명목 이동선 |
| 그래프 도면 변환상 벽 x | 1.643m | 경로와 45.5cm |
| 태그 자산 벽 x | 1.653m | 경로와 46.5cm |
| 그래프 설계 차체 반폭 | 25.5cm | 25.5+20=45.5cm 명목 설계. 실제 base→최외측 실측 확정으로 취급하지 않음 |
| 태그 등록 상태 | design_candidate | 신규 독립 실측 없이 과거 벽 기준으로 평행 이동한 후보 |

그래프와 태그 벽 기준은 1cm 다르다. 라이다가 본 실제 면과 태그 부착면의 관계, 실제 차체 기준점–옆면 거리, 지도 벽의 등록 오차를 확인하기 전 어느 한쪽을 임의로 옮기지 않는다. footprint 반폭 또는 카메라 장착 y=0.25046456m를 실제 차체 반폭으로 대체하지 않는다.

후속 계산 시 동일 벽면·평행 자세라는 전제에서 필요한 base–벽 거리는 “실제 base→차체 옆면 거리 + 0.20m”다. 현재 base–벽 기록만으로 물리적 20cm 성공 여부를 단정할 수 없다.

### 6.3 종료 문제

adapter_exit=0, capture_exit=1, detector/rectify=-11, camera=1, clean_shutdown=false. 주행 중 보정 요청 10건이 적용된 사실과 별개로 카메라 종료 정리 문제를 남긴다.

## 7. 이번 단계 종료 결정과 후속 고도화

**결정: 현재 모델·코드·로그를 기준으로 보존하고 태그 보정 기능 검증 단계를 마무리한다. 단순 SUCCESS 횟수를 늘리기 위한 추가 반복 주행은 하지 않는다.**

| 우선순위 | 후속 항목 | 확인 후 변경할 대상 |
| --- | --- | --- |
| 1 | 실제 옆면 간격과 base 거리 연결, 라이다 면·태그 면 관계 | 실측 기준과 자산 등록 |
| 2 | 태그 벽·그래프 벽 1cm 차이의 의미 확인 | 필요 시 해당 기준만 수정. 공유 지도·예찰에 미칠 영향 사전 검토 |
| 3 | 진입 중 편차와 작업 중 보정·경로 추종 상호작용 | 원인 확인 후 초기화·경로·제어 항목을 분리해 조정 |
| 별도 | detector/rectify 종료 -11 | 카메라 세션 종료 처리 |

태그 보상은 이미 라이다 대비 관측 오차를 줄였다. 벽에서 멀어진다는 이유만으로 보상량을 더 늘리지 않는다. 수정할 근거와 조정 가능한 요소가 있으나 해결 방식·개선 폭은 아직 확정하지 않았다.

후속 변경 시 이번 기준 모델을 덮어쓰지 말고 새 모델 ID·설정 및 별도 결과로 구분한다. 현재 프로파일의 자산 해시 검사를 우회하지 않는다.

## 8. 재현 실행 순서 — 필요할 때만 사용

현재 추가 주행 지시는 아니다. 아래는 **scan_sync 및 bias_trial 적용·빌드가 완료된 당시 로봇**을 재현하는 절차다. 최초 설치·패치 적용은 묶음 RUN.md/VALIDATION.md를 먼저 확인한다. 원격 HEAD만 checkout하면 최신 시험 패치가 모두 준비됐다고 가정하지 않는다. 기존 변경을 비교하지 않은 rsync 덮어쓰기는 하지 않는다.

1. 로봇을 10번 부근에서 14번 방향으로 배치하고 실제 옆면 간격을 기록한다. 모터 전원을 켜고 odom TF 및 /dev/motor 상태를 확인한다.
2. 모터 영구 설정은 [영구 설정 안내](VICPINKY_MOTOR_LATENCY_20261010.md)를 따른다. 아래 임시 쓰기 대신 최초 1회 install, 이후 check를 사용한다.

```bash
sudo python3 /home/vic/vmany/main/farm_project/robot/tools/vicpinky_motor_latency.py install
python3 /home/vic/vmany/main/farm_project/robot/tools/vicpinky_motor_latency.py check
```

3. PC RViz 터미널:

```bash
bash /home/eunbi/vmany/main/farm_project/robot/tools/tag_camera/bias_trial/trial.bash rviz
```

이 명령은 프로젝트 PC install 없이 rviz2를 직접 실행한다. harvest_tag.rviz를 사용하고 /tf·/tf_static·/initialpose를 /harvest_01 아래로 remap한다.

4. 로봇 실행 터미널:

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/tag_camera/bias_trial/trial.bash launch on
```

bringup/navigation을 따로 실행하지 않는다. launch 후 지도 수신 시 **60초 안에 PC RViz의 2D Pose Estimate로 실제 위치·방향을 지정**한다. 늦은 초기화로 planner 활성화가 실패했던 이력이 있다.

5. 초기화 후 로봇 별도 터미널에서 기록과 실제 이동:

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/tag_camera/bias_trial/trial.bash goal
```

goal은 실제 14번 이동을 요청한다. 실행 조건을 확인하고 rosbag 기록·목표 생성·결과 수집을 수행한다.

6. Goal 결과 수신 후 launch 터미널에서 Ctrl+C로 종료하고, 종료 완료 뒤 로봇 별도 터미널:

```bash
bash /home/vic/vmany/main/farm_project/robot/tools/tag_camera/bias_trial/trial.bash collect
```

7. PC로 복사한다. 날짜·시각을 붙여 기존 원본을 덮어쓰지 않는다.

```bash
scp vic@192.168.0.12:/tmp/harvest_tag_bias_latest.tar.gz \
  "/home/eunbi/Downloads/harvest_tag_bias_on_$(date +%Y%m%d_%H%M%S).tar.gz"
```

trial.bash가 주행 ROS 환경과 로봇 install을 로딩한다. 카메라 측 환경은 capture_session 책임이다. OFF 비교가 필요한 경우에만 launch off를 선택하며 태그 보정 전체 OFF와 혼동하지 않는다.

## 9. 원본 자료·무결성·참조

원본 압축파일은 Git에 중복 포함하지 않는다. 아래 파일명·SHA256으로 식별하며 사용자 제공 대화 파일 및 PC 원본을 보존한다. PC 원본의 영구 보관 위치는 아직 확인되지 않았다. Confluence는 사용자 commit/push 후 확정 커밋을 연결해 작성할 예정이다.

| 자료 | 이번 제공 파일명 | SHA256 |
| --- | --- | --- |
| 실제 ON 로그 | harvest_tag_bias_on_20261010.tar(1).gz | 07fceff369f242b068137e71c6924d64bfb441b6d1d07a3be2f1ad1d4fd45fa6 |
| 실제 적용 패치 묶음 | harvest_tag_bias_trial_20261010.tar(2).gz | 82de30b3529a81a1422c2564657300b0db211e83cf3fbbaee4211fa4397c51cf |

중복 다운로드 접미사 (1)/(2)는 파일 내용 버전과 동일한 뜻이 아니다. 패치 해시는 사용자 전달 원본 해시와 일치했다. 이전 파일명은 harvest_tag_bias_on_20261010.tar.gz 및 harvest_tag_bias_trial_20261010.tar(1).gz다.

로그 내부 기준 폴더에는 manifest.json, inputs/, bag/bag_0.mcap, goal.json, goal.log, launch.log, summary.json이 있다. 태그 세션에는 events.jsonl·관측 기록·촬영 설정·종료 상태가 포함된다.

패치 묶음에는 RUN.md, VALIDATION.md, apply_bias.py, files.txt, manifest.json, 코드·설정·테스트 및 문서 변경 내용이 있다. **이 패치는 전체 저장소나 scan_sync 설치본 전체를 대체하는 독립 설치 묶음이 아니다.**

### 실행 스냅샷 주요 SHA256

| 파일 | SHA256 |
| --- | --- |
| node.py | b090abf35310aa709f98c5984f975d664c391683ac66e5b7194cb57af8d3ca93 |
| pixel_bias.py | 37388c85a22c6dcbb8866947a5994464ba2b363fee2656cd0eb90ea8f2f8e01a |
| graph.geojson | fc72ffb617c0f756a6eb58477c0e1211dbc3f4cea2ca9855874008b150cfc504 |
| assets.candidate.json | abf2a55e952df9d5b88a860c0eca814a07d01024e6b03d407e8e4a8ae9f5fcc5 |
| observation_model.json | 539bf6c8a81578a5100b6a113ab18e9e7bd34da0226a8308581556d8f7fb6bb4 |
| many_farm.yaml（manifest 기준） | bbe46086336b76b5f11611160803260a91339d87c97709a6ffe5114d8d328fac |
| many_farm.pgm（manifest 기준） | a9f852637490aaff50c7115a543e2780a60ecf654747b3e777319251e151949e |

### 연결 문서

- [AprilTag 위치추정 보조 — 구현 및 검증（이전 단계）](https://robot3final.atlassian.net/wiki/spaces/3/pages/32145411)
- [매니팜 지도 및 Route Graph 명세 — 300cm 화단·21개 포인트](https://robot3final.atlassian.net/wiki/spaces/3/pages/33914899)
- [그래프 기반 경로 생성 및 로봇 이동 구조](https://robot3final.atlassian.net/wiki/spaces/3/pages/33194003)
- [Vic pinky 환경 설정](https://robot3final.atlassian.net/wiki/spaces/3/pages/12681239)
- [원격 조회 기준 커밋](https://github.com/Robot3FinalProject/main/commit/7689f3648007c643f01a2dcaee160ae6fcbefcdd)

기존 문서는 작성 당시 이력으로 유지한다. 현재 실물 Route Server 미사용·scan_sync 및 선택적 편향 보상 상태는 이 문서의 날짜와 시험 스냅샷을 기준으로 읽는다.


## 10. Git 정리 및 모터 영구 설정 — 후속 승인

2026-10-10 17:44 사용자 승인으로 모터 시리얼 BG02QM7Y에만 latency_timer=1을 적용하는 udev 규칙과 설치 도구를 추가한다. 현재 로봇 정보의 값은 1이며, 기존 99-vic-pinky.rules는 /dev/motor 이름·권한을 설정한다. 기존 규칙은 변경하지 않는다. 새 영구 규칙의 로봇 설치·재부팅 확인은 전달 시점 미실행이다.

작업본의 scout_navigation.launch.py 변경은 이전 scan_sync 연결이다. tag_scan_sync 기본 false, 실물 수확에서만 farm_tag_amcl 선택하며 이번 정리에서는 그 파일을 수정하지 않는다. 기존 HarvestWork·scan_sync·pixel_bias 구현을 보존하고 이번 전달물은 문서·새 시스템 설정/도구만 변경한다. 검증 및 commit 범위는 [Git 정리 안내](HARVEST_GIT_FREEZE_20261010.md)를 따른다.

