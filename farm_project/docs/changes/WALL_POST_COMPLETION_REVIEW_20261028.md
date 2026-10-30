# 벽 정렬 종료 후 재검사 문의 분석 — 2026-10-28

사용자가 전달한 Slack 문의를 실제 PC 소스와 대조했다. Slack 원문/시뮬 실행 로그·설치본은 직접 조회하지 않았다. HEAD e135cdef9462276cc25d9fa336f084e2dcac72e4. 기존 node.py·station_return_real 및 문서 미커밋 작업은 보존했다. 코드/설정/프로세스/로봇 상태 변경 없음.

## 확인한 호출

1. farm_wall_controller/include/farm_wall_controller/wall_control.hpp의 Control::step은 거리·각도 범위 안이며 측정 속도도 정지 기준 아래인 상태에서 관측 stamp 기준 dwell을 누적한다. wall_plugins.cpp의 WallGoalChecker가 reached를 Nav2에 반환한다. 실물 wall_alignment_wait_v2.json은 dwell=.5, 거리5mm, 각도0.5도다.
2. harvest_robot/handoff_navigation.py는 step.validate를 공통 Navigator.arrival_validator로 전달한다.
3. farm_navigation/navigator.py는 Nav2 execute 반환 후 출력 차단, MotionMonitor.wait_stopped, arrival_validator 순으로 실행한다. 기본 settle_s=.8이며 현 실물 프로필에서 override를 찾지 못했다. 정지 시간은 호출 후 odom stamp 진행으로 별도 누적한다.
4. harvest_robot/handoff_planning.py의 wall validate는 pose(stamp)를 먼저 조회하지만 벽 오차 계산에는 이 반환 pose를 사용하지 않는다. handoff_runtime._wall_error_once가 최신 유효 wall과 pose(0)를 사용해 다시 계산한다. 같은 허용치로 accepted를 반환한다.
5. accepted=false이면 Navigator는 '정지 후 목표 오차 초과'로 예외를 올린다. 이 분기에는 벽 재정렬 요청이 없다. handoff_motion은 stop 후 INTERRUPTED, poll은 성공 false로 전달한다.

따라서 '제어기 성공 뒤 추가 정지·재검사에서 실패' 경로는 존재한다. 재검사가 제어기보다 숫자상 더 엄격한 조건인 것은 아니며, 다른 시점의 관측/자세를 같은 좁은 범위로 다시 판정하는 문제다. 0.5초는 단순 타이머가 아니라 오차+정지 조건이며 0.8초는 정지 확인이다. 시뮬 적용값은 실제 실행 설정 확인 전 확정하지 않는다.

## 이력과 오프라인 확인

관련 planning/navigator/motion_monitor/wall_control 소스는 성공 기준48d2d1c와 현 HEAD 사이 diff가 없다. Git -S 기준 상위 오류 문구는5d47a23(10/21), 통합 planning wall 분기는cf870da(10/23)부터 확인된다. 독립 wall_trial_runtime에도 정지 후 벽 재검사가 존재한다. 최근 복귀5cm·6도 변경은 wall 분기에 적용되지 않는다.

/tmp/wall_postcheck_repro.py와 C++ 소형 실행으로 실제 Control 헤더 및 AST로 추출한 실제 validate 함수를 검사했다. 거리 오차4mm·정지 상태의 새 관측을 .6초 공급하면 controller_reached=true. 상위 validator는4mm accepted=true,6mm accepted=false. 입력을 인위적으로 바꾼 오프라인 경계 재현이며 ROS/Isaac 물리·스케줄링·실제 대기시간 재현은 아니다.

## 해석과 후속 제안 (미적용)

제어가 끝난 뒤 상위에서 정밀 벽 위치를 다시 책임지는 구조이며, 미세한 관측/자세 변화에 대해 재보정 없이 최종 실패시키는 완료 계약의 취약점이 있다. 다만 Slack의 실제 실패가 이 분기인지는 Nav2 성공→SETTLING→오차 검사 실패 로그와 수치를 확인해야 한다. Failed to make progress, 센서/TF 만료, 정지확인 실패는 별도 경로다.

정지·취소·충돌 보호를 제거하거나 전역 settle_s를0으로 바꾸는 접근은 피한다. 제어기/goal checker가 정렬 및 안정화를 책임지고 상위는 실제 정지·입력 유효성·작업 문맥을 확인하도록 완료 책임을 정리하는 것이 우선 제안이다. 정지 후에도 정밀 재검사가 요구된다면 소폭 이탈 시 제한된 재정렬을 수행하는 별도 계약이 필요하다. 그대로 실패를 성공 처리하는 변경은 제안하지 않는다. 공통 변경은 사용자 승인 후 실물/시뮬 영향과 회귀를 함께 검증한다.

추가 필요 증거: 시뮬 HEAD/설치 경로, dwell/settle/허용치, 같은 Goal의 Nav2 최종 상태 및 상위 오류, final_distance/final_angle_error, 정지 후 stamp와 wall stamp/pose. 본 작업은 분석만 수행, 운영 적용/재기동/이동/commit/push 없음.

## 시뮬 담당 전달 ZIP 대조 — 2026-10-28 후속

사용자 제공 `/home/eunbi/Downloads/real_robot_issue_share_20261028.zip`을 실행 없이 읽었다. manifest 18파일 크기/SHA256 모두 일치. 첨부 비교표의 wall_plugins.cpp/wall_control.hpp/handoff_planning.py 해시는 현재 PC와 일치한다. Nav2 소스 2개는 현재 경로에 없어 전달측 비교 결과로만 취급한다. 시뮬 기준은 ea25693+미커밋 통합본, domain13/SUBNET/CPU물리60Hz. 실물 재현 아님.

벽 정렬 3회 중1회성공/2회실패. 실제 Result에 rotate_to_transfer: 정지 후 목표 오차 초과가 있어 앞선 가능성 분석을 실제 해당 실패 경로로 좁혔다. 외부 재구성 각도는 시험2 완료부근.346도→실패부근.540864도, 시험3 .435도→.605895도. 최종 거리오차 각각.83975mm/3.19123mm로5mm 이내이며 각도0.5도 초과에 부합한다. 내부 validator 입력 직접기록은 없으므로 정확한 수치는 외부 근접표본이다.

정지구간 원본표본43/44개를 직접 계산해 cmd 및 wheel target 모두0, USD yaw변화 각각-.1939549/-.1741378도, wheel position 변화가 첨부요약과 일치함을 확인했다. 전달측 바퀴기반 yaw추정은-.196618/-.173792도다. 관측 노이즈만이 아니라 시뮬 실제 잔류 움직임 증거가 있다. 정지검사는 속도 임계값 이하이지 완전한 위치 고정 보장이 아니다. 실제 최종 검사까지 비교구간 약2.5초라는 전달 기록이며 .5초와.8초의 차이.3초로 설명하면 안 된다.

실패 threshold에는 실물 target_angle=.04276056667386108rad(+2.45도)가 포함됐다. angle_error는 그 목표를 뺀 값이다. 따라서 실물용 보정 설정 유입은 확인됐지만 2.45도 불일치 때문에 거절됐다는 증거는 아니다. 시뮬에 보정이 필요한지 별도 검토해야 하며 일괄0도 변경은 하지 않았다. 시뮬 담당은 후속 시험에서 사용자 승인으로 각도만0.8도로 임시 변경했다고 기록했다. 실패2건은0.5도 조건이고 실물0.5도는 불변이다.

별도 복귀 실패는 태그 복원+0.8도 시뮬 후보 시험이다. Result는 transfer_complete/transport_clear=true,restore_complete=false, WINDOW_REALIGN_REQUIRED(전방-.0922m,횡-.0143m). 외부재구성 실제목표거리2.02cm/map목표거리9.33cm/map위치오차7.34cm/최대8.49cm. 현재 correction_path는5cm 안이면완료, 밖이면전방3mm초과~6cm의짧은전진만가능하므로 목표가뒤9.2cm라는추정으로거절한것과일치한다. raw tag events의 적용3건을직접세었으며 인계중0건은첨부요약과현코드 권한흐름에부합한다. 태그미적용이오차의유일한원인이라는증거는없다. map표본은결과10.7ms전외부재구성이며내부직접표본아님.

후속검토는벽완료계약/시뮬잔류구동과map복귀·태그권한정책을분리한다. 인계중무조건태그를켜거나위치허용치를늘리지않는다. 수정·운영적용·재기동·이동·Slack발송없음.
