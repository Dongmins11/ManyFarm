# 예찰–선별 실행 기록 집계

집계 기준: 현재 로컬 sim/runs, sim/docs/test_results 및 기존 runs의 결과 파일. 원본 로그를 변경하지 않았다. 동일 선별 task_id의 복사본은 중복 제외했다.

**전체 사이클 성공 9회 = 새 전체 실행 4회 + 예찰·수확 재사용 완료 5회.** 새 전체 실행 4회는 기존 complete() 판정도 통과한다. 선별 액션 SUCCESS지만 전체 사이클 실패인 기록은 별도 3회다.

성공은 실행 액션·복귀 기준이며 과실 전량 선별 성공과 다르다. 재사용 기록은 독립된 새 예찰–선별 실험으로 합산하면 안 된다. 현재 기록으로 독립 실험 16회 또는 16개 SEC 성공을 주장할 수 없다.

## 16행 정리표

행 번호는 SEC 번호가 아니다. 1~12는 서로 다른 기록이고 13~16은 미확보이며, 성공률 계산의 실험 수에 넣지 않는다.

| 행 | 실제 SEC | 구분 | 투입 → 선별 | 원본 결과 |
|---:|---|---|---|---|
| 01 | SEC01 | 새 전체 실행 성공 | 12 → 9 | [기록](../runs/section_full_cycle_return_20261031_165651/attempt_006/result.json) |
| 02 | SEC03 | 새 전체 실행 성공 | 11 → 7 | [기록](../runs/sec02_departure_recovery_20261101/sec03_to_sec16/attempt_010/result.json) |
| 03 | SEC04 | 새 전체 실행 성공 | 11 → 10 | [기록](../runs/wall_approach_recovery_20261102/fresh_sec04_to_sec16/SEC04/result.json) |
| 04 | SEC05 | 새 전체 실행 성공 | 13 → 10 | [기록](../runs/amcl_alpha1_recovery_20261102/retry_sec05_to_sec16/SEC05/result.json) |
| 05 | SEC01 | 예찰·수확 재사용 완료 | 10 → 1 | [기록](../runs/transport_full_resume_20261029_attempt03/result.json) |
| 06 | SEC01 | 예찰·수확 재사용 완료 | 10 → 10 | [기록](../runs/transport_full_resume_20261030_roi05_attempt01/result.json) |
| 07 | SEC02 | 예찰·수확 재사용 완료 | 11 → 11 | [기록](../runs/sec02_departure_recovery_20261101/attempt_001/result.json) |
| 08 | SEC04 | 예찰·수확 재사용 완료 | 10 → 8 | [기록](../runs/sec04_idle_recovery_20261102/attempt_003/result.json) |
| 09 | SEC04 | 예찰·수확 재사용 완료 | 12 → 12 | [기록](../runs/wall_approach_recovery_20261102/attempt_002/result.json) |
| 10 | SEC01 | 선별 액션 성공 / 전체 실패 | 13 → 13 | [기록](../runs/fresh_full_cycle_20261030_114723_after_push/attempt_002/result.json) |
| 11 | SEC01 | 선별 액션 성공 / 전체 실패 | 13 → 8 | [기록](../runs/section_full_cycle_return_20261031_165651/attempt_001/result.json) |
| 12 | SEC02 | 선별 액션 성공 / 전체 실패 | 11 → 8 | [기록](../runs/sec02_restore_resume_20261101/attempt_001/result.json) |
| 13 | — | 미확보·미측정 | — | — |
| 14 | — | 미확보·미측정 | — | — |
| 15 | — | 미확보·미측정 | — | — |
| 16 | — | 미확보·미측정 | — | — |

## 전체 실패 기록의 제외 이유

- fresh_full_cycle_20261030_114723_after_push/attempt_002: 예찰 로봇 복귀 실패. 선별 13/13 완료와 전체 성공은 구분.
- section_full_cycle_return_20261031_165651/attempt_001: 당시 전량 선별 조건에서 8/13으로 실패. 이후 완화된 집계 기준으로 과거 실패를 성공으로 바꾸지 않음.
- sec02_restore_resume_20261101/attempt_001: 이전 예찰·수확 재사용, 수확 로봇 복귀 실패.

## 중복 제외한 복사본

- sim/docs/test_results/20261030_roi05_cycle/result.json
- sim/runs/portfolio_capture_20261030/worktree/farm_project/sim/docs/test_results/20261030_roi05_cycle/result.json

## 보고서에 사용할 수 있는 문장

“신규 예찰부터 선별 및 로봇 복귀까지 연속 완료한 실행은 4회다. 기존 예찰·수확 결과를 재사용한 복구·인계 실행 5회도 완료했다. 각 실행의 선별 수량은 별도 성능 지표로 집계했다.”
