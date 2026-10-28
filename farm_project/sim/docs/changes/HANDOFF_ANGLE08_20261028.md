# 시뮬 인계 벽 정렬 허용각 0.8° 임시 적용 — 2026-10-28

## 승인과 변경 범위

사용자: “시뮬레이션에서는 임시로 완료조건을 0.8도정도로 놓고 해봐”. 시뮬 인계 실행 묶음을 생성하는 `sim/tools/prepare_harvest_handoff.py`에서 실물 wall_config를 읽은 후 실행 복사본의 `controller.angle_tolerance`만 0.008726646259971648rad(0.5°) → 0.013962634015954637rad(0.8°)로 변경한다. 원본 실물 파일은 수정하지 않는다. 준비 도구로 이후 생성하는 시뮬 인계 묶음에 적용되며 이미 생성된 과거 실행 폴더는 변경하지 않는다.

- WallController/WallGoalChecker는 동일 `wall_alignment.angle_tolerance`를 사용한다.
- HandoffRuntime은 같은 wall_config를 서버 구성과 HandoffPlanner에 넘기며 최종 validator도 같은 값을 사용한다. 최종 검사만 별도로 완화하지 않는다.
- 거리43.25±0.5cm, dwell0.5초, 후단 정지0.8초, 속도/시간/원호/복원 허용치, 바구니 판정은 그대로다. 물리 solver4회·기존 damping·타이어·CPU60Hz도 그대로다.
- `source_adaptations.json`과 `fixture.json`에 원본/적용값·단위·임시 시뮬 예외·사용자 승인 근거를 기록한다. run_handoff_window_trial.py는 생성된 numeric_handoff_changes를 시험 fixture에도 전달한다.
- 기준 main ea25693 + 기존 미커밋 통합. 공통 코드/실물 설정 수정 및 커밋·푸시는 하지 않는다.

## 확인

- 변경 도구 2개 py_compile 통과.
- 생성 wall JSON과 실물 원본 비교: angle_tolerance 한 필드 외 동일, 실물0.5° 유지.
- 실행 ROS `/harvest_01/handoff/controller_server`의 `wall_alignment.angle_tolerance` 조회: 0.013962634015954637.
- 실제 시험: Domain13/SUBNET, headless CPU60Hz, 기존 SEC01 첫 윈도우 데이터 재사용. 전체SEC/새 예찰/선별장/스테이션 복귀가 아닌 수확 윈도우→운송접근→도킹→정렬 유지 기반 가상 인계→복원 시험이다.
- 로그: `sim/runs/handoff_angle08_20261028/attempt1/`.

## 복원과 자료

임시 완화를 되돌릴 때 prepare_harvest_handoff.py의 시뮬 angle_tolerance 덮어쓰기를 제거하고 실행 묶음을 새로 생성한다. 기존 실행 기록은 보존한다. 원본 실물 config를 복원할 작업은 없다.

```bash
unzip -o "$HOME/Downloads/handoff_angle08_changes.zip" -d /home/ysy/main/farm_project
```

## 실제 시험 결과

KST 17:20:14~17:22:55, 1회. **벽 정렬 및 정지 후 최종 검사 통과, 운송 도킹·가상 인계·이격 성공. 전체 인계 복원은 실패.**

- 수확 윈도우 SUCCESS, expected1/harvested0 (`student_no_reachable_targets_arms_stowed`). 실제 과실을 옮겼다는 의미가 아니다.
- DOCK_READY, DOCK_STABLE, TRANSFER_COMPLETE, TRANSPORT_CLEAR 실제 피드백 및 관제 이벤트 접수 확인.
- 운송 TransportPickup: SUCCESS. 수확 DockTransfer: transfer_complete=true, transport_clear=true, restore_complete=false.
- 수확 실패: `restore: WINDOW_REALIGN_REQUIRED: 짧은 전진으로 window 완료범위 확보 불가 (전방=-0.1139m, 횡오차=-0.0420m)`. 최종 위치 추정상 목표가 뒤쪽11.39cm/횡4.20cm에 있어 짧은 전진 보정으로 완료할 수 없다는 판정이다. 실제 USD 위치와 대조하지 않았으므로 실제 물리 변위라고 단정하지 않는다. 이전에도 있었던 별도 복원 오류이며 0.8° 변경과의 인과관계는 미확정이다.
- 이번 벽 각도 초과/운송 LEASE_EXPIRED/105는 관측되지 않았다. 1회 통과이므로 간헐적 벽 정렬 실패가 완전히 해결됐다고 선언하지 않는다.
- 공유 결과: sim/docs/test_results/20261028_handoff_angle08/. 원본 실물 wall 파일 SHA-256은 시험 전후 동일.
- 다음 확인 대상은 최종 복원 시점의 map/odom/USD 위치 차이와 WINDOW_REALIGN_REQUIRED 판정이다. 이번 요청 범위를 넘어 복원 조건을 완화하거나 공통 코드를 수정하지 않았다.

## 후속 분석 — WINDOW_REALIGN_REQUIRED 이력과 이번 실제 위치 대조

사용자 “이건또뭐야 언제생겼고 뭐가문제야”에 따른 읽기 분석이다. 동작 변경/추가 시뮬 실행은 없다.

- 도입 커밋 cf870da, Hyaline-52, 2026-10-23 21:39 KST, `fix(harvest): 실기 검증한 인계 통합 및 일반 주행 복귀 반영`. 실물 담당 브랜치에서 들어온 공통 수확 인계 코드다. 현재 handoff_window.py는 인수 기준e135cde와 byte 동일하다. 이번0.8°변경이 추가한 예외가 아니다.
- 48d2d1c(10/27 15:32 KST)는 복원 허용치를5cm·6°로 조정했다. 현재 실행에도 반영돼 있다. 이전10/28 pickup9에서도 같은 오류가 관측됐다.
- 최종 plan_window는 map 위치가 목표 반경5cm 안이면 완료 확인으로 넘어간다. 밖이면 전방3mm초과~6cm이하·횡오차1.5cm이하의 짧은 전진 보정만 허용한다. 후진/큰횡이동을 요구하면 해당 예외를 낸다. 역원호 복귀 자체의 성공과 최종 map 윈도우 위치 검사는 다르다.
- 이번 최종 결과시각17:22:55.961 근처 외부 odom 수신차이는 -0.761ms. odom시뮬시각136.583340457초와 USD진단시각136.5833404567초를 맞췄고 직전 수신map→odom을 조합했다. 실제기준 map/world 변환은 station 설정 기본 단위행렬이다.
- 추정 위치(-5.97328,9.17853), 실제USD(-6.01356,9.27900). 위치추정-실제 차이는X+4.03cm/Y-10.05cm, 평면약10.82cm.
- 목표윈도우까지 추정거리는12.14cm(전방-11.391cm/횡-4.195cm)로 오류 메시지와 일치한다. 실제목표거리는1.360cm, 방향오차0.074°라 현재5cm/6° 범위 안이다.
- 따라서 이번 실패의 직접 원인은 큰 실제복귀변위보다 **map 위치추정 불일치**다. 단순0.2°정지회전과 별개이다. 이 재구성은 내부validator표본직접기록이 아니라 외부동시로그대조라는 한계가 있다.
- 지도 추정오차가 어느 라이다 관측/AMCL갱신에서 누적됐는지는 이번 계산으로 확정하지 않았다. 이전 긴베드에서 관측된 위치추정문제와 같은 유형이며, 후속은 인계 전후map→odom보정추이를 확인하는 것. 실물에서도 같은조건이면 공통예외는 발생할 수 있지만 실물재현은 확인되지 않았다.
- 근거 JSON: test_results/20261028_handoff_angle08/restore_position_reconstruction.json. 보고서 이전 항목의 “USD미대조”는 이 후속 분석으로 보완됐다.

## 후속 분석 — 불일치가 커진 시점과 과거 크기 비교

- 사용자 “왜 불일치야? 저렇게 크게 불일치된적이 있었나?” 요청. 저장 로그 분석만 수행, 설정/공통코드/추가실험 변경 없음.
- 동일시각 USD와 초기 자세에 정합한 바퀴odom 비교: 전체 최대 평면오차4.62mm. 초기정합에 실제자세를 사용한 것은 오프라인 평가뿐이며 제어에 주입하지 않았다.
- map/odom 조합 추정 오차: sim20초약0.78cm →60초약3.01cm →100초약3.07cm →120초약4.31cm →130초약6.83cm →최종136.58초10.82cm. 복귀회전 후반에 증가했다.
- AMCL 직접 출력도 sim129.55초6.80cm →131.75초9.49cm →133.75초10.87cm(가장 가까운USD표본기준)로 증가. 따라서 TF를 나중에 잘못 조합한 설명만으로는 부족하고 AMCL 출력 자체의 오차가 확인된다. 최종AMCL Y표준편차12.31cm는 불확실성이며 실제오차와 구분한다.
- 이전 진단attempt2/3 AMCL 실제오차의 최대 평면거리를 같은 정의로 재계산하면6.16cm/4.80cm. 이전 문서의5.46cm/4.63cm는Y축만의 최대오차다. pickup9 최종Y오차약4.4cm도 이전에 존재했다. 이번10.8cm는 이 최근 비교군보다 크다. 전체과거시험최대값을 조사한 것은 아니므로 최초10cm발생이라고 단정하지 않는다.
- 실물기준AMCL alpha1~5=.2, sigma_hit=.2m, max_beams60, update_min_a=.2rad, update_min_d=.05m. 긴반복베드에서 진행방향관측제약이 약하고 회전중분포가 충분히수렴하지 않는 것이 기존증거에 부합하는 유력설명이다. 이번마지막scan의평면거리장진단점수는실제자세0.98156/추정자세0.95673: 잘못된위치도비교적높은점수. 이점수는전체빔간이진단이며실제AMCL입자/가중치계산이아니므로설정단독원인확정은아니다.
- 움직이는운송로봇의라이다반사,입자샘플링,오차모델각각의기여는아직분리하지못했다. “실물에서도10cm오차발생” 또는 “0.8°변경이원인”으로단정하지않는다.
- 증거 localization_timeline.json 및 amcl_analysis.json. 표본짝짓기차이: 직접AMCL평가최근접USD최대60ms허용, 이전분석기는USD선형보간이므로최종오차가약0.02cm다를수있다. 실제오차의단위와정의를맞춰비교한다.
