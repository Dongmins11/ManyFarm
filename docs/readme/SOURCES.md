# README 자료 출처

작성일: 2026-11-04. 사용자 제공 발표 자료 4종과 `Robot3FinalProject/main`의 `c9a2369e4ab4a645f5decf129dd1386fa025076b` 커밋을 대조했습니다. 문서 작성 중 새로운 로봇·시뮬레이션 시험은 수행하지 않았습니다.

## 이미지

아래 이미지는 제공 자료에서 선택한 원본입니다. 저장소 안에서 참조하기 쉽도록 파일명만 변경했으며, 사진·그림의 내용과 비율은 변경하지 않았습니다.

| README 파일 | 제공 자료의 원본 | 유형 |
|---|---|---|
| `assets/farm-overview.png` | `simulation-presentation-pngs-20261031 (1).zip` → `originals/01-farm-overview.png` | 가상 농장 배치 연출 |
| `assets/scout-detection.png` | 같은 ZIP → `originals/02-scout-annotated.png` | 시뮬레이션 예찰 검출 기록 |
| `assets/harvest-sim.png` | 같은 ZIP → `originals/harvest-grasp-closeup.png` | 시뮬레이션 파지 자세 설명 화면 |
| `assets/harvest-real.jpeg` | `매니팜_조병현_발표_시각자료_v13 (1).zip` → `A13_실물_수확테스트.jpeg` | 실물 시험 |
| `assets/learning-control.png` | 같은 ZIP → `10_학습과_수확제어.png` | 학습·제어 설명도 |
| `assets/harvest-result.png` | 같은 ZIP → `14_수확결과.png` | 조건이 명시된 단일 팔 시뮬레이션 시험 결과 |
| `assets/sorting-real.jpeg` | 같은 ZIP → `A17_HCR_실물_선별장.jpeg` | 실물 선별장 |
| `assets/sorting-result.jpeg` | 같은 ZIP → `A34_HCR_색상별_분류결과.jpeg` | 실물 색상별 분류 결과 |
| `assets/transport-real.jpg` | `운송로봇_발표_사진자료_.zip` → `실물사진_1_20261023.jpg` | 실물 운송로봇 |
| `assets/transport-dump-cad.jpg` | 같은 ZIP → `CAD실물반영_dump.jpg` | 배출 기구 CAD 설계 |

시뮬레이션 이미지의 상세 출처와 실제 시험·연출 구분은 [기존 이미지 전달 기록](../../farm_project/sim/runs/presentation_stills_20261031/delivery/README.md)을 따릅니다. 전경 및 파지 자세 이미지는 전체 연속 작업 성공의 증거로 사용하지 않습니다.

## 수확 차체 설명과 시험 결과

`MANYFARM_Harvest_Presentation_20261031 (1).pptx`에서 다음 내용을 참고했습니다.

- 1·4·9장: 작업 위치 이동, 정차·수확, 인계, 다음 작업·복귀 흐름
- 5–8장: 컴포넌트 구조, 비동기 실행, 경로 계획과 Nav2 실행
- 11–15장: AprilTag 위치 추정과 AMCL 연동, 10/10 요청 적용 기록
- 16–21장: 관제·Jetson 연동, 준비·정지·차단 구분, 인계 이벤트와 자세 복구
- 22–26장: 복귀·두 벽 도킹과 시험 날짜·장치 조건
- 27–28장: 전체 연속 실행의 확인 범위와 향후 과제

2026-10-27 시험은 실제 차체와 PC 더미를 사용했습니다. 2026-10-30 도킹은 팔 상태를 생략한 차체 시험입니다. 이 결과를 실제 팔·운송을 포함한 동일 회차 전체 성공으로 합산하지 않습니다.

## 정책 학습과 수량 지표

v13 시각자료의 PPO·BC·DAgger·학습과 수확제어 도식, 단일 팔 수확 결과, 선별 프로그램 및 Modbus TCP 도식을 참고했습니다. 단일 팔 시험의 10/10·5/5는 5개 시뮬레이션 장면과 단계별 보조제어 조건에 한정됩니다. 학습 정책 단독 성능이나 실물 농장의 수확 성공률로 확대하지 않습니다.

최신 수량 손실 과제는 [예찰–수확–선별 손실 분석](../../farm_project/sim/docs/SCOUT_TO_SORT_LOSS_ANALYSIS.md)을 참고했습니다. 예찰 예상량, 실제 바구니 과실 수, 선별 수량은 서로 다른 지표입니다. 재사용한 시험 이력과 합성 데이터가 포함된 표를 독립적인 전체 시험 성공률로 바꾸지 않았습니다.

양팔 분담과 승강을 이용한 다높이 수확은 제공 자료에서 향후 목표로 제시된 구상입니다. 생성 구상도를 실제 장비 사진이나 구현 완료 증거로 사용하지 않았습니다.
