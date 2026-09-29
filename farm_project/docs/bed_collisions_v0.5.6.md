# 베드 collision 복구 v0.5.6

제공받은 farm_framechanged.usdc의 GrowBed 메시 8개와 Bed_Edge 메시 16개에 PhysicsCollisionAPI가 없었습니다. 제공된 farm_bg.usd와 농장 씬의 상위 레이어에도 이 베드들에 collision을 추가하는 설정이 없었습니다. 현재 LiDAR는 렌더링 메시 대신 PhysX raycast_all을 사용하므로 collision이 없는 베드는 측정하지 않습니다. 최근 경로/feedback 변경이 collision을 제거했다는 근거는 찾지 못했습니다.

실행 시 /World/farm_framechanged 바로 아래의 GrowBed_*와 Bed_Edge_* 그룹에 있는 Mesh를 검사합니다. 빠진 collision을 추가하고 명시적으로 꺼져 있으면 켭니다. 새로 추가하는 충돌 형상은 현재 직육면체 메시용 convexHull이며 기존 활성 충돌 형상의 approximation 설정은 보존합니다. 동적 rigid body는 추가하지 않습니다.

원본 USD를 저장하지 않고 session layer에만 설정합니다. 바닥·로봇·벽·나무에는 변경을 적용하지 않습니다. 대상 배경이나 베드 메시를 못 찾으면 경로 문제를 알리는 오류로 중단합니다.

시뮬레이션 physics 초기화 전에 호출되므로 bringup을 완전히 종료하고 재시작해야 합니다. 시작 로그에서 다음을 확인하세요.

```text
[farm_sim] bed collision: {"mesh_count": 24, "added": 24, "enabled": 0, "existing": 0, ...}
```

기존 USD에 이미 collision이 있으면 added 대신 existing 또는 enabled로 집계됩니다.

## 적용

예찰 작업과 서버를 종료하고, Isaac Sim을 실행한 bringup도 종료합니다.

```bash
unzip -o ~/Downloads/farm_bed_collision_v0.5.6.zip -d ~/main/
cd ~/main/farm_project &&
source scripts/env.sh sim &&
(cd sim/ros_ws && colcon build --packages-select farm_sim_runtime)
```

```bash
cd ~/main/farm_project &&
source scripts/env.sh sim &&
ros2 launch farm_bringup scout.launch.py mode:=sim navigation:=true rviz:=true \
  isaac_python:=/home/ysy/isaac/env_isaaclab/bin/python \
  assets_root:="$HOME/main/farm_project/sim/assets"
```

먼저 정지 상태에서 RViz LiDAR 점이 베드 가장자리에 나타나는지 확인합니다. 여전히 없으면 시작 로그의 bed collision 줄과 RViz 화면을 함께 확인해야 합니다. 이번 점검은 사용자 PC에서 실행 중인 씬을 직접 측정한 것이 아니므로 센서 높이, 로드된 씬 차이, PhysX query 설정 등의 추가 원인이 남을 수 있습니다.

USD 오프라인 검증: 누락/비활성/기존 충돌체 처리, 대상 이외 메시 무변경, root layer 무변경, 반복 적용, 누락 배경 오류를 검증했습니다. 실제 제공 배경의 24개 메시에도 적용해 원본 파일 해시가 변하지 않음을 확인했습니다. 실제 Isaac Sim PhysX raycast는 이 환경에서 실행하지 못했습니다.

기존 점유 맵을 바꾸지는 않습니다. LiDAR 관측에 베드가 빠지면 맵과의 불일치로 AMCL 위치 추정에 영향을 줄 수 있지만, 이전에 관찰한 반복 회전의 원인이 이것이라고 아직 확정할 수는 없습니다.
