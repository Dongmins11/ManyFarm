# 실물 예찰 주행 설정과 시뮬 정렬

사용자 요청 “시뮬설정도 실제랑 동일하게 세팅해”에 따라 인수본의 `robot/config/environments/scout_real.yaml` 및 `robot/config/robots/burger/nav2.yaml`을 읽고 sim 설정에 적용했다. 공통 코드와 실물 파일은 수정하지 않았다. 실물 담당자가 현장에서 실행한 값이라는 의미가 아니라 전달된 파일과의 일치다.

## 동일하게 적용한 설정

| 항목 | 시뮬 적용값 |
|---|---|
| 미션 주행 모드 | follow_path |
| 선택 controller | RPP / RegulatedPurePursuitController |
| controller 주기 | 10Hz |
| 목표 선속도 | 0.15m/s |
| 고정 lookahead | 0.15m |
| 방향 정렬 각속도 | 0.35rad/s |
| goal checker | goal_checker / SimpleGoalChecker |
| Nav2 도착 허용오차 | 0.03m / 0.05236rad |
| 미션 최종 도착 허용오차 | 0.08m / 0.12rad |
| progress checker | 0.1m 이동 / 10초 |
| 경로 시작·목표 대응 허용거리 | 0.1m / 0.02m |
| Path 보간 간격 | 0.04m |
| 속도 제한 | 선속도 ±0.15m/s, 각속도 ±1rad/s |
| 가속·감속 제한 | 선형 ±2.5m/s², 각도 ±3.2rad/s² |
| inflation | 반경 0.3m, cost_scaling_factor 20 |

navigation 블록은 base_frame만 시뮬 프레임을 유지하고 실물과 일치시켰다. controller_server와 velocity_smoother 블록도 use_sim_time 및 odom_topic만 시뮬용으로 유지했다. RPP의 비용 기반 감속 설정과 일치하도록 local/global costmap의 inflation_layer도 실물값으로 맞췄다.

실물 controller 구성에 있는 `FollowPath`라는 ID의 DWB 플러그인도 같은 구성으로 포함된다. **FollowPath 액션 이름과 controller ID는 별개**다. 예찰 미션은 FollowPath 액션을 호출하면서 controller_id=RPP를 명시하므로 RPP가 선택된다. RViz에서 직접 보내는 NavigateToPose Goal의 컨트롤러 선택은 별개다.

## 시뮬 고유값으로 유지한 설정

- 연결 그래프, 지도, 16개 구역·80개 관측점, station 좌표.
- scout_01/base_footprint 및 scout_01/odom 프레임과 센서 토픽.
- use_sim_time=true, 가상 장치·센서 설정 및 AMCL station 초기 pose.
- 시뮬 로봇 반경 0.12m, LiDAR 감지 범위, costmap 센서 레이어, AMCL 보정값 등 환경·모델 관련 설정.

따라서 주행 방식과 선택된 제어 설정은 실물과 같지만, Nav2 파일 전체가 바이트 단위로 같은 것은 아니다. 실제와 시뮬의 지도/센서/좌표계를 섞지 않는다. 구형 시뮬 속도 제한(0.12m/s)과 가감속 튜닝은 이번 요청으로 실물값으로 변경했다.

## 적용과 검증

누적 패치에는 연결 경로 복원과 station 자동 배치가 포함된다. 적용 후 `bash scripts/build.sh sim`을 실행하고 Nav2·예찰·Isaac 실행부를 모두 재시작한다. 기존 시뮬 전용 launch 명령을 그대로 사용한다.

현재 공통 로더로 양 환경 설정을 읽어 주행 설정·플러그인 ID 일치 및 goal checker 허용오차를 검사했다. 371개 그래프 경로 계산과 station 시험 6개가 통과했다. 결과는 `FOLLOWPATH_VALIDATION_20261002.json`에 있다. ROS/Isaac 실주행·colcon 빌드는 이 환경에서 수행하지 않았다.

FollowPath가 그래프를 사용하도록 전환한 것이며 다중 로봇 교통 제어, 자동 station 복귀, 도킹 기능을 추가한 것은 아니다. 수확·운송 런타임은 이번 변경 대상이 아니다.

원복은 적용 전 시뮬 설정 백업을 사용한다. `navigation.mode`만 되돌리면 RPP/속도/goal checker 튜닝까지 이전 상태로 돌아가는 것은 아니다.
