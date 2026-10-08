# 수확 과실 충돌·중력·줄기 물리 확인

2026-10-08 KST. 기준 main/7d9ae40 이후 수확 시험 UI의 미커밋 변경에 추가.
사용자 요청: 충돌 표시 메뉴 복원, 실제 물리 적용 확인, 랜덤 자세가 유지되는 원인 확인.

## 실행과 충돌 표시

```bash
cd ~/main/farm_project
python3 sim/tools/harvest_test_ui.py
```

기존에 실행한 창에는 새 소스가 자동 반영되지 않는다. 새로 실행한 창을 사용한다.
이번 확인에서 사용자의 기존 시험 창은 종료/변경하지 않았으며, 새 진단 창을 별도로 열어 두었다.

GUI 실행에서 `omni.kit.viewport.menubar.display`와 `omni.physx.ui`를 활성화한다.
농장 단독/다중 실행의 GUI에도 적용하며 headless에는 적용하지 않는다.
정확한 메뉴 이름은 **눈 아이콘(Show/Hide) → Show By Type → Physics → Colliders → Selected 또는 All**이다.
`Physics Collision`이라는 단일 항목이 아니라 `Physics` 아래의 `Colliders`다.
[Isaac Sim 5.1 공식 메뉴 안내](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/importer_exporter/import_urdf.html).

시험 패널에는 같은 설정을 바꾸는 `Hide / Selected / All` 버튼도 추가했다.
`Place robot`을 누르면 시험 과실과 로봇을 선택하므로 `Selected`만으로 과실·집게·박스 충돌 모양을 볼 수 있다.
다른 과실은 Stage에서 root나 하위 Collision을 선택한다. `Select test fruit + robot`으로 원래 대상으로 돌아온다.

초록 와이어는 동적 강체의 충돌 형상, 자홍은 정적 형상이다. 주황색은 일반 선택 윤곽이므로 혼동하지 않는다.
시각 메쉬와 충돌 형상은 다를 수 있다. 특히 집게 안쪽 면, 과실 꼭지, 박스 바닥에 불필요한 빈틈/덮임이 없는지 본다.
표시 스위치는 **충돌 계산을 켜는 버튼이 아니다**. 켜져 있는 충돌 형상을 보여 주는 기능이다.
PhysX가 지원하지 않는 형상에서 fallback을 사용한 경우 표현과 실제 엔진 근사가 다를 수 있으므로 경고 로그도 확인한다.

## 팔 없이 물리만 확인하는 순서

1. `Place robot`으로 배치하고 정지 확인을 기다린다.
2. `Physics only: OFF`를 눌러 ON으로 전환한다. 기존 오른팔 주변 영역만 활성화하고 480Hz로 진행한다. Teacher 정책과 팔 작업은 시작하지 않는다.
3. 아래 `Fruit physics inspector`에서 상태와 수치를 확인한다.
4. `Physics only`를 다시 눌러 OFF로 전환한다. 움직이는 과실은 안정될 때까지 동적으로 유지한다. 정지 확인 후 재배치/수확이 가능하다.
5. 실제 집게 접촉은 관찰 모드를 OFF로 하고 `Harvest`를 실행하면서 `Finger -> fruit contact` 두 값을 본다.

| 표시 | 의미와 확인 기준 |
|---|---|
| DYNAMIC / FROZEN | 실제 활성 집합과 kinematic flag. 대기 중 부착 과실은 FROZEN이 정상이다. |
| gravity ON/OFF | RigidBodyEnabled와 disableGravity 설정. ON이어도 FROZEN이면 자유 낙하하지 않는다. |
| mass | 초기화 때 PhysX에서 읽고 검증한 질량. 현재 프로파일은 9g다. |
| Colliders enabled | 선택 과실의 CollisionAPI 개수와 collisionEnabled 개수. 이번 과실은 1/1, convexDecomposition이다. |
| Root dz | 최초 과실 root 위치 대비 수직 변위(mm). 음수면 내려갔다. |
| tip offset | 현재 꼭지점과 고정 앵커 사이 거리(mm). 0만 기대하는 강체 조인트가 아닌 유연한 스프링이다. |
| Rotation from initial | 최초 랜덤 quaternion에서 변한 각도. 초기 회전 자체를 0으로 바꾸지 않는다. |
| COM-to-tip tilt from up | 무게중심→꼭지 벡터와 위쪽 수직 방향 사이 각도. 과실 시각 메쉬의 축과 동일한 값은 아니다. |
| Gravity Fz | 초기 PhysX 질량 × PhysicsScene 중력으로 계산한 값(N). 동적/중력 유효 상태에서 표시하고 고정 시 0이다. 엔진에서 별도로 읽은 접촉력이 아니다. |
| stem Fz | 마지막 물리 tick 직전에 코드가 실제 적용한 줄기 지지력(N). 정지 평형에서 중력과 반대 부호로 비슷해야 한다. |
| Finger -> fruit contact | 선택한 과실에 대한 고정/움직이는 손가락의 PhysX 접촉력 크기(N). 다른 과실이나 차체 접촉을 포함하지 않는다. 실제 tick dt로 impulse를 힘으로 환산한다. |
| arm contact max | 손가락/팔 전체의 net 접촉력 최대값. 선택 과실 접촉과 구분한다. |

집게가 보기에 닿았는데 해당 과실 접촉력이 계속 0이면 먼저 충돌 윤곽선의 실제 간격·충돌 활성·필터를 확인한다.
0보다 큰 힘은 접촉이 있다는 근거이며, 충분한 양손 파지·방향·유지시간·적재 성공까지 보장하지 않는다.
현재 Teacher의 접촉 기준은 프로파일의 0.08N이며 성공은 기존 전체 조건을 따른다.

표식은 노랑=고정 앵커, 초록=현재 꼭지, 청록=COM, 빨강=중력 화살표다.
선/점은 실제 world 좌표이며 화살표 길이만 **1m/N** 표시 배율을 사용한다.
이 표식은 물리 collider나 joint가 아니다. 체크박스로 표시만 끌 수 있다.

## 랜덤 회전이 남는 이유

현재 구현은 connector rigid body와 paprika rigid body를 native joint로 묶은 자유진자 모델이 아니다.
과실별 최초 꼭지 world 위치를 고정 앵커로 저장하고, 매 물리 tick마다 다음 외력을 적용한다.

- 꼭지 변위·속도에 따른 스프링/감쇠력, COM 기준 lever×force 토크.
- 최초 랜덤 자세(`rest_orientation`)로 되돌리는 회전 복원 토크와 회전 감쇠.
- gravity는 켜져 있으며 중력을 상쇄하는 별도 +mg 보상은 없다.

`stem.angular_k=0.015 N·m/rad`, `angular_d=0.002 N·m·s/rad`이다.
따라서 중력 때문에 조금 처지고 회전한 뒤 회전 복원력과 평형을 이룰 수 있다.
랜덤 회전이 완전히 사라지거나 꼭지 아래로 곧게 정렬되는 것이 현재 모델의 동작 목표는 아니다.
기본 대기 모드에서는 성능을 위해 부착 과실을 kinematic으로 고정하므로 처짐도 진행하지 않는다.

회전이 자유로운 지지점 연결이라면 무게중심이 지지점 아래로 가려는 설명은 맞다.
다만 과실 메쉬의 세로축까지 정확하게 수직이 되거나 중력이 yaw까지 초기화한다는 뜻은 아니다.
현재 모델을 그 형태로 바꾸려면 실제 connector 연결점·자유 회전축·줄기 강성·분리 조건을 정하고
전달 Teacher가 사용한 모델과 달라지는 영향을 검증해야 한다. 이번 변경은 시각화/계측/관찰 모드이며
줄기 물성을 낮추거나 랜덤 회전을 재설정해 성공처럼 보이게 만들지 않았다.

코드 근거: `fruit_attachment.py`의 초기 anchors/rest_orientation 및 update,
`stem_physics.py`의 stem_step 회전 복원식, `fruit_asset_setup.py`의 disableGravity=False.

## 이번 실제 확인 결과

Isaac Sim 5.1 / RTX 4070 SUPER, seed713, SEC10의 `Bed_01/Fruits/Pepper_0017_yellow`.
팔 정책을 실행하지 않고 기존 줄기 물리로 8 시뮬 초 관찰했다.

| 항목 | 실제 기록 |
|---|---:|
| 물리 | 480Hz, 주변 5개 활성 |
| 상태 | dynamic, kinematic=false, gravity=true |
| 과실 충돌 | 1/1 enabled, convexDecomposition |
| 과실 root 하강 | 약 10.788mm |
| 최초 자세 대비 회전 | 약 8.360° |
| 정지 시 COM→꼭지 기울기 | 약 35.099° |
| 중력 mg의 Z 성분 | −0.088290N |
| 마지막 적용 줄기 힘 Z | +0.088290N |
| 관찰 종료 | 안정 후 60Hz, 활성0, 고정 상태, 프로세스 종료0 |

중력 반응과 외력 적용은 확인했다. 이것이 모든 과실·집게 충돌 형상의 적절성이나 Teacher 수확 성공을
검증했다는 뜻은 아니다. 이번 관찰에서는 팔을 움직이지 않았으므로 손가락 접촉력 0이 정상이다.
다음은 `Harvest` 중 선택 과실 접촉력과 형상을 함께 비교하는 단계다.

- 오프라인 99개 실행: 98 PASS, 1 SKIP(일반 Python의 USD 부재), 실패0.
- GUI 화면에서 공식 충돌 와이어와 진단 패널 표시를 직접 확인했다.
- 로그: `sim/runs/harvest_test_ui/physics_inspection_20261008/`의 `result.json`, `unittest.log`, `gui.png`, `final_gui.png`.
- 각 실행의 `physics_inspection.jsonl`에 선택 과실의 pose·중력·줄기 힘·충돌 flag와 접촉력을 5Hz로 기록한다.
- 공통/실물/원본 USD/정책/물성 변경 없음. 문서 갱신, 커밋·푸시 미실행.

## 변경 파일 전달

현재 작업 폴더에는 이미 반영했다. 다른 PC에 `harvest_physics_inspection_20261008.tar.gz`를 다운로드해 적용할 경우:

```bash
tar -xzf "$HOME/Downloads/harvest_physics_inspection_20261008.tar.gz" -C "$HOME/main/farm_project"
```

패치에는 앞선 수확 UI와 이번 진단 기능의 변경 파일만 포함한다. 대상 PC의 별도 미커밋 변경은 먼저 보관한다.


## 2026-10-08 추가 정정: 학습 팔 물리 정렬

사용자가 제공한 `main/arm_collision.png`와 `arm_collision_sim.png` 비교 후, 이전 검증에서 팔 충돌 근사화 차이를 놓친 것을 확인했다. 기존 농장은 convexHull, 전달 current_robot은 convexDecomposition이었다. 이전 물성 확인 기록은 팔 형상까지 동일함을 입증한 기록이 아니다.

사용자의 “로봇팔 물성치, 충돌 판정 … 다 학습환경에 맞춰서 수정” 요청에 따라 다음을 적용했다. 기준은 전달 `current_robot/82310b121a80b60a/harvest_current.usd`와 `teacher_ramp_20260930` 실행 환경이며, 전달 소스/정책은 수정하지 않았다.

| 항목 | 수정/검증 |
|---|---|
| 움직이는 오른팔 여섯 몸체 충돌 | 전달 메시 15개(메시14+박스1), 정점·삼각형·링크 내 변환 그대로 추출. convexDecomposition 유지 |
| 질량/무게중심/관성 | 전달값 사용. 실제 두 환경 PhysX 배열에서 여섯 몸체 전부 일치 |
| 집게/카메라 고정 연결 | 전달처럼 카메라·브래킷을 집게에 합성. 집게0.180kg. 기존0.087+0.018+0.075kg 별도 몸체/고정조인트 비활성화로 이중 질량·충돌 방지 |
| 팔/집게 drive | 25/1.5 및8/0.3 Nm/rad 계열 gain, effort2/0.5Nm, 속도1.2/1.5rad/s. 실제 PhysX 값 확인 |
| 관절 한계/프레임/마찰/armature | 전달값과 비교, 관절 한계 및 마찰/armature 복사. 팔 장착 위치는 농장 장착 TF 유지 |
| 자기충돌/solver | false→true, 위치32/속도1→12/4. TGS/GPU dynamics, 학습의 stabilization/CCD off 및 접촉 관련 scene 설정/버퍼 일치 |
| 접촉 재질 | 일반 팔1.0/0.8/0, 집게1.0/1.0/0.02(정지마찰/동마찰/반발). combine average |
| 팔 접촉 거리 | 기존 집게1mm override 제거, 전달 collider의 미지정 기본값 유지. 과실/박스의1mm 설정과 구분 |
| 접촉 판정 센서 | 학습과 같은 shoulder/upper/lower/wrist 네 링크. 집게/움직이는 턱 두 센서 별도 |

원본 농장 USD를 덮어쓰지 않고 세션 레이어에 적용한다. 기준 자산은 `sim/assets/robots/harvest_physics/teacher_arm_reference.usdc`와 SHA256 출처 JSON이며 runs 폴더에 런타임 의존하지 않는다. `teacher_alignment.enabled=false`는 이번 물리 정렬을 해제하는 복원 스위치다. 새 프로세스로 재시작해야 반영된다.

검증: USD 회귀7+기존 자산3+관련 단위46=56 PASS. 전달 독립환경1회 및 농장GUI3초 정상종료0. 독립 환경과 농장 실행의 USD/PhysX readback115항목 PASS; 최종 열린 GUI에서도115항목 재확인. 입력/로그/비교결과는 `sim/runs/arm_physics_alignment_20261008/`에 있다. 재검사 도구는 `sim/tools/check_teacher_arm_alignment.py`다.

후속 Nsight 계측에서 농장 GPU solver의 실제 반복은32/4로 확인됐다. GPU 경로가 활성 몸체·관절계의
반복 횟수 최대값을 사용하므로 수확 관절계12/4와 기존 관절계32/1의 영향을 함께 받는다.
위115항목 속성 일치가 장면 전체 solver 실행까지 같은 것을 보장하지 않는다.
[실측 근거와 CPU/GPU 성능 비교](HARVEST_TEST_UI_20261008.md)의 마지막 절을 참고한다.

수확 시험 결과는 **적재0/1**이다. seed713/SEC10 노랑에서3.870834초에 `arm_collision`, shoulder/lower 링크에 크기가 같은 반대 방향 접촉력이 기록됐다(자기접촉과 일치하는 양상, 충돌 pair ID는 미계측). 이어 복귀2.779N 접촉으로 `RETURN_FAILED`, safe_stopped=true,60Hz 복귀·프로세스 종료0. 성공률 개선을 입증한 것이 아니며 성공 판정/정책/안전 임계값을 바꾸지 않았다. 최종 GUI는 배치 및 Physics-only 관찰 후 사용자가 시험할 수 있도록 열어 두었다.

남는 환경 차이: 학습은 고정 베이스, 농장은 이동 차체/별도 왼팔·바퀴 관절이다. 농장 장애물·과실 자세/배치·적재함 위치도 같지 않다. scene query(lidar용)와 IsaacLab env collision group 구성은 농장 구조를 유지한다. 따라서 오른팔 물성 정렬을 전체 학습 환경의 완전 동일성이나 수확 성공 보장으로 해석하지 않는다.

변경 파일 전달본은 `sim/runs/arm_physics_alignment_20261008/changed_files.tar.gz`이며 기존 미커밋 내용이 포함된 현재 파일 사본이다. 이 PC에는 이미 적용했다. 다른 사본에 적용할 때는 그 사본을 백업한 뒤 다음처럼 프로젝트 폴더에 푼다.

```bash
tar -xzf /path/to/changed_files.tar.gz -C ~/main/farm_project
```


## 후속 정정 — 과실 물리 위치와 화면 위치 분리 (2026-10-08)

사용자 관찰이 맞았다. PhysX 위치·접촉·적재 로그만으로 화면에서도 과실이 운반됐다고 해석한 것은 불충분했다. 기존 사용자 시험 session `0c9d75093bfd4db88b4ac44815d8c56d`, job `dc6c9eb2c5d746de9d20172e84210470`는 Bed07/Pepper0017 yellow의 내부 적재 SUCCESS와 safe_stopped=true를 기록했지만, 이것은 화면 표시까지 검증한 성공이 아니다.

원인은 과실의 초기 배치와 kinematic 고정 코드가 작성한 사용자 정의 matrix 변환(`xformOp:transform:teacherFruit`, `xformOp:transform:fruitFreeze`)이었다. 동적 전환 후 PhysX tensor 위치는 움직였지만 USD/Fabric의 과실 root와 Visual/Part_0 위치는 초기 위치에 머물렀다. 따라서 내부 성공 판정과 사용자가 본 정지 과실이 동시에 발생할 수 있었다.

`farm_sim_devices/fruit_pose.py`에 표준 translate/orient/scale 작성 함수를 추가하고 `fruit_attachment.py`의 고정 처리와 `fruit_asset_setup.py`의 초기 배치에 적용했다. 기존 로컬 pose/scale을 보존하며 렌더 경로가 갱신할 수 있는 변환을 사용한다. 원본 맵, 마찰·질량·정책·성공 기준은 이번에 변경하지 않았다.

실제 Isaac GUI의 독립 통제 시험에서 같은 과실을 분리하고 물리 위치를 0.4m 이동시킨 뒤 낙하시키며 PhysX/렌더 root/표시 mesh 위치를 동시 기록했다. 이는 동기화 재현용 강제 이동이며 수확 성공 시험이 아니다. 이동 직후 경계를 제외한 23개 sample에서 수정 전 최대 오차 0.550647m, 수정 후 root 오차0m·표시 mesh 최대0.000590m였다. 최종 반복은5초/300render frame/1763physics tick, 프로세스 종료0. 앞선 임시 probe 세 개는 결과 저장·Kit shutdown 후 Python이 남아 해당 프로세스만 정리했고, 최종 probe는 정식 CLI와 같은 종료 처리를 사용했다.

검사43개 PASS: 과실 설정4, 표준 pose2, 활성화·영역·주기·inspector37. 일반 시험 GUI도 새로 실행해 배치, 주변5과실480Hz 관찰,60Hz 복귀 및 화면을 확인했다. 최종 창에는 강제 이동/분리 시험을 적용하지 않았으며 이번 수정 후 전체 파지→운반→적재 수확은 아직 재검증하지 않았다.

근거: `sim/runs/fruit_render_sync_20261008/`의 `comparison.json`, `poses*.jsonl`, `probe_verified.log`, 검사 로그와 `final_gui.png`, `final_gui.log`. 이전 로그는 보존했다. 최종 GUI에서 배치/수확으로 다시 관찰할 수 있다.

전달 파일은 `sim/runs/fruit_render_sync_20261008/changed_files.tar.gz`이며 이번 코드·검사·문서9개 현재본을 담는다. 해당 파일에 있던 이전 미커밋 변경도 현재본에 포함되므로 다른 작업본에 덮어쓸 때 비교한다.

```bash
tar -xzf ~/main/farm_project/sim/runs/fruit_render_sync_20261008/changed_files.tar.gz -C ~/main/farm_project
```

복원은 보관한 `fruit_attachment.before.py`, `fruit_asset_setup.before.py`와 이번 pose 함수·검사 차이만 비교 적용한다. 전체 작업폴더 reset은 하지 않는다. main/450bf5f 이후 미커밋 변경 보존, 커밋·푸시·외부발송 없음.
