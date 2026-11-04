# ManyFarm 발표 영상 재촬영

[영상 모아보기](index.html) · [검수 지시 원문](review_instructions.md) · [규격·출처·SHA-256](manifest.json) · [시각 검수 기록](qa/visual_review.json)

**04 투입 → 07 선별 → 02 예찰 순서로 독립 Isaac Sim GUI에서 재촬영했다.** 세 영상은 각각 **1920×1080, 30fps, 5초/150프레임, H.264/yuv420p, 무음·무자막**이다. 앞뒤 1초는 편집 여유이고 사용할 동작 구간은 `[30,120)` 프레임이다. 기존 7종·03 파지·편집본·설정은 `../presentation_video_20261104/`에 보존했다.

원격 `origin/main`을 fetch한 뒤 `524a193901a2b4884825fab9bbdea861dd0b559d`의 리뷰를 읽었다. 촬영은 기존 작업 브랜치 `integration/fleet-sim-clock-20261102` / `3bb5d0f` 및 미커밋 작업을 유지한 상태에서 실행했다. 게시 기준 main과 촬영 당시 코드가 모두 같다는 의미는 아니다. 촬영 도구 사본·runtime 설정·일부 핵심 원본 소스 해시를 동봉한다.

## 구도와 변경

| 영상 | 내용 | eye (m) | target (m) | 초점 / 시선 |
|---|---|---|---|---|
| [04_deposit.mp4](04_deposit.mp4) | 투입 | `[-6.46555, 7.11459, 1.87087]` | `[-5.66555, 7.71459, 0.90518]` | 31.0mm / 하향 44.0° |
| [07_sorting.mp4](07_sorting.mp4) | 선별 | `[-9.06072, 15.45132, 2.00042]` | `[-7.27629, 14.54809, 0.6]` | 42mm / 하향 35.0° |
| [02_scout.mp4](02_scout.mp4) | 예찰 | `[-6.05, 10.2, 0.65]` | `[-6.25, 9.05, 0.4]` | 25mm / 하향 12.1° |

- **04:** 서로 다른 방향 A/B/C 9장을 비교하여 서남 A를 선택하고 카메라만 평행 이동했다. 기존 약78° 수직 시점에서44° 사선으로 변경. 팔 장착부·상판·손목·바구니 앞벽/내부와 안착 과실 윗부분이 보인다. 03 끝과04 시작의 관절·부착·과실/집게 월드 행렬은 같다. 과실 화면 위치 차이는 A 초안 약282px에서 약178px로 줄였다. 기존 fill800을 유지했다. [비교9장](qa/04_deposit-candidates.jpg) · [미세조정3장](qa/04_deposit-refined.jpg) · [최종 동작9장](qa/04_deposit-motion.jpg) · [좌표 근거](04_CAMERA_NOTES.md)
- **07:** 전방 사선 A(35°)를 선택했다. 높은 시작 팔이 잘리지 않고 최소 두 분류함이 구분되며 RED 위치의 과실이 보인다. 세션의 측면45° 면광원1.4×1.4m/intensity600, 약한 정면 fill65, f-number4.6으로 면 방향 명암을 살렸다. 기존 재질을 새로 칠하지 않았다. [비교9장](qa/07_sorting-candidates.jpg) · [최종 동작9장](qa/07_sorting-motion.jpg) · [기하·재질 근거](07_CAMERA_NOTES.md)
- **02:** A/B/C 9장 비교 후, 통로 북동쪽 D를 추가하고 시선만 미세 조정했다. 센서 높이 근처0.65m에서 촬영하고 로봇 높이는 화면 약60~66%다. 마스트·바퀴가 들어오고 보수적 외형 계산의 하단 최소 여백은 약7%다. 센서 앞면과 그 앞쪽 작물 열을 함께 담았다. 원래 직선0.4m를 유지하면서 카메라는70%인0.28m만 따라간다. 센서 장착·광학축·외형은 바꾸지 않았다. fill160/f-number4를 사용하고07 측면광은 껐다. [비교9장](qa/02_scout-candidates.jpg) · [추가 구도](qa/02_scout-probe.jpg) · [최종 구도](qa/02_scout-refined.jpg) · [최종 동작9장](qa/02_scout-motion.jpg) · [센서 근거](02_CAMERA_NOTES.md)

좌하단 `x80–650,y810–990`는 후편집 자막 자리다. 과실·집게·투입 중심을 이 영역에 놓지 않았다. 원본에는 자막을 넣지 않았다. 후보·최종 영상 모두 실제 Isaac 렌더 이미지를 열어 확인했다. PNG를 만들어 놓기만 한 검수가 아니다.

## 검증과 남은 한계

최종 검사 결과는 [validation.txt](validation.txt)에 있다. 세 MP4 전체 디코딩·150프레임·5초·1080p30·무음·해시, 450개 렌더 참조 시각 증가, 시작/중간/끝 메타데이터,03→04 정확한 연결을 검사한다. [원본 해시 목록](original_hashes.json)의 로컬179개 파일이 촬영 전과 동일함도 확인한다.

- 04 바구니가 깊어 안착 과실 아래쪽은 벽에 가린다. 윗부분은 보이며 약3.405초 이후 끝까지 유지된다. 벽을 없애거나 과실 높이·크기를 바꾸지 않았다.
- 07 자산은 단순한 회색 팔·흰 판넬이다. USD의 surface 재질 바인딩 상태를 확인한 뒤 조명으로 대비를 개선했다. 기존 농장 조명 그림자는 남는다. 최종 안착 상태는3.5초 이후 끝까지 보인다.
- 02 센서 외형은 작은 직육면체이며 렌즈 메시가 없다. 이를 임의로 추가하지 않았다. 전면 가시성과 전체 바퀴를 우선하여 작물을 화면 왼쪽에 두었다. 로봇 뒤를 작물로 가득 채우는 구도와는 차이가 있으며 통로 바닥·외곽 배경이 일부 남는다.
- 독립 세션 layer의 **연출 영상**이다. Nav2·ROS Action·정책 완료·동역학 성공을 시험한 기록이 아니며 실제 성공률로 집계하면 안 된다. 물체/관절/과실 키프레임은 기존 설정 그대로다. 원본 USD·공통 업무 코드·실물 설정은 이번 작업으로 변경하지 않았다.

## 재현

기존 촬영 세션을 종료한 뒤 새 출력 폴더를 지정한다. 아래 예시는 원본과 이번 결과를 덮어쓰지 않는 새 폴더를 사용한다. Isaac/프로젝트 자산은 별도로 필요하다.

```bash
cd /home/ysy/main/farm_project
retake_dir=sim/runs/presentation_video_retake_20261104
capture_dir=sim/runs/presentation_video_retake_reproduce
mkdir -p "$capture_dir"
DISPLAY=:20.0 XAUTHORITY=/home/ysy/.Xauthority \
  /home/ysy/isaac/env_isaaclab/bin/python sim/tools/stage_portfolio_photos.py \
  --gui --all-beds --runtime "$retake_dir/settings" --output "$capture_dir"
```

`PORTFOLIO_READY`와 새 `ready.json`을 확인하고 두 번째 터미널에서 실행한다. GUI 요청은 동시에 여러 개 보내지 않는다.

```bash
cd /home/ysy/main/farm_project
retake_dir=sim/runs/presentation_video_retake_20261104
capture_dir=sim/runs/presentation_video_retake_reproduce
python3 sim/tools/request_presentation_capture.py --output "$capture_dir" \
  "$retake_dir/settings/04_deposit.json" \
  "$retake_dir/settings/07_sorting.json" \
  "$retake_dir/settings/02_scout.json"

# 게시된 결과를 읽기 전용으로 다시 검사(기존03 메타데이터 필요)
python3 "$retake_dir/verify_delivery.py"
```

촬영 도구 변경은 선택적 측면 조명·노출, 후보 프레임 지정·프리뷰 잔상 안정화에 한정했다. 기존 MP4의 자세당 렌더6회는 유지하고, 점프하는 프리뷰 자세의 렌더 대기는 기본48회로 늘렸다. 새 측면광·노출 옵션을 쓰지 않으면 조명 기본값은 유지한다. Git에는 세 영상·설정·후보/최종 검수 자료·문서를 포함하고 임시 요청·ready·실행 로그·중복 ZIP은 제외한다.
