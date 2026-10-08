# 실물 카메라·드라이버 재현 자료 정리

기준: `feat/apriltag-localization`, `591a72cbdd2ec50eb16bc4c0a5f13715b0e2ed92`.
2026-10-08 사용자 승인으로 실물 외부 실행 파일을 저장소 안에 포함했다.

## 변경 내용

- `robot/tools/tag_camera/`: 받은 캡처 Python 3개. `opencv_camera_compare.py`, `trial_io.py`는 원본 그대로다.
- `pinky_tag_capture_compare.py`: 기본 경로를 프로젝트 기준으로 변경하고 `--calibration`을 추가했다. 기존 `--workspace`는 명시적으로 전달한 경우만 지원한다. 둘을 동시에 지정하면 실패한다.
- `robot/config/cameras/pcweb400_720p_report.json`: 받은 원본 그대로. SHA256 `7f0512b9f466fb12e36cc424331af727f516670cb9e179dd2c25d7ead8f10e31`.
- `harvest_tag_capture.yaml` 및 `capture_session.py`: 내부 script/calibration을 argv로 전달한다. 이전 workspace 설정도 지원하며 경로 둘 다 지정하거나 둘 다 없으면 실패한다.
- `robot/config/robots/vicpinky/driver_sources.json`, `patches/`: 정확한 원본 커밋, 현장 패치, 적용 후 파일 SHA256.
- `/runs/`를 프로젝트 .gitignore에 추가했다. 이미 추적 중인 과거 파일은 자동 삭제하지 않는다.

캡처 Domain178/LOCALHOST, 1280×720 MJPG 요청30fps·ROS발행 최대10Hz, 수동노출 요청2ms, ID100~106, 검은 변50mm를 유지한다. 로봇 통신 Domain156, AMCL 보정·주행 FSM·메시지는 변경하지 않았다. 캡처 파일의 기존 영어 주석은 원본 이력을 보존했다.

## 현재 로봇과 새 장비의 차이

현재 로봇은 `/home/vic/vicpinky_ws`와 설치된 ROS Jazzy를 계속 사용한다. 이미 현장 수정이 적용돼 있으므로 패치를 다시 적용하지 않는다.

새 장비를 준비할 때는 별도 신규 드라이버 체크아웃에서 manifest의 정확한 커밋을 확보한 뒤 패치를 적용한다. 기존 작업공간에 checkout/reset/clean을 실행하지 않는다. 아래는 **원본 커밋으로 준비된 신규 체크아웃**에서만 실행하는 예다.

```bash
git -C "$new_vic_pinky_checkout" apply --check "$project_root/robot/config/robots/vicpinky/patches/vic_pinky.patch"
git -C "$new_vic_pinky_checkout" apply "$project_root/robot/config/robots/vicpinky/patches/vic_pinky.patch"
git -C "$new_sllidar_checkout" apply --check "$project_root/robot/config/robots/vicpinky/patches/sllidar_ros2.patch"
git -C "$new_sllidar_checkout" apply "$project_root/robot/config/robots/vicpinky/patches/sllidar_ros2.patch"
```

Vic Pinky 패치는 기존 RPM `int` 절삭을 `round`로 바꾼 현장 수정과 진단 코드를 보존한다. 이번에 새 제어 수식을 적용한 것이 아니다. 라이다 패치는 `/dev/rplidar`, `laser_link`를 보존한다. 패치 전/후 파일은 git blob ID 및 첨부 파일과 대조했다. 전체 upstream 저장소 다운로드·빌드 재현은 이번 검증에 포함하지 않았다.

설치 환경은 별도다: ROS Jazzy, colcon, Nav2와 nav2_route, apriltag_ros/apriltag_msgs, image_proc, rmw_cyclonedds_cpp, Python OpenCV/NumPy/PyYAML, v4l2-ctl 등이 필요하다. 정확한 설치 버전 목록·udev 규칙 원본은 이번 첨부에 없다. `/dev/rplidar` 장치 연결, 모터/카메라 권한, `net.core.rmem_max`(캡처 요구 최소10MiB), 카메라 컨트롤 지원을 보존해야 한다. Git 복사만으로 새 OS 설정까지 재현되는 것은 아니다. 로봇은 인터넷이 없으므로 설치가 필요하면 PC에서 아키텍처·버전에 맞게 별도 준비한다.

## PC 업데이트와 로봇 동기화

PC에서 변경분과 브랜치를 확인한다. `git status --short`에 변경이 있다면 먼저 비교·보존한다. 자동 stash/reset은 하지 않는다.

```bash
cd /home/eunbi/vmany/main
git branch --show-current
git status --short
git pull --ff-only origin feat/apriltag-localization
```

다음은 PC→로봇 최초 적용 방향이다. 로봇에서 소스를 수정했다면 먼저 역방향 변경을 PC와 비교하고 병합한다. 아래는 양방향 충돌 해결 도구가 아니다. 삭제 옵션을 사용하지 않으며 `.git` 및 아키텍처별 빌드 결과를 복사하지 않는다.

```bash
rsync -anc --itemize-changes --no-owner --no-group \
  --exclude='.git' --exclude='build/' --exclude='install/' \
  --exclude='log/' --exclude='runs/' --exclude='__pycache__/' \
  --exclude='.venv/' --exclude='venv/' \
  /home/eunbi/vmany/main/ vic@192.168.0.12:/home/vic/vmany/main/
```

변경 목록이 이번 커밋과 일치하면 위 명령의 `-anc`를 `-ac`로 바꿔 복사한다. 이후 `-anc`로 다시 검사해 출력이 없는지 확인한다. 파일 삭제는 별도 확인 후 정확한 경로로 수행한다.

로봇에서:

```bash
source /opt/ros/jazzy/setup.bash
source /home/vic/vicpinky_ws/install/setup.bash
cd /home/vic/vmany/main/farm_project/robot/ros_ws
colcon build --symlink-install --packages-up-to farm_bringup harvest_robot farm_tag_localization farm_real_devices --executor sequential
source install/setup.bash
cd /home/vic/vmany/main/farm_project
python3 robot/tools/tag_camera/pinky_tag_capture_compare.py --trial-label manual_2ms --plan
```

`--plan`은 파일·캘리브레이션 검증이며 ROS/장치를 실행하지 않는다. 2026-10-08 현장에서는 새 Git 경로의 카메라 수신·태그 검출을 확인했다. 종료 오류가 남아 있어 기존 외부 카메라 두 폴더는 유지한다. 통합 launch·실물 주행·위치 보정은 미검증이다.

## 검증과 복원

직접 실행: `python3 -m unittest discover -s robot/ros_ws/src/farm_tag_localization/test -p test_bundled_capture.py -v` 6개 PASS. 다른 cwd·임시 HOME에서 과거 폴더 없이 plan 성공, 새 설정의 명령 경로, 공백 포함 경로, 기존 workspace 호환, 누락/중복 설정 거절, 변조 캘리브레이션 거절, 드라이버·기록 코드 원본 해시를 검사한다.

첨부한 드라이버 파일에 patch 역적용→원본 blob ID 접두사 확인→재적용→첨부본과 바이트 동일 확인을 두 저장소 모두 수행했다. 최초 이식 검증 당시에는 ROS 빌드·카메라 구동·실물 주행을 실행하지 않았다. 이후 현장 확인 결과는 아래에 별도로 기록한다.

실행 경로 복원은 `harvest_tag_capture.yaml`의 calibration을 제거하고 다음 값을 사용한다. 이전 외부 파일이 남아 있어야 하며 두 방식의 키를 동시에 설정하지 않는다.

```yaml
script: ~/manyfarm_experiments/pinky_tag_amcl_map_20261007/pinky_tag_capture_compare.py
workspace: ~/manyfarm_experiments/apriltag_code_0wj0bg/apriltag_field_execution_v1
```

카메라 원본: `pinky_camera_code_review.tar.gz`. 캘리브레이션·패치 원본: `pinky_runtime_sources.tar.gz`. 사용자 PC 백업은 `/home/eunbi/vmany_1/backup_20261008/home_vic/`. 현장 파일을 덮어쓰기 전에 항상 변경분을 비교한다.

## 2026-10-08 현장 적용 결과와 시스템 설정

사용자가 제공한 로봇 터미널 출력 기준이다.

- `farm_tag_localization` 단일 패키지 빌드와 내부 경로 `--plan` 검사 종료 코드 0.
- 최초 캡처는 `net.core.rmem_max=212992`로 사전 검사에서 실패했다.
- 수신 버퍼 상한을 `16777216`으로 적용한 뒤 새 Git 카메라 실행을 확인했다.
- 세션: `runs/harvest_tag/20261008_174148_gz365wxt`.
- Git 내부 캘리브레이션 사용, 1280×720 MJPG 캡처 약 30Hz, 영상·검출 수신 약 8~9Hz, 태그 103 지속 검출.
- `roi60`은 비어 있었다. 전체 화면 검출 성공이며 ROI 통과나 위치 정확도 검증은 아니다.
- 주행·위치 보정은 실행하지 않았다. 이미지 저장 요청도 없어 저장 프레임은 0이었다.
- 종료 시 camera와 monitor는 코드 0, 카메라 컨트롤 복원은 true였다.
- detector와 rectify는 각각 SIGINT를 받은 후 -11로 종료했다. `clean_shutdown=false`, `unexpected_exits=[]`, `startup_error=null`이었다.
- 수신 중 예기치 않은 종료는 기록되지 않았지만, 종료 충돌 원인은 미확인이다. 이를 정상 종료로 간주하지 않는다.
- 로봇에 `coredumpctl`이 없어 해당 도구를 통한 충돌 기록 확인은 수행하지 못했다.

### DDS 수신 버퍼 설정

저장소 파일: `robot/config/robots/vicpinky/sysctl/99-vicpinky-camera.conf`.

현재 로봇에는 `/etc/sysctl.d/99-vicpinky-camera.conf`를 생성하고
`sysctl -p`로 `net.core.rmem_max=16777216` 적용을 확인했다.
재부팅 후 실제 값 확인은 아직 하지 않았다.

새 장비에서는 기존 sysctl 설정과 대상 파일을 비교한 뒤 로봇에서 적용한다.
아래 `project_root`는 해당 장비의 프로젝트 경로로 지정한다.

```bash
project_root=/home/vic/vmany/main/farm_project
sudo install -m 0644 \
  "$project_root/robot/config/robots/vicpinky/sysctl/99-vicpinky-camera.conf" \
  /etc/sysctl.d/99-vicpinky-camera.conf
sudo sysctl -p /etc/sysctl.d/99-vicpinky-camera.conf
```

저장소 동기화만으로 `/etc` 설정이 적용되지는 않는다.

### 과거 자료 정리와 유지 항목

검증 완료된 PC 전체 백업은 덮어쓰거나 삭제하지 않았다.
로봇의 과거 진단 로그, apriltag data/results, telemetry_checks,
공유 사본, 과거 mapping/config/startup_params/toolkit 및 일회성 패치 도구를 정리했다.

다음 항목은 유지한다.

- 기존 카메라 두 폴더와 `apriltag_ws`의 남은 설정·도구: 종료 오류 확인 및 후속 정리 전까지 보류.
- `manyfarm_experiments/diagnostics`: `.bashrc`의 bringup 로그 저장 경로.
- `manyfarm_experiments/pinky_correction.lock`: 기존·새 보정 코드가 공유하는 중복 실행 방지 잠금. 실행 중 삭제하거나 경로를 임의 변경하지 않는다.
- `vicpinky_ws`, `vic_pinky_library`, `bmany_fleet_ws`, `ap` 및 시스템·사용자 설정.

로봇 `.bashrc`의 navigation 별칭은 Git의
`robot/config/maps/harvest_field_20261007/many_farm.yaml`을 사용하도록 변경됐다.
삭제한 홈 지도와 Git 지도가 동일하다는 의미는 아니다.
