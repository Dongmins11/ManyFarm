# 관제 전체 Route 미표시 수정 — 2026-10-28

## 원인과 변경

현재 실행 관제의 `/api/live/snapshot?profile=simul`에서 예찰/수확 graph가 mismatch, “저장 Route와 배경 지도가 다릅니다 · 표시 보류”였다. Route 미리보기 토픽은 live였다. backend/live.py는 전체 graph를 saved_routes.overlay 결과로 선택하고, saved_routes.py는 저장 지도와 ROS OccupancyGrid의 좌표계·크기·해상도·원점 및 점유 픽셀 digest 일치를 요구한다. 표시 검사 버그가 아니라 저장 자산 갱신 누락이다.

Frontend/dashboard/config/environments.yaml의 simul.saved_routes는 선별장 추가 전 지도와 그래프를 가리켰다. 그래프의 선별장 노드8004도 기존 (5,13.25)였다. 현재 시뮬은 HCR 점유지도와 (-7,13.25) 접근점을 사용한다.

사용자 지도 변경으로 인한 Route 문제 조치 요청에 따라 다음 관제 표시 자산만 동기화했다. 로봇 공통/실물 제어·Nav2·판정 및 Frontend backend 소스는 변경하지 않았다.

- `Frontend/dashboard/maps/saved_routes/simul/count_test_farm_map.yaml`: 현재 `hcr_farm_map.yaml` 내용과 동일하게 교체. 실행 중 관제가 읽는 기존 YAML 경로는 유지하고 image는 hcr_farm_map.png를 참조한다.
- 같은 폴더 `hcr_farm_map.png`: 현재 시뮬 점유지도 원본 복사. 과거 count_test_farm_map.png는 역사 자료로 보존하며 새 YAML에서는 사용하지 않는다.
- 같은 폴더 `graph.geojson`, `harvest_graph.geojson`: 현재 로봇이 읽는 원본과 바이트 동일하게 동기화.
- `maps/saved_routes/manifest.json`: simul 원본 경로/해시/날짜 갱신, real 항목 보존.

## 검증

현재 ROS 점유 digest와 HCR 저장 지도의 digest 일치: `ac1ca24475af14941c7fa62e25f6aa9ec1e101dafbe1aacbca8a9637b156ca82`.

실행 중 관제 API에서 graph가 mismatch→saved로 전환됐다. 예찰211노드/452연결, 수확143노드/260연결, 양쪽8004좌표(-7,13.25). 기존 캐시가 파일 변경을 감지해 자동 반영했으며 서버/시뮬 재시작·업무 취소는 하지 않았다. 브라우저 화면 육안 검사는 미실시; API가 렌더링용 노드/선을 반환하는 것으로 확인했다. 기존 `backend/tests/test_saved_routes.py` 5PASS. venv에 pytest가 없어 설치 대신 시스템 pytest 경로를 추가해 같은 venv에서 실행했다.

운송 graph는 원래 저장 설정/발행 데이터가 없어 waiting이며 이번의 예찰·수확 mismatch 수정과 구분한다. 운송 표시를 새로 구현하거나 전체 공유 backend 정책을 변경한 것은 아니다.

근거: `sim/docs/test_results/20261028_frontend_route_sync/`. 원본 백업과 전체 API snapshot은 `sim/runs/frontend_route_sync_20261028/`. 복원은 before/의 관제 상대경로와 manifest_before.json을 원래 위치로 복사한다. 이전 지도로 복원하면 현재 HCR ROS 지도에서는 다시 표시가 보류된다.

기준 프로젝트18d0e00+기존 미커밋 변경. Frontend는 현재 상위 저장소에서 미추적 전달본이다. 커밋/푸시는 하지 않았다.

## 변경 파일 묶음

[변경 ZIP](../../runs/frontend_route_sync_20261028_changes.zip). ZIP은 Frontend와 farm_project를 포함하므로 **상위 main 폴더**에서 적용한다.

```bash
cd /home/ysy/main
unzip -o farm_project/sim/runs/frontend_route_sync_20261028_changes.zip -d .
```
