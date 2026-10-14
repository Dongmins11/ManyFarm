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
