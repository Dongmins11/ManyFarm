# 수확로봇: 화단 진입 경로와 Window 좌표 이동

사용자 승인: 2026-10-07, `feat/apriltag-localization` 브랜치에서만 구현.

## 좌표와 메시지

예찰 `Survey.windows()`는 이미 팔 장착·작업 오프셋을 적용한 base 정차 위치를 map 좌표 `goal_pose`로 만든다. 수확에서는 이 값을 그대로 사용한다. Window의 내부 중심 좌표로 다시 해석하거나 오프셋을 중복 적용하지 않는다. 예찰의 기존 장착 파라미터가 현장 장치와 일치하는지는 통합 설정 담당자가 맞춰야 한다.

`HarvestTask.action` Goal에 `section_id`를 추가했다. 관제는 `ScoutArea.Result.section_id`와 그 결과의 `harvest_tasks`를 연결해 전달한다. 공유 `HarvestTask.msg`와 ScoutArea 인터페이스는 변경하지 않았다. window_id/task_id 문자열에서 section을 추정하지 않는다.

**인터페이스 변경 때문에 수확 서버와 목표 발신 PC의 farm_interfaces 및 해당 클라이언트를 모두 재빌드해야 한다.** 예전 빌드의 HarvestTask 클라이언트와 혼용하지 않는다. 새 타입에서 기존 graph_only 설정은 section_id가 빈 값이어도 동작하지만 route_then_pose는 등록된 화단 ID가 필요하다. 이전에 안내했던 section_id 없는 Goal 명령은 새 실물 설정에 사용할 수 없다.

## 실행 순서

1. 새 화단: `ComputeRoute` → 반환 경로 → `FollowPath` → 진입점 도착·정지 확인.
2. Window: 예찰이 보낸 goal_pose → `NavigateToPose` → 정차 위치·방향 확인.
3. 같은 화단의 후속 Window: 2번만 수행.
4. 다른 화단: 이전 화단의 명시적 exit 위치로 좌표 이동한 후 새 화단의 진입 경로를 계산.
5. 실패/취소 시 이후 단계는 실행하지 않는다. 요청한 액션 종료를 확인하며, 종료 확인 실패 시 기존 blocked 처리를 유지한다.

Route Server를 사용하는 것은 이번에 추가한 동작이다. 이전 실험/기존 Git의 자체 그래프 계산을 ComputeRoute였다고 소급해서 설명하지 않는다. Route Server 실패 시 임의 직선 또는 NavigateToPose로 접근을 대체하지 않는다.

작업 구간 NavigateToPose는 기존 Nav2 planner와 RPP를 사용한다. 목표를 그래프의 2cm 이내로 제한하지 않는다. Nav2의 원래 충돌 감지와 목표 검사, 속도 설정은 변경하지 않았다. 경로를 벗어나는 목표의 이동 가능성은 costmap/planner가 판단한다.

## 화단 문맥

문맥은 수확 서버 프로세스 내에 유지한다. 작업이 정상 종료된 뒤 같은 화단 요청이면 진입을 반복하지 않는다. 재시작/실패/취소 후에는 문맥을 해제한다. 마지막 도착 후 로봇이 외부에서 이동한 경우도 기존 max_start_distance_m을 사용해 감지하고 재접근한다. 새로운 수치 제한을 추가하지 않았다.

태그 begin/end는 기존 HarvestMission 범위에 두며, 두 단계 사이에서 보정 프로세스를 재시작하지 않는다. 보정 수식, AMCL TF 소유권, 관측 모델, 예찰 좌표 계산은 변경하지 않는다.

## 설정과 실제 적용 범위

- 실물 `robot/config/harvest/harvest_real.json`: movement_mode=route_then_pose.
- 현재 SEC_01은 기존 A 시험 구간: entry=11, 진입 방향 11→12, exit=11, 이탈 방향 11→10. 좌표는 기존 graph.geojson에서 읽는다. 11번은 기존 시험의 접근·회전 종료/태그 구간 시작 경계다.
- 작업 목표는 12/13으로 고정하지 않으며 수신 goal_pose를 사용한다.
- 현재 실물 접근 그래프는 시험용 10~13이다. 임의의 주차장·다른 화단에서 출발하는 전체 농장 접근 경로가 완성됐다는 뜻은 아니다. 실제 운영 그래프와 화단 ID/진입·이탈 노드는 환경 설정으로 확장해야 한다. 임의 엣지나 화단 좌표를 만들지 않았다.
- 예찰 지도 통일은 사용자가 예정한 후속 변경이다. 이 커밋은 예찰 지도와 map_id를 덮어쓰지 않았다. 실제 예찰 좌표 연동 전에 양쪽 지도·map_id·화단 정의를 통일해야 한다. 문자열만 변경하지 않는다.
- 시뮬의 기존 설정은 graph_only로 유지한다. 시뮬에서도 route_then_pose를 선택하려면 해당 환경의 section 정의와 route_server_params를 제공한다. 실물 11번 좌표를 시뮬에 복사하지 않았다.

## Launch와 의존성

기존 `harvest.launch.py`를 사용한다. route_then_pose이고 navigation=true일 때만 같은 namespace에서 nav2_route/route_server와 전용 lifecycle manager를 추가한다. 동일 환경 그래프를 graph_filepath로 주입하고 실물 /tf,/tf_static을 harvest namespace로 remap한다. navigation=false이면 Route Server도 외부 실행에 맡긴다.

기존 장치/Nav2/태그 실행과 중복 실행하지 않는다. 로봇에는 ComputeRoute 인터페이스를 제공하는 nav2_msgs와 nav2_route가 필요하다. 단순 ROS Jazzy 설치만으로 해당 backport가 준비됐다고 가정하지 않는다. 이전 현장 Route Server 설치를 사용하되 설치 버전의 액션 필드는 빌드/통합에서 확인한다.

공통 Navigator에는 선택적 route_planner 주입점만 추가했다. 인자를 전달하지 않는 예찰과 기존 graph_only 동작은 그대로다. 실제 ComputeRoute ROS 어댑터는 harvest_robot에 있다.

진행 단계는 task_events의 navigation 기록에 SECTION_APPROACH, WINDOW_MOVE, SECTION_EXIT로 남는다. 도착 시 SUCCESS는 이동 완료이며 팔 수확 완료가 아니다.

## 검증

- 신규 오프라인 30건: 첫 진입, 같은 화단 연속 작업, 화단 전환, 외부 이동/재시작, 취소/실패, 태그 시작·종료 유지, 좌표 무변환, ComputeRoute 거절/오류/늦은 승인 취소/경로 형상 보존.
- 기존 태그/연결 검사 + 새 Route Server launch 검사 32건 통과.
- Python 컴파일과 XML/YAML/진입 노드 유효성 검사.
- ROS/DDS, colcon 빌드, 설치된 ComputeRoute backport와의 호환성, 실물·Isaac 주행은 이 환경에서 실행하지 못했다. 테스트 더블을 사용한 계약 검증을 실물 검증으로 표현하지 않는다.

오프라인 실행:

```bash
python3 -m unittest discover -s robot/ros_ws/src/harvest_robot/test -v
python3 -m unittest discover -s robot/ros_ws/src/farm_tag_localization/test -v
```

되돌리기: 이번 커밋을 revert하고 인터페이스를 양쪽에서 재빌드한다. 코드 복원 없이 이전 HarvestTask 바이너리만 실행하지 않는다.
