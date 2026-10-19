# harvest_robot

현재 v2는 `grasp → hold → pull → harvest` 네 단계다. `run.py train --task hold` 및
`run.py train --task pull`로 중간 과제를 실행한다. 최신 실행 순서·물성 가정·단일→다중 확장은
[v2 로드맵](../../docs/manipulation/HARVEST_RL_ROADMAP_KR.md)을 따른다.
v1 checkpoint는 호환되지 않는다. 고무 패드 마찰 1.0/1.0과 파지 preload 유지 제어를 사용한다.
이전 PLA v2 checkpoint는 명시적 warm-start와 마찰 변경으로 가져올 수 있다. 물리 gate의 검증 범위는 검증 기록을 확인한다.

오른쪽 SO-ARM101(`arm_2`)의 파프리카 수확 강화학습 구현이다.
전체 Vic Pinky·고정 프레임·양팔·박스를 보존하고, 이동 베이스·왼팔·박스 바닥은 고정한다.

- `train_grasp.py`: 접근 → 양쪽 손가락 접촉 → 파지 유지, Teacher PPO
- `train_harvest.py`: 접근 → 파지 → 당김 분리 → 박스에 놓기, Teacher PPO
- `run.py`: smoke / train / play / student-train / student-play
- `prepare.py`: 원본을 수정하지 않고 파생 URDF·USD·도달 후보 생성
- `physics_probe.py`: 손가락 접촉·당김·박스 안착을 검사하는 별도 물리 fixture
- `gripper_report.py`: 원본 STL 삼각형 기반 파지 여유 측정
- `harvest_rl/`: 환경·물리·관측/보상·Teacher/Student 정책
- `tests/`: Isaac 없이 실행할 수 있는 단위 테스트

설치 환경, 복사 가능한 실행 명령, 수식과 코드 읽는 순서는
[강화학습 학습 자료](../../docs/manipulation/HARVEST_RL_GUIDE_KR.md)를 참고한다.

현재는 학습 가능한 구현과 짧은 실행 검증 단계다. 성공률이 검증된 수확 정책이나 실물 제어기는 아니다.
ROS 2 런타임 어댑터·실물 안전 제어는 아직 포함하지 않는다.
