# U20 손목 카메라 농장 연결 — 2026-10-30

## 요청과 적용 상태

사용자: 실물이 현재 U20으로 수확하므로 시뮬도 U20으로 맞춘다. 바구니 카메라 검사는 제외하고 레이저 집계를 유지한다. 앞선 팔 복귀·영상 처리 최적화 요청도 함께 반영했다.

기준 HEAD `18d0e000d4c98e3478e0a8510d84948561fc7d5f`, main의 기존 미커밋 변경 위에 적용. 공통/실물 소스는 이번 작업에서 수정하지 않았다. 커밋·푸시하지 않았다.

기본 설정·코드·설치본 반영 완료. 진행 중인 9차 D435 시험은 중단하지 않았다. 다음 시뮬 실행부터 U20이다. **실제 Isaac 렌더링·U20 농장 수확 성공은 아직 검증 전이다.** 기존 시험이 성공해 자동 반복이 종료되면 U20 시험을 별도로 시작해야 한다.

## 전달본 보존과 변경

| 항목 | 적용 |
|---|---|
| 모델 | 기존 전달 `handoff/models/u20_student.pt`, SHA256 `dd1afeaeccce04593c3c97d544834b9e508ced2c2c2f1d8197994183b68abf1e`. 가중치 변경 없음 |
| 손목 | 전달 U20 URDF의 광학 좌표·내부 파라미터·1920×1080 RGB, 30Hz. 손목 깊이/IR 렌더 및 D435 중심보정 모델 제외 |
| 후방 | 기존 D435 RGB/깊이 및 전달 보정 유지 |
| 정책 | 원본 U20Inference·U20Controller·기존 v20 보조제어, 3프레임 이력·20Hz·실제 명령 ACK 유지 |
| 외형/물리 | 양손 U20 외형, 실제 오른손 pose 추종. 전달 U20 방식대로 기존 학습 물리 유지. 질량/충돌/drive/solver를 새 URDF에서 가져오지 않음 |
| 수확 성공 | 기존 평행 레이저 통과 집계. A5 바구니 카메라/신규 segmentation 모델 미적용 |
| 과실 사이 복귀 | 정상 레이저 확인 후 기존 lift 경로로 HOME·측정 정지, 다음 과실 시작. 마지막 과실만 접힘·최종 정지 |
| 시간초과 | 기존 60시뮬초, 안전 접힘 후 재관측·1회 재시도 유지. 실패 회복 때는 추가 접힘 가능 |
| 실패 | 복귀 경로 거부/실제 정지 불충족/차체 이동 등 기존 액션 실패 의미 유지. 미수확·비대상 이탈은 성능 지표 |
| 영상 처리 | 미검출 프레임은 후속 깊이 투영 생략. 매 프레임 전체 x/y 격자 할당 제거, 결측 픽셀 좌표만 계산. 촬영 시각·깊이·반올림·결측 의미 보존 |

장착값은 전달본의 `nominal_rectified_pinhole_not_measured`, 내부·장착 보정 미검증 상태를 그대로 유지했다. 사용자 확인은 실물의 U20 사용 사실이며, 현장 실측 장착값까지 동일하다고 확인한 것은 아니다. 손목 RGB가 1080p이므로 렌더 스트림 수 감소만으로 전체 속도 향상을 보장하지 않는다.

## 변경 파일

- `sim/ros_ws/src/farm_sim_config/config/{student_policy.json,harvest.json}`: camera=u20, backend=student_u20.
- `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/student_session.py`: 선택 모델/URDF/hash 검증, U20 원본 세션 연결, RGB-only 로그 저장, 정상 과실 사이 HOME 복귀 선택. 기존 차체 이동 진단 수정 보존.
- 같은 폴더 `student_camera.py`: U20 프로파일 검증·양손 외형, RGB-only 촬영. 클래스 이름 FarmD435Rig는 기존 호출 호환을 위해 유지하되 실제 구성은 선택 프로파일에 따른다.
- `sim/ros_ws/src/farm_sim_runtime/farm_sim_runtime/{run_fleet.py,fleet_config.py}`: student_u20 백엔드 및 모든 촬영/성능 기록 경로 연결. camera/backend 불일치 즉시 오류. 기존 student_d435 지원 유지.
- `sim/assets/robotarm_student/manyfarm_robotarm/src/harvest_robot/harvest_runtime/student60_mission.py`: 기본 동작은 보존하고 농장만 stow_between_targets=False. 시간초과 RETURN_STOW를 가로채지 않음.
- 같은 전달 자산 `harvest_sensors/student60_low_latency.py`: 투영 할당·미검출 처리 최적화.
- `sim/tools/check_teacher_action.py`: U20 선택 지원, D435 선택 시 별도 시험 프로파일을 D435로 고정하여 기존 시험 유지.
- `sim/tools/run_single_cycle.py`: 시도별 카메라 설정/코드 출처 추가 기록.
- `sim/tests/test_student_{u20,retry,camera_preprocessing}.py`, `test_harvest_action_config.py`: 입력·좌표·물리 보존·레이저·정상 HOME 복귀·시간초과·실패 회귀 검증.

## 직접 검증

`sim/docs/test_results/20261030_u20_integration/`에 원문 보존.

- `tests.log`: 50개 통과. U20 실가중치 CPU 추론/3-frame history/ACK, U20 sensor FK 변경과 팔·후방 FK 불변, RGB-only 수집/로그 저장/레이저 성공, 정상 2과실 HOME 경유 후 최종 접힘 1회, 중간 HOME 복귀 실패 시 다음 대상 진행 금지, 60초 재시도·미검출 건너뛰기·기존 물리 실패, 깊이 마스크 원본 일치 포함.
- 실제 농장 USD를 메모리에서 구성하고 U20 외형 연결 전후 전체 물리 signature 동일 확인. 새 외형 메시 8개. 기존 자산의 빈 visual 참조 경고 3개가 출력되지만 검사는 통과했다. 렌더/동역학 시험은 아니다.
- `build.log`: farm_sim_config/devices/runtime 3패키지 빌드 성공.
- `installed_sources.json`: 변경 실행 모듈 4개 및 설정 2개 소스/설치본 동일 확인.
- `projection_benchmark.json`: 저장된 후방 480×848 깊이 1프레임과 합성 중앙 마스크, 워밍업 후 교차 순서 20회. 투영+마스크 중앙값 5.254→4.419ms, 마스크 동일. 전체 x/y 배열 6,512,640byte 할당 제거. 결측 좌표에는 필요한 별도 할당이 남는다. 전체 영상 처리/수확 속도 결과가 아니다.
- 변경 대상 파일의 diff 공백 검사 통과. 전체 작업 트리 검사는 기존 운송 USD의 Git LFS 임시 쓰기 권한 문제로 실행하지 못해, 이번 변경 파일만 지정하여 검사했다.

## 다음 실행 확인과 복원

다음 실행에서 `[student_camera] policy: u20`, U20 체크포인트 SHA, `right rgb / rear rgb / rear depth` 초기 렌더, `RETURN_HOME` 및 최종 `RETURN_STOW`, 레이저 집계·타임아웃 재시도를 확인한다. 다음 실행에는 앞서 승인된 일반 주행 0.15 속도 변경도 포함되므로 시도별 설정 로그로 원인을 구분한다.

진단상 이전 카메라 대조가 필요한 경우에만 두 프로파일 값을 camera=d435/backend=student_d435로 함께 변경하고 빌드·다음 실행한다. 사용자 지시상 U20이 운영 기준이므로 문제 발생을 이유로 조용히 D435로 되돌리지 않는다. HOME 최적화는 농장 생성자의 stow_between_targets=True로 개별 대조 가능하다. 전체 파일 되돌리기로 기존 실패 진단·물리·속도 변경을 제거하지 않는다.
