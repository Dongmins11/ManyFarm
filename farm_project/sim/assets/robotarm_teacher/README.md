# 60Hz Teacher r2 실행 자산

원본: `robotarm_teacher_60hz/harvest_teacher_60hz_20261013_r2.tar.gz` (저장소 루트 기준).
압축 SHA256: `5149682ac79ee6ea7f1ee7e2273bf1898c6645fc2da21a83efe55c30cff16752`.

- `DEPLOYMENT.json`: 전달 실행 설정 원본. 물리60Hz / 정책20Hz / 렌더30Hz.
- `actors/`: 정규화가 포함된82입력 TorchScript. grasp/pull 학습 정책과 transport_reference.
- `harvest_training.urdf`: Cartesian 제어기의 FK/Jacobian용 전달 URDF. 메시 로딩용이 아니다.
- 정책 이외에 `_teacher_vendor/`의 원본 단계 제어와 농장 measured-state 어댑터가 필요하다.
  운반은 Cartesian 최종 명령, 정지·놓기는 별도 제어기다. Student가 아니다.
- `sim/tools/import_teacher60.py <압축해제된 manyfarm_robotarm 경로>`가 원본 계산 메서드와 필수 도우미를 가져온다.
  생성/리셋/렌더/학습·보상 실행은 제외하며 `PROVENANCE.json`에 원본 SHA와 추출 목록을 남긴다.
- 과실 연결은 response6 힘·토크 모델이며 fixed joint나 그리퍼 부착이 아니다.25mm 인장/40mm 전체 변위 등 유지 조건으로 분리된다.
  2.5N·60~80mm 실측 일치 모델 또는6Hz 모델로 해석하지 않는다.

이전480Hz entry/pull/transport/place 체크포인트와 실행 코드는 제거했다. 모델 SHA는 로드 전에 검사하고,
작업 로그에 DEPLOYMENT/URDF/actor SHA를 기록한다. 농장·실물·Student 성능은 독립26/32 결과와 구분한다.
