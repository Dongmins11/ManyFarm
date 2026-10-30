# 선별장 이탈 회전 중단 원인 조사 — 2026-10-29

## 결론과 확정 수준

원래 중단은 `CLEARANCE_FAILED / Distance exit rotation position drift`다. 회전 중 평행 이동 5cm 제한을 넘었다. 바퀴 odom 5.122cm와 USD 실제 위치 5.237cm가 함께 변했으므로 AMCL 표시만 틀린 문제가 아니다. 105 및 시간 초과도 아니다.

운송 USD 상부 뚜껑의 이동 제한이 원본 URDF와 일치하지 않는 결함을 확인했다. 별도 시험에서 뚜껑-온실 외벽 접촉도 직접 기록했다. 원래 운송 명령을 재생하자 비정상적으로 이탈한 뚜껑이 선별장 구조물/팔 베이스에 접촉하면서 회전 정체·후진 밀림이 재현됐다. 따라서 **시뮬 뚜껑 관절 결함에 따른 접촉이 가장 유력한 원인**이다. 원래 실패 당시에는 접촉/뚜껑 기록이 없고 재생에서는 3.23cm 밀린 뒤 원본 명령이 끝났으므로, 정확한 5cm 액션 실패 재현 또는 수정 전후 인과 검증 완료와는 구분한다.

## 원래 실행 경로와 로그

- 실행: `sim/runs/transport_full_resume_20261029_attempt01/`
- drive session: `e9e295d160894efaa372b3a4489a3f95`.
- 공통 `robot/ros_ws/src/farm_docking/farm_docking/precision_server.py`: `prepare_distance_exit()`에서 시작 odom 위치를 저장하고, `run_distance_exit()`에서 시작점 대비 거리를 `max_translation_m`와 비교한다.
- 회전 시작: 실제시각 1793276600.185854, sim 약519.117초. 위치 (-6.99470, 13.25913), yaw 1.74868rad.
- sim523.967초: 회전 명령 -0.3rad/s, 실제 각속도 -0.262rad/s, 위치 변화 약2.86mm.
- sim525.183초: 같은 회전 명령인데 양 바퀴 실제 속도가 모두 음수로 바뀌고 회전이 거의 멈춘다. 이후 뒤로 밀린다.
- 실제시각1793276622.076047: odom51.22mm, 실제52.37mm로 실패. 선별 시작/운송 복귀/수확 복귀는 이 실행에서 진행되지 않았다.

## 확인된 모델 차이

| 항목 | URDF | 실행 USD |
|---|---|---|
| top_lid_left/right_joint | prismatic | PhysicsPrismaticJoint |
| 직선 이동 범위 | 0 ~ 0.155m | -1.776169 ~ 10.657014m |
| 연동 | lid_pinion_joint ×0.05 | PhysxMimicJointAPI:rotY, gearing -0.05 |
| 선형 drive | URDF mimic 사용 | authored linear drive 없음 |

- 자산 파일 단독 metadata는 metersPerUnit=0.01이다. 그러나 run_fleet는 1m 농장 stage에 AddReference하고 World(stage_units_in_meters=1)로 실행한다. 1m stage 합성에서도 관절 제한 수치는 그대로다. 자산 단독 단위와 실행 stage 단위를 구분해야 하며, 런타임 관절 위치와 실제 뚜껑 프레임 변위도 함께 확인했다.
- 범위 차이는 확정이다. mimic의 rotY 축 지정과 부호가 런타임에서 어떤 방식으로 평가되는지는 추가 점검 대상이며, API 이름만으로 단독 원인을 단정하지 않는다.
- 자산: `sim/assets/robots/transport_robot/urdf/transport_robot.portable/transport_robot.sim.usda`, 실제 관절 설정 하위 레이어 `configuration/transport_robot.portable_physics.usd`.
- URDF: `sim/assets/robots/transport_robot/urdf/transport_robot.urdf`.
- 물리 USD의 Git 기록은 초기 커밋 `275b486`(2026-09-29)까지 이어진다. 이번 도킹 시계 변경으로 새로 만든 관절 설정이 아니다.
- 원본 바구니 형상·USD·공통 제어·5cm 판정은 이번 조사에서 수정하지 않았다.

## 직접 실행한 재현 시험

| 시험 | 결과 | 의미/제약 |
|---|---|---|
| at_exit: 실패 회전 시작 좌표에서 0,-0.3 회전 | 정상 회전, 최종 이동 약6.72mm | 같은 위치만으로 실패 재현 안 됨. 설치 모듈 반영 누락으로 이 실행에는 접촉 기록 없음 |
| reverse_then_rotate | 초기화 실패 | HOME 전 선별 팔과 side_lid 접촉으로 시작 위치 검증 실패. 원래 회전 실패의 재현으로 세지 않음 |
| sorter_sequence | 준비 실패 | 이전 진단 UDP 수신기 잔류로 포트17621 충돌. 원래 액션 실패와 별개, 정리 후 재실행 |
| sorter_sequence02: 도킹→투입→이격/회전→선별→복귀 | 액션 성공 | 원래 회전 중단은 미재현. 2개 투입 중 빨강1개 선별, 노랑1개 남음. 전체 10개 사이클 성공으로 해석하지 않음 |
| full_command_replay | 아래 최종 재생 결과 참고 | 원래 운송 명령을 sim시각 기준 재생. 공통 액션/위치 피드백 없이 운송 단독 실행, 원래 적재 상태 미복원 |

`sorter_sequence02` 접촉 로그는 `bc6ce3a4b1834ec1bc86a9e50439cd05/transport_01_contacts.jsonl`이다. 상부 오른쪽 뚜껑과 `/World/farm_framechanged/Cover_Side_soft_film__1/...` 접촉을 확인했다. 최대 개별 충격량 약0.0432N·s. 접촉 보고 중 충격량0인 근접 항목도 있어 모든 보고를 충돌력으로 세지 않았다. 이 실행은 접촉했지만 출구 회전이 성공했으므로 접촉 사실만으로 원래 실패 원인을 확정할 수 없다.

## 조사 변경과 재현 조건

- 기준 HEAD: `18d0e000d4c98e3478e0a8510d84948561fc7d5f`, 기존 미커밋 수정 유지. 원격 조회/커밋/푸시 미수행.
- ROS Domain13 / SUBNET, CPU 물리60Hz / 렌더30Hz. 명령 재생은 센서 일부 비활성, realtime=false이므로 정상 ROS E2E 결과와 구분한다.
- `drive_diagnostics.py`: 명시적 진단 모드에서만 접촉쌍/충격량, 전체 관절 위치 추가 기록. 휠 제한값도 setup에 기록.
- `run_sorter_cycle_trial.py`: `--contact-trace` 옵션으로 생성된 시험 설정에만 진단 기록 활성화. 이 파일의 기존 주행 progress 설정 변경은 이전 작업이다.
- `sim/tools/probe_exit_rotation.py`: 독립 시험용 UDP 회전/명령 재생. `inspect_transport_lid.py`: USD/URDF 읽기 전용 비교.
- `farm_sim_runtime` 빌드 완료 후 실제 접촉/관절 기록 확인. 최초 at_exit 실행은 설치된 이전 모듈이라 접촉 기록 미포함; 이후 시험과 구분한다.
- 승인 근거: 사용자 문제 확인 요청에 따른 시뮬 진단. 실물 코드 추가 변경 없음.
- 복원: 진단 옵션을 생략하면 기존 기록/동작 유지. 이번 접촉 기록 블록과 도구만 제거할 수 있으며 기존 도킹 수정은 보존한다.

## 다음 조치

주행 판정 완화보다 먼저 시뮬 뚜껑 관절 제한과 pinion 연동을 URDF 설계에 맞게 복원하는 것이 타당하다. 형상은 유지한다. 수정 전후 같은 장시간 주행→도킹→이탈을 비교해 뚜껑 이탈·외벽 접촉·회전 밀림이 사라지는지 확인해야 한다. 아직 그 수정이나 해결 완료를 주장하지 않는다.

## 최종 명령 재생 결과

- session `c2b9ffe532bd431299ba3a8450c4f9ff`, sim542초 종료. 드라이버 sim540.017초 정상 완료, Isaac/clock relay 종료 확인. 원래 명령 시각에 +3초를 더해 재생했다.
- 전체 주행 중 뚜껑 프레임과 cargo_box 프레임 사이 실제 최대 변위: 왼쪽0.61645m / 오른쪽3.29591m. 관절 position 숫자만이 아니라 USD world frame으로 확인했다.
- 회전 시작 sim522.1초 위치(-6.96072,13.25564), yaw1.70399. 원래 시작보다 약3.4cm/2.56도 다르므로 완전 동일한 닫힌루프 재현이 아니다.
- sim527.967초: yaw0.35345, 바퀴(+1.09265,-1.11869)rad/s로 정상 회전.
- sim528.667초부터 오른쪽 뚜껑-선별장 Controller 접촉. sim529.350초 왼쪽 뚜껑-팔 tool 접촉. sim529.417초 오른쪽 뚜껑-RearFoamWall 접촉, sim530.117초 오른쪽 뚜껑-팔 base 접촉.
- sim530초: 명령은 여전히(0,-0.3)이지만 yaw -0.01204, 바퀴(+0.02395,-0.29025)로 저하. sim533.967초에는 바퀴(-0.14208,-0.17044), yaw -0.03346으로 회전은 거의 멈추고 뒤로 밀림.
- sim535.983초에는 원본 기록의 정지 명령이 재생되어 종료. 회전 시작 대비 실제32.30mm 이동. 해당 명령 재생에는 공통 액션 서버가 없으며 원래5cm 오류를 발생시킨 시험이 아니다.
- 접촉 충격량 최대: 오른쪽 뚜껑-RearFoamWall0.09146N·s, 오른쪽 뚜껑-팔 base0.04669N·s. 근접 보고가 아닌 0보다 큰 충격량을 기록했다.
- 원래 실패와 회전 정체/바퀴 후진 양상이 같고 접촉 시각도 일치한다. 단, 뚜껑 수정 후 동일 조건 대조시험은 미실행이다.
- 증거: `sim/docs/test_results/20261029_sorter_exit_diagnosis/`의 원본/재생 drive, 실제 충격 접촉, 자산 비교, 설정, 요약, 소스 SHA256. 원본 전체 로그는 `sim/runs/sorter_exit_diagnosis_20261029/`와 각 drive session 아래 유지.
- 문법 검사 및 git diff --check 통과. 이번 수정은 진단 기록만이며 뚜껑 결함 수정·공통 동작 변경·커밋·푸시는 하지 않았다.
