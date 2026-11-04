# ManyFarm 발표 영상 — GUI 연출 촬영

**완료: 7종 GUI 촬영 + 20초 편집본 2종.** 9개 영상 모두 1080p·30fps, 프레임 수·전체 디코딩 검사 통과. 시작·중간·끝과 동작 구간의 추출 화면을 검수했다. [영상 모아보기](index.html) · [한글 자막 20초](ManyFarm_20s_captioned.mp4) · [무자막 20초](ManyFarm_20s_clean.mp4) · [검수·해시](manifest.json).

- 기획: [발표 영상 콘티](storyboard.md), 가이드 원격 커밋 `5ebbb1f`.
- 작업 시작 시 최신 원격 main: `4861193`. 로컬 작업 브랜치의 기준은 `integration/fleet-sim-clock-20261102` / `3bb5d0f`이며 기존 미커밋 작업을 보존했다. 두 코드가 동일하다는 의미는 아니다.
- 실행: Isaac Sim 5.1 GUI, `DISPLAY=:20.0`, `XAUTHORITY=/home/ysy/.Xauthority`. headless 촬영이 아니다.
- 용도: 시스템 동작 소개용 연출. 키프레임으로 차체·관절·과실·카메라를 움직이며 Nav2·정책·ROS Action 완료를 기다리지 않는다.
- 상세 배치·경로·바퀴·카메라 근거: [SHOT_NOTES.md](SHOT_NOTES.md). 컷별 원본 설정은 [settings/](settings/), 시작·중간·끝 및 주요 동작 미리보기는 [preview/](preview/)에 있다.

## 산출 규격과 편집

전 컷 **1920×1080 / 16:9 / 30fps / 무자막 MP4**다. 사용 동작 앞뒤에 각각 1초 여유를 둔다.

| 순서 | 파일 | 원본 규격 | 편집에 사용할 0-based 프레임 |
|---|---|---|---|
| 01 | [01_overview.mp4](01_overview.mp4) | 5초 / 150프레임 | `[30,120)` — 3초 |
| 02 | [02_scout.mp4](02_scout.mp4) | 5초 / 150프레임 | `[30,120)` — 3초 |
| 03 | [03_grasp.mp4](03_grasp.mp4) | 5초 / 150프레임 | `[30,120)` — 3초 |
| 04 | [04_deposit.mp4](04_deposit.mp4) | 5초 / 150프레임 | `[30,120)` — 3초 |
| 05 | [05_handoff.mp4](05_handoff.mp4) | 5초 / 150프레임 | `[30,120)` — 3초 |
| 06 | [06_transport.mp4](06_transport.mp4) | 4초 / 120프레임 | `[30,90)` — 2초 |
| 07 | [07_sorting.mp4](07_sorting.mp4) | 5초 / 150프레임 | `[30,120)` — 3초 |

각 구간을 순서대로 기본 컷으로 연결하면 **600프레임 / 20초**다. 대괄호의 끝 프레임은 포함하지 않는다. 03 마지막 파지와 04 시작에는 같은 과실·파지 자세를 사용한다. 자막은 후편집에서 추가하며, 원본에 성공률이나 실제 업무 처리시간을 표시하지 않는다.

## GUI 촬영 세션 실행

기존 촬영 세션이 종료된 상태에서 아래 명령을 실행한다. 남은 `request.json`을 먼저 지워 이전 촬영 요청이나 `{"quit":true}`가 새 세션에서 자동 실행되지 않게 한다. `ready.json`도 새 실행의 준비 완료 여부를 구분하도록 지운다.

```bash
cd /home/ysy/main/farm_project
capture_dir=sim/runs/presentation_video_20261104
rm -f "$capture_dir/request.json" "$capture_dir/ready.json"
DISPLAY=:20.0 XAUTHORITY=/home/ysy/.Xauthority \
  /home/ysy/isaac/env_isaaclab/bin/python \
  sim/tools/stage_portfolio_photos.py \
  --runtime "$capture_dir/settings" \
  --output "$capture_dir" --gui --all-beds \
  >> "$capture_dir/render.log" 2>&1
```

첫 터미널을 유지하고, `render.log`의 `PORTFOLIO_READY` 및 새 `ready.json` 생성 후 다른 터미널에서 촬영을 요청한다. `settings/fleet.json`·`settings/sorter.json`은 이 촬영 세션의 runtime 입력이다. 운영 시험을 새로 실행해 만들 필요가 없다.

## 한 컷 또는 7컷 재촬영

```bash
cd /home/ysy/main/farm_project
capture_dir=sim/runs/presentation_video_20261104

# 한 컷 미리보기
python3 sim/tools/request_presentation_capture.py --output "$capture_dir" \
  --preview "$capture_dir/settings/02_scout.json"

# 같은 컷의 MP4 원본 촬영
python3 sim/tools/request_presentation_capture.py --output "$capture_dir" \
  "$capture_dir/settings/02_scout.json"

# 전체 7컷 설정을 순서대로 지정
capture_settings=(
  "$capture_dir/settings/01_overview.json"
  "$capture_dir/settings/02_scout.json"
  "$capture_dir/settings/03_grasp.json"
  "$capture_dir/settings/04_deposit.json"
  "$capture_dir/settings/05_handoff.json"
  "$capture_dir/settings/06_transport.json"
  "$capture_dir/settings/07_sorting.json"
)
python3 sim/tools/request_presentation_capture.py --output "$capture_dir" \
  --preview "${capture_settings[@]}"
python3 sim/tools/request_presentation_capture.py --output "$capture_dir" \
  "${capture_settings[@]}"
```

요청 도구는 각 컷의 새 완료 JSON을 확인한 뒤 다음 컷을 요청한다. `--preview`를 생략하면 설정 파일 안의 `preview_only` 값과 관계없이 MP4를 촬영한다. 같은 이름의 컷을 다시 요청하면 해당 출력은 재생성된다. 한 GUI 세션에 요청 도구를 동시에 여러 개 실행하지 않는다.

## 촬영 세션 종료

현재 요청의 완료를 확인한 뒤 종료 요청을 보낸다. 다음 실행 전에는 위 절차대로 이 요청 파일을 제거한다.

```bash
cd /home/ysy/main/farm_project
python3 - <<'PY'
from pathlib import Path
p = Path('sim/runs/presentation_video_20261104/request.json')
tmp = p.with_suffix('.tmp')
tmp.write_text('{"quit":true}\n')
tmp.replace(p)
PY
```

## 결과 해석 범위

촬영용 세션의 표시·변환만 변경한다. 원본 USD·실물 설정·공통 업무 코드를 수정한 시험이 아니다. 이동에는 기록·설정의 경로와 자산 기하를 쓰지만 동역학·위치추정·실제 정책 성공을 검증하지 않는다. 05는 인계 위치 정렬, 06은 독립적으로 과실을 적재한 운송 장면이다. 03·04·07의 파지·분리·투입도 소개용 연출이며 실제 시험 성과로 집계하지 않는다.

## 이번 직접 확인 결과

- 원본: 6개 × 150프레임 + 운송 120프레임 = 1,020프레임. 모든 프레임에 새 렌더 참조 시각을 확인했고, 프레임 번호 누락 없음.
- 편집본: 각각 600프레임, 정확히 20초. H.264/yuv420p이며 오디오는 없다.
- 03 마지막 ↔ 04 첫 프레임: 관절, 과실 부착 변환, 과실·집게 월드 행렬의 차이 0.
- 선별 프리뷰의 잔상은 최종 연속 렌더 마지막 화면에서 보이지 않는다. 빨간 과실이 RED 함 내부에 놓인다.
- 바구니·손목 높이·관절 범위 검토는 [ARM_SHOT_NOTES.md](ARM_SHOT_NOTES.md), 실제 영상 추출 검수 화면은 [qa/](qa/) 참조. 전체 메시 충돌·동역학은 시험하지 않았다.
- 초기 렌더 참조값 처리 오류와 컷 전환 시 팔 재질 문제를 수정한 뒤 7개 원본을 모두 재촬영했다. 첫 편집 인코딩은 종료 신호로 불완전해져 재생성했고, 최종 2종 모두 검사 통과했다.
- 원격에서 최신 콘티를 가져왔고 기존 통합 브랜치/미커밋 작업을 보존했다. 이 문장의 코드 기준과 manifest의 git 항목은 촬영 당시 상태다. 이후 사용자 요청에 따른 게시 대상은 main이며, 아래 Git 게시 구성을 따른다.

편집·파일 검사를 다시 수행할 때(기존 7개 MP4 필요):

```bash
cd /home/ysy/main/farm_project
python3 sim/runs/presentation_video_20261104/assemble.py
python3 sim/runs/presentation_video_20261104/verify_delivery.py
```

GUI 재촬영에는 이 프로젝트의 USD·runtime 설정·Isaac 설치가 필요하다. 배포 ZIP은 영상과 촬영 설정·검수 자료이며 전체 프로젝트 자산 복사본이 아니다.

## Git 게시 구성

원본 7개와 편집본 2개, 촬영 도구·설정·검수 자료를 개별 파일로 게시한다. 같은 내용을 중복 저장하는 약 100MiB ZIP과 실행 중 임시 요청/로그는 Git에서 제외한다. 이 폴더의 파일을 내려받으면 `index.html`에서 영상을 확인할 수 있다.

`settings/fleet.json`은 동봉한 scout·harvest·transport·cycle_layout·stations 설정을 사용한다. 촬영 당시 원본 경로는 `fleet.capture-original.json`과 manifest에 보존했다. `verify_delivery.py`는 저장된 촬영 이력과 동봉 도구의 해시를 검사하며 촬영 당시 커밋 정보를 현재 체크아웃 값으로 덮어쓰지 않는다.
