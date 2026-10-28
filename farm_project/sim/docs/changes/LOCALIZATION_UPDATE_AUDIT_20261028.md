# 위치 추정 업데이트 전후 실행 조건 점검 — 2026-10-28

사용자 “위치추정오차가 원래 심했던거야? 이번에 업데이트되면서 바뀐건없고?” 요청에 따른 읽기 분석. 설정/운영 코드 변경이나 추가 시뮬 실행은 하지 않았다.

## 결론과 앞선 설명 보완

**이전 SEC01~16 시험과 최근 인계 시험의 위치 추정 실행 조건이 다르다.** AMCL 기본 설정이나 지도를 되돌린 증거는 없지만, 새 인계 시험 실행기에서 태그 보정을 끄고 일반 AMCL을 선택했다. “업데이트 전부터 원래 이 정도로 심했다” 또는 “위치 추정 관련 변경이 없다”는 결론은 현재 증거로 성립하지 않는다.

앞서 비교한4~6cm 오차 기록(HANDOFF_DIAGNOSIS의attempt2/3 및pickup9)도10/28 통합 이후 인계 시험이다. 업데이트 전 대조군이 아니므로 이를 근거로 업데이트 전 수확 위치 추정 성능을 단정해서는 안 된다. 이전 예찰의 위치 정합 개선 기록은 로봇/동작/평가항목도 달라 이번 수확 인계 정확도와 직접 비교할 수 없다.

## 확인된 차이

| 항목 | 이전 SEC01~16 3차 시험 | 최근 인계 재현시험 |
|---|---|---|
| 실행 도구 | run_section_campaign.py → all.launch.py | run_handoff_window_trial.py → harvest.launch.py |
| 태그 위치 보정 | tag_correction:=true | tag_correction:=false 명시 |
| 선택 위치 추정 노드 | farm_tag_amcl | nav2_amcl |
| 태그 보정 실제 적용 | SEC01_attempt_0002 수확로그46회 APPLIED | 해당 위치보정 노드를 실행하지 않음 |
| 주행 조건 | 수확 접근/윈도우 작업 등 | 윈도우 앞 초기배치 후 인계 원호·회전·역원호·최종위치검사 |
| 지도/AMCL 기본 수치 | 기존 공통 설정 | 동일 파일 유지 |

- 이전 실제 실행 증거: sim/runs/sec01_16_round3_20261023_151213/SEC01_attempt_0002/launch.json에true, stack.log에수확farm_tag_amcl실행경로, ros/python3_14389_1792738243338.log에TAG_CORRECTION_APPLIED46회. 켜져있기만했고실제적용되지않았던것이아니다.
- 현재 sim/tools/run_handoff_window_trial.py는harvest.launch.py에false를직접전달한다. 이는기존공통태그기능삭제가아니라새시뮬시험실행기의선택이다. 기존조건과동일하게비교하려면이차이를통제해야한다.
- harvest.launch.py → tag_launch_actions → tag_scan_sync → scout_navigation.launch.py의노드선택경로를확인했다. scan_sync가true면farm_tag_amcl, false면nav2_amcl이다. 수치만같다고실행구성동등이라고할수없다.
- 이번비교는위치추정용태그보정이다. 운송도킹용41/42마커검출과별도기능이므로도킹마커가보인다고map위치보정이켜진것은아니다.

## 보존된 부분

92ad63a(3차시험준비반영) 및ea25693(현재HEAD)와작업트리를비교해다음파일byte동일확인:

- robot/config/navigation/harvest_nav2.yaml (AMCL블록도동일)
- sim/ros_ws/src/farm_sim_config/config/nav2_harvest.yaml
- robot/ros_ws/src/farm_tag_amcl/src/amcl.cpp
- sim/ros_ws/src/farm_sim_config/maps/count_test_farm_map.yaml 및png

alpha1~5=.2, sigma_hit=.2m, max_beams60, update_min_d=.05m, update_min_a=.2rad 유지. 전체지도/태그코드롤백으로설명할근거는없다. 일반nav2_amcl외부설치패키지의과거바이너리동일성까지확인한것은아니다.

## 기타 함께 달라진 입력·동작

- 새시뮬실행묶음의수확state_clock_delay_s=.1 및ros_adapter의동일시각TF선발행/odom·scan후발행. 측정값·stamp계산자체는보존하지만DDS도착/관측처리시점은달라졌으며영향을0으로단정할수없다.
- 바퀴PI ki4→1 및정지시target0 반환, 새로운인계회전/역원호경로, 근처운송로봇·마커조건. 실제odom오차는현재mm수준으로측정됐으나회전궤적/관측조건차이는남는다.
- 공통PoseProvider는인수코드의동일시각map/odom쌍조회·일시적TF누락처리추가, 인계전용최종윈도우5cm/6°검사도새실행경로에존재한다. AMCL출력자체에큰오차가관측됐으므로최종조회만의문제라고할근거는없다.

## 판단과 다음 비교

태그보정비활성은이전성능과비교하기전에바로잡아야할중요한시험조건차이다. 하지만인계복귀중태그보정권한이열리는지·마커관측이가능한지확인하지않았으므로true한줄만으로해결된다고단정하지않는다. sim에서는현재capture_directory와보정입력연결도필요하므로기존all.launch의연결방식을사용해야한다. 복귀중권한을새로여는것은공통동작변경으로별도검토한다.

다음권장검증은이전과같은태그카메라/검출/AMCL연결을복원한시험구성을준비하고실제APPLIED이벤트를기록하며동일인계반복을비교하는것이다. 그전까지10cm오차가원래수준인지업데이트로악화됐는지확정하지않는다. 이번질문응답에서는태그설정이나코드를자동수정하지않았다.

근거: sim/docs/test_results/20261028_localization_update_audit/evidence.json. 원격fetch없이로컬확보커밋·작업트리·저장실행로그를비교했다. 미커밋/미푸시. 자료복원은이번문서추가분만제거한다.

```bash
unzip -o "$HOME/Downloads/localization_update_audit.zip" -d /home/ysy/main/farm_project
```
