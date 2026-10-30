# 선별 ROI +5px 적용 후 사이클 1회 결과

## 결과

**운송 출발 → 인계·수확 자세 복원 → 선별장 도킹·투입 → 10개 전량 선별 → 운송·수확 스테이션 복귀 모두 성공했다.** 액션 실패/105 결과/시뮬 재시작 없이 단일시도를 마쳤다.

- 실제 투입10개, 선별10개(빨강6/노랑4), 미선별0개. all_input_fruits_sorted=true. 물리 보고와 ROS 결과 수량 일치.
- 이전 ROI 시험은10개 중1개, 이번은10개 중10개다. 이는 이번 배치의 선별 결과이며 예찰·수확 성능을 새로 측정한 것이 아니다.
- 예찰·수확 완료 기록 재사용. 기존9윈도우/수확집계7개와 바구니 실제10개 차이는 그대로 보존했다. 새 예찰→새 수확 전체 사이클 시험으로 표현하지 않는다.
- 약29분33초: 시험 첫 로그00:28:02부터 수확복귀 Result00:57:34까지(KST, 2026-10-30). 선별 액션은약5분44초. 시작 전 프로세스 준비·종료 정리 시간은 제외한다.

## 단계별 실제 결과 (KST)

| 단계 | 결과 | 완료 시각 |
|---|---|---|
| 운송 도킹·인계·이격 | TransportPickup SUCCESS | 00:36:26 |
| 수확 인계·윈도우 복원 | DockTransfer SUCCESS / transfer·clear·restore 모두true | 00:37:47 |
| 선별장 이동·도킹·투입·이격 | BucketUnload SUCCESS / 기존과실10개 투입 | 00:43:13 |
| 선별·보관·HOME 복귀 | SortBatch SUCCESS / 빨강6·노랑4 | 00:48:57 |
| 운송 스테이션 복귀 | ReturnToStation SUCCESS / docked=true | 00:53:07 |
| 수확 스테이션 복귀 | ReturnToStation SUCCESS / docked=true | 00:57:34 |

물리 로그에10회 DONE이 기록됐고 과실10개 모두sorted=true다. 최종 카메라 영상의 레인도 비어 있다. ACTION의 SUCCESS만으로 전량선별을 판단하지 않았다.

## 조건 및 보존 범위

- 사용자 “이제 사이클테스트 한번 해봐” 요청. 기준 main18d0e000d4c98e3478e0a8510d84948561fc7d5f + 기존 미커밋 변경.
- ROS Domain13/SUBNET, headless CPU물리60Hz/render30Hz. 태그 위치보정은 인계·복원에서 미사용.
- 새 시뮬 ROI의 Y+5px 적용 경로 확인. 수확 AMCL alpha4=.002, 기존 뚜껑 임시고정·완료판정·가상인계/가상투입 방식 유지.
- 선별팔은 기존 기능 근사 모델·보조고정 파지다. 실물 선별 성능 검증이 아니다. 전체 관제 HTTP/교통관제 연동 검증이 아닌 기존 직접액션 시퀀스다.
- 이번에는 설정/제어코드 추가 변경 없이 시험1회와 관측자료 기록만 실행했다. 자동재시도 없음. 반복 배치/다른색배치/새 수확 데이터 일반화는 미검증이다.

## 영상·로그

- [투입 후 실제 영상](../test_results/20261030_roi05_cycle/camera_milestones/loaded_10.png)
- [전량 선별 후 실제 영상](../test_results/20261030_roi05_cycle/sorting_camera_rgb.png)
- [최종 전체 결과](../test_results/20261030_roi05_cycle/result.json)
- [선별·운송 결과](../test_results/20261030_roi05_cycle/sorter_transport_result.json)
- [단계별 타임라인](../test_results/20261030_roi05_cycle/action_timeline.json)
- [카메라 상태 변화 기록](../test_results/20261030_roi05_cycle/camera_index.jsonl)

원시로그: sim/runs/transport_full_resume_20261030_roi05_attempt01/. 세션63f2f248b9e041a3ba939404e70a351a. 원본영상164장을 camera_history/에 저장했고 수량1~10 단계별 대표영상/상태 및 SHA256은 sim/docs/test_results/20261030_roi05_cycle/에 보존했다. 영상은 runtime의약1sim초 저장주기이므로 상태와 정확히 동시촬영으로 취급하지 않는다. 관측기에서 파일저장 도중 읽은 PNG3건은 디코딩 실패로 건너뛰었고, 보존한164장 모두 디코딩 검증 통과. 로봇/카메라 액션 실패가 아니다.

시험·카메라 관측기 종료 확인. 종료 정리 중 gate=1/precision=-2는 SIGINT 정리 결과이며 probe/post_sorter/Isaac/로봇들은0 종료했다. 기존 관제는 유지했다. 커밋/푸시 미실행.
