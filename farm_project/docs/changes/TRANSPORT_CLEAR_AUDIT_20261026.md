# TRANSPORT_CLEAR 이후 복귀 실패 — 2026-10-26

사용자 요청: 이번 시험의 TRANSPORT_CLEAR 진행 문제 로그 분석. 운영 코드·설정·프로세스·관제 변경 없음.

대상 DOCK_TEST_ec1de1850afa49fea1ca5b30c56fd037 / TRANSFER_TEST_286abaab16f64e5f8064b1055348946f. 실행 launch20261026_092601_launch_41789.

|KST|확인 결과|
|---|---|
|09:32:19.680|벽 정렬 컨트롤러 목표 도달|
|09:32:20.557|수확 DOCK_READY 피드백|
|09:32:49.185|DOCK_STABLE 수확 서비스 수락|
|09:32:51.688|수확 TRANSFER_COMPLETE 피드백(PC 더미 배출 범위)|
|09:33:43.378|관제에 운송 TRANSPORT_CLEAR 피드백|
|09:33:43.449|관제에 운송 Action SUCCESS 결과|
|09:33:44.631|웹 TRANSPORT_CLEAR 요청|
|09:33:44.675|수확 서비스 accepted=true/NONE|
|09:33:44.898|수확 RESTORING 상태|
|09:33:46.494→09:33:59.547|후진 이탈 전용goal 시작→도달|
|09:34:00.625→09:35:36.195|HandoffRuntime.guard:align 실행 95.570초 후 방향 조정 이동 범위 초과|
|09:35:36.338|수확 최종FAILED/DEVICE_FAILED,restore: 방향 조정 이동 범위 초과|

수확 최종필드 transfer_complete=true/transport_clear=true/restore_complete=false. 전체인계성공으로기록하지않음. 운송의 실제물리이격은관제피드백/결과수신으로만확인,운송기기직접접속/변경없음.

운영소스 sensor_hold_robot_20261024/src/harvest_robot/harvest_robot/handoff_runtime.py의 guard:align은 check_grid 후 align_origin/target/envelope 저장, AsyncClearance 준비 및 연속정지검사·현재자세검사를 수행한다. 검사 완료 후에만 planner가실행객체를반환한다. 이번stage_error가guard내부이므로 방향조정실행전실패. 로그에새spin실행시작도없음.
09:34:01.489 HANDOFF_WAIT 검사 결과 대기. 종료사유는대기timeout문구가아닌_align_pose_valid의범위오류. 이분기는비유한값/목표중심거리limit초과/align_origin대비yaw16도초과를공통오류로낸다. 운영handoff_fsm.json reentry_position=.01m. 실제limit/center/current/yaw를실패로그가보존하지않아어느분기/초과량인지미확정. 사용자물리이동이나odom드리프트를원인으로단정하지않음.

판정: TRANSPORT_CLEAR는정상수락됐고통신지연이주된95초정체구간이아님. 후진이탈후회전공간검사대기및범위검사실패가후속조사대상. 기준완화/복구/재전송/재기동미실시.
자료 runs/transport_clear_audit_20261026: 관제handoff읽기응답(토큰제외),launch.log,task_events.json,align_trace.jsonl,runtime.json. 기존원본보존. commit/push없음.

## 주변 운송 로봇과 대기/실패 조건 추가 검토
사용자 약30~40cm 주변 운송로봇 관측 설명. 이거리만으로접촉/안전/실패원인확정불가. 차체간간격인지센서/중심거리인지와회전중swept footprint가필요하다. 62x52cm패딩포함사각형의중심-모서리반경약.405m는중심기준치이며차체간필요간격값이아니다.
운영 runtime._grid_key는region인자없이전체costmap기하/254·255차단셀마스크를hash한다. 실제회전경로밖의운송로봇셀변경도key불일치→ClearancePending→0출력재검사를유발가능. 일반inflation값변화만은이binarykey를바꾸지않는다. usable의최소clearance-자세drift<=0도대기다.
반면check_grid의경로footprint와254/255셀접촉/지도경계접촉/계산한도초과는RuntimeError→작업실패로전파. AsyncClearance의InputUnavailable만재시도하며solver오류/프로세스사망/응답timeout은실패. 운영응답제한인자는runtime recovery_timeout(설정5초),sensor_wait_indefinite=true가모든오류를무한대기로바꾸는것은아님.
최종align범위오류는비유한입력/기준중심거리1cm초과/align_origin대비16도초과중하나. 주변장애물유무직접분기가아니다. 장시간대기후위치추정변화로이분기에걸렸을가능성은있으나기록부족으로미확정.
개선검토우선순위(미적용): 회전영역외지도변경에대한불필요한무효화제거,실제장애물검출과계산실패분리,정지중기준범위이탈시무조건최종실패대신새전체충돌검사/안전한재계획가능여부평가,분기별수치진단. 충돌검사제거·1cm무작정확대는하지않음.
