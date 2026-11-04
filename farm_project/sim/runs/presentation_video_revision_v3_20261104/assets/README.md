# 예찰 삽입 이미지 출처

- 원본: `sim/runs/presentation_stills_20261031/delivery/evidence/scout-observation-2/`의 실제 시뮬레이션 관측. SEC01 / SEC01_G02, 640×384 RGB다.
- `02_scout_rgb.png`, `02_scout_observation.json`, `02_scout_map_detections.json`은 해당 원본을 바이트 그대로 복사했다. SHA256은 `02_scout_detection_provenance.json`에 기록했다.
- 예시 PNG에는 원본 `accepted`의 `mask_box_original_xyxy` 4개(빨강 2, 노랑 2)와 짧은 색상 이름만 표시했다. 검출 위치·수량을 추가하거나 보정하지 않았다. 이 한 화면의 검출 수를 구역 전체 성능이나 수확 성공 수로 해석하지 않는다.
- 픽셀별 마스크 원본은 남아 있지 않아 기록된 마스크 경계 상자만 사용했다. 마스크 픽셀을 복원하거나 새로 생성하지 않았다.
- 재생성: `python3 assets/build_detection_example.py`. Pillow와 Noto Sans CJK가 필요하다.

후편집의 이미지 크기는 520×312로 원본 비율을 유지한다. 제목·설명과 테두리를 포함한 카드는 540×416이며 화면 `(720,46)`에 놓인다. V3 예찰 시작·중간·끝 합성 3장을 직접 확인해 로봇, 센서, 마스트, 주요 작물, 근접 태그 및 좌하단 자막을 가리지 않음을 확인했다. 마지막 화면의 센서와 카드 사이에는 약25px 여백이 있다.

예찰 편집 구간 내부 0.3~2.8초(완성본 3.3~5.8초)에만 0.15초 페이드로 표시한다. `qa/02_scout-inset-placement-*.png`는 위치 검토용이라 실제 등장 시간과 무관하게 카드를 표시한다. 원본 예찰 MP4와 clean 편집본에는 삽입하지 않는다.
