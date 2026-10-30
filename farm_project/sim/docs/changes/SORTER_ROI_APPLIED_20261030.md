# 선별장 시뮬 ROI Y +5px 적용 및 전·후 이미지

2026-10-30 사용자 “수정 전 / 후 스크린샷 로그로 남겨놓고 수정해” 승인에 따라 적용. 기준18d0e000 + 기존 미커밋 변경 보존.

## 변경

- `sim/ros_ws/src/farm_sim_config/config/sorter_camera_zones.json`: 시뮬 전용 ROI 추가. A/B/D Y143→148, C Y142→147. X/폭/높이 유지.
- `sim/ros_ws/src/farm_sim_config/config/sorter_integration.json`: source_roi를 새 설정으로 연결. 기존 계약대로 source_workspace 기준 상대 경로를 사용한다. SorterScene과 시험 준비 도구가 이 경로를 그대로 읽는다.
- 기존 전달본 `sim/vendor/.../outputs/sorting_station/hcr_sim/zones.json`의 SHA256 불변 확인. 실물·공통 코드·HSV 임계값·팔 동작·3초 미검출 완료 조건은 변경하지 않았다.
- 운영 설정에서 해석한 실제 경로 및 ROI 좌표 검증, 영역 경계 검사, 기존 지도 검증, diff 공백 검사 통과. 새로운 시험 준비 시 적용되며 이전 시험의 runtime 설정은 이력 보존을 위해 수정하지 않았다.

## 이미지 로그

같은 실제 저장 RGB 위에 변경 전/후 검사 영역을 표시했다. 새 시뮬 실행 화면 캡처가 아니라 저장 영상의 검출 영역 대조 이미지다. 원본 RGB도 함께 보존했다.

| 입력 | 변경 전 | 변경 후(Y+5px) | 앞열 색상 정답 일치 |
|---|---|---|---|
| attempt03: 선별1개 후9개 잔류 | [전](../test_results/20261030_sorter_roi_applied/attempt03/before.png) | [후](../test_results/20261030_sorter_roi_applied/attempt03/after.png) | 0/4 → 4/4 |
| attempt01: 10개 투입 후 | [전](../test_results/20261030_sorter_roi_applied/attempt01/before.png) | [후](../test_results/20261030_sorter_roi_applied/attempt01/after.png) | 1/4 → 4/4 |

attempt03 적용 후 색상: A빨강/B노랑/C빨강/D노랑. 해당 색상 픽셀 비율은50.0%/38.2%/44.9%/28.7%로 기존8% 기준을 넘는다. 두 정지영상의 앞열4개 레인 평가이며 모든 과실 연속선별 성공 검증은 아니다.

전·후 설정 원본, 해석 경로, 검출 비율, SHA256은 [증거 폴더](../test_results/20261030_sorter_roi_applied/)에 저장. 적용 후 이미지는 새 운영 설정을 직접 읽어 생성하고 눈으로 영역 표시를 확인했다.

## 남은 검증과 복원

새 물리/팔 동작 시험은 이번에 실행하지 않았다. 다음은 새 ROI로 선별만 실행하여 앞 과실 제거 후 다음 과실의 검출·집기·보관·HOME 복귀를 확인하는 것이다.

복원은 sorter_integration.json의 source_roi를 `outputs/sorting_station/hcr_sim/zones.json`으로 되돌린다. 새 ROI 파일은 참조되지 않게 된다. 커밋/푸시 미실행.
