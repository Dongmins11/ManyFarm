# 모형 치수 기준 파프리카 geometry v2

기존 `src/Pepper_RL_Demo/assets`와 공통 pepper 원본은 그대로 보존한다. `Pepper_Red_v2.usda`, `Pepper_Yellow_v2.usda`, `Pepper_Green_v2.usda`를 새 장면에서 명시적으로 참조하여 사용한다. 이 v2는 과실 형상 버전이며 `attachment_version=2`를 뜻하지 않는다. 기존 수확 환경 및 진행 중인 Student 시연 수집은 자동 전환하지 않는다.

| 항목 | v2 값 | 해석 |
|---|---:|---|
| 몸통 최대 폭 | 0.067 m | 사용자 치수 |
| 몸통 높이 | 0.077 m | 꼭지 제외, 사용자 그림 해석 |
| 하단 최대 폭 | 0.035 m | 아래 15% 구간으로 임시 해석 |
| 다른 횡방향 두께 | 약 0.063443 m | 미실측; 원본 XY 비율 유지 |
| 꼭지 포함 전체 높이 | 약 0.083293 m | 새 형상에서 계산한 값, 실측 전체 높이 아님 |
| 질량 | 0.009 kg | 기존 실측값 유지 |
| 몸통/파지 기준 중심 | (0,0,-0.0077) m | v2 root의 local 좌표 |
| 꼭지 연결점 | 약 (0.016779,0.012049,0.037093) m | `manifest.json`의 색상별 값을 사용 |

사진에서 두께와 하단 폭 측정 높이는 확인할 수 없다. 최대 폭을 두 XY 축 모두 6.7cm로 강제하지 않고 원본 비율을 유지한다. 하단 15%에서 최대 횡폭3.5cm를 적용하고 몸통 높이50%까지 매끄럽게 원래 비율로 연결한다. 끝면 단면 직경을 뜻하지 않는다. 높이는 자산의 넓은 몸통 분리 기준으로 측정한다. STL 수준의 실물 형상 스캔이 아니다.

시각 mesh의 점과 숨겨진 `/Pepper/Collision`에 같은 변환을 적용하며 collision은 기존 mesh-contact 계열과 같은 convex decomposition이다. 표시만 작게 만들고 충돌을 크게 남겨두지 않는다. 색/UV/재질은 원본을 참조하고 변형 후 normals를 다시 계산한다. 연결점에도 동일한 변환을 적용한다. USD 질량중심은 위 파지 기준 중심으로 근사하며 실제 모형 질량중심 실측은 아니다. CCD를 유지하고 결합 힘·마찰·반발을 새로 보정한 것으로 취급하지 않는다.

원본 USD는 최대 폭 약9.053cm/꼭지 포함 높이11.705cm지만, 현재 수확 RL은 별도 스케일로 폭7.0cm/전체7.5cm를 사용한다. v2 폭은 원본 USD보다 약26.0%, 현재 RL보다 약4.3% 작다. 현재 RL 몸통은 약6.934cm이므로 v2 몸통7.7cm는 약11.1% 길다. 전체 형상을 동일 비율로 축소하는 모델은 아니다.

## 생성/검증

생성 코드와 SI 치수 설정은 각각 아래에 있다. Isaac GPU나 현재 수집 프로세스를 실행/종료하지 않는 오프라인 USD 생성기다.

- `src/smartfarm_description/scripts/generate_pepper_v2.py`
- `src/smartfarm_description/scripts/pepper_model_v2_geometry.py`
- `src/smartfarm_description/config/pepper_model_v2.json`

이미 생성된 `v2`를 덮어쓰지 않는다. 설정 수정 후 확인은 새 경로를 지정한다:

```bash
/home/bhc/isaac/env_isaaclab/bin/python \
  src/smartfarm_description/scripts/generate_pepper_v2.py \
  --output "outputs/harvest_rl/pepper_v2_check_$(date +%Y%m%d_%H%M%S_%N)"

/home/bhc/isaac/env_isaaclab/bin/python -m unittest discover \
  -s src/smartfarm_description/tests -p test_pepper_model_v2.py

/home/bhc/isaac/env_isaaclab/bin/python \
  src/smartfarm_description/scripts/generate_pepper_v2.py --verify
```

`manifest.json`에는 치수·연결점·변환·원본/출력 SHA256과 사진 출처를 기록한다. 원본 mesh/material/texture 참조가 필요하므로 v2 USD만 단독 복사하지 않는다. 이 디렉터리와 참조 원본을 함께 전달한다.

검증 결과: 치수/원본 불변/연결점/두께 비율/잘못된 설정 거부 테스트5개 통과. 저장 후 다시 연 세 색상 USD의 참조·변환이 적용된 시각 mesh와 충돌 mesh 좌표가 모두 일치하고 질량9g 및 원본 hash가 일치한다. [형상 비교 그림](../../../../../outputs/harvest_rl/pepper_geometry_v2_review_20261007/shape_comparison.png)은 원본 USD, 현재 RL v1, 실측 기반 v2를 같은 눈금으로 보여준다. 접촉 동역학이나 수확 성능 시험 결과는 아니다.

## 수확 정책 환경에 연결할 때

v2 USD를 지정하고 **새 환경 프로파일/캐시/데이터 버전**으로 구분한다. 기존 원본 자산을 덮어쓰거나 `fruit_asset()`에 다시 넣어 기존 7cm/7.5cm 스케일을 곱하지 않는다. world root 위치는 기존 후보 위치를 유지하고 연결점은 `manifest.json`의 새 값을 적용한다.

현재 RL은 `diameter`, `length`를 TCP/파지 중심·보수적인 박스 판정에도 사용한다. v2용 대응은 `diameter=0.067`, `length=0.09625`이며 이 length는 기존 수식의 `body height=length×0.8`에 맞춘 **판정 매개변수**다. v2의 실제 전체 높이0.083293m와 다르다. 새 파지 중심은 `-length×0.08=-0.0077m`다. 기존 length 주석의 '꼭지 포함 전체 높이'를 그대로 해석해서는 안 된다. `pepper_model_v2.json`에서 이 차이를 명시했다.

Teacher는 기존 크기로 학습됐다. v2 재사용에는 별도 크기 전이 계약과 workspace/TCP·실제 박스 충돌 경계 검증이 필요하다. 과실 USD만 교체하고 현재 고정 Teacher/관측 출처 검사를 우회하지 않는다. 이 작업에서는 해당 정책 크기 전이, 전체 수확 평가, 새 v2 학습·시연 수집을 실행하지 않았다. 현재 수집이 끝난 뒤 v2 전체 연결 평가를 먼저 하고, 성공을 확인한 자료만 v2 Student 데이터로 새로 준비한다. v1 자료와 묵시 혼합하지 않는다.
