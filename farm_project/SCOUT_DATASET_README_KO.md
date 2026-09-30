# 예찰 카메라 추가 학습 데이터 생성 — v0.6.4

**v0.6.1 수정:** 라벨 대상을 16개 예찰 섹션 기준으로 수정했습니다. 같은 물리 베드의 반대편 열매도 제외합니다.

Isaac Sim 5.1용. 기존 `farm_project`에 파일을 추가하는 패키지입니다.
기존 주행·실시간 추론 코드는 이 패키지의 교체 대상이 아닙니다.

## 파프리카 회전 추가 — v0.6.3

패널의 **0. Random XYZ rotation (config) and SAVE** 버튼으로 현재 배치에 적용합니다.
red/yellow/green 전체 과실의 기존 회전을 유지하면서 로컬 X·Y·Z축에 각각 설정한 범위의 랜덤 오프셋을 추가합니다.
위치·scale은 유지하며, 같은 seed로 재실행해도 회전이 누적되지 않습니다.
촬영마다 재배치하는 기능이 아니라 맵에 한 번 적용해 저장하는 기능입니다.
기존 파일은 `*.before_rotation_날짜`로 백업됩니다.

패널 없이 Script Editor에서 바로 실행할 수도 있습니다. 경로는 실제 프로젝트 위치로 변경합니다.

```python
import runpy
runpy.run_path("/home/ysy/main/farm_project/sim/tools/randomize_pepper_rotation.py")
```

`sim/config/scout_dataset.json`의 다음 값을 수정합니다. 기본 최대각은 10°이며 상한을 10°로 제한하지 않습니다.

```json
"fruit_rotation": {
  "max_degrees": 25.0,
  "seed": 930
}
```

위 예시는 각 축에 -25°~+25°를 적용합니다. `max_degrees`는 0 이상인 유한한 숫자이며,
0이면 추가 회전을 없애 기존 회전으로 돌아갑니다. 다른 랜덤 배치를 원하면 `seed`를 변경합니다.
설정 저장 후 0번 버튼 또는 회전 스크립트를 다시 실행하면 적용됩니다.
버튼과 스크립트 모두 실행할 때마다 같은 설정 파일을 다시 읽습니다.
v0.6.2에서 코드 파일을 교체한 직후에는 Isaac Sim을 한 번 재시작해 모듈 캐시를 갱신합니다.
이후 JSON 값만 바꿀 때는 재시작할 필요가 없습니다.
촬영 CLI 자체는 회전 변경을 실행하지 않으므로, 회전 적용·맵 저장을 먼저 합니다.
회전 후에는 이후 촬영분에 새 모습이 반영됩니다. 이미 저장한 데이터셋은 바뀌지 않습니다.

## 파일명 타임스탬프 — v0.6.4

촬영 실행 시작 시각(UTC, 마이크로초 포함)을 이미지와 라벨 파일명에 함께 붙입니다.
예: `20260930_071250_123456_s930_BED_01_P01_00000.png`와 동일 이름의 `.txt`.
원본 RGB, GT 마스크, 미리보기, 프레임 메타데이터도 같은 이름을 사용합니다.
각 실행은 기존처럼 별도 폴더에 저장되며, 다른 실행 결과를 합칠 때도 파일명이 구분됩니다.
조명/HDRI를 바꾸고 촬영을 다시 시작하면 새 타임스탬프가 적용됩니다.
기존에 생성한 파일은 변경하지 않습니다.

## 적용과 실행

ZIP의 `farm_project` 폴더를 현재 프로젝트와 합칩니다. `env_isaaclab` 환경에서
프로젝트 폴더로 이동한 뒤 필요한 영상 처리 패키지를 설치합니다.

```bash
python -m pip install -r sim/tools/scout_dataset/requirements.txt
```

### 현재 열린 씬에서 실행

Isaac Sim Script Editor에서 아래 경로를 실제 프로젝트 경로에 맞춰 실행합니다.

```python
import runpy
runpy.run_path("/home/ysy/main/farm_project/sim/tools/scout_dataset_panel.py")
```

`Scout training dataset` 패널이 열립니다.

1. **Label Red/Yellow and SAVE current map**: 현재 열린 씬의 red/yellow 과실에 의미 라벨을 붙이고 원본 맵에 저장합니다. 기존 파일은 `*.before_labels_날짜`로 먼저 백업합니다.
2. Sections를 `BED_01`, Images per section을 `30`으로 설정하고 **Generate dataset**을 누르면 해당 구역에서 시험 촬영합니다.
3. 결과의 `previews`를 확인한 뒤 Sections를 `all`, 수량을 원하는 값으로 변경합니다.
4. **Stop generation**으로 중단하면 이미 저장한 프레임과 진행 기록은 남습니다.

패널의 `all`은 16개 예찰 면입니다. 실제 USD 베드는 8개이며, 양쪽 면에서 찍습니다.
생성 중에는 타임라인을 일시 정지합니다. 화면 갱신은 유지되며 촬영 진행은 터미널에 표시됩니다.
촬영 중에는 씬을 바꾸거나 다른 Replicator 작업을 시작하지 않습니다.

### 별도 프로세스로 실행

현재 작업 내용을 맵에 먼저 저장하고, 기존 Isaac Sim 창을 종료한 뒤 실행합니다.
기본 씬은 `sim/assets/envs/output/farm_with_plants_v5.usd`입니다.

```bash
# 라벨맵만 생성
python scripts/generate_scout_dataset.py --label-only

# BED_01에서 30장 시험 촬영
python scripts/generate_scout_dataset.py --sections BED_01 --frames-per-section 30

# 전체 16개 면 × 100장 = 총 1,600장
python scripts/generate_scout_dataset.py --sections all --frames-per-section 100 --headless

# 물리적인 USD Bed_02만, 양쪽 면에서 각 100장
python scripts/generate_scout_dataset.py --physical-beds 2 --frames-per-section 100

# 다른 최신 씬을 사용할 때
python scripts/generate_scout_dataset.py --scene /절대경로/current_scene.usd --sections BED_01 --frames-per-section 30
```

CLI와 패널의 촬영 기능은 원본과 같은 폴더에 `원본이름_vision_labeled.usd`를 저장합니다.
이미 같은 이름의 라벨맵이 있으면 `*.bak_날짜`로 백업합니다.
라벨맵은 기존 자산을 참조하므로 현재 프로젝트 폴더 구조를 유지해야 합니다.
현재 열린 원본 자체에 저장하는 기능은 패널의 1번 버튼입니다.

## 구현한 조건

| 요청 | 적용 방식 |
|---|---|
| Red/Yellow 의미 라벨 | 각 과실 최상위 Prim에 `class=pepper_red/pepper_yellow`, 소속 물리 베드·면·예찰 섹션, GT ID 저장 |
| 기존 모델 클래스 | `0: Red`, `1: Yellow`; green은 학습 라벨에서 제외 |
| 카메라 거리 | `Bed_Edge` 나무 프레임의 실제 월드 경계에서 카메라 광학 중심까지 수평 수직거리 **1.14m** |
| 랜덤 위치 | 베드 전체 길이 안에서 연속 균등 추출. segment나 경로 노드에 맞추지 않음 |
| 촬영 방향 | 선택한 베드 면의 안쪽을 바라봄. 기본 yaw 흔들림 0° |
| 높이·상하 각도 | 현재 씬의 `scout_camera` 월드 높이·pitch 사용. 조회한 자산은 약 0.60m, 수평 방향 |
| 대상 베드 필터 | 픽셀 인스턴스 ID → 실제 Prim 경로 → 과실 → 소속 물리 베드와 면(west/east)으로 판정 |
| 먼 열매 | RGB에는 그대로 보이며, 다른 섹션이면 같은 베드 반대편도 라벨에서 제외 |
| 가림 | 실제 보이는 마스크만 라벨링. 같은 열매의 여러 메시/가려진 조각은 하나의 인스턴스로 묶음 |
| 저장 | RGB 원본, 후처리 RGB, YOLO segmentation TXT, 정확한 가시 마스크, 오버레이, 촬영 조건 |

같은 물리 베드라도 반대편 열매는 라벨에서 제외합니다.
과실 배치점의 월드 좌표를 베드 중심선 기준으로 나눠 west/east 소속을 고정하고,
`graph.geojson`의 면→섹션 매핑으로 연결합니다. 화면상의 좌우 위치로 판정하지 않습니다.
중심선 위에 있어 소속이 불분명한 과실은 임의 배정하지 않고 오류를 표시합니다.
예: 물리 `Bed_01`의 west 면은 `BED_09`, east 면은 `BED_10`입니다.
`BED_09` 촬영에서는 `BED_10` 과실이 비쳐 보여도 라벨을 만들지 않습니다.
`crop:bedId`와 Prim 경로의 번호가 충돌하면 잘못된 라벨을 만들지 않도록 중단합니다.
원거리 여부를 추정하는 Depth 임계값이나 이미지상의 크기로 베드를 구분하지 않습니다.

## BED 번호 구분

기존 `graph.geojson`의 `survey_sections`에서 소속 관계를 읽습니다.

| 예찰 구역 | 실제 USD 베드 | 면 |
|---|---|---|
| BED_01 / BED_02 | Bed_02 | west / east |
| BED_03 / BED_04 | Bed_04 | west / east |
| BED_05 / BED_06 | Bed_06 | west / east |
| BED_07 / BED_08 | Bed_08 | west / east |
| BED_09 / BED_10 | Bed_01 | west / east |
| BED_11 / BED_12 | Bed_03 | west / east |
| BED_13 / BED_14 | Bed_05 | west / east |
| BED_15 / BED_16 | Bed_07 | west / east |

예를 들어 `--sections BED_02`는 실제 `Bed_02`의 east 면을 촬영합니다.
원하는 것이 물리 베드 번호라면 `--physical-beds` 옵션을 사용합니다.

## 설정과 후처리

설정 파일: `sim/config/scout_dataset.json`.

기본 출력은 **1280×720**입니다. 실제 씬의 scout 카메라 **가로 화각**을 유지하고,
출력 종횡비에 맞춰 세로 aperture를 조정합니다. 기존 자산의 5:3 렌즈 설정을
16:9 출력에 그대로 끼워 넣어 영상을 늘리지 않습니다.
사진만으로 D435의 실제 내부 파라미터를 복원한 것은 아닙니다.
실측 K가 있으면 `intrinsics_mode`를 `calibrated_K`로 바꾸고 출력 해상도에 맞는
3×3 K를 넣을 수 있습니다. 렌즈 왜곡 추가는 포함하지 않습니다.

첫 첨부 `rgb2.png`를 주 기준으로 한 **초기 후처리 프리셋**입니다.
노이즈·흐림·압축값은 센서를 정밀 교정한 결과가 아니며, 실제 추론 성능을 보며 조정합니다.

| 처리 | 기본 범위, 1280px 너비 기준 |
|---|---|
| Gaussian blur | sigma 0.35~0.70px |
| 조금 강한 defocus | 10% 확률, sigma 0.80~1.15px |
| 짧은 motion blur | 10% 확률, 3px 커널, 무작위 방향 |
| 공통 밝기 노이즈 | read sigma 0.5~1.3 / 255, 신호 의존 성분 추가 |
| 약한 색상 노이즈 | sigma 0.15~0.40 / 255 |
| 밝기·감마 | gain 0.96~1.04, gamma 0.97~1.03 |
| JPEG 흔적 | 20% 확률, quality 92~99; 최종 파일은 PNG |

후처리 순서는 **광학 흐림 → 밝기·감마 → 노이즈 → 압축**입니다.
RGB에만 적용하며 픽셀 크기, 크롭, 카메라 좌표, 마스크 위치는 바꾸지 않습니다.
한 시점당 후처리 이미지는 1장만 생성합니다. RGB 원본은 비교용이며 train에 중복 등록하지 않습니다.
`--no-postprocess`로 후처리를 끌 수 있습니다.

카메라 높이·yaw·pitch 흔들림의 기본값은 모두 0입니다. 현재 예찰 장착 조건을 유지하면서
길이 방향 위치만 바뀝니다. 필요한 경우 설정에서 작은 범위의 흔들림을 줄 수 있습니다.

## 결과 파일

매 실행마다 `runs/scout_dataset/날짜_시각_seed/`에 새 폴더를 만듭니다.

| 경로 | 내용 |
|---|---|
| `images/train`, `images/val` | 학습에 사용할 후처리 RGB |
| `labels/train`, `labels/val` | 같은 파일명의 YOLO segmentation TXT |
| `raw_rgb/train`, `raw_rgb/val` | 후처리 전 RGB |
| `gt_masks/train`, `gt_masks/val` | 라벨 대상 과실만 포함한 16bit 가시 마스크. 0=배경, 1..N=과실 |
| `previews` | 실제 학습 이미지 위에 정답 마스크와 TXT 폴리곤을 그린 검수 이미지 |
| `metadata` | 사진별 카메라 위치, 베드, 제외한 열매, 후처리 강도, 과실 Prim과 마스크 번호 |
| `session.json` | 유효 설정, 카메라 K, 실제 베드 경계와 클래스 목록 |
| `manifest.jsonl`, `summary.json` | 이미지 목록, 개수, 완료·실패 상태 |
| `data.yaml` | Ultralytics 데이터 설정 |

YOLO TXT는 `class x1 y1 x2 y2 ...` 형식이며 좌표는 0~1입니다.
한 과실은 한 줄입니다. 가려져 분리된 조각과 내부 구멍은 왕복 연결선을 가진 단일 폴리곤으로
변환합니다. TXT를 다시 래스터화하면 연결선 주변에 약 1px 차이가 생길 수 있어
정확한 원본 마스크도 함께 저장합니다. convex hull로 잎의 가림을 채우지 않습니다.
가시 픽셀 8개 미만이거나 유효 폴리곤이 없는 과실은 제외하며 그 이유를 metadata에 남깁니다.

## 학습 분리와 검수

기본 검증 베드는 물리 `Bed_07`, `Bed_08`입니다. 같은 물리 베드의 양쪽 면은 같은 split에
들어가므로 가까운 랜덤 시점이 train/val 양쪽에 나뉘는 것을 줄입니다.
전체 실행 기준 train 1,200장 / val 400장입니다. 수량은 면당 100장일 때의 값입니다.

`BED_01` 30장만 생성한 시험 실행에는 val 이미지가 없습니다. `summary.json`의
`train_and_val_present`가 true인 데이터셋에서 학습하거나, 기존 실사 검증셋에 연결합니다.
합성 검증 점수는 실사 성능을 대신하지 않습니다. 추가 학습에서는 기존 실사 데이터를 함께
사용하고, 실사 검증셋으로 전후 결과를 비교합니다.

요청한 정책대로 **다른 섹션(같은 베드 반대편 포함)의 보이는 열매에는 라벨이 없으므로, 일반 YOLO 학습에서는
그 열매도 배경으로 취급**합니다. 이 데이터셋은 예찰 시점에서 대상 섹션만 검출하는 목적에 맞춘 것입니다.

우선 `previews`에서 다음을 확인합니다.

- 대상 섹션 면의 red/yellow만 표시되는가.
- 같은 베드 반대편과 다른 베드 열매에는 라벨이 없는가.
- 가려진 부분을 마스크가 채우지 않는가.
- `raw_rgb`와 `images`를 비교했을 때 첫 실사 샘플과 비슷한 정도로 흐려지는가.

## 확인한 범위

- CPU 기능 검사 12개: 같은 베드 반대편 제외(양 방향), 회전된 베드의 면 판정, 거리·방향, 연속 위치, 회전된 베드, 다른 베드 제외, 매 프레임 ID 매핑,
  가림·분리 마스크, 후처리 재현성, 출력 마스크, 라벨맵 저장과 카메라 행렬.
- 제공된 농장 USD 구조: red 96개, yellow 96개, 물리 베드 8개.
- Bed_Edge 외곽 실측: 약 1.00m × 8.00m. 실제 렌더링 시 다시 현재 씬에서 측정합니다.
- 현재 제작 환경에는 Isaac Sim RTX 런타임이 없어 **실제 GPU 촬영은 실행하지 않았습니다**.
  패키지에는 학습 이미지가 포함되지 않습니다. 첫 30장으로 Replicator 출력과 라벨을 확인합니다.
- 자산이 누락되어 열매/나무 메시를 읽을 수 없으면 빈 씬으로 데이터를 만들지 않고 오류를 표시합니다.

## 기준 문서

- [NVIDIA Isaac Sim 5.1 Replicator 예제](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/replicator_tutorials/tutorial_replicator_getting_started.html)
- [NVIDIA Replicator instance segmentation API](https://docs.omniverse.nvidia.com/kit/docs/omni_replicator/1.12.27/source/extensions/omni.replicator.core/docs/API.html)
- [NVIDIA Synthetic Data Recorder 동기화와 subframes](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/replicator_tutorials/tutorial_replicator_recorder.html)
- [Ultralytics segmentation 데이터 형식](https://docs.ultralytics.com/datasets/segment/)
