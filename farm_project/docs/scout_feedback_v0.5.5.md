# ScoutArea segment feedback — v0.5.5

## 전송 시점

촬영 → YOLO → 깊이/구역 필터 → 열매 ID 연결 및 좌표 갱신 → window 계산 → 결과 저장 후, 완료된 segment당 feedback 1회.

| 시점 | phase | segment_id | harvest_tasks |
|---|---|---|---|
| 마지막 이외의 segment 완료 | SEGMENT_COMPLETE | 이번 segment | 빈 배열 |
| BED의 마지막 segment 완료 | SECTION_COMPLETE | 마지막 segment | 해당 BED 전체 task 목록 |

마지막 segment에서 SEGMENT_COMPLETE와 SECTION_COMPLETE를 두 번 보내지 않습니다. SECTION_COMPLETE 한 번으로 segment 완료와 BED 완료를 함께 알립니다. 수확 task는 기존처럼 한 BED 전체를 처리한 뒤 한 번에 전달합니다. task가 0개여도 SECTION_COMPLETE는 전송됩니다.

시작점 접근, segment 이동 시작, 추가 끝점 이동에는 feedback을 보내지 않습니다. 주기적인 heartbeat도 없습니다. 5개 segment의 정상 완료는 feedback 5개, 16개 구역 × 5개 segment는 80개입니다. 실패한 segment에는 완료 feedback을 보내지 않으며 실패·취소 정보는 Action Result로 반환합니다.

## 추가 필드

ScoutArea.action의 Feedback 부분에 추가:

```text
int32 segment_expected_count
```

이번 촬영에서 유효한 깊이 좌표를 얻고, 요청 구역의 길이/베드 거리 필터를 통과한 파프리카 ID 개수입니다. 구현은 이번 촬영에 연결된 ID의 고유 개수입니다.

- 누적 개수가 아닙니다. 새로 만들어진 ID 개수만 세는 것도 아닙니다.
- 이전 segment에서 본 열매를 이번에도 보면 이번 segment의 개수에도 포함합니다.
- window 개수나 task 개수가 아닙니다.
- 해당 구역의 검출이면 수확 높이/깊이 조건으로 window에 포함되지 못한 열매도 포함합니다.
- 깊이 좌표를 얻지 못했거나 다른 구역/베드로 걸러진 검출은 제외합니다.
- 검출이 없으면 0입니다.
- 따라서 segment_expected_count를 합한 값은 중복 제거된 BED 총 수확 개수와 다를 수 있습니다. Result의 total_expected_count는 기존처럼 최종 task들의 expected_count 합입니다.

예: 동일 열매 1개를 5번 촬영했다면 각 feedback의 segment_expected_count는 1이고, 해당 열매가 window에 들어갔다면 최종 예상 수확 개수는 1입니다.

현재 segment의 개수는 survey.json의 sections.<BED>.segments[]와 observations[]에도 저장합니다. 임시 관제 클라이언트의 터미널 로그와 JSONL에도 표시합니다.

## 선택적인 경로 끝 이동

기본 finish_at=last_segment 동작은 동일합니다. finish_at=route_end를 별도로 사용하는 경우에도 마지막 촬영 처리가 끝나면 즉시 SECTION_COMPLETE를 보내고, 이후 경로 끝으로 이동합니다. 이 후속 이동에는 feedback이 없습니다. 후속 이동만 실패한 경우 BED 예찰은 COMPLETE로 남고, 전체 Action Result는 FAILED가 됩니다. post_capture_navigation에 후속 이동 상태를 기록합니다.

## 적용

v0.5.4까지 적용된 프로젝트 기준 패치입니다. 실행 중인 예찰 서버와 관제 클라이언트를 종료하세요. Action 정의가 바뀌었으므로 통신 양쪽이 같은 farm_interfaces를 빌드해야 합니다.

```bash
unzip -o ~/Downloads/farm_scout_feedback_v0.5.5.zip -d ~/main/
cd ~/main/farm_project &&
source scripts/env.sh sim &&
(cd robot/ros_ws && colcon build --packages-select farm_interfaces scout_robot)
```

서버 터미널:

```bash
cd ~/main/farm_project &&
source scripts/env.sh sim &&
ros2 launch farm_bringup scout_survey.launch.py mode:=sim \
  project_root:="$PWD" \
  vision_python:="$(cat runs/vision_python.txt)" device:=0
```

관제 터미널도 새 환경을 불러와서 실행:

```bash
cd ~/main/farm_project &&
source scripts/env.sh sim &&
python control/scripts/send_scout_area.py --section BED_01
```

별도 PC의 관제 프로그램을 사용하면 그 PC에도 변경된 ScoutArea.action을 전달하고 farm_interfaces를 재빌드해야 합니다. USD와 맵, 센서 설정에는 변경이 없습니다.

## 검증

가짜 ROS/비전 입출력으로 실제 예찰 서버 함수를 실행한 오프라인 테스트 13개 통과. segment당 1회, 마지막에만 BED task 전송, 0개 검출, 재검출 개수, 구역 밖 제외, window 미포함 검출의 개수, 두 BED 누적, 중간 실패/취소, 마지막 촬영 이후 이동 실패를 확인했습니다.

이 환경에서는 ROS Action 코드 생성/실제 DDS 통신 및 Isaac Sim 실행은 검증하지 않았습니다.
