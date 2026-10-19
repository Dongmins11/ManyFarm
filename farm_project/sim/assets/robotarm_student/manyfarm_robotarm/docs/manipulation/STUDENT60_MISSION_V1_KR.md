# Student 접힘·다중 과실 실행 v1 — 별도 후보

2026-10-16 사용자 요청에 따른 별도 버전이다. 기존 D435 Student/v20, U20 모델·자료·수집기, 이전 전달 압축 파일은 보존한다. 학습 가중치를 바꾸지 않고 실행 계층과 별도 평가 장면을 추가했다. 오른팔 한 대를 제어하며, 왼팔은 기존 고정 자산이다.

## 실행 순서와 완료 의미

접힘 대기 → 기존 HOME으로 물리 이동 → 지정 Student 수확 → 해당 과실의 박스 안착 확인 → 상방으로 빠져나와 HOME 경유 → 접힘 복귀. 남은 지정 과실이 있으면 같은 과정을 반복한다. 마지막 과실의 접힘 복귀 후 연속 정지 확인까지 통과해야 작업 완료다.

과실 수확 성공 수와 전체 작업 완료를 따로 기록한다. 과실을 적재했지만 팔 복귀가 실패하면 적재 성공은 남고 작업 완료는 거짓이다. 복귀 중 이미 적재한 과실이 박스에서 벗어나거나 남은 과실이 분리되면 실패한다. 장면 초기화나 관절 위치 순간이동으로 복귀를 대신하지 않는다. 최초 시뮬레이션 장면 배치/정적 미리보기에서만 위치를 설정한다.

`StudentHarvestMission`은 확정된 유한 목표 목록이 필요하다. 과실이 안 보인다고 모두 수확했다고 처리하지 않는다. 목표별 ID·색상·카메라로 관측한 초기 위치를 보관한다. 초기 관측 위치를 `box_from_arm`으로 중력 기준 task/world 좌표로 변환하고 Z 높이가 낮은 순서로 정렬한다. 높이가 같으면 ID 순서로 결정하며, 탐지 confidence 순서나 기울어진 팔/카메라 좌표의 Z를 높이로 오인하지 않는다. 순서와 측정 높이는 `result.json`의 `ordered_target_ids`/`observed_target_heights_m`에 남는다. 다음 HOME에서 새 영상과 위치 연속성으로 재지정한다. 같은 색 과실이 둘 이상이어도 거리 게이트/모호성 검사를 거친다. 동색 추적은 CPU 검사를 했으며, 현재 native 시험 장면은 Red/Yellow 두 개다. 임의 농장의 모든 과실·보이지 않는 과실까지 자동 탐색 완료를 판정하는 기능은 아니다.

## 기존 다중 과실 지원 감사

기존 선택된 D435/U20 자료의 `TeacherDomainEnv`는 Red와 Yellow 두 자산 중 한 개만 작업 영역에 놓고, 나머지는 `(1.25,1.25,0.9)m`로 치운다. 기존 Student 뷰어는 한 과실 종료 후 `reset()`한다. 기존 전달 `Student60Session`도 목표 한 개이며 동일 색의 복수 후보를 자동 지정하지 않는다. 별도의 과거 Teacher 순차 수확 실행기는 있으나 현재 Student 연결 완료의 근거가 아니다. 따라서 기존 개발4/4·fresh4/4는 단일 과실 시험이며 다중 과실 반복 성공률이 아니다.

새 `StudentMissionEnv.author_multifruit_scene()`는 held-out 도달 가능 bank에서 최소12cm 떨어진 두 위치와 각 과실 자세를 최초 한 번 배치한다. 두 과실을 동시에 작업 영역에 두고, 이후 과실·줄기·박스·로봇 상태를 유지한다. 기본 장면은 두 개이고 공통 실행기의 외부 목표 목록은 더 많은 개수도 처리할 수 있다. 신경망이 다중 과실로 새로 학습된 것은 아니다.

## D435 / U20 구분

- D435: 기존 recurrent Student + 기존 camera center + v20 보조제어, 손목 RGB·오른IR 및 후방 RGB-D.
- U20: 기존 U20 RGB 전용 Student + v20 보조제어의 새 조합, U20 손목 RGB와 후방 D435 RGB-D. D435 IR/center 모델을 대입하지 않는다. 기존 U20 수집기는 시연 데이터 보존을 위해 그대로 둔다.
- 두 카메라 경로는 동일 mission 상태기·접힘 설정·안착 후 복귀 계약을 사용한다. 실제 카메라 외형과 센서 FK는 각각의 URDF/rig를 사용한다.
- 학습된 정책 내부의 20Hz 순차/촬영30Hz/물리60Hz 계약은 유지한다. 목표별 시간 원점을 함께 옮겨 영상 age와 정책의 elapsed 입력을 보존한다. 처리 완료마다 임의 주기로 실행하는 지연 대응 버전은 아니다.

## 실행

저장소 또는 새 전달본의 `manyfarm_robotarm` 루트에서 실행한다. Isaac Sim 5.1/Isaac Lab 환경과 별도의 Ultralytics Python 경로가 필요하다. 기본은 검사만 수행하며 `--execute`를 붙여야 시뮬레이션이 시작된다. 출력 디렉터리는 항상 새 이름이어야 한다.

```bash
ISAAC_PY=/home/bhc/isaac/env_isaaclab/bin/python
VISION_PY=/home/bhc/manyfarm_ws/manyfarm_robotarm/.venvs/harvest_vision/bin/python

# 접힘/HOME 이미지 생성: 물리 수확 시험과 구분되는 정적 미리보기
"$ISAAC_PY" scripts/run_student60_mission.py --camera d435 --headless --execute --preview-only --output outputs/stow_preview_d435_01
"$ISAAC_PY" scripts/run_student60_mission.py --camera u20 --headless --execute --preview-only --output outputs/stow_preview_u20_01

# 실제 시뮬레이션 접힘→HOME→접힘 검사
"$ISAAC_PY" scripts/run_student60_mission.py --camera d435 --headless --execute --motion-only --output outputs/stow_motion_d435_01

# 동일 장면 다중 과실 mission. GUI는 --headless를 빼면 된다.
"$ISAAC_PY" -u scripts/run_student60_mission.py --camera d435 --execute --vision-python "$VISION_PY" --wall-seconds 1800 --output outputs/mission_d435_01
"$ISAAC_PY" -u scripts/run_student60_mission.py --camera u20 --execute --vision-python "$VISION_PY" --wall-seconds 1800 --output outputs/mission_u20_01
```

새 전달본에서는 먼저 `"$ISAAC_PY" scripts/sim_team/check_student60_mission_release.py`로 파일·양쪽 모델과 원래 D435 계약을 검사한다. 원래 단일 목표 실행기는 `scripts/sim_team/run_student60_delivered.py`로 유지되며 새 순서의 진입점은 `scripts/run_student60_mission.py`다. `handoff/MISSION_RELEASE.json`, `MISSION_MANIFEST.json`이 새 버전의 기준이다. 기존 `handoff/DEPLOYMENT.json`/`MANIFEST.json`은 원래 단일 목표 기준으로 그대로 보존한다.

`--wall-seconds`는 렌더링을 포함한 실제 경과시간의 상한이다. 명령 주기나 수확 제한 시뮬레이션 시간을 바꾸지 않는다. 장비가 느려 이 상한에 도달하면 완료로 처리하지 않고 `wall_budget_interrupted`를 기록한다. 위 예시는 두 과실의 복귀까지 관찰할 여유를 두었다.

`--record-video`를 추가하면 전체 로봇·박스 영상과 실제 손목 RGB/오른쪽 IR/후방 RGB 입력을 `mission_raw.mp4`로 기록한다. 별도 관찰 카메라는 기존 센서 렌더링 결과만 읽으며 물리를 추가로 진행하거나 정책 입력을 바꾸지 않는다. 재생은 시뮬레이션 시간 기준 1배속(20fps)이고, 실제 컴퓨터의 처리 지연을 보여주는 성능 영상은 아니다. 완료 시 마지막 화면만 2초 유지한다. IR은 기존 환경과 동일한 광학 위치의 가시광 휘도 근사다. U20에는 IR 입력이 없으므로 해당 패널은 없음으로 표시한다.

## 확인한 결과

- CPU 상태기·센서·보조제어 관련 34개 검사 통과. 높은 과실이 먼저 탐지된 경우, 팔 좌표축이 기울어진 경우, 같은 높이·동색의 복수 목표를 포함한다.
- D435와 U20 각각 실제 시뮬레이션 접힘→HOME→접힘 통과. 단순 자세 표시나 관절 순간이동을 이동 성공으로 집계하지 않았다.
- D435 `d435_low_first_r2`: 같은 장면에서 낮은 빨강(관측 높이 0.888m)→높은 노랑(0.971m) 순으로 2개 모두 박스 안착. 각 과실 사이 접힘 복귀, 마지막 접힘과 정지까지 완료(`DONE`, 시뮬레이션 124.35초). 장면 리셋 0회. 한 장면의 검증이며 일반적인 성공률을 의미하지 않는다.
- 동일 설정 녹화 재실행 `d435_recorded_r2`도 2/2 안착과 마지막 접힘·정지 완료(`DONE`, 시뮬레이션 124.60초). `handoff/mission_demo.mp4`는 이 실행을 기록한 126.65초 영상이며, 마지막 정지 화면 유지 2초를 포함한다. 1280×800/20fps H.264 전체 디코딩과 주요 장면을 확인했다. 동일 장면 재실행을 새로운 독립 평가 장면으로 세지 않는다.
- 카메라·프레임 경로 기하 검사: D435/U20 각 78개 자세 샘플에서 검사 대상 겹침 없음. 제외 항목과 연속 충돌 검사의 한계는 아래와 같다.
- U20 `u20_native_smoke`: 실제 카메라가 있는 장면에서 240회 제어, HOME 이후 65회 카메라 기반 Student 추론까지 통과하고 의도적으로 짧은 검사를 종료했다. 다중 과실 전체 수확을 검증한 결과는 아니며, D435의 2/2를 U20 수확 성적으로 대신하지 않는다. 최종 개별 실행 결과는 `FINAL_CHECKS.json`을 따른다.

## 접힘 자세를 수정하는 위치

`src/harvest_robot/config/student60_mission_v1.json`의 `stow_rad`가 접힘 자세다. 순서는 shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper. 기본 후보는 rad `[0,-1.50,0.77,-1.30,0.0487963268,1.1]`, 약 deg `[0,-85.94,44.12,-74.48,2.80,63.03]`이다. 기존 HOME은 유지한다. 손목/집게가 수확 공간 쪽으로 뻗는 대신 위·몸체 쪽으로 접히는 후보이며 사용자 이미지 검토가 남아 있다.

원본 파일을 덮어쓰지 않고 새 설정 파일을 만들 수 있다.

```bash
"$ISAAC_PY" scripts/configure_student60_stow.py --joint-deg 0 -85.94 44.12 -74.48 2.80 63.03 --output outputs/my_stow_v2.json
"$ISAAC_PY" scripts/check_student60_stow_geometry.py --config outputs/my_stow_v2.json --output outputs/my_stow_v2_geometry.json
"$ISAAC_PY" scripts/run_student60_mission.py --camera d435 --config outputs/my_stow_v2.json --preview-only --headless --execute --output outputs/my_stow_v2_preview
"$ISAAC_PY" scripts/run_student60_mission.py --camera u20 --config outputs/my_stow_v2.json --motion-only --headless --execute --output outputs/my_stow_v2_motion
```

경유 자세는 `home_to_stow_via_rad`에6개 각도의 배열을 순서대로 넣는다. 접힘→HOME은 이 순서를 역으로, HOME→접힘은 정순으로 사용한다. 중력 때문에 목표에 조금 못 미치는 경우 이동 중 위치 오차를 적분하되 보정량은±0.06rad, 명령의 실측각 선행은0.08rad, 이동 속도는 설정값 이내로 제한한다. 완료 판정은 보정된 명령이 아니라 원래 목표 자세와 실제 관절각을 비교한다. `speed_rad_s`는 이동 속도, `return_lift_m`는 안착 후 위로 빠지는 높이다. 관절 한계를 넘어선 값은 거부한다. 임의 HOME 변경은 기존 Student 시작 분포를 바꾸므로 기본 HOME을 유지한다.

정지는 관절각의 직전 실제 표본과 현재 표본 차이/50ms가0.08rad/s 이하, 순간 joint_vel이0.5rad/s 이하, 자세 오차0.035rad 이하인 상태가0.4초 연속인 것으로 판정한다. 순간 물리 solver 속도가 정적인 자세에서도 약0.17rad/s여서 순간 속도만0.08로 판정하던 첫 검사는 시간초과했다. 미래 표본 없이 실제 관절각 변화와 순간 속도를 함께 확인하도록 보완했다. 정책에는 원래 측정 joint_vel을 유지한다. 이 숫자는 실제 STS3215 정지 판정 보정을 대신하지 않는다.

## 팀에 전달할 내용과 한계

새 압축 파일에 기존 D435 전체 전달본, 카메라 로봇 USD/URDF/mesh, 추가 mission 코드, U20 모델·URDF·rig, 새 검사 결과·이미지·설정 편집 도구가 포함된다. D435의 카메라 포함 USD는 기존 물성을 보존한 자산이며, U20은 포함된 frozen 물성 USD 위에 U20 외형·센서를 구성하는 runner와 원본 URDF/mesh를 제공한다. U20 실행기 없이 D435 USD에 U20 모델만 꽂는 방식은 지원하지 않는다.

수신 농장에서는 `MissionCameraSession`과 `StudentHarvestMission`에 실제 카메라 입력, 관절 피드백, 완전한 할당 목록, 실제 적용 명령 ack와 박스 확인/오류를 연결한다. 시뮬레이션 runner의 truth↔ID 매핑은 평가 전용으로만 사용하며 정책 목표 위치는 영상 탐지에서 만든다. 시뮬레이션 박스 확인은 기존 mesh 안착/분리/양집게clear/0.6초 기준이다. 실물에서는 해당 event를 박스 카메라/센서로 구현해야 한다. 수확 정책·이동 경로 계산 자체는 Teacher/과실 정답을 입력받지 않는다.

카메라·프레임 검사는 현재 URDF collision 형상의 보수적 convex hull과 최대0.025rad 간격의 경로 샘플을 쓴다. 장착 접촉부인 gripper/wrist/움직이는 jaw와 왼팔 가동 링크는 제외한다. 연속적인 모든 mesh 충돌이나 실물 장착 오차 인증은 아니다. 기존 frozen 물성에는 최신 카메라 충돌/질량이 자동 대체되지 않으므로 이 기하 검사를 별도 수행한다. 실물 모터 구동, 실제 박스 판정, STS 강성 대응, 양팔 연동은 이번 구현 범위 밖이다.

실제 native 수확 결과는 `handoff/mission_verification/` 및 개발 작업 폴더의 `FINAL_CHECKS.json`을 따른다. CPU 상태기 성공을 물리 수확 성공으로 집계하지 않는다.
