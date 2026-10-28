# HCR 선별장 점유지도 갱신 및 복귀 재시험

2026-10-28 KST. 기준 main ea25693650a9a61d8bbcfcf6e02f6ac6889a97a1 + 기존 미커밋 통합 작업. 사용자 “업데이트해야지 지도도 업데이트해야되고” 승인. 이번 변경은 sim 지도·시험 도구·문서이며 실물/공통 주행 코드·AMCL 수치·성공 판정은 바꾸지 않았다.

## 결과

지도 갱신/실행 연결 완료. 실제 도킹→기존 과실 투입→이격→선별은 성공했으나, 스테이션 복귀는 여전히 위치 추정 오차로 실패했다. 지도 갱신만으로 문제 해결을 선언할 수 없다.

| 항목 | 이전 attempt09 | 갱신 지도 attempt10 |
|---|---:|---:|
| 정지 후 map 위치 추정 오차 | 25.60cm | 20.30cm |
| 같은 시점 바퀴 odom 오차 | 1.40cm | 1.28cm |
| 기존 전면 라이다 351점과 최근접 점유셀 중심 거리 평균 | 16.17cm | 1.45cm |
| 도킹·투입·이격·선별 액션 | 성공 | 성공 |
| 스테이션 복귀 | 실패 | 실패 |

각 1회 비교이며 통계적 개선율로 일반화하지 않는다. AMCL의 확률적 추정과 도킹 소요시간은 서로 다르다. 지도 이외 최종 제어 설정은 동일하다. 추가한 측정 기록은 제어에 사용하지 않는다.

## 지도 변경

- 원본 `count_test_farm_map.yaml/png`를 보존하고 `hcr_farm_map.yaml/png`를 생성했다. 기존 모델을 쓰는 실행은 기존 지도 유지.
- `build_sorter_map.py`가 전달본의 원본 `create_station`을 실제 Isaac USD stage에서 실행한다. 새 형상 수식을 별도 복제하지 않는다.
- 운송 base_scan 장착 높이 0.132m의 고정 충돌 cube 단면을 world 좌표로 구하고, 교차하는 5cm 셀을 점유 처리한다. 얇은 벽도 셀 중심 밖이라는 이유로 사라지지 않는다. 동적 팔·운송로봇·과실은 정적 지도에 넣지 않는다.
- 이전 선별장 ROI X=[−7.45,−6.5], Y=[13.5,14.75]에서 이전 점유 및 내부 unknown127만 제거한다. 이 밖은 새 고정 단면이 겹치는 셀만 추가한다. 해상도 5cm·원점·크기323×603과 기존 외벽/베드/접근 통로 보존.
- 총179셀 변경: 기존 점유→자유31셀, 자유→점유128셀, 기존 unknown20셀 갱신. 변경 셀 중심 범위 X=[−7.55,−6.65], Y=[13.55,14.95].
- `sorter_integration.json`에 지도/제거 ROI/스캔 높이 연결. `run_sorter_cycle_trial.py --sorting`은 실제 station 배치와 원본 형상·기존 지도 해시가 manifest와 일치할 때만 갱신 지도를 선택한다. 원본/배치 변경 시 재생성 요구로 실행 준비 중단.
- 실제 map_server가 `hcr_farm_map.png`를 읽은 로그 확인. 모든 로봇의 기존 전역 기본 지도를 강제 변경한 것은 아니다. 이후 HCR fleet 확장 시 해당 실행에 참여하는 지도 소비자도 같은 환경 지도를 선택해야 한다.

## 남은 오차를 좁힌 근거

이번 기록은 `/transport_01/scan` 1,102개, odom 3,296개, AMCL pose23개, map→odom TF1,098개다.

- AMCL 출력 자체의 오차가 55.55초에8.42cm, 73.85초11.04cm, 회전 중78.65초20.64cm, 마지막84.35초20.31cm였다. 정지 후 새 AMCL pose 갱신 없이 이 값이 유지됐다.
- 마지막 정지 시 `map→odom × odom→base` 합성 위치와 관제 status 위치 차이는 약0.000126cm(1.26µm). 최종20cm가 TF 합성/관제 표시에 새로 생긴 것은 아니다. 이것만으로 이동 중 모든 TF 시각 처리가 정상이라고 일반화하지 않는다.
- 같은 최종 scan을 실제 시뮬 pose로 투영하면 유효320개 중97.5%가 지도 점유셀 중심5cm 안에 있다. AMCL pose 투영은58.44%. 최근접 거리 중앙값은 실제pose1.82cm, AMCLpose4.14cm. 실제 pose는 평가에만 사용했다.
- 전체 beam 평균은 실제5.53cm/추정7.93cm로 일부 큰 잔차가 남아 있다. 스캔과 지도 전체가 완전히 같다는 뜻은 아니다.
- 바퀴 odom 최종1.28cm·최대2.17cm에 비해 AMCL 오차가 회전 중 증가했다. 다음 조사는 회전 구간 AMCL 입자/관측 갱신·장거리 평행 벽 방향의 구속 부족·남은 scan 잔차에 집중한다. 원인을 확정하지 않은 채 noise/허용치/주행 판정을 변경하지 않았다.

복귀 오류 원문:

```text
NAVIGATION_FAILED
위치 (-6.978942363951455, 13.462182613411354)가 그래프에서 0.15m 이상 떨어져 있습니다.
```

실제 위치는 약(−6.99557,13.25987), 기존 접근점(−7,13.25) 근처다. 제어기가 목표까지 못 간 문제가 아니라 잘못 추정된 현재 위치 때문에 복귀 경로 시작이 거절됐다. 실패를 성공 처리하거나 정답 위치를 제어 입력에 주입하지 않았다.

선별은 기존과 동일하게 입력2개 중 빨강1/노랑0, 노랑1개 미검출 잔류. 성능 개선은 이번 지도 변경 범위가 아니다. 실제 예찰/수확/Frontend 전체사이클 시험도 아니다.

## 검증 및 재현

- Domain13/SUBNET, CPU60Hz, render30Hz, 같은 초기 접근 노드9001과 배치, 실물 도킹 거리/시간/정밀 조건 유지.
- `python3 -m pytest -q sim/tests/test_sorter_map.py`: 4PASS. 지도 메타데이터·외부 영역 보존/북쪽 벽 비삭제/얇은 벽 점유/변경 배치 거절/실측 전면 단면 검사.
- 도구3개 py_compile, git diff --check PASS.
- 실제 attempt10: TF freshness6,741회 거절0·미래TF0. runner는 복귀 실패로 exit1. Isaac/ROS 정리 완료; gate1/precision−2는 정리 SIGINT 결과다.
- 준비 과정에서 기존 모델 내부unknown20셀도 제거 대상임을 확인하여 생성기의 최초 과도한 unknown 거부를 수정했다. 실제 제어 시험 재시도/설정 변경은 하지 않았다.

```bash
cd ~/main/farm_project
/home/ysy/isaac/env_isaaclab/bin/python sim/tools/build_sorter_map.py
source /opt/ros/jazzy/setup.bash
source robot/ros_ws/install/local_setup.bash
source sim/ros_ws/install/local_setup.bash
source sim/runs/hcr3a_intake_20261028/ros/install/local_setup.bash
ROS_DOMAIN_ID=13 ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET \
  /usr/bin/python3 sim/tools/run_sorter_cycle_trial.py \
  sim/runs/hcr3a_farm_cycle_20261028/NEW_ATTEMPT --sorting
```

지도 재생성 후 `build_sorter_map.validate`와 회귀 검사를 통과해야 한다. 생성 입력/출력 해시는 `hcr_farm_map.manifest.json` 참고.

자료: `sim/docs/test_results/20261028_sorter_map_update/`의 비교그림·결과·AMCL 시계열·TF 합성·최종scan·최종 설정차이. 원시로그 `sim/runs/hcr3a_farm_cycle_20261028/attempt10/`, drive session `7da3787381bc4e0d81e5103ef50ff811`. 분석용 actual/odom 좌표는 평가 전용. status 이동 구간은 wall−0.15초 근사 매칭, AMCL/scan은 측정stamp 매칭. 최종 정지 비교는 신뢰 가능하다.

미커밋·미푸시. 되돌림은 HCR 시험의 지도 선택/manifest 검사를 이전 상태로 복원하는 것으로 가능하지만, 오래된 지도 불일치가 다시 생기므로 운영 권장하지 않는다. 기존 원본 지도는 수정되지 않았다.
