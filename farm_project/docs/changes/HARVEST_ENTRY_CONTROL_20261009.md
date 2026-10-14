# 수확 진입 끝점 접근 제어 수정

기준 커밋: `9fefb4828e18215282cdf262d7d7a83a0f9244ef`.
2026-10-09 사용자 진입 제어 수정 승인. 예찰/scout_new, 공통 farm_navigation, 드라이버는 수정하지 않았다.

## 근거와 변경

사용자 제공 `harvest_recheck_debug_20261009_162459.tar.gz`의 task
`graph_test_d7c7c5913d7346a29e9db19dfd97da30`을 분석했다.
SECTION_APPROACH에서 끝났고 작업 구간에 들어가지 못했다. 첫 태그 보정 전 약 1.7초부터 오른쪽 회전 명령이 보인다.
로봇 좌표계의 마지막 경로점은 조금 오른쪽에 있지만 최종 경로 방향은 왼쪽 회전이 필요한 상태였다.
태그만이 원인이라고 단정할 수 없다. 마지막 충돌 셀이나 물리적 접촉을 이 분석으로 확정하지 않았다.

기존 RPP는 끝점이 0.4m보다 가까우면 실제 끝점을 곡률/경로 방향 참조로 사용한다.
추가 `HarvestApproach`는 `use_fixed_curvature_lookahead=true`, `curvature_lookahead_dist=0.4`,
`interpolate_curvature_after_goal=true`를 사용한다. 마지막 선분 방향으로 가상 참조점을 계산한다.
0.4m는 기존 lookahead_dist와 같아서 충분한 경로가 남아 있는 구간의 참조 계산을 보존한다.
최종 목표 위치·방향과 도착 허용치를 바꾸는 설정이 아니다. 방향 오차가 크면 필요한 제자리 정렬은 남는다.

선택 연결: harvest_real.json → HarvestNode의 approach_settings → 기존 Nav2Client의 controller_id → FollowPath Goal.
SECTION_APPROACH만 추가 프로파일, WINDOW_MOVE/SECTION_EXIT는 RPP. graph_only 또는 키 없는 기존 설정의 선택은 유지한다.
사전 검사에서 추가 프로파일 누락을 거절한다. 실행 중 Nav2 파라미터를 쓰지 않는다.
Nav2 설정의 기존 항목을 파싱 비교한 결과 추가 프로파일/등록 외의 모든 값은 동일했다.
11번 도착 후 정지 검사와 전환, 충돌 검사, Nav2 4cm/2.5도, 미션 5cm/3도는 유지했다.

## 직접 실행한 검증

- 실제 HarvestNode 클래스와 공통 Navigator/Nav2Client/RouteGraph를 사용한 오프라인 수확 검사 56개 PASS. ROS 통신·pose·motion은 대역이며 물리 시험은 아니다.
- AprilTag 검사 46개 PASS. check_runtime.py PASS.
- 새 검사: 진입/작업/이탈 controller_id, 키 없는 기존 설정, graph_only, 명시적 Route Server 방식, 잘못된 설정, 설치 플러그인 누락 시 Goal 0개, 도착/충돌 설정 보존.
- 공식 Jazzy RPP의 circleSegmentIntersection/getLookAheadPoint C++ 계산부를 그대로 추출해 g++로 컴파일했다. 메시지 자료형만 최소 대역으로 제공했다. 운영 소스나 Nav2 설치본을 변경하지 않았다.
- 녹화된 received_global_plan 340개 비교: 충분히 먼 점이 남은 165개는 기존/새 참조 계산 동일, 끝점 인근 175개는 참조 거리가 0.4m인 것을 확인했다.
- 다음은 해당 녹화 경로를 두 방식에 동일 입력한 결과다. 새 설정으로 주행한 궤적이나 충돌 검사 결과가 아니다.

| ROS 시각(s) | 목표 거리(m) | 최종 방향 오차(도) | 기존 참조 각도(도) | 새 참조 각도(도) |
|---|---:|---:|---:|---:|
| 1791530487.494 | 0.0837 | 5.34 | -8.46 | 2.48 |
| 1791530488.494 | 0.0628 | 9.32 | -7.80 | 6.67 |
| 1791530488.995 | 0.0622 | 11.48 | -5.71 | 8.85 |
| 1791530489.494 | 0.0617 | 13.56 | -3.67 | 10.94 |
| 1791530489.644 | 0.0610 | 14.27 | -2.99 | 11.68 |

양수는 로봇 기준 왼쪽이다. 첫 표본은 기존 -8.46도(6도 기준 초과)에서 새 +2.48도로 바뀌어 불필요한 오른쪽 제자리 회전 분기를 피한다.
후속 표본은 이미 틀어진 녹화 위치를 입력한 것이므로 새 설정에서도 왼쪽 정렬이 필요할 수 있다.
최종 위치/방향 허용치 만족 여부는 실제 목표 기준으로 계속 검사한다.

공식 소스: https://github.com/ros-navigation/navigation2/tree/jazzy/nav2_regulated_pure_pursuit_controller/src
계산부 원본 regulated_pure_pursuit_controller.cpp SHA256: `9f5f23dc174e2bfae10c502fdebecc37b65d5397039d0c2c4504404557101d85`.
PathHandler의 두 점 보존과 단일 점 입력 거절도 원본에서 확인했다. 프로젝트 Nav2Client도 2점 미만 Path를 거절한다.
다운로드한 Jazzy 소스와 로봇에 설치된 바이너리가 바이트 동일하다는 의미는 아니다.
원본 연구 소스/실행 바이너리는 프로젝트에 추가하지 않았다.

## 남은 확인과 복원

실제 설치된 RPP 프로파일 로딩·ROS 주행·태그 결합·차체 제동·충돌 검사 재현은 이 환경에서 실행하지 않았다.
로봇 빌드/사전 검사, 재시작 후 추가 제어기 파라미터 확인, 동일 출발 조건의 주행 로그 비교가 필요하다.
AMCL 시각 경고·카메라 종료 -11·물리 간격 오차는 별도 미해결이다. 실측 차체 옆면–벽 20cm 기준을 바꾸지 않았다.
되돌림: harvest_real.json의 approach_controller_id 키 제거 후 수확 노드를 재시작하면 기존 RPP를 선택한다.
전체 파일 복원은 적용 도구가 저장소 밖 ~/vmany_backups에 남긴 해당 파일만 사용한다.
commit/push·로봇 동기화·실행은 자동 수행하지 않는다.

## 2026-10-09 실물 적용 후 확인

이 절은 앞선 실물 재주행 미검증 기록 이후의 확인 결과다.

- 사용자 로봇 출력에서 harvest_robot 빌드와 check_runtime.py --ros 통과를 확인했다.
- 실행 중 HarvestApproach 등록 및 고정 곡률 lookahead 설정 적용을 확인했다.
- 작업 graph_test_5286d38532614b4aa6a641ff1a3a228e는 many_farm_v1의 SEC_01에서 14번 목표까지 SUCCESS로 종료했다.
- 사용자 관찰상 11번 진입의 흔들림과 불필요한 회전이 감소했다. 단일 주행 결과이며 반복 재현성은 아직 확인하지 않았다.
- 제공된 bag과 작업 이벤트 분석에서 11번 도착 오차는 약 1.56cm/0.93도, 14번은 약 2.21cm/1.24도였다. AMCL/TF 기준 오차이며 실제 벽 간격 실측값이 아니다.
- 태그 보정 요청 10회와 AMCL 수신을 확인했다. 10회 모두 TF 시각 경고가 남았으며 보정 정확도 검증 완료로 간주하지 않는다.
- 작업 끝부분 회전과 카메라 종료 -11은 해결 완료로 판정하지 않았다.
- PC RViz 설정에 Actual FollowPath와 Local costmap 표시를 추가했다.
- 분석 자료: harvest_entry_success_20261009_174834.tar.gz.
- 다음 단계: 코드·파라미터를 유지하고 유사한 출발 위치와 방향에서 14번 목표 주행을 2회 더 기록·비교한다.
