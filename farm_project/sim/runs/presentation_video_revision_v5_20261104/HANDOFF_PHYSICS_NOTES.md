# V5 수확→운송 인계의 물리 베이크

V3 원본 `Handoff_01~07`(빨강4·노랑3)의 메시·색·크기를 유지했다. V4의 6개 제한과 `Handoff_07` 숨김을 제거했다. 기존 V3/V4 궤적을 복사하지 않고 **Blender 4.0.2의 Bullet 강체 계산**으로 7개 낙하를 새로 계산했다. Isaac GUI는 확정된 행렬을 재생한다. 운영 미션이나 실물 성공 시험은 아니다.

- 원본 수확 바구니 벽 Cube, 회색 바닥의 유한한4개 타일 메시, 운송 바구니 바닥·벽·앞문·뚜껑 Cube를 원본 USD에서 읽었다. 원본 USD는 저장하지 않았다.
- 과실은 원본 메시의 볼록 외피로 접촉을 계산했다. 원본 크기는 그대로이며 물리 계산용 좌표 원점만 바구니 근처로 옮겼다.
- 중력9.81m/s², 30fps×16서브스텝=480Hz, 접촉 반복60회. 3초 사전 안정화 후5초를 기록했다. 초기 속도/각속도0, 공중 횡이동 임펄스나 임의 회전력은 사용하지 않았다. `seed=20261104`는 입력 식별용이며 이번 계산에는 무작위 교란을 사용하지 않는다.
- 과실 질량9g, 과실/벽 마찰0.32/0.35, 반발0.06/0.04, 감쇠0.1/0.18을 사용했다. 이는 촬영용 물성 가정이며 실물 측정값으로 보정한 결과는 아니다.
- 7개 각각 다른 접촉으로 회전하며 옆으로 이동하고, 하부 바구니에서 눕거나 굴러 안정됐다. 최종 위치를 원하는 슬롯에 맞추거나 정렬하는 후처리는 하지 않았다.

| raw 시각 | 동작 |
|---|---|
| 0~1초 | 상부 바구니에7개, 하부 뚜껑 열림 |
| 1~1.65초 | 원래 축으로 회색 바닥0→0.105m 개방 |
| 2.4초 | 이후 전 구간에서7개 모두 선속도5mm/s·각속도0.1rad/s 이하 |
| 3~3.3초 | 전량 안착 후 수확 바닥 복원 |
| 3.35~3.85초 | 운송 상부 뚜껑 닫힘 |
| 3.85~5초 | 닫힌 상태 유지 |

151개 베이크 프레임에서7개 ID·원본 scale·총수량을 확인했다. 모든 과실이 운송 바구니에 들어갔고, 닫히는 상부판과의 최소 높이 여유는119mm다. raw3초 이후 최대 선속도0.0203mm/s, 최대 각속도0.000524rad/s다.

[별도 기하 검산](qa/05_independent_bake_geometry_audit.json)은 실제 과실 메시 정점과 원본 평판의 최대 침투0.284mm, 과실 볼록 외피 교차의 최대 내접구 반경0.117mm를 기록한다. 0.5mm 경보 기준 초과는 없었다. 유한 정밀도 강체 접촉의 작은 침투를0이라고 보고하지 않는다. 삼각면 전체·프레임 사이 연속 충돌·전체 로봇 충돌 인증은 하지 않았다.

[최종 적재 상태](settings/handoff_continuity_state.json)의7개 `final_cargo_matrix`를06·07에서 그대로 사용한다. 자연 안착 결과 cargo Y 양쪽 개수는2/5이며, 중앙에 가까운2개를 포함해 연속 장면에서 혼합4+3을 구성하는 별도 경로를 검토한다.05 결과를 임의로 옮기지 않는다.

V4 소스가7번째 과실을 제외한 사실은 확인했다. 사용자가 본 V4의 “서서히 사라짐” 전체를 이것만으로 설명하지 않는다. V5에는 프레임별 visibility/opacity/scale 변경이 없다. V5 E 카메라의 동적72프레임에는 이미 내려간 과실의 초기 형상이 상부에 희미하게 남았으나, 동일72프레임 상태로 처음부터 시작한 [정적 진단](preview/05_static_settled_diagnostic-0000.png)에서는 상부가 완전히 비었다. 이는 모션 행렬의 과실 누락이나 고정 중복 형상보다 이전 렌더 상태에 의존한 잔상을 가리킨다. 구체적인 렌더 내부 경로는 아직 분리하지 않았다.

진단의 요청 상태와 GUI에서 읽은 실제 상태는 정확히 같았다. 누적 초기화 API만 호출한 동적72에서는 잔상이 남았다. 카메라 원래 자세를 저장하고, 기록하지 않는 한 프레임을 다른 공간에서 렌더한 뒤 정확한 자세로 복원한 동적72에서는 상부가 완전히 비었다. 과실 visibility와 물리 궤적을 바꾸지 않고 해당 V5 프리뷰 잔상을 해소했다. 이미지 해시와 관찰은 [렌더 상태 비교 기록](qa/05_render_history_diagnostic_review.json)에 남겼다.

승인 E 카메라 `eye=[-6.45,2.75,1.5]`, `target=[-6,3.68,0.49]`, 32mm, fill650과 프레임별 렌더 이력 초기화·24번 갱신 대기 옵션을 확정했다. 물리 베이크·최종 적재 행렬은 유지한다. 최종 자연스러움·잔상 재발 여부·정상속도/느린속도 검수는 [최종 영상 검수](qa/05_handoff_continuity-mp4-review.json)에 기록한다.

완성 MP4에서150프레임을 전부 추출하여 contact sheet10장과 핵심8개 원본 프레임을 직접 확인했다. 낙하 중 자세 변화·하부 구름과 안착·후속 닫힘이 보이고, 초기 상부 잔상은 재발하지 않았다. 벽·과실 겹침·닫힌 뚜껑 때문에 화면에서7개를 매순간 개별 계수할 수는 없다. 이는 [프레임 기반 검수](qa/05_handoff_continuity-all150-frame-review.json)이며 연속 영상을 정상속도나 느린속도로 재생하여 시청한 검수는 아니다.

재현(프로젝트 `farm_project`에서 실행):

```bash
PYTHONPATH=/home/ysy/isaac/env_isaaclab/lib/python3.11/site-packages/isaacsim/extscache/omni.usd.libs-1.0.1+69cbf6ad.lx64.r.cp311 LD_LIBRARY_PATH=/home/ysy/isaac/env_isaaclab/lib/python3.11/site-packages/isaacsim/extscache/omni.usd.libs-1.0.1+69cbf6ad.lx64.r.cp311/bin /home/ysy/isaac/env_isaaclab/bin/python sim/runs/presentation_video_revision_v5_20261104/settings/build_handoff_v5.py --inspect-usd
python3 sim/runs/presentation_video_revision_v5_20261104/settings/build_handoff_v5.py
python3 sim/runs/presentation_video_revision_v5_20261104/settings/audit_handoff_v5.py
```

Blender는 렌더 없는 고립 강체 계산에만 사용한다. 실제 발표 영상은 Isaac Sim GUI에서 촬영한다. 저장된 물리 결과로 설정만 다시 만들려면 `--reuse-bake`를 사용한다. 입력·베이크 해시는 [근거](settings/05_handoff_continuity_evidence.json)에 있다.
