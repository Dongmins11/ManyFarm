# v0.5.3 — 베드별 촬영 segment와 완료 시점

## 1. segment 정의

**한 번의 촬영 지점 = 하나의 segment**입니다.
현재 sim 베드는 자동 계산으로 5개이며 `BED_01_S001`부터 `BED_01_S005`까지 사용합니다.
카메라 관측 영역은 서로 겹칠 수 있습니다. 공간을 겹치지 않는 다섯 조각으로 자른다는 뜻은 아닙니다.

- segment 완료: 이동·정지·촬영·검출·좌표 보정·결과 저장까지 완료한 상태.
- 검출 열매가 없어도 정상 촬영·처리가 끝났으면 segment 완료로 셉니다.
- 수확 윈도우의 소속: 처음 윈도우를 생성한 segment.
- 이후 다른 segment에서 같은 열매를 다시 보면 기존 ID의 좌표와 윈도우 포함 여부를 갱신합니다.
- 열매를 처음 본 segment와 윈도우를 처음 만든 segment는 다를 수 있습니다. 보류 후 포함된 경우가 이에 해당합니다.
- 작업 목록은 베드 완료 시 한 번만 전달합니다. 촬영마다 같은 작업을 반복 전송하지 않습니다.

## 2. 왜 마지막 촬영 후 오래 걸렸나

사용자가 제공한 세션 `56571de5ad6f`의 이전 로그 기준입니다.

| 단계 | 기록 |
|---|---|
| 5번째 촬영 위치 | 경로 시작부터 약 6.045m |
| 기존 코드의 추가 목표 | 경로 끝 7.000m |
| 남은 거리 | 약 0.955m |
| 마지막 추가 주행 시작 | 2026-09-29 09:40:55.863 KST |
| 도착·정지 확인 완료 | 09:41:16.992 KST |
| 추가 주행·정지 확인 소요 | **21.130초** |
| 도착 후 최종 기록까지 | **0.467초** |

마지막 영상의 전처리·추론·깊이 처리는 약 21.7ms였습니다.
긴 지연의 주된 원인은 추론이 아니라 **촬영이 끝난 뒤 경로 끝까지 추가 이동하는 코드**였습니다.
새 버전에는 이 완료 조건을 베드별로 선택하는 `finish_at`을 추가했습니다.

| finish_at | 동작 |
|---|---|
| `last_segment` | 마지막 segment 처리 후 결과를 보내고 종료. 현재 sim 적용값 |
| `route_end` | 마지막 촬영 뒤 경로 끝까지 추가 이동한 후 결과 전송. 기존 동작 |

`last_segment`에서는 현재 베드의 끝점까지 로봇이 실제로 이동하지 않습니다.
현재 계획의 마지막 촬영 영역이 경로 끝까지 덮는지를 검사하고 종료합니다.
이 검사는 계획된 카메라 위치 기준이며 실제 위치추정 오차까지 없는 관측을 보증하는 것은 아닙니다.

## 3. sim/real 설정 분리

| 구분 | 설정 파일 |
|---|---|
| sim | `sim/ros_ws/src/farm_sim_config/config/scout_survey.json` |
| real | `robot/config/survey/scout_real.json` |
| 실물 담당자용 양식 | `robot/config/survey/scout_real.example.json` |

공통 `scout_survey.launch.py`가 mode에 따라 파일을 선택합니다.
`survey_config:=/사용할/파일.json`으로 직접 지정할 수도 있습니다.
real 양식은 `configured: false`이고 실물 치수·경로는 빈칸입니다. 그대로 실행할 수 없습니다.
실물 담당자가 채워서 실제 파일명으로 저장하고 `configured: true`로 바꾸어야 합니다.
실제 장치 드라이버와 실제 카메라 설정도 별도로 준비해야 합니다.

촬영·검출·좌표 보정·관제 통신 코드는 계속 공통 코드로 사용합니다.
현재 기하는 한 베드의 직선 주행 구간을 지원합니다. 구부러진 경로를 직접 넣는 기능은 추가하지 않았습니다.

## 4. 베드별 자동/직접 지정

각 `sections.BED_01` 안에 아래 설정이 들어갑니다.

### 자동 계산 — 현재 sim 기본

```json
{
  "finish_at": "last_segment",
  "segmentation": {
    "mode": "auto",
    "id_prefix": "BED_01_S",
    "overlap_fraction": 0.15
  }
}
```

베드 경로 길이·실제 카메라 정보·크롭 범위를 사용해 촬영 개수와 위치를 정합니다.
현재 7m 구간은 약 1.91m 관측 폭과 최소 15% 겹침으로 5회 촬영합니다.
다른 길이의 real 베드에는 같은 코드로 다른 개수와 위치가 계산될 수 있습니다.

### 직접 지정 — 현재 sim 베드의 예

```json
{
  "finish_at": "last_segment",
  "segmentation": {
    "mode": "manual",
    "overlap_fraction": 0.15,
    "segments": [
      {"segment_id": "BED_01_S001", "offset_m": 0.955},
      {"segment_id": "BED_01_S002", "offset_m": 2.228},
      {"segment_id": "BED_01_S003", "offset_m": 3.500},
      {"segment_id": "BED_01_S004", "offset_m": 4.772},
      {"segment_id": "BED_01_S005", "offset_m": 6.045}
    ]
  }
}
```

`offset_m`은 **해당 베드 경로 시작점부터 진행 방향으로 잰 거리(m)**입니다.
GeoJSON node ID나 map의 x/y 좌표가 아닙니다. 공통 코드가 map 좌표로 변환합니다.
real에서는 실제 베드의 경로와 촬영 위치를 사용해야 하며 위 예시 값을 그대로 복사하지 않습니다.

ID 중복, 경로 밖 거리, 역순, 관측 영역의 빈틈, 최소 겹침 미달을 검사합니다.
카메라 정보를 읽어야 가능한 범위 검사는 베드 시작점 접근 후에 수행됩니다.
설정은 예찰 서버 시작 시 읽으므로 변경 후 예찰 서버를 재시작합니다.

## 5. 관제 피드백

메시지 자료형은 변경하지 않습니다. 기존 `string phase`에 베드 완료와 추가 이동을 구분하는 값이 추가됩니다.
임시 관제 클라이언트는 이 변경을 함께 반영했습니다.

| phase | 의미 | harvest_tasks |
|---|---|---|
| `MOVING` | 베드 시작점 또는 해당 segment로 이동 | 빈 배열 |
| `SEGMENT_COMPLETE` | 해당 촬영 처리 완료 | 빈 배열 |
| `FINISHING` | route_end 설정에 따른 추가 이동 | 빈 배열 |
| `SECTION_COMPLETE` | 베드 완료 | 베드 전체 작업 목록 |

완료된 segment 수는 베드 사이에도 누적됩니다. 5개짜리 베드 두 개를 완료하면 10입니다.
3번째 촬영에서 실패하면 완료 segment는 2, 완료 베드는 0이며 미완료 베드의 작업 목록은 전송하지 않습니다.
완료한 베드에서 이미 전송한 배치는 유지됩니다.

`HarvestTask.segment_id`에는 각 윈도우가 처음 생성된 segment ID가 들어갑니다.
종전의 `BED_01_BATCH` 임시 값과 베드 수를 segment 수로 세던 코드는 제거했습니다.
실제 관제 연동 시에는 **작업 목록 수신 조건이 SECTION_COMPLETE**임을 반영해야 합니다.
이는 임시 클라이언트 동작이며 외부 관제 구현과의 호환성은 별도 확인 대상입니다.

## 6. 적용·실행

v0.5.2까지 적용된 프로젝트 기준입니다. 예찰이 끝난 상태에서 예찰 서버만 Ctrl+C로 종료합니다.
Isaac/Nav2는 유지할 수 있습니다. robot_venv에서:

```bash
unzip -o ~/Downloads/farm_scout_segments_v0.5.3.zip -d ~/robotarm/
cd ~/robotarm/farm_project
source scripts/env.sh sim
python scripts/apply_scout_segment_config.py &&
(cd robot/ros_ws && colcon build --packages-select scout_robot farm_bringup farm_vision)
```

적용 스크립트는 기존 config의 2cm 허용 오차·카메라·팔 치수를 보존하고, 기존 segment 설정이 없을 때 자동 모드와 `last_segment`를 추가합니다.
이미 직접 작성한 segmentation과 finish_at은 덮어쓰지 않습니다. 원본은 `runs/config_backups/`에 백업합니다.
전체 sim config를 덮어쓰는 파일은 ZIP에 없습니다.

서버 재실행:

```bash
cd ~/robotarm/farm_project
source scripts/env.sh sim
ros2 launch farm_bringup scout_survey.launch.py mode:=sim \
  project_root:="$PWD" vision_python:="$(cat runs/vision_python.txt)" device:=0
```

다른 터미널에서:

```bash
cd ~/robotarm/farm_project
source scripts/env.sh sim
python control/scripts/send_scout_area.py --section BED_01
```

5번의 `SEGMENT_COMPLETE`, 한 번의 `SECTION_COMPLETE`, 마지막 `SUCCESS`가 정상 순서입니다.
`completed_segment_count`는 현재 베드 기준 5입니다.

## 7. 확인할 기록

- 영상 상단: 현재 segment ID.
- `survey.json` → `sections.<bed>.design.segments`: 계획된 segment ID·촬영 거리·관측 범위.
- `sections.<bed>.segments`: 실제 진행 상태·이동 시간·촬영/처리/저장 시간.
- `sections.<bed>.post_capture_navigation`: 추가 주행 여부·소요 시간.
- `sections.<bed>.batch_finalize_wall_s`: 작업 구성/저장/피드백 전송 시간.
- `worker_cleanup_wall_s`: 추론 프로세스 정리 시간.
- `completed_segments`: 완료된 section/segment ID 목록.
- 열매 `first_segment_id`, `observed_segment_ids`, 측정 샘플의 `segment_id`.
- 윈도우와 관제 작업의 `segment_id`: 최초 생성 segment.
- 촬영 폴더 이름은 기존 `observation_001` 형식을 유지하며 내부 JSON에 segment ID를 기록합니다.

## 검증

새 segment 검사 10개와 기존 회귀 검사 31개, 공유메모리 작업 프로세스 검사가 통과했습니다.
자동/수동 설정, 다른 베드 길이, 윈도우 소속 유지, 마지막 촬영 종료/경로 끝 종료,
중간 실패·취소 시 완료 개수, 베드 두 개의 누적 집계와 한 번씩 배치 전송을 검증했습니다.
ROS 서비스/액션은 가짜 입출력으로 대체했습니다. 실제 ROS 빌드·Isaac 주행은 이 환경에서 실행하지 못했습니다.
