# ManyFarm 발표 영상 V3

`origin/main`의 `PRESENTATION_VIDEO_REVISION_V3_20261104.md`와 카메라 참조를 반영한 **Isaac Sim GUI 촬영용 키프레임 연출**이다. 자율 예찰·수확·운송·선별 시험의 성공 기록으로 사용하지 않는다.

## 바로 보기

- [자막·예찰 이미지 포함 22초 편집본](ManyFarm_22s_captioned.mp4)
- [무자막 22초 편집본](ManyFarm_22s_clean.mp4)
- [영상·검수 이미지 모아 보기](index.html)
- [규격·출처·SHA-256](manifest.json), [검수 기록](qa/visual_review.json)

| 컷 | 원본 | 내용 |
|---|---|---|
| 01 | [전경 · 5초](01_overview.mp4) | 뒤쪽 네 베드 중앙 통로, 하우스 안에서 같은 높이·각도로 전진 |
| 02 | [예찰 · 5초](02_scout.mp4) | 기존 구도·0.4m 이동 유지, 실제 검출 이미지 별도 제공 |
| 03 | [기존 수확 · 5초](../presentation_video_20261104/03_grasp.mp4) | 기존 파일 그대로 재사용, 해시 기록 |
| 04 | [바구니 투입 · 5초](04_deposit.mp4) | 닫힌 회색 바닥 위로 과실 낙하·안착 |
| 05 | [수확물 인계 · 5초](05_handoff.mp4) | 바닥 패널 개방 후 빨강4개·노랑3개 낙하·회전·안착 |
| 06 | [운송 · 4초](06_transport.mp4) | 같은7개 적재 자세를 이어받아 이동 |
| 07 | [선별 · 7초](07_sorting.mp4) | 설비·팔 함께 촬영용 이동, 낙하→경사면 구름→안착·유지 |

모든 원본은 1920×1080, 30fps, 무음 H.264/yuv420p이며 자막·삽입·페이드가 없다. 두 편집본은22초/660프레임이다. 03→04는 직접 컷, 나머지는 원본 여유 프레임을 쓰는 짧은 전환이다. 마지막1.2초 정착 상태 유지 후0.8초 페이드아웃한다.

검증 완료: 새 원본930프레임, 편집본 각각660프레임의 전체 디코딩·규격 검사 통과. 기존358파일 해시 일치, 03→04 자세 일치, 05→06 바구니 상대 적재 자세 일치를 확인했다. [검사 출력](qa/validation.txt)과 [최종 편집 검수 화면](qa/ManyFarm_22s_captioned-mp4-keyphases.jpg)을 남겼다.

## 변경·보존 범위

- 원본 하우스 프레임·아치·필름의 표시 상태를 유지하고 운영 배치표의 베드 AprilTag240개와 Pattern을 설치했다. [근접 렌더](00_apriltag_closeup.png)와 [설치 목록](apriltag_installation.json)을 남겼다.
- 바구니 바닥은 기존 `box_floor_v3.usd` 메시를 기존 개폐 링크에 연결했다. 회색 불투명 재질과 벽 맞물림은 촬영 session layer에만 적용했다.
- 인계 과실7개는 기존 파프리카를 원래 크기로 복제했다. 원본 과실 ID·배치와 집계 자료는 수정하지 않았다.
- [선별장 강체변환](settings/station_transform.json)은 HCRStation/HCRRobot에 같이 적용했다. 06도 같은 설비 위치를 사용한다.
- 기존 두 촬영 폴더·원본 USD·태그 지도는 [보존 해시](original_hashes.json)로 대조한다. 공통 로봇 제어·지도·실물 설정은 이번 게시 범위에 없다.

## 검출 이미지와 재현 자료

[예찰 이미지](assets/02_scout_detection_example.png)는 실제 저장 관측 RGB와 기록된 검출 박스4개로 만들었다. 겹치는 긴 ID만 제거했고 검출을 추가하지 않았다. [출처](assets/02_scout_detection_provenance.json), 원본 RGB·메타데이터, [삽입 위치·시간](overlays/02_scout_insert.json), 시작·중간·끝 합성 프리뷰를 함께 제공한다. 원본 마스크 비트맵이 없어 실제 좌표가 남은 박스를 사용했다.

카메라·배치·관절은 `settings/`에, 인계 시드·궤적은 [05_motion_evidence.json](settings/05_motion_evidence.json)에, 선별 낙하·경사면 접촉·회전은 [07_motion_evidence.json](settings/07_motion_evidence.json)에 있다. 사용한 촬영 도구 스냅샷은 `capture_tools/`에 보관한다.

저장소 `farm_project/`에서 기존 결과를 덮어쓰지 않는 새 출력 경로로 실행한다. Isaac Sim Python과 동작하는 GUI DISPLAY가 필요하다.

```bash
/home/ysy/isaac/env_isaaclab/bin/python sim/tools/stage_portfolio_photos.py --gui --all-beds --runtime sim/runs/presentation_video_revision_v3_20261104/settings --output sim/runs/presentation_video_revision_v3_replay
```

별도 터미널에서 `ready.json` 생성 후 각 설정을 순서대로 요청한다. 빠른 구도 확인에는 `--preview`를 붙인다.

```bash
python3 sim/tools/request_presentation_capture.py --output sim/runs/presentation_video_revision_v3_replay sim/runs/presentation_video_revision_v3_20261104/settings/04_deposit.json sim/runs/presentation_video_revision_v3_20261104/settings/05_handoff.json sim/runs/presentation_video_revision_v3_20261104/settings/06_transport.json sim/runs/presentation_video_revision_v3_20261104/settings/07_sorting.json sim/runs/presentation_video_revision_v3_20261104/settings/01_overview.json sim/runs/presentation_video_revision_v3_20261104/settings/02_scout.json
```

패키지 안에서 `python3 assemble_v3.py`로 편집하고 `python3 verify_delivery.py`로 저장된 규격·해시·연속성 근거를 검사할 수 있다. 편집에는 같은 저장소의 기존03 원본이 필요하다.

## 표현의 한계

05는 중력·회전된 메시의 보수적 AABB 접촉·작은 반동·마찰을240Hz로 계산해30fps로 베이크한 연출이다. 07은 실제 경사면·과실 메시를 기준으로 낙하와 구름을 계산했다. 전체 로봇 충돌이나 실제 정책 성능을 검증한 물리 시험은 아니다. 바구니·분류함의 실제 벽으로 일부 과실이 가려질 수 있으며 구조물을 숨기지 않았다.
