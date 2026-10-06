# 실물 담당자 소스 인수 검토 및 시뮬레이션 적용 기준

기준일: 2026-10-02

## 결론

이번 소스는 **공통 예찰 실행 구조와 주행 라이브러리를 정리하고 실물 Burger·D435를 연결한 상태**다. 시뮬레이션은 이 공통 코드를 사용하면서 `sim/`의 환경·장치·데이터를 연결하는 방향으로 진행한다.

기존 harvest-scout 시험은 사용자의 개별 시험이다. 이번 소스의 운영 기준으로 자동 병합하지 않는다. 이번 검토에서는 실행 코드·설정·모델을 수정하지 않았고 작업 규칙과 검토 기록만 추가했다.

## 1. 검토 근거와 한계

- 첨부 `farm_project.zip`의 실제 소스·설정·메시지·시험을 확인했다.
- 첨부 인수인계서와 ZIP 내부 `docs/SUMMARY_인수인계서.md`는 바이트 기준 동일하다.
- ZIP에 `.git`과 수정 전 소스가 없으므로 정확한 커밋별 diff나 작성자별 변경 목록을 확정한 것은 아니다. 아래 변경 설명은 인수인계서·이관 기록을 현행 코드와 대조한 결과다.
- 9월 10일 기획서와 시뮬 파트 문서는 파트 역할 및 통합 원칙을 참고했다. 최신 장치·작물·메시지 값은 현행 소스를 기준으로 확인했다. 현재 Goal의 작물 값은 `PAPRIKA`다.
- 인수인계서의 최근 실물 시험 3개 세션은 ZIP에 없다. 실물 도착·실패 결과는 담당자 보고이며 이번 환경에서 직접 재현한 결과가 아니다.

## 2. 핵심 변경 내용

| 영역 | 반영된 내용 | 통합 시 의미 |
|---|---|---|
| 예찰 실행 구조 | `scout_new/`의 Node·Mission·Communication·StateController·States로 책임 분리 | 설정/ROS 연결, 작업 데이터, 관제 통신, 상태 전환, 단계 행동을 각각 관리 |
| 비동기 상태 처리 | State가 작업 요청 후 반환하고 완료 이벤트를 Controller에서 처리. 취소 후 늦은 응답 차단 | 주행·카메라 대기 중에도 취소·종료를 처리하는 구조. 업무 FSM을 시뮬 전용으로 다시 작성하지 않음 |
| 공통 주행 | `farm_navigation`에 그래프 탐색·Path 생성·Nav2·TF·odom 정지·도착 검사 이관 | 예찰 내부 변수 의존을 줄이고 다른 로봇도 사용할 주행 경계 마련 |
| 환경 선택 | 환경 YAML → 지도·그래프·Nav2·장치·예찰·영상 설정 선택 및 ID 일치 검사 | 같은 로봇 코드에 sim/real 데이터를 따로 연결 가능 |
| 실물 입력 | Burger 기존 드라이버, 매니팜 지도, D435 SDK/기존 비전 워커 연결 | 실물 어댑터를 시뮬에서 흉내 내기보다 기존 공통 입력 계약에 시뮬 센서를 연결 |
| 영상 워커 수명 | `VisionRuntime`이 노드 시작 때 준비. 정상 미션 후 재사용, 실패·취소 후 교체 | 영상 준비 전 Goal은 거절. 기존에 Goal 이후 준비하던 실행 순서와 다름 |
| 이동 좌표 수정 | `bed.world()`의 XYZ를 주행 호출 경계에서 XY로 변환 | 두 번째 촬영점 이동에서 발생한 입력 형식 오류 수정 |
| 과실 처리 정책 | 중앙값 갱신/소속 재검사와 최초 위치/기존 소속 유지 두 정책 제공 | 현재는 `MEDIAN_REVALIDATE`. 선택은 공통 Python 코드이므로 변경 전 승인 필요 |

기존 `survey_server.py`와 계산 코드는 보존되어 있다. 새 통합 launch의 기본 실행은 `scout_node`이며 두 서버를 같은 액션 이름으로 동시에 실행하지 않는다. `Scout New/scout_new` 경로는 별도 사본이 아닌 심볼릭 링크다.

공통 주행의 그래프 모드는 자체 경로 탐색 → Path 보간 → `FollowPath`다. 현재 공통 경로가 `ComputeRoute` 액션을 호출하는 구조는 아니다. Nav2 성공 응답 외에 정지 및 실제 TF 도착 오차도 확인한다.

## 3. 현재 시뮬·실물 설정 비교

| 항목 | 시뮬레이션 | 실물 |
|---|---|---|
| 공통 실행 | `scout_new` + `farm_navigation` | 동일 |
| 환경 진입점 | `sim/ros_ws/src/farm_sim_config/config/scout_runtime.yaml` | `robot/config/environments/scout_real.yaml` |
| 지도 ID | `farm_map_v1` | `many_farm_v1` |
| 관측 구역 | `BED_01`~`BED_16`: 물리 베드 8개의 양쪽 면 | `SEC_01` |
| 촬영점 | 카메라 FOV 기반 자동 분할 | patrol 설정의 4·6·8번 노드 |
| 기본 주행 | `navigate_to_pose` | `follow_path`, RPP |
| 그래프 구조 | 128노드·112엣지, 16개 약연결 성분 | 18노드·40엣지, 1개 약연결 성분 |
| base frame | `scout_01/base_footprint` | `base_footprint` |
| 시간 | 시뮬레이션 시간 | 실시간 |
| 영상 입력 | Isaac RGB-D 공유메모리 | D435 SDK + 기존 실물 워커 |
| 카메라 설정 | 640×384, 15FPS | 1280×720, 6FPS, 시작 시 120프레임 대기 |
| 모델 설정 | `model_yolo11_seg_ver1.0.pt` | `model_yolo11_seg_ver1.2.pt` |
| 검출 신뢰도 설정 | 0.25 | 0.6 |

시뮬 설정의 15FPS는 카메라 목표 주기이며 통합 추론 성능을 직접 측정한 값은 아니다. 그래프의 약연결 성분 수는 방향을 무시한 연결성 검사이며 모든 방향의 경로 가능성을 보장하지 않는다.

실물 비전은 `~/pi_d435_setup/.venv`와 `~/bmany_fleet_ws/perception_worker`에 의존한다. v1.2 모델은 이번 ZIP에 포함되어 있지 않다. 두 환경의 검출 결과를 같은 조건으로 비교하려면 모델·전처리·임계값·카메라 조건을 먼저 맞추거나 차이를 기록해야 한다.

## 4. 시뮬 통합 전에 정리할 부분

### 4.1 시뮬 전용 파일이 아직 완전히 분리되지는 않았다

| 현재 위치/참조 | 확인 사항 | 다음 작업 기준 |
|---|---|---|
| `robot/config/vision/scout.json` | 공유메모리·시뮬 크롭 범위가 담긴 영상 설정 | 시뮬용 원본을 `sim/.../farm_sim_config/config/`에 두고 `scout_survey.json`에서 선택. 이번에는 미적용 |
| `scripts/run_scout_sim.py`, `generate_scout_dataset.py` 등 | 시뮬 도구가 루트 scripts에도 남아 있음 | 새 시뮬 기능은 `sim/tools/` 또는 시뮬 패키지에 작성. 기존 호출부 이동은 영향 확인 |
| `VisionRuntime` 및 공통 launch | 워커 시작 경로 `scripts/run_scout_survey_worker.py`를 코드에서 선택/확인 | 경로 이동이 필요하면 해당 공통 호출부의 최소 변경안을 별도로 승인받음 |
| `output_dir: runs/scout_survey` | 두 환경이 같은 상대 출력 경로 사용 | 새 시뮬 프로파일의 출력은 `sim/runs/scout_survey` 등으로 분리 가능 |
| `survey_policy.py` | 공통 코드 상수로 처리 정책 선택 | 시뮬 실험 때문에 직접 바꾸지 않음. 설정화가 필요하면 공통 변경으로 제안 |

공통 전처리·검출 코드는 재사용한다. `sim/` 안에 공통 로봇 코드를 복사해 별도 FSM이나 과실 처리 로직을 만드는 방식은 사용하지 않는다.

### 4.2 그래프 추종 조건이 실물과 다르다

시뮬 그래프는 베드별 직선 16개가 분리되어 있다. 현재 `NavigateToPose`로 이동할 수 있더라도 실물과 같은 그래프 경로 추종·통로 공유·교통 정리까지 검증한 것은 아니다.

기존 농장 구조를 유지하고 실제 통로와 주행 방향에 맞는 연결 데이터를 `sim/`에서 설계한 뒤 공통 `FollowPath` 모드 적용을 검토해야 한다. 연결을 임의로 넣거나 `FollowPath` 실패를 숨기고 다른 주행 방식으로 대체하지 않는다. 교통 제어 자체는 이번 공통 코드의 완성 기능이 아니다.

### 4.3 메시지·피드백은 인수인계서가 대조한 관제 규격과 차이가 있다

| 항목 | 첨부 코드에서 확인한 현재 상태 | 인수인계서가 비교한 규격 |
|---|---|---|
| Goal 구역 | `section_ids` 배열 | `section_id` 문자열 |
| Result 구역 | `completed_section_ids` 배열 | `section_id` 문자열 |
| 구역/촬영점 ID 예 | 실물 `SEC_01`/`SEG_01`, 시뮬 `BED_01` 등 | `SEC01`/`SEC01_G01` 등 |
| 수확 작업 전달 시점 | `SECTION_COMPLETE`에서 구역 작업 목록 전달 | Segment별 작업 목록 전달 |
| 상태·조회·복귀 | status·작업 조회·복귀 인터페이스 미구현 | 별도 인터페이스 요구 |

오른쪽 규격은 인수인계서의 Confluence 46버전 비교 내용이다. 외부 문서의 현재 버전을 새로 조회한 결과는 아니다. 코드의 현재 동작은 소스에서 확인했다.

ID 문자열만 바꾸어 메시지 타입 차이를 해결할 수 없다. 프로토콜 변경은 `farm_interfaces`, 관제, 예찰 통신/상태 코드를 함께 검토할 공통 변경이다.

### 4.4 수확·운송 연계는 이번 ZIP의 구현 범위와 구분한다

- `harvest_robot/`에는 구현 예정 README만 있고 ROS 패키지로 등록되어 있지 않다.
- `harvest.launch.py`는 미구현 오류를 내도록 되어 있다.
- 기존 `control/scripts/run_bed_scout_harvest.py`는 이번 ZIP에 없다.
- `HarvestTask.msg`는 예찰이 계산한 작업 데이터 형식이다. 이것만으로 수확 로봇의 이동·수확 실행 서버가 구현된 것은 아니다.
- 복귀·도킹·교통 제어도 완성 기능으로 취급하지 않는다.

## 5. 검증 상태

### 담당자 보고

인수인계서에 따르면 최신 실물 시험에서 4·6·8번 도착과 두 Segment 관측 완료를 확인했다. 마지막 관측의 유효 깊이·신뢰도 표본 부족으로 전체 결과는 `FAILED`다. 이전 실행에는 TF 시각 오류도 남아 있다.

이때 수확 작업 수 0은 과실이 전혀 없었다는 뜻이 아니다. 현재 구조에서는 구역 전체 관측을 마쳐야 작업 목록을 확정한다. 준비된 워커의 정상 미션 간 재사용 및 최신 구조의 Isaac Sim 전체 미션도 추가 확인 대상이다.

### 이번 직접 확인

- 첨부 코드의 환경 로더로 sim/real 설정 모두 정상 로드.
- 실제 그래프 로더로 두 그래프의 노드·엣지·약연결 성분 확인.
- 기존 오프라인 시험 **44개 통과**: 도착 검사 10, 16면 설정 5, 과실/윈도우 범위 12, 기존 Segment 흐름 13, 환경 설정 4.
- 이 44개에는 새 `scout_new`의 전체 State 흐름·`VisionRuntime`·실제 Nav2 전송 검증이 포함되지 않는다.
- 이 실행 환경에는 ROS 2·Isaac Sim이 없어 빌드·통신·가상/실물 주행을 실행하지 않았다. 인수인계서의 59개 통과 기록을 이번 재검증 결과로 계산하지 않았다.
- 문서 추가 전에 원본 ZIP의 모든 파일과 비교하여 실행 소스·설정이 변경되지 않았음을 확인했다.

실행한 오프라인 시험:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=robot/ros_ws/src/farm_navigation:robot/ros_ws/src/scout_robot:tests \
python -m unittest \
  test_scout_arrival test_scout_beds_16 test_scout_range test_scout_segments \
  robot/ros_ws/src/farm_navigation/test/test_configuration.py
```

## 6. 이후 작업 순서와 승인 범위

1. **시뮬 설정 분리:** 영상 프로파일과 출력 경로를 `sim/` 내부로 분리하고 기존 공통 설정 선택 기능으로 연결한다. 실물 설정은 유지한다.
2. **새 예찰 구조 단독 통합:** Isaac 장치 → 새 예찰 노드 → 관측 → 구역 완료 → 결과까지 먼저 검증한다. 1개 면 이후 여러 면, 취소·실패·두 번째 Goal 순으로 확인한다.
3. **주행 조건 일치:** 실제 농장 통로를 반영한 시뮬 그래프 연결을 검토하고 공통 그래프 추종 모드를 시험한다.
4. **공통 변경 승인:** 프로토콜, Segment별 작업 전달, 과실 처리 정책, 워커 경로 변경 등이 필요하면 대상 파일과 구체적인 변경안을 먼저 제시한다.
5. **수확·운송 통합:** 담당자가 제공하는 운영 인터페이스와 구현을 기준으로 연결한다. 이전 개별 시험을 운영 로직으로 자동 승격하지 않는다.

공통 변경 기록에는 이유·파일·승인 근거·전후 동작·실물 영향·검증·복원 방법을 남긴다. 현재 승인된 공통 실행 코드 변경은 없다.

## 7. 주요 근거 파일

- `docs/SUMMARY_인수인계서.md`, `docs/NAVIGATION_REFACTOR_HISTORY.md`
- `robot/ros_ws/src/scout_robot/scout_new/scout_node.py`, `scout_communication.py`, `vision_runtime.py`
- `robot/ros_ws/src/scout_robot/scout_new/states/navigation_move_state.py`, `segment_complete_state.py`, `section_complete_state.py`
- `robot/ros_ws/src/farm_navigation/farm_navigation/configuration.py`, `route.py`, `navigator.py`, `nav2_client.py`
- `robot/ros_ws/src/farm_bringup/launch/scout.launch.py`, `scout_survey.launch.py`, `harvest.launch.py`
- `robot/ros_ws/src/farm_interfaces/action/ScoutArea.action`, `msg/HarvestTask.msg`
- `robot/ros_ws/src/scout_robot/scout_robot/survey_policy.py`
- sim/real 환경·장치·예찰·비전·patrol 설정과 두 GeoJSON
