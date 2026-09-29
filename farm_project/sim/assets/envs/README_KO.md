# 파프리카 농장 자동 식재 · 열매 배치 v1

제공된 BG USD를 불러오고, 화분에 나무를 심고, 아치 지지대 양옆 바깥에 3색 파프리카를 배치합니다.
원본 GLB를 매번 임포트할 필요 없이 **변환된 USD와 텍스처, 기본 배치 결과를 함께 제공**합니다.

## 가장 빠른 확인

압축을 전부 푼 뒤 Isaac Sim에서 `output/farm_planted.usda`를 열면 기본 배치 결과를 볼 수 있습니다.
`output` 파일만 옮기지 마세요. `background`, `assets`, `output`의 상대 위치를 유지해야 합니다.
나무/열매/연결 줄기는 `/World/Vegetation/Bed_01` ~ `Bed_08` 아래에 있습니다.
리뷰 카메라는 `/World/Vegetation/ReviewCamera`입니다.

기본값은 화분당 나무 12그루, 초록 12개·빨강 12개·노랑 12개입니다.
전체 **화분 8개 / 나무 96그루 / 열매 288개**입니다. 실제 재배 밀도의 정답이 아니라 첫 배치 확인용 설정입니다.

## Python으로 Isaac Sim 실행 + 재배치

### Ubuntu · pip 설치형 Isaac Sim

Isaac Sim을 사용하는 가상환경을 활성화한 뒤, 이 폴더에서 실행합니다.

```bash
python run_isaacsim.py
```

### Ubuntu · Isaac Sim 배포본

Isaac Sim 설치 폴더의 `python.sh`로 실행합니다. 아래 경로를 실제 경로로 바꾸세요.

```bash
/path/to/isaac-sim/python.sh /path/to/TreePlacement_Auto/run_isaacsim.py
```

### Windows · Isaac Sim 배포본 (PowerShell)

```powershell
& "C:\isaac-sim\python.bat" "D:\TreePlacement_Auto\run_isaacsim.py"
```

pip 설치형은 Isaac Sim 가상환경에서 `python run_isaacsim.py`로 실행합니다.
**Blender Python이나 Isaac Sim Script Editor에 붙여 넣는 코드가 아닙니다.** 별도 터미널에서 실행하세요.
처음 실행은 셰이더 로딩 때문에 시간이 걸릴 수 있습니다. 생성 후 창을 닫으면 프로그램이 종료됩니다.

옵션:

```bash
python run_isaacsim.py --open-only
python run_isaacsim.py --build-only
python run_isaacsim.py --headless
python run_isaacsim.py --config my_config.json
```

- `--open-only`: 만들어진 결과를 그대로 열기. 기존 배치를 다시 만들지 않음.
- `--build-only`: GUI 없이 USD만 생성. 일반 Python에서도 `numpy`, `usd-core`가 있으면 실행 가능.
- `--headless`: 화면 없이 Isaac Sim 실행 → 생성·로딩 → 종료.
- 일반 실행은 설정에 맞춰 결과 USD를 다시 생성하므로, 결과 파일을 수동 편집했다면 먼저 별도 저장하세요.
- 배치가 불가능한 설정이면 오류를 내고 기존 결과 USD를 유지합니다.
- 원본 `background/fram_bg.usd`, `farm_framechanged.usdc`는 수정하지 않습니다.

## 개수·크기·위치 조절

`config.json`을 수정하고 다시 실행하세요. JSON에는 주석을 넣지 마세요.

| 설정 | 의미 / 기본값 |
|---|---|
| `plants_per_bed` | 화분당 나무 수. 기본 12 |
| `tree_variants` | 사용할 나무 종류. Tree_01 ~ Tree_06 |
| `tree_height_m` | 흙 기준 나무 높이 범위. 1.70~1.95m |
| `canopy_width_m` | 나무 X 방향 전체 폭. 0.94m |
| `canopy_length_m` | 나무 Y 방향 전체 폭. 0.62m |
| `fruit_counts_per_bed` | 화분당 색상별 정확한 개수. 0 가능 |
| `fruit_scale_range` | 원본 파프리카 대비 배율. 0.9~1.1 |
| `fruit_center_height_above_soil_m` | 흙 표면에서 열매 중심까지의 높이. 0.45~1.35m |
| `fruit_sides` | `both`: 양쪽 / `left`: 화분 로컬 -X / `right`: 로컬 +X |
| `wire_clearance_m` | 열매 전체와 지지대 외곽 사이 최소 여유. 0.025m |
| `fruit_gap_m` | 열매끼리의 최소 여유. 0.035m |
| `connect_stems` | 실제 나뭇가지 메시에서 열매 꼭지로 연결 줄기 생성 |
| `max_connector_length_m` | 연결 줄기 최대 길이. 0.65m |
| `seed` | 랜덤 시드. 같은 설정·시드면 같은 배치 |
| `bed_overrides` | 특정 화분만 개수·크기 등 다르게 설정 |

나무는 뿌리 원점을 유지하며 화분 폭·길이·높이에 맞춰 **축별로 스케일을 조정**합니다.
원본 비율을 그대로 보존하는 모드는 아닙니다. 나무 실루엣은 `canopy_width_m`, `canopy_length_m`, `tree_height_m`로 조절합니다.
열매는 등방 스케일을 사용하므로 원본 형태 비율을 유지합니다. 원본 높이는 꼭지 포함 약 11.7cm입니다.

색상별 개수 예:

```json
"fruit_counts_per_bed": {"green": 10, "red": 20, "yellow": 5}
```

모든 화분에 적용되므로 전체 개수는 각각 80, 160, 40개입니다.
특정 화분만 다르게 설정하려면:

```json
"bed_overrides": {
  "1": {
    "plants_per_bed": 8,
    "fruit_counts_per_bed": {"green": 5, "red": 15, "yellow": 0}
  },
  "2": {
    "fruit_counts_per_bed": {"green": 0, "red": 0, "yellow": 0}
  }
}
```

화분 번호: 1·2번은 x=-5, 3·4번은 x=-2, 5·6번은 x=2, 7·8번은 x=5입니다.
홀수는 y=-6, 짝수는 y=6입니다. 최종 USD의 실제 위치를 읽으므로 좌표를 수동으로 입력할 필요는 없습니다.
`seed`, `background`, `output`, 조명 설정은 전역 설정으로 사용하세요.

개수를 크게 늘려 공간이 부족하면 일부만 놓고 넘어가지 않고 오류를 냅니다.
이 경우 개수를 줄이거나 높이 범위를 넓히세요. 높이 범위는 나뭇가지가 존재하는 구간이어야 합니다.

## 배치 방식과 범위

- 제공된 USD의 `Trellis_Frame_XX`, `Soil_Surface_N`을 찾아 위치·크기를 읽습니다.
- 기존 GLB의 전시용 배열 위치는 제거하고, 나무 6종과 새 파프리카 3종만 사용합니다.
- 기존 `FRUITS_INDIVIDUAL`의 열매는 포함하지 않습니다.
- 열매의 모든 정점을 포함하는 구로 여유 거리를 계산합니다. 중심뿐 아니라 꼭지까지 지지대 바깥에 둡니다.
- 아치 지붕 위나 화분 앞뒤 끝에는 배치하지 않고, **긴 화분의 양옆 외측**에 배치합니다.
- 열매 높이·색·방향·크기를 무작위화하며 열매끼리 겹치지 않도록 검사합니다.
- 실제 줄기 메시의 표면 정점에서 파프리카 꼭지 최상단 정점까지 연결 줄기를 만듭니다.
- 연결 줄기와 잎의 와이어 통과, 잎·열매 간 가림, 가지의 생물학적 자연스러움까지 보장하지는 않습니다. 첫 실행 후 모양 조정이 필요할 수 있습니다.
- 나무·열매는 USD 인스턴스로 공유합니다. 개별 열매의 위치를 바꾸거나 제거할 때는 `Pepper_XXXX_color` 부모 Xform을 조작하면 됩니다.
- `crop:color`, `crop:bedId`, `crop:sourceTree`와 `output/farm_planted.report.json`에 ID·좌표를 남깁니다.
- 이 속성은 일반 USD 메타데이터이며, Replicator의 semantic label을 설정한 것은 아닙니다.
- 이번 작업은 **시각 배치 단계**입니다. 열매 동적 강체·충돌·수확 탈착·ROS2 발행·YOLO 라벨 생성은 포함하지 않습니다.

## 재질과 조명

GLB의 원본 텍스처 해상도를 유지하고 Base Color, Normal, Roughness, Metallic,
AO(있는 경우), 잎의 알파 마스크를 USD Preview Surface로 연결했습니다.
Y-up → Z-up, UV 좌표계와 Normal 텍스처 값 범위 변환을 적용했습니다.
Isaac Sim 렌더러에서의 실제 잎 투명도·색감은 실행 후 확인이 필요합니다.

BG의 `../hdri/sky.hdr`가 제공 ZIP에 없었습니다. 기본 설정에서는 결과 레이어에서 해당
텍스처 참조만 비우고 원래 DomeLight를 무텍스처 조명으로 사용합니다. 원본 BG는 그대로입니다.
따라서 기존 HDRI 사용 화면과 조명이 달라질 수 있습니다. 원본 HDRI가 있다면
이 패키지 최상위에 `hdri/sky.hdr`로 넣고 `python run_isaacsim.py`로 다시 생성하면 해당 참조가 정상 해석됩니다.

## 포함 파일

- `run_isaacsim.py`: Isaac Sim 실행·배치·열기
- `placement.py`: USD 배치 코드
- `config.json`: 수량·크기·범위 설정
- `prepare_assets.py`: 제공 GLB → USD 재변환 코드 (일반 사용 시 실행 불필요)
- `assets/`: 변환된 나무 6종·열매 3종, 원본 해상도 텍스처, 원점/가지 정보
- `background/`: 제공된 BG USD, USDC, 텍스처
- `output/farm_planted.usda`: 기본 배치 결과
- `output/farm_planted.report.json`: 열매·나무별 ID·위치·스케일
- `output/farm_planted.validation.json`: 기본 결과의 실제 검증 기록
- `validate_scene.py`: 참조/재질/열매 개수/열매 겹침/와이어 외측 검사

원본 GLB를 다시 변환해야 할 때만:

```bash
python prepare_assets.py --source /path/to/TreePlacement
python run_isaacsim.py --build-only
python validate_scene.py
```

`prepare_assets.py`는 이번에 제공된 두 GLB 구조를 위한 변환기입니다. 임의의 GLB 전체를 지원하는 범용 변환기가 아닙니다.
Isaac Sim 실행 환경에는 별도 `usd-core`를 추가 설치할 필요가 없습니다. 일반 Python으로 생성/검증만 할 경우 `python -m pip install numpy usd-core`가 필요합니다.

## 검증 범위

OpenUSD로 결과를 생성·재개방하고, 인스턴스 내부의 실제 메시 정점까지 검사했습니다.
기본 결과: 참조 및 재질 누락 0건, 화분 8개·나무 96그루·열매 288개,
열매 정점과 와이어의 보수적 외곽 경계 사이 최소 거리 약 0.0392m.
동일 시드 재생성, 화분별 설정, 열매 0개, 한쪽 배치, 배치 실패 시 기존 결과 보존도 확인했습니다.
**검증 환경에는 Isaac Sim/RTX가 없어 Isaac Sim 5.1 GUI 실행 및 최종 렌더링은 검증하지 못했습니다.**

API 참고:
- [NVIDIA Isaac Sim 5.1 SimulationApp](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/py/source/extensions/isaacsim.simulation_app/docs/index.html)
- [OpenUSD Preview Surface](https://openusd.org/dev/spec_usdpreviewsurface.html)

제공된 모델의 원래 이용 조건은 그대로 적용됩니다. 파프리카 출처 링크는 `source_licenses/`에 보존했습니다.
