# V4 05 인계 연결 설정

- 원본 V3 `05_handoff.json`을 읽어 새 `05_handoff_continuity.json`을 작성했다. 기존 영상·설정·USD 및 운영 코드는 변경하지 않았다.
- 처음부터 끝까지 Handoff_01~06만 보인다. 원본 과실 ID/색/크기를 유지한 빨강 3개·노랑 3개다. Handoff_07은 첫 프레임부터 숨긴다.
- 후속 배출의 혼합 두 묶음을 위해 Handoff_05(빨강)와 Handoff_06(노랑)의 **궤적 슬롯을 시작부터** 교환했다. 각 원본 크기와 메시 최저점 높이는 유지했다. `cargo_box` 기준 +Y는 RRY, -Y는 RYY다.
- V3 낙하 베이크를 재사용했다. 새 물리 계산·자율 인계 시험을 수행했다는 의미가 아니다.

| 원본 시간 | 동작 |
|---|---|
| 1.00~1.65초 | 회색 수확 바닥 개방 및 6개 낙하 |
| 2.15~2.50초 | 빈 수확 바닥 복구 |
| 2.65~3.35초 | 운송 상부 덮개와 피니언을 함께 닫음 |
| 3.35~5.00초 | 닫힌 상태 유지; 운송 출발은 다음 연속 장면 |

사용 구간 `[1,4)`초 안에 낙하와 닫힘이 완료된다. 닫힘 설계 끝점은 3.35초이며, 30fps 실제 완전 닫힘 첫 샘플은 3.3667초다. 최종 운송 상부 덮개 2개·피니언·앞문·기울임 값은 모두 0이다.

## 실제 수행한 오프라인 검사

원본 USD 관절 프레임/축, URDF 한계, 원본 과실 Mesh 점, 원본 덮개 Cube의 실제 꼭짓점으로 측정했다. Cube의 authored extent 중복 스케일 때문에 `BBoxCache` 결과를 실제 형상으로 사용하지 않았다.

- 151개 키프레임(렌더 150프레임 + 끝점): 동일 6개 ID, 색 3+3, 원본 스케일 유지.
- 회전한 과실 AABB 상호 겹침: **0m**.
- 덮개 닫힘 구간에서 과실 최상점과 덮개 하부 사이 최소 간격: **13.14mm**.
- 움직이는 덮개/랙/연결부의 실제 Cube AABB와 과실 AABB 겹침: **0m**.
- 복구한 수확 바닥 하부와 운송 덮개 상부의 보수적 수직 간격: **49.00mm**.
- 덮개 좌우 이동량 = 피니언 각도 × 0.05, 닫힘 값 0으로 일관됨.

`transport_robot.sim.usda`는 기존 물리용 상부 덮개 관절을 0에 잠근다. 촬영 도구는 세션에서 rigid body/joint/mimic을 끄고 원본 관절 프레임으로 FK를 적용한다. 촬영 개방량 0.155m는 원본 URDF의 범위이며, 기존 시뮬 잠금 자산은 수정하지 않았다.

검사 상세는 `05_mechanism_geometry.json`, `05_handoff_continuity_evidence.json`에 있다. 다음 연속 장면은 `handoff_continuity_state.json`의 `clones[].final_cargo_matrix`와 `closed_joint_values`를 그대로 사용한다.

## 재현

프로젝트 저장소 루트에서:

```bash
LD_LIBRARY_PATH=/home/ysy/Downloads/blender-4.2.23-linux-x64/lib /home/ysy/Downloads/blender-4.2.23-linux-x64/4.2/python/bin/python3.11 farm_project/sim/runs/presentation_video_revision_v4_20261104/settings/build_handoff_v4.py --inspect-usd
python3 farm_project/sim/runs/presentation_video_revision_v4_20261104/settings/build_handoff_v4.py
```

## 검증 범위

오프라인 기하 검사는 PASS다. 이는 보수적 AABB/꼭짓점 검사이며 전체 로봇·팔의 mesh 충돌 시험, 실시간 PhysX, 실물 인계 검증이 아니다. 최종 촬영·전체 MP4 시각 검수 결과는 실행 폴더 README와 QA 기록을 따른다.

추가로 실제 GUI가 저장한 최종 inspect 행렬과 0110 프리뷰/배경 과실 숨김 진단 PNG를 직접 확인했다. `05_gui_pose_check.json`에 결과를 기록했다.

- 실제 GUI 최종 cargo 상대행렬과 전달 상태의 최대 성분 차이: `9.32e-9` 이하.
- 실제 6개 메시의 가장 높은 점은 0.431863m로 상부 바구니 바닥 0.506m보다 낮다.
- 상부 안쪽 벽의 붉은/초록 형상은 원본 배경 과실 288개만 숨긴 진단에서 사라졌다. 진단 전후 인계 6개의 좌표 차이는 `1.39e-17` 이하이고 6개 show를 유지했다. 따라서 인계 6개의 상부 잔류가 아닌 배경 과실과 연동된 렌더 반사/효과다. 정확한 RTX 반사 경로는 분리 검증하지 않았다.
- 최종 영상은 배경 과실을 보존한다. 진단 PNG는 문제 구분용이며 최종 컷에 사용하지 않는다.
- 이후 실제 MP4 추출 프레임 `qa/05_handoff_continuity-mp4-frame-0105.png`도 직접 열었다. 배경 과실이 그대로 보이는 상태에서 상부 바구니가 비어 있고 프리뷰의 붉은/초록 형상은 없다. 해당 프리뷰 현상은 이 실제 MP4 프레임에서 재현되지 않았다. 메인 에이전트가 별도로 실제 MP4 11시점 검수를 완료했다.
- Handoff_07은 최종 상태 hide 목록에 있으며, runtime visibility 속성 자체는 별도 측정하지 않았다.
