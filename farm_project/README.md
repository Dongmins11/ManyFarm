# Farm Project 실행 안내

현재 실행 절차는 [실물·시뮬 실행 가이드](docs/RUN_GUIDE_20261002.md)를 따른다.

- 로봇 단독: `farm_bringup scout.launch.py mode:=real` 또는 `farm_sim_runtime scout.launch.py`.
- 시뮬 환경만: `farm_sim_runtime isaac.launch.py`.
- 모니터링만: `farm_bringup rviz.launch.py`.
- 시뮬 전체: `farm_sim_runtime all.launch.py`.

로봇 launch는 장치·Nav2·예찰 서버를 기본 실행한다. 필수 경로와 Python 인자는 가이드 참조. 수확·운송 및 정식 관제는 아직 미구현이다.
