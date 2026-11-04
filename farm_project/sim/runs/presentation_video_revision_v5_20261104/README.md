# ManyFarm 발표 영상 V5

[영상 목록](index.html) · [재생 검수 페이지](qa/playback_review.html) · [V5 요구사항](INPUT_V5.md)

**제작·프레임 검수 완료:** 원본2편과25초 편집본2편을 생성했다. 05 전150프레임, 06·07 전360프레임, 편집본 각각26개 주요 프레임과 추가 원본 크기 이미지를 직접 확인했다. **정상속도·저속의 연속 재생 시청은 수행하지 않았다.** [최종 기술검사](qa/validation.txt)는 PASS다. 연속 재생 시청을 포함한 V5 전체 완료 판정과는 구분한다.

| 영상 | 규격 | 내용·상태 |
|---|---|---|
| [05 인계 원본](05_handoff_continuity.mp4) | 5초 · 150프레임 | 빨강4·노랑3 전량 낙하·안착→바닥 복원→운송 덮개 닫힘. 촬영 완료 |
| [06·07 운송·선별 원본](06_07_transport_sorting.mp4) | 12초 · 360프레임 | 동일7개 배출→혼합4+3→색별1개 선별·5개 잔류. 촬영 완료 |
| [25초 자막 없는 편집본](ManyFarm_25s_clean.mp4) | 25초 · 750프레임 | 생성 완료 |
| [25초 자막 편집본](ManyFarm_25s_captioned.mp4) | 25초 · 750프레임 | 생성 완료 |

모두1920×1080/30fps/H.264/yuv420p/무음이다. 01·02·04는 채택한 V3 원본, 03은 최초 채택 원본을 재사용한다. 예찰 삽입 이미지는 제거하고 자막본의 하단 글씨만 유지한다. 05는 raw `[1,4)`초, 06·07은 raw `[1,11)`초를 사용한다. 9·12·15초는 직접 컷이며, 연속 장면 내부 컷 없이 마지막2초 정착 유지와 끝0.8초 페이드를 적용한다.

05는 **Blender 4.0.2/Bullet의 짧은 강체 계산**이다. 원본 바구니 형상·유한한 개방 바닥·7개 원본 크기의 볼록 접촉 형상으로 중력·마찰·접촉 회전·감쇠를 계산한 뒤 Isaac GUI에서 재생했다. 임의 공중 임펄스나 최종 슬롯 정렬은 사용하지 않았다. 물성은 촬영용 가정이며 실물 보정값은 아니다. [물리 방법·수치 한계](HANDOFF_PHYSICS_NOTES.md), [베이크 근거](settings/05_handoff_continuity_evidence.json).

**04→05의 한계:** 편집359프레임은 재사용04의 빨강1개 투입 장면,360프레임은7개가 이미 적재된 새05의 시작이다. 카메라·배치·과실 상태가 바뀌는 직접 컷이며, 중간 적재 과정은 생략했다. 04부터 동일7개를 연속 적재한 증거는 아니다. 동일7개 상태의 연결은 새05→06·07부터 적용한다. [04 컷 지점 비교](qa/04_cut_stability_review.json)에서 raw119/149의 투입 후 안정 상태를 확인해 기존 trim을 유지했다.

06·07은 원본 관절 축·제한·FK와 메시 지지면을 사용한 **기하 기반 키프레임 동작**이다. 05의 최종7개 cargo 상대 행렬을 이어받았으나 전체 구간을 강체 접촉 해석한 것은 아니다. 05의 마지막 영상 프레임(4.9667초)과 저장한 베이크 끝점(5.000초) 사이에는 안착 후 미세한 잔여 움직임이 있다. 새06은 저장한 끝점 행렬을 그대로 사용한다. 실제 두 영상 경계의 원본 메시 전체24,934정점을 대조한 최대 변위는0.639µm이며, 별도1µm 상한으로 검사했다. [연결 정밀 검수](qa/continuity_precision_review.json)에 초기 행렬 비교 실패와 원인을 기록했다. 두 원본 모두 GUI 촬영 연출이며, 자율 미션·실물 운용 성공 시험이 아니다. [연속 동작 근거](settings/06_07_motion_evidence.json).

선별장 작업 공간은 실제 베드 경계를 읽고 후보 A/B/C를 비교해 **B**를 채택했다. 선별장 원점은 약 `[-3.4,13.4,0]m`, 카메라는 `[-5.563,11.445,2.25]m`·35mm다. 설비·팔·운송 경로·과실·카메라에 같은 변환을 적용했고, 하우스·베드·작물을 숨기지 않았다. 운영 지도와 원본 USD에는 저장하지 않는다. [경계 실측](settings/workspace_bounds.json), [채택 프리뷰 검수](qa/06_07-independent-preview-review.json). [완성 원본의 전360프레임 검수](qa/bed_nonexposure_review.json)에서 베드·작물·지지대·나무 테두리 비노출을 확인했다. 화면 밖 원본 보존은 별도 visibility 기준과 원본 해시로 확인했다.

초기05 프리뷰에서 과실이 이미 내려갔는데도 상부에 초기 형상이 희미하게 남았다. 동일 장면 상태를 처음부터 렌더하면 비어 있었고, 누적 초기화 API만으로는 잔상이 남았다. **저장하지 않는 한 프레임 동안 카메라를 옮겼다가 정확한 원래 자세로 복원하고24회 갱신한 뒤 캡처**하여 해소했다. 물체 표시·크기·궤적은 바꾸지 않았다. 최종05 MP4의150프레임에서 잔상 재발은 관찰되지 않았다. [비교 진단](qa/05_render_history_diagnostic_review.json).

[05 영상 검수](qa/05_handoff_continuity-mp4-review.json)는 실제 MP4 전150프레임 contact sheet와 핵심8장 원본 이미지에 대한 직접 검수다. 바구니 벽·과실 겹침·닫힌 덮개 때문에 모든 ID를 매순간 화면에서 개별 계수할 수 없으며, 수량·접촉은 별도 장부와 기하 감사로 확인한다. 연속 재생 시청과 프레임 검수는 구분한다. `verify_timed_decode.py`의1×/0.25× 처리는 시간에 맞춘 디코딩 검사이며 사람이 해당 속도로 영상을 시청했다는 근거가 아니다. [원본1,070개 보존 확인](qa/05_originals_preservation_review.json)은 변경0·누락0이다. [06·07 검수](qa/06_07_transport_sorting-mp4-review.json), [자막 없는 편집본 검수](qa/ManyFarm_25s_clean-mp4-review.json), [자막본 검수](qa/ManyFarm_25s_captioned-mp4-review.json)에 각각 범위와 한계를 기록했다.

05 QA는10개 contact sheet·핵심8개 원본 PNG·추출 JSON을 게시하며, 전150개 원본 PNG는 로컬에 보존한다. 추출 JSON의150개 항목은 로컬 검수 기록이며 모든 PNG가 게시되는 것은 아니다.

재현·검수 명령은 이 폴더에서 실행한다. 촬영은 [실제 GUI 실행 기록](capture_session.json)과 `capture_tools/`, `settings/`를 따른다.

```bash
python3 assemble_v5.py
python3 extract_phase_qa.py
python3 verify_timed_decode.py
# 실제 프레임 검수 결과를 qa/*-mp4-review.json에 기록
python3 build_manifest.py
python3 verify_delivery.py
```

기존 manifest 갱신은 `build_manifest.py --replace`다. `verify_delivery.py --preflight`는 준비 상태만 확인한다. 최종 검수·파일 해시는 [QA 종합 기록](qa/visual_review.json)과 [manifest](manifest.json)에 기록한다.
