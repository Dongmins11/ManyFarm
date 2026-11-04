# ManyFarm 발표 영상 V4

**V4 촬영·편집·직접 시각 검수 및 자동 검증 통과.** `main@a5f0881`의 V4 지시를 적용하고 V3(`80bdbed`) 원본을 보존했다. 전체 디코딩·규격·현재 설정/영상 해시·원본660파일 보존 검사 결과는 [verification.txt](qa/verification.txt)에 있다.

Isaac Sim GUI의 촬영용 키프레임 연출이다. 자율 미션이나 실물 하역·선별 시험의 성공 기록으로 사용하지 않는다. 요구사항은 [INPUT_V4.md](INPUT_V4.md)에 있다.

| 영상 | 구성 |
|---|---|
| [05 인계 원본](05_handoff_continuity.mp4) · 5초 | 빨강3·노랑3 인계 후 운송 상부 덮개 닫힘 |
| [06·07 운송·선별 원본](06_07_transport_sorting.mp4) · 12초 | 도킹→앞문 개방→기울임/배출→혼합3+3 안착→빨강·노랑 각각1개 집기/분류 |
| [25초 무자막본](ManyFarm_25s_clean.mp4) / [25초 자막본](ManyFarm_25s_captioned.mp4) | 앞5장면 각3초 + 통합장면10초, 총25초/750프레임 |

원본·편집본 규격은1920×1080,30fps,무음 H.264/yuv420p다. 원본은 자막·삽입·페이드 없이 보존한다. 기존 [01 전경](../presentation_video_revision_v3_20261104/01_overview.mp4), [02 예찰](../presentation_video_revision_v3_20261104/02_scout.mp4), [03 수확](../presentation_video_20261104/03_grasp.mp4), [04 투입](../presentation_video_revision_v3_20261104/04_deposit.mp4)은 재사용한다.

편집의15–25초는 통합 원본의 `[1,11)`초를 끊김 없이 사용한다. 마지막2초는 같은 장면을 유지하고 끝0.8초에 페이드한다. 03→04는 직접 컷, 나머지 장면 전환은 여유 프레임을 사용한다. 자막본의02 검출 예시는 V3의 실제 RGB·검출좌표·출처를 그대로 참조한다.

상부 덮개와 배출용 앞문은 별도 기구다. 통합 장면은 상부 덮개를 닫은 채 앞문과 바구니만 움직인다. 같은6개 ID·원본색·크기를 유지하며, 두 색을 하나씩 분류한 뒤 남은4개는 투입부에 남긴다. 전량 선별 완료를 표현하지 않는다.

설정·측정·베이크는 `settings/`, 실제 MP4에서 추출한 단계별 화면과 검수는 `qa/`에 둔다. [05 독립 수치 검토](qa/05-independent-geometry-review.json)는 보존된 메시 꼭짓점과151개 키프레임을 대조한 결과다. 순간적인 바닥 AABB 침투4.814µm를 포함해 수치를 그대로 기록했다. [6개 연결 상태](settings/handoff_continuity_state.json)와 [통합 모션 근거](settings/06_07_motion_evidence.json), [과실 볼록체 검사](settings/06_07_convex_fruit_audit.json)는 실제 GUI/MP4 시각 검수와 구분한다. 접촉·구름은 촬영용 기하 계산이며 전체 로봇의 물리 충돌 검증이 아니다.

카메라는 최종 E/F/G 세 후보의 주요 동작을 비교해 고정 F·35mm를 선택했다([비교](qa/final-camera-comparison.jpg), [선택 근거](qa/camera_selection.json)). 실제 MP4의 [05 단계 화면](qa/05_handoff_continuity-mp4-keyphases.jpg), [통합 동작 42장](qa/06_07_transport_sorting-mp4-keyphases.jpg), [자막 편집본](qa/ManyFarm_25s_captioned-mp4-keyphases.jpg), [무자막 편집본](qa/ManyFarm_25s_clean-mp4-keyphases.jpg)을 직접 검수했다. 통합 원본150프레임에서 혼합3+3이 모두 보인다. 최대 기울임 중에는 게이트가 뒤쪽 과실 일부를, 집기 순간에는 전완이 집게 일부를 가린다.

기구 사이클은3.8초다. 독립361키프레임 검사에서 차단 대상 과실 관통·팔과 설비 교차·관절 제한 위반은0건이었다([검토 범위와 수치](qa/06_07_INDEPENDENT_GEOMETRY_NOTES.md)). 보수적 볼록체 검사1건은 실제 삼각형 검사로 재확인해 관통0건이었다. 선택 과실과 손가락 패드의 파지 접촉은 최대1.936mm(허용2.05mm)로 별도 기록했다. 이산 프레임의 기하 검사는 연속 물리 충돌 검증을 대신하지 않는다.

편집·검증 재실행은 이 폴더에서 한다. `verify_delivery.py`는 기록·규격을 읽기만 하며, 실제 영상 시각 검수 기록이 없으면 최종 통과하지 않는다.

```bash
python3 assemble_v4.py
python3 extract_phase_qa.py
# 실제 MP4 단계 이미지 시각 검수 및 qa/*-mp4-review.json, qa/visual_review.json 기록
python3 build_manifest.py --replace
python3 verify_delivery.py
```

준비 확인은 `python3 verify_delivery.py --preflight`다. [기존 원본660파일 해시](original_hashes.json)와 재사용 파일을 확인하지만 준비 검사만으로 촬영 성공을 의미하지 않는다. GUI 실행 인자는 [capture_session.json](capture_session.json), 현재 영상·설정·근거 해시는 [manifest.json](manifest.json), 직접 검수는 [visual_review.json](qa/visual_review.json)에 있다. 하우스304개 프림과 베드 태그240개를 보존했다. Git에는 최종 영상·설정·검수 근거만 포함하며 중간 구도·진단 촬영도 로컬에 보존했다. 기존 V3·이전 촬영 폴더·원본 USD·태그 지도는 변경하지 않았다.
