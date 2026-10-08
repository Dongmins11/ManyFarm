# AprilTag 농장 배치 및 수확 카메라 반영

기준: 2026-10-08 KST, main `450bf5f100a81986469a22aba47847d9c2619acc` + 기존 미커밋 작업 보존.
승인 근거: 사용자 요청의 bed별 태그 배치, 수확 카메라 장착/bringup 연결, 공용 주행 코드 인수 여부 확인. 시뮬 코드·자산·설정과 상태 문서를 수정했으며 공용 업무/주행/실물 코드는 수정하지 않았다.

## 적용 결과

`main/AprilTag/AprilTag_Awall_8m` 원본을 보존하고, sim에서 필요한 원본 규격/장착 JSON 및 100~114 PNG를 `sim/assets/apriltag/`에 복사했다. 사용자 확정에 따라 각 면에 원본 ID100~114를 반복 사용한다. 추가 고유 ID 패턴은 최종 자산에서 제거했다. 원본 100~114의 검은 패턴은 같은 사전의 회전0 패턴과 픽셀 단위로 일치한다.

16개 Section별 ID 범위는 `apriltag_layout.json`, 좌표·텍스처 경로는 `apriltag_map.json`에 있다. 사용자가 각 면에100~114 반복 및 구간 ID와 함께 식별하는 방식을 확정했다. 식별키는 `(section_id, tag_id)`이고 `requires_active_section=true`다. 구간 미확정·경계 모호 시 ID만으로 map pose를 선택해서는 안 된다. 실물 다른 벽의 설치 완료를 의미하지 않는다.

실제 USD의 Bed_Edge 16개는 길이8m, 외측면은 bed 중심에서0.5m, 상단0.2975m다. 종이는 폭0.064m×높이0.069m, 하단0.227m/상단0.296m로 벽 범위에 들어간다. 중심 피치0.564m, 검은 중심 높이0.264m, 종이 중심 높이0.2615m. 첫 종이 끝을 각 관측면 시작에 맞춰 검은 중심은32mm 안쪽이고 마지막 종이 끝은7.960m다. 텍스처는 통로를 향해 직립하며 벽 바깥1mm 오프셋으로 겹침을 피한다.

`apriltag_scene.py`가 `run_sim.py`/`run_fleet.py`의 session layer에 평면과 텍스처를 생성한다. 운영 scout/scout_fleet/harvest 설정에서 동일한 배치표를 선택한다. **USD를 단독으로 열면 원본에는 태그가 없고, 시뮬 런타임 시작 시 적용된다.** 원본 농장 USD·장애물 지도·주행 경로는 변경하지 않았다.

## 수확 카메라

URDF는 `sim/assets/robots/harvest_robot/urdf/harvest_robot.urdf`에 `apriltag_camera_optical_frame` 고정 링크를 추가했다. 구동축 중간 바닥 원점은 URDF의 base_link z0.087m, 바퀴 중심 상대 z−0.0048m, 반지름0.0822m로 확인했다. 기존 자산축과 논리 주행축은 yaw π 차이가 있으므로 제공된 optical 변환에 이 변환을 먼저 적용했다. 자산 기준 xyz는 `[+0.00433822, −0.25046456, +0.26142254]`m이며 논리 주행 기준에서는 제공값 그대로 왼쪽을 본다.

런타임은 기존 수확 USD의 실제 `base_link` 아래 Camera를 생성하므로 로봇 이동을 따른다. USD 본체를 URDF로 다시 임포트해 기존 물리 모델을 덮어쓰지 않는다. 외형 CAD/질량이 없는 웹캠은 광학 센서로만 추가했으며 임의 충돌체/질량을 넣지 않았다. 장착 수치는 전달자료의 추정값이고 실물 정밀 보정 완료로 취급하지 않는다. 예찰 카메라 위치·영상 조건은 유지했다.

`harvest.json`의 camera 활성화, 1280×720·10Hz, K/D/장착 행렬을 통해 기존 sim 장치 bringup이 `CameraSim` → 공유메모리 → `CameraRos`로 발행한다. 기존 `farm_bringup harvest.launch.py`가 sim 장치 어댑터를 포함하므로 공통 launch 수정은 불필요했다.

| 항목 | 설정 |
|---|---|
| RGB | `/harvest_01/apriltag_camera/image_raw`, rgb8, sensor-data QoS |
| CameraInfo | `/harvest_01/apriltag_camera/camera_info`, 영상과 같은 timestamp/frame |
| optical frame | `harvest_01/apriltag_camera_optical_frame` |
| 렌즈 | 전달 K/D를 Isaac5.1 OpenCV pinhole 모델로 적용 |
| 주기 | sim10Hz 목표. 실물 요청30fps/MJPG/노출2ms는 참고 조건으로 보존 |
| depth | 웹캠이므로 발행하지 않음. 기존 공통 버퍼의 depth 슬롯은 모두 NaN/미사용 |

실물 harvest 장치 bringup은 기존부터 미구현이다. 이번 적용은 sim 영상 발행까지이며 USB 드라이버·실물 노출 설정·검출기·주행 보정은 포함하지 않는다. 실물 실행부 인수 항목은 [주행 담당자 요청서](APRILTAG_NAVIGATION_REQUEST_20261008.md)에 정리했다. 외부 발송은 하지 않았다.

## 검증 및 한계

- 19개 검사 PASS: 15개 원본 PNG를 사용하는240개 배치의 패턴/디코드, 태그 간격/높이/구간 내 고유 ID, URDF optical 좌표, ROS Image/CameraInfo 시각·K/D 일치/이전 세션 거절, 센서 TF 계약, fleet 진입점, 기존 수확 UI 격리 설정. UI의 UDP 소켓 시험은 샌드박스 제한으로 처음3개 실패 후 로컬 소켓 허용 환경에서 전체 통과했다.
- USD 직접 검사 PASS: 실제 벽16개 안에 종이240개, 외측1mm·64×69mm 확인, 실제 로봇 USD 장착 optical 행렬과 전달 행렬 일치. 기존 sorting/빈 visuals reference 경고는 발생했으며 이번에 고치지 않았다.
- 실제 Isaac5.1/RTX4070SUPER headless 정차 렌더: SEC01 현행 수확 정차선에서1280×720 영상 생성, OpenCV로ID104 검출. 최종 시험은 `CameraSim.publish()`의 RGB 공유메모리 전달과 NaN depth도 확인. K/D 렌더 속성 조회 일치. `sim/runs/apriltag_20261008/`에 영상·JSON·로그 보관.
- sim3패키지 colcon build PASS, 기존371개 경로 검사 PASS, diff 공백 검사 PASS.
- ROS 검사는 실제 메시지 형식으로 생성한 단위 검사다. 전체 bringup의 DDS 수신/연속 주기, 다중 로봇 동시 카메라 부하, 양쪽 면 전체 영상 검출률, 주행 중 검출/보정, USB 실물 시험은 미실행이다. 실제 주행 보정 코드는 현재 로컬 인수본에 없다.
- 첫 렌더는 결과 저장 후 Kit 종료가 지연되어 해당 시험 프로세스만 종료했다. 최종 시험은 종료 대기를 제한해 실행했고 종료 상태는 `validation.json`에 기록한다. 영상 생성/검출 성공과 프로세스 정상 종료를 구분한다.

## 재현

프로젝트 `~/main/farm_project` 기준:

```bash
python3 sim/tools/build_apriltag_assets.py
source /opt/ros/jazzy/setup.bash
source robot/ros_ws/install/setup.bash
colcon --log-base sim/ros_ws/log build --base-paths sim/ros_ws/src \
  --build-base sim/ros_ws/build --install-base sim/ros_ws/install \
  --packages-select farm_sim_config farm_sim_devices farm_sim_runtime --symlink-install
source sim/ros_ws/install/setup.bash
```

이후 기존 `sim/docs/RUN_GUIDE_20261006.md`의 수확/fleet 실행을 재시작한다. sim 장치가 활성화된 수확 bringup에서 위 영상·CameraInfo가 발행된다. 태그 검출/주행 보정 노드를 자동으로 시작하지는 않는다.

설정 변경 시 `apriltag_layout.json` 및 `task.yaml`을 원본으로 generator를 재실행한다. 실제 벽이 바뀌면 `check_apriltag_scene.py`의 USD 검증도 다시 실행한다. 원본 A벽 지도 YAML의 원점은 이번 sim 태그 좌표에 복사하지 않았다.

되돌리기: device JSON의 `apriltag_map` 항목 제거 및 harvest camera.enabled=false로 런타임 태그/카메라를 비활성화하고 재시작한다. URDF의 이번 광학 고정 링크/조인트는 별도로 제거한다. 기존 사용자의 미커밋 수확 작업은 되돌리지 않는다.

미커밋·원격 미반영. 후속 작업은 주행 담당자 소스 인수, 실물 카메라 bringup 계약 확정, 검출/주행 보정 통합 및 주행 전후 비교다.

## 적용 파일 묶음

[AprilTag 적용 파일](../runs/apriltag_20261008/apriltag_sim_20261008.tar.gz). 이번에 수정한 파일만 포함한 현재 작업폴더 스냅샷이다. run_fleet/run_sim 및 상태 문서에는 작업 시작 전의 미커밋 수확 변경도 보존돼 있으므로 다른 기준 체크아웃에 적용할 때는 파일 차이를 먼저 확인한다. 현재 작업폴더에는 이미 적용됐다.

다운로드 후 동일 기준 프로젝트에 적용하는 명령:

```bash
cd ~/main/farm_project
tar -xzf ~/Downloads/apriltag_sim_20261008.tar.gz -C "$PWD"
```
