# Farm Project

파프리카 예찰·수확·운송·분류를 연결하는 ROS 2 / Isaac Sim 프로젝트다. 현재 통합 실행 범위는 예찰과 수확 이동 시험이며, 수확 팔 작업은 생략한다.

- **Codex 시작:** [인수인계 및 공유 절차](docs/CODEX_HANDOFF.md)
- **현재 구현·통신·검증 상태:** [PROJECT_STATE](docs/PROJECT_STATE.md)
- **확정 설계·남은 결정:** [DECISIONS](docs/DECISIONS.md)
- **최신 시뮬 실행·로그:** [2026-10-06 실행 가이드](sim/docs/RUN_GUIDE_20261006.md)
- **예찰 상세 구조의 과거 인수 기록:** [2026-10-02 인수인계서](docs/SUMMARY_인수인계서.md)
- **최신 통신규약 반영:** [PROTOCOL-20261006-014](docs/changes/PROTOCOL-20261006-014.md)

## 실행 단위

| 목적 | launch |
|---|---|
| 예찰 로봇 | `farm_bringup scout.launch.py` 또는 시뮬용 `farm_sim_runtime scout.launch.py` |
| 수확 공통 서버·장치·주행 | `farm_bringup harvest.launch.py` |
| 수확 시뮬 및 박스 평가 | `farm_sim_runtime harvest.launch.py` |
| Isaac 환경 | `farm_sim_runtime isaac.launch.py` |
| RViz 모니터링 | `farm_bringup rviz.launch.py` |
| 예찰·수확 시뮬 전체 | `farm_sim_runtime all.launch.py`에 `harvest:=true` 지정 |

필수 Python·환경 인자와 빌드 절차는 최신 실행 가이드를 따른다. `farm_bringup all/transport/sorting.launch.py`는 이 통합 저장소에서 미구현 스텁이다. 수확 실물 장치 연결과 실제 팔 수확, 외부 관제 전체 연계는 별도 인수·검증 대상이다.

문서는 2026-10-06 코드 기준이며 이후 변경은 상태·결정·변경 기록을 함께 갱신한다.
