# 인계 시험의 기존 태그 보정 연결 복원 — 2026-10-28

## 변경 이유와 책임

사용자 “아이씨 왜껐냐고 마음대로” 지적 및 기존조건보존지시에 따라 잘못된 시험구성을 바로잡았다. run_handoff_window_trial.py를 새로 만들 때 기존 SEC시험의 태그연결을 확인하지 않고 공통launch에tag_correction=false를 명시한 것이 원인이다. 사용자가 비활성화를 지시한 것이 아니다. 이전 코드/수치 보존만 확인하고 실제 실행기능의 동등성을 놓친 잘못이며,태그OFF결과를업데이트전성능기준으로간주하지않는다.

## 최종 변경

- sim/tools/run_handoff_window_trial.py: farm_bringup 직접실행+tagfalse에서 기존 farm_sim_runtime/harvest.launch.py+tagtrue로전환. handoff_config와initial_spawn_config전달, fixture에tagtrue/farm_tag_amcl명시.
- sim/ros_ws/src/farm_sim_runtime/launch/harvest.launch.py: 선택handoff_config를기존공통런치에전달. 기존tag_capture_actions로ROS카메라→rectify→AprilTag검출→capture→tag_amcl_adapter→farm_tag_amcl연결을재사용한다. 복제보정로직/정답주입없음.
- 시험초기배치검증은선택initial_spawn_config를읽고,업무환경의station_config는원래스테이션으로유지한다. 일반수확은기존audit를유지하고인계시험은기존runner의별도계측을유지한다.
- sim/tests/test_tag_capture_launch.py: 새선택launch인자의기본값을기존조립검사fixture에반영.
- 공통코드/실물설정/태그보정권한정책/AMCL기본수치/지도/0.8°임시허용치/물리는변경하지않았다. simruntime만빌드했다. 미커밋·미푸시.

## 검증과 실패 기록

1. py_compile통과, farm_sim_runtime빌드통과.
2. 기존태그런치조립검사6/6통과. 최초실행의3개환경오류는샌드박스에서~/.ros/log쓰기거절이며로그경로를sim/runs로설정한재실행은통과했다. 최초로그도보존.
3. 실제첫검증attempt1은시험초기배치를업무station_config에도넘겨공통스테이션/그래프일치검사에서시작실패. `스테이션 위치와 경로 노드가 다릅니다.` 원래스테이션을유지하고초기배치검증인자를분리해수정했다. 실패로그보존,시작하지못한것을액션실패/정확도시험으로집계하지않는다.
4. attempt2는Domain13/SUBNET/CPU60Hz로실제HarvestTask와인계시험실행. **태그보정3회요청/queued/APPLIED확인**. AMCL노드TAG_SCAN_SYNC_READY확인. 단순플래그/노드시작확인보다실제적용까지검증했다.
5. 윈도우수확SUCCESS(expected1/harvested0), DOCK_READY·운송도킹·가상인계·운송이격통과. 수확최종복원은WINDOW_REALIGN_REQUIRED로실패: 전방-0.0922m/횡-0.0143m. 운송SUCCESS,수확restore_complete=false.
6. 최종실제목표거리2.02cm 대지도추정9.33cm, 최종위치추정오차7.34cm. AMCL최대실제오차8.49cm. 태그ON1회만으로OFF대비개선/악화를정량확정하지않는다. **태그연결복원과인계복원문제해결은별개이며후자는미해결**이다.

## 왜 태그를 켰는데 복원 오차가 남는가

이번APPLIED3회는수확윈도우이동중에발생했다. 기존HarvestNode는WINDOW_MOVE에서구역권한을열고HarvestMission종료시TagControl.end()로닫는다. 인계FSM에는새태그권한을여는동작이없다. 태그이벤트로그에서도인계회전/복귀중추가적용0건이다. 따라서이번연결복원은기존수확기능을살린것이지인계회전중보정을새로허용한것이아니다. 후자공통정책을무단변경하지않았다.

원래실행조건을끄고비교했던잘못은수정했다. 위치오차자체가비활성한가지때문이라고확정하지않으며,원호·복귀구간AMCL추정과허용할보정시점은별도원인검토가필요하다.

## 자료와 복원

- raw sim/runs/handoff_tag_restored_20261028/attempt1,attempt2 및실행/빌드/검사로그.
- 공유 sim/docs/test_results/20261028_tag_restoration/: 결과/태그원시이벤트/3회적용요약/최종위치재구성/시작실패metadata.
- 모든시험프로세스정리확인. 신규예찰/전체SEC/선별장복귀시험아님.
- 되돌릴경우이번시뮬런치/시험기/시험fixture변경만대상으로한다. 단,태그false였던잘못된시험조건을정상운영기준으로다시사용하면안된다. 기존누적통합변경은보존한다.

```bash
unzip -o "$HOME/Downloads/tag_restoration_changes.zip" -d /home/ysy/main/farm_project
```
