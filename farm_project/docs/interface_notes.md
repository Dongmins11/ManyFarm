# 이번 인터페이스 범위
제공 PDF의 `/scout_01/scout_area`만 작성했습니다. ROS action 파일 순서는 Goal / Result / Feedback입니다.
`status`, `return_to_station`은 포함하지 않습니다. Action 서버와 임시 관제 클라이언트는 아직 구현하지 않았습니다.

PDF 내부 불일치: Feedback의 completed_segment_count는 표에서 string이나 예제와 Result에 맞춰 int32로 두었습니다.
window_id는 표의 int32 대신 HarvestTask.msg와 예제의 string을 적용했습니다.
이는 임시 인터페이스이며 실제 관제와 동일한 패키지명·타입명·필드로 맞춰야 최종 연결됩니다.

Section은 하나의 베드입니다. Segment의 의미는 확정 전입니다.
HarvestTask.goal_pose는 수확로봇이 멈출 위치이며 예찰로봇의 현재 위치나 열매 좌표가 아닙니다.
재관측 시 이미 전송한 window의 expected_count를 갱신하는 규칙도 후속 합의가 필요합니다.

공유메모리 RGB-D에는 frame sequence, 촬영 simulation timestamp, optical frame ID,
해상도/stride/dtype, intrinsics, depth 단위, RGB/depth 정렬 기준을 포함해야 합니다.
완료된 프레임만 읽도록 동기화하고 촬영 시각의 TF로 변환합니다. 이 구현은 다음 단계입니다.
