# 실물 브랜치 추가 업데이트 확인 — 2026-10-27

- 사용자 요청: 교통 시험 반영분 커밋·푸시 및 실물 브랜치 재확인. fetch 성공, 원격 main은 로컬 HEAD68e5ef7과 동일.
- 실물 origin/feat/harvest-handoff-real-20261018: 5ff5b50 → **48d2d1c812a968058254ddb2355ee5dfc9b96c68**, 2026-10-27 15:32:29 KST, Hyaline-52.
- 커밋: `fix(harvest): 복귀 완료 판정 완화 및 다음 window 연속 주행 검증`. 9파일 변경.

## 실제 변경

- robot/config/environments/harvest_handoff_real.yaml: 일반 주행 heading_tolerance_rad=6도 명시. 공통 기본 설정 변경 아님.
- robot/config/robots/vicpinky/transfer/handoff_fsm.json: 정지 후 return_position=.05m, return_endpoint_position=.05m, return_heading=6도.
- harvest_robot/handoff_planning.py: 선택 프로필에서 정지 후 끝점 완료 허용치를 실행 중 경로 한계와 분리. 실행 중 motion_heading=min(return_heading,3도) 유지. 미지정 프로필은 기존 판정 유지.
- harvest_robot/handoff_window.py: 보정 이동 중 이탈 검사에 완료용6도가 아니라 motion_heading을 사용.
- 인수인계/결정/상태/성공 기준 문서 갱신. 경로·충돌·취소·실제 정지 검사 유지라고 기록됨.

## 실물 담당자가 기록한 검증

`docs/changes/HARVEST_SUCCESS_FREEZE_20261027.md`에 인계·복귀 및 다음 window 성공1회가 기록됨:
- 15:17:48 수확 SUCCESS(PC더미2개)
- 15:20:06 인계 SUCCESS, transfer_complete/transport_clear/restore_complete=true
- 15:20:32 다음 window 수확 SUCCESS(PC더미2개), 목표(2.181,-.035)

이 기록은 실물 차체 이동 + PC 더미 팔 시험이다. 실제 팔·실제 운송 도킹 전체 연동/반복 신뢰성/기존 주행 오류 전체 해결로 확대하지 않는다. 이번 담당자가 직접 재현한 실기 검증은 아니다.

## 시뮬 영향과 처리

직전 비교 이후 실물 프로필의 방향/복귀 완료 조건이 다시 달라졌다. 시뮬의 성공률 비교 시 이 차이를 기록해야 한다. 실물 최신 전체 통합본 수령 후 공통 코드와 환경별 조건을 다시 대조한다. 이번 커밋·푸시에는 이 검토 기록만 포함하며 실물 브랜치 코드 병합이나 시뮬 허용치 변경은 하지 않는다.
