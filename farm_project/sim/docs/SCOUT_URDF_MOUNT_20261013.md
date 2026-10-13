# USD 연결 추가 — 2026-10-13 후속 요청

사용자 “usd까지 반영한다음 커밋푸쉬해”로 URDF 수정본과 USD 연결의 main 반영 승인.
아래 기존 URDF 전달 단계의 “USD 연결 미완료”는 당시 상태다. 이 절이 최신 상태를 나타낸다.

- 추가 자산: `sim/assets/robots/scout_robot/scout_mount_20261013.usda`. 기구/센서 좌표를 URDF에서 생성한 독립 텍스트 USD 레이어다. 해당 파일만 하위 .gitattributes에서 일반 Git 추적하고 기존 바이너리 LFS 규칙은 유지한다.
- `scout.json`/`scout_fleet.json`의 `scout_mount_asset`으로 선택한다. `scout_mount.py`가 기존 base_link 아래 참조를 장착하고 base_footprint와의 실제 변환을 사용한다. `run_sim.py`와 `run_fleet.py`에서 센서 TF 산출 전에 적용한다.
- 기존 D435 Camera prim의 위치/회전만 재설정한다. focal length, aperture, clipping, 해상도/FPS/K/D는 유지한다. USD -Z 시선과 ROS optical +Z 축 변환을 반영한다.
- 기존 camera_optical_frame 계약을 유지하며 PDF의 body/color optical 및 파이캠 TF 4개를 함께 발행한다. 파이캠은 외형·TF만 추가하며 영상 스트리밍은 활성화하지 않는다.
- 기둥 외곽 collision은 기존 base_link 강체에 붙인다. 새 rigid body, joint, mass/inertia는 만들지 않는다. 기둥 질량/무게중심은 반영되지 않은 모델이다. 상판·홀더·카메라는 근사 visual이다.
- 원본 `scout_robot_camera_fixed.usd` 및 농장 USD 바이너리를 다시 저장한 것은 아니다. 기존 프로젝트의 세션 레이어 적용 방식으로 연결한다. **USD 파일만 단독으로 열 때가 아니라 sim 런타임 시작 시 적용된다.**

직접 검증: OpenUSD 26.8로 독립 합성 stage에서 테스트 4개 PASS. 회전·이동한 로봇, lens XYZ/시선, 파이캠, 본체 이동 추종, 반복 적용, 세션 한정 변경, 광학값/질량 보존, 비활성 카메라 오류를 검사했다. 최초 비활성 prim 검사 실패를 IsActive 확인으로 수정 후 재실행 통과. Python 구문 검사 PASS. URDF 394 assertion PASS는 앞선 직접 검사 기록이다.

미검증: 기준 원격의 원본 USD는 LFS 포인터만 읽었다. 실제 binary fetch는404로 실패하여 원본 농장 합성·기존 외형 중복/간섭·Isaac5.1/PhysX/렌더·ROS DDS·Nav2 주행·실물은 확인하지 못했다. 독립 stage 검사 성공을 실제 농장 성공으로 해석하지 않는다. 기존 자산의 별도 기둥/카메라 외형이 있으면 실제 stage에서 확인 후 중복을 정리해야 한다.

로컬 반영: 실행 중인 sim을 종료하고 원격 변경을 로컬 작업과 병합한 뒤 기존 sim 빌드·launch 절차로 재시작한다. 사용자가 앞서 URDF 패치를 적용했다면 해당 로컬 변경을 보존·대조하고 병합한다. 자동 reset/덮어쓰기는 금지한다. 실제 확인 후 PROJECT_STATE 검증 항목을 갱신한다.

검사 명령(usd-core와 numpy가 있는 Python):
```bash
python3 sim/tests/test_scout_mount_usd.py
python3 sim/tools/build_scout_mount_usd.py --project-root "$PWD"
```

복원: scout 두 JSON의 scout_mount_asset을 제거하고 재시작하면 이번 런타임 적용과 추가 TF가 비활성화된다. 세션 변경이므로 기존 USD 원본에는 쓰지 않는다. 원격 전체 복원은 작업 커밋 revert로 하되 다른 로컬 변경을 보존한다.

---

# Scout URDF 장착 수정 — 2026-10-13

기준 저장소 Robot3FinalProject/main, 브랜치 main, 커밋 a393f1a9dd73052f601abd23f5901dbacdcbde9e.
근거: 사용자 첨부 「예찰로봇 부품 치수와 변경 관리 — TurtleBot3 Burger」(2026-10-09 기준, 10-13 PDF 내보내기).
승인: “이거 확인해서 scout robot urdf 수정해줘” 및 후속 PDF 제공.

## 변경과 정확도

- sim/assets/robots/scout_robot/urdf/turtlebot3_burger.urdf 및 portable.urdf에 동일 장착 구조를 추가했다. 기존 본체·바퀴·캐스터·IMU·라이다 노드와 물성은 유지한다.
- 판 중심 지면 기준 (-0.032,0,0), 기둥 바닥 Z0.200/상단 Z0.620m. 기둥 외곽 0.05×0.05×0.42m의 visual/collision. 속빈 관 질량·관성은 미측정이므로 생성하지 않았다.
- D435 렌즈 위치는 base_footprint 기준 (-0.049,+0.055,0.595)m, body RPY=(0,π/180,π/2). 기둥 상단보다 25mm 낮다. pitch1도/roll0은 C(잠정)다.
- 파이캠은 (-0.032,+0.063,0.117)m, body RPY=(0,0,π/2). 판 중심 X0은 C값이다. 두 optical 회전은 body 기준 (-π/2,0,-π/2).
- PDF 프레임 bmany_camera_link/camera_color_optical_frame/picam_frame/picam_optical_frame을 추가하고 기존 sim 명명과 비교 가능한 camera_optical_frame identity alias를 둔다. 외부 static TF와 동시에 발행하면 중복이므로 로컬 연결 시 확인한다.
- 연결봉 6개 축·길이39.5mm·중심Z171.25mm를 반영했다. 육각봉은 외접 원통 시각화다.
- 추가 상판은 137.55×137.55×9mm 외곽 상자 시각화, DUX는 137mm 길이·3mm 두께·높이50mm 교차판 시각화다. 상세 CAD/홀은 제공되지 않았다. 이 근사 부품들과 카메라에는 collision을 추가하지 않았다. 상판 사각 외곽은 실제 깎인 모서리와 다르므로 PDF의 최대반경109.02mm 검증에 사용할 수 없다.
- 카메라 외형은 렌즈 뒤에 둔 개략 상자다. 하우징 중심까지의 정확한 변환은 알 수 없다. D435 상단 마운트는 변환 미정이라 제외했다.

## 적용 범위와 남은 작업

이번 결과는 URDF 파일 수정본과 정적 검증이다. 사용자 PC 파일·실물에 적용하지 않았으며 commit/push하지 않았다.
현재 scout.json/scout_fleet.json은 농장 USD 안의 /World/scout_robot_camera_fixed와 base_link/scout_camera를 사용한다. **이 URDF 변경만으로 기존 Isaac USD와 실행 카메라가 바뀌지 않는다.** USD 재임포트 또는 세션 override 연결·ROS TF 검증은 로컬 Codex 후속 작업이다. 기존 농장 전체를 재임포트해 바퀴/캐스터 물성을 덮어쓰지 않는다.

로컬 Codex 인계:
1. 로컬 HEAD·미커밋 변경을 먼저 확인한다. PDF에 등장한 robot/models/scout/description 및 devices.json의 최신 PC 버전은 원격 기준에서 확인되지 않았다. 그 실물 장착 모델/CAD가 있다면 근사 외형 대신 재사용한다.
2. 기존 USD의 base_link 높이·회전을 확인한 뒤 D435 base_footprint→lens를 환산한다. base_link가 Z0.010m이면 상대 XYZ=(-0.049,0.055,0.585)m이다. USD 카메라 축과 ROS optical 축 변환을 적용한다.
3. sim USD/센서 장착을 같은 기준으로 연결하고 시각화·TF·센서 영상·라이다 간섭을 확인한다. 해상도/FPS/내부 파라미터·왜곡·깊이 스케일을 이 치수 변경 때문에 바꾸지 않는다.
4. 경로 기준 화단 거리1.14m에서 카메라55mm를 다시 차감하지 않는다. Nav2 반경0.11m는 실물 문서값이며 이 근사 외형에서 검증된 값이 아니다. 실제 CAD/배선 포함 외곽과 함께 별도 확인한다.
5. 질량·관성 자료 확보 전 Isaac importer 기본 질량을 실측 물성으로 취급하지 않는다. 높은 기둥의 동역학·주행 안정성은 미검증이다.
6. portable URDF의 기존 meshes/wheels/left_tire.stl 및 right_tire.stl 참조는 기준 Git 트리에 실파일이 없다. 원본 Burger 메시를 로컬에서 확보해야 한다. transport의 동명 파일로 대체하지 않았다.

## 검증

XML 파싱, 링크 이름 고유성, 단일 부모/연결 트리, 기존 노드 불변, 두 변형의 장착 일치, 렌즈 TF·광학 방향·기둥 높이·봉 치수를 Python으로 직접 검사했다. 상세 결과는 SCOUT_URDF_VALIDATION_20261013.json.
ROS check_urdf/xacro 실행, RViz, Isaac import/물리/영상, 실물 검증은 실행하지 않았다.

## 적용과 복원

압축 파일은 패치와 이 안내를 담는다. 프로젝트에 직접 수정 파일을 덮어쓰지 않고 git apply --check 성공 후 적용한다. 로컬 변경과 충돌하면 중단하고 Codex로 병합한다.
복원은 같은 패치에 git apply -R --check 후 git apply -R을 사용한다. 새 문서/URDF를 작업 후 다시 수정했다면 역적용 충돌도 먼저 해결한다. 기존 사용자 파일을 reset/clean하지 않는다.
