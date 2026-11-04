# 시뮬레이션 통합 변경 이력

시뮬 전용 변경과 시뮬 통합에 필요한 공통 변경을 기록한다. 공통 변경은 사용자 승인 전 적용하지 않는다.


## PRESENTATION-VIDEO-V3-PLAN-20261104 — 사용자 촬영 피드백과 참조 이미지 인계

- 승인/기준: 사용자 후속 피드백, 확인한 main `981b794`. 본 항목은 확정 촬영 설계 기록이며 구현·재촬영 완료 기록이 아니다.
- 대상: `PRESENTATION_VIDEO_REVISION_V3_20261104.md`, `presentation_video_revision_v3_20261104/01_drone_camera_reference.jpg`, 이전 리뷰의 최신 지시 연결.
- 변경: 비닐하우스 전체와 등록 베드 AprilTag 복원,01 중앙 통로 드론 전진,02 실제 검출 이미지 예시,03 원본 유지,04 회색 바닥,05 바닥 개방과 약7개 낙하·회전,06 하우스 배경,07 촬영용 설비 이동·과실 구름,2초 여유를 더한 약22초 엔딩.
- 근거/검증: 촬영 설정의 하우스 hide 목록, 태그 설치 함수와240개 배치, 기존 예찰 검출 이미지, 보간 방식과4/5초 길이 제한을 원격 소스에서 확인했다. 사용자 그림을 직접 확인하고 형상을 바꾸지 않은 JPEG 참조로 함께 게시한다. 이번 단계에서 Isaac 실행·새 연출 검증은 하지 않았다.
- 실물 영향/복원: 현재는 문서·참조 이미지만 변경한다. 후속 구현도 sim 촬영 도구·session layer에 한정하며 공통/실물 설정과 원본 USD는 보존한다. 본 문서 커밋을 되돌리면 계획 안내만 복원된다.

## PRESENTATION-RETAKE-20261104 — 리뷰에 따른 04·07·02 GUI 재촬영

- 승인/기준: 사용자 `git fetch origin main` 후 리뷰를 읽고04→07→02재촬영·원본보존·직접검수·Git게시 지시. 원격main `524a193`의 `PRESENTATION_VIDEO_REVIEW_20261104.md`를 사용했다.
- 대상: 촬영 도구 `stage_portfolio_photos.py`의 선택적 세션 측면광/f-number, `presentation_video_frames.py`의 프리뷰 프레임 지정/렌더 안정화(프리뷰 대기6→48회, 최종MP4는6회 유지). 기존 도구·runtime을 재사용하고 업무코드/실물설정/원본USD는 변경하지 않았다.
- 전후:04의약78°수직뷰를44°서남사선으로,07의팔잘림·낮은대비를35°전방사선/측면광으로,02의센서뒷면·바닥위주뷰를센서높이통로사선/70%추적으로 개선했다. 원본 모션·관절·과실부착은 모두 같다.
- 검수: 컷별 서로 다른3방향×시작/중간/끝9장을 실제로 열어 비교했다.04/02추가미세조정과최종각9프레임도확인했다.03→04과실·집게월드행렬차이0. 세MP4각150프레임/5초/1080p30/무음 전체디코딩·SHA·렌더기록통과. 원본179파일해시일치.
- 결과/한계: `sim/runs/presentation_video_retake_20261104/README.md`, MP4 3종·설정·후보/최종검수이미지·manifest·읽기전용검증기를별도저장했다.04깊은바구니의과실하부가림,07단순재질,02렌즈없는센서외형과통로배경은유지한다. 자율/물리시험성과가아닌GUI연출이다.
- 실물 영향/복원: 없음. 새 광원·노출은 촬영session에서만 적용되며 컷마다 기본값으로 돌아간다. 복원은이번촬영도구diff만역적용하고원본/재촬영결과는보존한다. 기존통합브랜치와미커밋작업은유지하고분리된최신main작업공간에서이번결과만게시한다.

## PRESENTATION-GUI-VIDEO-20261104 — 7종 연출 영상 촬영 완료

- 승인: 사용자 최신 발표 가이드 확인 및 7종 Isaac Sim GUI 촬영 지시. 원격 main `4861193`에서 콘티 `5ebbb1f`를 확인하고, 로컬 `integration/fleet-sim-clock-20261102` / `3bb5d0f` 및 기존 미커밋 작업은 보존했다.
- 대상: `sim/tools/stage_portfolio_photos.py`, `presentation_video_frames.py`, `request_presentation_capture.py`, 발표 콘티·인계 문서. 기존 PNG 촬영에 별도 GUI 키프레임 MP4 모드를 추가했다. 컷마다 배치·관절·과실·표시 상태를 복원하고, 프레임 번호/30으로 연출하며 새 렌더 확인 후 인코딩한다.
- 실행: Isaac Sim 5.1 / RTX 4070 SUPER / DISPLAY=:20.0, `--gui --all-beds`. 농장 전경·예찰·파지·투입·인계 정렬·운송·선별의 7개 무자막 1080p30 원본과 20초 무자막/한글 자막 편집본을 저장했다.
- 보완: 예찰 하단 잘림·투입 팔 가림·선별 기둥 가림을 구도로 조정했다. 촬영 세션에서 팔 재질을 메시에도 바인딩해 컷 전환 후 외형을 유지했다. 초기 렌더 참조값 형식 오류는 수정 후 전 컷 재촬영했고, 첫 편집 인코딩의 종료 신호로 생긴 불완전 파일은 재생성했다.
- 검증: 원본 1,020프레임, 편집본 각 600프레임. 9개 MP4 해상도·FPS·길이·전체 디코딩 통과, 원본 새 렌더 시각/프레임 번호 연속 확인. 시작·중간·끝 및 동작 구간 추출 화면 확인. 03 끝/04 시작의 과실·집게 월드 행렬 차이 0. 전체 메시 충돌·물리·정책 성공은 검증하지 않은 연출이다.
- 산출물: `sim/runs/presentation_video_20261104/`의 `index.html`, MP4, `settings/`, `preview/`, `qa/`, `manifest.json`, `README.md`. 실제 재촬영 명령과 구도·기하 근거 포함.
- 실물 영향/복원: 공통 업무·실물 설정·원본 USD 변경 없음. 세션 layer만 변경한다. 복원 시 이번 촬영 도구 diff만 역적용하고 영상은 보존한다. 사용자 Git 게시 요청에 따라 이 변경과 영상 9개를 main 게시 대상으로 포함했다. 과거 로컬 실행 폴더를 참조하던 runtime JSON은 내용 그대로 동봉하고 경로만 연결했다. 검증 스크립트는 기존 촬영 provenance를 덮어쓰지 않도록 보완했다. 중복 ZIP·임시 요청·로그는 제외한다.


## SCOUT-SORT-LOSS-AUDIT — 실측 수량 차이 원인 감사와 오프라인 재현

- 사용자 요청에 따라 합성 5행을 제외한 실측 11행을 조사했다. 7·12번 예찰/수확 재사용을 구분하고, 원본 수량 데이터는 보존했다.
- 예찰 ID 연계 재생, 실제 수확 세션의 trace/바구니/최종 과실 위치 대조, 선별 저장 영상 분류 및 NO_COLOR 완료 판정을 재현했다.
- 결과: 중복 예찰 후보, 작업영역 제외, 가림, 집기 미완료/낙하, 선별 ROI 미검출과 조기 완료를 구분했다. 세부 미확정 원인과 개선·검증 조건을 함께 기록했다.
- 자료: `SCOUT_TO_SORT_LOSS_ANALYSIS.md`, `SCOUT_TO_SORT_LOSS_ANALYSIS.json`, `sim/tools/analyze_scout_sort_losses.py`.
- 영향: 운영/공통 코드·ROI·원본 시험 데이터 변경 없음. 새 Isaac 물리 시험은 수행하지 않았으며 해결/재발 방지 완료를 주장하지 않는다.

## CAMERA-RETRY-METRICS-20261021 — 실적 손실 비중단·1회 재탐색·성능 집계

- 승인: 사용자 비대상 이탈/평가 ID 연결을 Action 실패로 삼지 말고60초 실패 후1회 재탐색/재시도하며 actual/expected/harvested를 평가하라는 지시, D-051.
- 대상: farm_sim_devices/student_session.py, sim 전달 student60_mission.py의 opt-in 복귀, sim harvest.json/harvest_task.json 외부 대기 제한, run_section_campaign.py/campaign_performance.py 및 관련 sim 시험. 기존 공통 TF 수정/실물 설정/모델 가중치는 유지한다.
- 전후: ID 불명·비대상 과실 이탈·목표 낙하/60초 실패가 전체 중단으로 이어지던 경로를 분리했다. 카메라만으로 시도하고 익명 레이저 통과를 집계하며, 측정 복귀 후 새 관측으로 한 번 재시도한다. 재시도 소진/대상 없음은 수확 실패 실적이며 다음 대상으로 진행한다. 실제 복귀·정지/통신/주행 실패는 Action 실패를 유지한다. 평가 ID는 접촉 정지 기준에도 사용하지 않는다.
- 평가: 수확 전 실제 장면의 작업범위 red/yellow, 예찰 expected, 레이저 harvested를 별도 집계한다. 성능 사건과 Action 실패·평가 진단을 분리한다. 설정 복사20초 실패는 진단만 남긴다. 외부 sim 대기 제한만7200/7260/7500벽시계초로 조정하고 개별 수확60시뮬초는 유지한다.
- 검증: 관련81개 통과, diff/컴파일 정상.09:52 KST SEC07 2회차부터 기존 성공 예찰을 재사용해 실제 시험 재개. 실제 Isaac의 시간초과/비대상 이탈 전 시나리오 검증은 진행 중이다. 상세 PROJECT_STATE §88 및 기존 캠페인의 policy_camera_retry_once_20261021.
- 실물 영향/복원: 공통/실물 배포 변경 없음. 전달 미션 새 옵션은 기본False로 기존 사용자 동작을 보존한다. 시험 정리 후 이번 sim 변경만 역적용하고 원본/캐시는 보존한다. 미커밋·미푸시.

## OVERNIGHT-REPORT-20261021 — 야간 시험 중간 집계

- 승인: 사용자 결과 보고 요청. 운영 코드/설정 및 진행 중 시험은 변경하지 않았다.
- 09:27 KST: SEC01~05 완료, SEC06 5회차 마지막W008 진행. 전체18시도 중 성공5/실패12/진행1. 성공한 최종 시도39window에서 예상56/수확34.
- 누적 실패: 주행105 1건(야간 지시 전), 파라미터 수집2건, 팔/시뮬9건. SEC01 3건의 선행 원인은 비대상 과실 이탈이며 이후 정지 확인 실패로 종료. SEC03 평가 ID 매칭2건, SEC06 같은 목표의 시간초과/낙하 감시4건. 상세/한계/원본 위치는 PROJECT_STATE §87.
- 원본 및 보고 스냅샷 보존, 예찰 캐시 재사용 실제 확인. 실물 영향 없음, 복원 대상 운영 변경 없음. 문서만 미커밋·미푸시이며 시험은 계속 진행한다.

## SCOUT-CACHE-OVERNIGHT-20261020 — 성공 예찰 재사용과 SEC01~16 야간 실행

- 승인: 사용자 성공 예찰 보존/수확부터 재시작 및 밤샘16SEC 순차 진행 요청, D-050.
- 대상: `tools/run_section_campaign.py`, `tests/test_section_campaign.py`, 기존 상태/결정 문서. 시뮬 시험 실행 도구만 변경하며 공통·실물·운영 미션/팔/주행 판정에는 영향이 없다.
- 전후: 이전에는 실패할 때마다 전체 재시작 후 예찰부터 실행했다. 이제 성공 예찰 원본을 캠페인별/SEC별 캐시에 저장하고 재시작 후 모든 window를 수확부터 실행한다. 현재4회차의 성공8window/예상12개를 보존했고 진행 중 작업을 중단하지 않았다.
- 야간 실행: 현재 SEC01 감독자 종료 후 같은 캠페인에서 SEC02~16으로 이어지는 독립 서비스를 활성화했다. Domain13/SUBNET, 시간 제한 없는 시험/읽기 전용 기록, 자동 절전 방지를 확인했다. 시도별 실패·수량·로그를 유지하고 성공한 SEC만 다음으로 넘긴다. 전체 완료 후 종료한다.
- 검증: 캐시/재시도/SEC01→SEC02~16 재개 회귀6개, 실제 ROS 메시지 왕복 보존, 셸 문법, diff 검사 통과. 실제 캐시 재시작 E2E/16SEC 완주 확인 전이며19:20 KST 현재 W001·W002 완료/W003 진행이다. 상세 PROJECT_STATE §86 및 runs/sec01_goal_time_fix_20261020_183345.
- 복원: STOP으로 시험 정리 후 이번 실행기/시험 diff만 역적용한다. 원본/캐시 데이터는 보존한다. 미커밋·미푸시.

## SEC01-GOAL-TIME-RETEST-20261020 — W001 수확 완료 및 W002 명령 전달 중단 기록

- 승인: 사용자 재시험 진행 지시. D-049 공통 시각 수정본·Domain13/SUBNET으로 기존 캠페인을 계속한다. 이번에는 운영 코드/설정 변경 없이 계측·문서만 추가했다.
- 결과: 2회차 예찰9window/예상13개 성공. W001 도착→팔 실행→박스 센서1개→접힘 확인→Action SUCCESS. W002는0.6704m 이동을 시작했으나 최종 cmd_vel 출력이 재개되지 않아105, 팔 미실행이다. RPP는전진0.1m/s를 계속 내고 회전 상태는false였으므로 이전 도착 시각 불일치와 구분한다.
- 증거: 두 ROS 기록기에서 W002 cmd_vel0메시지, sim transport6294수신 유지/거절0/마지막0명령을 확인했다. 원본·수량·실패를 보존하고 전체 재시작 후 재시도 중이다. smoother 내부/DDS 책임은 아직 미확정이며 읽기 전용 endpoint·lifecycle 기록을 추가했다. 상세 PROJECT_STATE §85.
- 영향/복원: 실물 및 공통 운영 동작 변경 없음. 시험을 끝내려면 해당 캠페인 STOP과 기록기 서비스 종료를 사용하고 원본 로그를 보존한다. 자료 runs/sec01_goal_time_fix_20261020_183345. 전체 SEC01 성공·105 전면 해결을 주장하지 않는다. 미커밋·미푸시.

## COMMON-GOAL-TIME-20261020 — 추종과 도착 판정 시각 일치

- 승인: 사용자 “당연히 일치시켜야지 뭐하는거야?”, D-049. 이전 계측으로 확인된 공통 시간 불일치를 수정한다.
- 대상: 공통 `robot/ros_ws/src/nav2_controller`의 공식1.3.12 원본과 제한된 controller_server.cpp/.hpp 수정·회귀 시험, `scripts/build.sh`. 원본 출처·해시/Apache-2.0 라이선스 보존. sim 전용 코드나 실물과 다른 성공 조건을 추가하지 않는다.
- 전후: 이전에는 경로 생성 시각의 목표를 변환하다 과거 TF가 없으면 latest를 사용했다. 이후에는 실제 제어에 사용한 로봇 pose를 최종 판정에 전달하고 그 stamp로 목표를 변환한다. 같은 시각 TF 실패는 기존102 경로로 전달한다. 도착/진행 허용치·stateful·경로 연장·물리·수확 정책 변경 없음.
- 실물 영향: real/sim 모두 공통 workspace overlay의 ControllerServer를 사용한다. 실물에도 재빌드·환경 로딩·재시작이 필요하며 실제 장치 배포/주행은 이번에 하지 않았다.
- 검증: 원본 별도 빌드에서3.94cm/5.10cm 불일치로 실패 재현, 수정본6회귀+11원본 기능 시험 통과, 기존 설정 검사39통과. lint통과, cppcheck17항목은 도구 버전 정책으로skip. 실제 SEC01은 새 캠페인183345에서 재시험 중이며 첫 시도는 주행 전 param dump20초 시간초과로 실패했다. 105 해결/전체 완주는 아직 미확정. 상세 PROJECT_STATE §84.
- 자료/복원: runs/nav2_goal_time_fix_20261020 및 runs/sec01_goal_time_fix_20261020_183345. 수정 전 캠페인18회차는 로그 보존 후 STOP. 복원은 이번 공통 overlay 소스/build/install만 제거하고 공통 workspace 재빌드·새 환경에서 기본 Nav2 prefix 확인 후 재시작한다. 미커밋·미푸시.




## NAVIGATION-PARITY-20261020 — 실물 담당 브랜치와 주행 성공/실패 판정 비교

- 승인/목적: 사용자 Hyaline-52 실물 브랜치와 공통·실물·시뮬 주행 정밀 비교 요청. 운영 소스/설정 변경 없이 분석한다.
- 비교: 원격 최신 real6f21119, 이전afdcc05, main e735dc9+기존 sim override. 최신 real와 운영 소스/인터페이스130개 동일, 목표·진행 판정 기준 동일. 실제 제어 설정은 접근 lookahead0.1/0.4m, RPP stateful/끝점 연장, costmap/footprint 등 차이가 있다. 현재 main real도 실물 성공 설정과 다르다.
- 증거/결론: PROJECT_STATE §81 및 runs/navigation_parity_20261020. 실패4회차 명시 controller 파라미터101개 일치, controller_server 실제105 기록, 기존 오프라인 시험38개 통과. 실물 런타임/바이너리·동적 설정은 미확인. 같은 판정만으로 공통 코드 결함을 확정하지 않는다.
- 변경: 문서/분석 산출물만 추가. 공통/실물/sim 운영 동작 영향 없음. 되돌릴 경우 이번 문서 절과 비교 산출물만 제거하며 원본 시험 로그는 보존한다. 미커밋·미푸시.

## SIM-ROS-DISCOVERY-20261020 — 후속 시험 Domain13/SUBNET

- 승인: 사용자 “다음부터 시험할때 ROS Domain 13, 통신 범위 SUBNET”.
- 대상: `tools/run_section_campaign.py`, `tools/continue_section_campaign.sh`, 기존 감독자 시험 fixture. 기본 Domain74→13, discovery LOCALHOST→SUBNET; 새 manifest에 discovery 범위를 기록한다. 현재 실행은 유지하며 후속 새 실행부터 적용한다. 공통/실물 설정 영향 없음.
- 검증: 기존 감독자 회귀 시험과 셸 구문 확인. 실제 Domain13 관제 연결 시험은 아직 미실행이다. 복원은 해당 기본값/셸 인자만 역적용한다. 미커밋·미푸시.

## SEC01-RETEST-20261020 — SEC01 단독 통합 재시험

- 승인: 사용자 SEC01 재시험 요청. 소스·설정은 추가 수정하지 않고 D-044~046 적용본을 실행한다. 실물 영향 없음.
- 기존 navfix 캠페인은 STOP 정상 종료·자료 보존. 새 `sim/runs/sec01_retest_20261020/`에서 SEC01 예찰→전체 window 수확, 실패 시 전체 Isaac/ROS 재기동·동일 SEC 재시도를 시작했다. SEC02 이후는 실행하지 않는다.
- 10:28:20 KST 준비/10:28:29 예찰 Goal 전송과 실제 Nav2 수정 파라미터를 확인했다. 아직 SEC01 완료를 주장하지 않는다. 서비스 `farm-sec01-retest-20261020`, 상세 PROJECT_STATE §79. STOP 파일로 중단 가능. 미커밋·미푸시.

## STUDENT-AVAILABLE-TARGETS-20261020 — 예찰 예상량과 무관하게 팔 관측 목록 수확

- 승인: 사용자 “로봇팔 입장에서 할수있는만큼만 하고 넘어가야지 다음윈도우로”. D-040의 예찰 기대개수 일치 전제는 이번 요청으로 폐기한다.
- 대상/전후: `farm_sim_devices/student_session.py`에서 expected_count 양수/영상 작업가능 개수의 동등성 조건을 제거했다. 기존3초 관측시간 후 팔 카메라로 확인된 익은 과실 중 기존 작업 범위를 통과한 목록만 실행한다. 적거나 많아도 수량 불일치로 실패하지 않는다. 목록0은 측정 정지/접힘 확인을 거쳐 SUCCESS/수확0/실패0으로 반환한다. 원래 expected_count는 요청·결과·로그의 참고값으로 보존한다. 실제 수확량은 기존 평행3빔 통과로만 센다. 주행·충돌·팔 제어/정지 실패는 기존 오류로 전달한다.
- 영향: 공통 메시지/미션/실물/전달 vendor·가중치·작업 범위를 변경하지 않았다. 기존 공통 Action은 예상량과 실수확량이 달라도 SUCCESS를 전달하므로 시뮬 Student 어댑터만 수정했다. 기존 inventory_timeout_s 설정 이름은 호환을 위해 유지하며 현재 목록 확정 관측시간으로 사용한다.
- 검증: assignment11·팔 세션19·팔 ROS9·캠페인 감독자1, 총40시험 통과. 예상량보다 적음/많음/예상0/작업범위 밖/관측0과 원래 예상9→실제0/1/2의 ROS 결과 보존을 검사했다. 실제 Isaac/ROS에서 예상1·작업가능0 요청은 sim4.4초에 SUCCESS/수확0/실패0/safe_stopped=true를 반환했다. 로그 `sim/runs/inventory_policy_20261020/zero_action.log`, 원본 `sim/runs/harvest_test_ui/20261020T002245_w_1q7wfa/`.
- 이번 변경 추가 검증 기록: 실제0대상 시험의 최초 검증기는 ArmActionClient 반환 dict에 없는 expected_count를 조회해 해당 검사만 false였다. 원본 요청(request.json)의 expected_count=1로 정정한 독립 검증 `sim/runs/inventory_policy_20261020/zero_action_verified.json`에서10검사 통과를 확인했다. 최초 보고서는 보존했다. 새 서비스 `farm-section-campaign-20261020`는09:24 KST 시작했고 새 manifest의 Student 소스 SHA가 수정본과 일치함을 확인했다.
- 반복 시험: 기존 `section_campaign_20261019`의 실패46건과 정책 교체를 위한 중단47회차는 보존한다. 구정책·신정책 자료를 섞지 않도록 새 `section_campaign_20261020`에서 SEC01부터 같은 반복 조건으로 재개한다. 실행기가 Student 세션 소스 SHA도 manifest에 기록하도록 보완했다.
- 복원: 이번 student_session.py/시험/실행기 변경만 역적용한다. 새 캠페인은 STOP 요청 후 종료 확인/서비스 중지한다. 미커밋·미푸시.

## SECTION-CAMPAIGN-20261019 — 16개 SEC 예찰·전체 window 수확 반복 시험

- 승인/목적: 사용자 요청에 따라 SEC01~SEC16 각각 예찰 성공 후 반환된 모든 window를 수확한다. 중간 실패 시 자료를 보존하고 Isaac·ROS 전체를 종료/재기동하여 같은 SEC의 예찰부터 반복한다. 재시도 횟수 제한은 없다.
- 대상: `sim/tools/run_section_campaign.py`, `sim/tools/continue_section_campaign.sh`, `sim/tests/test_section_campaign.py`. 공통 로봇 소스·운영 파라미터·실물 설정을 변경하지 않는다. 기준 HEAD `e735dc9`.
- 시험 조건: 독립 ROS domain74/localhost, headless, RViz OFF, 태그 보정 ON, 현행 D435 Student 및 평행3빔, 기존 station 시작. 비교 가능한 독립 시도를 위해 성공 후 다음 SEC도 전체 스택을 새로 시작한다. 예찰 SUCCESS + 반환된 모든 수확 Action SUCCEEDED/SUCCESS/failed_count=0일 때 SEC 성공이다. 예상 수량과 실수확 수량의 일치를 별도로 강제하지 않으며 window0은 empty_harvest로 표시한다.
- 자료: `sim/runs/section_campaign_20261019/` 아래 시도별 Action 전체 요청/피드백/결과, cmd_vel_nav/cmd_vel/odom/AMCL/TF/clock/ROS 경고, 실제 Nav2 파라미터, 프레임 성능, 호스트 GPU/프로세스 상태, ROS/Isaac 로그 및 기존 예찰/구동/팔/평가 산출물 사본. 실패 자료는 덮어쓰거나 삭제하지 않는다. 원본 설정 해시·실행 명령·PID·시각을 기록하고 summary/failure_analysis JSON으로 집계한다.
- 지속 실행: 사용자 transient service `farm-section-campaign-20261019`가 현재 감독자 종료 후 배타 잠금을 얻어 체크포인트를 인계한다. 중단된 시도는 시스템 실패와 별도 표시하고 같은 SEC를 재시도한다. STOP 파일이 있으면 중단한다. 저장공간10GiB 미만이면 증거 보존을 위해 BLOCKED로 중단한다.
- 검증: Python 컴파일/셸 구문/기존 ROS·비전 import/16SEC 설정 확인. 감독자 시험은 실패2회→같은 SEC 재시도→16SEC 완료/18시도·36프로세스 종료 호출·재개 시 성공SEC 재실행 없음/실패 자료 보존을 검증했다. 이는 실제 로봇 성공률 시험과 구분한다. 실제 첫 SEC01 예찰은 17:40 KST 시작; 캠페인 전체 완료는 아직 미확인이다.
- 복원: 캠페인 폴더에 STOP 파일을 만들고 시험 종료/로그 보존을 확인한 후 사용자 서비스를 중지한다. 새 실행기/시험 파일 및 이 기록만 되돌린다. 실행 결과는 증거로 보존한다. 미커밋·미푸시.

## HARVEST-COMPLETION-PROFILE-20261016 — 이동 전용 실행 경로의 팔 생략 수정

- 요청/범위: 팔 작업 없이 완료되는 현상 확인 요청. 실제 런치·서버 파라미터·로그로 ARRIVAL_ONLY_NO_HARVEST 선택 확인.
- 대상/전후: 실제 사용 중인 `runs/navigation_smoke_20261014/harvest_runtime.yaml`의 harvest_config 참조를 이동 전용 시험 JSON→현행 canonical harvest_task.json으로 변경. 다음 시작부터 ARRIVAL_THEN_ARM을 선택한다. 이전 이동 전용 JSON은 증거로 보존했다. 공통/실물 변경 없음.
- 검증: 공통 환경 로더로 수정 경로를 읽어 팔 작업 정책/팔 활성화/60Hz 확인. 기존 실행 중 서버는 재시작하지 않았으며 사용자 작업 중단·Goal 전송 없음. 재시작 후 시작 로그와 실제 수확 완료는 아직 이번 실행에서 미확인.
- 복원/반영: `runs/harvest_completion_20261016/harvest_runtime_before.yaml` 또는 참조 한 줄 복구. PROJECT_STATE §67과 실행 가이드에 재시작 필요 명시. 미커밋/원격 미반영.

## WHEEL-TIRE-FIX-20261016 — 저속 회전 접촉 단면 수정과 정지 유지 보완

- 승인: 사용자 “진행해 … 원인을 … 설명해” 실행 요청. 기존60Hz 통합과 사용자 변경 보존, 공통/실물 수정 없음.
- 대상: `assets/robots/harvest_count_test/harvest_robot.usd`, `farm_sim_devices/wheel_servo.py`, `tests/test_wheel_servo.py`, `tools/rebuild_harvest_tire_collisions.py`, 진단 결과와 PROJECT_STATE §66/DECISIONS D-039/이 기록.
- 전후: 평평한50mm 원통 충돌선에서 같은 +0.05rad/s 4초 입력0.970° 정체→같은 외경/폭의 둥근 native 원통 묶음10.425° 회전. 평평한 단면 분할 대조군0.953°로 개수 증가 효과를 배제했다. 정지 유지 때 매 tick 적분 초기화→정지 전환에서만 초기화/유지 중 외란 오차 적분. 원래 kp1/ki4/상한2 유지(kp8 후보 탈락·복구).
- 검증: 바퀴 단위5개/자산 범위 검사 통과.46sim초 전후진·회전·정지 특성 기록, 실제 Nav2 양방향 정렬/0.5m 이동3개 정상 완료, 실제 Teacher 팔 Action2/2 적재·복귀·safe_stopped. 중속 급정지 피크2° 목표는 약3.4°로 미달한 계측 한계를 명시했다. 전체 농장 연속 미션·실물·밀집3개 복귀·접촉 취소는 이번 인증 범위 아님.
- 복원: `runs/wheel_contact_20261016/before_apply`의 자산과wheel_servo.py만 원위치 복사. 기존60Hz 통합을 되돌리지 않는다. 미커밋/원격 미반영. SHA와 결과/시행착오는 같은 runs의applied.json/verification_final.json을 따른다.

## WHEEL-CONTACT-DIAG-20261016 — 무부하/접지 분리 및 후보 탈락 기록

- 승인: 사용자 sim 전용 구동·접지 개선 방향 승인. 대상은 `sim/runs/wheel_drive_20261016/` 진단 실행 사본/집계와 PROJECT_STATE §64 정정·§65, DECISIONS D-038, 이 문서다.
- 전후: 속도 보정 상한 부족을 근본 원인으로 단정했던 설명을 철회했다. 무부하 정상 추종/접지 정체, 접촉 폭 영향, 질량 증대·유한 force drive·직접 토크 PI 후보 미통과를 확인했다.
- 운영/실물 영향: 이번 진단은 운영 소스·USD·설정 및 공통/실물 변경 없음. 사용자 확인 결과 공식 공개 자료에 필요한 질량/감속비/출력축 토크 사양 없음. PI 상한 확대, 타이어 폭 축소, 임의 질량/토크 변경은 운영에 반영하지 않았다.
- 검증/복원: 실제 Isaac CPU60Hz 격리 시험의 관절 위치 차분·차체 회전·정지 구간 집계. 전체 Nav2/실물 회귀는 미실행. 시험 출력과 문서만 있어 운영 복원 대상 없음. 미커밋/원격 미반영.

## HARVEST-105-20261016 — 실제 정체 원인 분리

- 요청/범위: 사용자105 발생 당시 움직이지 못한 원인 확인 요청. 운영 소스·설정·공통 코드·자산 수정 없음. 기존 프로세스 종료 이후 별도 포트·scene으로 접촉/구동 비교 시험만 실행했다.
- 결과: 실제 명령 수신 정상, 바퀴 PI 보정±2rad/s 포화와 차체 정체 확인. 실패 자세에서 동일 +0.05rad/s 10초 입력에 기본0.919°/보정 상한20 시험26.448° 회전. 내부 충돌 제거·GPU·drive gain/type 변경만으로는 미해결. 마찰 감소/solver 반복 증가로 개선돼 현행 접지·구동 보정 조합의 한계로 확인. 운영 상한20 적용은 하지 않았다.
- 검증/제약: 유효8개 격리 시험의14sim초 trace/contact와 실제 수신/휠/차체 로그 집계. 최초 마찰 시험은 instance 편집 오류로 제외하고v2로 재시험. 종료 지연으로 소유한 시험 프로세스만SIGTERM 정리. 전체 Nav2 재주행/실물 미실행. 수치와 다음 검증은 PROJECT_STATE §64.
- 파일/복원: `sim/runs/harvest_105_20261016/`의 진단 산출물, PROJECT_STATE §64 및 이 기록만 추가. 운영 복원 대상 없음. 문서·결과 미커밋, 원격 미반영.


## TEACHER60-ACTION-20261016 — 수확 Action과 팔 실행/국소 물리 연결 확인

- 승인: 사용자 수확 액션에60Hz Teacher 팔 움직임 연결, 향후 카메라 정책 교체, 근처 과실만 물리 적용 요청.
- 대상: `farm_sim_runtime/{fleet_config.py,launch/harvest.launch.py}`, `sim/tools/check_teacher_action.py`, `check_teacher_harvest.py`, sim 액션 설정/통신 시험과 실행 문서. 기존 공통 `HarvestMission`/`ArmActionClient` 및 sim 팔 실행 연결을 재사용하며 공통·실물 소스 변경 없음.
- 전후: 기존 ARRIVAL_THEN_ARM/내부 팔 Action 기본값은 유지하고 팔 OFF·endpoint 불일치·국소 물리 OFF를 시작 전에 거부한다. 미래 카메라 모델 교체는 관측/정책/대상 선정 어댑터 경계로 명시하며 새 추상화나 Student 대역을 넣지 않는다.
- 검증: 실제 ROS→UDP→Isaac로2개 적재·물리 복귀·접힘·정지 및 ROS SUCCESS/2개 수량 확인. 활성 과실0→4→2/전체288. 취소 시험 상세와 로그는 [PROJECT_STATE §63](../../docs/PROJECT_STATE.md#63-수확-action의60hz-teacher-팔-실행과-주변-과실-물리--2026-10-16). 관련 최종62개, sim3패키지 build PASS. 전개 중 취소는 실제 정지/CANCELED 확인, 접촉 중 취소는 CANCEL_UNCONFIRMED로 미해결. 외부 주행→팔 호출은 단위시험, 이번 실제 Nav2 미실행.3개 밀집 복귀 문제는 미해결.
- 복원/영향: 이번 사전검사와 검증 도구/문서 변경만 역적용하면 §62 상태다. 이전60Hz 모델/정책 통합을 되돌리지 않는다. 공통·실물 영향 없음. 새 launch는 재시작 필요. 미커밋·원격 미반영.

## TEACHER60-R2-20261016 — 60Hz Teacher 통합,480Hz 폐기

- 승인: 사용자 “그렇게 적용하고480hz는 폐기하자”. 기준 `7b0e1a4` 위 미커밋 작업. sim 전용 변경이며 공통·실물 파일 변경 없음.
- 대상: `assets/robotarm_teacher/`, `assets/robots/harvest_physics/teacher_arm_reference.*`, sim config5개, `farm_sim_devices`의 Teacher/줄기/장치/세션과 `_teacher_vendor`, runtime 물리 스케줄/자산/UI/진단, 해당 시험·fixture·import/replay 도구 및 실행 문서. 이전4개 체크포인트·staged_teacher/kernel 제거.
- 전후: 기존480Hz/response5·분리 정책 실행을 전달60Hz r2의 JIT+원본 단계 제어/response6/마찰2.2/단일 바닥/실제 속도 제한으로 교체. 유휴·수확60Hz/정책20Hz/렌더30Hz. 낮은순·물리 복귀 후 다음 목표, 적재 보존. SDK qd 잔류에 대한 정지 판정은 실측 q 변화·hold 오차·bounded qd를 함께 검사한다.
- 검증: 전달 SHA/내부1438개 일치, 독립 GPU26/32 재현,239tick 원본 명령 비교 최종목표 최대4.06e-6rad. 농장 단일1/1·연속2/2 적재/복귀/접힘/정지 PASS.3개 배치는 첫 적재 후 복귀 중 비목표 분리로 안전 정지(1개 적재/뒤2개 미시도),3개 순차 성공은 미완료. 상세와 최초 fixture 불일치 기록은 [PROJECT_STATE §62](../../docs/PROJECT_STATE.md#62-60hz-teacher-r2-적용과480hz-폐기--2026-10-16) 참조. 관련108개+84subtests, 추가 과실/배치17개+9subtests, USD 팔11개·과실19개 PASS. sim3패키지 빌드 PASS. 로그 `sim/runs/teacher60/`.
- 실물 영향/한계: 직접 영향 없음. 공유 Isaac scene 시간은60Hz로 고정되므로 기존 주행 사용자 확인과 이번 주기 변경 후 전체 연계 재검증을 구분한다. Student·실물·전체 Nav2 연계·실측 분리력 대응은 미검증. 기존 실행 세션은 유지했고 재시작이 필요하다.
- 복원/전달: sim 소스·자산·설정을 기준 커밋 버전으로 함께 복원 후3패키지 재빌드. 새 모델과480Hz를 혼용하지 않는다. 변경 파일과 삭제 목록만 담은 `sim/runs/teacher60/teacher60_changes.tar.gz` 및 패치 적용 방법은 같은 디렉터리 `PATCH_README.txt`. 현재 workspace에는 이미 적용했으므로 재적용 불필요. commit/push 없음.

## HARVEST-PROGRESS-AUDIT-20261014 — 최근 수확 주행 두 건 실패 진단 (미해결)

- 요청: 최근 수확 주행 중 제자리회전 후 ABORTED 원인 확인 및 현재 작업 커밋·푸시. 운영 코드·설정 변경이나 추가 주행 없이 기존 로그를 대조했다.
- 대상: `smoke_33b0484b8905`(16:41:21 KST), `smoke_48ad6a58d594`(16:50:29 KST). 두 건 모두 목표 (-6.015, 3.5278)로 WINDOW_MOVE 중 Nav2 `105: Failed to make progress`. 장치 세션은 각각 `4f43c6d8925a4201b06a6051bb44d861`, `c4518e851e42419897b6c52d236b6312`; 원본은 로컬 `sim/runs/drive_diagnostics/<session>/harvest_01.jsonl` 및 `sim/runs/harvest_motion/`에 있다(실행 로그는 Git 제외).
- 확인: 목적지 약 3.7m 앞, 실제 위치 x≈-6.02/y≈7.21에서 두 번 모두 정체했다. 두 번째 주행 sim 185.388초에 전진 0.1m/s·회전 -0.00372rad/s 명령, 좌우 바퀴 목표 약 -1.2rad/s였으나 측정 오른쪽 +0.468/왼쪽 -1.876rad/s. 제자리 보정 명령보다 실제 차체 방향 이탈이 먼저이며, 이후 진행 검사(10cm/20 ROS초) 실패로 중단됐다. 도착 판정/다음 주행 시작 조건의 실패가 아니다.
- 태그: 첫 실패 Goal 중 보정 요청 없음. 두 번째 마지막 태그 보정은 sim≈181.02초, 물리 방향 이탈은 ≈184.9초 이후. 태그 보정이 직접 회전을 유발했다는 근거는 없다.
- 미확정: 반복 위치의 물리적 접촉·걸림 또는 구동/물리 응답 이상을 의심하나, 접촉 대상·힘이 기록되지 않아 특정 충돌이나 시뮬 전용 결함으로 확정하지 않는다. 다음 검증은 해당 위치의 접촉 쌍/힘·바퀴 구동 힘을 동시 기록하는 재현 시험이다. 기존 0.313/0.35 성공 시험은 이 위치를 지나지 않아 이번 문제를 검증하지 못했다.
- 실물 영향/복원: 이번 추가는 진단 기록뿐이며 주행 동작 변경 없음. 이 항목 삭제로 문서만 복원 가능. 본 커밋은 누적 통합 작업의 체크포인트이며 수확 실패 해결 완료를 뜻하지 않는다.

## SHARED-NAVIGATION-CODE-20261014 — 공통 구현 한 벌과 변경 가능한 설정

- 승인: 사용자 “똑바로 통합해”와 후속 “같은 코드를 … 동일한 파일”, “설정값은 … 바꿀 수 있어야”, “sim … 전용 파일만” 지시. 초기 편집의 설정 override 금지를 제거했다. 공통/실물/시뮬 연결 변경 범위이며 기존 미커밋 작업을 보존했다.
- 공통 실행: `farm_navigation/configuration.py`의 설정 병합/공통 Nav2 로딩, `harvest_robot/configuration.py`의 수확 기본값 로딩, `farm_tag_localization/{launch_support,ros_capture,detection}.py`의 태그 연결/기록/검출 변환을 양쪽에서 호출한다. sim 태그 구현은 공통 import wrapper만 남긴다. 실물 USB 도구도 공통 태그 ID/크기/검출 override 경로를 사용한다. 수확 태그 구역 신호는 공통 단계 callback으로 전달한다.
- 데이터: `robot/config/navigation/`과 `robot/config/localization/common_observation_model.json`을 한 원본으로 참조한다. 기존 sim/real Nav2 파일은 해당 참조와 환경 데이터, 필요한 `overrides`만 관리한다. 공통 기본값 변경은 양쪽에 반영되며 환경별 수치 변경도 허용한다. BT/기존 모델 경로는 링크로 호환한다. 지도 생성기는 로컬 튜닝값을 삭제하지 않고, 실물 시험 manifest는 참조한 공통 파일까지 기록한다.
- 기본값 영향: 수확 RPP/SimpleGoalChecker 및 끝점 선분연장을 전달 `bf10fcd` 기준으로 정렬했다. 4cm/2.5°·0.10m/s·CLOSED_LOOP·진행20ROS초·Goal300wall초가 공통 기본값이다. 이전 실험 Settling/Stopped 소스는 보존하지만 기본 선택에서 제외했다. 종료 잔차 비차단(D-029)과 예찰 RPP.stateful=false는 유지한다. CPU 물리·휠 PI·센서 교정은 이번에 바꾸지 않았다.
- 검증: 공통4/sim3 패키지 빌드, 주행20·수확90·태그80·sim 통합32·launch9 검사 PASS. 추가 관련 fixture41개 및 경로371개 PASS(일부 시험은 앞 검사와 중복). 별도 real/sim 셸에서 주요9개 모듈의 실제 원본 파일 경로가 동일함을 확인했다. CPU/GUI/RViz/카메라3개/태그ON 전체 실행 결과는 PROJECT_STATE §52와 [검증 JSON](changes/SHARED_NAVIGATION_CODE_20261014.json)에 기록한다.
- 한계/적용: 실물 PiCam 자료 미확보를 configured:false로 명시했고 실제 모터 펌웨어/응답 동등성은 미검증이다. 실물 주행/배포는 하지 않았다. 사용 중인 팔OFF smoke 프로파일도 공통 참조로 갱신했다. 소스/설정 적용에는 launch 재시작이 필요하다. 이번 참조·로더·호출 변경을 함께 역적용해 복원하며 다른 누적 변경은 유지한다. commit/push 없음.


## SIM-REAL-NAVIGATION-AUDIT-20261014 — 추가 수정 전 동등성 감사

- 사용자 실물/시뮬 차이 검증 요청. 운영 코드·설정 수정/재주행 없이 실제 선택 프로파일·공통 호출·전달 이력·최신 실패 로그를 대조했다. [감사 JSON](changes/NAVIGATION_SIM_REAL_AUDIT_20261014.json), PROJECT_STATE §51에 근거·값·한계를 기록했다.
- 공통 구현 사용과 동작 일치를 혼동한 설명을 정정한다. 수확 도착/새 출발/진도/timeout/끝점 추종/속도/smoother 차이, 전달본의 진입·작업 끝점 정책 미반영, 실물 예찰 기본 태그 연결 미완료를 확인했다. 하위 바퀴PI도 공유 구현이 아니며 실물 응답 정합 미검증이다. 필요한 지도·장치 차이로 이 정책 차이를 정당화하지 않는다.
- 최신 실행은 첫 진입Goal에서 회전 지속 후 취소, 태그보정0회. 직전 작업점 도착 수정과 다른 단계이며 이번에 원인 확정/수정 완료로 기록하지 않는다. 기존 각 성공 기록은 유지하되 반복 신뢰성/실물 검증의 증거로 확대하지 않는다.
- 이번 대상은 감사 JSON/현행 문서뿐이며 문서 추가만 역적용 가능하다. 기존 미커밋 작업 보존, commit/push 없음.

## SIM-HARVEST-ARRIVAL-STATE-20261014 — 작업 도착 판정을 실물과 일치

- 사용자 수확0.313 도착 회전 반복 보고 및 기존 원인 확인·조치·CPU 검증 지시에 따른 시뮬 설정 수정. 원본은 SECTION_APPROACH 성공 뒤 WINDOW_MOVE에서 전진0/±0.06rad/s 회전을 지속하다 사용자 취소됐다. 태그 요청 직전 map XY11.34mm→보정 후26.47mm로15mm 도착 범위를 벗어났다.
- 대상: `sim/ros_ws/src/farm_sim_config/config/nav2_harvest.yaml`의 기본 SimpleGoalChecker.stateful=false→true. RPP의 위치 도착 기억과 완료 판정을 맞춘다. 실물 vicpinky 설정은 이미true이므로 수정하지 않았다. 위치 도착 확인 후 방향 정렬을 마치며 새 Goal은 이력을 초기화한다. 진입 전용 Stopped checker·허용 수치·공통 코드/PID·물성·센서·timeout은 유지한다. 작업·이탈의 기본 checker에 적용되며 출발 차단/자동 뒤돌기 추가 없음.
- 직접 CPU/태그ON/카메라3개/GUI/RViz 시험:0.313→0.35 두 Goal 모두SUCCESS, 두 번째는 재진입 없이SECTION_RESUME→WINDOW_MOVE, 태그 보정11회. 정지 후 map 거리16.20/15.48mm, 방향0.411/1.192°. 예찰 서버는 정차했으며 예찰 미션 재실행·실물·16구역·장시간 반복은 미검증이다.
- 검사: 관련 Python20개 PASS, 설치 SimpleGoalChecker 직접 재생7 assertions PASS, config 빌드/소스·설치 일치. 전후 YAML mapping 차이는 stateful 한 항목뿐이다. [검증 JSON](changes/HARVEST_ARRIVAL_STATE_FIX_20261014.json), PROJECT_STATE §50/D-031 및 `sim/runs/harvest_arrival_fix_20261014/` 참고.
- 실행/복원: 기존 및 시험 런치 종료, CPU 런치 재시작 필요. 종료 중 Isaac SIGTERM/예찰 detector -11은 미션 성공과 별도로 기록했다. 이번 stateful 한 항목/주석만 역적용해 복원하며 다른 미커밋 작업은 보존한다. 문서 갱신, commit/push 없음.

## SIM-SCOUT-PROGRESS-FIX-20261014 — 예찰 도착 상태 고정 수정

- 승인: 사용자 “원인 확인 - 조치 - 보고”. CPU에서105를 재현하고 실물·시뮬 공통 RPP 동작을 최소 수정했다. 대상은 `sim/ros_ws/src/farm_sim_config/config/nav2_scout.yaml`, `robot/config/robots/burger/nav2.yaml`의 RPP.stateful=false 및 공통 `farm_nav2_controller/test/test_settling_controller.cpp`의 대조시험2개다.
- 전후: 한번 XY 범위에 들어가면 밖으로 나가도 회전/전진0 유지 → 현재 위치가 밖이면 경로 추종 재개. CPU 재현은 태그 적용 전에도 발생했다. 따라서 태그만의 오류라는 설명은 하지 않는다. 도착/진행 허용치·물리·PI·태그·수확 프로파일·종료 잔차 비차단 정책은 변경하지 않았다.
- 직접 Isaac 검증: CPU/태그ON/카메라3개/RViz/GUI 동일 조건, 원래 station 배치. 수정 전 첫 관측에서105/ABORTED, 수정 후SEC01 5개 관측 전체SUCCESS/SUCCEEDED 및 태그 보정129회. 전후 각1회이며 실물 배포/주행·전체16구역·장시간 반복은 미실행이다. 수정 후 정지 잔여 위치25.13~40.32mm는 그대로 기록하며 정밀도 인증으로 확대하지 않는다.
- 오프라인: 설치 RPP 직접 회귀 포함 C++12개+관련 Python14개=26개 PASS. 공통 controller/시뮬config 빌드 PASS, 소스/설치config 일치, 수정 전 YAML 대비 RPP 한 항목만 변경 확인. [검증 JSON](changes/SCOUT_PROGRESS_FIX_20261014.json), PROJECT_STATE §49/D-030 및 `sim/runs/scout_progress_fix_20261014/` 참고.
- 적용/복원: 기존 실패 런치와 시험은 종료했다. CPU 런치를 재시작해야 새 설정을 읽는다. 실물 설정 로컬 반영, 실제 장치 검증은 별도다. 두 RPP 설정 추가·신규 시험만 역적용하며 기존 미커밋 변경은 보존한다. commit/push 없음.

## SIM-SCOUT-PROGRESS-20261014 — 예찰 Nav2 105 로그 조사

- 사용자 로그 확인 요청. CPU/태그ON/RVizON 실행의 SEC01 세 번째 목표에서 Nav2 FAILED_TO_MAKE_PROGRESS(105)를 확인했다. 종료 오차 추가 검사 이전의 실패다.
- 약7.4sim초 동안 전진 명령0·실제 위치 변화0.0183mm, map 추정은 목표에서36.64~54.36mm로 도착3cm 밖이었다. 실행 중 RPP.stateful=true와 progress10cm/10초를 읽기 전용 확인했다. 위치 보정 후 RPP의 XY 도착 상태 고정이 추종 재개를 막는 조건이 가장 유력하지만 내부 latch는 직접 기록되지 않았다.
- 예찰은 기존 RPP이며 수확 진입 plugin을 사용하지 않는다. CPU만의 문제/태그 오차/저속 물리 기여는 아직 미분리다. 운영 코드·파라미터 변경, 새 주행/재현 시험은 하지 않았다. 대상은 분석 JSON과 PROJECT_STATE §48뿐이며 [증거](changes/SCOUT_PROGRESS_FAILURE_20261014.json)에 세부값을 남겼다. 문서 변경만 역적용 가능, commit/push 없음.

## SIM-ARRIVAL-GATE-REMOVAL-20261014 — 종료 잔여 오차로 다음 이동을 차단하지 않음

- 요청/승인: 사용자 “어제 작업종료 오차로인해 다음주행 시작조건 막는거 빼라고했잖아”. 이전 추가 오차 검사 유지 판단을 정정한다(D-029, PROJECT_STATE §47).
- 대상/전후: 공통 `farm_navigation/navigator.py`의 정지 후 도착·재측정·진입·이탈 오차 초과 4개 예외를 경고로 바꾼다. 측정값/`accepted=false`는 그대로 기록하고 다음 이동 잠금을 남기지 않는다. Nav2 실패·정지 미확인·TF 오류는 기존대로 실패다. 현재 예찰·수확, 실물·시뮬 공통 경로에 반영한다. 제동 개선·물성·허용 수치와 새 경로 검사는 변경하지 않았다.
- 검사: `sim/tests/test_recorded_arrival_overshoot.py`와 `test_parallel_approach.py`에서 오차 기록·후속 요청·중간 단계 진행 및 실제 실패 대조를 검증한다. CPU 26.82mm 기록에서 실제 수확 단계기/작업 경로 생성기로 다음 전방 30cm Window가 재진입 없이 실행됐다. 같은 이전 목표 재시도와 다음 목표 이동을 구분하며 별도 종단 제어가 필수라는 이전 설명은 철회한다.
- 결과: 기록 재생/평행 접근 11개 + 공통14개 + 수확 단계18개 =43개 PASS, farm_navigation 빌드 및 수정 소스 런타임 import 확인. Isaac/실물 재주행은 미실행이며 과거 실제 실패 결과는 그대로 보존한다. 로그는 `sim/runs/arrival_gate_removal_20261014/`.
- 적용/복원: ROS 런치 재시작 필요. 해당 Navigator 수정 전 백업/이번 diff만 복원하고 다른 미커밋 변경은 유지한다. commit/push 없음.

## SIM-STOPPED-ARRIVAL-20261014 — 공통 진입 정지 제어와 도착 판정 수정

- 요청/승인: 사용자 “아니그래서 어떻게 조치할거야 일단 해결은 해야될거아니야”에 따라 D-027 개선 실행. 시뮬·실물의 같은 공통 주행 제어를 수정하며 물성/PI/최종 허용치는 유지한다. 실제 실물 배포·주행은 미실행이다.
- 변경: 공통 farm_nav2_controller RPP subclass는 기존 경로·충돌 검사 후 최종 XY/yaw 안에서0속도 명령을 내린다. farm_navigation은 Stopped checker 사전검사와 속도 masking 검증을 지원한다. harvest_robot/node.py의 optional approach_goal_checker_id로 진입에만 새 controller/checker를 선택하고 작업·이탈은 기존 설정을 보존한다. sim nav2_harvest.yaml/harvest_task.json, real vicpinky/nav2.yaml/harvest_real.json, farm_bringup 의존성 및 check_runtime.py를 연결했다.
- 호환/검사: 복수 checker의 일반 NavigateToPose/ThroughPoses 호환을 위해 기본 BT의 기존 일반 checker ID만 명시한 환경별 XML4개와 상대경로 해석을 추가했다. sim/tests 및 기존 진입/작업 테스트, 공통 C++ 단위검사를 갱신했다. 기존 default설정 생략 동작은 유지한다.
- 전후: 회전 중 목표각 통과 성공 → 목표 자세 안에서 제동 명령 → 속도까지 검사 → 기존0.8초 정지·최종 pose 검사. 설정만 바꾼 후보는 진입 또는 작업 회전 반복이 재발하여 폐기했다. 좁은 작업 구간에 새로운 XY 재접근/복구 회전을 추가하지 않았다.
- Isaac 직접 검증: 최종 구성 CPU/GPU 각1회 진입 정렬 완료; 전체 HarvestTask 결과는 다음과 같다. cpu_brake_01 전체결과 FAILED: 진입 6.85mm/0.279°, 작업 도착 26.82mm/0.426°; gpu_brake_01 전체결과 SUCCESS: 진입 6.87mm/0.221°, 작업 도착 11.31mm/0.778°. 팔OFF/expected_count0, 원래 카메라·태그·GUI 조건 유지. 후보의 성공·취소·무효 배치 기록도 모두 JSON에 구분 보존한다. [검증 JSON](changes/STOPPED_ARRIVAL_FIX_20261014.json), PROJECT_STATE §46 참고.
- 남은 문제: CPU 작업 지점은 Nav2 종료 뒤26.82mm map 오차로 최종검사가 거절했다. 그 사이 태그 보정도 적용됐으나 요청 변화는진행축각0.3mm수준이어서 전체 원인으로 단정하지 않는다. 안전한 기존 직선 재접근 검사도 목표방향9.777°로 거절하므로 자동 재시도하지 않는다. 진입 과회전과 별도인 작업 종단제어 문제이며 전체 미션 완전 해결로 기록하지 않는다.
- 검증: 관련86개 PASS, 정적 runtime5그룹 PASS, 공통/시뮬5패키지 빌드 PASS. 전체 geometry의 기존 연결선48 subcase 실패는 HEAD 시험에서도 동일하다. 실물 동작·모든 구간·장시간 반복·팔 수확은 미검증이며 목표 범위 밖의 원본 RPP/시뮬 저속 물리 응답 원인을 해결했다고 주장하지 않는다.
- 실물 영향/복원: 로컬 실물 프로파일도 새 공통 package가 필요하므로 실물 아키텍처에서 소스 빌드해야 한다. sim/runs/rotation_fix_20261014/*before 및 before_* 백업/이번 diff로만 복원하고 기존 미커밋 작업은 보존한다. commit/push 없음.

## SIM-ARRIVAL-REGRESSION-20261014 — 공통 주행 검증 방향과 실패 조건 보존

- 요청/범위: 사용자 “그래 그 방향성으로 가야지”. 시뮬 모델 오류와 실물에서도 가능한 공통 제어 실패를 분리하고, 성공을 위한 시뮬 튜닝으로 실패를 가리지 않는 D-027을 기록했다. 운영 코드/설정 변경 없음.
- 변경: `sim/tests/test_recorded_arrival_overshoot.py`가 기존CPU/GPU 성공3·실패3의 실제 도착 좌표를 공통 Navigator 종료 경계에 재생한다. 정지 확인 뒤 같은 시각 pose 사용, 과회전 거절/성공 대조군 유지, 실패 후 새 이동 우회 차단을 확인한다. 기존 증거와 허용치는 그대로다.
- 검증: ROS Jazzy 환경에서 `python3 -m unittest sim.tests.test_recorded_arrival_overshoot -v` 1검사/6기록조건 PASS. I/O를 대체한 오프라인 회귀이며 물리/Nav2 재실행·과회전 수정·실물 검증이 아니다. 회전 공간 검증 없는 공통 자동 재정렬은 도입하지 않았다.
- 실물 영향/복원: 실물·공통 실행 코드 및 USD/PI 변경 없음. 시험 제거만으로 되돌릴 수 있으며 기존 실패 증거·다른 미커밋 변경은 보존한다. 상세 PROJECT_STATE §45. commit/push 없음.

## SIM-ROTATION-ROOT-CAUSE-20261014 — 진입 정렬 과회전 분석

- 구분/요청: 사용자 “6도 이상의 오차 … 원인 분석”. 분석 문서·격리 시험 산출물만 추가. 운영 코드/설정·USD·허용치 변경 없음. 기존 main/62a80ed 미커밋 변경 보존, commit/push 없음.
- 결과: 6~7°는 실제 차체 과회전이며 최종2.865° 허용치 초과를 상위 도착 검사가 정상 차단한다. 저속 구동 응답 저하→시뮬 PI 누적→회전 속도 상승→측정 속도를 따르는 RPP 감속 제한→회전 중 Nav2 순간 도착 판정→제동 중 추가 회전의 흐름을 기존 실패3회에서 확인했다. GPU 실패는 첫 기록된0명령 뒤에도 최대4.77° 더 회전했다. 정확한 물성/접촉 원인은 미확정이며 정지 후 PI 적분 잔류는 아니다.
- 격리 검증: ROS/Nav2 없이−0.06rad/s를8sim초 명령했다. 기본 스테이션−90°에서 CPU23.57°/GPU26.41°, 실패 방향−71.03°에서는 진입 위치CPU0.80°/스테이션CPU0.69° 회전, 두 후자는 PI 적분 상한2.0 도달. 방향에 따른 시뮬 구동 응답 차이를 확인했다. 각1회이며 전체 Nav2 실패 재현 시험은 아니다. PI 제거 시 정상 방향에서도 CPU1.61°/GPU0.09°에 그쳐 단순 제거는 해결책이 아니다. 모든6조건14sim초 계산 완료, app.close 대기로 종료−15, 시험 프로세스 잔류 없음.
- 원인 범위: 명백한 cmd 월드축/로봇축 혼동 없음. 기존6회 정지 map/world yaw 차이≤0.184°, 실패 태그 적용0회. CPU/GPU 선택이나 태그 변경만으로 해결할 근거 없음. 다음은 방향별 바퀴 구동력·접촉력 계측, 시뮬 PI 포화/제동 수정 검증 후 동일 Nav2 반복 시험이다. 허용치를 풀지 않는다.
- 근거/복원: [분석 요약](changes/ROTATION_OVERSHOOT_ANALYSIS_20261014.json), [추적 그래프](changes/ROTATION_OVERSHOOT_20261014.png), `sim/runs/rotation_root_cause_20261014/`. 상세는 `docs/PROJECT_STATE.md` §44. 문서/JSON 검증 완료; 실행 코드 변경이 없어 복원할 운영 변경 없음.

## SIM-DOC-20261002-001 — 인수 검토 및 작업 규칙 기록

| 항목 | 내용 |
|---|---|
| 일자 | 2026-10-02 |
| 구분 | 문서·작업 규칙. 실행 코드·설정 변경 없음 |
| 기준 자료 | 사용자 첨부 `farm_project.zip`, `SUMMARY_인수인계서.md`, 프로젝트 기획·시뮬레이션 파트 문서 |
| 승인 근거 | 이번 사용자 요청: 변경사항 검토, 시뮬 전용 변경의 폴더 분리, 공통 코드 사전 확인 및 변경 기록 |
| 대상 파일 | `AGENTS.md`에 규칙 추가, `sim/AGENTS.md`, 이 문서, `sim/docs/INTEGRATION_REVIEW_20261002.md` 추가 |
| 이유 | 실물 담당자 소스를 기준으로 시뮬 통합을 시작하면서 실물·공통 코드에 대한 영향과 승인 범위를 명확히 하기 위함 |
| 변경 전후 | 기존 구현 합의를 보존하고 시뮬 수정 위치, 공통 변경 승인, 변경 기록 기준을 추가 |
| 실물 영향 | 실행 소스·설정·모델·메시지·실물 자산 변경 없음 |
| 직접 검증 | 기존 오프라인 시험 44개 통과. 두 환경 설정 로드 성공. 시뮬 그래프 128노드/112엣지/16개 약연결 성분, 실물 18노드/40엣지/1개 약연결 성분 확인 |
| 미실행 | ROS 2 빌드·통신, 새 State 흐름 전체 시험, VisionRuntime 시험, YOLO 실행, Isaac Sim 통합, 실물 주행 |
| 복원 | `AGENTS.md`의 이번 추가 절만 제거하고 이번에 추가한 `sim/AGENTS.md`와 문서 2개를 제거. 다른 변경이 누적된 뒤에는 해당 기록의 변경분만 되돌릴 것 |

원본 ZIP SHA-256:

`ca092228082a9e47b6fa79de8878408923f82d9ca9dbfa328811811a65728b24`

공통 실행 코드 수정 승인을 받은 항목: 없음.

## SIM-CONFIG-20261002-002 — 시뮬 설정 실제 분리

| 항목 | 내용 |
|---|---|
| 일자 | 2026-10-02 |
| 구분 | 시뮬 설정·진입점·출력 경로. 공통 ROS 실행 소스 및 실물 설정 변경 없음 |
| 승인 근거 | 사용자 후속 요청: “시뮬레이션 설정은 sim 폴더안에 있어야돼. 명확히 분리해” |
| 승인 범위 해석 | 시뮬 전용 설정 이동, 필요한 기존 경로 참조 갱신. 공통 업무 로직 변경 승인으로 확대하지 않음 |
| 설정 이동 | `robot/config/vision/scout.json` → `sim/ros_ws/src/farm_sim_config/config/scout_vision.json`. 이전 경로의 설정 파일·링크는 제거 |
| 환경 선택 | `scout_survey.json`이 새 영상 설정을 참조. `scout_runtime.yaml`에 시뮬 `rviz_config` 추가 |
| RViz 분리 | `sim/.../farm_sim_config/config/scout.rviz` 추가. `sim/.../farm_sim_runtime/launch/scout.launch.py`에서 공통 bringup과 별도로 선택하여 한 번 실행 |
| 비전 진입점 | `sim/tools/run_scout_vision.py`에서 기본 설정 선택. 기존 루트 스크립트는 인자를 그대로 전달하는 호환 진입점으로 변경 |
| 외부 참조 갱신 | `scripts/run_scout_vision.py`, `tests/test_scout_survey.py`만 시뮬 외부 실행/시험 파일로 변경. 기존 시험은 survey의 `vision_config`를 읽도록 수정 |
| 출력 분리 | 예찰·단독 비전·합성 데이터 기본 출력을 각각 `sim/runs/scout_survey`, `sim/runs/scout_vision`, `sim/runs/scout_dataset`으로 변경 |
| 평가 도구 | `--survey latest`는 시뮬 결과 폴더만 검색. 기존 결과는 명시 경로로 읽을 수 있음 |
| 패키징 | 새 설정·launch는 기존 glob으로 설치. 시뮬 runtime의 실행 의존성만 추가 |
| 실물 영향 | `robot/ros_ws/src/`, 실물 설정·모델·센서 값·메시지·공통 알고리즘은 유지. 기존 실물 launch와 기존 결과 데이터도 유지 |
| 검증 | 기존 오프라인 44개 통과. sim/real 환경 로드 성공. 수치·ID·모델 선택·그래프 참조 보존. 공통 ROS/실물 설정/모델 124개 파일 원본 동일. 실행 객체를 대체한 launch 구성 4조건·외부 설정 거절 4조건, 비전 함수만 대체한 신·구 CLI 인자 전달 6조건 통과. 변경 Python 문법 및 패키지 XML 확인 |
| 미실행 | ROS 2 빌드 및 실제 launch, Isaac·YOLO·실물 실행 |
| 복원 | 적용 전 설정·진입점·시험·sim 패키지 파일로 되돌리고 이번 추가 파일만 제거. 기존 비전 설정은 `sim/runs/config_backups/`에서 복원 가능. 새 결과 폴더는 삭제하지 않음 |

추가/수정 파일의 상세 위치와 실행 명령은 `sim/README.md`를 참고한다. 기존 `INTEGRATION_REVIEW_20261002.md`는 변경 전 인수 검토 기록이며 현재 설정 위치는 이 변경 항목이 우선한다.

## 다음 변경 기록 양식

```text
변경 ID / 일자:
구분: 시뮬 전용 / 공통 / 실물 / 문서
상태: 제안 / 승인 대기 / 승인 완료 / 적용 완료 / 검증 완료
기준 버전: Git commit 또는 전달 파일 식별값
대상 파일:
변경 이유와 재현 조건:
구체적인 변경안 / 변경 전후 동작:
실물 영향:
시뮬 영향:
사용자 승인 일자·요청 내용·승인 범위:
적용 결과:
검증 명령·결과·미실행 범위:
시험 로그 / 보고서 경로:
되돌리는 방법:
```


## SIM-DATA-20261002-003 — 연결 경로·로봇 station 복원

- 승인 근거: 사용자 요청 “어제 업데이트한 경로 데이터 yaml … 경로끼리 연결, 각 로봇 station … sim 파트 데이터 다시”.
- 이유: 인수본에는 과거의 분리 그래프와 FOV 자동 관측 설정이 남아 있어 이후 업데이트한 연결·station·고정 촬영점 데이터가 누락돼 있었다.
- 대상: sim의 task.yaml, 연결 원본/역할별 GeoJSON, 원본 점유 지도, scout_survey/scout_patrol/scout_runtime/scout.json, 재생성·검증 도구, 문서와 작업 규칙. 상세 목록은 패치 ZIP에 포함된 파일 목록 기준.
- 출처: farm_scout_harvest_count_v0.8.5.zip의 최신 연결 데이터. 운송/선별장 용도는 기존 sim_route_design_v1 설계. 보관본 자체와 실제 git 커밋 비교는 구분한다.
- 변경 전후: 16개 분리 성분 → 연결 원본 227노드/516방향 엣지. BED_01~16/FOV 자동 관측 → SEC01~16/고정 관측점 80개. 예찰·수확 station 좌표·방향 복원, 운송/선별장 설계 좌표 복원(방향 미정).
- 호환: 공통 로더가 role 메타데이터를 읽지 않아 역할별 파생 그래프를 생성. 원본 베드 경계는 scout 파생 그래프의 기존 엣지를 분할해 보존. 공통 코드 복제나 변경 없음.
- 실물 영향: 이번 변경은 전부 sim/ 내부. 공통 코드·실물 설정·모델·USD 자산 변경 없음.
- 검증: 현재 공통 로더와 기하 계산/순찰 로더에서 16구역·80관측점 유효, 371개 역할별 경로 계산 통과. 원본 그래프/지도 동일, 원본 구역·베드·예찰/수확 station 동일, 227개 원본 노드의 지도 free 픽셀 확인.
- 미실행/유지: ROS/Isaac/colcon 미실행. station 자동 배치, AMCL station 초기화, FollowPath 전환, 수확/운송 실행부 연결은 미적용. 기존 navigate_to_pose 유지. 자동 station 복귀 없음.
- 복원: 패치 적용 전 백업 사용. 이번에 추가된 파일은 제거하고 기존 파일만 백업본으로 돌린다. sim/runs 결과는 보존한다.
- 보고: sim/docs/ROUTE_RESTORE_20261002.md 및 ROUTE_RESTORE_VALIDATION_20261002.json.


## SIM-RUNTIME-20261002-004 — Isaac 실행 대상 station 자동 배치

- 승인 근거: 사용자 “robot의 station 자동 배치는 isaacsim 실행용 코드에 포함”. FollowPath 설명 요청은 모드 전환 지시로 해석하지 않았다.
- 대상: sim runtime의 station_spawn.py/run_sim.py/scout.launch.py, scout.json, task.yaml, station_spawn.json, nav2_scout.yaml, 재생성·검증 도구, sim/tests/test_station_spawn.py 및 sim 문서.
- 변경 전후: USD 저장 위치에서 시작 → task 기반 station JSON의 예찰 station XY/yaw로 물리 시작 전 배치. 기존 body 높이·센서 상대 위치 유지. USD session layer만 사용하며 원본 저장 없음.
- 위치추정: AMCL 초기 pose를 같은 station 원본에서 생성. launch에서 서로 다르면 오류. 물리 reset 후 배치 검증. 주행 중 정답 pose 주입 없음.
- 범위: 현재 단일 예찰 런타임에 적용. 수확/운송 실행부 생성·구동 및 FollowPath 전환은 미적용. 공통 코드·실물 설정·USD 자산 변경 없음.
- 검증: 좌표/설정 시험 6개, launch 구성 4개 및 AMCL 불일치 거절 검사 통과. 경로 371개 검사 통과. nav2는 초기 pose 외 설정 값 유지.
- 한계: ROS/Isaac/USD API 실실행, 물리 구동, colcon 빌드 미검증.
- 복원: 이전 sim 파일 백업을 복원하고 새 station_spawn.py/json 및 시험 파일을 제거한다. sim/runs 결과는 보존. 배치만 끄려면 station_spawn.enabled=false와 실제 시작 위치의 AMCL 초기 pose를 함께 맞춘다.
- 상세: sim/docs/STATION_SPAWN_20261002.md.


## SIM-NAV-20261002-005 — 실물과 동일한 FollowPath/RPP 설정

- 승인 근거: 사용자 “시뮬설정도 실제랑 동일하게 세팅해”.
- 대상: sim의 scout_runtime.yaml, nav2_scout.yaml, task.yaml, 재생성된 scout_survey.json, 문서·작업 규칙. 공통 코드/실물 파일 변경 없음.
- 전후: navigate_to_pose → follow_path, controller_id FollowPath → RPP, goal checker general_goal_checker → goal_checker. 실물과 navigation 파라미터 동일(base_frame 제외).
- 제어 설정: 인수본 실물의 controller_server·velocity_smoother 값을 적용(use_sim_time/odom_topic 제외). controller 10Hz, RPP 0.15m/s·lookahead 0.15m, goal 0.03m/0.05236rad, progress 0.1m/10s. local/global inflation도 RPP 비용 모델에 맞게 실물과 동일하게 설정.
- 유지: 시뮬 지도·graph·관측점·station, TF·센서·장치·시간, AMCL station 초기 pose, 로봇 반경/센서 costmap 레이어. 모든 Nav2 값을 무조건 복사한 것은 아님.
- 실행 동작: 공통 RouteGraph가 연결 그래프 경로를 계산하고 Nav2 FollowPath 액션에 controller_id=RPP로 전달한다. 교통 제어·자동 복귀·도킹 추가 없음.
- 검증: 양 환경 설정 로드, 주행값/선택 controller/goal/progress ID 일치, 공통 goal checker 검사 통과. 371개 경로 계산 및 station 시험 6개 통과. 이번 수정이 sim 내부로 한정됨을 파일 해시로 확인.
- 한계: ROS/Isaac 실주행·colcon 빌드 미실행. 인수본 설정과 동일하다는 의미이며 담당자의 현장 실행값은 별도 확인 대상.
- 원복: 적용 전 시뮬 설정 백업 복원. 주행 모드 한 줄만 바꾸면 제어 튜닝까지 원복되지는 않는다.
- 상세: FOLLOWPATH_ALIGNMENT_20261002.md, FOLLOWPATH_VALIDATION_20261002.json.


## LAUNCH-SPLIT-20261002-006 — 로봇/Isaac/RViz 독립 실행 및 시뮬 전체 실행

- 승인: 사용자 “그럼 그렇게 수정해 … 시뮬레이션용 전체실행 런치 … 만들어줘 … 실행 절차 … 작성”. 공통 launch 변경을 포함한 실행 구조 분리 승인으로 적용.
- 공통 대상: farm_bringup의 scout.launch.py, scout_navigation.launch.py, 새 rviz.launch.py, tests/test_launch_composition.py, 공통 실행 안내/루트 README/AGENTS.
- 시뮬 대상: sim 런타임의 scout/scout_devices launch, 새 isaac/all launch, setup.py의 launch 파일 설치 패턴, 안내 문서.
- 변경 전후: 로봇 launch에서 Isaac/RViz를 함께 시작 → 로봇 단독 기본은 장치+Nav2+예찰 서버, Isaac과 RViz는 독립 실행. 시뮬 all은 독립 launch 세 개를 조합.
- 실물 영향: 기존 survey=true 실행은 장치·Nav2·서버 구성 유지. RViz는 별도 실행. survey/navigation 기본값이 true로 변경됨. start_isaac/rviz=true는 명시적으로 이관 안내 오류. navigation 전용 sim 실행도 환경 프로파일을 선택하도록 보완.
- 유지: 실물 설정·공통 미션/FSM/주행 계산/메시지·USD 및 station 배치 구현 변경 없음. 수확/운송/관제 구현을 임의 추가하지 않음.
- 검증: launch 기록 객체 기반 9개 시험 통과. 시뮬 전체의 Isaac/어댑터/예찰서버/RViz 각 1개, 독립 실행 경계, 실물 장치 포함 및 Nav2/서버, 모드별 RViz 시간/TF, 옵션 및 잘못된 구형 옵션 거절 확인. 직접 ROS/Isaac 구동·실물·colcon 빌드는 미실행.
- 실행 안내: docs/RUN_GUIDE_20261002.md. 실물 담당자 변경표, 각 장비 실행, 시뮬 전체/세 터미널 실행, 시험 관제, 종료·재시작 범위, 다중 로봇 미구현 항목을 명시.
- 복원: 적용 전 공통/시뮬 launch와 setup.py 백업 복원. 새 launch·구성 시험·안내 파일 제거. 실행 결과는 삭제하지 않음.


## SIM-LAUNCH-20261002-007 — 활성 robot_venv의 비전 Python 자동 선택

- 사용자 확인: 비전 의존성이 robot_venv에 설치되어 있어 별도 vision_python 인자가 불필요해야 함.
- 대상: sim 런타임의 launch_environment.py, all/scout launch. 공통/실물 코드 변경 없음.
- 전후: 인자/환경변수 미지정 시 빈 경로 → FARM_VISION_PYTHON 우선, 없으면 VIRTUAL_ENV/bin/python, 활성 venv도 없으면 launch Python 사용. 명시적인 vision_python 인자는 계속 우선함.
- venv 심볼릭 링크는 resolve하지 않아 가상환경을 유지. 잘못된 활성 venv 경로는 명시적 오류.
- 검증: 우선순위 및 경로 선택 검사, 기존 launch 구성 시험 9개 통과. 실제 ROS/Isaac/추론 실행은 미검증.
- 원복: 이전 all/scout launch 복원 후 새 launch_environment.py 제거.

## HARVEST-SIM-20261002-008 — 수확 이동 Action 및 시뮬 bringup

- 상태: 사용자 승인 후 적용, 오프라인 검증 완료. ROS/Isaac 실실행 미검증.
- 승인 근거: 수확 코드/bringup·sim/real 구분·sim 내부 작성 요청과 후속 “action 추가해. 진행해도 돼”, “그렇게 result 보내면 됨”. 사전 제안한 공통 인터페이스 추가와 이동 완료/수확량 0 계약을 적용했다.
- 공통 대상: farm_interfaces/action/HarvestTask.action 신규, CMakeLists.txt 등록만. 기존 HarvestTask.msg 및 주행/예찰/실물 설정 유지.
- 시뮬 대상: farm_sim_harvest 신규 서버/미션/통신/상태/평가; runtime harvest launch/fleet 실행/all 조합/clock relay; harvest 자산/설정/지도 선택/RViz; 데이터 생성·검증·시험·안내.
- 전후: 수확 실행부 없음 → 같은 공통 Navigator와 harvest 역할 graph로 window XY/yaw 도착 후 SUCCESS/harvested_count=0. 팔 작업 없음. expected와 실제 USD pose의 과실 박스 판정은 별도 로그. real 장치 연결은 미구현 오류, 실물 가상 구동 대체 없음.
- 출처: 제공된 v0.8.5 수확 물리 자산/주행좌표 변환/시뮬 센서 및 GT 수집 부분만 이식. 예전 서버·관제·공통 로직은 복원하지 않음. 실제 팔 도달성 대신 기존 임시 박스이며 인수 후 보정 필요.
- 실행 영향: harvest=true일 때 두 로봇 포트·TF 분리 및 독립 clock 하나. scout 단독 기본 동작 유지. fleet scout profile이 중복 clock을 막음. 새 Action 사용자는 robot workspace 재빌드 필요.
- 검증: sim 단위/구성 20개, 기존 launch 9개, 기존 경로 371개, 수확 엣지 내부 목표 경로 48개 통과. 공통 변경 2개 외 모든 변경 sim 내부 확인. ROS/colcon/Isaac/실물 미실행.
- 수정 안내·실물 인수 경계·로그·원복: HARVEST_RUN_GUIDE_20261002.md. 적용 전 파일 백업 복원 및 신규 파일 제거 후 재빌드, sim/runs 결과 보존.

## HARVEST-COMMON-20261002-009 — 수확 서버의 공통 위치 정정

- 승인: 수확 서버와 bringup을 공통 위치로 옮기고 평가만 sim에 남기자는 구체적 제안에 대한 사용자 “그래임마 정신차려”.
- 이유: 008에서 수확 서버 전체를 sim 전용 패키지에 배치한 것은 동일 서버를 sim/real에서 공유하는 기존 합의에 맞지 않았다. 008의 서버 위치 설명은 이 항목으로 대체한다.
- 공통 변경: robot/ros_ws/src/harvest_robot 신규(Node/Communication/Mission/StateController/계약), farm_bringup/launch/harvest.launch.py 실제 조합 및 package.xml 의존성. 기존 farm_navigation과 HarvestTask 계약 유지.
- sim 변경: farm_sim_harvest는 audit_node/evaluation만 유지. 작업 설정과 평가 설정 분리, fleet 평가 경로 갱신, sim harvest launch가 공통 launch+평가를 조합. 이전 sim 서버 소스 5개 제거용 백업 이관 도구 추가.
- 전후: sim 서버가 평가 함수를 호출 → 공통 서버는 Action/주행 처리와 환경 독립 task_events 진단 발행만 담당, sim 평가 노드는 비동기 구독하여 비교 로그 생성. 서버에서 sim import/Isaac snapshot 접근/평가 대기 제거.
- 실물 영향: real 설정과 외부 드라이버가 있으면 devices=false로 같은 서버 실행 가능. 미구현 실물 장치 기본 분기는 오류. 실물 맵/드라이버/팔 작업을 가짜 구현하지 않음. 공통 workspace 재빌드 필요.
- 검증: 오프라인 31개, 기존 경로 371개, 수확 내부 좌표 경로 48개 통과. sim/real 동일 서버, 시간 선택, 평가 분리, 중복 launch 없음 확인. 실제 ROS/Isaac/colcon/실물 미실행.
- 전달/원복: HARVEST_COMMON_MIGRATION_20261002.md. 이전 수확 패치를 대체하는 합본 패치, 이관 도구로 옛 서버만 백업 후 제거. 결과 로그는 보존.

## SIM-FLEET-20261002-010 — Isaac fleet 진입점 누락 수정

- 증상: 17:09 실행 로그에서 Isaac Python이 시작 직후 exit 0으로 종료, OnProcessExit에 의해 모든 ROS 노드가 SIGINT로 종료됨.
- 원인: run_fleet.py에 main 함수는 있으나 직접 실행 시 호출하는 __main__ 진입점 누락. 기존 문법/launch 구성 검사는 함수 호출 여부를 검증하지 못했음.
- 대상: sim runtime/run_fleet.py, sim/tests/test_fleet_entrypoint.py, 이 변경 기록. 공통/실물 파일 변경 없음.
- 변경: 직접 실행 시 main() 호출 추가. 종료 연동은 그대로 유지.
- 검증: 수정 전 --help가 출력 없이 exit 0인 현상 재현. 수정 후 실제 subprocess --help에서 옵션 출력, 필수 인자 누락 시 exit 2 확인(2개 통과). Isaac 물리 구동은 해당 환경이 없어 미검증.
- 적용: 패치 압축 해제 후 sim workspace의 farm_sim_runtime 재빌드, 환경 다시 로드 후 기존 전체 실행 명령 사용.
- 원복: run_fleet.py 마지막 __main__ 블록과 새 시험 파일을 되돌림. 결과 데이터는 변경하지 않음.

## SIM-TF-20261002-011 — 카메라 없는 수확 로봇 상태 패킷 수락

- 증상: HarvestTask는 수락됐으나 harvest_01/base_footprint TF가 없어 NAVIGATION_FAILED.
- 원인: ros_adapter.valid가 고정 TF 3개를 강제. fleet 런타임은 카메라 없는 harvest에 base/link·lidar TF 2개를 전송하여 모든 패킷이 거절됐음. odom·scan·TF 발행에 도달하지 못함.
- 변경: camera.enabled에 따라 2/3개를 선택하고 설정의 부모/자식 프레임 쌍과 일치하는지 검사. 공통 서버·실물·Nav2 변경 없음.
- 검증: 실제 valid 메서드를 ROS 없이 실행, harvest 2개/scout 3개 수락 및 누락/다른 로봇 프레임 거절 4개 통과. ROS/Isaac 직접 실행 미검증.
- 적용: farm_sim_devices 재빌드 및 전체 launch 재시작. 확인: harvest_01/odom → harvest_01/base_footprint TF 출력.
- 복원: 이전 ros_adapter.py 복원 후 시뮬 패키지 재빌드. 시험 로그 데이터 유지.

## DRIVE-DIAG-20261006-012 — 수확 무응답 구동 진단

- 근거: cmd_vel 0.12m/s, wheel odom 약 0, 로봇 정지 및 Failed to make progress. 전달 경로/물리 구동 중 원인 미확정.
- 범위: sim runtime/run_fleet.py와 신규 drive_diagnostics.py. 공통/실물/게인/구동 제한 변경 없음. 앞선 main 호출 수정 포함.
- 변경: ROS→Isaac 수신 패킷과 gate 수락/거절 누적, 실제 적용 cmd, 공통 kinematics로 계산한 관절 목표, 관절 실측 속도/인덱스, 실제 pose를 1Hz로 기록. 적용된 USD 바퀴 drive 설정 기록.
- 산출: sim/runs/drive_diagnostics/<세션>/<robot_id>.jsonl 및 <robot_id>_setup.json. 목표 속도는 apply_action에 전달한 입력으로 계산한 값이며 PhysX 내부 target readback은 아님.
- 정적 검사: 제공 자산의 바퀴 stiffness=0, damping=625. 별도 자산의 검사이며 사용자 실행 중인 scene 적용 상태의 증명은 아님.
- 검증: 실제 common wheel_targets를 사용한 목표 rad/s, 수락/거절 카운터, JSON 출력/1Hz 제한, USD 관절 추출 검사 통과. Isaac 물리 실행 미검증. 근본 원인 수정 완료가 아닌 진단 계측 패치.
- 원복: 적용 전 run_fleet.py 복원, drive_diagnostics.py 제거 후 runtime 재빌드. 기록은 보존.



## DOC-HANDOFF-20261006-015 — Codex·ChatGPT 최신 인수인계 문서 패키지

- 일자: 2026-10-06 (Asia/Seoul).
- 구분: 문서·작업 지침. 실행 코드·환경 설정·ROS 정의·USD·모델 변경 없음.
- 승인 근거: 사용자 요청 “필요한 인수인계용 파일 최신버전으로 작성해서 전달해줘”. 문서 작성·전달 범위이며 공통 실행 코드 변경 승인으로 확대하지 않음.
- 기준 코드: `068b42eb0ebe54b3b57cffe254a20b2f9e3b202e`, Robot3FinalProject/main의 main 브랜치.
- 상태: 다운로드 적용용 문서 패키지 작성. 사용자 PC 적용·GitHub 반영은 별도 확인 필요.
- 대상: `AGENTS.md`, `README.md`, `docs/CODEX_HANDOFF.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, `docs/HANDOFF_SOURCES_20261006.json`, `sim/docs/RUN_GUIDE_20261006.md`, 이 변경 이력.
- 변경 이유: 초기 토마토 기획과 10/2 예찰 인수 기록만으로는 10/6 수확·통신·다중 로봇 실행 상태를 전달하기 어려움. 코드·문서·사용자 확인의 시점을 구분하기 위함.
- 변경 내용: 최신 구조·메시지·로그·실행 인자·미구현 영역 정리. 루트 AGENTS의 복원 전 그래프 설명과 README의 수확 미구현 포괄 설명을 정정. 인수인계 읽기·갱신 규칙과 ChatGPT 프로젝트에 추가할 지침을 문서화.
- 현재 규칙 유지: 시뮬 전용 작업은 sim 내부, 공통 코드 변경 승인, sim 정답 평가와 실제 제어 분리, 코드 및 사용자 미커밋 변경 보존.
- 직접 검증: 기준 커밋의 관련 소스·설정 정적 대조; 8베드/16Section/80관측점, 원본/예찰/수확 그래프의 노드·엣지·약연결성 계산; 최종 패키지의 링크·경로·필드·Bash 구문·ZIP 내용 검사. 상세 결과는 전달 시 검증 기록 기준.
- 미실행: 사용자 PC의 git 상태, colcon 빌드, ROS 네트워크·관제 연동, Isaac 물리 실행, 실물 실행. 과거 시험 횟수를 이번 재실행 결과로 쓰지 않음.
- 실물 영향: 실행 동작 변경 없음. 새 세션에서 갱신된 문서 확인 절차가 적용됨.
- 되돌리기: 적용 전 문서 백업과 비교하여 이번 문서 변경만 복원. 이번에 새로 추가된 문서의 제거 여부는 이후 편집 유무를 확인한 뒤 결정. 실행 코드·데이터를 되돌릴 이유는 없음.
- 관련 과거 기록: 캐스터 보정은 `sim/docs/changes/CASTER-FIX-20261006-013.md`, 통신규약은 `docs/changes/PROTOCOL-20261006-014.md`에 별도로 존재한다. 여기에서 해당 변경을 새로 적용한 것으로 기록하지 않는다.


## DOC-STATE-20261006-016 — 로컬 코드·문서·기존 로그 대조

- 일자/구분: 2026-10-06 KST / 문서. 적용 완료, 정적 검토 완료.
- 승인 근거: 사용자 요청 “인수인계서, 변경 이력, docs/changes와 현재 코드를 대조해서 docs/PROJECT_STATE.md를 작성해 … 이번에는 문서만 작업해”.
- 기준: main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e 및 시작 시 미커밋 인계 문서. fetch 후 origin/main과 0/0. 기존 AGENTS/README/이력 수정, 미추적 인계 파일과 백업 보존.
- 대상: docs/PROJECT_STATE.md, 이 변경 이력. 코드·설정·시험·모델·USD 변경 없음.
- 전후: 인계 패키지의 원격 기준 요약 → 실제 로컬 Git 상태, 실행 요약, 구형 설명과 코드의 차이, 저장된 수확 성공 2건/실패 6건의 증거·한계 보강. 로컬 장면 USD는 포인터가 아닌 바이너리 객체임을 정정.
- 실물/시뮬 영향: 실행 동작 변경 없음. 최신 프로토콜 E2E 검증 완료로 확대하지 않음.
- 직접 검증: Git fetch·차이 조회, 관련 문서/launch/메시지/미션 정적 대조, GeoJSON 규모·약연결성 및 16Section/80관측점/8베드 계산, 기존 survey/audit JSON 열람, USD 헤더·크기·캐스터 패치 체크섬 비교, 문서 링크·기존 파일 보존 검사.
- 미실행: 기존 단위/경로 검사의 재실행, colcon/ROS/CDR/Isaac/실물/최신 프로토콜 E2E.
- 로그: 새 런타임 로그 없음. 기존 증거 위치와 다음 통합 시험 조건은 PROJECT_STATE §11·§13.
- 복원: 문서의 이번 보강과 이 항목만 이전 내용과 비교해 복원. 시작 시 미커밋 변경은 유지. commit/push 미실행, 원격 미반영.

## ROBOTARM-REVIEW-20261006-017 — 로봇팔 인수 자료 검토 및 반영 승인 대기

- 일자/구분: 2026-10-06 KST / 문서 검토. 실행 코드·설정·USD 반영은 승인 대기.
- 승인 근거: 사용자 “main에 robotarm 폴더에 … 확인해보고 sim에 반영할 내용 정리해서 나한테 확인받고 적용해”. 이번에는 검토서 작성만 수행하고 적용 전 확인 절차를 따른다.
- 기준: main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e. 이번 fetch 후 origin/main과 0/0. 기존 미커밋 문서·백업 및 robotarm 원본 4개 보존.
- 대상: 신규 `sim/docs/ROBOTARM_INTEGRATION_REVIEW_20261006.md`, 이 변경 이력. 실행 파일·공통/실물 코드·기존 설정·자산 변경 없음.
- 전후: 인수 명세 4개만 존재 → 현재 sim과의 차이, 필수 추가 인수, 단계별 대상 파일·영향·검증·승인 경계를 문서화.
- 주요 발견: 정책 4개/run.json/profile/runtime/RL 소스/전용 자산/검증 원본 미수신. 오른팔 Teacher와 기존 왼팔 Window/audit 불일치. 현재 60Hz와 Teacher 실효 480Hz/정책20Hz 차이. 활성 농장 과실 288개 하위에 rigid body/mass/collision API 없음. 현재 과실 크기와 root 의미 대조 및 박스 바닥 물리 준비 필요.
- 직접 검증: 문서/JSON/현행 코드 정적 대조, 후보18개 범위·HOME 거리·18cm 간격 조합 계산(최대3개), 파일 목록/SHA256, Git 상태·fetch·커밋 차이, 설치 pxr를 사용한 USD 정적 TF/기하/물리 API 검사.
- 미실행: 정책 추론, Isaac SimulationApp/PhysX, ROS/colcon, 실제 수확 및 실물 시험. 문서의 적재3/6은 담당자 과거 기록이며 이번 검증 결과가 아님.
- 제안: A sim 인수 설정·검사 도구 → 원본 수령 후 B 독립9g 평가 → C 농장/오른팔 기하 정합 → 별도 공통 승인 후 D 실제 팔 작업 연결. 이번 승인 요청은 A이며 B~D 동작을 자동 승인받은 것으로 취급하지 않음.
- 실물/시뮬 영향: 문서만 추가되어 실행 영향 없음. Teacher 내부 상태 입력은 독립 평가 범위로 한정하며 기존 공통 제어 정답 주입 금지를 유지.
- 결과/다음 작업: 상세 검토서의 A 범위를 사용자에게 제시. 승인 후 설정·검사 도구를 구현하고 누락 원본 확보 후 물리 재현 진행. 새 런타임 로그 없음. commit/push 미실행.
- 복원: 이번 검토서와 이 항목만 되돌린다. 기존 이력과 시작 시 미커밋 변경을 보존한다.

## ROBOTARM-RECEIPT-20261006-018 — 전체 전달 묶음 수령 및 이식 문제 검토

- 일자/구분: 2026-10-06 KST / 수령 검사·문서. 사용자 요청 “파일 받아서 robotarm 폴더안에 넣어놨어 파악해봐”. 앞선 전체 자료 수신 후 일괄 작업 요청에 따라 017의 A 단독 반영은 보류.
- 기준: 농장 main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e, 이번 fetch 후 origin/main과0/0. 전달 소스 base abe9e13357e1be549500712b62c5582649d444ab + 현재 수정본.
- 대상: 신규 `sim/docs/ROBOTARM_BUNDLE_RECEIPT_20261006.md`, 기존 검토서의 최신 문서 연결, `docs/PROJECT_STATE.md` §14, 이 이력. `sim/runs/robotarm/received_20261006_143434/`에 검토용 원본 추출 및 검사 JSON2개. 실행 소스·정책·기존 자산·프로파일은 수정하지 않음.
- 전후: 문서4개만 수령 → 소스·정책·자산·환경·YOLO·평가 원본 확보 및 무결성 확인. 새 평가/농장 통합 완료는 아님.
- 직접 검증: archive SHA256, 안전한 상대경로/일반파일 검사, manifest2148 및 정책4/run.json 해시 일치, 기존4개 파일 동일, 미수신LFS 포인터0. USD/URDF 참조·박스 바닥·팔/차체/캐스터 정적 대조, 환경metadata 비교, 과거episode JSON 집계, 동작코드 분석.
- 발견: prepare 경로 치환 뒤 converter asset hash가 달라져 USD 재생성 경로 발생. 복귀는12×1/480s이나 제어·dwell은50ms 사용. 전달 current USD는 고정차체 평가용, 농장 주행 USD 통째 교체 불가. 비전 환경 일부 버전 차이. 상세는 수령 검토서.
- 미실행: prepare/캐시변환/설치/정책로딩/Isaac·ROS·실물·학습. 원본3/6 성공은 과거 기록이며 수신PC 결과가 아님.
- 실물/시뮬 영향: 문서·검토용 추출만 수행, 현재 운영 동작 영향 없음. source 원본/기존 미커밋 문서·백업 보존. commit/push 없음.
- 후속: 이식·비전환경·복귀시간 보완을 포함해 독립9g 재현 및 농장 통합 범위를 확정. 공통 업무 변경은 기존 구체안 승인 절차 유지.
- 복원: 이번 문서 항목만 비교 복원. 원본 archive/기존 자료를 삭제하지 않으며 검토용 추출본은 운영에서 참조하지 않음.

## ROBOTARM-PHYSICS-20261006-019 — 농장 과실·오른팔 물리 및 수확 목표 좌표 적용

- 일자/구분: 2026-10-06 KST / sim 코드·설정·독립 자산·시험·문서. 구현 및 GPU 기초 물리/진입점 시험 완료, 정책 파지·적재와 실제 Nav2 주행은 미실행.
- 승인 근거: 사용자 “전달받은 파일들 기반으로 아이작심에 적용 … 농장 맵 … 물성치 … 오른쪽 팔 … 예찰로봇 좌표 … 오른쪽 암 기준 … 그것부터 작업”. 추가 선택 “Teacher 규격으로 통일”. 017/018의 검토 대기는 이 sim 1단계에 한해 구현 요청으로 대체했다.
- 기준: main/068b42eb0ebe54b3b57cffe254a20b2f9e3b202e와 기존 미커밋 변경. fetch 후 origin/main과 동일. 받은 전체 묶음 및 공통/실물 실행 파일은 보존했다.
- 과실: `sim/assets/fruit/teacher_9g/`, `fruit_asset_setup.py`, `fruit_attachment.py`, `stem_physics.py`, 생성 도구. 농장288개를70mm폭/75mm높이·9g로 통일하고 마찰/감쇠/접촉·줄기 response5·40ms 지속 분리를 적용했다. 기존 ID·색·위치·회전 보존. 선속도3m/s·각속도20deg/s를 source runtime까지 대조해 적용. 받은 runs 폴더에 대한 운영 의존 없음.
- 오른팔: `robotarm_asset_setup.py`, `sim/assets/robots/harvest_physics/`.6축 힘 drive·그리퍼 접촉·HOME·박스 바닥4타일. 주행용 USD를 교체하지 않고 기존 바퀴/캐스터/왼팔/rigidbody/전체 articulation 물성은 보존했다. 고정차체 Teacher와 전체 solver/self-collision이 같은 환경이라고 주장하지 않는다.
- 좌표: `task.yaml`, 생성 `scout_survey.json`/`harvest_audit.json`, `rebuild_route_data.py`, `scout_vision.json`.16구역 오른팔 mount `[.19,.185,.713]`, 작업중심 `[.19,.5,.838]` 및 크롭 높이를 동기화. `harvest_runtime.yaml` 연결한계.09m/도착.02m·.05rad, `nav2_harvest.yaml` 내부허용.015m·.04rad. 원본 graph·베드 좌표 변경 없음.
- 실행: `robotarm_physics.json`, scout/scout_fleet/harvest.json, `harvest_physics.py`, run_sim/run_fleet, isaac.launch.480Hz 물리 한 tick마다 외력을 갱신하며60Hz 렌더를 별도 호출. 원본 USD 저장 없이 session layer에서 적용. 단독 runner도 실제 project_root를 받는다. 실행별 setup/물리 분리 로그를 저장하고 정책·수확 성공으로 사용하지 않는다.
- 직접 검증: 관련 단위54개+USD 정적7개=61개 통과(skip0), 원본 줄기 Torch와256개 상태 수치 대조,371개 경로,48개 오른팔 Goal과 정적 map 연결선, sim3패키지 colcon 빌드. GPU RTX4070SUPER/Isaac5.1에서288과실2초 자연이탈0, 선택 과실3N 외력으로40ms 이상 지속 후 분리·0.6초 낙하를 확인. 실제 fleet 진입점2초에서288결합 유지, RGB-D29프레임, 로봇별 상태60개. 상세값과 명령은 `ROBOTARM_PHYSICS_20261006.md`.
- 중간 문제: sandbox CUDA 접근 실패는 GPU 권한 환경에서 재시험. fast_shutdown 기본값이 결과 기록 전 프로세스를 끝내는 문제는 정상 종료/종료 전 보고서 기록으로 수정. 최초 낙하0.2초 검사는 분리 직후 상승속도 때문에 실패하여 초기속도/궤적을 기록하고0.6초 관측으로 보완했다. 최종시험은 누락된 과실 속도 제한까지 적용한 후 다시 통과. 중간 JSON 보존.
- 남은 차이/미실행: 실제 Nav2 정밀 정지·동적 장애물/footprint 검사, 전체 예찰→수확 E2E, 정책4개 독립 재현/20Hz 추론·파지·박스 적재, 실물 시험. 원본 농장 빈 visual 참조와 종료 UI extension 경고는 보고서에 구분했다. 공통 수확 Action은 현재 이동+수확0 계약 유지.
- 문서: 신규 `sim/docs/ROBOTARM_PHYSICS_20261006.md`, RUN_GUIDE 최신 절, PROJECT_STATE §15, DECISIONS D-013/D-014 및 이력 갱신. 실물 소스·설정·모델·공통 업무/메시지 변경 없음.
- 로그: `sim/runs/robotarm/physics_smoke_gpu_20261006/result.json`, 같은 이름 `.log`, `fleet_physics_smoke_20261006.log`, `asset_setup_static_final_20261006.log`, `physics/98d899878bda4638a1aa82bbaa51f46b/`.
- 종료 보완: 정상 app.close 후에도 Kit 스레드가 남는 현상을 확인해 CLI에서 파일·앱 정리와 출력 flush 후 검사 결과의 종료코드로 종료한다. 이전 시험 중 결과 기록을 마치고 남은 프로세스4개만 종료했다. 보완 후 물리 검사와 fleet 진입점을 재실행해 각각 종료코드0을 확인했다. 물리/장치 검증 성공과 종료 문제가 있었던 중간 실행을 구분한다.
- 복원: 신규 물리 프로파일 enabled=false로 물리 override를 임시 비활성화할 수 있다(480Hz와 좌표 변경은 별도). 전체 복원은 이번 sim 실행/설정 변경만 비교해 되돌리고 task 원본 기준으로 생성 설정을 함께 재생성한다. 기존 캐스터 패치·인계 문서·사용자 변경을 전체 reset하지 않는다. 소스 농장 USD는 변경하지 않았으므로 복구 저장이 필요 없다. commit/push 미실행, 원격 미반영.

## ROBOTARM-VERIFY-20261006-020 — 인장력 비교 검사 및 커밋·푸시 요청

- 승인: 사용자 “테스트하고 커밋푸쉬 … 정상적용 확인 … 어느정도 인장력 … 강화학습 환경을 적용한거야?”.019 구현과 관련 문서를 테스트 후 게시한다. 별도 AGENTS/README 등 기존 수정, 수신 archive·백업은 작업 트리에 보존한다.
- 대상: `check_harvest_physics.py`에0.1N 유지1초/무외력 회복0.5초 비교·GUI 카메라·실제COM/관성 및 초기tick 기록 추가. `stem_physics.py`/`fruit_attachment.py`에 힘 clamp 전후 및 분리 조건 진단 추가, 줄기 회귀1개 추가. 물리 수식·계수·판정·공통 코드는 변경하지 않는다.
- 검증:62개 테스트(skip0),371개 경로,sim3패키지 빌드 통과. GPU15항목/종료코드0,288과실 유지→0.1N 유지→3N 실제 분리·0.6초간0.90448m 하강 확인. 원본 USD와 주행 구성 보존.
- 중요한 중간 관측:0.5N·1초 유지 예상은 실패했다.116.7ms 뒤 인장축32.32mm, 원시0.51955N, 후크조건41.667ms로 분리됐다. 전달 수식의 거리 분리 조건이며 단순 힘 임계값 실패가 아니다. 별도1kg 무중력 GPU 시험에서 두 외력 호출은 합산됨을 확인했다. 실패 JSON을 보존하고, 물성을 바꾸지 않고 유지 확인 하중을0.1N으로 명시했다.
- 문서/증거: `ROBOTARM_PHYSICS_20261006.md` §10, PROJECT_STATE §16, `sim/docs/changes/ROBOTARM_PHYSICS_VALIDATION_20261006.json`. 원본 로그 `sim/runs/robotarm/precommit_20261006/`. 최초 격리 빌드의 underlay 의존경로 누락은 기존 install을 지정한 최종3패키지 빌드로 해결했으며 실패/성공 로그 모두 보존.
- 경계: 받은9g 평가 환경을 적용했으며 원 체크포인트의35g 학습조건 전체 재현·학습정책 적용·실물 파괴력 측정으로 해석하지 않는다. 정밀Nav2 이동·정책 파지·적재는 미실행.
- 복원:019 물성은 유지하고 이번 진단/검사 도구 추가만 별도로 되돌릴 수 있다. 기존 사용자 파일과 받은 원본은 삭제하지 않는다. commit/push는 이번 사용자 요청으로 승인됐으며 실행 결과는 최종Git 원격 일치로 확인한다.


## ROBOTARM-PERFORMANCE-20261006-021 — GUI 검사 종료와 CPU 물리 병목 분석

- 일자/구분:2026-10-06 KST / 사용자 요청에 따른 성능 계측·문서 정정. 기준main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd.
- 대상:`ROBOTARM_PHYSICS_20261006.md` §11 및 CCD 설명, `docs/PROJECT_STATE.md` §17, 이 이력. 임시 계측 도구/JSON/로그는 ignored `sim/runs/robotarm/perf_20261006/`와 `cpu_microbenchmark_20261006/`에 저장했다.
- 전후:GUI 검사 종료와12FPS 원인 미확인 →사용자 JSON15 checks 통과/유한 검사 후 의도된 종료 확인. 현재 물리/진단 생략/과실 고정480Hz/과실 고정60Hz의 GUI 비교를 각각 실행해8.30/8.27/22.22/89.52FPS 측정. 마지막60Hz 대조군은 초기 reset 영향으로 카메라Z 약8.05mm 차이가 있고 이전 운영 버전 성능이 아니다.
- 결론:현재 조건 frame120.44ms 중 CPU 물리 실행/결과 동기화100.63ms(83.5%). runtimeCPU/GPUDynamicsfalse, GPU평균11.9%.288개 동적 과실과 전역480Hz가 부하를 늘렸으며 추가 상태 진단만 제거해서 해결되지 않는다.
- 정정:실행 시sceneCCD=true를 확인했다. 기존 “scene CCD false 유지” 설명은 잘못됐다. 설정 자체를 변경하지 않고 Teacher와의 차이를 기록했다.
- 검증:4개 GUI 비교 정상 종료, 물리1tick/렌더 시간 불변 검사 및 대조군288kinematic/변위0 확인. 준비30/측정120프레임씩. 순수 NumPy 수식288개0.495ms/tick. 초기 SDK getter 계측 실패 기록 보존 후 임시 도구만 수정했다. 전체fleet/정책 수확/장기 성능·최적화 적용은 미실행.
- 실물/시뮬 영향:운영 코드·자산·물성·공통/실물 실행 변경 없음. 분석용 고정/60Hz는 별도 프로세스 메모리/session 안에서만 적용하고 종료했다. 이번 문서는 미커밋·원격 미반영.
- 복원:이번 문서 항목만 비교 복원한다. 기존 사용자 변경 및 원본 JSON/전달 묶음은 보존한다.

## ROBOTARM-ADAPTIVE-20261006-022 — 수확 활동에 따른 물리 주기·주변 과실 선택

- 일자/구분:2026-10-06 KST / 사용자 승인 sim 구현·실제GPU/ROS 검증. 기준main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd 이후 미커밋. 승인 문구 “물리주기도 동적으로 … 수확중 수확로봇 인근 …”. 공통 업무 코드 변경 없음.
- 대상: runtime `physics_schedule.py`, `harvest_regions.py`, `harvest_physics.py`, `run_fleet.py`, `run_sim.py`; devices `fruit_attachment.py`, `harvest_activity.py`, `ros_adapter.py`, `package.xml`; config `robotarm_physics.json`, `harvest.json`; 새 검사도구 `check_adaptive_harvest.py`와 단위시험4개. 상세문서 `ADAPTIVE_HARVEST_PHYSICS_20261006.md`, 기존 물리/실행문서 연결, PROJECT_STATE §18, DECISIONS D-015, 검증JSON 갱신.
- 전후: 전체288개 항상동적/480Hz → 유휴60Hz·부착과실 고정, 수확중480Hz·오른팔 실제장착점0.8m/유지1.0m 영역합집합만 활성. 분리과실은 고정하지 않고0.6초 정지 후60Hz/움직이면480Hz. 부착과실의 움직임/분리타이머 동안 freeze 유예. 현재pose·앵커·기준자세·분리상태 보존. kinematic중CCDoff, 활성화시 원복·PhysX flush로 전환 순서 보장.
- 시간/동시성:60Hz 프레임당1~8물리tick과 렌더1회. 매tick 힘갱신, reset없이dt변경, 실제누적시각으로odom/clock/센서. 활동은 로봇별세션/seq/유효기간 검사, 다른 활동이 남으면 고주기 유지. 미래복수수확기 영역합산은 단위시험이며 현재 실제GPU는 예찰+수확각1대.
- 연결 경계:공통이동완료를 팔작업으로 추정하지 않는다. 내부set_activity와 sim전용Bool heartbeat를 추가했으며 실제팔정책/공통FSM 연결은 후속이다. 과실정답은 물리영역선택에만 사용하고 목표/수확성공으로 전달하지 않는다.
- 직접검증:단위/USD107개(skip0),sim3패키지빌드,실제ROS bridge13항목. GPU선택물리19항목/종료0,기존전체288개기준15항목/종료0. 근거리3개활성,3N분리41.667ms,0.20714m하강,60Hz복귀. 원본USD SHA256불변. fleet6초2개조건에서clock360/상태각180/RGB-D89/라이다10Hz/카메라pose시각검사 통과.
- 관측된 한계:동일0.08m/s 개방루프명령에서 고정60Hz와60→480→60Hz의 최종world위치 약2.6cm차이. 시계정상과 궤적동일성은 별개다. 바퀴drive/명령을 보정해 차이를 감추지 않았다. 짧은headless측정 실시간배율0.725대0.483. 이전GUI성능과 직접비교 불가.
- 중간문제:시험초기mount가 과실반경밖이어서 최초검사실패, 실제장착점기준 초기배치로 시험만 수정한뒤 통과. 초기kinematic+CCD경고는 batchflag전환순서로 해결. 실패로그 보존. 기존visual참조/Kit종료UI경고와 검사실패를 구분한다.
- 실물영향/미실행:실물·공통·원본자산 수정없음. 정책파지/적재·Nav2폐루프주행정밀도·다수수확기/운송·전체E2E·실물 미검증. 같은Scene고주기는 여전히 전역CPU비용이다. 독립세트주기는 별도인스턴스가 필요하다.
- 로그:`sim/runs/robotarm/adaptive_20261006/`, 각 결과의physics_log_directory. 검증요약:`sim/docs/changes/ADAPTIVE_PHYSICS_VALIDATION_20261006.json`. 문서/코드 로컬적용·sim패키지빌드 완료, 커밋/푸시 미실행.
- 복원:`adaptive.enabled=false`로 전체과실/기준480Hz모드 복귀. 영역처리유지/주기고정시험은idle_hz와harvest_hz를 동일값으로 설정. 전체코드복원은 이번파일만 비교복원하며 기존사용자문서/인수자료/백업을 보존한다. USD는 저장하지 않았다.

## TEACHER-INTEGRATION-20261006-023 — 도착 후 순차 수확 실현성·공통 변경 검토

- 일자/구분:2026-10-06 KST / 사용자 요청에 따른 구현 검토·승인 제안. 기준main/1666a23bf47dc7f0e8a6f2dfafbc1d41e190f6cd 및022 미커밋 구현. 요청은 도착 후Teacher에과실좌표제공→시도별물리성공/실패Feedback→대상처리후Result. 사용자선택으로빨강·노랑각1회/일반실패다음진행/녹색및차체추가이동제외 확정.
- 대상: `TEACHER_HARVEST_INTEGRATION_REVIEW_20261006.md`, `proposals/HARVEST_ARM_COMMON_CONTRACT_20261006.md`와 `.proposal` 스키마3개, `changes/TEACHER_INTEGRATION_REVIEW_20261006.json`, PROJECT_STATE §19, DECISIONS D-016/O-008, 이 이력. 검사스크립트/원본JSON은ignored sim/runs/robotarm/policy_integration_review_20261006 아래다.
- 직접검증: 정책4개/각run.json SHA256, 현재설치공식ActorCritic strict load·정규화·합성82D입력5개→6D유한/결정적출력. 전달/농장팔·박스 FK9자세/9link 강체변환 최대오차2.22e-16,실제USD정적8link 최대5.96e-7. 농장288root간격/자세/현재planner기하 정적비교. ROS Jazzy rosidl parser로 제안3종문법통과. 물리수확성공/타입생성·통신을시험한것은아니다.
- 주요발견: 좌표만이아닌82D+접촉/진행상태 필요. 원본환경은scene/physics소유하므로farmWorld어댑터 필요. 첫실패batch종료/실패후assign거절/미수집분리과실복귀거절과복귀25ms/계산50ms불일치를보완해야한다.0.8m물리영역과Teacher도달범위는별개,주변장애물은정책관측에서제외됨. 농장root최소132.77mm,18cm미만34쌍/66개.
- 제안: 공통harvest_robot가후보순서/누적결과/취소/Window종료를소유, sim이후보발견/단일과실Teacher/실제결과·정지·다음시도준비ACK를제공. 외부HarvestTask필드유지,내부HarvestCandidate/GetHarvestCandidates/PickFruit추가. 대상파일/실물영향/검증안을제시하고사전확인질문을보냈으며아직미승인이다. 부분실패를수량으로반환하면서대상처리완료SUCCESS로보는안도확인대기.
- 승인/실물영향: sim Teacher 정답입력은이번사용자의명시지시로허용,예찰/실물입력으로확대하지않는다. 공통/실물실행소스·기존모델·자산·물성·운영설정 수정없음. 새ROS타입등록/빌드/팔GPU실행/전체수확E2E미실행. 추가정책파일은필수누락아니며담당자에게검증된연속도달범위·실패복구·독립추론접점이있으면요청하는문구만작성했다. 실제외부메시지는전송하지않았다.
- 다음: 공통범위/부분성과종결의미 확인 후 독립9g재현→농장단일과실→실패후순차진행→Action·취소→동시Nav2검증. 기존022의주행응답차이를해결완료로취급하지않는다.
- 복원:이번검토문서/제안/상태기록만비교복원한다. 기존미커밋022/사용자AGENTS·README/받은원본은보존한다. 이번검토는미커밋·원격미반영이다.


## SIM-COMMON-20261006-024 — 최소 공통 연결과 sim Teacher 실행

| 항목 | 내용 |
|---|---|
| 기준 | main/1666a23 이후 미커밋. 앞선 동적 물리·검토 및 사용자 변경 보존 |
| 승인 | 사용자 “대부분 로봇팔 구동 코드는 sim 전용 … 공통에서 도착하자마자 result를 날리면 그 부분을 sim 코드에 연결”. 앞선 빨강/노랑 각1회·Teacher규격·좌표정답사용 승인 유지 |
| 공통 대상 | harvest_robot의 node/mission/communication/contract 및 새 arm_client. 상세는 docs/changes/HARVEST_ARM_HOOK_20261006.md |
| sim 대상 | teacher_policy/state/device/_teacher_vendor, arm_session/arm_ros, ros_adapter/package/setup, run_fleet/physics_schedule, harvest/harvest_task/teacher_policy 설정, 정책4개+run자산, 시험/도구/문서 |
| 변경 전후 | 도착 후 수확0 즉시반환→시뮬 내부Action 실제완료·정지대기. 지역활성→후보확정→20Hz정책→물리복귀/안착→누적결과. 메시지신규타입/공통Window실행기 제안은 미채택 |
| 성과 의미 | 정상 후보전체처리SUCCESS, 실제안착·실패수량 별도. 취소는정지확인, 미확인은차단. 과실/관절teleport·재부착·가짜성공없음 |
| 실물 영향 | 실물설정/모델/장치·공통주행/비전·외부메시지 불변. legacy도착전용설정 유지. 현재새팔장치는sim만 선택 |
| 직접 검증 | 178단위/USD 중176PASS/ROS2skip, 별도실ROS/UDP2PASS,4패키지build. 최종Isaac fixture 실제정책/복귀/실패수량/정지/정상종료 PASS. 원본FK·CPU재생 대조. 자세한 숫자와 취소 결과는 실행보고서 |
| 성능 한계 | 실제농장3과실 적재0. ENTRYtimeout/bad_detach 후복귀. 적재성능PASS와구분. 다중과실/기존적재실물보존/Nav2전체E2E/실물/카메라/다수로봇 미검증 |
| 중간 실패 | SDK sensor/filter길이오류 수정, testerSIGINT/짧은Kit종료대기-11 수정. 최종프레임종료+60초대기 code0확인, 중간실패로그보존 |
| 결과 | sim/runs/robotarm/teacher_integration_20261006, teacher/<session>/<job>; 요약 sim/docs/changes/TEACHER_RUNTIME_VALIDATION_20261006.json |
| 되돌림 | 실행중지후 harvest_task completion_policy=ARRIVAL_ONLY_NO_HARVEST, harvest runtime.harvest_arm.enabled=false. 소스복원은 이번변경만, 다른미커밋변경초기화금지. 동적물리별도설정유지 |

[실행·검증 보고서](TEACHER_HARVEST_RUNTIME_20261006.md). 커밋·푸시는 수행하지 않았다.

## SIM-TEMP-CONTROL-20261007-025 — 임시 예찰→수확 관제 CLI

- 사용자 요청: 나중에 삭제할 사이클 확인용 관제를 sim 안에 추가. 공통/실물 소스 변경 없음.
- 추가: `sim/tools/temporary_control.py`, `sim/tests/test_temporary_control.py`. 실행 가이드 §7 및 PROJECT_STATE §21 갱신.
- Section 입력→ScoutArea 성공 최종 목록→원본 HarvestTask 순차 요청→수량 출력. 실패/취소 부분 예찰 목록 제외, 중복 ID 사전 거절, 수확 작업 실패 시 큐 중단. Ctrl+C 자기 Goal 취소/종료 대기, 정지 미확인 차단. JSONL은 sim/runs/temporary_control.
- 직접 검사: ROS 설치 메시지를 이용한 단위검사 6개, --help 로딩, diff 공백 검사. 실제 네트워크 Action/Isaac/Nav2 전체 사이클은 이번에 실행하지 않음.
- 기준 main/1666a23 이후 미커밋. 기존 미커밋 변경 보존. 커밋·푸시 없음.
- 되돌림: 위 임시 도구/시험과 가이드 §7 제거. launch와 로봇 실행은 변경하지 않았음.

## SIM-RVIZ-20261007-026 — FollowPath 추종 경로 표시

- 사용자 요청에 따라 sim의 scout_harvest/scout/harvest.rviz에 로봇별 `/received_global_plan` Path를 추가했다. 예찰 초록, 수확 주황, 선폭0.045m·높이0.12m. 기존 planner `/plan` 표시는 비활성화하고 이름으로 구분했다.
- 현재 GeoJSON 경로는 FollowPath로 직접 전달되므로 planner `/plan`만 구독하면 추종 경로가 표시되지 않을 수 있다. RPP가 발행하는 변환/가지치기 구간을 표시하며 전체 원본 Goal Path나 전체 그래프와 동일하다고 설명하지 않는다. 기존 route_markers 표시는 유지한다.
- 공통/실물/주행 코드·주기·도착 허용오차 변경 없음. 설치된 RPP 라이브러리의 토픽 이름과 YAML3개 설정을 확인했다. 실제 RViz 화면·이동 중 수신 검증은 미실행.
- RViz만 설정 재로드하면 적용. 되돌림은 이번 Path 항목 제거와 기존 plan Enabled 복원. 기준1666a23 이후 미커밋, 커밋·푸시 없음.

## SIM-NAV-20261007-027 — 베드 평행 접근 분석·공통 변경 승인 대기

- 사용자 베드 앞 정렬/평행 주행 요청.16개Section 모두 정차선과 기존 수확 graph가60mm 불일치함을 정적 확인. 실제6개 수확로그 최종60mm 구간이 목표 yaw와90도 차이. geometry.json에 저장.
- sim/docs/proposals/HARVEST_PARALLEL_APPROACH_20261007.md에 sim 수확 graph 정렬과 공통 선택적 진입/최종방향 검사·이미 도착 처리의 파일/영향/검증안을 작성. 실행 코드/설정/graph 미변경, 공통 승인 대기.
- 실제 새 주행 미실행. 기존 변경 보존, 커밋·푸시 없음. 되돌림은 이번 제안/분석 기록만 제거.

## SIM-COMMON-20261007-028 — 수확 평행 접근 적용

- 사용자 “수정해”로027 제안 승인. common farm_navigation3파일+parallel_approach.py, sim 생성기/task/survey/harvest graph/runtime/Nav2 설정 변경. 상세 docs/changes/HARVEST_PARALLEL_APPROACH_20261007.md.
- 주행선60mm 정렬, 넓은 기존 진입부 도착/정렬 후 평행 주행, 다른 구간 이동 전 정방향 이탈. 이미 도착 시 정지 재검사. 좁은 구간 복구 조건 불충족은 실패. 실물 옵션기본false/설정 불변.
- 신규7검사/371경로/build PASS. 기존도착검사9PASS/1구형메시지fixtureERROR. 실제 신규 Isaac 주행/회전충돌 여유 미검증. 사용자 실행 중인 프로세스는 재시작하지 않았음.
- 재시작 후 station에서 첫 Goal 재전송 필요. 기준1666a23 이후 미커밋·원격 미반영. 복원은 이번변경만 대상으로 한다.

## SIM-DRIVE-20261007-029 — 수확 회전·제동 보정

- 사용자 진입 정렬0.2486rad 실패 및 “해결해” 요청. sim base_sim/wheel_servo, harvest.json, nav2_harvest.yaml, harvest_runtime.yaml, drive_diagnostics, 물리 시험도구/단위시험/보고서 수정. 공통·실물 소스 및 원본USD 불변.
- 엔코더 각도차 속도 PI 보정과 정지시 적분 초기화·반대방향 제동. 수확만 활성화, 저속정렬0.06rad/s/각가속0.1/yaw gate0.01; 최종0.05rad 도착 기준 유지. 느린회전 대응 progress120/goal600초.
- 실제 Isaac 기존추가회전0.2534rad 재현. 최종 양방향 저속제동 추가회전0.00319/0.01317rad, 목표각도 후정지 오차0.00510/0.00932rad PASS/code0. 신규servo4+평행7검사/371경로/3패키지build PASS. Nav2 전체 경로·관제E2E·480Hz 동시주행 미실행.
- 비교시험 gain/solver/휴면 설정은 최종코드에서 제거. 중간시험 snapshot 공유 충돌 발견 후 별도 출력으로 수정. 해당 실패 및 중지한 비정상종료는 PASS 제외. 운영 snapshot 기반 평가가 시험 중 섞였을 가능성은 상세보고서에 기록.
- 상세 sim/docs/HARVEST_BRAKING_20261007.md, 결과 changes/HARVEST_BRAKING_VALIDATION_20261007.json. 사용자 운영프로세스 재시작은 하지 않았다. 적용은 all launch 재시작. 원복은 servo설정 제거 및 이번 속도/대기설정 복원. 미커밋·푸시 없음.

## SIM-NAV-20261007-030 — 실제 Nav2 코너 회전 시작 실패 보정

- 사용자18:06실패로그 직접 확인: controller_server Failed to make progress. 구동로그539072...에서첫코너전제자리 각명령약±.005rad/s. 이전 일정.06rad/s시험은 Nav2피드백결합 검증이 아니었다.
- sim nav2_harvest.yaml의 RPP.max_angular_accel만.10→1.2. 정렬속도.06/도착기준/PI/충돌검사 유지. 실제 전체Nav2 재검증 미실행. 설정생성일치/371경로검사 PASS.
- 실행중은 ros2 param set으로 적용가능. 사용자프로세스에는 자동 명령을 보내지 않았다. 원복은각가속도.10이나 기존정지문제재현가능. 미커밋·원격미반영.

## SIM-HARVEST-UI-20261008-031 — 배치·480Hz 수확 시험 패널

- 일자/기준: 2026-10-08 KST, main/7d9ae40ec8e0d0bebf0e0552f8a6ee85ddfc9bc3 이후 미커밋. 시작 Git 상태 clean. 원격 재조회·커밋·푸시 없음.
- 승인 근거: 사용자 “로봇팔 480hz 물리 연산 기준 … UI … 배치 버튼(수확가능한 열매가 있는 무작위 적정 위치) … 수확 버튼(480hz 전환, 인근 파프리카 물리)”. 시뮬 전용 시험 범위다.
- 파일: tools/harvest_test_ui.py; runtime harvest_test_placement.py/harvest_test_ui.py/run_fleet.py; devices arm_session.py/teacher_device.py의 읽기 전용 상태·장착점 조회; tests/test_harvest_test_{placement,ui,ui_launcher}.py; HARVEST_TEST_UI_20261008.md, RUN_GUIDE, PROJECT_STATE, 이 이력.
- 전후: 고정 fixture/CLI 위주 → 실제 Isaac GUI의 Place robot/Harvest/Stop 버튼으로 반복 관찰 가능. 기존 정차선/측정 팔 장착/Teacher 범위/원본 바닥지도 footprint 검사 후 미시도 부착 빨강·노랑 후보가 있는 배치를 선택한다. 차체 전체의 시험용 순간 배치이며 Nav2 성공으로 기록하지 않는다.
- 실행: python3 sim/tools/harvest_test_ui.py. 단독 수확 장치·사용 가능한 별도 UDP 포트·snapshot/로그 생성. ROS/빌드 불필요, 외부 UDP 제어 무시. 원본 fleet/지도/USD/Teacher/물성 보존. 공통·실물 코드 변경 없음.
- 물리/제어: 기존 ArmSession/Teacher/HarvestPhysics/AdaptivePhysicsTicks 재사용. 실제 정지/HOME/후보 재확인, 60→480→안정후60Hz, 주변 활성·20Hz 정책·실제 성공수량 유지. 활동 중 배치/중복 수확 차단. 적재 후 차체만 순간이동하거나 취소 후 비HOME 상태로 재배치하지 않는다.
- 직접 검증: 관련75검사 PASS(skip0); 새 배치10/UI13/실행기8 포함. Isaac5.1 GUI/RTX4070SUPER seed713 SEC10 Bed01/Pepper0017 yellow: 정책400회, 주변5/288 활성, 실제복귀/정지확인 및480→60Hz·활성0, 종료0. 처리SUCCESS지만 실제 적재0/실패1(target_timeout). 수확성능 개선 PASS가 아니다.
- 화면 검증: 최초 ReviewCamera 선택/한글 글리프 문제를 발견했다. Perspective를 명시 선택해 작업 팔과 과실/바구니를 보여주고 패널은 영문으로 제공한다. 최종 GUI 재실행·창 캡처에서 카메라/버튼/단계/480Hz/활성5개 표시 확인. UI 창 닫기 버튼을 제거하고 전체 Isaac 종료로 정리, timeline reset은 프레임 시작에서 감지한다.
- 로그/보고: sim/runs/harvest_test_ui/validation_20261008/{result.json,unittest.log,isaac.log,final_gui.png,final_gui_run.json}; 연결된 physics/teacher 경로는 result.json. 최종 GUI는 직접 조작하도록 실행 상태로 남겼다.
- 미검증/다음: 사용자 수동 클릭·다양한 seed의 실제 성공률·동시 운영 시뮬·Nav2 포함 E2E는 미검증. 적정 배치의 근거리/바닥 검사는 팔 IK/모든 동적 장애물 회피 인증이 아니다. 다음은 사용자가 버튼으로 반복 관찰하고 기존 Teacher 농장 성능을 별도 개선하는 일이다.
- 되돌림: 독립 도구/패널/기하/시험 추가 파일, run_fleet 선택 연결과 devices 읽기 API 및 문서 항목만 비교 복원한다. 전체 reset 금지. 배포 패치는 변경 파일만 sim/runs/harvest_test_ui/harvest_test_ui_20261008.tar.gz, 적용 명령은 실행 가이드에 기록했다.

## SIM-PHYSICS-INSPECT-20261008-032 — 충돌 메뉴·과실 물리 관찰

- 사용자 요청: Show By Type에 없는 Physics collision 표시 추가, 중력/connector 연결과 랜덤 회전 유지 여부 확인. 031 미커밋 변경을 보존하고 추가. 기준main/7d9ae40, 이번 원격 조회·커밋·푸시 없음.
- 대상: runtime 신규 harvest_physics_inspector.py 및 run_fleet/run_sim/harvest_test_ui; devices fruit_attachment 진단 snapshot/teacher_device 읽기 접촉 API; inspector 신규4검사/UI 추가2검사/접촉 추가1검사; 물리 진단 가이드·기존 UI가이드·PROJECT_STATE·이력.
- 전후: PhysX GUI 확장 미활성/수확 때만 확인 → GUI 실행에서 공식 omni.physx.ui 활성화, Show By Type > Physics > Colliders 메뉴와 패널 Hide/Selected/All 제공. Physics only 관찰은 팔정책 없이 기존 주변영역480Hz를 사용한다. 전역물성/원본USD/정책/실물·공통 코드는 변경하지 않았다.
- 계측: 선택 과실의 active/kinematic/gravity/collider flag, 초기 PhysX질량, 실제 pose/속도·root dz·tip 변위·회전각, 이전 tick 적용 줄기 힘, SDK 선택과실별 손가락 접촉력. mg는 Scene중력×질량 계산값임을 명시. 앵커/꼭지/COM/중력 표시만 추가하며 물리 joint를 생성하지 않는다.
- 발견: 현재 connector와 과실의 자유회전 native joint가 아닌 world 고정 앵커 spring + 초기 랜덤 quaternion 복원 토크다. 유휴부착과실은 kinematic. 중력이 작동해도 수직으로 완전히 정렬되지 않는 이유이며 성공0의 단일 원인을 확정하지 않는다.
- 직접검증: 99개 실행98PASS/1USD미설치skip/실패0. 실제GUI seed713 Bed01/Pepper0017 yellow, 팔정책 없이8초480Hz/주변5개: root하강10.788mm, 회전8.360°, 남은COM-꼭지기울기35.099°, mgZ -0.088290N/적용줄기Fz +0.088290N. collider1/1 convexDecomposition, 안정후60Hz/활성0, 종료0. 새GUI 재실행에서 와이어/표시와 선택과실별접촉0/0 확인. 이번 직접 수확접촉/파지 성공 검증은 아니다.
- 로그: sim/runs/harvest_test_ui/physics_inspection_20261008/{result.json,unittest.log,gui.png,final_gui.png}; 실행별 physics_inspection.jsonl. 최종 진단창은 열어두고 기존 사용자시험창/로그는 건드리지 않았다.
- 다음/한계: Harvest 중 실제집게 접촉력과 충돌형상 대조; 자유진자 connector 모델이 필요하면 별도 물리 모델 설계/Teacher 영향검증. 이번에 angular_k 완화/자세 초기화/가짜 성공은 하지 않았다.
- 복원: 032의 inspector/관찰 토글/읽기 API/GUI 확장 활성화와 해당 문서 항목만 비교 복원한다. 031 및 사용자 변경은 유지한다. 패치는 변경 파일만 포함, 적용 명령은 UI 가이드와 동일하다.

## SIM-TEACHER-DIAGNOSTIC-20261008-033 — 로봇암팀 요청 재현·회신 로그

- 승인/기준: 사용자 “robotarm/SIM_TEAM_TEACHER_DIAGNOSTIC_REQUEST 확인 … 자료 보고 회신 로그 확보”. main/7d9ae40 이후031/032 및 사용자 미커밋 변경을 보존했다. 공통·실물 코드/운영 설정·정책·물성·원본 robotarm 자료 변경 없음.
- 대상: sim teacher_policy.py에 기본off forward hook 계측; 신규 runtime teacher_diagnostics.py; run_fleet/check_teacher_harvest 선택적 --teacher-diagnostic-trace 연결; 신규 test_teacher_diagnostic_trace.py; 회신 문서·PROJECT_STATE·이 이력. 산출물은 sim/runs/robotarm/receiver_diagnostic_20261008.
- 전후: 기존 sample/최종action 위주 로그 → 실제 원본/시간보정/정규화82D와 전문가 raw action, 후처리/clip/최종6D, 상태 플래그, 실제 관절 target buffer·시뮬/벽시계·물리step·dt·초기/복귀/정지 연속 기록 및 USD/PhysX 설정. 추가추론/정규화 재학습 없음. USD 자동계산·무제한 Infinity는 최종계측에서 문자열로 저장하며 초기 노랑 원본은 보존하고 portable사본 추가.
- 전달본 직접 확인: 최초143434 TAR hash7b33...일치; 새해제본2148개검사 후 cache경로보정. 정책4개+run.json·전달평가소스불변. prepare/cache차이12파일은diff로보존.
- 실제 GPU 독립진단: 받은 무카메라 어댑터·전달실행기로 red182/yellow183각5회. 성공3+4/실패2+1, 두프로세스0종료. 송신10개trace1069tick가 SHA256까지일치. 카메라/YOLO포함원본스크립트E2E는미실행.
- 실제 GPU 농장: 기존headless fixture 노랑400POLICY timeout, 빨강42POLICY bad_detach, 실제적재0/2; 두job복귀/정지확인·종료0. 정책dt=.050000002608s, 각24physics step=480Hz. 원본관측/명령/PhysX전달 각19검사통과. taskSUCCESS/검증passed와수확성공을분리.
- 발견: 빨강양손접촉3.754/3.982N 있으나 파지확인0.05s<0.25s, 총변위46.790mm·지속41.667ms 이탈(인장0N), 정상파지전분리. 노랑최소거리74.99mm/양측접촉없음. farmUSD자기충돌false·solver32/1 vs전달소스true·12/4, 초기과실랜덤회전/고정차체차이. 단일원인으로확정하거나이번에수정하지않음.
- 검증: 실제가중치등Teacher/ArmSession60개+fleet entrypoint2개PASS, skip0; 새로운계측11개포함. 추가추론없이action/target·normalizer불변검사. diff --check/구문검사 및 회신manifest검증.
- 오류/한계: GUI2회는Teacher/recorder생성전World.__init__.render nativeOmniGraph SIGSEGV(-11). startup_error 로그별도보존, 성공/수확실패분모제외. 이번viewport영상미확보. 동일초기조건farm대조·Nav2·실물미실행.
- 회신: sim/docs/TEACHER_DIAGNOSTIC_REPLY_20261008.md, TAR+SHA256+MANIFEST. 원본stdout/trace/결과·설정·모델계약·관련source포함,checkpoint/RGB-D/전체해제본제외. 발송·커밋·푸시·원격재조회없음.
- 복원: 진단 플래그를 생략하면 기존제어경로다. 추가계측/CLI연결/시험·문서만비교복원하며031/032·사용자변경은유지한다. 다음은 담당자와같은q/목표pose/TF/threshold조건으로최초관측/action차이와solver·접촉영향을분리하는비교다.

## 2026-10-08 — AprilTag 태그 배치와 수확 PCWEB400 가상 카메라

- 구분/승인: 사용자 직접 요청의 sim bed 배치·수확 카메라/bringup 연결·공용 코드 인수 확인. 후속 답변으로 각 면100~114 반복/구간ID와 함께 식별 확정. 기준main/450bf5f, 기존 미커밋 수확 작업 보존.
- 대상: `assets/apriltag/`, 수확URDF, `farm_sim_config/config/{apriltag_layout,apriltag_map,harvest,scout,scout_fleet}.json`, 런타임`apriltag_scene.py` 및`run_sim/run_fleet`, 장치`camera_sim/camera_ros/ros_adapter`, generator·USD/렌더검증도구, 관련시험·상태/결정/실행문서.
- 전후: 태그없음/수확camera.disabled → session layer16벽240개(15원본반복), 수확측면optical센서 및RGB/CameraInfo발행. 기존공통bringup의sim장치선택으로연결해공통소스변경불필요. 실제웹캠depth없음. 예찰센서장착·경로·원본USD·실물설정은유지.
- 검증:19PASS,USD벽범위/크기/TF검사PASS,실제IsaacID104렌더검출/공유메모리전달PASS,3패키지build/371경로PASS. 첫Kit종료지연으로해당시험만정리, 최종렌더결과저장후종료timeout124. 최종반복IDUSD검사재실행. 전체DDS·이동검출/보정·실물미시험. [상세](APRILTAG_INTEGRATION_20261008.md),로그`sim/runs/apriltag_20261008/`.
- 코드인수: 로컬공용코드에AprilTag검출/보정없음. [요청서](APRILTAG_NAVIGATION_REQUEST_20261008.md)작성,발송없음. 공통수정승인대상diff는이번작업에없으며후속소스인수후검토한다.
- 실물영향: 없음. 실물harvest장치bringup은여전히미구현. 카메라장착은실측기반추정이며정밀실물검증완료가아님.
- 복원: 장치JSON의apriltag_map제거/harvest.camera.enabled=false후재시작,URDF추가광학링크/조인트제거. 기존미커밋수확변경을통째로되돌리지않는다. 미커밋·원격미반영.

## SIM-PEPPER-ROTATION-20261008-035 — 수확 비교용 랜덤 기울기 0도

- 사용자 요청: 기존 seed/최대각도 회전 스크립트를 찾아0도로Isaac적용. 기준 main/450bf5f 및 기존 미커밋·AprilTag 변경 보존.
- 도구: sim/tools/randomize_pepper_rotation.py → scout_dataset.stage.randomize_current_stage_and_save. 기존 구현 그대로 사용; sim/config/scout_dataset.json fruit_rotation.max_degrees만30→0, seed734유지.
- 실제 Isaac headless stage에서 기존 runpy 스크립트를 실행해 farm_with_plants_v5.usd 저장·정상종료0. 288개 jitter XYZ=0, world local-Z 기울기 전0.964~41.171°→후모두0°. 위치/원래xform op/ID 유지. 원래 yaw는보존하며모든quaternion이identity라는뜻은아님.
- 백업: sim/assets/envs/output/farm_with_plants_v5.usd.before_rotation_20261008_142400_041527. 설정백업/실행스크립트/stdout/전후288개검증은 sim/runs/pepper_rotation_zero_20261008.
- 실물·공통·물성·정책변경없음. 기존실행창의메모리상태는유지. 별도UI는초기화SIGSEGV(-11)로종료해ready미확인(gui.log/gui_result.json). 맵저장프로세스종료0과구분. 기존Isaac재시작으로새맵로드필요. 이번수확성공률재시험은아직수행하지않음.
- 복원: 위USD백업을원래파일로복사하고설정max_degrees=30(seed734)복원한뒤Isaac재시작. 커밋·푸시없음.

## SIM-HARVEST-UI-STARTUP-20261008-036 — 시험 GUI 시작 종료 수정

- 사용자 오류 수정 요청, 기준 main/450bf5f 및 기존 미커밋 보존. 대상: 런타임 `run_fleet.py`, `run_sim.py`, `harvest_physics_inspector.py`, `physics_schedule.py`, inspector 회귀 검사 및 상태 문서.
- 조기 PhysX UI 확장 활성화 상태에서 World 초기 render가 native SIGSEGV로 종료됐다. 확장 등록을 World/장치 초기화 뒤로 이동했다. 이후 드러난 dt 오류는 layers 확장이 USD 편집 대상을 session→root로 변경해, 더 강한 session의480Hz가 root에 쓴60Hz를 덮은 문제였다. 확장 활성화 성공/실패 모두 기존 edit target을 복원하며 dt 불일치 메시지에 실제/기대값을 추가했다. 충돌 메뉴와 엄격한 주기 검사는 유지한다.
- 실제 Isaac5.1 GUI: 일반3초/180tick 종료0, 물리 관찰14초/840render/4200tick 종료0. 1.520833초에480Hz·주변5과실 활성,9.520834초에60Hz·0과실 복귀. 일반 무기한 시험창 재실행 및 패널/60Hz 화면 확인 후 열어둠. 로그·화면 `sim/runs/harvest_ui_startup_fix_20261008/`.
- 관련 검사39개 PASS(레이어 복원 성공/실패, 주기, UI, launcher, fleet entrypoint). 넓은 harvest 패턴 검사112개에서는 별도 geometry 단일 테스트의48개 subtest 실패 및 sandbox UDP 차단3오류가 있었다. UDP 관련 launcher8개는 허용 환경에서 전부PASS. 경로 기하 실패는 이번 시작 수정 범위에서 수정하지 않았다. run_sim 실제 GUI 및 수확 성공률은 이번 미검증.
- 실물/공통/Teacher/물성/0도맵 변경 없음. 복원은 이번 확장 호출 이동·edit target 보존·오류 메시지만 역적용하며 기존 사용자 변경을 통째로 되돌리지 않는다. 수정 파일 묶음 `sim/runs/harvest_ui_startup_fix_20261008/changed_files.tar.gz`는 현재 미커밋 파일 전체를 포함한다. 커밋·푸시 없음.


## SIM-TEACHER-ARM-ALIGNMENT-20261008-037 — 학습 오른팔 물리 정렬

- 승인: 사용자 “로봇팔 물성치, 충돌 판정 … 다 학습환경에 맞춰서 수정”. main/450bf5f 및 기존 미커밋 보존. sim 전용, 실물/공통/전달 정책 소스 변경 없음.
- 대상: `teacher_arm_alignment.py`, `robotarm_asset_setup.py`, `harvest_physics.py`, `teacher_device.py`, `teacher_diagnostics.py`, `run_fleet.py`(종료 전 최초 예외 보존), `robotarm_physics.json`, 기준 팔usdc/manifest, 추출/대조 도구2개, 회귀 검사, 물리 확인/진단 회신·상태·결정 문서.
- 변경: convexHull→전달 convexDecomposition 메시15개; 여섯몸체 질량/COM/관성·집게카메라 합성; 자기충돌true/solver12·4, 학습GPU/TGS/접촉설정, material, 팔 collider1mm override제거, 학습4링크 접촉센서. 이동 차체·왼팔/바퀴 구동 구조 유지. 원본USD 미저장/세션적용. [상세 비교와 환경 차이](HARVEST_PHYSICS_INSPECTION_20261008.md).
- 검증: 독립 전달1회 종료0, 농장GUI3초 종료0, USD/PhysX115항목 일치(최종GUI 반복확인), 회귀56PASS. 수확480Hz/주변5과실 및60Hz복귀/정상종료0. 수확 적재0/1: arm_collision→return_contact_2.779N→safe_stopped=true. 수확성공률 개선/전체학습환경 동일성 검증 아님. 최종 GUI 열어둠.
- 최초 통합2회는 SDK 확장속성 API 부재로 초기예외, 종료native오류가 원인을 가림. typed USD attribute fallback 및 종료전 예외기록 후 해결, 세 번째부터 정상. 실패로그도 보존.
- 결과 `sim/runs/arm_physics_alignment_20261008/`, 설정/초기 코드 백업 포함. 복원: teacher_alignment.enabled=false 후 새실행(기존 팔 물리 경로). 전체 파일 reset 금지. 변경파일묶음/적용명령은 상세문서에 기록. 커밋·푸시/외부발송 없음.


## SIM-FRUIT-RENDER-SYNC-20261008-038 — 과실 물리/화면 위치 동기화

- 승인: 사용자 내부 적재 로그와 초기 위치 화면의 차이 조사 요청. main/450bf5f 및 기존 미커밋 보존.
- 대상: devices 신규 fruit_pose.py 및 fruit_attachment.py, runtime fruit_asset_setup.py, pose 신규검사/asset 설정검사, 물리진단·회신·PROJECT_STATE·이력 문서.
- 원인/수정: 사용자 정의 matrix op로 고정된 과실은 동적 PhysX만 이동하고 표시 root/mesh는 정지했다. 초기 배치/재고정 모두 pose를 보존한 표준 translate/orient/scale로 작성한다. 내부 SUCCESS만으로 화면 운반을 확인했다고 한 판단을 정정했다.
- 검증: 실제GUI 통제 이동·낙하23sample 최대 물리/표시 오차0.550647m→0.000590m(root0m). 최종5초/300render/1763physics/종료0. 초기3probe는 완료 후 잔류종료를 수동 정리했으며 최종 정상종료와 구분. 단위·USD43PASS. 새 일반GUI480→60Hz 및 화면 확인. 전체수확 성공 재검증은 미실행.
- 실물영향 없음. 정책·마찰·질량·성공기준·원본맵 불변. 결과/백업/변경파일묶음 sim/runs/fruit_render_sync_20261008. 복원은 before.py와 이번함수/검사 차이만 비교하며 기존변경 유지. 적용명령은 물리진단문서 마지막 절.
- 다음: 새GUI에서 실제 파지→운반→적재 관찰. 문서갱신, 커밋·푸시·외부발송 없음.


## SIM-HARVEST-PHYSX-OPT-20261008-039 — 단독 시험 UI의480Hz 비용 축소 (정적화는040에서 철회)

- 승인: 사용자의 PhysX step 최적화 요청. sim 런타임3개 파일(physics_schedule, harvest_test_ui, run_fleet)과 관련 검사만 변경. 실물·공통·원본USD·학습 팔 물성/충돌/주기 불변.
- 변경: 미사용 선별기/정찰 로봇43강체를 표시·충돌 형상 보존한 정적 배경으로 전환. USD 위치/속도 쓰기를 렌더 프레임의 마지막 tick에 수행. 힘/물리/접촉은480Hz 유지. 두 변경 모두 시험 UI에만 활성화.
- 실측: 동일seed713의480Hz GUI 수확에서 물리 step195.84→102.43ms, FPS4.28→7.01. 실제 적재0/1, 복귀 접촉 실패는 남음. GPU backend 유지; CPU/MBP10.51FPS 비교는 미적용.
- 검증: 관련37검사PASS, 운영GUI 종료0·표시 위치136표본/배경형상불변·PhysX오류0. 독립 sleep/재활성/480→60→480 시험 종료0(최대 위치오차1.92e-8m). Stop→재배치→240Hz 재수확 확인. [상세 수치·재현·범위](HARVEST_TEST_UI_20261008.md), 로그 sim/runs/physx_optimization_20261008.
- 복원: run_fleet의 configure_test_background 호출과 batch_usd_writeback 활성화만 역적용. 기존 사용자 변경/물성정렬/과실표시수정 보존. 커밋·푸시·외부발송 없음.


## SIM-HARVEST-PHYSX-RESTORE-20261008-040 — 네 로봇 동시 운용 요구에 따른 정적화 철회

- 사용자 정정: 예찰·수확·운송·선별팔은 최종적으로 모두 동시에 움직여야 하므로 다른 로봇 정적화는 부적절함.
- 변경: harvest_test_ui의 configure_test_background, run_fleet의 해당 호출, 전용 test_harvest_test_background.py 제거. USD 쓰기 프레임 단위 처리만 유지. 이전 GUI 세션 종료 후 새 stage로 실행. 원본USD/실물/공통코드 불변.
- 수치 정정: 7.01FPS/PhysX102.43ms는 두 로봇을 정적화한 폐기 조건이다. 로봇 물리 유지 시 기존 비교4.28→4.67FPS이며 네 로봇 동시 운용 실측은 미실행. fetch_results는 계산 완료 대기/결과 반영을 포함하므로 readback 주병목 단정도 철회.
- 검증: 스케줄러15·UI17·진입점2개PASS. 실제 물리 복원 로그는 sim/runs/physx_optimization_20261008/restored_scene.json 및 restored_ui.log. [현재 범위와 기록](HARVEST_TEST_UI_20261008.md).
- 사용자 변경 보존, 커밋·푸시·외부발송 없음. 정적화는 다시 적용하지 않는다.

## SIM-HARVEST-PHYSX-PROFILE-20261008-041 — GPU 커널과 대기 FPS 간극 실측

- 승인/기준: 사용자 “병목을 더 확실하게 파악 … 기존 Nav2 약70FPS와 현재대기22FPS 간극 확인”. main/450bf5f 및 기존 미커밋 보존. 운영 소스·설정·정책·원본USD·실물·공통 코드 변경 없음.
- 대상: `sim/runs/physx_bottleneck_20261008/`의 격리 계측 wrapper/결과와 `HARVEST_TEST_UI_20261008.md`, `HARVEST_PHYSICS_INSPECTION_20261008.md`, `docs/PROJECT_STATE.md`, 이 이력. CPU/MBP 전환·좌표기록 생략/캐시는 임시 대조 실행만 적용.
- 전후: fetch_results 경과시간만으로 CPU/GPU원인을 분리하지 못함 → Nsight CUDA/NVTX/OSRT와 PhysX profile zone으로428tick분리. USD쓰기없는fetch17.843ms 중GPU커널15.924ms, GPU→CPU복사0.0619ms/tick. 상위관절커널각15408회=428×36,1block×32thread. GPU solver최대반복32/4의 장면전체영향을 공식107.3소스/실제커널로 확인. 기존팔115항목속성검사한계를명시.
- 대기 비교: 동일ReviewCamera1280×720/센서OFF/각새프로세스. 모든기존로봇97동적/3관절계·과실형상4829유지, GPU29.80FPS→CPU50.23FPS. 좌표기록생략진단GPU31.95/CPU59.53FPS. 원본맵대조는43동적/2관절계/29convex/CPU,실제59.56FPS(60cap)·물리1.81ms. sleep제외처리용량138.49를실제FPS로사용하지않음. 원본맵SHA전후동일.
- 수확 비교: CPU480Hz작업13.01FPS,seed713적재0/1,RETURN_FAILED/2.839N·실제정지확인·정상종료0. 성공률개선/물리backend동등성으로해석하지않음. 상세현재GPU대조와좌표캐시결과는연결보고서참고.
- 검증/한계: 실제Isaac5.1 GUI격리대조와Nsight원본보존. 최초Nsight실행은optional SDK cooking API선택오류로capture전종료1,수정후최종종료0; 실패로그보존. CPU IP sampling권한제한은우회하지않음. 실제Nav2경로주행·과거사용자70FPS정확조건·최종4로봇동시미션·다지점수확회귀는미실행.
- 복원: 이번에는운영변경없음. 진단wrapper를사용하지않으면기존기본GPU/수확480/대기60Hz. 추가문서만해당절비교복원하고원본로그는보존한다. 다음은환경조건완화보다CPU480Hz접촉/관측/성공률회귀우선. 문서갱신,커밋·푸시·외부발송없음.

## SIM-HARVEST-REPORT-20261008-042 — 최적화 종합 자료와 Git 반영

- 승인: 사용자 “최근커밋 이후 수정사항 커밋메세지에 간략하게 … 480hz 물리 연산 적용 후 … 보고서 작성용 md”, 후속으로 commit+pull+push까지 명시. 기준 main/450bf5f 이후 미커밋 변경 전체를 보존·반영한다.
- 대상: `HARVEST_OPTIMIZATION_REPORT_MATERIAL_20261008.md`, `changes/HARVEST_OPTIMIZATION_EVIDENCE_20261008.json`, PROJECT_STATE 링크, 이 이력, sim/.gitignore의 회전 전 로컬백업 제외 규칙.
- 변경: 초기 CPU480Hz→지역 활성화/주기전환→UI/정확성 수정→Hz비교→USD쓰기→정적화 철회→Nsight/CPU/원본맵 대조를 종합했다. 핵심 JSON8개를 출처SHA256과 함께 버전관리 경로에 복사해 원격 보고서 작성에 사용할 수 있게 했다. raw runs/회전 전 백업은 로컬 보존한다.
- 범위: 이번 종합 과정에서 운영 로직·물성·backend를 추가 변경하지 않았다. 최근 미커밋에는 별도 승인된 AprilTag 작업도 포함하며 보고서에서 물리 최적화와 구분한다. 맵과 팔자산은 기존 LFS로 저장한다.
- 검증: 원본 JSON8개 hash/내용 및 Markdown 내부링크 대조 PASS, Python43개 구문 PASS, 기존 전달 CSV의 CRLF를 보존한 변경공백 검사 PASS. Isaac Python에서 수확/물리/진단58개, ROS Jazzy 환경에서 AprilTag4개 PASS(skip0). 최초 검사는 테스트 import 경로 누락, 이전 진단 대역의 PhysX view 누락, Isaac 환경 OpenCV API 차이로 실패했다. import 경로/실행 환경을 맞추고 `test_teacher_diagnostic_trace.py`의 대역 view만 보완해 통과했다. 운영 소스 변경은 없다. 성능/수확 숫자는 앞선 실제 시험 기록이며 보고서 작성 중 재측정값으로 표현하지 않는다. 최종 커밋·원격 반영 상태는 Git 결과를 따른다.
- 복원: 이 종합자료/링크/백업 제외 규칙만 필요에 따라 역적용한다. 이전 변경을 통째로 reset하거나 raw 로그·복원용 USD를 삭제하지 않는다.



## SIM-SCOUT-URDF-20261013 — PDF 장착 모델 반영

- 기준 main/a393f1a, 사용자 URDF 수정 요청 및 첨부 PDF 기준. sim scout 원본/portable URDF에 기둥·상판/홀더 근사 외형·봉·D435/파이캠 TF 추가. 기존 기본 링크/물성 불변, 공통·실물 소스 변경 없음.
- 변경 전 센서/장착 없음 → D435(-49,55,595)mm/하향1도, 파이캠(-32,63,117)mm, 기둥 상단620mm. PDF A/B/C 구분 유지; 추가 질량/관성은 미정.
- 직접 검증: XML/트리/기존 노드 보존/좌표·방향 계산. ROS·Isaac·실물 미실행. 기존 USD/실행 설정은 자동 변경되지 않으며 PC 적용/원격 반영 없음.
- [상세·한계·복원](SCOUT_URDF_MOUNT_20261013.md). 패치 역적용으로 복원하며 사용자 변경이 있으면 먼저 병합.


## SIM-SCOUT-USD-20261013 — 장착 USD 및 단독/fleet 연결

- 승인: 사용자 “usd까지 반영한다음 커밋푸쉬해”. 기준 main/a393f1a. 앞선 URDF 수정본까지 함께 반영.
- 대상: scout_mount_20261013.usda/하위 .gitattributes, build_scout_mount_usd.py, scout_mount.py, run_sim.py/run_fleet.py, scout.json/scout_fleet.json, test_scout_mount_usd.py 및 관련 상태·결정/보고서.
- 전후: URDF만 수정 → 실제 sim 진입점에서 기존 base_link에 장착 USD 참조·D435 transform 적용·파이캠/PDF TF 발행. 기존 Camera 광학/구동 joint/본체 질량 유지. 공통·실물 변경 없음.
- 직접 검사: OpenUSD26.8 합성 stage4PASS(비활성 prim 검증 결함 수정 후 통과), Python 구문PASS. 원본 농장 LFS binary 미확보로 실제 농장 합성/Isaac/PhysX/ROS/주행은 미검증.
- 복원: scout_mount_asset 설정 제거 및 재시작. 원본 USD는 세션 방식으로 보존. [상세·한계](SCOUT_URDF_MOUNT_20261013.md) 최상단 절을 따른다. 원격 게시 승인은 받았으며 최종 Git ref 결과로 게시 여부 확인.

## SIM-APRILTAG-HANDOFF-20261013 — 인수 주행 병합과 시뮬 영상 보정 연결

- 기준: `main/a393f1a` + 기존 사용자 미커밋 변경. 전달 `bf10fcd`, SHA-256 120개 일치. 승인 근거는 이번 사용자의 “새로 받은 주행 기준으로 업데이트하고 변경내용 적용하고 시뮬레이션 추가 조치” 요청이다. 공통 통합도 이 요청 범위로 적용했다.
- 대상: 공통 `farm_navigation`, `farm_bringup`, `harvest_robot`, 신규 `farm_tag_localization`/`farm_tag_amcl`; 전달 실물 config/tools/문서; sim 설정·영상 어댑터·launch·생성기·관련 시험. 상세는 [통합 변경 기록](../../docs/changes/APRILTAG_HANDOFF_INTEGRATION_20261013.md), [실행 안내](APRILTAG_INTEGRATION_20261013.md).
- 전후: graph_only 수확→graph 기반 진입/직선 작업/이탈 및 정방향 중간 출발; 태그 배치/가상 영상만 존재→정류·실제 검출·구간별 등록·공통 관측기·scan-sync AMCL 연결. 기존 RPP/오른팔 정차선/Teacher 및 ARRIVAL_THEN_ARM 보존. wire Section 추가 없이 sim 목표 좌표·방향으로 유일한 구간을 선택한다.
- 반복 ID는 `(section_id, family, tag_id)`로 등록하고 진입/이탈 중에는 적용하지 않는다. 실제 ROS 영상 검사로 발견한 detector QoS 불일치와 태그 x/z축 반전을 수정했다. 검출 신뢰도나 보정 pose를 정답으로 대체하지 않았다.
- 실물 영향: 담당자 전달 주행/설정 반영, 실물은 도착 전용·TF 복구 OFF 유지. 반복 구간 기능은 기존 고유 ID와 호환하고 USB 자동 실행은 real에 한정한다. 시스템 udev/sysctl/드라이버 설치·로봇 재배포 없음.
- 검증: 공통5+sim3 패키지 빌드, 공통123/태그65/시뮬23 회귀검사(평행 접근7개 중복), 경로371개, 실제 ROS AMCL22개 PASS. 실제 launch 기동 READY·기동 오류 없음·종료0. 실제 Isaac 새 정차 렌더240태그/1280×720·공유메모리 확인 후 Kit 종료 대기 timeout124. 해당 영상의 genuine ROS 검출/Journal/공통 관측기 연결10/10프레임 확인(ID104 기준 약1.44mm/0.171°); 한 장면 결과다. 영상 재생 후 upstream 정류/검출기 SIGINT 종료 -11 미해결(전달본 기존 이슈), 모든 시험 프로세스 정리. 전체 주행/팔 E2E 미실행.
- 환경: detector/image_proc 시스템 설치는 관리자 암호로 미완료; 임시 ROS 바이너리를 `sim/runs/apriltag_integration_20261013/deps/`에 풀어 실제 시험했다. 설치 명령과 재빌드/보정 ON 방법은 실행 안내 참조. 기본 보정 OFF.
- 로그·초기 실패·수정 후 결과: `sim/runs/apriltag_integration_20261013/`. 버전관리용 [검증 요약](changes/APRILTAG_VALIDATION_20261013.json), 변경 파일 패치 및 적용 명령은 [실행 안내](APRILTAG_INTEGRATION_20261013.md)에 연결했다. 기존 사용자 URDF/문서·다른 경로 삭제 상태 보존. 세 공용 문서에는 담당자 과거 이력을 요약/연결했고 전면 덮어쓰지 않았다.
- 복원: 이번 파일만 적용 전 사본/시작 커밋과 비교해 복원 후 재빌드한다. 기존 수정 문서/실물 설정 사본은 위 로그 폴더 `before/`. 보정만 OFF할 경우 tag_correction:=false이며 단계별 주행은 유지된다. 미커밋·원격 미반영, commit/push 미수행.

## SIM-SCOUT-MERGE-20261013 — 62a80ed 로컬 병합 및 장착 TF 수신 수정

- 승인: 사용자 `62a80ed`의 예찰 URDF/USD 반영 요청, 후속 “아니요, main에 예찰 변경만 반영”. 원격 heads 직접 조회로62a80ed=main 확인. 로컬 main a393f1a→62a80ed fast-forward; 어떤 브랜치도 삭제하지 않았다.
- 반영: 기존 URDF 두 개는 이미 같았고, 누락된 USD 장착 자산/단독·fleet 실행/카메라/TF 설정과 검사를 병합했다. 공용 문서3개 충돌은 양쪽 이력을 보존했다. 미커밋 AprilTag 소스·설정은 해시로 보존을 확인했고 기존 삭제55개 상태도 유지했다.
- 추가 수정: `sim/ros_ws/src/farm_sim_devices/farm_sim_devices/ros_adapter.py`, `sim/tests/test_adapter_tf_contract.py`. 장착이 켜진 예찰의 정적 TF 기대값3→7개. 정확한 부모/자식/namespace를 검증하며 누락·중복·미등록 프레임은 거절한다. 이 수정 없이는 새 예찰 상태 패킷 전체가 무시된다. 공통·실물·수확 설정 영향 없음.
- 검증: 수신 계약11/진입점2/OpenUSD4 PASS, sim3패키지 재빌드 PASS. 실제 농장 binary USD에서 세션 장착·D435 렌즈 위치/방향·추가 TF4개·원본 보존 확인. 실제 Kit/PhysX/주행·ROS 전체 E2E는 이번 미실행.
- 로그·적용 전 사본: `sim/runs/scout_merge_20261013/`. 실행 중인 sim에는 소급되지 않으므로 새 overlay source 및 재시작 필요. 원격 main에 이미 있던 커밋만 가져왔고 새 commit/push 없음; 추가 호환 수정은 기존 AprilTag 작업과 함께 미커밋.
- 복원: 추가 수신 수정은 두 파일만 역적용한다. 장착 비활성화는 두 scout 프로파일의 `scout_mount_asset` 선택 해제 후 재시작한다. 이번 Git 병합을 되돌리려고 기존 미커밋 작업을 reset/clean하지 않는다.

- 원본 정리(2026-10-13): 전달 폴더 120개 파일의 반영 대상 존재, SHA-256 및 Git `bf10fcd` 원본 일치, 실행 symlink 의존성 없음을 확인하고 사용자 요청으로 전달 폴더를 삭제했다. `sim/runs/apriltag_integration_20261013/SOURCE_HANDOFF.md`와 `source_cleanup.json` 보존.
- 주행 시험: `sim/runs/navigation_smoke_20261013/harvest_runtime.yaml`과 관련 파일을 준비했다. 기존 수확 설정에서 완료 정책만 `ARRIVAL_ONLY_NO_HARVEST`로 변경하여 팔 동작 없이 시험한다. 운영 기본 `ARRIVAL_THEN_ARM` 유지. 환경 로딩·수확 launch 조립(태그 OFF)·SEC01 Goal 생성 확인, 실제 주행은 실행하지 않았다. 태그 ON 실행 전 시스템 `apriltag_ros`/`image_proc` 설치가 필요하다.


### 수확 진입 경계 오류 — 2026-10-13 (공통 변경 승인 대기)

- 사용자 시험 `smoke_7616aba8822b` 로그에서 SEC01 진입 `(-6.015,10.7)`에 실제 `(-6.01767356,10.71018813)`로 도착했다. 오차 0.010533m는 허용 0.02m 이내라 ARRIVED지만, `CorridorNavigator._plan_current()`의 시작점 앞 무오차 경계 검사에서 WINDOW_MOVE가 즉시 실패했다. 태그 보정의 원인 여부를 추측하지 않으며 확인된 직접 원인은 두 판정 기준의 불일치다.
- 최소 제안: `robot/ros_ws/src/harvest_robot/harvest_robot/corridor_navigation.py`의 작업 경로 시작 검사에서 기존 구간 내부 또는 진입점 반경 `arrival_tolerance_m` 이내를 허용한다. 목표 구간, 종료 경계, 전방·횡오차·방향 검사, 진입 생략 조건은 유지한다. 양 환경 공통 영향 때문에 AGENTS의 명시 확인 전 실제 소스에는 적용하지 않았다.
- 산출물: `sim/runs/corridor_entry_review_20261013/proposal.patch`, `corridor_navigation.py.proposed`, `verification.json`. 원래 실패를 실제 기록 좌표로 재현했고 수정안의 정상 연결 및 2cm 초과/횡오차/끝점 초과/후방 목표/방향 오류 거절·진입 생략 조건 유지 8개 오프라인 확인을 통과했다. 실제 ROS/Isaac 재주행은 하지 않았다.
- 승인 후 적용·관련 회귀검사·빌드·재시작 후 동일 목표 재시험이 다음 단계다. 실행 코드/설정 변경 없음, commit/push 없음. 제안 취소 시 산출물만 폐기하면 된다.


## SIM-SHARED-TAG-20261013 — 예찰 PiCam과 공통 주행 보정

- 승인: 사용자가 “예찰도 apriltag 기준으로 주행보정 … 동일 개념의 주행 시스템을 공유”하도록 요청했다. 공통 코드 변경을 포함한 직접 승인 범위에서 적용했다. 기준 `main/62a80ed`, 기존 미커밋 변경 보존, 이번 commit/push 없음.
- 공통 연결: `farm_navigation/tag_control.py`에 보정 권한 신호를 두고 두 로봇이 재사용한다. 수확 import 호환 경로 유지. ScoutNode의 `tag_correction`과 관측 이동 상태를 연결해 진입 완료 후 해당 구역 이동에서만 활성화하고 접근/이탈/정지 관측·완료/실패/취소 때 해제한다. 기존 공통 Navigator/Nav2, 업무 FSM과 관제 메시지는 유지한다.
- 시뮬 센서: 예찰 USD PiCam optical 프레임에 실제 Camera를 생성해 별도 RGB/CameraInfo/공유메모리로 연결했다. D435 과실 영상은 유지한다. 단독/fleet 모두 동작하며 장착 TF를 중복 생성하지 않는다. USD 원본 대신 세션 레이어를 사용한다.
- 시뮬 연결: `farm_sim_runtime/tag_localization.py`가 두 로봇의 정류·검출·기록을 공통 조립한다. `all.launch.py tag_correction:=true`는 선택한 예찰·수확 모두에 적용되고 두 로봇이 같은 `farm_tag_localization`/`farm_tag_amcl`을 사용한다. namespace·보정 권한·캡처 폴더는 각각 분리한다. 실행 중인 Isaac/ROS는 재시작해야 한다.
- 자산: 동일 240개 구역 태그 지도와 계산 코드를 사용한다. PiCam URDF 외부변환, 명시적인 시뮬 pinhole 광학, 약1.1m 관측 거리와 약48px 태그 조건은 예찰 프로파일로 분리했다. 실물 PiCam 교정값이 아니며 수확 자산은 기존 SHA와 일치한다.
- 확인: 공통4·시뮬3패키지 빌드, 수확82·현행 예찰 통신6·예찰 보정수명5·시뮬 태그/카메라26·공통 launch9 검사 PASS. OpenUSD 장착7검사 PASS. 구형 `tests/test_scout_state_flow.py`는 30개 중20오류: 기존 HEAD의 `section_id` 계약에 옛 fixture가 `section_ids`를 보내는 불일치이며 이번 범위에서 변경하지 않았다.
- 실제 Isaac PiCam 1280×720 렌더·공유메모리 전달과 ROS 정류→검출→Journal→공통 관측기 5/5프레임 수신/채택을 확인했다. 초기 배치가 아니라 RGB와 함께 받은 CameraParams로 촬영 시점 좌표를 비교했다. 해당 정차 장면은 횡방향 약3.72cm·진행방향7.16cm·yaw3.41° 오차로, 시험의 축별5cm 정확도 조건을 **실패**했다. 검출 해상도 축소 해제(decimate1)로 개선되지 않았다. 작은 정면 태그의 자세 추정 민감도가 확인됐으나 이동 중 성능·전체 원인은 추가 검증 대상이다. 정밀 주행 성공으로 기록하지 않는다.
- 종료 제한: Isaac은 영상/메타데이터 저장 후 종료 대기로 timeout124. ROS 검출기도 SIGINT 시 -11 또는 종료 대기로 시험 소유 프로세스만 강제 종료한 기록이 있다. 정상 종료 시험으로 기록하지 않는다. 실물·폐루프 실제 주행은 실행하지 않았다.
- 기록: `sim/runs/shared_tag_navigation_20261013/`의 빌드/회귀 로그, 초기·촬영시점 렌더, ROS replay 결과 및 [검증 요약](changes/SHARED_TAG_NAVIGATION_20261013.json). 실행 안내는 [시뮬 통합 안내](APRILTAG_INTEGRATION_20261013.md).
- 남은 작업: 예찰 실제 카메라 교정 및 관측 모델/정면 소형 태그 정확도 개선, 이동 중 보정 평가. 기존 수확 진입 허용오차 수정은 여전히 별도 제안 상태이며 이번 변경에 적용하지 않았다.

- 복원: 이번 변경 파일에서 공통 신호 이동·예찰 연결·추가 센서/프로파일만 되돌린 후 빌드/재시작한다. 단순 보정 OFF 비교는 `tag_correction:=false`로 가능하며 이전 인수/예찰 장착 변경 전체를 reset하지 않는다.


## SIM-HARVEST-START-AUDIT-20261013 — 원본 대조·수정 초안 보류

- 사용자 추가 확인 요청: 실물 성공본은 별도 출발 조건을 제거했다고 전달받았으며, 시뮬 중단 직전에는 SEC01 태그가 카메라에 보이지 않았음. 최신 실패 `smoke_7c647822d87c`와 전달 커밋 `bf10fcd`를 대조했다. 원격 재조회·실물 접속은 하지 않았다.
- 원본 확인: `corridor_navigation.py`와 공통 `parallel_approach.py`는 전달 원본과 바이트 일치. 원본에도 구간 내부·방향·횡오차·전방 목표 검사가 남아 있다. 태그 응답/READY/검출을 기다리지 않는 동작은 원본과 현재 모두 같다. 담당자가 전달 뒤 별도 변경한 실물 실행본이 있는지는 미확인이다.
- 통합 설정 차이: 실물은 작업 허용구간10→14, 진입11번으로 시작 경계보다1m 안쪽이다. 시뮬은 진입20102번을 작업 허용구간 시작점에도 사용했다. 이 때문에 진입 도착 오차 범위의 위치가 구간 밖으로 분류된다. 조건 제거 코드 누락으로 확인된 문제가 아니라 시뮬 구간 설정이 원본의 전제를 재현하지 못한 문제다. 최근 도착 기록상 시작점 직전5.985mm·횡오차6.030mm·방향0.648°였다(실패 판정 시각보다 약41ms 앞의 도착 기록).
- 실제 구조: 진입과 작업 모두 FollowPath 경로를 사용하고 태그 관측이 AMCL 위치를 보정한다. 작업 단계 전환은 태그 검출 성공을 기다리지 않는다. 이번 실패는 작업 경로 생성 중 발생했고 태그 보정 요청/적용은0회다.
- 영상 확인: 검출 journal `sim/runs/apriltag/9462dccc81d049669fbb3a35950747d2/`에서 도착 시각83.354171s 전후1초의8프레임 모두 검출0. 앞선 접근 중7회 검출은 구역 미확정으로 제외됐다. 반복ID이므로 해당 검출을 SEC01로 단정하지 않는다.
- 기하 확인: SEC01 수확 진입y10.7, bed시작y10.0, 첫태그y9.968로 첫태그는 진행방향0.732m 앞이다. 측면 카메라의1280폭 화면에 첫태그 중심은 진입목표에서u3509px, 도착기록 위치에서u3363px로 시야 밖. 계획 직선 기준 약0.598m 이동 후 전체 태그가 화면에, 약0.662m 후 보정ROI에 들어온다. 이는 정적 투영이며 실제 RGB/가림/월드 정답 재렌더 검증은 아니다.
- 임시2cm 진행축 허용 수정은5개 신규 검사·수확87개·sim설정3개 및 빌드를 통과했으나, 사용자 원본 대조 요청에 따라 `sim/runs/corridor_entry_fix_20261013/`에 제안 패치/검사를 보관하고 소스·운영/시험 설정을 적용 전으로 복원했다. 출발 조건 완화는 현재 적용하지 않았다.
- 권장 후속: 원본처럼 진입점이 작업 허용구간 안에 놓이도록 시뮬 구간 정의를 먼저 맞춘다(SEC01은 기존 그래프의 진입 전 직선노드9002가 후보). 태그 관측 전 약0.6m 구간의 의미와 작업 시작 시 태그 가시성 요구는 별도로 정해야 한다. 현재 진입점에 단순 검출대기를 넣으면 태그가 시야 밖이라 대기 상태에 머물 수 있다.
- 근거: `sim/runs/harvest_abort_audit_20261013/{source_and_detection_audit.json,camera_geometry.json,camera_geometry.py}`. 운영 코드/설정의 최종 변경 없음, 문서/검사 산출물만 추가. 실물·시뮬 주행 명령 및 commit/push 없음.

- 승인 범위는 원본/영상 기록 확인과 직전 초안 보류다. 실제 주행 기준 추가 변경은 미적용이다. 복원할 운영 변경은 없고 산출물만 보관한다.

## SIM-HARVEST-START-ALIGN-20261013 — 실물 기준 작업 구간 적용

- 구분/승인: 시뮬 전용 설정·생성기·검사. 사용자 “실물이랑 맞춰 실물방식을 무조건 따라가”로 적용 승인. 기준 main/62a80ed 및 전달 bf10fcd, 미커밋 변경 보존.
- 대상: `sim/tools/rebuild_route_data.py`, `sim/ros_ws/src/farm_sim_config/config/harvest_task.json`, `sim/tests/test_staged_harvest_config.py`, 이동 시험용 `sim/runs/navigation_smoke_20261013/harvest_task.json`.
- 변경 전후: 이전에는 진입점=허용 시작점이라5.985mm 직전 도착도 구간 밖이었다. 기존 그래프에서 진입점에 직접 연결된 직선 직전 노드를 허용 시작으로 선택하여16구역 모두 진입점이 내부에 놓이도록 했다. SEC01은9002→20100을 허용 구간으로,20102를 진입 목표로 사용한다. 시작→진입 거리는 시뮬0.8m/1.3m(실물1m)이며 진입/이탈 목표와 그래프·좌표는 보존했다. 후보가 없거나 여러 개면 생성 실패로 처리한다.
- 실물 영향: 이번 공통·실물 코드/설정 변경 없음. 원본 구간/횡오차/각도/전방 검사를 그대로 사용한다. 태그 검출 대기 없이 작업 이동하며 유효 관측으로 보정하는 흐름도 유지한다. 임시2cm 진행축 완화 제안은 미적용이다.
- 검증: `python3 -m unittest sim.tests.test_staged_harvest_config -v` 6개 PASS. 두 실패 로그의 실제 도착 좌표를 원본 코드에 넣었을 때 이전 설정의 오류 재현/새 설정 통과,16구역 진입 전1cm 허용과 옆 방향·각도·후진·외곽 거절 유지 확인. `python3 sim/tools/validate_route_data.py` 371개 경로 계획 PASS. `colcon build --symlink-install --packages-select farm_sim_config` PASS. 실제 Isaac/ROS 재주행 미실행.
- 기록/다음: `sim/runs/harvest_start_alignment_20261013/`의 로그 및 비교 그림. 수확 launch 재시작 후 같은 SEC01 Goal로 시험한다. 진입에서 태그가 보이지 않는 기존 배치는 유지하므로 작업 이동 중 검출·보정 여부는 별도 확인한다. 문서 갱신 완료, commit/push 없음.
- 복원: 생성기의 이번 직전 노드 선택 부분을 제거하고 두 설정의 각 `work_corridor_nodes` 첫 원소만 해당 `entry_node`로 되돌린다. 팔 완료 정책·기존 태그/예찰 변경·다른 미커밋 파일은 보존한다.

## SIM-DRIVE-PERFORMANCE-AUDIT-20261013 — 약17FPS 주행 원인 조사

- 구분/승인: 사용자 “프레임드랍 원인 확인하고 무슨조치 할수있는지 리스트업”에 따른 읽기 전용 조사와 문서 기록. 실행 코드/설정/물성 변경 없음, 실제 재주행·A/B계측 미실행.
- 대상:17:20 실행 fleet/session `298ffb11e69e4a8cbaba7634ba963954`의 주행·물리·태그·Kit/ROS 로그, 현재 runtime/device 소스, 이전10/8 물리 비교 기록. 호스트 GPU/프로세스 조회 시 이미 시뮬 종료 상태였다.
- 결과: RTF0.2854 및 환산17.1248FPS 확인. 물리는60Hz, 활성과실0. GPU물리·센서3개·5simHz 전체과실 평가와 태그RGB-only 미사용depth 복사가 유지된다. 비용의 존재와 이번 실행에서 각 비용의 비중은 구분하며, 일반fleet에 세부 성능로그가 없어 주병목 비중은 확정하지 않았다.
- 추가 확인: 태그 결과 예찰3.40Hz/수확4.32Hz 및 raw영상/CameraInfo 동기 경고. 전송손실/소비지연/원본센서속도 분리 필요. 태그 저널은 영상파일을 저장하지 않는다.
- 후보/영향: CPU물리 비교(주행·접촉 회귀), 미사용 센서 실제렌더 중지와 뷰포트 축소(태그입력 유지), 평가 snapshot 필요 시 갱신, RGB-only 버퍼 낭비 제거, 영상 전달 계측. 카메라fps 또는 tag_correction만 낮춰서는 렌더 부하가 비례 감소하지 않는다. 태그 해상도·충돌/물리 정밀도 완화는 우선안에서 제외한다.
- 상세/산출물: PROJECT_STATE §41, `sim/runs/drive_performance_audit_20261013/evidence.json`. 실물 영향 없음. 되돌릴 운영 변경 없음. 문서 갱신, commit/push 없음.


## SIM-DRIVE-PERFORMANCE-20261014 — 우선순위 성능 조치

- 구분/승인: 사용자 성능 조치 제안 후 “우선순위대로 진행해”. 시뮬 실행/센서 및 제안한 공통 RGB-only 공유메모리 최적화 범위. main/62a80ed 위 미커밋 변경 보존, commit/push 없음.
- 대상: runtime `run_fleet.py`, `run_sim.py`, `launch/{all,isaac}.launch.py`; devices `camera_sim.py`, `camera_ros.py`; 공통 `rgbd_shm.py`; `sim/tests/test_rgb_only_transport.py`.
- 전후: 기존 프로파일만 사용하던 물리에 CPU/GPU 선택 추가(기본 profile 보존), 일반 fleet 성능 기록 추가, headless viewport 갱신 제외. RGB-only는 NaN 깊이 버퍼를 재사용하고 ROS RGB 발행에서 깊이 복사를 생략한다. 기존 RGB-D ABI/기본 API 유지, 실물 설정/주행 업무 정책 영향 없음.
- 검증: 관련36검사·3패키지 빌드·launch 인자 조회 PASS. 직접 Isaac 짧은 주행 GPU17.66→CPU29.05FPS, CPU+headless36.23FPS; 정상3카메라 프레임 유지. 각14sim초/조건1회, ROS/Nav2 제외 비교다. 종료 대기로 -15 정리, 팔 정책/접촉 검증 미실행. 상세 PROJECT_STATE §42 및 `sim/docs/changes/DRIVE_PERFORMANCE_20261014.json`.
- 미적용: 예찰D435 중지는34.73FPS 비교만 수행. 렌더 예약은 영상 미발행으로 철회. 평가 snapshot/충돌체 단순화 보류. 태그 화질·주기·출발 판정 그대로다.
- 기록: `sim/runs/drive_optimization_20261014/`의 before 원본·벤치 manifest/stdout/frames·빌드/검사 로그. 복원은 physics_device:=profile 사용 및 이번 성능 선택/로그/headless 설정과 RGB-only 변경만 역적용한다. 같은 파일의 기존 AprilTag 변경을 함께 되돌리지 않는다.

- 후속 실제 Nav2: CPU28.26FPS이나 진입 방향0.1069rad>0.05로 ABORTED(위치8.7mm 정상). 같은 GPU 조건17.38FPS에서 SEC01 진입·작업 이동 SUCCEEDED, 실제 AprilTag 보정4회. CPU 기본 전환 보류, 도착 기준 유지. 둘 다 팔OFF/expected0이며 예찰은 정차했다. 영상/CameraInfo 동기 경고 잔존. `e2e_cpu/`, `e2e_gpu/`; 추가 런치 검사5개 PASS. 이 결과는 이전 §40의 미실행 재주행 중 해당 SEC01 수확 이동을 보완한다.

- GPU 유지+headless 추가 비교:18.64FPS(화면ON17.66), 센서3개 프레임 유지. 물리 변경 없이 얻는 개선은 약5.5%로 제한적이다. 현재 권장 선택은 기존 물리 유지와 필요할 때 `rviz:=false headless:=true`; CPU는 주행 차이 원인 검증 후 판단한다. 종료 시 기존 tag/image_proc -11 및 Isaac SIGTERM(-15) 문제가 남아 있어 ROS launch 부모0을 모든 자식 정상 종료로 해석하지 않는다.


## SIM-DRIVE-BACKEND-REPEAT-20261014 — CPU/GPU 주행 재현성 검사

- 승인/범위: 사용자 CPU/GPU 결과가 우연인지 확인 요청. 운영 소스·설정·실물 영향 없음. 반복 도구/로그는 sim/runs 안에 작성, 기존 미커밋 변경 보존.
- 시험: 기존 조건에서 GPU→CPU→CPU→GPU 각2회 신규 실행. SEC01 fraction0.313/expected0/팔OFF, 동일 센서/제어/허용치 유지. Goal 이전 액션 발견 실패1회는 별도 제외 보존하고 신규 도메인으로 재실행했다.
- 결과: 신규는 두 backend 모두1성공/1실패. 기존 포함 CPU1/3·GPU2/3 성공. CPU 방향6.124°/6.504° 실패뿐 아니라 GPU7.314° 실패도 재현됐다. 실제 차체 과회전이 기록돼 CPU 고유 실패라는 해석은 철회한다. 성능 차이는 CPU27.76~28.26/GPU17.12~17.38FPS로 유지. 신규 성공 주행에서 GPU 태그 보정7회, CPU11회.
- 해석/제한: 3회씩으로 성공률 차이·동등성 확정 불가. 물리 backend와 실행 속도/ROS 타이밍이 함께 달라 순수 물리 원인 분리는 미완료다. 공통 정렬·정지 응답을 먼저 조사하며 도착 허용치는 유지한다. 기본 backend 변경 없음, 팔 수확 검증 없음.
- 산출물: PROJECT_STATE §43, sim/docs/changes/DRIVE_BACKEND_REPEAT_20261014.json, sim/runs/drive_repeat_20261014/. 시험 소유 프로세스 종료 확인. 부모 launch0과 자식 종료 -11/-15는 별개다. 되돌릴 운영 변경 없음. commit/push 없음.


## SIM-PROGRESS-105-DIAGNOSIS-20261015 — 반복 중단 로그 진단

- 사용자 반복105 보고에 따라 기존 예찰 SEC02 및 수확 TASK005 로그를 분석했다. 기준 main/66b8287. 운영 코드·설정과 실행 프로세스, 실물 영향 없음.
- 예찰의 회전 중 위치 진행 제한과 수확의 명령/휠 응답 진동을 구분했다. 원인 전체 확정이나 수정 완료가 아니다. 상세 근거·후속 검증은 PROJECT_STATE §53 및 changes/PROGRESS_105_DIAGNOSIS_20261015.json에 기록했다.
- 검증: 원본 JSON/JSONL 파싱 및 시간 구간 추출, 설치 FollowPath 코드 정의와 현재 공통 설정 대조. 새 Isaac/실물 시험 없음. 공통 변경 승인 요청 전 진단 단계다.
- 복원: 이번 문서 항목과 신규 진단 JSON만 제거한다. commit/push 없음.


## COMMON-ROTATION-PROGRESS-20261015 — 예찰·수확 회전 진행 판정

- 승인: 사용자 “공통코드면 수정해 회전도 진행 판정에 포함돼야지”. 대상 robot/config/navigation/{scout,harvest}_nav2.yaml. 공통 SimpleProgressChecker→PoseProgressChecker, 각도 문턱0.1rad 추가. 거리/시간/도착/속도 유지. 실물·시뮬에 같은 기준 적용.
- 검증: 설치 Nav2 검사기 직접 호출92 assertions 및 기존 공통 설정pytest6개 PASS. 환경4개 최종값/나머지 설정 불변 PASS. 상세 PROJECT_STATE §54, sim/runs/progress_checker_20261015/. 신규 Isaac/실물 주행 및 실행 프로세스 재시작은 미실행.
- 적용: 해당 Nav2 launch 재시작 후 반영. 수확 휠 응답 진동은 별개로 남는다. 복원은 두 YAML의 SimpleProgressChecker 복구 및 required_movement_angle/주석 제거. 사용자 후속 지시로 이 공통 수정과 해당 기록의 커밋·푸시를 승인받았다.


## SIM-HARVEST-PROGRESS-105-20261015 — 회전 판정 수정 후 수확 정체 분석

- 요청: 최신 수확105 원인 분석. main/8cfcc3f 기준 기존로그만 읽고 운영 코드/설정/실행은 유지했다. 실물 영향 없음.
- 최신 두 SEC02 SECTION_APPROACH 실패는 거의 같은 위치의 실제 정체다. PoseProgressChecker 로드 확인, 신선한 명령 수신/거절0, 최신 태그 보정0회, 휠 PI 보정 포화와 미미한 차체/odom 변화를 확인했다. 물리 접촉/마찰/제어 진동 인과는 추가 계측이 필요하다.
- 상세/검증: PROJECT_STATE §55, changes/HARVEST_PROGRESS_105_20261015.json, sim/runs/harvest_progress_105_20261015/analyze.py. 원본로그 파싱/통계와 실행설정 대조만 수행. 신규 주행/수정/재시작 없음. 이번 기록/JSON 제거로 복원 가능. 미커밋/푸시 없음.


## SIM-HARVEST-CONTACT-ROOT-CAUSE-20261015 — 수확105 접촉 원인 확인

- 사용자 “원인 찾아내”에 따라 격리 CPU 물리 시험5개를 수행했다. 운영 코드/설정/자산과 기존 사용자 실행은 유지했다. 실물 영향 없음.
- 최신SEC02 정체는 왼팔 손목 카메라와 Bed_04/Pepper_0003_yellow 접촉으로 재현됐다. 비수확중 과실은kinematic/충돌유지다. 해당 collider만 시험 씬에서 제외하면 동일 저속회전 응답−0.304°→−22.727°, 직진 방향변화20.789°→−0.327°. 카메라 mount 자체관통도 확인해 별도 역대조했다.
- 검증/한계: 유효5개22sim초 완료, 최초mount 시험은USD instance proxy 편집 오류로 무효. 일부종료SIGTERM−15. Nav2 E2E/실물/운영수정은 미실행. 상세 PROJECT_STATE §56, changes/HARVEST_CONTACT_ROOT_CAUSE_20261015.json, sim/runs/harvest_root_cause_20261015/. 이번기록·시험자료만 제거해 복원. 미커밋/푸시 없음.

## 2026-10-15 — 양팔 접힘 주행, 오른팔 작업 전개/복귀

- 구분/승인: 시뮬 전용 구현. 사용자 “양팔: 주행 중 접고 수확할 때 오른팔만 펼침”. 기준 main/8cfcc3f, 기존 변경 보존. 실물·공통 Nav2/미션 수정 없음. 커밋/푸시 및 사용자 실행 재시작 없음.
- 대상: farm_sim_config/config/robotarm_physics.json; farm_sim_runtime/{robotarm_asset_setup,harvest_physics,run_fleet}.py; farm_sim_devices/{teacher_device,arm_session}.py; tests/{test_arm_session,test_robotarm_asset_setup}.py. 상태/결정: PROJECT_STATE §57, D-034.
- 전후/이유: 왼팔 돌출 및 오른팔 작업 HOME으로 주행하던 방식에서 양팔 별도 접힘 자세로 시작한다. 정차→오른팔 전개→기존 작업 HOME에서 수확→오른팔 접기→양팔 실측 접힘/정지 확인 뒤 주행한다. 취소/접힘 실패 시 차체 잠금을 유지한다. 작업 HOME/정책·과실별 복귀·실물은 유지한다.
- 관련 물리: 왼팔 mount–wrist 인접 CAD 관통만 pair filtering하며 외부 충돌을 유지한다. 왼팔 유지 drive도 같은 오른팔 서보의 기존 SI 값으로 맞춰 접힘 자세의 속도 진동을 없앤다. 초기 더 깊은 접힘 후보는 팔 자체 접촉 때문에 제외했다.
- 검증: 오프라인 회귀45 PASS, 설치 USD/PhysX 정적4 PASS. 실제 CPU transition_v2는 전개5.9초/접기5.95초 및 정지 후SUCCESS. travel_final은 문제 접근 구간 직진1.009m·방향 변화−0.041°,저속 회전−13.679°; 팔 접촉 없음, 주행 중 접힘 판정 누락0회. 실제 수확 후보는 빈 목록으로 전환만 시험했으며 Nav2 전체 미션/과실 수확 E2E/실물은 미실행.22sim초 완료 시험은 앱 종료 지연으로SIGTERM 정리.
- 근거/적용/복원: docs/changes/HARVEST_ARM_TRAVEL_20261015.json 및 runs/arm_stow_20261015/. 다음 Isaac 시작 때 반영된다. 이번8개 파일의 diff만 되돌리면 이전 동작이다. travel_pose 미설정 프로파일은 기존 HOME 방식과 호환된다.

## 2026-10-15 — 박스 간섭 가능한 낮은 열매98개와 커넥터 Z 상향

- 승인/범위: 사용자 요청으로 `assets/envs/output/farm_with_plants_v5.usd`의 낮은 과실·대응 커넥터만 수정. 공통/실물·박스·충돌 설정·기존 팔 코드는 변경 없음. 기준8cfcc3f의 기존 미커밋 작업 보존.
- 변경 전후: 박스 collider 상단0.7013m와 과실 하단 offset−0.0375m,5cm 여유에서 root 최저0.79m 산정. 총288개 중98개를0.79~1.0792028165m 범위로 배정하고 커넥터도 같은ΔZ 이동. 나머지190개, 모든X/Y·회전·scale·ID·mesh 보존. 새 과실 간 AABB 겹침을 피하는 높이를 선택했다.
- 검증: 실제 runtime collider 전체의 박스 위 간격 최소5.3501cm, 신규 과실 AABB 겹침0. 씬의 변경 속성294개가 허용된 Z 이동 속성뿐임을 확인. 실제CPU22sim초에서 이전 박스 간섭 구간 직진 통과 및 박스–과실 접촉0. 기존 높은 열매와 팔의 초기 접촉은 잔존하며 전체Nav2 미션은 미검증. 상세 PROJECT_STATE §58 및 docs/changes/FRUIT_BOX_CLEARANCE_20261015.json.
- 적용/복원: 씬 재로드/Isaac 재시작 필요, 기존 실행 유지 및 커밋/푸시 없음. runs/fruit_height_20261015/farm_with_plants_v5.before.usd를 원래 씬 경로에 복사하면 이번 높이 변경만 복원된다.

## 2026-10-15 — 최신 수확 Goal timeout 진단

- 사용자 응답시간 초과 확인 요청. 코드·설정 변경 없이 최신 로그 분석만 수행했다. 수확 시작300실시간초 후 공통 Nav2Client가 결과 대기 제한으로 취소한 것이며105가 아니다.
- 시뮬 속도비0.4201로 약126sim초만 경과.16.535m 경로는0.1m/s에서 직선 이동만165.35sim초가 필요했다. 취소 직전 정상 전진 및 controller의 취소 응답을 확인했다.
- 근거: PROJECT_STATE §59, docs/changes/HARVEST_GOAL_TIMEOUT_20261015.json. 실행 완료 제한의 ROS 시간 기준 수정은 제안만 했으며 공통 소스/실물 영향 없음. 새 시험·재시작·커밋·푸시 없음. 이번 문서 항목만 제거하면 진단 기록 복원.

## 2026-10-15 — 승인된 공통 주행 sim/real 시계 분리

- 승인: 사용자 “sim이랑 real이랑 서로 다른 시간대를 쓰도록 조정”. 대상은 robot/ros_ws/src/farm_navigation의 nav2_client.py/navigation_types.py/새 test_nav2_execution_clock.py 및 harvest_robot/test/test_follow_work.py의 시계 더블이다. 기존 미커밋 작업 보존.
- 변경 전후: 주행 완료300초를 양쪽 모두 실시간으로 계산하던 방식에서 sim은 기존 use_sim_time의 /clock,real은 monotonic 실시간을 사용한다. 전체 TF 재시도 주행 예산도 일치시켰다. 통신/수락/준비/취소/TF 복구 제한은 실시간 유지. 실행 timeout 오류 문구 분리,sim 시계 역행 시 오류와 Goal 정리 상태 보존.
- 영향/검증: 공통 클라이언트를 쓰는 예찰·수확에 적용,실물 시간 기준은 기존과 동일. 새 설정/의존성 없음. 오프라인59 PASS(시계 전용12 포함),설치 rclpy 시계 API 및 소스 symlink 확인. 실제Isaac 전체 미션/실물 주행 미실행. 상세 PROJECT_STATE §60 및 docs/changes/NAVIGATION_EXECUTION_CLOCK_20261015.json.
- 적용/복원: 실행 중 로봇 노드 재시작 후 적용. 이번 공통 diff만 되돌리면 이전 실시간 주행 제한으로 복원된다. 기존 실행 재시작·커밋·푸시하지 않았다.


## 2026-10-16 — 수확 프레임 저하: 평가 경계 캐시와 실시간 pacing

- 사용자 승인으로 sim 전용 SceneTruth의 정적 로컬 경계를 재사용하고 현재 world 변환은 매번 반영한다. 기하 편집 시 무효화·종료 시 USD notice 해제. run_fleet은 렌더 지연 후 추가 대기를 줄이며 물리 tick을 생략하지 않는다. 일반 Action의 stage 성능 계측과 check_teacher_action --performance-log 연결도 추가했다. 실제 수확 계측으로 CPU Teacher의 Torch intra-op=1을 적용해 팔 계산 평균7.614→4.700ms, 동일 수확 구간13.38→15.55fps를 확인했다. 실제1,649관측 정책 출력 차이0.
- 고정60/20/30Hz·주변 과실 물리·모델·solver·카메라 설정·공통/실물 유지. 전체 센서 headless4sim초 비교에서20.56→26.28 렌더fps, 평가 tick평균3.831→0.657ms. 실제288개 경계 오차0, nativeUSD4+schedule4 PASS. 실제 GUI12fps의 개선 수치로 해석하지 않는다. 수확 PhysX 비용은 잔존한다.
- 실제2과실 수확 재검증/제외 후보/실패 시험/로그 및 원본 소스 복원법은 PROJECT_STATE §68. 현재 실행을 재시작하지 않았으며 다음 시작에 적용. 미커밋·원격 미반영.

- 최종 전체 센서4sim초는25.40fps, 카메라58/39/39로 원본과 동일. 실제 수확 비교3개 모두2/2·접힘·safe stop 통과. 최종 소스 관련13시험 PASS. 상세/패치: runs/performance_20261016/{harvest_summary.json,final_sensor_verification.json,performance_fix_20261016.tar.gz}.


## 2026-10-16 — D435 Student 기본 수확 Action 연결

- 사용자 “D435 Student 연결까지 진행” 승인. 기준2a397da 위 sim 전용 변경이며 공통/실물 미수정. 전달1330파일·모델/URDF/외형 SHA 검증, import 도구·원본 자산 보존, student_camera/student_session 및 student_policy 설정을 추가했다. 기본 backend=student_d435, Teacher 비교·복원/U20 후보 보존.
- 물리CPU60/정책20/촬영30Hz·기존 물성/바퀴·근처 과실 물리를 유지한다. 실제 손목 pose·보정/시각을 센서 rig에 연결하고 PhysX readback을 ack한다. 영상 목표 완전성·중력 순서, 실제 박스 연속 안착, 매 과실 접힘 및 최종 정지를 확인한다. 시뮬 truth는 정책 좌표 입력에 사용하지 않는다. Action 실시간 예산만1800/1860초로 확대.
- 직접 검증: 제공 독립 D4352/2 DONE/리셋0, 농장단일1/1·순차2/2(노랑→빨강)·매과실복귀·안전정지SUCCESS, 정책 중 ROS 취소CANCELED·성공0·차체잠금. 전체센서2sim초120physics tick 및 기존카메라29/19/19프레임. bounded SDK 종료 지연은 소유 프로세스 SIGTERM 정리.61 offline PASS. 물성 원본5layer SHA 동일, 카메라 외형 연결 전후2457물성속성 보존.
- 실패 원인/범위: global visuals 경로 차이 수정,3앱 동시 GPU OOM은 순차 시험, 확장 측정ROI의 인접 창은 기존 고정 작업 범위를 영상에 적용. 다양한 농장/전체Nav2 미션/U20다중/실물/양팔협조 미검증. 추가센서비용의 FPS 보장은 하지 않는다. 상세로그/검증/복원은 PROJECT_STATE §70 및 RUN_GUIDE의 D435 Student 절.
- 반영: 기존 GUI/ROS 미중단, 런치 재시작 후 적용. Teacher 복원 backend=teacher. 신규 commit/push 없음. 변경 파일 패치 student60_integration_20261016.tar.gz, 자산은 전달 원본 import 도구로 설치한다.

## Student 전달본 재확인 — 2026-10-19

- 사용자 `main/robotarm_1019` 최신화 요청으로 재검사. 압축 SHA256 `409633afa28bc4c05e1558a4df7f9c1ff9da95e412f4a608b1b8bc7d0c56cbec`는 기존 10/16 통합본과 동일하며, 압축 내 일반 파일 1,331개를 설치본과 대조해 차이 0개를 확인했다. 새 모델·실행기 변경이 없어 기존 D435 Student 연결을 유지한다.
- `harvest.json`의 오래된 Teacher 설명만 현재 Student 동작에 맞게 수정. 기본 backend `student_d435`, ARRIVAL_THEN_ARM, 물리60/정책20/촬영30Hz와 근처 과실 물리를 유지하며 공통/실물 변경 없음.
- 직접 검증: 설정·목표 대응·세션·물리 스케줄 37 PASS(추가 subtests 2). 동일 바이너리여서 native 수확은 재실행하지 않았으며 10/16의 실제 단일/순차 시험과 구분한다. 증거: `sim/runs/student60_20261019/receipt_verification.json`. 기존 실행 프로세스는 재시작하지 않았다. 미커밋·미푸시.
- 복원: harvest.json의 notes 설명만 이전 문구로 복구. 모델·제어 동작 변경 없음.


## HARVEST-COMMUNICATION-20261019 — 공통 인계 기반 및 ZIP 선택 적용

- 구분/승인: 공통·시뮬 설정·실물 비활성 설정·문서. 사용자 “필요한코드있으면 브랜치에서 가져오고 전달받은 zip을 적용해”; D-041, 시작 main/2a397da + Student 미커밋 상태.
- 대상/이유: 8466ac1의 공통 인계 기반13파일을 먼저 반영하고 ZIP의 수확량 집계·팔 이동 차단·Spin·Discharge를 적용. 상세 대상/근거는 PROJECT_STATE §71 및 runs/harvest_communication_20261019/receipt.json. 상태/결정/이력은 과거 스냅샷으로 덮어쓰지 않고 이번 로컬 적용 내용을 병합했다. 기존 두 시험의 노드 대역도 새 의존성에 맞췄다.
- 전후: 기존 도착→Student 수확은 유지하며 성공 증가분 누적과 실패/취소 후 접힘 미확인 이동 차단을 추가. transfer.enabled=false를 양 환경에 명시하므로 운송 요청·회전·배출은 켜지지 않는다. sim 클라이언트1860초, Student 모델/영상/물리와 기존 사용자 파일1348개 해시 보존.
- 실물 영향: 공통 런타임은 변경되지만 기존 이동 전용 정책·지도·태그·Nav2·Zenoh 설정 유지. 실물 프로파일에는 비활성 transfer 설정만 병합. 원격 브랜치의 전체 실물 설정/후속 현장 조정은 가져오지 않았다. 로봇 배포나 실물 재시험 없음.
- 검증: 최종 오프라인213 PASS(공통/Action183 + Student7 + 세션/스케줄23), 운영5패키지 빌드 성공. ROS 모의 배출4 PASS는 Fast DDS/domain207/동일 프로세스 범위이며 sandbox UDP 경고와 CycloneDDS 미설치 한계가 있다. 최초 시험/격리 빌드 실패 원인과 해결은 PROJECT_STATE §71. Isaac/운송/Jetson 전체 인계는 미실행.
- 복원: runs/harvest_communication_20261019/before.json·before/로 이번 대상만 복구하고 신규 파일만 제거한 뒤5패키지 재빌드. 기존 Student 작업을 덮어쓰거나 reset/clean하지 않는다. 실행 프로세스 재시작·commit/push 없음. 다음은 운송 측 미션/도킹·이격 이벤트 및 sim 장치 서버 연결이다.


## BASKET-LASER-20261019 — Student 성공을 두 레이저 하강 통과로 변경

- 구분/승인: 시뮬 전용 장치·설정·검사·문서. 사용자 “레이저센서 두개 … 통과하면 카운팅”; D-042.
- 대상: devices의 basket_laser.py(신규), student_session.py, arm_session.py의 안착 유지 훅; config의 student_policy.json/harvest.json; test_basket_laser.py(신규)/test_student_assignment.py; check_basket_laser.py(신규)/check_teacher_harvest.py; 현행 상태/결정/실행 문서.
- 전후/이유: 기존 박스 collider 포함·분리·양손가락 clear·0.6초 안정 대신, 배출 허가 후 익명 위→아래 통과를 한 번 집계한다. 단순 박스 좌표만으로 성공하지 않는다. 한 번 센 뒤 반동/반복 신호를 재집계하지 않고 취소 시 감지를 닫는다. 입구 통과 후 물리 잔류를 보장하지 않으며 전체 성공에는 기존 접힘·정지 확인이 별도로 필요하다.
- 실물 영향: 공통 메시지/적재 누적·실물 설정/드라이버 변경 없음. 원본 자산/vendor/모델 유지, Teacher 비교 경로의 기존 판정 유지. 실제 GPIO/PLC 센서 연결은 미구현이다.
- 검증: 오프라인61 PASS, 시뮬2패키지 빌드 PASS, PhysX 익명 낙하1회 PASS. 초기60Hz 동시 진입 누락은 후행 차단 해제 순서 검사로 수정했다. 기본 Action은 초기 영상 지연으로 ARM_LINK_LOST가 재현됐으며 운영 timeout을 늘리지 않았다. 최종 단일 과실 진단(통신/상태 감시만15초)은46.4667sim초에1회 집계,69.2667sim초 SUCCESS/안전정지 완료. 기본 설정 전체 통과나2과실 시험 통과로 해석하지 않는다. 제한시간 차이/증거는 PROJECT_STATE §72와 runs/basket_laser_20261019/verification.json을 따른다.
- 복원/다음: runs/basket_laser_20261019/before.json·before/와 task-only applied_changes.patch로 이번 대상만 복구한다. 기존 Student/통신 작업 보존, 실행 프로세스 재시작·commit/push 없음. 기본 환경 초기 영상 처리 지연 해결과 실제 센서 장착/입력 연결은 별도로 확인해야 한다.


## BASKET-PARALLEL-LASERS-20261019 — 평행3빔 영구 자산과 feedback/result 계수

- 구분/승인: 시뮬 소스·설정·URDF·USD·시험·문서. 사용자 “urdf랑 usd 전부 … 레이저 … feedback이나 result” 및 후속 진행 승인. D-043, main/2a397da + 기존 미커밋 작업 보존.
- 대상: `farm_sim_devices/{basket_laser,student_session}.py`, `farm_sim_config/config/{student_policy,harvest}.json`, 운영 URDF1개/USD base2개, `tools/{build_basket_laser_assets,check_basket_laser,check_teacher_harvest}.py`, 센서/Student/자산 시험과 현행 문서. 파일 목록은 runs/basket_parallel_lasers_20261019/before.json.
- 전후: 중앙 상하2빔의 방향 판정을 폐기하고190mm 입구를47.5mm 간격의 평행3빔으로 덮는다. 실제 배출 중 어느 빔 차단→모두 비차단50ms를 한 개로 집계하며 기존 feedback.success_count/result.harvested_count에 전달한다. USD의6개 헤드와 optical/빔은 영구 저장하며 실측 차체 pose를 따른다. 고정 센서 외 기존 자산 내용·질량·drive는 보존했다.
- 검증: 오프라인69 PASS, 실제 PhysX 낙하14 PASS, 운영USD4+base2 좌표 일치, 시뮬2패키지 빌드 PASS. 전체 Student ROS 단일 수확은46.6167sim초에1회 계수 후69.4167초 SUCCESS/안전정지, 실제 feedback0→1/result1, 모든29개 검사 통과. 진단 timeout15초 조건은 PROJECT_STATE §73 및 이번 runs/verification.json 참조. 턴 중단으로 끝나지 않은 첫 실행은 통과로 세지 않는다.
- 실물 영향/한계: 운영 모델 형상에만 센서 장착부를 추가했으며 실제 GPIO/PLC 입력·제품 규격·질량/관성·배포는 미확정. 종류·통과 방향·박스 잔류는 판정하지 않는다. 비교 Teacher 판정과 전달 모델 해시 기준 자산은 유지한다. 기본 초기 영상 지연 해결은 이번 범위가 아니다.
- 복원/다음: 이번 before.json·before/로 해당 파일만 복구하고 새 파일2개만 제거한 뒤 시뮬2패키지 재빌드. 기존 Student/통신 작업 보존, 사용자 실행 프로세스 재시작·commit/push 없음. 다음 정상 재시작 때 적용하며 실물 센서는 별도 입력 드라이버가 필요하다.

## SIM-ACTION-OUTCOME-20261020 — 실행 완료와 수확 실적 분리

- 승인: 사용자 “윈도우에 도착하고 팔이 실행이 됐고 수확을 시도했으면 일단 성공 … expected 수와 harvested 수가 다른걸로 … 판단”. 최신 의미는 DECISIONS D-045/PROJECT_STATE §77.
- 변경: `tools/run_section_campaign.py`의 ROS SUCCEEDED/result SUCCESS 외 failed_count==0 추가 조건을 제거했다. 예상량 부족/개별 수확 실패 수량만으로 정상 완료 window를 실패/재시도하지 않는다. 요청·피드백·결과의 수량은 보존한다. Student의 미션 중단/정지 미확인/주행 오류를 임의 SUCCESS로 변환하지 않는다. 현재 실행 worker는 시작 때 읽은 조건을 사용하며 다음 worker부터 새 시험 조건을 읽는다.
- 검증: `tests/test_student_assignment.py`에 원래 예상9/수확1/개별실패2의 정상 ROS SUCCESS 전달을 추가했다. assignment11·캠페인1시험, Python 컴파일·diff 확인 통과. 공통/실물/Student vendor 파일은 변경하지 않았다.
- 복원: 이번 실행기 조건과 추가 검증만 역적용한다. 실행 중인 캠페인/기존 로그는 유지한다. 미커밋·미푸시.

## HARVEST-ENDPOINT-105-20261020 — sim 끝점 추종과 위치 재접근 설정

- 승인/범위: 사용자 “원인이 … 시뮬레이션 세팅문제같은데 … 역할을 못하고” 원인 규명/해소 요청. 공통/실물/자산/물성을 수정하지 않고 sim 수확 Nav2 환경 override만 변경했다. DECISIONS D-046/PROJECT_STATE §78.
- 원래 설정: 실패44회차 진입 경로를 그대로 재현하여 목표38.12mm 안으로 들어온 뒤56.65mm로 이탈, 직진0/미세 회전 반복, sim188.48초에105를 확인했다. 일정 ±0.05rad/s 입력은 같은 실패 자세에서 실제+10.54°/-10.92° 회전했다. 따라서 이번 목표 근처105를 바퀴가 전혀 못 도는 물리 문제로 설명하지 않는다.
- 수정: `ros_ws/src/farm_sim_config/config/nav2_harvest.yaml`의 RPP/HarvestApproach/HarvestWork stateful=false. HarvestApproach/HarvestWork interpolate_curvature_after_goal=false. 경계 이탈 후 실제 끝점으로 재접근하도록 한다. 도착4cm/2.5°와 progress10cm/0.1rad/20초는 그대로다. stateful 해제만 한 비수렴 후보와 중간 동적 변경 후105도 모두 보존했다.
- 검증: 두 설정을 처음부터 적용한 동일 실제 경로1/1 SUCCEEDED/error0, 실제 예찰 연속3 window의 Nav2 직접 이동3/3 SUCCEEDED/error0. 이 window fixture에서는 station node_id 불일치로 공통 HarvestNode가 종료했으므로 공통 수확/팔 성공 검증으로 확대하지 않는다. 기존 BT5/staged config6/Action config7 =18검사 PASS와 canonical 환경 로더의 기준값 보존 확인. 후속 전체 캠페인으로 통합 검증을 계속한다.
- 자료/재개: `runs/navigation_105_20261020/comparison.json`과 각 case 원본. 이전 캠페인은 관리 중단/자료 보존 후 `runs/section_campaign_20261020_navfix`를 새 서비스에서 시작했다. 복원은 이번 nav2_harvest.yaml overrides만 제거한 뒤 시험 스택을 재시작한다. 미커밋·미푸시.


## 2026-10-20 — 최신 실물 주행 기준을 공통 설정에 반영 (D-048)

- 구분/승인: 공통·실물·시뮬 수확 주행 설정 변경. 사용자 “실물 기준으로 반영해” 승인. 운영 공통 소스는 변경하지 않는다.
- 대상: robot/config/navigation/{harvest_nav2.yaml,harvest_task.yaml}, robot/config/robots/vicpinky/nav2.yaml, sim/ros_ws/src/farm_sim_config/config/nav2_harvest.yaml; 기존 test_entry_controller.py/test_harvest_arm_geometry.py 기대값 갱신; DECISIONS/PROJECT_STATE 갱신.
- 이유/전후: bf10fcd 시점 기본값으로 남은 접근 추종40cm→10cm, local costmap5cm→2cm, footprint70×60cm→60×50cm+padding2cm, 접근 시작점 허용10cm→20cm. 최신 실물6f21119를 공통 기준으로 삼는다. D-046 sim 전용 override를 제거해 실물과 같은 RPP 옵션을 사용한다. 실물 costmap의 절대 scan 토픽도 담당자 설정과 일치시킨다.
- 실물 영향: 현재 main real의 다음 launch에 새 공통 설정 및 scan remap 입력이 반영된다. 물리 장비에 배포하거나 프로세스를 재시작하지 않았다. 지도·장치별 연결은 기존 환경을 유지한다.
- 검증: 병합 Nav2 main real↔6f21119 차이0; sim 제어/속도 동일, 환경 연결 차이14개만 허용. 접근 설정 양쪽0.2m. 관련 기존 검사39/39 통과. 최초 ROS 환경 누락 및 이전 기대값2건 실패도 로그 보존. 실제 주행/105 해소는 미검증.
- 자료/복원: sim/runs/navigation_parity_20261020/real_baseline_apply/에 이번 변경 전 파일 before.json, 비교/검사 로그, 변경분 changes.patch를 보존한다. 이번 변경만 복원할 때 해당 패치를 역적용하며 기존 Student/시험 실행기 등 다른 미커밋 작업은 보존한다.
- 실행 중 시험에는 hot reload하지 않았다. 다음 신규 launch부터 반영되므로 기존 조건 결과와 혼합하지 않는다. 후속 시험 통신은 domain13/SUBNET. 미커밋·미푸시.


## 2026-10-20 — SEC01 105의 회전 전환 원인 계측 (운영 변경 없음)

- 사용자 회전 전환 원인 확인 요청으로 기존 시험에30분 제한 읽기 전용 ROS 기록기를 추가했다. 설정·메시지·제어 코드는 변경하지 않았다.
- 17회차 W001에서105 재현. RPP는 현재 pose 시각 TF로3.94cm를 계산해 XY 도착 상태를 기억하고 전진0으로 전환. 도착 checker가 사용하는 최신 TF로 재계산하면 같은 순간5.10cm여서4cm 도착 범위 밖이었다. 현재/최신 TF 분기는 예전 stamp의 경로 끝점과 TF helper의 외삽 fallback에 연결된다.
- 실제 tf2 BufferCore 재생 및1005샘플 거리 비교로 검증했다. 도착 checker 내부 인자는 직접 로깅하지 않았으며 source+TF 재생 근거다. 10회차에 같은 상세 토픽이 있었다고 소급하지 않는다. 주행 수정/실물 재현/105 해결 완료가 아니다.
- 자료·한계·권장 공통 수정 방향은 PROJECT_STATE §83. 모든 새 스크립트/원본 로그는 sim/runs/sec01_real_baseline_20261020_164129/에 보존; 문서만 갱신, 미커밋·미푸시.


## CAMPAIGN-TERMINAL-WATCH-20261021 — 시험 재개와 임시 터미널 감시

- 승인: 사용자 시험 계속 진행 및 bash feedback/result 기록 도구 요청. 대상 tools/watch_section_campaign.sh와 PROJECT_STATE §89.
- 동작: 기존 ActionClient의 events.jsonl에서 현재/후속 시도의 goal·feedback·result를 읽어 KST로 출력하고 캠페인 terminal_feedback.log에 기록. 30초 상태 표시, 부분 줄 대기, Ctrl+C 감시만 종료. 예찰 결과의 전체 좌표는 원본에 유지한다. ROS 메시지/공통 코드/실물 영향 없음.
- 실행: 기존 캠페인 SEC07 3회차부터 재개, 성공 예찰 재사용 확인. 감독자·기록기·절전 방지 복구.
- 검증: 문법 검사, 실제 READY/GOAL/FEEDBACK 수신 기록, 임시 fixture의 result/다음 시도/부분 줄 처리 확인. 복원은 감시 도구만 제거하며 시험·원본은 유지한다. 미커밋·미푸시.


## CAMPAIGN-CPU-PHYSICS-20261021 — 연속 시험 CPU 선택 누락 복구

- 승인: 사용자 CPU 전환 유실 지적 및 복구 요청. 대상 tools/run_section_campaign.py, farm_sim_runtime/run_fleet.py, tests/test_section_campaign.py.
- 원인:47fabb5의 새 캠페인 launch가 CPU 옵션을 누락해 기존 profile의 GPU 정렬 설정을 선택. 기존 CPU 검증 조건을 새 실행 경로에 유지하지 못했다.
- 전후: 캠페인에 physics_device:=cpu 명시, manifest 기록, Isaac의 실제 GPU dynamics/broadphase readback 출력. 모든 재시도도 CPU 유지. 일반 launch/물성/센서/공통/실물 영향 없음.
- 실행/검증: 설정 변경 STOP으로 SEC07 3회차 보존 후4회차 재개. 감독자7검사 및18회 launch CPU 유지 검증, 컴파일/diff 통과. 통합 결과는 PROJECT_STATE §90의 후속 기록 참조. 복원은 해당 옵션/진단 출력/검사만 역적용. 미커밋·미푸시.

- CPU 실배포 확인: SEC07_attempt_0004 stack.log에서 [physics_device] requested=cpu, gpu_dynamics=false, broadphase=MBP를 직접 확인했다. 성능 개선 폭/CPU 수확 완주 결과는 아직 측정 전이다.


## STUDENT-CAMERA-PERFORMANCE-20261021 — 전처리·현재 pose 렌더 공유

- 승인/범위: 사용자 가능한 카메라 성능 개선 요청. sim/farm_sim_devices의 student_camera.py/student_session.py, sim/farm_sim_runtime/run_fleet.py, sim 전달 자산의 student60_mission_session.py 및 관련 검사. 공통/실물 운영 코드 변경 없음. 기준/상세 PROJECT_STATE §91.
- 원인/변경: 정차 촬영97.4ms 중 깊이 정렬39.9ms와 리맵20.7ms가 컸다. 이미 전달된 CPU 컴파일 가속기를 warmup 후 선택적으로 사용하고, 불필요한 overlay 생성을 생략한다. RGBA를 직접 리맵한 뒤 동일 RGB를 반환한다. 물리 직후 현재 카메라 pose를 준비해 같은 시각의 일반 render를 첫 pass로 공유하며 총2pass를 유지한다. 재사용 불가 시 기존2pass, 오류는 기존 안전 정지 경로.
- 보존: CPU60Hz·촬영30Hz·정책20Hz, 원본 영상 크기/K/실측 pose/깊이 z-buffer·invalid mask, 검출·학습 가중치, 기존 Action 판정. MissionCameraSession의 새 processor 인자는 기본None으로 기존 사용자 경로 유지. 새 의존성 설치 없음.
- 검증: 기존 Student+새 전처리/시각/오류 회귀28, physics4, fleet2, vendor14 PASS. 실제 깊이80뷰와 비전 기록12개 일치. 동일 정차 카메라165촬영의 전체 frame69.7→41.3ms, RTF0.239→0.403. 실제 수확/다른 센서 부하에서의 성능은 별도. 공유 render 시간이 다른 계측 항목으로 옮겨가는 점을 명시한다.
- 기각: renderer 끄기/켜기는163.5ms로 악화해 제외. RGB/IR의 두 pass 필요성을 확인해 1pass 축소는 적용하지 않는다.
- 실행/복원: SEC07 4회차를 설정 개선 STOP으로 보존하고 격리 실제 ROS 팔 Action 확인 중. 자료 runs/camera_optimization_20261021. 완료 후 성공 예찰로 SEC07 수확 재개. 복원은 이번 카메라/processor/계측 diff만 역적용하며 CPU/캐시/주행 수정 유지. 미커밋·미푸시.

- 실검증 완료: 실제 ROS 팔 Action 29개 검증 항목 PASS, result SUCCESS/harvested1/failed0/safe_stopped=true, sim71.433초 완료. 운영 timeout 변경 없음. SDK 자연 종료0/process_exit, exception 없음. 수확 중 RTF0.2746(1sim초=3.64wall초), 복귀 RTF0.3765(2.66wall초). 단일 로봇·Nav2 없는 검증 조건이므로 기존 다중 로봇 캠페인과 동일 조건의 배속 비교는 아니다.

- 재배포 확인: SEC07_attempt_0005에서 physics_device requested=cpu/gpu_dynamics=false/broadphase=MBP 및 student_camera geometry backend=compiled_cpu를 직접 확인했다. 기존 예찰 재사용, Domain13/SUBNET·완료 SEC01~06 보존. 최종 소스 사본/해시는 runs/camera_optimization_20261021/applied 및 verification.json에 기록한다.

- 최종 연속 시험 확인(11:46 KST): SEC07 5회차는 수확 controller_server configure 응답 timeout 로그와 함께 Nav2 준비300초 실패로 원본 보존했다. 기존 감독자가 전체 스택을 자동 재시작했고 SEC07_attempt_0006은11:46:52 기존 예찰8window로 W001 Goal/feedback을 수신해 RUNNING/harvest다. 준비 오류 원인을 카메라 개선이나 DDS로 단정하지 않는다. CPU/compiled_cpu 설정 유지, 이후 SEC16까지 감독을 계속한다.


### 2026-10-21 14:12 KST SEC10 W001 접근 주행 전체 시간 초과

- 사용자 방금 NAV 실패 원인 확인 요청. 운영 변경 없이 원본과 공통 실행 경로를 분석했다. SEC07~09는 성공 완료했고 SEC10 1회차 W001의 SECTION_APPROACH에서 실패, 팔 SKIPPED다.
- 원인: 경로27.535m/희망속도0.1m/s로 직진만275.35초 필요. 실제 제자리회전 명령32.83sim초/감속48.78sim초가 더해져 공통 harvest_navigation.yaml/NavigationSettings의 goal_timeout_s=300을 초과했다. Nav2Client._wait가 ROS 시계300초에서 timeout을 발생시켰고 controller_server는 취소 성공을 기록했다.105/팔 실패/최종 도착 불일치로 분류하지 않는다.
- 근거: controller goal14:06:33.823→cancel14:12:38.773, cmd_vel_nav7300·최종cmd_vel7322메시지, odom 이동25.871m. 마지막 AMCL(-3.01386,-11.40379)로부터 남은 경로 약1.9m. 최종 프로세스 종료/-2 로그는 시험 정리 시점이다. 느린 wall시간 자체가300초를 소모한 것은 아니며 sim에서는 ROS 시간이 예산 기준이다.
- 공통/실물 영향: 동일 설정의 긴 경로/같은 속도라면 실물에서도 가능한 시간 예산 문제. 경로 길이·회전 여유를 반영한 예산 검토가 필요하며 이번에는 공통 설정/코드를 수정하지 않았다. 기존 자동 재시도로 SEC10 2회차 수확부터 진행 중, 예찰 재사용. 상세 runs/sec01_goal_time_fix_20261020_183345/SEC10_attempt_0001/failure_navigation_timeout_20261021.json. 분석 문서는 미커밋·미푸시.


### 2026-10-21 경로 길이 기반 공통 timeout 제안 — 승인 대기

- 사용자 “경로 길이에 따라 타임아웃이 달라져야할거같은데”에 따라 공통 변경안을 준비했다. AGENTS.md의 공통 소스 적용 전 구체안/명시 확인 규칙을 따른다. 운영 farm_navigation 소스/설정은 수정하지 않았다.
- 대상: nav2_client.py의 preflight에 선택 제어기 desired_linear_vel 읽기를 기존 RPC에 추가하고, 실제 FollowPath XY 누적 길이 L로 max(기존 goal_timeout_s, ceil(2*L/v+60))을 계산한다. TF 복구 바깥 예산과 각 FollowPath 결과 대기에 같이 쓴다. 실제 SEC10 조건27.535m/0.1m/s는611초. 현재300초는 하한이다.
- 영향: 공통 실물/시뮬 FollowPath에 같은 계산. 기존 진행 정체105·도착 범위·취소/응답 제한은 유지한다. 직접 경로가 없거나 제어기가 속도 파라미터를 제공하지 않으면 기존 제한 유지. 속도는 사전 점검 기준이며 동적 변경은 다음 점검 때 갱신한다.
- 검증: /tmp의 제안 소스만 별도 프로세스로 로드해 기존 시계/취소/TF 및 추가 경로 예산21검사 통과. 실제 Isaac 배포/실물 검증은 미실행. 적용 전 검토 자료 sim/runs/goal_timeout_proposal_20261021/{proposal.patch,README.md,proposed/,tests.log}. 기존 test_nav2_execution_clock.py 보완과 test_nav2_route_timeout.py 추가도 패치에 포함한다.
- 다음: 사용자 확인 후 공통 소스·검사 적용, 기존 검사/실패 경로 재시험. 승인 전 운영 적용/빌드/재시작 없음. 기존 자동 캠페인과 원본은 유지한다.


### 2026-10-21 경로 길이 기반 공통 timeout 적용 — D-052

- 사용자 “적용해” 승인 후 공통 nav2_client.py와 관련 시험2개에 제안 패치를 그대로 적용했다. `max(기존 제한, ceil(2*경로길이/설정속도 + 60))`초이며 SEC10 접근은 약611초다. 실물/시뮬 공통이며 기존105/도착/취소 조건은 유지했다.
- 적용 소스로 farm_navigation 전체 단위시험48개 PASS. 실제 ROS overlay에서 수정 함수 로드 확인. 원본 로그: `sim/runs/goal_timeout_proposal_20261021/applied_tests.log`, 적용 기록 applied_status.json. 기준 HEAD e145d9de 및 기존 미커밋 변경 보존, 이번 commit/push 없음.
- SEC10_attempt_0003은 배포를 위해 STOPPED로 정상 중단(주행 실패 아님). SEC01~09 완료 및 SEC10 성공 예찰8window/expected11을 보존한 채 attempt_0004부터 수확 재개했다. Domain13/SUBNET, CPU 물리와 기존 진단 기록기를 유지했다. 실제 장거리 접근 완료 여부 확인 중이며 실물 검증은 미실행이다.
- 되돌리기: 제안 proposal.patch의 이번3파일 변경만 역적용하고 시험 프로세스를 재시작한다. 다른 미커밋 변경은 되돌리지 않는다.

- **적용 후 실제 Isaac 확인 완료:** SEC10_attempt_0004에서 제한611초 로그 확인. SECTION_APPROACH는 약341.47시뮬초(벽시계401.85초)에 `Reached the goal!`로 완료해 기존300초 제한을 넘는 정상 주행이 성공했다. 이어 WINDOW_MOVE도 도착했고 팔 CAMERA_INVENTORY에 진입했다. SECTION 전체 수확 완료와 구별하며 캠페인은 계속 실행 중이다. 원본 stack.log/telemetry.jsonl 및 `sim/runs/goal_timeout_proposal_20261021/applied_status.json`에 도착 근거를 보존했다.


### 2026-10-21 복귀 중 불필요한 팔 카메라 중지

- 승인: 사용자 “그래 그렇게하는게 맞지”. sim 전용 student_session.py/student_camera.py 및 관련 시험2개에 한정한다. 공통/실물 제어는 변경하지 않는다.
- 원인: SEC10_attempt_0004 RETURN_STOW에서 카메라5218회 처리. 시뮬173.95초/실제688.21초 중 student_camera_s371.85초(약54%), arm_s6.30초였다. 일반 render126.03초와 카메라 내부 세부 시간은 중첩되므로 단순 합산하지 않는다.
- 변경: RETURN_STOW/FINAL_STOP에서 센서/렌더 제품을 pause한다. 다른 작업 단계에서 재개하며, 재시도 CAMERA_INVENTORY 진입 시 즉시 현재 자세로 새 촬영한다. 재개 시 누적 sequence/FK오차/촬영 기준시간은 유지하고 이전 영상 캐시는 비운다. 관절 피드백·복귀 경로·정지/레이저 판정은 유지한다.
- 검증: Isaac Python에서 student 관련30개 단위시험 PASS. 복귀/최종정지 중 중지, 탐색/수확 재개, 새 프레임 요청과 누적 계수 보존 확인. 실제 캠페인 성능 개선 배율은 아직 미측정이다.
- 배포: 기존 SEC11 시도를 STOP으로 정상 중단해 수정 모듈을 로드하는 프로세스로 재개한다. 이는 시스템 실패가 아닌 설정 적용 중단이다. 성공 SEC01~10과 예찰 캐시는 보존한다.
- 복원: 이번 stage별 카메라 활성 제어 및 reset_capture 선택 변경만 제거하고 프로세스를 재시작한다. 기존 영상 최적화/CPU 물리 변경은 유지한다. 커밋/푸시는 미실행.


### 2026-10-21 SEC01~16 전면 재예찰·수확 성능 캠페인

- 승인: 사용자 SEC01~16을 예찰부터 다시 밤새 실행, A/B/C와 누락 원인·중복·정량 비율, 오류 시 전체 재시작 후 같은 SEC 예찰부터, 동일 현상3회면 생략 지시. 공통 코드는 변경하지 않고 sim 시험 감독자/오프라인 보고서/시험을 수정했다.
- 새 캠페인: `sim/runs/sec01_16_fresh_metrics_20261021_172329`, 서비스 `farm-fresh-metrics-20261021.service`. Domain13/SUBNET, CPU 물리, 경로별 제한시간/복귀 카메라 중지 유지. `--fresh-scout --max-identical-failures 3`. 기존 캠페인은 정상 STOP 후 보존했다.
- FAILED에 한해 SEC/단계/가변 ID를 제거한 오류 서명별 누적3회면 skipped_sections 및 skip_reason.json으로 생략한다. 다른 오류는 별도 누적, STOPPED/INTERRUPTED는 실패3회에서 제외. 완료 상태 COMPLETE_WITH_SKIPS를 전체 성공과 구분한다. 기존 기본 재사용/무제한 동작은 옵션 없는 호출에 유지한다.
- A는 전체 배치 수를 별도 기록하고 비교 분모는 관측면/높이/경로 내 red/yellow다. B는 window expected, C는 레이저 통과다. A-B/B-C 개수 차이와 객체 대응 누락을 분리한다. 정답은 오프라인 평가에만 사용한다. ID 미대응을 AI 미검출로 확정하지 않고 가림/깊이/위치 오차 등 후보와 증거 미확인을 표시한다. 레이저 물체 ID 역시 확정하지 않는다.
- 원본 장면/예찰 RGB-D·좌표/윈도우 소속/팔 관측·시도·낙하·레이저·제어/주행·프레임 시간 및 코드·설정 snapshot/해시를 보존한다. 이전 비교 보고서는 previous_comparison에 복사, 전체 원본은 기존 폴더 유지. report.md/performance_summary.json/시도별 performance_report.json을 시도 종료마다 자동 갱신한다. 원본 파일 손상은 evidence_errors에 남기며 집계 전체를 막지 않는다.
- 검증: 감독자/보고서12개 단위시험 PASS. 3회 실패→생략→다음 SEC, 재개 시 생략 유지, fresh-scout 전달, 가변ID/운영중단 구분, 예찰 누락·윈도우 미생성·중복·팔 손실 분류 확인. 기존 실제 캠페인 로그로 새 보고서 생성 확인. 새 SEC01~16 결과는 아직 미완료.
- 되돌리기: 이번 감독자 옵션/실패 서명/보고서 분류 변경만 제거하고 기존 실행 옵션을 사용한다. 기존 CPU/카메라/공통 제한시간 변경은 유지한다. commit/push 미실행.


### 2026-10-22 야간 SEC01~16 완료 및 보고서 자료

- 사용자 요청으로 완료된 캠페인 원본을 조회해 `sim/docs/SEC01_16_NIGHT_TEST_REPORT_MATERIAL_20261022.md` 작성. 운영 코드 수정/재시험/커밋·푸시는 하지 않았다.
- 새 캠페인 sec01_16_fresh_metrics_20261021_172329는 KST10/21 17:23~10/22 06:50 COMPLETE,16SEC 완료/생략0,21시도 중 실패5회. SEC06 예찰105가1회 재발했고, 전방 목표 거부2회·준비 지연1회·정지 미확인1회가 있었다.
- 최종 성공 시도 기준133윈도우, A192/B180/C98, C/A51.0%. 객체별 예찰 윈도우 누락32개(최종ID 미대응23+검출 후 윈도우 없음9), 미대응 expected20개가 단순 A-B12개를 상쇄한다. 팔 대상 미선택53건은 AI 미검출로 단정하지 않는다. ID 대응/익명 레이저 및 사건 중첩의 한계를 자료에 명시했다.
- 자료의 SEC별 수치/합계/실패 목록을 summary.json, performance_summary.json 및 실패 stack.log와 대조했다. 원인 후보와 확정 관측을 구분했으며 parser evidence_errors0을 확인했다.


### 2026-10-22 시험 결과 및 검증 코드 Git 반영

- 사용자 “테스트 결과 커밋푸쉬해줘” 승인. 야간 시험에 사용한 공통 경로별 timeout/시뮬 CPU·카메라 최적화/복귀 카메라 중지/새 캠페인·보고서 코드와 결과 자료를 함께 반영한다. 별도 multirobottrafficcontrol 및 robotarm_harvest_communication 폴더는 제외한다.
- 원격 재검토용 완료 집계5개(summary/performance_summary/failure_analysis/manifest/evaluation_contract)를 `sim/docs/test_results/20261022_sec01_16/`에 보존했다. 대용량 원본 로그는 기존 로컬 sim/runs 경로에 유지하며 보고서에 상대 링크를 추가했다.
- 커밋 전 검증: farm_navigation48 + student30 + campaign12 =90개 PASS, git diff --check 통과. 실제 통합 결과는 야간16SEC 완료/실패 재시작5회 기록을 따른다. 실물 주행 시험은 미실행.

## 2026-10-22 — 공통 교통 클라이언트 및 시뮬 교통 프로파일

- 구분/승인: 사용자 공통·시뮬 적용 및 실물 인계 문서 작성 요청. 기준 main/0832b6f 이후 미커밋 변경.
- 대상: 공통 farm_interfaces/farm_navigation/예찰·수확 node/status/communication, sim farm_sim_config의 두 traffic runtime 및 traffic 등록 원본, setup.py, sim/.gitignore.
- 전후: 기존 기본 프로파일은 종전 주행 유지. traffic 프로파일에서는 등록·경로 전체 허가 후에만 Nav2 실행하며 진행 보고·반납·우회 및 초기화 중단을 수행한다. 실물 설정/실행 중 프로세스는 변경하지 않았다.
- 검증/제한/실물 인계/복원: `../../docs/changes/TRAFFIC_ROBOT_HANDOFF_20261022.md`. 실제 관제+Isaac 공동 25개 시험과 실물 주행은 미실행. 초기화 완료 이벤트는 관제 실행기 통합 지점으로 남긴다.
- 원격: commit/push 없음. 영속 ID DB는 시험 종료나 rollback 때 삭제하지 않는다.


### 2026-10-22 예찰 윈도우와 팔 실행 상자 범위 정렬

- 사용자 “팔 실행필터보다 예찰 윈도우 생성 범위가 더커서 … 해결” 요청. sim 설정만 수정했다. 공통 플래너/팔 실행 필터·실물 설정은 변경하지 않았다.
- 원인: 예찰 task.yaml의 팔 상대 높이는−0.10..0.35m 및 축별 여유0.02m였으나 실제 continuous_near_mask는 x0.265..0.365/y±0.175/z0.087..0.35m와 HOME 거리0.09<d<0.34m를 사용했다. 계획 pose로 야간 expected180개를 변환하면37개가 상자 밖(x29/z11, 중복3)이다.
- 변경:16SEC의 원본 task.yaml height_offsets 하한을0.087m, range_tolerance를0으로 정렬. 파생 scout_survey.json과 harvest_audit.json의 평가 상자도 재생성했다. 다른 생성 파일의 주석/키 순서 차이는 제외했다.
- 검증: 원본 map_detections를 관측 순서대로 공통 Survey에 재생한 결과 expected143개, 팔 상자 및 HOME 거리 필터 밖0개(부동소수 비교1e-9). 경로 검증16SEC/80관측/371경로 통과. 실제 Isaac/실물 주행은 미실행이며 실제 도착 pose·표면점/파지점 차이는 남는다.
- 근거: sim/runs/workspace_alignment_proposal_20261022/replay.json 및 aligned_replay.json. 기존 야간 결과192/180/98과 보고서는 수정하지 않는다. 새 높이 범위로 평가 분모도 달라지므로 후속 성능 비교에서는 전체 배치 수와 작업 범위 제외 수를 함께 표시해야 한다. 예상량 감소를 수확 성공 증가로 해석하지 않는다.
- 되돌리기: 위3개 sim 설정의 이번 높이/여유/기하 주석 및 파생 평가 상자 변경만 복원. 다른 작업자의 교통 제어 변경은 유지했다. 커밋·푸시 및 새 장시간 시험은 수행하지 않았다.


### 2026-10-22 전체 빨강·노랑 과실 작업 범위 확인

- 사용자 요청으로 공통 예찰 알고리즘과 sim 설정 책임을 확인했다. 공통 survey_core/b_planner는 불변, 직전 변경은 sim task/scout_survey/harvest_audit 높이·여유 설정이다.
- 야간 초기 snapshot192개(red96/yellow96) 중심점 중153개는 경로 내 정차 위치에서 현재 상자/HOME 조건 충족,39개는 초과(하한10/상한8/깊이25, 중복4). 실제 중심높이0.785711~1.071028m 대 실행높이0.800~1.063m.
-192개 모두 AABB 일부는 깊이/높이 상자와 겹침. 필터 입력은 중심이 아닌 영상 파지점이므로39개를 수확 불가능으로 확정하지 않았다. 실제 파지점/IK/충돌 검증은 미실행. 배치·팔 필터·공통 코드는 이번에 바꾸지 않았다.
- 근거 JSON은 sim/runs/workspace_alignment_proposal_20261022/all_ripe_coverage.json, 기존 시험 자료 MD §11에 한계와 결과 추가. 커밋/푸시 미실행.


### 2026-10-22 전체 빨강·노랑 작업 범위 내 재배치

- 승인: 사용자 “로봇팔 필터 조정은 성능 변수 … 밖에있는 열매들을 안으로 재배치해”. 팔 필터/예찰 범위/공통·실물 코드는 이번에 변경하지 않았다.
- 실제 장면 sim/assets/envs/output/farm_with_plants_v5.usd에서 빨강·노랑192개 중 실제 물리모델 외곽이 깊이/높이 경계 밖이거나 안쪽1mm 여유가 없는180개를 최소 이동. 중심만 벗어났던39개와 달리 외곽 기준이다. 나머지12개와 초록96개는 위치 유지. ID/색/회전/크기/개수 보존. 연결 줄기는 식물 쪽 끝 유지, 과실 쪽 끝만 이동했다.
- 깊이/높이 이동으로 새로 겹칠 수 있는7쌍은 베드 길이 방향 최소 이동으로 해소했다. 기존 AABB 겹침5쌍은 유지되며 새 겹침0쌍. 단위m, 전체 외곽 검증은 실제 runtime 과실 자산의 AABB를 사용했다.
- 검증: 저장 장면 재개방 후 재배치 후보0개.192개 모두 계획 상자 내 외곽 및 팔 box/HOME 범위를 만족하는 경로 내 정차점 존재. 실제 과실 중심을 평가 전용으로 공통 plan_harvest에 입력한 오프라인 시험에서192/192 window 소속 생성, 보류0. 원본 레이어 변경은 과실 translate180개+줄기 points180개만 확인. 실제 USD/PhysX 과실 자산 검사4개 PASS. 비전 검출/도착 오차/IK·충돌·수확 성공의 새 통합 시험은 미실행.
- 재현 도구 sim/tools/align_ripe_fruit_workspace.py는 기본 dry-run, --apply 명시 시 원본 백업 후 저장한다. 근거 및 이동 전후 좌표/해시: sim/docs/changes/FRUIT_WORKSPACE_RELOCATION_20261022.json. 원본 백업·검증 원문은 sim/runs/fruit_relocation_20261022.
- 기존 야간 시험은 이전 배치 결과이므로 그대로 보존한다. 이후 비교는 새 장면 해시/새 캠페인을 사용해야 한다. 복원은 백업 USD를 원래 장면 경로로 복사한다. 커밋/푸시 및 장시간 캠페인은 이번에 수행하지 않았다. 다른 작업자의 교통 제어 변경은 유지했다.


### 2026-10-22 역순 윈도우 전달 수정 — D-054

- 승인: 사용자 “그래 정렬해야지 순서대로가야지 …”. 실제 SEC14 W003→W004는6.1cm 역방향, SEC16은11.4cm 역방향이었다. 단순 정차 오차 추정에서 목록 자체 역순으로 원인을 확인했다.
- 공통 Survey.windows() 반환 시 실제 수확 heading의 map 방향 투영값으로 정렬한다. 윈도우 번호는 생성 ID로 유지하므로 예: W001/W002/W004/W003/W005로 전달될 수 있다. 생성 계획·멤버·예상량·좌표·구간 연결은 바꾸지 않는다. 실물/시뮬 공통 동작 변경이다.
- 검증: 실제 Survey 누적 관측에서 늦게 생성된 뒤쪽 창을4개 지도 진행 방향으로 검사(1test/4subcases) PASS, 기존 메시지 프로토콜6개 PASS. 야간 두 실패 report로 실제 task_messages 변환 후 모든 구간 전진 순서/ID·좌표·멤버·expected 보존 확인. 근거 sim/docs/changes/WINDOW_EXECUTION_ORDER_REPLAY_20261022.json. 실제 재주행은 미실행.
- 변경: robot/ros_ws/src/scout_robot/scout_robot/survey_core.py, test/test_window_execution_order.py. 이전 성공 캐시/완료 결과는 소급 변경하지 않는다. 복원은 반환 정렬을 제거하고 해당 회귀 시험을 원복한다. 다른 교통 코드/과실 재배치 변경은 유지했다. 커밋/푸시 미실행.


### 2026-10-22 영상 사용 단계에만 팔 카메라 활성화

- 승인: 사용자 “영상이 필요하지 않은 동안에는 켜져있을 이유가 없어”. sim student_session.py 및 test_student_retry.py만 이번에 수정했다. 공통/실물·전달 미션 상태기계는 변경하지 않았다.
- 기존 RUNNING 중 RETURN_STOW/FINAL_STOP만 제외하던 조건을 CAMERA_INVENTORY/HARVEST/WAIT_BOX 허용 목록으로 변경했다. TO_HOME/STOW_WAIT/PREPARE/정지·종료·주행에서는 촬영/렌더 제품을 pause한다. WAIT_BOX는 실제 영상 정책이 계속 호출되므로 유지한다.
- 같은 tick에 TO_HOME→HARVEST로 전환되는 경우, sim 미션 세션 어댑터의 step 경계에서 지연 capture_provider를 호출해 새 현재 자세 프레임을 확보한 뒤 영상 정책에 전달한다. 기존 사용자는 provider 미지정 시 원래 camera.step을 그대로 사용한다. 재개 시 누적 촬영/FK계수는 유지한다.
- 검증: student 관련32개 PASS. 상태3종×단계10종 활성 조건, 정책 첫 호출 전까지 비활성, 재개 직후 새 프레임 전달/불필요한 재개 반복 없음, 기존 재시도/레이저/복귀 완료 회귀 포함. 실제 Isaac 성능 배율은 새로 측정하지 않았으며 새 장시간 시험/커밋·푸시는 미실행. 다른 작업자 및 이전 미커밋 변경은 유지했다.
- 복원: 이번 허용 목록 및 지연 촬영 어댑터 변경만 제거한다. 이전 복귀 카메라 중지/카메라 처리 최적화/과실 재배치/윈도우 정렬은 유지한다.


### 2026-10-22 2차 SEC01~16 시험 시작

- 사용자 “2차 테스트 가자” 승인. 새 캠페인 `sim/runs/sec01_16_round2_20261022_151624`, 서비스 `farm-round2-20261022.service`로 시작했다. 성공 예찰 재사용 없이 SEC01부터 매 시도 예찰→모든 window 수확. 같은 오류 누적3회면 SEC 생략, 그 외 실패는 전체 Isaac/ROS 재시작 후 해당 SEC 예찰부터 반복한다.
- Domain13/SUBNET, CPU/headless, 기본 교통 비활성 프로파일 유지. 수정된 공통 예찰 정렬과 sim 카메라 활성 조건의 실제 ROS/Isaac Python 모듈 로드를 확인했다.
- 과실 재배치 USD(sha256 22be2e1f423ab553eee3d471f321ea2fb49761a6cab8ddfe0648d6d3182207f3), 범위 정렬/태스크 진행 방향 정렬/영상 단계 촬영 조건 적용. 장면 복사·코드 해시는 round2_contract.json, 이전 비교 결과는 round1_comparison에 보존했다. 배치가 바뀐 비교이므로 알고리즘 단독 개선 효과와 구분한다.
- A/B/C·객체별 손실/중복/성능 사건·실패/명령체인/RPP/프레임 시간 기록 및 시도 종료별 report.md 자동 갱신. 새 결과는 아직 미완료다. 시험 시작 자체에 따른 코드 변경·커밋·푸시는 하지 않았다.


### 2026-10-23 2차 예찰/복귀/진입/준비 오류 원인 분석

- 사용자4항목 분석 요청으로 운영 코드는 수정하지 않고 동결 소스·원본 로그·오프라인 수치 재현을 대조했다. 근거 sim/docs/changes/ROUND2_FAILURE_ANALYSIS_20261023.json 및 ROUND2_* 상세 JSON.
- 동일15SEC 검출 객체 대응은157→160으로 감소하지 않음. 실제 윈도우 대상은148→131로 감소. 검출 후 미소속29개는 모두 깊이 hold이며 map 변환 오차12~36mm와 여유0 조합. 실제 시뮬 차체 자세로 재변환하면29개 모두 범위 내(최근 진단 pose 최대0.45시뮬초, 정지 촬영). 이전2cm여유 재생시 expected152→184이나 실행 범위 문제를 가릴 수 있어 그대로 복원하지 않았다.
- SEC09는1차에 팔 대상이 아니던 동일 Pepper_0033_yellow가 낙하한 뒤60초 만료, 기존 고정XY/13cm상승 복귀 IK가15.7~22.6mm 오차로15mm한도를 초과. 함수는1/2차동일. 현재TCP높이1.004~1.009m는 상자여유높이0.881m보다 높았으나 추가13cm상승을 요청했다.
- SEC12/16 작업 진입 실패는 역순이 아님. 전체TF기록 실패 직전 재구성에서 목표전방12.7/9.0cm, 횡오차1.81/1.28cm, 차체방향오차−0.28/+0.04도, 목표선각둘다8.1도로3도제한초과. 함수/설정은1/2차동일. 도착5cm허용과 짧은구간 진입3도기준 불일치다.
- 준비2회는 양 로봇odom15~17초에정상, harvest Nav2 active 후 scout bt_navigator configure전이 또는 get_state서비스발견에서정체. 300초부팅지연으로 보지않는다. SHM lock오류는 성공시도에도있어 단독원인확정불가. 정확한 내부대기/DDS경로는 추가계측이 필요하다.
- 수정/실제재주행/커밋·푸시는 수행하지 않았다. 후속 우선순위는 예찰map정합, 도달가능한복귀후보, 짧은직진기준정렬, lifecycle단계계측이다.


### 2026-10-23 예찰 좌표 정합 심층 분리 조사

- 사용자 “파악할수있는만큼 … 아주예전부터” 요청. 운영 코드/설정/장면은 수정하지 않았다. 실제 USD/URDF 센서 장착과2차75개관측, 실제물리자세/encoder, 원시태그1090개, 태그투영212개를 대조했다. 상세 sim/docs/changes/SCOUT_LOCALIZATION_DIAGNOSIS_20261023.json 및 LOCALIZATION_* JSON. 재현스크립트는 sim/runs/round2_failure_analysis_20261023.
- D435 렌더광학프레임과URDF프레임의행렬차이0, PiCam실장과설정차이약1e-13. 같은실제행렬이CameraSim metadata/TF에연결됨.75개촬영/pose stamp차이0, 공통코드는촬영시각TF를조회함. 독립렌더시각계측까지완료한것은아님.
- map평면자세가과실깊이에주는오차평균약16.0mm, 실제roll/pitch를2D에서생략한깊이영향평균0.159mm(높이영향2.35mm). 현재깊이누락의주원인은장착행렬이나기울기가아닌평면위치/방향추정.29개제외점은실제자세재변환시모두깊이범위내.
- 태그보정이실제로켜져있어LiDAR단독원인으로해석하면안됨. 원시태그후보홀수SEC502개는바깥쪽평균20.50mm,짝수588개는8.29mm편향.212개투영표본에서태그변검출폭은약49px대비홀수0.863px/짝수0.348px작음. 렌더/검출코너/시각기여는아직분리미확정이며단순보정상수를적용하지않음.
- 바퀴odom은회전에서실제각도와불일치:SEC01표본실제/odom0.890,SEC03 0.936;같은직진비는약0.9985. USD바퀴간격0.159999996m로설정0.16m와일치. 접촉/미끄러짐/가속기여미확정. AMCL/태그가큰누적오차를보정해도cm잔차는남는다.
- §38(10/13)에이미PiCam태그횡3.72cm/진행7.16cm/yaw3.41도정확도미달기록이있다. 기존정합문제에예찰여유0이겹쳐expected누락이표면화된것으로확인했다. 후속은동일포즈태그ON/OFF·정지태그픽셀위상/거리·회전전용encoder/실제비교. GT는평가에만사용한다. 커밋/푸시·3차실험미실행.

### 2026-10-23 예찰 위치 정합 통제 비교 시작

- 승인: 사용자 “그래 비교해봐”. 목표는 태그 보정/정지 영상 측정/바퀴 회전 오차를 분리하는 것이며 공통 알고리즘·운영 설정·실물 코드는 수정하지 않는다.
- `sim/runs/localization_compare_20261023`에 평가 전용 실행 도구와 원본 로그를 분리. 기존 캠페인 worker에서 수확 요청만 생략한 시험 worker를 사용하며 예찰은 실제 공통 ScoutArea Action을 그대로 호출한다.
- SEC01, 매회 전체 재기동, CPU 물리·headless·Domain13/SUBNET. 태그 보정 ON/OFF/OFF/ON 순서로 반복. 마지막 예찰 완료 후 개방루프 ±0.25/±0.5rad/s 회전에서 encoder/실제 물리 자세를 평가한다. 정답은 제어 입력으로 사용하지 않는다.
- 주행 스택 종료 뒤 정지 태그 RGB/동일 프레임 CameraParams를 거리·화소 위상·각도별 수집하고 운영 apriltag_ros에 재생한다. 실행 서비스 farm-localization-compare-20261023 및 farm-localization-static-20261023. 현재 실행 중이며 최종 결과는 별도 기록한다.
- 기존 소스/설정 복원 불필요. 중단은 해당 runs/STOP 파일과 이번 시험 서비스만 대상으로 한다. 커밋·푸시 미수행.

- 재개: 사용자 컴퓨터 종료/재부팅으로 세 번째 OFF 예찰 도중 중단. 성공한01 ON/02 OFF는 보존했다.03 중단 결과를 로봇 오류와 구분한 `INTERRUPTED_HOST_REBOOT`로 기록하고 `sim/runs/localization_compare_20261023/interrupted/03_tag_off_before_reboot`에 원본 및 생성 산출물을 보관했다.03 OFF부터 전체 초기화 후 재실행하며04 ON·회전·정지 광학 시험을 이어간다. summary는 기존 성공 결과를 유지하도록 시험 runner만 수정, scan 수집은 append로 변경했다. 운영 소스/설정 영향 없음.

- 추가 진단: 사용자 “최대한 원인 찾아서 해결” 범위에서04 완료 후 정지 AMCL `request_nomotion_update` 12회 효과를 평가한다. 감독기 메인만 SIGSTOP/SIGCONT로 순차 실행을 대기시키며 로봇/Isaac는 계속 실행한다. GT 입력·운영 소스 변경 없음. 정지 RGB 비교에는 실제 기본값 DLSS 성능(AA3/execMode0), DLSS 품질(3/2), TAA(1), AA없음(0)을 추가했다. 근거는 설치된 SimulationApp 기본 anti_aliasing3 및 isaacsim.exp.base.kit의 dlss.execMode0이며 실제 렌더 설정/같은 RGB 시각의 CameraParams도 저장한다. 원인 확정 및 설정 적용 결과와 구분한다.

### 2026-10-23 태그 텍스처 축소 편향의 시뮬 전용 개선 적용/검증 중

- 승인: 사용자 “최대한 원인 찾아서 해결”. 실제 정지 영상과 같은 시각 CameraParams를 사용한 태그104 측정에서 기본 텍스처의 거리 편향 평균25.7mm, 이상적 PNG 투영은 절대1.51mm 이내. 검출기 decimate1/2, DLSS/TAA/AA없음, 기본 USD 투영 K 정렬만으로는 해결되지 않았다.
- 같은 크기/패턴을 흑백 기하 셀로 표현하면 기본 렌더 조건 평균10.6~11.3mm로 감소. 색·조명/화소 위상·평면 PnP에 따른 잔차는 남으며 완전 해결로 기록하지 않는다. DLSS 품질 변경은 평균5.0mm지만 최대21.3mm 잔차 및 다른 카메라 성능 영향이 있어 적용하지 않았다.
- 최소 적용: sim/tools/build_apriltag_assets.py에서 기존 제공 PNG의36h11 8×8셀을 생성 배치표 pattern_cells로 보존. sim apriltag_scene.py는 원래 종이/PNG/인쇄ID 위 코드 영역에만 동일 크기64개 기하 셀을10µm 띄워 표현한다. 기존 배치표에서는 기존 텍스처 방식으로 호환된다. 운영/실물 공통 알고리즘·필터·검출 설정·카메라 K/TF·장면 USD는 이번에 변경하지 않았다.
- 수정 파일: 위2개, sim config/apriltag_map.json 및 기존 sim/tests/test_apriltag_assets.py, tools/check_apriltag_scene.py. 새 설치 의존성 없음. 원본240태그의 좌표/크기/ID/텍스처 등 기존 JSON필드는 HEAD와 완전히 동일함을 비교했다.
- 검증: 패턴15개를 실제 PNG/정식36h11 사전과 대조한 기존3검사 PASS. 실제 USD 전체240태그의 기하 크기50mm·셀색/순서·면위치 및 기존 종이/광학프레임 검증 PASS. 현재 기본 렌더·CPU·Domain13/SUBNET으로 SEC01 실제 예찰 검증 중: sim/runs/localization_compare_20261023/05_geometry_tag_on. 결과 후 적용 유지 여부를 결정한다.
- 원상복구: pattern_cells 필드 없는 원래 배치표를 사용하면 기존 표현. 이번5개파일 diff만 되돌릴 수 있다. 다른 작업자의 미커밋 변경은 보존한다. 커밋/푸시 미수행.

- 적용 후 결과: 첫시도는 촬영전 TF102(요청17.116668초/latest16.750001초), 원본 보존 후 전체 재시작. 재시도 SEC01 SUCCESS, 5관측/9윈도우/expected14/실제윈도우대응11of13. 원시 태그 법선 편향−16.32mm(기존ON−22.49/−22.94), 차체 법선 절대13.02mm(기존15.85/16.23), 과실 깊이 절대17.65mm(기존17.54/21.64). 최종오차는 기존ON범위 내 단회검증으로 전체해결/확정개선이라 하지 않는다. 개선은 적용 유지하되 여러SEC/수확 재검증은 남음. TF102·AMCL잔차·회전물리는 별개 미해결이다. 보고서 SCOUT_LOCALIZATION_COMPARISON_20261023.md 및 changes/LOCALIZATION_CONTROLLED_COMPARISON_20261023.json에 원본/정량근거 보존. 커밋/푸시 미수행.
- 종료 확인: 모든 실제 예찰/렌더/검출 비교 완료 후, 첫 기하 진단의 SDK 예외로 종료 대기 중이던 단일 서비스 farm-localization-vector-20261023만 종료해 GPU 메모리를 반환했다. 예외 원본 보존. 사용자 작업 프로세스는 종료하지 않았다.

### 2026-10-23 AMCL/회전 물리 분리 및 예찰 캐스터 접촉 개선

- 승인: 사용자 “그것도 진행해” — 직전 보고의 AMCL잔차·회전물리 분리 검증. 원본 `sim/runs/localization_motion_20261023`. 공통/실물 코드와 주행 설정은 변경하지 않는다.
- Nav2/업무/카메라/LiDAR를 끈 별도 Isaac+장치 launch에서 단일 cmd_vel 발행자를 확인하고5조건 비교: 기존, 캐스터 재질마찰0(기본 평균결합), 바퀴damping10배, 캐스터마찰0+min결합, min결합+damping10배. 각조건 좌우±.25/±.5rad/s 및 전후직진/정지, 매회 전체재시작. GT는 평가에만 사용했다. 준비 시 station파일 누락/상위USD의m·Z메타데이터 누락은 별도 preparation_failure 로그에 보존 후 보완했다.
- 기존 caster는고정상자이며별도접촉재질없음. 단일발행자에서도 실제/encoder회전0.948~0.965, 낮은명령누적각추종약19% 재현. caster재질0만 적용하면0.973~0.988/명령추종51~52%. min결합까지적용하면0.9950~1.0038/저속명령추종79~80%, 고속89~90%. damping10배만으로는개선없음, min+damping10배추가이득없음.
- 적용: `sim/assets/robots/scout_robot/urdf/scout_robot_camera_fixed.usd` 캐스터 충돌체에 정/동마찰0·반발0·frictionCombineMode=min 재질만 연결. 자유롭게구르는수동캐스터를마찰없는지지접촉으로근사, 실제캐스터의완전한구름저항모델은아님. 바퀴형상/구동gain/질량/odom치수불변. 원본백업 `scout_before_caster_fix.usd`, 재현도구 `sim/tools/configure_scout_caster.py` 기본dry-run/--apply 및기존백업덮어쓰기거부.
- 실제Sdf모든spec비교 및재개방검사PASS: 새캐스터재질과해당충돌체binding외수정없음(asset_diff.json). 기존Nav2/AMCL/태그그대로SEC01 실제예찰검증중(06_caster_fix).
- AMCL: 실제동일scan·encoder·추정초기분포를실제farm_tag_amcl에별도namespace재생, GT입력없음. 기본/360빔/σhit.05 비교각3회(동일seed로수치재현,독립통계표본아님). 정지수동10프레임동안갱신1회,nomotion35회강제후에도Y잔차약142/150/204mm. 실측지도점수의5cm이동민감도X3.7%/Y0.13%,360빔도유사. 길이방향관측부족이며단순대기/빔추가/σ축소는해결책으로적용하지않음.

- 최종검증: 06_caster_fix SEC01 SUCCESS, 5관측9윈도우expected13/평가13/윈도우대응13, 차체법선11.17mm/yaw.407도/과실깊이12.27mm. 직전태그개선05는13.02mm/1.135도/17.65mm. 각1회이며다른SEC/수확미검증. 속도솔버1→8도개선없어미적용. 6물리조건모두worker_code0.
- AMCL공통후보: 동일영상복수태그의6D PnP 사전검증 및품질/불확실성/fallback/실물영향을 MULTITAG_LOCALIZATION_PROPOSAL_20261023.md에 구체화, 공통코드미적용/승인전. 정답보정/도착완화는없음. 원본/결과/소스해시는 SCOUT_MOTION_AMCL_ISOLATION_20261023.md 및changes/동명JSON. 전태그보고서의SEC01 분모12는원본13으로검산·정정했음.


### 2026-10-23 예찰 복수 태그 공통 관측 적용 (D-055)

- 승인: 사용자 “예찰은 거리가 머니까 복수태그 적용해도 괜찮을듯 반영해봐”. 공통 farm_tag_localization observer/runtime/node/pixel_bias와 회귀시험, 시뮬 예찰 모델 ID만 수정. 실물/수확 프로파일·AMCL 보정량·주행·Action 판정 불변. 기존 미커밋 교통/팔 변경 보존.
- 동일 시각/활성구간의 기존 usable 태그2개 이상을 coplanar IPPE+LM 6D로 계산. 각 태그/전체 RMS·거리·높이/기울기·동일 공분산 검증, 부족/불량/모호 시 단일 fallback. 공분산 축소 없음. 단일 pixel-bias 적용 차단. 별도 모델 ID/원본 IDs/각 RMS/거부 이유 기록.
- 회귀76개 PASS(신규11개 포함). 기존 수확 launch stub의 transfer_parameters 누락으로15개 ImportError는 별도 미통과 기록. 원시 로그재생05/06 복수선택116/67프레임, 같은표본X/Y13.56/24.99→5.45/10.83mm 및13.72/17.68→6.26/13.48mm. 정답은 사후평가에만 사용.
- Domain13/SUBNET/CPU/headless 실제 SEC01 예찰07 첫시도 SUCCESS,5구간9윈도우expected13/실제대응13of13,105없음. 복수선택12회/태그부족54회/복수품질거부2회,보정요청61회. 직전06 대비 과실깊이절대12.27→11.74mm,차체법선11.17→10.66mm이나yaw.407→.446도로 단회 개선폭 제한. 실물/다른SEC/수확 미검증.
- 상세 sim/docs/changes/MULTITAG_IMPLEMENTATION_20261023.md 및JSON, 원본 sim/runs/multitag_validation_20261023. 시험종료·프로세스정리. 복원은 시뮬예찰 model_ids.tag_multi 제거(기능OFF) 또는 이번 공통diff만 되돌림. 미커밋/미푸시.


### 2026-10-23 정지 촬영 전 실제 태그 보정 확인 (D-056)

- 승인: 구체적인 첫 촬영 전 보정 공백 개선안에 사용자 “ㅇㅋ 그렇게 ㄱ”. 공통 TagControl에 현재 token/구간/로봇/지도/시각이 맞는 실제 AMCL 적용 이벤트 확인, SegmentProgressState 촬영 전에 정지 상태에서 해당 구간 권한을 열어3회/최대8초 확인 후 새 시각 capture 요청. finally에서 사용권 종료. 적용 부재는 사유를 저장하고 예찰 진행. 접근 중 보정/이동계약/AMCL gain·공분산/Action 판정 불변.
- 신규10개 및 기존 프로토콜/이동/정렬/사용권/복수태그 총34개 독립 회귀 PASS. harvest 사용권 mock에 신규 구독 API만 추가. 다른 교통/주행/팔 미커밋 작업 보존.
- Domain13/SUBNET/CPU/headless 실제 SEC01 첫 시도 SUCCESS,105없음. 첫 촬영 위치추정 기여 과실깊이절대34.62→6.53mm,전체11.74→7.70mm,차체법선10.66→5.42mm. 단회비교. yaw평균.446→.770도로증가,검출13개/윈도우대응12of13으로 후퇴도 있음. G03 보정1회 후8초timeout,같은촬영F0009 depth_out_of_range hold. 이를 숨기거나 범위완화하지않음. 남은 방향잔차/단일태그편향·관측부족은 미해결.
- G01~05 대기2.61/2.31/8.04(timeout)/3.43/3.27초, 총19.67초. 첫촬영공백개선과전구간정확도해결을구분. 실제/추정자세로동일카메라점을재변환한오차이며 센서측정포함전체과실오차아님. 실물/다른SEC/수확미검증.
- 상세 sim/docs/changes/SCOUT_CAPTURE_TAG_SYNC_20261023.md 및JSON, 원본sim/runs/capture_tag_sync_20261023(소스사본/해시/시험/적용이벤트보존). 실행종료·시뮬정리. 복원은이번TagControl/SegmentProgressState diff와관련시험만대상. 미커밋/미푸시.


### 2026-10-23 추가 정지 없는 예찰 태그 보정 (D-057, D-056 대체)

- 승인: 시간 증가 없이 정확도/윈도우 누락을 개선한다는 제안에 사용자 “그렇게 잡고 ㄱ”. 공통 SegmentProgressState의3회/8초 촬영 전 대기 및 미커밋 TagControl 대기 API 제거. 기존 capture after_stamp 경로 복원. TagControl/NavigationMoveState에 section_start 목표pose 전달, Lease는 유한성/같은token 불변검증. 다른 교통/주행/팔 미커밋 변경 보존.
- adapter는 목표0.1~0.5m/방향30도/TF0.5초 이내의 접근에서 유효 복수 태그만 보정. 마지막0.1m 새 요청은 동결. 실제 적용된 복수태그 기준3초/odom0.3m/회전20도·동일token 안에서 단일gain0.5→0.1, 그외기존0.5. 별도 카메라/정지대기·공분산축소·PnP prior·Nav2속도/도착/Action판정 변경 없음. 실물/수확 설정 미변경(복수모델OFF에서는 접근보정OFF).
- 회귀100 PASS, 기존 수확launch stub transfer_parameters 누락15개 ImportError는 별도 미통과. Domain13/SUBNET/CPU/headless 실제 SEC01 기준07/11 2회평균137.51초/깊이위치추정기여11.60mm. 초기무대기09/10 평균140.25초/6.23mm로 시간조건미달. 마지막10cm동결 최종12/13 평균138.60초/8.14mm, 각9윈도우expected13/대응13of13,holds없음/성공실행105없음. 정확도약29.8%개선이나 실제시간평균+1.09초(+0.79%)로 **엄밀한 시간비증가조건은 아직달성/입증하지못함**. 명시적촬영대기0과시간비증가를구분한다.
- 실패도보존:12최초시도는odom/clock정상이나 scout map_server configure/harvest bt_navigator configure 준비정체로goal전종료후재기동. 둘째시도ActionFAILED102: RPP가11.350001초요청/latestmapodom10.950001초(0.4초부족),완료구간0/태그보정요청전. 이후전체재시작성공. 정확한lifecycle내부원인은미확정. 두실패는preparation_failures원본/진단에남김.
- 기준11은보존07공통소스를잠시실행후4파일finally복원(다른동시수정은해시검사로보호),최종소스해시일치검증. 최종근거sim/docs/changes/SCOUT_NO_WAIT_LOCALIZATION_20261023.md/JSON,원본sim/runs/scout_no_wait_20261023. GT평가전용. 실물/다른SEC/수확미검증. 모든시험종료/개선코드적용상태,미커밋/미푸시. 복원은이번TagControl/Node/runtime/tag_adapter/NavigationMoveState diff만대상,촬영즉시진행은기존상태유지.


### 2026-10-23 예찰 깊이 방향 ±2cm 판정 여유 (D-058)

- 승인: 사용자 “그정도면됐고 … 허용 범위를 … 넓히자”, 축 질문에 “베드 깊이 방향에 ±2cm 추가” 선택. 직전 D-057의 실제시간+1.09초/정확도 개선 수준 수용. 기존 수치를 바꾸어 시간비증가 달성을 주장하지 않는다.
- 공통 b_planner Config.depth_tolerance 기본0, survey_core harvest.depth_tolerance_m 연결. 신규 생성/기존 창 편입/재검증/관측 목록 모두 깊이 축에만 추가. 시뮬 task.yaml SEC01~16 .02 지정,공식build로 scout_survey.json만재생성. 실제 명목 작업 깊이10cm·팔필터/높이/진행방향/실물설정/과실배치/경로 불변. 판정 깊이만14cm(±7cm). 보고서·허용범위마커도 깊이 여유 반영, 기존 교통/정렬 변경 보존.
- 신규6+기존프로토콜6/정렬1 총13회귀 PASS, route검증16SEC/80관측/371경로 PASS. 저장된기존Plan/등록좌표 재생에서08case expected12→13/hold1→0,기존9창물리위치보존. 최근5기록13→13/hold0유지. 실제Isaac/수확/실물 재시험은하지않음.
- 상세sim/docs/changes/DEPTH_WINDOW_ALLOWANCE_20261023.md/JSON,원본sim/runs/depth_window_allowance_20261023. 복원은시뮬depth_tolerance_m=0및예찰파생만재생성. 미커밋/미푸시.


### 2026-10-23 작업구간 짧은 이동 실패 원인 추가 확정

- 사용자 원인 조사 요청. 운영 코드/설정 수정 없이1·2차 원본 로그, 동결 소스, 실제 차체 진단을 대조. 상세 `sim/docs/changes/APPROACH_ROOT_CAUSE_20261023.md`/JSON.
- 최초 베드 진입이 아니라 윈도우 사이 이동 전 resume_current의 straight_plan 각도 검사 실패. 중복 관측 ID가 별도 겹치는 창을 만들어 목표 간격SEC12 8.98cm/SEC16 4.70cm가 됐고, 기존 허용 횡오차를 가까운 목표선3도 조건이 거부. 팔 작업 중 실제 차체 이동은1mm 미만이며 실제 자세로도3도 초과.
- SEC12 관측 쌍9.4~9.6cm가 실제 자세 재변환 후4.1cm로 줄어6.5cm 연결 기준 내. SEC16은 재변환 후도8.6cm로 표면점 차이 기여가 남음. GT는 평가 전용,0.90~0.95시뮬초 진단 보간 한계 표시.
- 1차SEC16 attempt2에도 관련 중복/역순창으로 WORK_TARGET_NOT_AHEAD 실패 존재. 2차는 순방향 정렬됐지만 가까운 전방 목표 조건에 걸림. 판정 두 소스는1·2차SHA256 동일. ‘1차 관련 문제 없음’ 해석 정정.
- 공통 주행의 짧은 구간 경로/허용 조건 정합이 필요하며 미적용. 실물 가능성/실물 재현을 구분. Isaac 재실행·커밋·푸시 없음.


### 2026-10-23 짧은 작업구간 전방 이동 조건 수정 완료

- 승인: 사용자 “그래 해 작업”. 공통 farm_navigation/parallel_approach.py에서 목표선각 제한을 제거하고 차체yaw/횡오차/전방 조건을 독립 유지. 순수횡이동의 부동소수점 잔차는 전방1e-9m 이하 거부. 새 제어기/설정 변경 없이 기존 실제 목표·FollowPath 유지.
- 새 회귀5+기존48=53개 PASS. Domain13/SUBNET CPU/headless 실제 Isaac HarvestTask 이동 전용2회 SUCCESS: SEC12 6.72초/최종3.33cm·1.74°, SEC16 5.76초/최종2.15cm·0.25°. 시작위치는 실패추정XY, yaw는정렬. 과거전체상태/팔수확 검증과 구분.
- 기존 RPP 제자리 방향 보정 명령은 있었고 실제진단yaw 최대4.77/5.14°.3도는 시작/최종 판정이며 주행중 무회전 보장은 아님. 샘플 횡오차초과 없음, 충돌검사 유지.
- 준비프로파일 오류와SEC12 lifecycle 응답10초만료를 별도보존, 시험도구60초로 재시도성공. 종료단계Isaac−11은 Action성공후 supervisor종료 중 발생. 상세 sim/docs/changes/PARALLEL_APPROACH_FIX_20261023.md/JSON 및 sim/runs/parallel_approach_fix_20261023.
- 실물/전체SEC 수확 미검증. 중복 ID는미해결. 다른작업변경보존, 미커밋/미푸시.


### 2026-10-23 반복 시작 준비 오류 응답 손실 경로 확인

- 사용자 반복문제 지적에 저장로그/설치헤더/동일릴리스공식소스확인. SEC05 bt_navigator configure 후change_state응답송신실패가직접확인됨. 다른기간AMCL/map/planner/smoother에도동일경고. rmw_fastrtps8.4.4의응답구독자매칭실패→RMW_RET_TIMEOUT,Nav2기한없는change_state응답대기가300초전체실패로확대하는경로확인.
- SEC16 get_state서비스발견불가/Creating정체는별도형태이며동일근본원인미확정. SHM경고만으로원인단정안함. 상세sim/docs/changes/STARTUP_RESPONSE_DIAGNOSIS_20261023.md/JSON. 운영변경/신규시험/커밋/푸시없음,해결완료아님. 다음은단계별응답/스택계측과시험전용동시기동·전송비교.


### 2026-10-23 반복 시작 준비 오류 통제 재현/버퍼 포화 경로 확인

- 사용자 “확인해봐 이유가있겠지”. Isaac없는실제Nav2 map_server+manager 부하에서동일응답누락재현. 별도GetState는inactive, manager GDB는change_state 응답 무기한대기.
- 32쌍동시×6묶음: 기본20/192실패·호스트UDP수신버퍼드롭204247, DDS수신버퍼만확대0/192·드롭0, UDP전용4/192·드롭166434. 기본수신상한212992B→시험XML요청2MiB/커널상한4MiB. SHM단독원인아님. 부하시험결과를실운영실패율로해석하지않음.
- 정상전체구성기본4회성공,후보버퍼2회모두18초대양로봇active. CPU/headless Domain13/SUBNET,이동/수확명령없음. 운영프로파일·공통코드·sysctl변경없음. SEC16 Creating/get_state불가형태는동일원인확정아님. 상세sim/docs/changes/STARTUP_RESPONSE_DIAGNOSIS_20261023.md/JSON,원본sim/runs/startup_discovery_20261023.
- 다음권장: 시뮬기동에검증한DDS버퍼프로파일연결. 응답대기상한/상태기반복구는별도검토. 미커밋/미푸시.


### 2026-10-23 전체 시뮬 기동 DDS 수신 버퍼 기본 적용

- 승인 사용자 “그래 좋아 잘했어 수정해”. sim config fastdds_discovery.xml의listenSocketBufferSize2MiB를all.launch.py에서scoped자식환경에기본연결. 기존외부DDS프로파일은보존/로그표시. setup기존glob포함,실물/공통/전역환경/sysctl/기동제한불변. 개별launch직접실행은미적용.
- 신규4+기존7=11개PASS. 외부프로파일미지정일반명령으로실제CPU/headless Domain13/SUBNET전체기동2회모두양로봇active18.690/18.080초,응답누락0. DDS발견소켓64개수신상한4MiB확인. 이동/수확Goal없음.
- 상세sim/docs/changes/STARTUP_DDS_BUFFER_FIX_20261023.md/JSON,원본sim/runs/startup_discovery_20261023/full_integrated. 모든Creating정체해결보장은아님. 미커밋/미푸시,시험프로세스종료.


### 2026-10-23 사용자 요청 커밋·푸시 준비

- 사용자 “이상태로 커밋푸쉬” 승인. 예찰 창/과실 정렬·배치/태그 표현·캐스터/복수태그·추가정지없는보정·깊이±2cm·팔카메라활성·짧은전방이동·DDS기동프로파일과관련시험/보고서만선별했다. 다른작업자의교통코드/설정/문서는작업트리에보존하고혼합파일도해당부분제외.
- 이번직접회귀148개PASS,git diff --cached --check PASS. 기존 farm_tag_localization test_launch_contract의transfer_parameters mock ImportError15개는범위밖기존오류로제외명시. 결과sim/docs/test_results/20261023_regression.json. 실제Isaac결과는각상세보고서따름,실물검증미실행. 대용량sim/runs원본은로컬유지,재검토용수치/분석JSON은함께커밋.
- origin/main직접조회0832b6f로로컬기준과일치확인. git fetch는로컬refs/codex/turn-diffs 임시참조의누락객체때문에실패해원격직접조회로대체했고임시참조는변경하지않음. 이항목작성시커밋/푸시대기,최종원격반영상태는해당커밋과최종보고참조.


### 2026-10-23 3차 SEC01~16 시험 시작

- 사용자 “3차 테스트 시작” 승인. 기준92ad63a 및교통미커밋변경보존/기본교통비활성프로파일. 새캠페인 `sim/runs/sec01_16_round3_20261023_151213`. 매시도새예찰→모든반환창수확, 오류시전체재기동/동일SEC재시도,동일오류누적3회SEC생략. Domain13/SUBNET CPU/headless. 팔복귀/새모델건은보류해현재모델유지.
- A/B/C,객체대응/중복/누락원인,원시실패로그를기존평가기로기록. 추가태그소스/XML/장면/캐스터스냅샷과round3_contract.json 보존. 별도읽기전용RPP/명령체인기록기포함. 독립백그라운드감독PID1571501,종료시기록기정리.
- SEC01_attempt_0001 준비완료06:12:46UTC,예찰Goal06:12:57UTC전송. DDS기본버퍼자동적용로그확인,확인시점응답누락0. 전체시험완료아님. summary.json/result.json/events.jsonl/supervisor.log에서진행확인. 시험중코드수정/새커밋/푸시없음.


### 2026-10-23T15:51:21.851487+09:00 재부팅 후 3차 캠페인 재개

- 사용자 “컴퓨터멈춰서 재부팅함 재개”. 기존 sec01_16_round3_20261023_151213 이어실행. SEC01 attempt1은9번째창중중단,완료창8개모두SUCCESS. 원본result백업/공유scene/기존산출물보존뒤INTERRUPTED로별도분류,로봇오류3회누적에서제외.
- 기존정책유지: 매시도새예찰→모든창수확,같은오류3회SEC생략,Domain13/SUBNET CPU/headless. 감독PID14127,SEC01_attempt_0002시작. 양로봇Nav2active와DDS기본버퍼선택로그확인. 전체시험완료아님. resume_history.jsonl 및summary.json으로중단/재개추적.
- 코드/설정수정·커밋/푸시없음. 컴퓨터멈춤의원인을로봇Action실패로단정하지않음.


### 2026-10-27 3차 시험 완료 평가와 원격 업데이트 확인

- 3차 SEC01~16 전체완료: 2026-10-23 15:12:25~10-24 08:39:19KST(17시간26분54초),최종성공137창.19시도=성공16/Action실패2/컴퓨터재부팅중단1. 생략없음. 중단시도의실적은최종합계에서제외.
- A192/B195/C125,실제윈도우대응181(94.27%). 실제창누락11=예찰미대응10+검출후창누락1. 팔대응181분류122통과연결/48시도미통과/6미선택/4미시도/1ID미확정. 익명레이저C125와ID연결122차이3,이벤트중복·ID불확실성유지.
- 시작준비오류재시작/105기록0,SEC07정렬조건과SEC09팔복귀각1회실패후재시도성공. SEC07직전TF재구성yaw약3.53도로차체3도초과의심이나정확한판정TF미저장한계명시.
- 보고서sim/docs/SEC01_16_ROUND3_TEST_REPORT_20261027.md,검토용원본/집계/실패Action/SHA256은sim/docs/test_results/20261027_round3/. 전체숫자·창결과·분모/해시검증PASS. 제어코드변경/새시험없음.
- git fetch복구: 0바이트Codex임시참조백업후격리,원격main92ad63a동일확인. 실물담당브랜치4b5c5b1→cf870da(10/23 21:39KST)인계통합/TF·취소/주행판정변경확인. 공통파일이현재main과겹쳐자동병합하지않음. 다른교통미커밋작업보존. 사용자보고서/결과커밋푸시승인,이기록작성시푸시대기.


### 2026-10-27 현재 main/실물 담당 브랜치 비교

- 사용자비교요청,fetch후main68e5ef7/실물cf870da를비교. 공통조상2a397da,고유커밋6/8. 공통실행코드도달라‘설정만차이’아님. 우리Nav2시각패치·경로별제한·목표선각분리와실물의인계/TF/취소·잠금개선이분기됨.
- YAML실제병합으로VicPinky핵심RPP/footprint/costmap/도착값은일치확인. 공통기본yaml만덮으면실물브랜치sim에큰차체/0.4주시가적용되는차이있음. 양브랜치실제함수재생에서SEC12/16기하 main허용,실물기본3도/선택5도모두path_heading거부.
- 상세sim/docs/changes/REAL_BRANCH_COMPARISON_20261027.md/JSON,재현sim/runs/branch_comparison_20261027. 실물설치Nav2패치여부미확인. 소스수정/병합/주행/커밋푸시없음,교통미커밋변경보존.


### 2026-10-27 공통 주행 재시도 선별 통합 준비

- 사용자 승인으로 실물5ff5b50의 제한106재시도를 공통farm_navigation에 선별 반영. 기본0/운영 비활성, 거리 기반 제한·교통 미커밋 변경 보존. 대기시간만 총 실행 제한에서 제외. 105는 대상 아님.
- 관련32검사 통과, 교통 생성메시지 미빌드로 해당검사 미실행. 실제 주행/빌드/인계 전체 통합 미실행. 상세 sim/docs/changes/NAVIGATION_RECOVERY_INTEGRATION_20261027.md. 미커밋/미푸시.


### 2026-10-27 관제 교통·주행 시험 전달본 반영

- 사용자 traffic_and_drive_tests_sim_20261027 반영 승인. 9타입 중 기존8동일/NavigateToNode 추가, 두 시뮬 교통 프로필에 시험 서버 연결. 공통 ActionHandoff/계획·주행·허가 재사용, 작업 구간 예약/출구 차단 우회와 취소 정리 확인 보완. 기존 업무·실물 설정 보존.
- 공통4+sim2패키지 빌드,117회귀,Domain13/SUBNET 대역 주행의 실제DDS Action 성공/실패/취소·동일UUID조회 통과. 저장그래프47.5m우회 확인. Isaac/실제관제 공동시험 NOT_RUN. 상세 sim/docs/changes/TRAFFIC_DRIVE_HANDOFF_20261027.md, 공유검증 sim/docs/test_results/20261027_traffic_drive/. 미커밋/미푸시.


### 2026-10-27 교통 시험 반영분 커밋·푸시 및 실물 추가 업데이트 확인

- 사용자 커밋·푸시 승인. 기존 교통 연동과 테스트 Action, 기본 비활성106재시도 및 검증자료를 함께 반영한다. 117회귀/공통4+sim2빌드/대역DDS Action 검증 결과 유지, 실제 공동 주행 NOT_RUN. 원본 전달 폴더와 runs/build/state는 커밋에서 제외.
- fetch 후 실물 브랜치5ff5b50→48d2d1c(15:32KST) 확인: 일반 방향6도, 정지 후 복귀5cm/6도, 실행 중 최대3도 유지, PC더미 기반 인계·복귀 후 다음window 성공1회 기록. 자동병합 없음. 상세 sim/docs/changes/REAL_BRANCH_UPDATE_20261027.md.


### 2026-10-27 공용 코드 로컬/실물 사전 병합 검토

- 사용자 검토 요청. main b5ef6f2/실물48d2d1c,공통조상2a397da를3방향비교. src변경경로 로컬만66/실물만83/양쪽37(17동일/20상이). 실행코드 변경·병합 없음.
- 우선 ActionHandoff 외부check잠금밖/재시도설정검증/TF구분·조회API, 인계 API는묶음검토.106핵심동일SHA. 로컬교통·거리예산·D059·TF원본조회·예찰개선/vendorNav2보존필요. 인계유일출력검사와교통정지publisher다중생성의구성충돌확인.
- 잠금/설정실제함수오프라인경계검사실행, 운영교착/실주행재현아님. 상세sim/docs/changes/COMMON_CODE_MERGE_REVIEW_20261027.md/JSON. 문서만미커밋/미푸시.


### 2026-10-27 — 최신 운송 통합 브랜치 검토·시험 환경 설계

- 구분: 사전 검토/설계, 사용자 최신본 비교 요청 범위. main b5ef6f2 / feature_dongmin9686aca.
- 대상: sim/docs/changes/TRANSPORT_SIM_SCOPE_REVIEW_20261027.md 및 JSON, docs/PROJECT_STATE.md. 기존 미커밋 검토 문서 보존.
- 전후: 실행 동작 변경 없음. 추가 기능/실행 장애/반영 파일 경계/마커·카메라·기구·시간·관제·교통 시험 순서와 수량A~F 기록계획을 문서화. sim station복귀의 marker32 생략은 사용자 요구이며 구현 전 상태. pickup42/41와 sorter40 도킹은 유지.
- 실물 영향: 없음. 공통 코드/실물 설정 변경안은 보고서에 제안만 기록. 승인 전 적용하지 않음. 커밋/푸시 없음.
- 검증: 전체Git inventory, actual config함수 sim거절/ROS입력확인, 기존RouteGraph station-sorter 양방향6.5m, 원격FSM 대역12검사PASS. Isaac/실기/통합빌드/E2E 미실행. 로그 sim/runs/transport_scope_review_20261027/.
- 되돌리기: 새 보고서/JSON과 이번 문서 추가 항목만 제거. 기존 검토자료/코드/자산 영향 없음.


### 2026-10-27 — 인계 시험 범위 축소 (D-063)

- 사용자 지시: 과실 배출·낙하 물리/하역 기구 구현 제외, 도킹 후 두 바구니 정렬·정지 유지로 sim 인계 성공 판정. 기존 설계의 실제 과실 전달 시험/D~F 측정을 대체. 허용 오차·유지 시간은 형상 확인 후 결정. 마커 도킹/주행/이격/복귀와 A/B/C 유지.
- 운송 URDF/portable URDF/USD 및 cargo_box·바퀴·덮개·틸트 관절 존재 직접 확인. 실제 런타임 연결·시험 미실행.
- 변경: TRANSPORT_SIM_SCOPE_REVIEW_20261027.md 상단에 우선 적용되는 범위 조정, DECISIONS D-063. 문서만 변경/실물 영향 없음/커밋·푸시 없음. 되돌리기는 이번 문서 추가 항목만 제거.


### 2026-10-27 — 운송 시뮬 구현 1단계: 계약·공통 운송/도킹·복귀

- 사용자 “구현해야되는 파트 확인하고 하나씩 작업시작해” 승인으로 사전 검토 범위의 실행 코드 통합 시작. 바구니 정렬 유지 기준 D-063, 기구/낙하 구현 제외 유지.
- feature_dongmin9686aca에서 transport_robot/farm_docking 선별 도입 및 메시지8종 추가. 기존 교통·NavigateToNode·공통주행/예찰/수확 코드는 보존. sim 환경 허용·경로/시계 검증, sim return에 한정한 navigation_only 정책 구현. 실제 도착/정지 실패와 취소는 실패/취소 유지. 실물 기본 마커 도킹/하드웨어 검증 유지.
- 운송 교통 미연결 상태에서 traffic.enabled 시작 거절. 도킹 단일 출력과 충돌하는 별도 Nav2 정지 설정 거절. 도킹 비활성 close/pending 처리 보완. 기존 all.launch/fleet는 변경하지 않아 운송 자동 기동 없음.
- 검증: 3패키지 빌드/기존117+새24=141시험PASS, 최종 운송24재확인PASS, 실제DDS Domain13/SUBNET의 대역주행 성공·실패·취소·같은UUID조회·중복task거절PASS. 실제USD 읽기 확인. Isaac/실물/전체E2E NOT_RUN.
- 상세 sim/docs/changes/TRANSPORT_SIM_IMPLEMENTATION_20261027.md. 자료 sim/docs/test_results/20261027_transport_integration, 로컬로그 sim/runs/transport_integration_20261027. 공통코드 적용됨/미커밋·미푸시. 다음: 가상운송 차체·센서/마커/바구니정렬→관제인계→선별장이동→교통통합.
- 복원: 이번 추가패키지/메시지와 CMake등록, sim시험·문서만 제거하고 인터페이스 재빌드. 기존 사용자 미커밋 검토문서/전달폴더 보존.

### 2026-10-27 — 운송 가상 하드웨어 연결

- 승인: 사용자 “가상 하드웨어 연결해”. sim 장치/자산/실행/시험 및 상태 문서만 변경. 공통 주행·미션/실물 설정 추가 변경 없음.
- 운송 wheel/cmd_vel/관절 odom/PhysX scan/카메라/TF 연결. transport 기본 false, 운송 단독·3대 fleet 및 장치 launch 추가. 수확 없는 fleet의 평가 선택화, 팔 없는 운송의 공통 월드 물리 사용. 수확 평가/프로파일 검증 보존.
- station 8003 yaw를 기존 출구 edge 방향으로 원본 task/generated spawn에 같이 확정. 카메라 장착은 실물 waffle 기준, 내부 보정 미제공으로 임시 K 명시. 구독 없는 동안 렌더 OFF, 2초 wall lease. 기존 카메라 설정 유지.
- 첫 실제 구동 실패: 원통 바퀴/고정 캐스터 접촉에서 차체 정지. 진단 후 원본 보존 파생 USD의 둥근 단면·캐스터 자유 구름 근사·타이어 마찰 반영. 질량/관성/drive/바퀴 외경·폭 보존. visual instance 재개 렌더 오류도 파생 자산에서 수정.
- 직접 검증: sim 3패키지 빌드, 87 구성/ROS 시험 + 5 USD 검사 PASS. Domain13/SUBNET/CPU 실제 농장 단독 및 3대 실행, ROS 8검사 PASS, 최종60초완료/정상종료. GT 순변위0.1906m/yaw0.4390rad, 카메라 OFF/ON/OFF/ON/OFF. SDK 종료 메뉴 AttributeError2건 별도 기록. 고속/정밀도킹/E2E 미검증. 구식 mock4개 제외 사유와 수정 전 HEAD 재현 포함.
- 상세 `changes/TRANSPORT_VIRTUAL_HARDWARE_20261027.md`, 공유자료 `test_results/20261027_transport_hardware/`, 원본 `sim/runs/transport_hardware_20261027/`. 복원은 이번 sim 변경/새 설정/파생 자산만 제거. 미커밋·미푸시.

### 2026-10-27 — 담당자 브랜치 원본 보존 통합 규칙

- 사용자 지시: 병합 중 수치/판정 변경 및 코드 누락 재발 금지. 프로젝트 AGENTS.md에 원본 커밋 고정, 의존/호출 코드 포함 반영 목록, 최종 실행 설정 비교, 승인된 sim 예외 명시, 동작 검증과 미검증 구분을 추가했다.
- 이번 변경은 작업 규칙/이력 문서뿐이며 실행 코드·수치·판정을 변경하거나 추가 병합하지 않았다. 기존 통합 전체의 동등성을 새로 검증한 것은 아니다. 문서 diff/공백 검사 수행, 미커밋·미푸시. 복원은 이번 규칙과 이력 항목만 제거한다.


### 2026-10-27 — 실측 대기 없는 임시 도킹 마커 배치

- 승인: 사용자 “마커위치 추정…답변 기다리는건 지금 시간없어서 곤란해”. 원본 담당자 브랜치 수치/판정 보존 조건 유지. 실측값 아님을 PROVISIONAL_NOT_MEASURED로 표시.
- 변경: sim/assets/docking_markers의 배치표/PNG3개, runtime/docking_marker_scene.py·run_fleet.py·fleet_config.py, transport_fleet.json, 정차 렌더 도구와 USD 검사. 이전에는 도킹 마커 없음; 이후 운송3대 fleet에서만42/41/40을 모델에 부착. 원본USD/공통/실물/마커32 변경 없음.
- 검증: PNG3개·실제Isaac 정차RGB3개 모두ID검출, USD장착/부모이동/물리보존2검사 및 기존19검사 PASS,2패키지빌드 PASS. 초기GPU접근/시험clipping/mimic API 실패원인·로그보존. 최종렌더Error0. 실제주행/도킹전환/라이다/바구니정렬/E2E 미검증.
- 발견: 선별장 자산(-7,14)과 그래프8004(5,13.25) 불일치. 자동이동하지 않고 후속정합항목으로기록.
- 상세 sim/docs/changes/DOCKING_MARKER_PROVISIONAL_20261027.md, 공유 sim/docs/test_results/20261027_docking_markers/, 원본 sim/runs/docking_markers_20261027/. 되돌림:transport_fleet의docking_markers항목제거. 미커밋·미푸시.

### 2026-10-27 — 도킹·바구니 정렬 실제 검증

- 승인: 사용자 “도킹 바구니 정렬 검증 시작해”. 공통 farm_docking27파일 원본9686aca와 동일, 선택42/41프로필 숫자 변경0. Domain13/SUBNET/CPU/headless 실제센서·PrecisionMotion 실행.
- 결과:42접근 성공. 기존41임시마커/라이다면 약20cm 불일치 및TF시각오류로실패. 시험복사본만41면을 맞춘 경우 최종20cm 도킹 성공했으나 바구니겹침72.84%/중심오차10.36cm/높이차5.65cm로정렬실패. 운영마커/로봇USD/공통판정불변. 연속E2E·인계이벤트아님.
- sim수정:팔비활성 student 카메라 호출2곳None보호; 운송CameraInfo reliable선택으로공통구독연결; 평가용프레임/주기선택진단파일추가. 진단/분석/시험도구·명목개구부평가설정·회귀추가. 다른로봇기본QoS/기록주기보존. GT는파일평가만.
- TF진단:원본fresh()반환값불변 sys.monitoring으로 음수age -16.7ms 184회확인. 성공실행에서도발생; 이전실패순간내부age미계측한계명시. 해결완료아님.
- 검증:회귀24/3패키지빌드PASS. 시작오류2/카메라frame오류1/도킹실패2·성공2로그보존.42종료시SDK-11별도기록. 상세DOCKING_BASKET_ALIGNMENT_20261027.md 및 test_results/20261027_docking_alignment.
- 복원:이번sim연결diff/선택진단·평가·시험파일만제거,선행미커밋통합보존. 실물파일변경/커밋/푸시없음.

### 2026-10-27 — 최신 도킹 재시험 실패, 진행 상태 정정

- `final100/41/result.json`: status6, success=false, stopped=true, `모터 제어권 상실: LEASE_EXPIRED`. 공통 제어 스케줄 지연21030.1ms, odom/scan 수신 공백22~23초. 양 sim 어댑터에도 같은 시각 telemetry 중단 경고가 기록됐다. 지연의 근본 원인은 미확정이며,100ms 전달 대기로 안정화 완료됐다고 보지 않는다.
- 같은 실행에서 `on_odom`의 미래 시각 거절1회(-16.7ms)도 남았다. 최종100ms 설정은 검증 미완료/실패 상태. 앞선50ms 설정의41 두 회 성공과42 한 회 성공은 이전 시험 결과로만 유지한다.
- 대화 중단으로 runner가 사라진 뒤 남은 해당 시험 전용 ROS 프로세스 그룹을 확인하고 SIGINT 종료했다. Isaac은 기존 로그상 종료 완료. 최신 실패를 성공으로 집계하지 않는다.
- sim 전용 marker41 면 보정(-0.455→-0.251m), 운송 센서 시계 대기0.1s/유한 큐/영상 발행 고갈 수정. 공통27파일·수치·판정·원본 USD 보존. 회귀31PASS,3패키지빌드PASS,실행 안정화 미완료. 복원/실물 영향 없음/승인 근거는 상세 보고서 참조.

### 2026-10-27 — 72.1% 겹침 바구니 독립 낙하 시험

- 사용자 “그 조건만 … 테스트” 승인으로 원본 USD를 변경하지 않고 개방된 배출구/상단 덮개 조건의 한 알 낙하만 추가했다. 공통 코드·도킹·인계 성공 판정 변경 없음.
- 실제 성공 도킹 상대 자세에서 위치25×자세3=75조건: 수용60, 외부 낙하10, 가장자리 부근잔류5. 중심 정렬 비교75/75수용. CPU60Hz/120Hz 각150조건의 개별 분류 모두 동일. 80%는 선정한 표본 수용률이며 실제 일괄 배출 확률로 해석하지 않는다.
- 원본 자산4개 SHA256불변, 실제 CPU/MBP확인,문법/diff검사통과. Isaac 종료 잔존은 결과 저장 뒤 정리(exit143/124); 물리 결과와 별도 기록. 이번 시험 종료.
- 구현 sim/tools/check_partial_basket_transfer.py, 분석 analyze_partial_basket_transfer.py. 상세 sim/docs/changes/PARTIAL_BASKET_TRANSFER_20261027.md, 공유 sim/docs/test_results/20261027_partial_basket_transfer/, 원시 sim/runs/partial_basket_transfer_20261027/.
- 이번 한 알 시험은 동시 배출·덮개 구동·실물·전체 E2E를 검증하지 않았다. 현행72%조건의 무조건 인계 성공 전환은 하지 않음. 원복은 이번 독립 도구/자료만 제거. 미커밋·미푸시.

## 2026-10-27 — D-065 72% 도킹 승인 및 시뮬 인계·이격

- 승인: 사용자 “72% 겹친 상태를 정상도킹이라고 보고 다음단계 가자”. 완전포함 평가에서 최소72%+높이양수+기존정지0.8초로 변경, 이전 물리낙하 실패기록 보존.
- 대상: config/docking/basket_alignment_evaluation.json, transport.json/transport_fleet.json; sim_devices basket_alignment.py/mechanical_ros.py/ros_adapter.py; sim_runtime basket_monitor.py/fleet_config.py/run_fleet.py; 도킹 분석·준비·실행 probe 도구 및 신규 probe_sim_handoff.py; 관련 시험/보고서.
- 실물 영향 없음: 공통 도킹27파일9686aca원본일치, USD/과실4자산hash불변, 공통FSM·20cm도킹·25.2cm이격·오차수치 보존. 기구는 추상 상태만 변경하며 실수령량을 만들지 않는다.
- 검증: 36시험PASS,3패키지빌드PASS, 문법/diff검사. 기록재평가5.183초PASS. 새 Isaac CPU/Domain13/SUBNET 실제 DOCK41→가상인계→CLEAR 성공(72.4506%,정지1.10초,후진24.4198cm). freshness3218회거부0. SIGINT 종료 gate1/precision-2는 별도 종료오류로 기록; 업무 중 실패 없음.
- 미검증: 전체TransportPickup/TransferEvent DDS/관제/선별장 이동. 다음 운송환경·목적지 정합 후 이동 연결. 상세 changes/BASKET_HANDOFF_ACCEPTANCE_20261027.md, test_results/20261027_basket_handoff/.
- 원복: 가상기구enabled와fleet평가연결 해제, minimum_coverage=1.0 복귀. 기존공통/자산 변경없음. 미커밋·미푸시.

## 2026-10-27 — D-066 선별장 실제 위치 정합·운송 Nav2 연결

- 승인: 사용자 선별장이동연결/성공후커밋푸시 및 실제모델위치에접근점·경로맞추기 선택. 8004 (5,13.25)→(-7,13.25),yaw북쪽,연결9019→9001. 원본task/scout_harvest 및생성station/역할graph만수정,USD불변.
- 대상: transport_runtime/nav2_transport/transport_destinations/transport_sources 및도킹시험fixture; transport_navigation.launch.py와package의기존Nav2의존성선언; prepare_sorter_route_trial/analyze_sorter_route_trial와기존실행probe연결; test_sorter_navigation_config; config패키징/보고서.
- 실제실행: Domain13/SUBNET,CPU MBP60Hz,도킹→가상인계→이격→선별장CheckRoute 2회성공. Nav이동141.34/147.37초,실제오차11.19/9.82cm별도기록. 업무중오류없음. 종료뒤SDKchild-11,gate1,precision-2는잔존종료문제로보존.
- 보존/검증: 공통실행소스이번턴변경없음,활성RPP원본지정값런타임일치,원본도킹수치와27파일/4자산hash불변,75단위회귀PASS·371경로PASS·2sim패키지빌드PASS. 비활성DWB stateful런타임미선언은검증한계로명시.
- 실제도착/정지와추정오차/실과실수량미측정/관제전체업무미검증을구분. 상세 changes/SORTER_ROUTE_CONNECTION_20261027.md,공유test_results/20261027_sorter_route/. 원복은원본접근점/연결복귀후재생성및신규운송navigation조립해제. 기존도킹/바구니수정불필요.

## 2026-10-28 — D-067 실물 수확 인계 공통 코드 통합

- 승인: 사용자 “1번부터 진행해”. 대상 harvest_robot/farm_navigation/farm_common/farm_bringup 및 새 farm_arc_controller/farm_wall_controller/jetson_harvest_interfaces, 실물 참고 JSON6개·wall capture도구, 관련시험. 파일별 SHA와 제외이유는 보고서/manifest 참조.
- 변경 전 인계 차체/복구 코드 없음 → 원본 e135cde 모듈과 의존성 반영. 실물 원본 생성설정 동일, 원본 허가대기/장치실패/취소 정책 보존. 기존 거리예산·교통·D-059 조건 유지. 실물 실행기능은 명시선택, 기존 실물/시뮬설정463파일불변.
- 검증: 7패키지빌드,438검사PASS/5SKIP. 기존 교통그래프불일치21오류는변경전에도재현, 임시자료정합시21PASS. 운영설정미수정/Isaac미실행/전체사이클미검증.
- 다음: 시뮬시계·TF·가상기구·출력소유권 연결 및교통자료정합. 복원은manifest의이번파일만ea25693복귀/신규파일제거후재빌드,사용자Frontend보존. 상세 changes/HARVEST_HANDOFF_INTEGRATION_20261028.md, test_results/20261028_harvest_handoff_integration/. 미커밋·미푸시.

## 2026-10-28 — D-068 수확 인계 환경·가상배출 연결

- 승인: 사용자 “다음 작업 해”. 변경: 공통 harvest launch/Runtime/server_config/trace, arc·wall odom 인자·Spin 프레임; sim harvest_transfer_ros/arm telemetry/adapter/fleet; 준비·실행·검증도구; 교통 snapshot/구역/manifest 및 시험. 정확한22파일과 해시는 test_results/20261028_harvest_handoff_connection/changed_files.json.
- 전후: 실물고정시계/odom 및 수확가상배출미연결 → 환경시계/프레임 선택, 실측팔준비·바구니평가 기반 Discharge. real 원본 생성설정동일/기존실물설정·USD불변. 기본프로필은미활성,생성묶음선택. 기존도킹72%판정·수치유지.
- 교통: 기존선별장8004이전위치등록불일치수정, 해당2구역·참조·bounds동기화 및 graph_02/zone_02증가. Frontend미변경/상대등록갱신필요. 교통검사21포함 전체469PASS/5SKIP·6패키지빌드PASS.
- 실제시험: Domain13/SUBNET CPU MBP60Hz, 정차연결/거절조건PASS 및72.6426%겹침2.90초증거로 운송덮개열기→수확Discharge성공→덮개닫기PASS. 실제재도킹·원호이동·수확윈도우·관제전체사이클은미검증. 종료후SIGINT예외/SDK-11잔존 별도보존. 최초odom이름준비실패와cache권한실패도보존.
- 복원: 이번파일만작업전해시내용으로되돌림,교통snapshot/zone/manifest동시복원,1단계통합/Frontend보존. 상세 changes/HARVEST_HANDOFF_CONNECTION_20261028.md, 공유 test_results/20261028_harvest_handoff_connection/. 미커밋·미푸시.

### 2026-10-28 — SEC01 윈도우/관제 인계 진입 시험 및 시뮬 최초 영상 지연 보완

- 구분: sim환경연결/진단. 승인근거 사용자 “다음 작업해”, D-069. 대상 prepare_harvest_handoff.py, run_handoff_window_trial.py, probe_handoff_window.py, student_session.py, ros_adapter.py 및 결과/문서. 실물·공통 수치/정책/자산/Frontend 원본은 추가변경 없음.
- 전후: 상태보고미설정→원본보고연결; 수확중 최초검출초기화/압축저장→시작준비시추론초기화/무손실무압축저장; 동일표본odom→TF 발행을 TF→odom으로 정렬(수신순서보장아님). 실제 최대inventory프레임1.591→0.207초, NPZ약5.49→16.57MB. 원본timeout유지.
- 실제4시도 중 최종 윈도우정상완료·관제DockTransfer접수·후진원호완료. 벽정렬 2cm/s명령에 실제약2.667cm/s과속, 원본2.5cm/s감시로 DEVICE_FAILED. 105없음. DOCK_READY/운송/배출/복귀 미완료, 바퀴보정계수미변경. 72검사+41subtest 및 farm_sim_devices빌드PASS. Frontend HTTP fastapi미설치 수집실패와 ROS/SDK종료예외 별도기록.
- 자료 sim/docs/changes/HANDOFF_WINDOW_TRIAL_20261028.md, test_results/20261028_handoff_window/, runs/handoff_window_20261028/. 복원은 이번모듈차이만되돌린뒤시뮬장치재빌드; 직전공통통합·가상장치는보존. 미커밋·미푸시.

## 2026-10-28 — D-070 인계 연쇄, 거리 허용오차, 정지/시험 순서 보완

- 승인: 사용자 “쭉쭉 진행해” 및 “거리 허용오차 반영: 하한 약69.4%”. 기준ea25693+D067~069 미커밋. 실물/공통 제어 정책 추가변경 없음.
- 대상: sim_devices/{wheel_servo,ros_adapter,mechanical_ros}.py, sim_config/config/{harvest.json,docking/basket_alignment_evaluation.json}, sim/tools/{run_handoff_window_trial,probe_handoff_window,prepare_pickup_trial,probe_handoff_return}.py, 대응시험 및 문서.
- 변경: 바퀴ki4→1/정지target0; 지연odom 발행 전에 동일측정TF; 원본TriggerDevice로 lid_open/lid_close/stop 연결; 닫기에는 정렬재판정 대신 소유권/최신정지 확인; 인계하한72→69.3684% 승인 적용. 높이/0.8초/수량미측정 유지.
- 실행환경: 임시42마커를 기존통로에 정합한 시험 layout. 원본USD/운영layout 불변. 선별장 이격의 지도yaw0→π/2,노드17→15 대신8004→9001; 기존sim목적지/그래프에서 읽음. 제어값 변경과 환경좌표 변경 분리.
- 실제: ki1단계검사 및pickup1~10로그보존. pickup7양쪽인계/복원SUCCESS(열기71.9349%). 이후수확먼저복귀105는 정지운송과물리간섭;운송먼저출발로시험순서수정. pickup8벽정지후0.537도, pickup9map추정오차에따른복원실패, pickup10LEASE_EXPIRED미해결. 선별장후속/전체SEC01/신규예찰은미검증.
- 검증: 기존7개시험파일52개PASS,추가정지보정후wheel_servo5개PASS;장치/config빌드PASS;5정밀프로파일원본대비제어수치/불리언차이0. 종료SDK/ROS예외별도보존. 실행프로세스정리,미커밋/미푸시.
- 복원: 해당sim변경만개별역적용,ki4/minimum_coverage0.72 및PI정지정책복구후재빌드. 기존누적통합/Frontend/다른미커밋파일을reset하지않음.
- 상세: changes/HANDOFF_CYCLE_20261028.md, changes/HANDOFF_ALIGNMENT_REVIEW_20261028.md, test_results/20261028_handoff_cycle/.

## 2026-10-28 — 인계 복귀/제어권 만료 원인 계측

- 사용자 “확인해 왜문제발생하는지”, 기준ea25693+D067~070미커밋. sim도구 `probe_handoff_window.py`, `trace_docking_freshness.py`와 분석/문서만 변경. AMCL/scan/map→odom/staticTF/monotonic 기록 및 Python/native 경과·CPU시간·갱신간격 계측, 동기파일쓰기→비동기큐. 공통반환값/실물설정/판정/USD불변.
- Isaac2회 양쪽인계/복원SUCCESS. odom최대4.26/3.96mm vs AMCL Y최대5.46/4.63cm로 위치보정오차분리. 약5cm위치차이에도 라이다거리장점수가 비슷한 지도방향 관측제약 확인, 세부설정별인과는미확정. LEASE_EXPIRED추가미재현, 실제계산/대기 원인미확정.
- Python3.12 PY_UNWIND local등록오류는계측수정, Domain환경누락은시작전거절후올바른환경으로재실행. py_compile/모니터등록/실제2회/오프라인분석2회검증. 제어기회귀/실물/전체사이클미실행. 종료정리ROS예외별도보존.
- 상세 changes/HANDOFF_DIAGNOSIS_20261028.md; 공유 test_results/20261028_handoff_diagnosis/; raw runs/handoff_diagnosis_20261028/. 되돌리기는 두도구의이번계측부분만역적용,기존누적통합보존. 미커밋/미푸시.

## 2026-10-28 — 동일 조건3회 재시험 및 gate 수신 계측

- 승인근거 사용자 “다시 테스트해봐 재현조건이뭐야”. sim/tools/trace_motion_gate.py추가, run_handoff_window_trial.py의 gate실행만계측진입점연결. sys.monitoring으로실제공통함수호출전후/기한/결과기록, 비동기파일쓰기. 공통함수교체/반환값/실물설정/제어판정변경없음.
- 실제3회: 성공1, 벽정렬정지후각도초과2. 목표도착후0명령/target0인데USD방향0.194/0.174°추가변화, 외부벽각오차0.541/0.606°로0.5°초과. 내부판정표본미기록한계명시. AMCL복원도달1회/성공, 운송LEASE만료0회; 이전오류해결로간주하지않음.
- 실행설정동일(경로/journal제외), 시험중소스불변. py_compile/실제3회계측/프로세스종료확인. raw runs/handoff_repeat_20261028/, 공유 docs/test_results/20261028_handoff_repeat/, 보고 changes/HANDOFF_REPEAT_20261028.md. 종료ROS예외별도보존, 미커밋/미푸시.
- 복원: runner의gate시작을기존ros2 run farm_docking motion_gate로되돌리고새계측파일만제거. 기존누적변경보존.

## 2026-10-28 — 과거 도착 판정 정합과 새 인계 경로 비교

- 사용자 기존수정확인요청. 문서/비교JSON만갱신,실행코드변경없음. D-049원본ControllerServer유지/회귀6PASS. D-029일반잔차비차단유지이나실물인계원본에서별도최종validator가추가된경로확인.
- 벽Nav2 .5초완료와후단 .8초정지후재검사로시점다름,수치동일. 시뮬정지움직임과공통인계중복완료판정의결합으로분류보완. 물성단독원인설명정정. 상세 HANDOFF_REPEAT_20261028.md후속비교. 새Isaac/실물미실행,미커밋·미푸시. 문서역적용으로복원가능.

## 2026-10-28 — 정지 후 미세 바퀴 구름과 물리 계산 비교

- 승인 근거: 사용자 “확인해봐 원인”. sim/tools/check_wheel_stop_diagnostic.py 및 진단 보고/자료 추가, PROJECT_STATE 갱신. 운영 코드·공통/실물 설정·USD 파일 변경 없음. 비교용 gain/solver는 Isaac 세션에서만 변경.
- 실제 로그 wheel yaw와 world yaw 일치 확인. 축소 물리4조건에서 damping10배 개선 없음, velocity solver4→16은 정지0.5~3초 잔류yaw 약59~62% 감소. 접촉/구동 수치 계산 영향 증거이며 정확한 접촉 원인/실제 인계 해결 확정 아님.
- py_compile 및 실제 Isaac4조건 완료. 종료 단계 프로세스 잔류는 SIGTERM 정리. 상세 changes/WHEEL_STOP_DIAGNOSIS_20261028.md와 test_results/20261028_wheel_stop_diagnosis/. 커밋/푸시 미수행. 복원은 이번 진단 도구/자료/문서 추가분만 제거.

## 2026-10-28 — 시뮬 인계 각도 0.8° 임시 완화 (사용자 명시 승인)

- 대상 prepare_harvest_handoff.py/run_handoff_window_trial.py: 실행복사본 angle_tolerance 0.5→0.8°, source_adaptations와fixture에원본/적용값/승인/임시예외기록. 실물파일/공통코드/물리수치불변. 이유시뮬정지후미세회전에대한임시허용.
- py_compile/생성JSON한필드차이/실행ROS0.8°/실물해시유지확인. 실제1회정렬·도킹·가상인계·운송이격성공, 이후수확복원WINDOW_REALIGN_REQUIRED로전체실패. 상세 changes/HANDOFF_ANGLE08_20261028.md와 test_results/20261028_handoff_angle08/.
- 복원: 준비도구의각도override제거후실행묶음재생성,과거시험자료보존. 커밋/푸시없음.

- 0.8°시험 후속 읽기분석: WINDOW_REALIGN_REQUIRED도입cf870da/현재원본유지확인. 외부동시로그로실제목표1.36cm 대 map추정12.14cm확인,약10.82cm위치추정불일치. 도구/운영수정없음,재구성JSON·보고·상태문서보완. 상세 HANDOFF_ANGLE08_20261028.md. 다음오차발생시점확인.

- 추가읽기분석: 사용자위치불일치원인/과거크기질문. 현재AMCL직접오차후반10.9cm증가와odom최대4.62mm대조,이전평면최대6.16/4.80cm비교. 시계열JSON/AMCL진단자료/보고갱신만수행. 상세 HANDOFF_ANGLE08_20261028.md,운영변경없음.

## 2026-10-28 — 위치 불일치 재현 반복 시험

- 사용자재현시험요청승인.기존운영코드/설정은유지하고동일0.8°조건3회+카메라중단보충1회실행.분석스크립트/공유자료/보고/PROJECT_STATE추가만수행.
- 성공2/복원추정오류1/카메라중단1.10cm급미재현이나6.38cm추정오차로실제목표0.95cm인데복원거절하는현상재현. AMCL최대2.61/6.42/2.64/3.98cm.공통·실물·물리설정불변,동일조건파일정규화/소스해시불변확인.
- 상세changes/LOCALIZATION_REPEAT08_20261028.md,공유test_results/20261028_localization_repeat08/.종료정리확인,미커밋·미푸시.복원은이번진단문서/자료추가분만제거하고원시로그보존.

## 2026-10-28 — 업데이트 전후 위치 추정 실행 조건 검토

- 사용자질문에따른읽기감사/문서·증거JSON추가. 기존SEC캠페인은태그보정true/farm_tag_amcl/수확실제46회적용,최근인계시험도구는false/nav2_amcl. 이전4~6cm기록도통합후임을명시해“원래심했다”해석제한.
- 기본AMCL설정·지도·태그AMCL소스92ad63a/ea25693대비동일,운영코드/설정변경없음. 관련TF발행/지연·구동·경로차이도기록. 상세changes/LOCALIZATION_UPDATE_AUDIT_20261028.md.복원은이번문서/자료추가분만제거.미커밋/미푸시.

## 2026-10-28 — 인계 시험 태그 보정 연결 복원

- 사용자임의비활성지적/기존조건보존지시. run_handoff_window_trial.py를기존simharvest런치/tagtrue로복원,sim harvest.launch에handoff/초기spawn선택연결,기존태그검사fixture기본인자추가. 공통·실물·AMCL수치·권한정책불변.
- 첫준비실행은station/spawn혼동으로실패해원래업무스테이션보존하도록수정. 재실행태그APPLIED3회확인. 인계·운송이격통과하지만수확복원위치오류남음(실제목표2.02cm/map9.33cm).동작연결복원만완료,위치문제해결선언안함.
- py_compile/빌드/기존런치6검사/실제시험/종료정리확인. 최초검사로그권한오류별도보존. 상세changes/TAG_RESTORATION_20261028.md.복원범위는이번sim3파일·문서/자료만,이전태그OFF조건을정상기준으로사용하지않음.미커밋·미푸시.

## REAL-ROBOT-ISSUE-SHARE-20261028 — 실물 담당자 전달 문서·로그 패키지

- 사용자 요청: 벽 정렬 완료 후 각도 초과와 인계 복귀 AMCL 오차를 Markdown 및 근거 로그 ZIP으로 작성.
- 대상: `sim/docs/test_results/20261028_real_robot_issue_share/인계_주행_검토요청.md`, 동일 폴더의 로그 복사본·manifest, `sim/runs/real_robot_issue_share_20261028.zip`.
- 기존 시험 결과를 전달용으로 정리했다. 0.5초/0.8초 별도 검사, 0.5° 실패와 시뮬 임시 0.8°의 구분, 태그 ON이지만 인계 중 보정 0회, 실제/추정 목표 거리 및 외부 재구성 한계를 명시했다.
- 검증: 복사 SHA-256, JSON/JSONL 파싱, 문서 상대 링크, ZIP CRC 정상. 신규 주행 시험 없음. 코드·설정·실물 영향 없음, 미커밋·미푸시.
- 복원: 이번 전달 문서 폴더·ZIP 및 이 이력만 제거하면 된다. 원본 시험 로그는 보존했다. ZIP은 검토 자료이며 저장소 적용 패치가 아니다. 수신자는 `unzip real_robot_issue_share_20261028.zip -d ./handoff_review`로 별도 폴더에 풀어 열 수 있다.


### HCR3A-INTEGRATION-20261028 — 원본 선별 인수·물리 검증·공통 계약 연결

- 요청/범위: 전달본의 레인 투입 이후 선별만 검증. 운송/배출 경로 제외. vendor 원본 보존, 시험복사본만 실행.
- 승인: AGENTS 공통 변경 절차에 따라 3개 인터페이스 파일 및 hcr_sorting15파일 제안; 사용자 “공통 연결 변경 적용” 후 반영. 미승인 상태로 공통 파일을 변경하지 않음.
- 파일: robot/ros_ws/src/farm_interfaces/{action/SortBatch.action,msg/SorterStatus.msg,CMakeLists.txt}, robot/ros_ws/src/hcr_sorting/15파일, sim/vendor/hcr3a_20261008/, sim/tools/probe_hcr_sorting.py, 상세보고/소스대응/패치 및 상태·결정 문서.
- 전후: 로컬 선별 ROS 타입/서버 없음→원본 namespace를 farm_interfaces로 맞춘 서버 추가. 기존 공통업무/실물 설정/주행 판정 불변. core/Modbus는 원본과 동일. 실물 공통패키지에 additive 타입/서버가 생기며 자동 launch되지 않음.
- 검증: ZIP275파일 무결성, 15파일 namespace 외일치, 타입필드/순서Frontend일치, 별도2패키지빌드, 오프라인32PASS, 실제ROS+모의장치 완료/중복/취소PASS, 실제RGB·팔물리 취소완료수량red1PASS. 정상ROS물리배치 SUCCESS red2/yellow2, 물리4/4·잔량0도 확인.
- 실패: 원본8개중7개 보관후SUCCESS(잔여red1의ROI빨강7.07%<8%). 높이32px변경은3개후MIXED정체; 원본/농장에채택안함. 단독CPU240Hz/농장CPU60Hz구분.
- 미완료: 농장투입실제prim바인딩, station좌표변환/자산배치, 기존실행루프/reset/pause, Frontend 전체연쇄. 정답과실위치 기반 보조집기는 기능근사 검증으로 명시.
- 복원: 실행종료후 common_integration.proposed.patch 역적용(후속변경없을때), 새sim도구/vendor제거. 기존사용자미커밋변경에는 git reset/clean을 사용하지 않음. ROI시험변경은 runs복사본에만 있어운용복원불필요.
- 근거: sim/docs/changes/HCR3A_INTEGRATION_20261028/REVIEW.md, sim/runs/hcr3a_intake_20261028/. 미커밋·미푸시.
# 2026-10-28 — 농장 HCR 선별장·팔 배치 및 도킹→선별 연결

- 구분/승인: sim 전용. 사용자 “기존 농장맵에 선별소 위치에 배치 후 도킹→선별 시퀀스”, “실물과 동일한 방식”. 사전 방향 정렬 활성화 제안은 미적용, 공통/실물 소스 수정 없음.
- 대상: `sorter_scene.py`/`sorter_runtime.py`, fleet 설정·실행 훅, HCR USD/config, 기존 과실 이동 API, runner/probe, 라이다 진단. 전체 목록 `docs/changes/HCR3A_FARM_SEQUENCE_20261028/changed_files.json`.
- 전후: 별도 HCR 단독 World에서 농장 공통 CPU60Hz World로 연결. 기존 선별장만 세션에서 대체하고 원래 과실 ID를 가상 레인 투입한다. 원본 HCR RGB/선별/Modbus/ROS 판정 유지. 배출 기구 물리 제외.
- 실패 수정: 선별장 투입면을 기존 접근 edge와 원본 이격거리/센서 offset에 맞춰0.358m 배치. `ros_adapter.py`의 즉시 TF 선발행으로 1프레임 미래 TF 오류2회 발생하여 기존0.1초 대기 안에서 TF0.05초→odom0.1초로 나눔. stamp/값/odom 지연/공통 freshness 불변.
- 검증: 단위14PASS, sim2패키지 빌드/문법/관련 diff 검사 PASS. 최종 실제 attempt09 접근→도킹→기존 과실2개 투입→이격→SortBatch SUCCESS(red1/yellow0), 약96.95초. TF5851검사 거절0. 노랑 잔류1개 및 이전 실패 원시 로그 보존. 이후 스테이션 복귀는 추정오차25.6cm로 실패, 전체 runner 성공 아님.
- 한계/다음: 검출 성능·다중 배치·pause/reset 실제 시험·Frontend 선별 자동 워커 미완료. 복귀 위치 추정 원인 분리 필요. 실물 영향 없음. 미커밋·미푸시.
- 복원: fleet에서 `sorter_config` 미지정 시 기존 농장 실행. 원본 USD 저장 안 함. TF 수정은 이번 시계 대기 변경만 되돌리고 이전 장치 통합은 보존. 보고 `docs/changes/HCR3A_FARM_SEQUENCE_20261028/REVIEW.md`; 실행/압축 해제는 DELIVERY.md.
# 2026-10-28 — 선별장 위치 추정25cm 오차 로그/지도 감사

- 구분: 조사·문서. 사용자 AMCL/odom/TF 정합 확인 요청. 실행 코드/지도/파라미터 변경 및 실제 재시험 없음.
- HCR로 교체·재배치된 환경에 예전 선별장 점유지도를 그대로 사용한 누락 확인. 실제 전면 ray와 기존 점유셀 평균16.17cm 차이. 접근2cm→정지8cm→이격 회전25.6cm인 반면 마지막 wheel odom 위치오차1.4cm. TF 마지막 수정 전 attempt06에서도24.69cm 발생.
- 지도 불일치는 확인,25cm의 전체 인과는 새 지도 단일변수 시험 필요. 원시 TF/전체scan 부재와 이동 중 시간 대응 근사 한계를 기록. 근거 `docs/changes/SORTER_LOCALIZATION_AUDIT_20261028.md`, `docs/test_results/20261028_sorter_localization_audit/`.
- 실물 영향/복원: 실행 변경 없음, 조사 문서/자료만 추가. 다음 모델에 맞는 지도와 동일조건 비교. 미커밋·미푸시.

### 2026-10-28 — HCR 선별장 지도 갱신 (시뮬 전용, 사용자 승인)

- 승인: “업데이트해야지 지도도 업데이트해야되고”. 대상: sorter_integration.json, 신규 hcr_farm_map.yaml/png/manifest, build_sorter_map.py, run_sorter_cycle_trial.py, probe_sorter_cycle.py, test_sorter_map.py 및 보고/자료.
- 전: 새 HCR 모델에 이전 선별장 점유지도. 후: 원본 USD 고정 단면 지도 선택/입력해시 검사, raw AMCL/TF/scan/odom 기록. 기존 지도와 외벽/베드/경로 보존. 실물/공통 코드·AMCL/도킹 수치 변화 없음.
- 검증: 지도 회귀4PASS, 도구 py_compile/diff체크PASS, 실제 attempt10 도킹/투입/이격/선별성공·복귀실패. 최종추정20.30cm, odom1.28cm. 이전25.60cm보다 감소했지만 해결 아님. rawAMCL도20.31cm; TF합성/status1.26µm 일치. 상세 SORTER_MAP_UPDATE_20261028.md.
- 원시 sim/runs/hcr3a_farm_cycle_20261028/attempt10, 공유 test_results/20261028_sorter_map_update. 되돌림: 시험 지도 선택과 검사 원복(오래된 지도 불일치 재발), 기존 count_test 지도 자체 수정 없음. 미커밋·미푸시. 다음 회전중 AMCL 관측/입자 수렴 원인 분리.

### 2026-10-28 — 운송 AMCL 갱신 간격/미실행 모델 잔존 수정 (시뮬 전용)

- 승인근거: 사용자 AMCL오차개선요청. 파일: nav2_transport.yaml 두AMCL값, run_sorter_cycle_trial.py 단독씬레이어/원본값차이기록, replay_sorter_localization.py 및analyze_amcl_diagnosis.py, 활성예찰보존검사/보고자료.
- 전: 25cm/0.2rad마다AMCL관측갱신, 단독운송씬에미실행예찰모델잔존. 후: 5cm/0.05rad갱신·잔존모델제외. 실물원본및공통코드/실패판정/속도·시간제한불변. 의도적인시뮬AMCL수치차이명시.
- 검증: 원래센서재생20.31cm→2.00cm; 실제attempt15 선별장회전후3.46cm/전체평균3.19cm·최대7.66cm. 스테이션도달후최종제자리회전중10초병진진행검사105. 전체성공아님. 준비오류11/12·scan stale13·모델제외만14 실패기록보존. TFfuture5,장거리wheel odom99cm도별도기록.
- 5검사PASS/py_compile/diffPASS. 보고changes/AMCL_DIAGNOSIS_FIX_20261028.md,자료test_results/20261028_amcl_diagnosis/. 되돌림: AMCL두값0.25/0.2복원 및비교옵션--keep-unused-scout. 원본USD/기존미커밋보존. 미커밋·미푸시.

### 2026-10-28 — 통합 상태 커밋 스냅샷

- 사용자 “지금상태로 커밋푸쉬” 요청에 따라 수확 인계·HCR 선별 연결, 지도 갱신, 시뮬 운송 AMCL 개선 및 시험 자료를 저장한다. 기준 HEAD `ea25693`, 원격 fetch 후 `origin/main`과 동일함을 확인했다.
- 최신 실제 시험은 도킹→투입→이격→선별→스테이션 위치까지 진행했으나 마지막 회전에서 105로 실패했다. 예찰부터 시작하는 전체 연속 사이클은 미검증이며, 정상 완료로 보고하지 않는다. 선별 잔류 노랑 1개와 장거리 odom 오차도 남아 있다.
- 관련 오프라인 검사 57개 통과 확인. 최초 ROS 환경 미설정으로 수집 실패했고, 환경 로드 후 54개 통과/3개 로그 디렉터리 쓰기 오류가 발생했다. 로그 경로를 `/tmp`로 지정하여 해당 launch 파일 6개 모두 재검사 통과했다. 실제 시뮬 시험은 추가 실행하지 않았다.
- 프로젝트 반영 코드·설정·자산·선택 시험 자료를 포함한다. 루트 `Frontend/`와 원본 ZIP, gitignore 대상 `sim/runs/` 원시 실행 자료는 로컬에 보존한다. 이전 항목의 미커밋·미푸시 표시는 각 기록 시점의 상태다. 최종 원격 반영 여부는 push 후 원격 HEAD로 확인한다.
- 다음 작업: 최종 회전의 진행 검사 105 해결 후 예찰→수확→운송→선별→양 로봇 복귀 전체 연속 검증. 이번 저장 작업에서 제어 코드·판정·설정을 추가 변경하지 않았다.

### 2026-10-28 — 스테이션 마지막 회전 105 수정·복귀 성공 확인

- 사용자 마지막 회전105해결 요청. 기준18d0e00. 시뮬 운송 `SimpleProgressChecker → PoseProgressChecker`, 각진행0.5rad 명시. 병진0.1m/10초/회전0.3rad/s/도착·정지 기준/실물·공통 소스 보존. fixture에 원본 대비 의도적 검사 차이 기록.
- 원인: 마커 단계는 기존부터 생략하지만 RPP 목표방향 맞추기는 실행. 기존 병진전용 검사에서10초 넘는 정상제자리회전도105. 이 설정은 ea25693부터 같았고 AMCL 수정이 바꾼 값 아님.
- 설치된Nav2 플러그인7검사PASS(정상회전/정지실패/미세흔들림/직진), 지도·씬5PASS/문법·diffPASS. 실제 Domain13/SUBNET CPU60/render30 attempt01: 도킹→투입→선별→스테이션복귀SUCCESS, 마지막회전12.40초/105없음, marker_stage=SKIPPED_SIM_POLICY. 전체260.56초/복귀159.84초.
- 잔여: 마지막map추정오차1.91cm/3.85°, 실제차체3.89cm/8.74°로방향잔차존재. 선별빨강1·노랑잔류1. 전체예찰부터연속사이클미검증. 성공후SIGINT정리에서gate context오류exit1/precision KeyboardInterrupt−2기록; 전체runner/probe/운송/Isaac exit0,모든시험프로세스종료.
- 상세 `sim/docs/changes/STATION_RETURN_105_FIX_20261028.md`, 공유 `sim/docs/test_results/20261028_station_return_105/`, raw `sim/runs/station_return_105_20261028/`. 복원은운송checker를Simple로/각도항목제거(긴회전105재발가능). 미커밋·미푸시.

### 2026-10-28 — SEC01 한 사이클 시험: 예찰 성공, 수확 첫 접근 실패

- 사용자 한사이클1회 요청. 새 시뮬 시험기에서 기존 예찰/수확/Frontend인계worker/선별 액션을 한세션으로 연결. CPU60/render30, Domain13/SUBNET, 예찰·수확태그ON. 기존 실제과실만 가상이동하도록 인계 어댑터 연결; 선별용 초기적재fixture 제거. 실물·공통 코드 변경 없음.
- 준비오류3건(새지도 태그해시, vision Python torch환경 누락, 교통OFF에서없는예찰status대기)을 기록/수정. 업무수락은 attempt04의1회뿐. 21:25:26~21:32:09: 예찰SUCCESS 5구간/9윈도우/expected13, 예찰복귀와수확W001접근동시실행, 북쪽공유통로정체로수확실패. 최종 CANCEL_UNCONFIRMED, Nav2 Failed to make progress 관측. 팔·인계·선별미도달, 자동재시험없음.
- 중심약40cm/footprint겹침/15sim초간2.1mm·0.76°운동으로 로봇간간섭유력. 접촉력·최초예외task_events 미보존으로 정확한접촉/105최초원인단정불가. 수확은이미PoseProgressChecker이므로직전운송회전105와다름. 다음공유통로진입순서대기권고;판정완화안함.
- 관련24검사+가상인계거절4검사/빌드/문법통과. 종료후 task_events와취소결과계측누락보완,미재시험. 새기능의정상가상인계·완주미검증. 모든소유프로세스종료. 상세 sim/docs/changes/SEC01_SINGLE_CYCLE_20261028.md 및 test_results/20261028_sec01_single_cycle/. 미커밋·미푸시.

### 2026-10-28 — SEC01 예찰 복귀 대신 SEC02 연속 예찰

- 승인: 사용자 SEC02 연속 예찰 명령. 시뮬 single_cycle_steps/probe_handoff_window/run_single_cycle만 수정. SEC01 예찰 뒤 ReturnToStation→ScoutArea SEC02, 별도 결과 보존/완료 후 대기. SEC01 수확·운송·선별 순서는 유지. 실물/공통 코드 영향 없음.
- 공통 RouteGraph 정적 계산으로 아래 Y=0 통로 7.31m 확인, 문법 검사. 실제시험 attempt01은 선별 ROS overlay 누락으로 업무 전 종료; 사전 패키지 검사 추가/환경 복원 후 attempt02 진행. 실패 준비 로그 보존. 상세 SEC01_SINGLE_CYCLE_20261028.md. 미커밋·미푸시. 되돌림은 시뮬 시험기 다음 예찰 요청을 이전 복귀 요청으로 복원하되 북쪽 공유통로 동시 진입은 피해야 함.

- attempt02 실제 확인: 21:49:16 KST SEC01 예찰 SUCCESS(5구간,9윈도우,expected13) 후 SEC02 ScoutArea 수락 및 SEC01 W001 HarvestTask 수락. SEC02 survey session=3eb7cc0fcbf3 RUNNING, 예찰 실제 위치가 남쪽(-6.55,-0.10)까지 진행한 것을 확인했다. 같은 시점 수확은 북쪽(-2.00,11.62)에서 접근 중이다. 예찰 ReturnToStation 명령 없음. 전체 수확·인계·선별·복귀 결과는 아직 미확정이며 시험 runner가 계속 실행한다. 자동 업무 재시도는 없다.

### 2026-10-28 — 관제 저장 Route/HCR 지도 동기화

- 사용자 Route 미표시 조사·조치 요청. 현재 API에서 저장 graph mismatch, Route preview live 확인. Frontend 표시 자산의 오래된 점유지도와8004좌표가 원인. 사용자 지정 Frontend의 simul 저장 YAML/image/예찰·수확 GeoJSON/manifest만 현재 sim 원본으로 갱신. 검사완화/실물/공통 제어 변경 없음.
- 자동 캐시 갱신 후 실시간 API saved: 예찰211/452,수확143/260,8004=(-7,13.25). 점유digest일치, 기존5검사PASS. 관제/시뮬 재시작 없음. 운송graph추가는 범위 밖. 상세 FRONTEND_ROUTE_MAP_SYNC_20261028.md. before백업으로복원가능(현재지도에서는mismatch재발). 미커밋·미푸시.

### 2026-10-28 — 터미널 한 화면 작업 모니터

- 사용자 로봇별 현재/남은 일과 프로그레스바 요청. sim/tools/cycle_monitor.py 단일 표준라이브러리 프로그램 추가. 최신 한사이클 로그 자동선택 또는 폴더 지정, 예찰/수확/운송/선별 현재단계·완료수·남은일·수확수량·주요오류 표시. 1초마다 같은 화면 갱신, 센서원문은 제외하고 JSONL 증분 읽기. --once 지원. Ctrl+C는 모니터만 종료.
- 완료작업수 기준이며 시간기반예측/전체완주 보증 아님. 로그 갱신지연 표시, result 오류/중단 표시. 로봇/시험 제어·ROS·공통/실물 변경 없음. 현재시험 --once/TTY 실행·Ctrl+C 정상복원, 실패 미집계/feedback 중복방지/부분줄 재읽기/증분읽기 확인, 문법·diff PASS. 복원은 새 모니터 파일 제거. 미커밋·미푸시.
- 실행: `python3 /home/ysy/main/farm_project/sim/tools/cycle_monitor.py`. 현재 SEC01 수확/SEC02 연속 예찰 시험 이벤트 형식 대상. ZIP sim/runs/cycle_monitor_20261028_changes.zip은 farm_project에서 해제.

### 2026-10-29 — SEC01/SEC02 연속 시험 최종 결과 확인

- 10/28 21:45:40~22:41:17 KST 약55분37초. SEC01예찰9윈도우/13개,SEC02예찰8윈도우/11개 성공. SEC01수확9/9액션SUCCESS,harvested8/expected13(61.5%). 주행105미발견,모든수확이동ARRIVED.
- 이후 운송Goal REJECTED: 수령 장치 미연결 LID_OPEN. 시험기가 선별UNLOAD/STOP서비스를 인계후에만 시작하지만 공통덮개준비검사는 그서비스도 필요로함. 시뮬시험 연결순서결함,출발/도킹전거절. 인계·선별·복귀미실행. 프로세스종료,재시험없음. 이번에는보고만수행/제어수정없음.
- 상세 sim/docs/changes/SEC01_CYCLE_RESULT_20261029.md,근거test_results/20261029_sec01_cycle_report/. 이전 진행중기록은 본결과로갱신. 미커밋·미푸시.

### 2026-10-29 — 운송 접수 장치 서비스 실행 순서 수정

- 사용자 수정 지시. 시뮬 시험기4파일만 변경: post_sorter 서비스 시작 시점→전체시험 시작, 작업 명령은 실제 양쪽인계완료 뒤 fixture 허가까지 대기. 예찰 전 덮개/UNLOAD/STOP4서비스 연결검사. 인계후동일프로세스재사용/중복서비스없음. 고용량센서로그는 허가후만저장하되 최신odom/정지검사유지. 공통/실물소스·기준불변.
- 실제 ROS+Isaac 짧은검증: 네서비스연결/도킹전하역거절/이전staging_pose운송Goal접수/취소CANCELED NONE PASS. 인계전선별명령0. 기존거절관련8검사/문법diff PASS. 전체인계·선별·복귀재시험아님. runner/probe0,소유프로세스종료(정리SIGINT코드별도보존).
- 보고 sim/docs/changes/PICKUP_SERVICE_ORDER_FIX_20261029.md,근거test_results/20261029_pickup_service_order/,raw runs/pickup_service_order_20261029_attempt01/. 다음단계인계이후연속확인. 복원시기존접수거절재발가능. 미커밋·미푸시.

### 2026-10-29 — SEC01 저장 예찰 재사용·한 사이클 정적 준비 검토

- 사용자 정적 검토 후 예찰 생략 실행 요청. 지도 해시/SEC01 설정/9윈도우 expected13/정렬 검증, 공통 그래프13계획 성공. 새 예찰/SEC02 액션 없이 기존 수확 시퀀스에 저장 태스크 전달. 초기 실제 과실은 새 씬, 과거 수확 수량 재사용 안 함.
- 시뮬 레인 상한0.65m 고정값이13번째를 거절하는 결함 발견. 원본 경사판 길이/과실반경 기반 중심 상한0.661514m로 수정. 형상·간격·공통/실물 판정 불변.13/16개 허용17개 거절 포함 관련16검사, 준비 전용 실행/재사용 분기/문법/diff/빌드 PASS.
- 18:25 KST `sim/runs/sec01_reuse_cycle_20261029_attempt01/` 실행 시작. Domain13/SUBNET CPU60/render30, 한 시도/자동 재실행 없음. 전체 실제 완료 미확정. 보고 `sim/docs/changes/SEC01_REUSED_CYCLE_READINESS_20261029.md`. 되돌림은 재사용 옵션 생략/레인 고정 상한 복원(13번째 거절 재발). 미커밋·미푸시.

### 2026-10-29 — 시뮬 운송 관측 제한 180→900초

- 사용자 시뮬 관측시간 여유 적용 승인. SEC01 재사용시험은 수확9/9·7개 후 운송 출발180실제초에 마커관측 만료로 실패(주행예산419초, 목표8.27m 남음). 전체완주실패/인계이후미실행.
- sim docking/transport_profiles.yaml의 관측시간만900초로 변경. prepare_pickup_trial.py에서 실물 원본 조립 후 이 항목만 시뮬설정 선택·전후값 기록. 공통/실물·다른 제한/판정 유지.
- 준비 전용 실행·최종 프로파일 단일항목 차이·문법/diff·config빌드 PASS. 실제재시험없음. 새 실행부터 적용, 기존 실패로그 보존. 보고 sim/docs/changes/TRANSPORT_OBSERVATION_BUDGET_20261029.md. 복원은180으로 설정. 미커밋·미푸시.

### 2026-10-29 — 수확 완료 상태 복원 후 운송 재개

- 사용자 지시. 지난 성공9윈도우/수확집계7개 재사용. 같은 세션 최종 장면/바구니 모서리로 실제 적재10개 확인, 같은prim을 저장 bbox중심으로 초기배치. 집계7과물리10분리. 자세/속도 전체체크포인트아님(원본자세/속도0), 수확로봇 초기위치/AMCL일치·정상복귀목적지유지.
- sim 시험기/명시적 복원만 변경, 공통/실물불변.5sim초 안정화후10개적재 확인하고 새 예찰/수확 없이 운송. prepare-only/문법diff/기존11검사/빌드PASS. 19:34 KST transport_resume_20261029_attempt01 시작, 전체완료미확정. 상세 sim/docs/changes/TRANSPORT_RESUME_20261029.md. 옵션생략으로기존흐름복원. 미커밋·미푸시.

- 재개 실행 갱신: attempt01은 비활성 과실 pose 읽기 오류를 적재 검사가 차단(업무 Goal0). 보존 위치 사용 수정/회귀1검사PASS 후 attempt02에서 실제10/10 적재 유지 확인·운송 출발. 새 예찰/수확 Goal0. 전체완주 아직 미확정.

### 2026-10-29 — 터미널 진행 표시 누락 수정

- 사용자 모니터 수정 요청. cycle_monitor.py에서 워커 ledger feedback/result와 precision.log 단계 증분 읽기. 정차마커재확인/후진/도킹/인계/선별장/복귀 상태, 수령접근 포함4단계 실제완료수 표시. 실패 우선/후속미실행/간결한오류/과거수확재사용 명시. 시험 제어/공통/실물변경없음.
- 회귀6검사/문법diff/실제실패로그 표시 PASS. transport_resume attempt02는19:41:46 마커재확인 소진 DOCK_FAILED로 종료됐음. 자동재실행없음. 상세 sim/docs/changes/CYCLE_MONITOR_FEEDBACK_FIX_20261029.md. 기존 모니터만Ctrl+C후재실행 필요. 미커밋·미푸시.

### 2026-10-29 — 운송 마커 조기 도킹 전환 수정

- 사용자 “붙어서 도킹으로 넘기도록 수정해그럼” 승인. 공통 precision_server.update_harvest_route가 기존 도킹 추적기의 동일 관측시각 TF·최종 설정·접근 목표 거리 판정을 통과해야 ready 발행. 먼 마커는 일반 주행 유지, 정차 후 목표 재취득 유지. 주행 중 검사 샘플은 버림.
- 현재 1.2m 접근 목표 허용거리/0.54m stand-off·속도·성공·회복/timeout 수치 불변. 실물/시뮬 공통 전환에 적용. 11개 오프라인 회귀검사 및 farm_docking 빌드/diff PASS. 실제 재주행 미실행, 도킹 완주 아직 미검증.
- 원인·파일·복원·검증 상세: sim/docs/changes/HARVEST_ROUTE_ENVELOPE_FIX_20261029.md. 관련 함수 전환 검사만 제거하면 종전 동작 복원(조기 정차 재발 가능). 기존 미커밋 작업 보존, 미커밋·미푸시.

### 2026-10-29 — 운송 출발→도킹 재시험: 42 접근 성공, 41 도킹 미도달

- 사용자 요청으로 수확 완료 상태 재사용, Domain13/SUBNET CPU60/render30, 단일 시도. 시험기에 --stop-after-docking 추가(실제 DOCK_STABLE 관측 후 배출 허가 전 종료). 공통 판정 추가 변경 없음.
- 20:02:57 출발→20:08:05 접근목표1.193m에서 전환→20:08:52 마커42 정밀접근 DONE/WAITING_FOR_TRANSFER. 원거리76관측에서 ready=false로 계속주행. 기존 조기 전환/105 미관측.
- 20:08:53 수확 DockTransfer REJECTED: 새 노드의 마지막 성공 window 기록은 None인데 재개 도구가 물리배치/과거 결과만 복원함. 공통 readiness는 WINDOW_MISSING이면 거절. 구체 코드 경로 확인이며 로그는 포괄적 장치/형식 거절 문구. 다른 동시 조건 실패 여부 미확정.
- 따라서 마커41 최종도킹 미실행/시험실패. 운송은 시험 정리로 CANCELED. 인계/선별 미실행, 프로세스 정리 완료. 다음은 유효한 현재 세션 도착 기준 확보 및 출발 전 준비검사. 자동 재시험/공통 복원 수정 없음.
- 원본 sim/runs/transport_docking_retest_20261029_attempt01/, 상세 sim/docs/changes/TRANSPORT_DOCKING_RETEST_20261029.md. 문법/diff PASS, 성공 종료 분기 실동작 미검증. 옵션 생략으로 기존 시험 흐름 복원. 미커밋·미푸시.

### 2026-10-29 — 운송 재개 도착 문맥 보완 및 최종 라이다 시간 초과 확인

- 사용자 재시험 후 준비누락 지적에 따라 sim 재개 도구만 보완. 과거 기록 주입 대신 마지막 window10cm전 로봇/적재 동시 초기이동, 기존 ARRIVAL_ONLY_NO_HARVEST 실제 도착 성공 후에만 운송 출발. 현재 세션 window 도착기록 생성. 수확9건/집계7개 재사용과 새 도착검증0개 집계를 분리. 공통·실물 추가 변경 없음.
- prepare-only/동일과실10개 위치변환/문법diff PASS. attempt02 실제 도착 위치오차1.06cm/방향1.46° SUCCESS,팔SKIPPED. 운송42 접근성공/수확DockTransfer접수 및 DOCK_READY 성공. 기존 준비 누락 해결.
- 최종41도킹은20.3cm까지 도착 후 정지확인 중 Final lidar approach timed out. 설정65초를 공통 distance_heading_trial 계산이 약25.5실제초로 축소. 실제25.72초 동안 sim14.03초 진행(1.83배지연). DOCK_STABLE 미관측,전체실패 보존. 성공기준/시간수식 추가수정·자동재시험 없음.
- 상세 sim/docs/changes/TRANSPORT_RESUME_WINDOW_FIX_20261029.md, raw sim/runs/transport_docking_retest_20261029_attempt02/. 다음은 실물기본값 보존한 sim시간예산 조정 계약 검토. 복원은재개보완3블록제거(누락재발),일반전체시험옵션생략시기존흐름. 미커밋·미푸시.

### 2026-10-29 — 도킹 접근/상위 동작 제한을 시뮬 시계로 계산

- 사용자 시뮬시간 사용 지시로 공통 precision_server 수정 승인·적용. use_sim_time=true ROS /clock, 실물false 기존monotonic. 라이다 접근/초기 표면 대기/전체정밀주행/execute120초 예산 적용. 센서복구 실제/동작 경과 분리, 시계역행 실패. 센서단절·lease·통신 감시 실제시간 유지.
- 수치·거리계산·속도·성공판정 불변. 시계9+전환11=20검사/빌드/diff PASS. 수정 후 실제 재시험 없음. 다른 모든 주행 단계 시간 전환 완료를 의미하지 않음.
- 상세 sim/docs/changes/DOCKING_MOTION_CLOCK_20261029.md. 이번 시계 관련 코드만 되돌리면 복원; 앞선 거리전환 수정 보존. 미커밋·미푸시.

### 2026-10-29 — 시뮬 시계 수정 후 attempt03: 초기 마커 목표 취득 실패

- 사용자 재시험 요청. 도착전용 실제 검증 성공/팔SKIPPED 후20:42:25 운송출발.20:47:31 접근목표 약1.186m에서전환했으나 정차후1.208~1.225m 재측정되어1.2m범위거절,8개중3개관측만수락.20:48:06 DOCK_FAILED/Initial marker reacquisition exhausted. 초기복구30초는아직실제시간(직전라이다시계수정범위밖).
- 마지막라이다접근미도달로시계수정E2E미검증. DOCK_STABLE/인계/선별미실행. 다음은전환경계여유와초기복구시계검토. 이번새소스변경/추가재시험없음,정리완료. 상세 sim/docs/changes/DOCKING_MOTION_CLOCK_RETEST_20261029.md,raw sim/runs/transport_docking_retest_20261029_attempt03/. 미커밋·미푸시.

### 2026-10-29 — 도킹 전환 여유 및 초기 마커복구 시계 보완

- 사용자 “조치하고 재시험해” 승인. 공통 precision_server에 선택적 approach_margin_m(기본0) 지원, sim만0.1m 적용해1.1m에서전환/실제도킹1.2m유지. 초기마커복구 및 거리취득 시계 sim=/clock,real=monotonic으로일치. 30초·속도·성공판정 보존. 프로파일 조립/전후값기록 함께수정.
- 29개 회귀검사와 두 패키지 빌드PASS. attempt04 운송출발→최종도킹 성공(20:53:59~21:01:32,7분33초). 1.09769m에서전환/42접근DONE/수확DOCK_READY/41최종20.3cm정지/DOCK_STABLE확인. 최종라이다 실제25.83초·sim약14.37초,105/도킹시간초과없음. 도킹후범위종료취소로전체인계·선별·복귀미실행. 종료gate context오류/SIGINT는정리기록이며정밀주행실패아님. 시험종료,원본·요약로그보존. 원본로그 sim/runs/transport_docking_retest_20261029_attempt04/. 변경/실물영향/복원은 sim/docs/changes/DOCKING_HANDOFF_MARGIN_20261029.md. 미커밋·미푸시.

### 2026-10-29 — 수확 완료 재사용 후 인계·선별·복귀 연속시험

- 사용자 후속시험 요청, 소스/설정 추가변경 없이 직전 도킹 성공 설정 사용. Domain13/SUBNET CPU물리60/render30. 예찰/수확 재사용, transport_full_resume_20261029_attempt01 실행.
- 운송인계SUCCESS/수확인계 및 window복원SUCCESS. 기존과실10개 가상인계→선별장 도킹→같은10개 레인투입 성공.
- 선별장 이격 후 회전에서 CLEARANCE_FAILED: Distance exit rotation position drift. 5cm제한에 odom5.122cm/world5.237cm 실제밀림. AMCL만의오류아님, 물리접촉/구동제약 원인미확정. 105/시간초과아님. 선별·운송복귀·수확복귀미실행,전체실패/정리완료.
- 보고서 sim/docs/changes/TRANSPORT_FULL_RESUME_20261029.md, 증거 sim/docs/test_results/20261029_transport_full_resume/. 다음은해당자세회전접촉재현, 판정완화/추가소스수정없음. 문서추가만으로복원필요없음. 미커밋·미푸시.

### 2026-10-29 — 선별장 이탈 회전 정체: 시뮬 뚜껑 관절 결함 조사

- 사용자 문제 확인 요청. 시뮬 진단에 접촉쌍/충격량·전체 관절 기록과 독립 명령 재생/자산 비교 도구 추가. 공통 제어·원본 형상·USD 관절·성공 기준은 이번에 수정하지 않음. 기존 미커밋 변경 보존, 실물 영향 없음.
- URDF 뚜껑 범위0~0.155m 대비 실행 stage 합성 USD -1.776~10.657m. 자산 단독 단위0.01과 실행 stage1m를 구분. 실제 긴 주행에서 뚜껑 프레임 최대3.296m 이탈 확인.
- 도킹 단독 시험은 이탈/복귀 성공(2개 중1개만 선별). 원래 운송 명령 전체 재생에서는 이탈한 뚜껑과 선별장 구조물/팔 base 접촉 직후 회전 정체·후진 밀림 재현. 3.23cm 이동 후 원본 정지 명령으로 종료, 정확한5cm 액션 실패/원래10개 전체 사이클 성공은 아님. 뚜껑 물리 결함이 가장 유력하며 수정 전후 대조시험은 남음.
- runtime 빌드/실제 접촉·관절 기록/문법/diff 검사 확인, 진단 프로세스 종료. 복원은 --contact-trace 생략 또는 이번 기록 블록/도구만 제거, 이전 도킹 수정 유지.
- 상세 sim/docs/changes/SORTER_EXIT_DRIFT_DIAGNOSIS_20261029.md, 증거 sim/docs/test_results/20261029_sorter_exit_diagnosis/. 다음은 형상을 보존한 뚜껑 관절 범위·연동 복원 및 같은 주행 대조. 미커밋·미푸시.

### 2026-10-29 — 운송 뚜껑 닫힌 위치 임시 고정

- 사용자 “일단 뚜껑이 안막히게 조치해” 승인. 시뮬 transport_robot.sim.usda의 두 상부 prismatic 관절만 lower/upper=0, 잘못된 rotY mimic API 해제. 바구니 형상/충돌/원본 URDF/공통 코드/주행 판정 유지. 실물 영향 없음. 실제 개폐는 구현하지 않고 기존 가상 기구 계약 유지.
- 정적 합성 및 LFS 원본 대비21줄 추가 확인. 동일 운송 명령542sim초 재생 후 뚜껑 변위0, 유효 충격 접촉0건, 이탈 회전 최대차체이동7.25mm. 이전 회전 정체·32.30mm 밀림 해소. 초기 Modbus 주소 인자 누락 준비실패1건은 별도 보존. 전체 액션 사이클은 미시험.
- 상세 sim/docs/changes/TRANSPORT_LID_HOLD_20261029.md, 증거 sim/docs/test_results/20261029_transport_lid_hold/. 복원은 sim.usda에 추가한두관절 override21줄만 제거. 다음 전체시퀀스 재시험 시 이 모델 적용. 미커밋·미푸시.

### 2026-10-29 — 뚜껑 고정 후 사이클 attempt02 시작

- 사용자 사이클 재적용 요청. 수확 완료 데이터(9윈도우/집계7개/바구니 실제10개) 재사용, 뚜껑 고정 USD로 운송→인계→선별→양 로봇 복귀 재실행. Domain13/SUBNET CPU60/render30.
- 실제 도착 전용 재확인 및 운송 MOVING_STARTED 확인. 현재 진행 중, 완료/성공 미확정. 기존 직접 액션 시험·자동 재시도 없음. 관제 프로세스 유지.
- 로그 sim/runs/transport_full_resume_20261029_attempt02/, 상세 sim/docs/changes/TRANSPORT_FULL_RESUME_LID_HOLD_20261029.md. 이전 추적 소스해시 동일/새 모델해시 보존. 새 소스 변경·커밋·푸시 없음.

### 2026-10-29 — attempt02 종료: 위치추정 차이로 수확 인계 복원 거절

- 앞선 진행 중 기록 갱신. 22:46:52 KST DEVICE_FAILED / WINDOW_REALIGN_REQUIRED(전방-7.96cm,횡-3.19cm). 운송Pickup 성공·과실인계/운송이격 완료, 수확 window복원 실패. 양쪽 성공 gate에서 시험 종료, 선별장 이동/선별/양복귀 미실행.
- 실패 직전 지도 추정 목표오차8.57cm 대비 실제2.74cm(허용5cm), 지도/실제 차이5.89cm. odom/USD 시각차0.283sim초 근접정지표본 비교. 이전 위치추정 기반 복원거절과 같은 양상이며 이번 뚜껑 회전 단계 미도달. AMCL/태그/TF 세부 원인기여는 미확정.
- 상세 sim/docs/changes/TRANSPORT_FULL_RESUME_LID_HOLD_20261029.md, 증거 sim/docs/test_results/20261029_transport_full_resume_lid_hold/. 시험 프로세스 정리 완료. 소스/판정 변경·자동재시도·커밋·푸시 없음.

### 2026-10-29 — attempt02 위치추정 오차 증가 구간 확인

- 사용자 원인 질의에 저장 로그 추가분석. window도착 AMCL오차0.09cm→복원302초2.04cm→324초5.33cm→328초5.94cm. 실제시각정합 odom오차 최대4.93mm/마지막3.42mm로 AMCL 지도추정 영향 지배 확인.
- 태그 노드는 켜졌으나 관측31건 selected없음/보정요청0회. 수확 작업 lease 종료 뒤 인계복원에서는 태그 lease 재개 없음. 전역설정false로 되돌린 것이 아니라 현재 작업별 보정 계약의 범위. 실제센서정합/AMCL noise 기여도 추가분리 필요.
- 상세 TRANSPORT_FULL_RESUME_LID_HOLD_20261029.md 후속절 및 test_results/20261029_transport_full_resume_lid_hold/localization_timeline.json. 코드/설정 수정·시험 재실행·커밋·푸시 없음.

### 2026-10-29 — 어제 전후 위치추정 변경 감사: 인계 복귀 태그 연결 공백

- 사용자 최근 악화 원인 확인 요청. 10/23~현재 수확AMCL설정/태그AMCL/태그어댑터 핵심 파일 해시 동일. 이전 연속수확 태그APPLIED46회 대비 신규 인계·복귀 작업 lease 미연결, 현재 노드true이지만 적용0회. 초기시험 false 복원과 단계별보정 연결을 구분.
- 저장라이다3313개 지도비교: 선별장179셀 변경, 복귀말 실제위치 새지도점수0.98533/구지도0.98240, Y±5cm도0.98338/0.98427로 구분력약함. 진단점수이며 필터재생아님.
- 복귀후반 ROI통과75건, 기존 관측코드에 SEC01 문맥을 주는 오프라인 계산33후보 통과. 실제시각대조가능28개 태그오차중앙2.63mm/최대5.09mm. 사용가능관측을 실제 보정에 연결하지 않은 공백 확인. 새 실제주행/보정적용 성공은 미검증.
- 권장: 복귀정지 후 제한적태그보정/APPLIED확인 뒤 기존window판정. 공통동작변경은 아직 미적용. 상세 sim/docs/changes/HARVEST_LOCALIZATION_REGRESSION_AUDIT_20261029.md. 분석자료만 추가·미커밋/미푸시.

### 2026-10-29 — 정정: 인계 태그 미사용은 사용자 요구, 연결 누락 아님

- 사용자 “태그보정은 인계에서는 안 쓴다고 했어” 재확인. 앞선 태그 미적용을 연결 누락/결함으로 본 결론과 복귀 후 태그 재활성화 제안 철회. 해당 제안은 구현하지 않았으며 태그·공통 코드·운영 설정 변경 없음.
- 태그 관측/오프라인 정확도는 진단 사실만 보존. 이전 태그 사용 연속수확과의 조건 차이를 인계 결함의 증거로 삼지 않는다. 인계 태그 미사용과5cm기준 유지.
- 현재 확정: 복귀 중 AMCL오차 약2→6cm, odom오차 최대약5mm. AMCL 악화의 직접 원인은 미확정. 다음 조사 대상은 동일 scan/odom의 지도정합·갱신/운동모델·동적장애물 영향이다.
- HARVEST_LOCALIZATION_REGRESSION_AUDIT_20261029.md 및 TRANSPORT_FULL_RESUME_LID_HOLD_20261029.md 정정. 문서만 변경, 추가 시험·커밋·푸시 없음.

### 2026-10-29 — 사용자 명시: 태그 위치 보정 사용 범위

- 태그 위치 보정은 예찰·수확 주행 중에만 사용한다. 인계 과정 및 운송로봇과 도킹하는 과정에서는 사용하지 않는다.
- 도킹 상대의 상대 위치를 얻는 마커 검출과 map 위치 보정은 구분한다. 이번 발언을 근거로 기존 도킹 마커 검출을 제거하거나 비활성화하지 않는다.
- 인계·복원 AMCL 문제의 해결책으로 태그 위치 보정을 새로 활성화하지 않는다. 기존 태그 미사용 조건 아래 라이다/odom/AMCL을 조사한다.
- 이번 작업은 요구사항 기록만이며 운영 코드·설정·실행 상태 변경 없음.

### 2026-10-29 — 수확 AMCL 회전 노이즈 영향 동일센서 A/B 확인

- 사용자 원인 재확인 요청. 같은 farm_tag_amcl/scan3313/odom/정적TF/지도/초기위치 격리 재생, 태그 미사용. baseline23출력이 원래 로그와 최대1.99e-15m 차이로 일치, 마지막오차5.94cm 재현.
- 각도갱신0.2→0.05rad 단독은 마지막4.68cm/최대12.23cm로 악화, 미채택. alpha4만0.2→0.002는 동일23표본 마지막0.85cm/최대0.88cm/평균0.42cm. 실제 odom최대4.93mm와 반복베드의약한라이다구분력을 고려해 과도한 회전병진노이즈가 이번 오차의 주요원인임을 확인.
- 운영 설정은 변경하지 않음. 시뮬실제회전/다른SEC/실물 적합성은 미검증. 다음은 sim전용후보 실제인계대조이며 태그미사용/성공기준 유지.
- 상세 sim/docs/changes/HARVEST_AMCL_REPLAY_CAUSE_20261029.md, 증거 sim/docs/test_results/20261029_harvest_amcl_replay/. 준비namespace거절1건 별도기록/유효재생모두정리. 미커밋·미푸시.

### 2026-10-29 — 시뮬 수확 alpha4 적용 및 실제 재시험 시작

- 사용자 “그건 시뮬레이션 설정이지? 변경해서 적용하고 재시험해봐” 승인. sim/ros_ws/src/farm_sim_config/config/nav2_harvest.yaml에 AMCL alpha4=0.002 override 추가(기존0.2). 동일센서 A/B 근거는 HARVEST_AMCL_REPLAY_CAUSE_20261029.md. 공통/실물 기본값0.2 파일해시 유지, 최종 병합값 차이도 alpha4 한 항목만 확인.
- Domain13/SUBNET, CPU물리60/render30. 수확완료9윈도우/집계7/실제바구니10 재사용, 운송→인계→window복원→선별→양복귀 단일시도. 인계 태그보정 미사용·5cm판정·기존뚜껑고정 유지.
- 실행 sim/runs/transport_full_resume_20261029_attempt03/, 소스/설정해시와 변경검증 저장. 실제결과는 진행 중으로 미확정. 기준18d0e000 및 기존미커밋변경 보존. 커밋/푸시없음. 복원은 이번sim YAML overrides 블록만 제거.

### 2026-10-29 — alpha4 실제 시험: 인계·window복원 성공

- attempt03 23:54:14 KST 수확 DockTransfer SUCCESS(transfer/clear/restore 모두true), 운송Pickup SUCCESS. 기존태그보정미사용/5cm판정 유지. 복원 마지막AMCL오차 이전5.94cm→1.29cm, 최대2.39cm. 한 번의 실제 시험이며 전체구간/반복 안정성 증명은 아님.
- 같은 프로세스에서 선별장 이동 이후 계속 진행 중. 전체 사이클 완료 결과는 아직 없음. 보고서 sim/docs/changes/HARVEST_ALPHA4_LIVE_RETEST_20261029.md, 증거 sim/docs/test_results/20261029_harvest_alpha4_live/, 원시로그 sim/runs/transport_full_resume_20261029_attempt03/. 미커밋·미푸시.

### 2026-10-30 — 선별장 검출만 독립 시험

- 사용자 요청으로 저장된 실제 RGB2장에 원본 검출기를 적용. 새 물리/팔/주행 실행 없이 ROI Y0~40px 대조. attempt03 기존0/4레인, attempt01 기존1/4레인 검출. 아래5~10px 이동만으로 각각4/4 앞열 색상정답 일치. 원인: 얇은 ROI가 실제 과실 몸체보다 위쪽에 있음. HSV 기준/운영 ROI/공통 코드 미변경. 연속선별·시간안정화는 미검증.
- 시뮬 도구 sim/tools/test_sorter_detection_snapshot.py 추가. 상세 sim/docs/changes/SORTER_DETECTION_ONLY_20261030.md, 자료 sim/docs/test_results/20261030_sorter_detection/. 승인범위는 검출 시험. 도구 제거로 복원 가능, 운영 영향 없음. 미커밋·미푸시.
- 기존 attempt03은00:08:14 KST 수확복귀까지SUCCESS, 프로세스정리완료. 연쇄액션완료와 전량선별은 구분:10개중1개/잔류9개.

### 2026-10-30 — 선별 시뮬 ROI 수정 및 전·후 이미지 보존

- 사용자 “수정 전 / 후 스크린샷 로그로 남겨놓고 수정해” 승인. sorter_camera_zones.json에 원본 ROI의 Y만+5px 추가, sorter_integration.json의 source_roi를 연결. 원본전달/실물/공통/판정 유지. 상대경로는 기존 source_workspace 기준 계약 사용.
- 실제 저장영상2장에 원본검출기 적용, 앞열색상정답 각각0/4→4/4 및1/4→4/4. 새 운영설정 경로/좌표·기존지도·diff검사 통과. 전후이미지·설정·색비율·해시는 sim/docs/test_results/20261030_sorter_roi_applied/ 보존. 새 물리/연속선별 미실행.
- 상세 sim/docs/changes/SORTER_ROI_APPLIED_20261030.md. 복원은 source_roi를 원본 outputs/sorting_station/hcr_sim/zones.json으로 변경. 새시험부터적용/과거runtime보존. 미커밋·미푸시.

### 2026-10-30 — ROI +5px 적용 후 사이클 1회 시작

- 사용자 사이클시험 요청. transport_full_resume_20261030_roi05_attempt01 시작. 예찰·수확 완료 데이터 재사용, 운송출발/인계/복원/선별/양복귀 단일시도. Domain13/SUBNET, CPU물리60/render30, alpha4=.002 및 인계태그미사용 유지.
- 실제 준비된 runtime 설정에서 새 시뮬 ROI 경로·Y+5px와alpha4 확인. 소스해시/ROI스냅샷 보존. 카메라 상태·팔단계·수량 변화 시 원본영상과물리상태를 camera_history/에 관측 전용으로 보존(영상과상태 최대약1sim초시차).
- 아직진행중/성공미확정, 자동재시도없음. 실제투입10/선별수/잔류수와액션결과 분리평가. 운영코드추가변경·커밋·푸시없음. 로그 sim/runs/transport_full_resume_20261030_roi05_attempt01/.

### 2026-10-30 — ROI +5px 사이클 완료: 전량선별·양복귀 성공

- transport_full_resume_20261030_roi05_attempt01 단일시도 완료(00:28:02~00:57:34 KST, 약29분33초). 기존예찰·수확재사용, 인계·window복원·선별장도킹/투입·선별·양복귀 모든액션SUCCESS. 액션실패/105/재시작없음.
- 실제10개→빨강6/노랑4 선별10개, 잔류0, all_input_fruits_sorted=true, 물리/ROS수량일치. 이전1/10 대비이번10/10. 새예찰/수확성능·반복신뢰성 검증과는구분.
- 원본영상164장/각수량단계대표영상/설정해시/결과 보존. 관측PNG저장중읽기3건은디코딩실패로제외,저장영상전부검증. 시험·관측기정리완료,기존관제유지.
- 상세 sim/docs/changes/ROI05_CYCLE_RESULT_20261030.md, 자료 sim/docs/test_results/20261030_roi05_cycle/. 실행/판정추가변경·커밋·푸시없음.

### 2026-10-30 — 새 예찰부터 병행 전체 사이클 성공까지 재시도 시작

- 사용자 명시: SEC01 새예찰→SEC02예찰/SEC01수확 병행→수확후운송호출→인계후운송선별장이동/수확복귀 병행→투입후선별/운송복귀 병행→모든로봇복귀·전량선별. 실패시시뮬재시작/새예찰부터재시도,최초완전성공에서종료.
- 시뮬 시험기에 --overlap-cycle 선택 모드 추가. 예찰은SEC02완료후대기,다른로봇복귀후기존ReturnToStation으로복귀. 기존기본순서 유지,실물/공통 제어와성공판정 변경없음. 전체시험 성공은모든액션/모든수확윈도우/양구역예찰/세로봇복귀/실제투입전량선별을모두요구.
- 단위검사23개·문법/diff검사·prepare-only로새예찰/초기빈적재/ROI/병행설정 확인. Domain13/SUBNET CPU60/render30,AMCLalpha4=.002,인계태그미사용 유지. 독립 관측기로선별상태변화시영상기록.
- 실행 sim/runs/fresh_full_cycle_20261030/ (status.json이현재시도·실패이력,attempt_NNN별원본로그). 소스스냅샷·SHA256보존. 최초attempt_001실행중,성공미확정. 운영코드수정/커밋/푸시없음.
- 복원은--overlap-cycle및run_fresh_cycle_until_success 사용중단으로기존순차시험경로사용. 새도구·선택분기만추가/기존미커밋변경보존.

### 2026-10-30 — 전체 반복시험 실패 원인 분석 병행

- 사용자 “시험하는동안 실패하면 계속 원인분석” 요청. 기존 반복시험은 유지하고 sim/tools/analyze_cycle_failures.py 관측 전용 분석기를 별도 실행. 완료 실패마다 원문/행번호/단계/구동 표본/실제·odom 원호 정합 오차를 sim/runs/fresh_full_cycle_20261030/failure_analysis/에 저장. 10초 감시, 처리 완료 시도 재파싱 없음, 전체성공/중단 시 종료.
- 실제 실패1~5차 분석: 1~3차 Nav2 106 arc deviation exceeded, 4차 Spin완료후재진입1.0543°>1°, 5차 원호끝점정지중위치오차. costmap실제수신0.5초초과/ROS나이정상→정지→차체병진·회전감속불일치 확인. 2·3차는 실제/odom정합오차가 거의같아 AMCL map점프가 원인이라는 증거없음. 6차 계속진행/전체성공미확정.
- 근사재구성의1초진단표본/원점불확실성을명시. 공통/실물/시뮬주행설정·판정미변경. 문법검사·완료5건실행·분석기heartbeat확인. 상세 sim/docs/changes/FRESH_CYCLE_FAILURE_ANALYSIS_20261030.md. 미커밋·미푸시. 복원은관측분석기만종료/새도구제거이며시험프로세스는유지.

### 2026-10-30 — 인계 실패를 만드는 발행 간격·물리 제동 설정 수정

- 사용자 원인 규명·해결 요청. 시뮬 수확 costmap 발행 5→20Hz(계산10Hz 유지), teacher_alignment 위치 반복12→64회(속도4 유지). 공통/실물/판정/전달USD는 보존. 기존 미커밋 변경 유지, 새 커밋·푸시 없음.
- 팔 카메라 부하 중 실제 costmap 수신 최대간격 1.101→0.401초, 20초 관측에서 0.5초 초과18→0건. 독립 동일모델 원호→정지 시험은 이동22.224→3.915mm/최대원호오차28.914→6.159mm. 속도 반복 증가 후보는 개선 없어 제외.
- 6차 시험은 중단하지 않고 인계 costmap 발행만 라이브 적용. 위치 반복은 현재12, 다음 시뮬 실행부터64. 실제 전체 인계·복원 성공은 아직 미검증. 작은 Spin 근사에서64회 최종0.879°로 여유가 작아 회전 문제 완전해결로 판단하지 않음. 팔 성능/계산비용도 통합확인 필요.
- 대상은 sim/config의 nav2_harvest.yaml·robotarm_physics.json, runtime의 teacher_arm_alignment.py·drive_diagnostics.py, 진단도구/실행별 설정기록/관련검사. USD검사7개·인계/전체완료검사22개·runtime빌드 통과. 별도 기존launch fixture controller_output 누락1건은 미해결로 명시.
- 상세 sim/docs/changes/FRESH_CYCLE_ROOT_FIX_20261030.md. 증거 sim/runs/fresh_full_cycle_20261030/fixes_20261030/ 및 wheel_arc_position_20261030 등. 복원은 이번발행override/위치반복키만 제거 후 재시작,기존alpha4유지.

### 2026-10-30 — 7차 수확 중 차체 밀림 회귀 수정, 9차 준비

- 사용자 8차 유지/9차 조치 요청. 7차W002는 정지 명령0 상태에서약104.5초동안차체23.64mm밀림,팔장착점2cm한계초과. 주행을 위해 articulation 전체를12→64회로올린설정이팔작업에도영향. 같은팔명령재생64/12/64에서마지막이동6.960/1.876/6.290mm로차이확인(과실·베드없는축소시험).
- 시뮬 물리 프로파일에 harvest_solver_position_iterations=12,run_fleet에서busy또는접힘미확인동안12/작업종료와접힘확인후64. 실제PhysX getter확인및전환로그. student_session 실패로그에이동/회전/변환/한계추가. 공통·실물·2cm/.05rad기준변경없음.
- 실제64→12전환후동일104.45초명령재생최대5.378mm/마지막5.331mm,exit0. 관련회귀28개·두패키지빌드·문법/diff통과,설치본해시확인. 새전체사이클검증은아직남음. 8차프로세스미변경,다음9차부터적용.
- 상세 sim/docs/changes/ATTEMPT007_ARM_DRIFT_FIX_20261030.md. 원문/명령/해시/진단로그 sim/runs/fresh_full_cycle_20261030/fixes_attempt007/. 기존미커밋보존·커밋푸시없음. 새프로파일키제거후재시작시이전64고정으로복원(회귀위험있음).

### 2026-10-30 — 수확 일반 경로 속도 0.15 시험 설정

- 사용자 “그렇게 적용해보고 그걸로 문제되면 롤백” 승인. 시뮬 nav2_harvest.yaml의 controller_server FollowPath/RPP만 desired_linear_vel 0.1→0.15m/s, rotate_to_heading_angular_vel 0.1→0.15rad/s. 실물/공통파일 변경없음. 수확 일반 이탈·복귀 등에 선택되는 RPP 적용이며 HarvestApproach 베드진입/HarvestWork 윈도우작업/StationReverse/도킹/인계/예찰·운송 설정은 보존.
- 실제 설정 로더의 전후전체병합비교에서 위4개값만차이. 인계 build_server_config 결과 전체동일 확인,가감속·감속거리·성공판정변경없음. 현재9차실행은기존값을유지하고다음시작부터적용. 새속도의실주행검증은아직미실행이며동작개선/성공확정아님.
- 전후원본·4개차이·공통파일해시는 sim/runs/fresh_full_cycle_20261030/speed_trial_20261030/ 보존. 문제발생시속도변경과관련있는지확인후새controller_server override블록만제거해0.1/0.1복원한다. 전체YAML백업덮어쓰기로alpha4/발행주기등다른수정까지되돌리지않는다.
- 물리모드 주행64/팔12와기존실패로그는그대로유지. 미커밋·미푸시.9차가전체성공으로감시기를종료하면새속도전체시험은별도실행이필요함.

### 2026-10-30 — Robotarm_update 참고 전달물 읽기 전용 검토

- 사용자 시험 유지/새 팔 전달물 내용 파악 요청. 실제 경로 Robotarm_update의10/28 ZIP·문서 검토. 새Student학습본이아니라윈도우미션/A5박스검사/입력최적화참고묶음. SHA251건일치,로컬기존4모델해시일치. A5소스182개중로컬154동일/2수정/26없음.
- 현재D435·레이저계수·timeout1회재시도·compiled_cpu보존필요. U20/A5실행기그대로교체시성공증거계약불일치및timeout RETURN_STOW 가로채기위험. v20보조명령7076/신경망단독0,Jetson20Hz는무구동시험임을원본결과로확인.
- 권장후속은D435/레이저/재시도정책을유지한윈도우최종접힘1회이식검토이며이번에는미적용. 9차전체시험중단·모델교체·새의존성설치없음. 상세 sim/docs/changes/ROBOTARM_UPDATE_REVIEW_20261030.md,해시/차이 sim/docs/test_results/20261030_robotarm_update_review/. 문서·검토자료만작성,미커밋·미푸시.

### 2026-10-30 — 실물에 맞춘 U20 연결 및 정상 과실 사이 HOME 복귀

- 사용자 실물 U20 사용/시뮬 일치 지시로 camera=u20/backend=student_u20. 기존 전달 모델·광학 URDF·RGB-only 입력·후방 D435 연결, 양손 외형 교체. 레이저 집계/60초·1회 재시도 유지, A5 제외. 공통·실물 수정 없음.
- 정상 과실 사이는 lift→HOME, 마지막만 접힘. 시간초과 안전 접힘은 유지. 미검출 깊이 투영 생략/전체 좌표 격자 할당 제거. source/installed 갱신 완료, 9차 시험은 중단하지 않음. 다음 실행부터 적용.
- 50개 오프라인 회귀·실가중치 CPU 추론·실제 농장 USD 물리 불변 검사·3패키지 빌드 통과. 실시간 렌더/수확 검증은 아직 전. 전달 U20 장착값은 실측 보정 완료가 아님.
- 상세/파일/복원: changes/U20_FARM_INTEGRATION_20261030.md. 증거 docs/test_results/20261030_u20_integration/. 이전 D435 대조는 camera/backend를 함께 변경, U20 기준을 임의 롤백하지 않음. 기존 미커밋 보존, 커밋·푸시 없음.

### 2026-10-30 — SEC01 예찰 복귀·수확 출발 간섭 지도 이미지

- 사용자 지도·경로·충돌 위치 이미지 요청. `sim/tools/render_sec01_conflict_map.py`와 `sim/docs/test_results/20261030_sec01_conflict_map/{sec01_routes_conflict_map.png,sources.json}` 추가. 맵 +Y를 북쪽으로 정의하고 전체 지도/북쪽 Y=11.5 통로/최근접 표본 확대 표시.
- 2026-10-28 기록의 실제 궤적(실선), 현재 그래프 좌표 재구성 경로(점선), 두 로봇 중심·Nav2 외곽을 구분. 최근접 중심 간38.6cm는 약0.2초 차이 표본이며 접촉점/접촉력 확정 자료 아님을 이미지에 명시.
- PNG 생성 및 시각 확인 완료. 시험·로봇·주행 설정 미변경. 미커밋·미푸시. 복원은 추가 도구/이미지/출처 자료만 제거.

## 2026-10-30 — SEC01 좌측 평행 경로 교행 확인

- 승인 근거: 사용자 “좌측 서로다른 노드타는 경로에서 마주칠때 충돌하는지 확인”.
- 대상: `sim/tools/check_sec01_robot_passing.py`, `sim/docs/test_results/20261030_sec01_parallel_passing/`. 진단 도구·결과만 추가. 기존 운영 주행·지도·실물 코드 영향 없음.
- 실제 USD와 기존 물리·접힌 팔 설정으로 별도 CPU PhysX 교행 시험. 예찰 후진/수확 전진 및 반대 방향 양쪽 전진 모두 통과, 상호 접촉 0, 최소 X축 충돌 경계 간격 31.09cm. 기존 전체 시험은 유지.
- 초기 도구의 USD 인스턴스 참조 만료와 guide 충돌체 경계 누락을 수정해 verified 실행에서 재검증. Nav2/AMCL·회피·회전/합류는 미검증.
- 검증: 실제 2조건 물리 실행 완료 및 결과 확인, py_compile. 상세 근거는 위 REPORT.md.
- 되돌리기: 새 진단 도구·결과만 제거하면 됨. 운영 설정 변경 없음. 커밋·푸시 미실행.

## 2026-10-30 — SEC02 수확 / SEC03 예찰 교행 충돌 확인

- 승인: 사용자 해당 경로의 충돌 여지 확인 요청. 기존 전체 시험 유지, 별도 진단만 수행.
- 대상: `sim/tools/check_sec01_robot_passing.py`의 SEC 선택 인자·방향 처리, `sim/docs/test_results/20261030_sec02_harvest_sec03_scout/`. 기존 SEC01 기본값 유지.
- 경로 중심33cm. 정상 작업 방향의 물리 교행에서 예찰 오른쪽 바퀴↔수확 왼쪽 바퀴 접촉력 확인(비영 충격량 이벤트309건); 예찰 밀림·회전 발생. 비교 후진에서는 근접 보고만 있고 비영 충격량 없음.
- 기존 passed_each_other는 Y순서 역전만 판정하므로 안전 통과와 구분; contact_analysis와 보고서에 실제 접촉력 검증 기록.
- 실제 CPU PhysX 두 조건 실행, 지도/그래프 대조, py_compile 검사. Nav2/관제 회피는 미검증. 운영·공통·실물 변경 없음. 되돌리기는 진단 인자 추가와 결과 파일만 제거. 커밋·푸시 미실행.

## 2026-10-30 — 사이클 모니터 현재 시험·재시작 자동 추적

- 승인 근거: 사용자가 attempt마다 모니터를 재실행하지 않고 현재 시험/재시작 화면으로 자동 전환하도록 요청.
- 대상: `sim/tools/cycle_monitor.py`, `sim/tests/test_cycle_monitor.py`, 실행 가이드.
- 변경 전: 인자 생략 시 최상위 최신 시험을 시작 시 한 번 선택. 변경 후: 중첩 반복 시험의 status current를 매초 읽어 다음 attempt로 전환하고 진행률·오류·읽기 offset 초기화. 같은 터미널 화면 덮어쓰기 유지. 개별 폴더 지정은 기존 고정 모드 유지. 기록 없음/새 폴더 생성 전 대기와 종료 결과 유지 지원.
- 검증: 관련 테스트9개 통과, 실제 현재 attempt_009 자동 선택/부모 폴더 선택 확인, 별도 PTY에서 attempt_001→002 전환 및 이전 오류 제거/화면 덮어쓰기 확인, py_compile. 테스트 준비 파일 생성 누락1건은 보완 후 통과.
- 실물·로봇 제어·진행 시험 영향 없음(로그 읽기 전용). 기존 실행 모니터만 한 번 재실행 필요. 복원: 이번 자동 선택/루프 변경과 테스트를 되돌리면 기존 고정 선택 동작. 커밋·푸시 미실행.

## 2026-10-30 — 9차 인계 전 벽 접근 거리 실패 확인

- 사용자 재출발 원인 확인 요청. 9개 수확 윈도우 완료/레이저 집계2개, 운송 수령 위치 도착 후 수확 인계 자세 준비의 벽 접근 계획에서 실패.
- 목표43.25cm + 최대 접근20cm = 허용 상한63.25cm. 실패 직전 wall_observation와 12.5ms 차이 odom으로 재계산한 거리63.84cm, 상한 약5.9mm 초과. 실제 함수 내부 입력의 직접 캡처는 아니며 인접 관측에서도 같은 범위 확인.
- `sim/docs/test_results/20261030_attempt009_handoff_distance/diagnosis.json`에 근거 기록. 왜 준비 위치가 이 범위에 도달했는지는 추가 원인 분리 필요. 허용값·실물·공통 코드 변경 없음. 기존 supervisor가10차 자동 재시작, 계속 유지. 문서 추가만이며 삭제로 복원 가능. 커밋·푸시 없음.

## 2026-10-30 — 사용자 요청 전체 시험 중지·커밋 체크포인트

- 사용자 승인: “시험 다 중지…현재까지 수정한 내용 커밋푸시…그다음 다시 진행”. 자동재시작 감독기 SIGINT→실행기의 자식 프로세스 정리 완료, 상태 STOPPED 확인. 읽기 전용 실패 감시기도 종료. 사용자 터미널 모니터는 유지.
- 본 커밋은 누적 도킹 접근 전환·시뮬 시간 예산, 운송 뚜껑/인계·선별 연동, AMCL/물리/속도 설정, U20·팔 HOME/영상 최적화, 전체 사이클/진단/자동 모니터 및 보고 자료를 보존한다. 각 변경의 승인·검증 범위는 기존 상세 문서 참조. 이번 체크포인트에서 동작값 추가 변경 없음.
- 회귀 검증: 제어·모니터70PASS, Student41PASS/44subtests/8USD환경SKIP, Frontend 저장지도5PASS. 환경 준비 오류는 기존 ROS setup/Isaac Python/Frontend venv로 재실행해 해결.
- 알려진 미해결: 9차 벽 접근 거리 상한 초과(인접로그 재구성5.9mm), SEC02수확/SEC03예찰 동시 교행 접촉, 전체 사이클 최초 완전 성공 미달성.
- 푸시 후 새 실행 폴더로 동일 승인 조건 재개 예정. 이전 실행 로그는 보존. 원본 전달 ZIP·별도 Frontend 저장소를 상위 저장소에 중첩 추가하지 않는다. Frontend 지도 수정은 해당 저장소에 별도 커밋.


## 2026-10-30 — 인계 후 운송 출발·수확 후진 동시 실행 차단

- 기준 main `399379087374f9982b177e70d68e11721d5fdaaf`. 사용자 “운송이 충분히 출발하고나서 출발했어야지…경로가 겹치는데” 지시로 시뮬 시험 순서 수정. 공통/실물 주행·속도·105 판정·허용 오차 변경 없음.
- 실패 근거: `sim/runs/fresh_full_cycle_20261030_114723_after_push/failure_analysis/attempt_001/transport_start_rotation/README.md`. 수확 복귀와 운송 선별장 출발이 약15ms 차이, 저장 자세/고정 충돌 형상 겹침. 접촉력 직접 기록은 없음.
- `sim/tools/single_cycle_steps.py`, `probe_sorter_cycle.py`: 인계 완료 후 운송만 먼저 출발. 자기 선별장 작업 WAITING_FOR_UNLOAD + 기존 정지 확인 + UNLOAD_READY 접수 후 원자적으로 저장한 도킹 증거가 있어야 수확 복귀 허가. 교통 미연결 시험에서 공유 통로 이탈을 보수적으로 선별장 도킹까지 기다린다. 시간 경과만으로 출발하지 않으며 운송 실패/증거 누락이면 수확 출발 없음. 기존2400초 시험 watchdog을 사용하며 주행 자체 시간/성공 조건은 유지한다.
- 이미 모듈을 import한 현재 attempt_002는 새 함수를 반영하지 못하므로, 인계 전 base fixture의 기존 overlap_cycle 분기만 false로 선택했다. 현재 시험은 선별 및 운송 복귀까지 전부 완료한 뒤 수확 복귀. SEC02 예찰과 최종 예찰 복귀는 프로세스의 기존 활성 플래그로 유지. 시뮬 중지/재시작 없음. 원본 fixture와 변경 시각은 해당 attempt의 `fixture.before_departure_sequence.json`, `departure_sequence_override.json`에 보존.
- 검증: `python3 -m pytest -q sim/tests/test_cycle_departure_order.py` 4PASS(도킹 확인 후 허가, 운송 실패·증거 누락·거절 시 미출발), py_compile/diff check 통과. supervisor/두 시험기 프로세스 생존 확인. 수정 후 실제 출발·전체 사이클 성공은 아직 미검증.
- 복원: 두 시험기에서 이번 도킹 증거/대기 블록 제거. 현재 fixture 복원은 진행 단계 확인 후에만 수행하며 과거 동시 출발 문제를 다시 활성화함에 유의. 커밋·푸시 없음.


## 2026-10-30 — 포트폴리오 작업 장면 외부 카메라 촬영 준비

- 사용자 요청: 전체 전경 대신 수확 작업/운송 인계/선별팔 작업 사진. 기준3993790 및 기존 출발 순서 수정 보존. 현재 headless 시험은 중단하지 않는다.
- 대상: sim runtime `portfolio_capture.py`, `run_fleet.py`, 시험기 `run_single_cycle.py`. 해당 캠페인의 명시적 portfolio_capture.json 요청만 다음 실행 runtime으로 전달. 외부 Camera 한 대,1920×1080,사선2방향,장면별 최대6장. 촬영 시에만 데이터 수집/Hydra 렌더를 활성화하고 기존 물리/렌더 tick을 그대로 사용. 센서/제어 입력·공통/실물 코드 변경 없음.
- 실제 HARVEST/WAIT_BOX, basket hold_pass, 투입 후 선별팔 작업 단계로 촬영. 인계 사진은 실제 바구니 정렬 장면이며 가상 과실 인계를 실제 배출 기구 동작으로 설명하지 않는다. PNG는 무자막 원본, JSON에 session/작업 상태/시뮬·렌더·실제시간/구도 기록. 실패는 capture_error.json, 제어 실패로 간주하지 않음.
- 준비/예약: sim/runs/fresh_full_cycle_20261030_114723_after_push/portfolio_capture.json 및 PORTFOLIO_CAPTURE.md. 현재 이미 실행 중인2차에는 적용되지 않음. 다음 실행의 screenshots/portfolio/로 저장한다. 해당 반복 시험이 이번 시도에서 성공해 종료하면 별도 촬영 실행이 필요하며 촬영 완료로 보고하지 않는다.
- 검증: py_compile/diff check, 실제/대기 상태 선택 및6개 카메라 자세 오프라인 검사 통과. farm_sim_runtime colcon build 성공, 설치본 갱신. Isaac 실제 외부 렌더·구도/가림·추가GPU부하 미검증. 촬영 후 육안검수 및 대표컷 선정 남음. 새GPU시뮬 병행 실행 없음.
- 복원: 캠페인 portfolio_capture.json의 enabled=false로 다음 실행 촬영 비활성. 이미 준비된 runtime도 동일 파일 비활성화. 커밋/푸시 없음.


## 2026-10-30 — 2차 예찰복귀103·레이저8/실제13 분석

- 사용자 원인/초기배치 확인 요청. 읽기 전용 분석, 공통/실물/시뮬운영 코드 추가 변경 없음. 현재3차 유지.
- 2차 선별13/13(빨강7·노랑6), 수확/운송복귀 성공. 마지막 SEC02예찰복귀103: 공통 StationReturn의 가상 스테이션→현재 경로 역순/전구간후진 방식과 완료 차체방향 불일치. 명목경로 재구성 북진, SEC02 차체도 북향. 정확한 당시 carrot입력은 미기록.
- 레이저 W007 두 번째부터 beam1 지속차단→통과 REJECTED, W008/009 CLEARING 대기. 후속5과실 바구니 실제수령/선별되지만 레이저 계수8에서 정체. 지속차단 물체ID는 미기록, 적재물 추정과 구분.
- 원본 USD 읽기 확인 SEC01 빨강7/노랑6/초록7, ripe13개 ID와 인계13개 완전일치. 증거/재현/보고서: sim/runs/fresh_full_cycle_20261030_114723_after_push/failure_analysis/attempt_002/README.md 및 diagnosis.json/initial_fruits.json. 미커밋·미푸시. 분석 파일 제거로 복원 가능.


## 2026-10-30 — 실물 스테이션 도킹과 복귀 변경 호환성 검토

- 사용자 실물 구조물 도킹 보존 지시. fetch 성공 후 feature_dongmin366e0c3/실물수확e135cde 비교. 코드는 미변경, 시험 유지.
- 운송은 일반접근A→마커32 관측/티칭목표 전진진입→20→3 출발방향 주차회전→정지/도킹성공. 예찰·수확 StationReturn은 양 실물브랜치/로컬 동일 후진코드이며 real docked=false, 별도 최종도킹 미연결. 실기검증으로 확대하지 않음.
- 결론: 접근 경로 선택과 정밀도킹을 분리하고 실물 기존 최종방식 유지. 일괄 도착후회전/후진진입 적용안은 채택하지 않음. 상세 및SHA: sim/docs/changes/REAL_STATION_RETURN_REVIEW_20261030/README.md, source_comparison.json. 분석문서만 추가, 제거로 복원. 미커밋·미푸시.


## 2026-10-30 — 승인된 공통 스테이션 복귀 방향 선택

- 사용자 명시: 예찰/수확 실물마커도킹 없음, 경로길이에 따른 전진/후진 복귀 및 전진도착후180도 주차정렬 공통코드 수정 승인.
- station_return.py 및 새 공통 test_station_return.py 변경. 후보거리/초기방향 로그, 기존RPP 전진과 StationReverse 후진 선택. 스테이션yaw/정지확인·충돌·실패/취소·시간·실물/시뮬결과계약 유지. 운송코드/설정 미변경.
- 57PASS 및 시뮬 지도32명목종점 계획 성공. 현재3차 유지, 다음실행부터 적용. 물리/실기 미검증. 상세 docs/changes/STATION_RETURN_DIRECTION_20261030.md. 복원은 이번공통변경만 역적용. 미커밋·미푸시.


## THRESHOLD-OVERRIDE-AUDIT-20261030 — 실물/시뮬 최종 한도 전수 비교 자료

- 승인/범위: 사용자 판정 한도·한계·덮어쓰기 전체확인 요청. 운영변경 없음; 감사도구/문서만 추가. 기존시험/미커밋변경 보존.
- 기본값·환경override·생성인계서버·시험runtime을 비교. 수확각도6°/3°, 충돌재시도5/0, 예찰준비300/120초·RPC180/30초, 최신실물복구기능 차이 확인. 의도적D059/벽0.8°/운송progress/시뮬예산 예외 별도표시.
- 검증: collector3구성 실행,4482행비교,실행중controller입력419개대조, W005원시측정 허용치재계산(real통과/sim거절). ROS직접dump실패보존. 실제로봇/신규Isaac재현시험은 하지 않음.
- 결과: sim/docs/changes/THRESHOLD_OVERRIDE_AUDIT_20261030. 공유정책 정합과 외부watchdog수정은 후속작업. 실물·시뮬 동작 영향 없음. 복원은 이번 감사자료/추가문서절만 제거. 미커밋·미푸시.


## 2026-10-30 — 실물 수치 정합 및 예찰 TF 대기 통합

- 사용자 실물 우선 정합/TF 무제한 대기 승인. 인계 선택 수확 도착6°·충돌 재시도5회, 일반 수확 속도0.1m/s·0.1rad/s 및 Spin 실물값, 예찰 영상 준비300/RPC180실제초 반영.
- 최신 실물 공통 Nav2 활성화 확인·취소 가능한 TF 무제한 복구 연결. 기본 false/선택된sim예찰true. 기존 ROS 시계·거리별 예산·충돌 복구 유지. 선별 외부 시험 대기가 내부1800초를 먼저 자르지 않도록 정합.
- 연결선5°/벽0.5°/운송병진전용진행검사/도킹전환여유0 복원은 상세 설명 요청으로 보류. 예찰 범위도 승인 미수신으로 기존값 유지. 환경/기존승인 예외 유지.
- 관련44PASS 및 추가 설정검사+주행 전체233PASS(중복 합산 금지), 세 패키지 빌드·설치 모듈 확인. 최초 이전설치본 참조4실패는 source검사/빌드 후 해결. 새 실제전체시험 미실행, 진행 중 시험 중단 없음. 새 생성/프로세스부터 반영.
- 상세 sim/docs/changes/REAL_SETTING_ALIGNMENT_20261030.md; 생성값 sim/runs/real_setting_alignment_20261030/effective_values.json. 미커밋·미푸시.


## 2026-10-30 — 운송 이동·회전 진행 판정 실물 정합

- 사용자 병진/회전 진행인정 지시. 실물 운송 Nav2 원본366e0c3을 로컬 원래 경로에 추가하고 progress_checker만PoseProgressChecker/각도0.5rad로 변경. 시뮬 기존검사와 동일, 병진0.1m/정체10초 및 기타실물수치 유지.
- 별도 환경YAML의 선택/판정값 동등성 회귀2개와 기존 짧은 경로검사 포함12PASS, 설치 Nav2 검사기7PASS(오프라인; DDS sandbox 경고). 새 물리시험/실물배포 없음.
- 짧은 작업이동 해결은92ad63a 공통수정,18d0e00 통합의 선택적5°제한이 실물에서만 켜져 차이 재발. 해당정책은 이번 설명요청에서 미수정.
- 상세 sim/docs/changes/TRANSPORT_PROGRESS_PARITY_20261030.md. 실물담당원격브랜치 변경/배포/커밋·푸시 없음. 진행중시험 유지.


## 2026-10-30 — 공통 정지 후 오차 복구 승인·적용

- 사용자 “공통코드에서 … 조치한다음 커밋” 승인. farm_navigation 도착오류형, harvest wall 재보정, farm_docking 접근전 거절/정지증거, transport 상태 재접근 연결. 시뮬 전용 성공조건 변경 없음.
- 최초+재시도2회 한도, 원래 목표/거리/각도/충돌/취소 유지. 실패값/정지시각/재시도번호 기록. 새 회귀와 기존검사353PASS, 공통네패키지빌드 성공. 실제 새 시뮬시험 미실행/기존실행유지.
- 상세·복원 범위: docs/changes/STOPPED_ARRIVAL_RECOVERY_20261030.md. 이번 코드/검사/기록만커밋하고 이전수정은작업트리에보존. 원격push미요청.


## 2026-10-30 — 포트폴리오 근접 장면 연출 재촬영

- 승인: 사용자 요청으로 보라색 디버그 윈도우 제거, 벽 가림 없는 수확·선별·도킹 클로즈업 및 촬영용 배치/포즈 허용.
- `farm_sim_devices/scene_truth.py`: 평가 wire box visibility만 invisible. 좌표/과실 집계 계산 유지. 실행 중 프로세스 강제 변경 없음; 다음 시작부터 적용.
- `sim/tools/stage_portfolio_photos.py`: 독립 Isaac 세션에서 원본 USD 참조, 기존 U20 외형 함수와 HCR 자세 재사용, 관절/과실 연출, 카메라·조명 설정, PNG/JSON 저장. ROS 연결·운영 명령·동역학 없음. 모델 원본 저장 없음.
- 결과: `sim/runs/portfolio_staged_20261030/selected/` 원본 PNG 6장(1920×1080), 장면별 JSON, manifest, HTML 미리보기. `portfolio-photos-20261030.zip`에 최종본만 포함. 직접 이미지 열어 파지/선별/도킹 대상과 가림·디버그 제거 확인. 시험 성공 증거가 아닌 연출 정지 사진.
- 첫 2560×1440 병렬 렌더는 GPU 메모리 부족으로 종료(`render.log`). 기본 뷰포트 중단·먼 베드 비활성화·1920×1080으로 촬영 완료. 원래 attempt_005 PID 3744765/3744574는 계속 실행, 촬영 세션만 종료.
- 검증: 두 Python 파일 구문 검사, git diff --check, PNG 6장 형식/해상도·SHA256 확인 및 육안 검수. 공통 코드/실물 설정/성공 판정 영향 없음.
- 복원: SceneTruth에 추가한 visibility 2줄과 독립 촬영 도구 제거. 원본 USD 복원 불필요. `capture-changes.zip`은 이번 코드 2개 파일의 패치와 적용 안내. 변경은 미커밋·미푸시.

### 같은 날 — 촬영용 줄기 재질 비활성화 오류 수정

- 사용자 회색 줄기 지적에 따라 확인: 원본 `Vegetation/Looks/Stem`은 짙은 초록색이나, 촬영 도구가 Bed_01/02 이외의 모든 자식을 비활성화하면서 Looks까지 껐다. 실제 USD에서 기존 조건 적용 시 bound material이 무효, 수정 조건에서는 원래 색상 `(0.075, 0.19, 0.028)`과 연결이 유효함을 확인했다.
- `stage_portfolio_photos.py`의 비활성화 대상을 `Bed_` 이름에 한정. 별도 Isaac 세션에서 수확 사진 2장을 다시 렌더링하고 직접 열어 초록색 줄기 확인. selected PNG/JSON, manifest, 사진 ZIP 및 코드 패치 ZIP 갱신. 수정 전 사진은 `stem_material_fix/before/`, 비교 수치는 `stem_material_fix/material_diagnosis.json`에 보존.
- 원본 자산·운영 시험·물리·판정 변경 없음. 촬영 프로세스만 종료. 구문 검사 및 PNG 1920×1080/해시 확인. 재현용 수정 전 조건은 진단 자료에 보존. 미커밋·미푸시.

## 2026-10-30 — SEC01~16 전체 사이클 및 실제 동작 영상 캠페인

- 승인: 사용자 전체 SEC 예찰~복귀 순차시험, 실패 SEC 재시도, 실제 수확/도킹/이동의 여러 각도 30초 영상 및 로그 요청. 기존 SEC01 반복 감독자에 SIGINT로 정상 종료, 로그/중단 사유 보존 후 전환.
- 시뮬 시험 도구만 확장: `run_single_cycle.py --section`, `single_cycle_steps.py`의 해당 SEC 새 예찰/복귀 및 맵 데이터 기반 운송 목표 투영, `run_fresh_cycle_until_success.py --sections`의 완료 SEC 보존·실패 SEC 재시도/실패분석. 기존 옵션 없는 SEC01+SEC02 시험 방식 유지. 교통 미연결이라 예찰 복귀 후 수확 출발, 운송 선별장 도킹 후 수확 복귀. 공통 액션/성공 한도 변경 없음.
- `probe_handoff_window.py`는 해당 캠페인의 시험 대기에 /clock을 사용하고 120실제초 clock 정지를 별도 감시. 최초/최종 과실 snapshot을 시도에 복사. `cycle_monitor.py`는 현재 SEC와 전체 SEC 완료 수를 표시.
- `portfolio_video.py`와 run_fleet 선택 연결: 외부 카메라 한 대, 촬영 때만 활성, 실제 동작 1920×1080/15fps/30시뮬초 MP4. 수확 최대4, 도킹/선별/각 로봇 이동 최대2클립/시도. 로봇 상대 근접·드론 시점, 원본 센서 입력·조명·모델/물리·제어 미변경. 프레임별 시뮬시각/카메라 및 중복 프레임, 실패·중단 영상은 별도 기록. GPU 영상은 추가 렌더 부하가 있으며 물리는 CPU 유지.
- 오프라인 45PASS(16SEC 투영, 완료누락 거절, 영상 시각, 기존 출발순서/모니터 포함), 16개 설정 생성, sim 2패키지 빌드 성공. 현재 `sim/runs/section_full_cycle_video_20261030_174700/attempt_001` SEC01 시작. 전체 통과/전체 영상 검수는 아직 미완료. ROS Domain13/SUBNET. 기준 a2db520+기존 미커밋; 커밋·푸시 없음.
- 복원: 이 절의 시험 도구 옵션/영상 모듈/선택 연결만 되돌림. 코드·설정·실행 자료와 이전 미커밋 변경을 별개로 보존. 실행 STOP은 캠페인 루트 STOP 파일 생성 또는 감독자 SIGINT.
- 최초 실제 촬영 확인: `attempt_001/videos/travel_scout_01-01.mp4` H.264,1920×1080,15fps,450프레임,30.000초(ffprobe),중복0,encoder0. 시작/끝 PNG 직접 확인. 수확·도킹·선별 영상 검수 및 전체16SEC 통과는 진행 대기. 캠페인 README·source_manifest·changed-code.zip에 실행/전달 조건 기록.

### 같은 날 — 고정 광각·다양한 각도·AprilTag 원본 영상 추가

- 사용자 고정 시점/광각/각도 다양화/태그 카메라 시점 요청. portfolio_video에 이동 고정광각18mm·낮은사선25mm·긴통로고정14mm·추적드론23mm 순환, 작업 근접/고정측면/상부/하부 구도 추가. 클립·재시도마다 순환하고 파일명/JSON에 구도 기록. 고정 구도는 클립 중 카메라 갱신 없음.
- 실제 예찰/수확 태그 Camera의 원본 RGB/해상도/FPS를 읽어 촬영. 센서 자세/K/활성 상태를 건드리지 않고 추가 렌더를 만들지 않는다. 30시뮬초 및 실제 영상 원장 유지. 실행 중4차를 중단하거나 코드를 주입하지 않고 다음 시도에 적용. sim runtime 빌드 완료, 영상/기존clock순서 검사12PASS.
- 병행 조사: 1~3차 예찰 복귀가 미래 TF 거절로 실패. 20실제초 ROS관측4681표본 중66개에서 TF가 clock보다16.666668ms 앞섬. 수확·운송에 있던 state_clock_delay_s=0.1이 scout_fleet에 빠져 있었음. 같은 기존 sim 어댑터 순서 보정을 예찰 fleet에만 추가. timestamp/공통 거절 정책/물리/실물 변경 없음. 다음 실행에 원문과 복귀 결과 검증 필요.
- 근거/실행조건: `sim/runs/section_full_cycle_video_20261030_174700/capture_update/`. 현재 프로세스 유지, 미커밋·미푸시. 복원은 이번 영상 선택 확장과 scout_fleet의 새 지연 키만 제거.
- 후속 실제 확인: 4차도 같은 미래 TF로 종료한 후 자동 시작된 5차에 적용됐다. 고정 광각 MP4는 1920×1080/15fps/450프레임/30초이며 450개 프레임 기록에서 카메라 자세가 동일하다. 실제 AprilTag 원본 MP4 2개도 각각 1280×720/10fps/300프레임/30초, 중복0으로 저장했다. 시작 PNG를 직접 확인했고 센서 영상에서 베드 태그가 보인다. 관련 회귀는 총55PASS.
- 5차 ROS 재관측: clock 수신 전 초기112표본은 별도 보존·제외하고, 유효4214표본에서 미래 TF 0건, TF 나이50~100ms. 원문·비교는 capture_update/scout_tf_age_after.json 및 tf_age_comparison.json. 예찰5/5 완료 후 복귀 중이며 복귀/전체 사이클 성공은 아직 미확정.

후속 18:16:01 KST: attempt_005 scout_return_result는 status=4, result_code=SUCCESS, docked=true, error_code=NONE으로 확인. 앞선 1~4차가 실패한 예찰 복귀를 실제로 통과했고 같은 시각 수확 W001을 요청했다. 현재 전체 SEC 완료가 아닌 수확 진행 중이다. 근거: attempt_005/events.jsonl:15643~15644, capture_update/tf_age_comparison.json.

## 2026-10-30 — 수확로봇 촬영 외형 누락 조치

- 사용자 수확 영상 외형 누락 지적. 5차 실제 isaac.log:831~851에서 21개 상자형 외형의 `cannot find protoPath`와 기둥/상판/바구니가 빠진 RGB를 확인했다.
- sim robotarm_asset_setup.py: Cube가 포함된 visuals 인스턴스만 session layer에서 해제. 기하·재질·변환·충돌·관절·질량·drive와 원본 USD 유지. run_single_cycle.py는 해당 소스도 시도별 snapshot에 기록. 공통·실물 수정 없음.
- 실제 USD 전체 composed 속성/관계·충돌 인스턴스·원본 보존 검사1PASS, 기존 자산/학습 정합11PASS, 촬영4PASS, runtime 빌드 성공. 별도 Isaac CPU 물리 장면1920×1080에서 전체 차체 표시 확인. 단독 장면은 수정 전에도 누락 미재현이므로 버그 재현 성공/농장 통합 해결 완료로 취급하지 않는다. 최초 PhysX 환경 경로 누락 검사 실패는 환경 설정 후 통과했다.
- 진행5차 중단/코드 주입 없음. 다음 자동 시뮬 시작부터 적용, 통합 RGB/오류 재검증 필요. 센서 RGB에도 원래 외형이 복원되므로 적용 시도 구분. 기존 영상 quality_review.json에 최종 포트폴리오 부적합 표시, 시험 로그 유지.
- 근거/비교 사진/재현 조건/전달 패치: sim/runs/harvest_visual_fix_20261030/README.md 및 changed-code.zip. 복원은 새 helper와 configure_harvest_arm 호출/보고 필드 제거 후 재빌드. 기준 a2db520+기존 미커밋, 미커밋·미푸시.

## 2026-10-31 — 영상 촬영과 운송 TF 단절 조사

사용자 촬영 영향 확인 요청. TF 실패5건 모두 영상 경계와 연관: 8/11/12/19차 운송 클립 저장 종료 프레임0.55~0.68실제초 지연 뒤 실패, 10차 미완성 운송 클립 시작0.407초 지연 뒤 실패. 시뮬 루프의 동기 PNG/인코더 종료 대기와 운송 위치 캐시 실제시간1초 만료를 코드에서 확인. 상세 조회 예외 미기록으로 분기 확정 불가, 촬영 ON/OFF 대조 미실행이므로 유력 유발 요인으로 판단. 직전 두 캠페인 결과/오류32파일에서 같은 문자열0건이나 동일조건 대조 아님. 근거 sim/runs/video_tf_investigation_20261031/README.md. 진행 시험 유지, 이 조사에서 코드/설정/판정 변경 없음. 다음은 촬영 저장 분리 및 운송 구간 비교 검증. 미커밋·미푸시.

## 2026-10-31 — 동작 판정 시간 기준 통일 요청·적용 전 조사

사용자 시뮬 동작의 실제시간 사용 금지 지시. Python 시간 호출69파일463개 후보(공통48파일), C++/blocking wait 후보를 조사·보존했다. 운송 위치/센서 캐시, 정밀제어·도킹해제, lease 및 sim UDP watchdog에 실제시간 잔존 확인. 생산/소비 시각 함께 변경, sim은 ROS/world clock, real은 기존 monotonic, pause/reset/시각0 검증안 마련. 구체 범위·파일: sim/runs/sim_clock_audit_20261031/PROPOSAL.md. AGENTS 공통 변경 사전 확인 규칙에 따라 공통 적용 승인 대기. 이번 조사에서 코드·설정 수정/프로세스 중단 없음, 미커밋·미푸시.


## 2026-10-31 — 공통 동작 시계의 sim/real 선택 적용

- 승인: 사용자 “시간 시뮬레이션 시간으로 시뮬레이션 시행시에 맞추는 코드 공통코드에 작성하고 커밋푸시”. 기준 a2db520. 기존 미커밋 변경과 실행 시험은 보존.
- farm_navigation.operation_clock.operation_time: ROS sim clock 활성 시 /clock 초, 실물은 기존 monotonic. farm_common→farm_navigation 기존 의존 방향을 유지하기 위해 navigation에 배치. farm_docking의 의존성만 추가.
- 운송 pose/scan/device 수신과 만료, lease/명령, 정밀 도킹·이탈·센서 회복, Nav2/Spin 응답·취소·TF/충돌 회복·정지 대기, 수확 팔/인계/배출·영상 RPC 대기에 생산·소비 시계를 함께 적용. 하위 legacy 도킹의 lidar 버퍼도 같은 기준. lease 독립 IO 타이머는 부모 ROS 시계 사용.
- 제한시간 수치/거리/각도/수확 성공 조건은 변경하지 않음. 프로파일링·일시·OS 종료 정리는 실제시간 유지. 시계0에서 실제시간 fallback 금지, gate는 clock 준비 전 소유권 거절. 시계 역행 시 이전 lease 무효화·미래 수신 캐시 거절; 시뮬 reset은 기존 캠페인처럼 관련 노드를 재시작해야 함. 모든 노드의 무중단 reset 복구를 보장하지 않음.
- 검증: 작업 트리 대상 회귀126PASS, 공통6패키지 빌드 성공. 커밋 전용 소스(기존 미커밋 기능 제외) 별도 검사 결과는 상세 문서 참조. 실제 촬영 ON/OFF 비교·전체 사이클 재검증은 미실행. 실행 중인 프로세스에 hot reload하지 않으며 다음 노드 시작부터 설치본 적용.
- 남은 범위: sim UDP/ROS 어댑터·world command watchdog·시험 도구의 실제시간 경로는 이번 공통 코드 커밋에 포함하지 않음. 따라서 시스템 전체의 실제시간 판정 제거 완료 또는 TF 실패 완전 해결로 보고하지 않는다.
- 상세: docs/changes/OPERATION_CLOCK_20261031.md. 복원은 이 변경 커밋만 revert 후6패키지 재빌드; 기존 허용값을 조정하지 않는다.


## 2026-10-31 — 실물 수확 복귀 컴포넌트의 시뮬 연결

사용자 분석·수치 선택·반영 승인으로 cf4023b의 Mission/Controller/States와 정리 보완·선택형 후진 충돌 분류를 도입했다. 원본 상태 코드는 그대로, Mission에는 기존 전진/후진 선택과 시뮬 시계 주입만 추가했다. 복귀 검사5cm/6°, 출력 소유자가 있는 전체 사이클 재시도5회; 단독·교통 프로필은 기존0회. Nav2 도착4cm/2.5°·속도0.1m/s 유지. 시뮬 지도/스테이션좌표·최종방향·마커 생략·SUCCESS/docked 의미 유지. 실물 코너반경/벽도킹 측정치/팔상태생략은 가져오지 않았다. 전체 사이클 생성 설정과 최종9개 제어값 비교 완료. 실제 Isaac 복귀 검증은 아직 하지 않았고 진행 시험은 유지했다. 상세 및 소스 범위: sim/docs/changes/HARVEST_RETURN_COMPONENT_INTEGRATION_20261031.md; 수치 근거 sim/runs/return_components_20261031/effective_settings.json. 미커밋·미푸시.


## 2026-10-31 — 발표 정지 이미지 자료 확보 및 시험 종료

사용자 요청으로 section_full_cycle_return_20261031_155740 시험을 STOPPED로 종료하고 로그를 보존했다. 신규 전경·작업구역·U20 센서 시점은 GUI 별도 연출 세션으로 촬영, 원본 USD·공통 코드·업무 판정 변경 없음. 기존 예찰/수확 실제 기록과 기존 연출 사진을 재사용하고 실제/연출/로그 설명도를 이미지별 구분했다. 촬영 도구에 GUI/전체 베드 유지, 최신 예찰 mast 설치, 외형 인스턴스 누락 방지, 카메라 up 방향 및 정수 좌표 지원만 추가. 전달: sim/runs/presentation_stills_20261031/delivery, presentation-stills-20261031.zip. 발표4장과 원본/파생본/예찰 근거 총34PNG, manifest의 커밋·설정·출처·해시 확인. 과거 U20 실제 실행의 로딩 커밋은 미확정으로 명시. 증강5종 픽셀 일치 재현 확인, 밝기 변경은 gain/gamma 후처리이며 물리 광원 재렌더 아님. 시뮬 시험은 재개하지 않음. 변경 미커밋.


### 발표 전경 수정 — 수직 탑뷰

사용자 요청으로 전경만 GUI 수직 탑뷰로 교체. station_spawn.json의 scout(-5,13.25), harvest(-2,13.25), transport(2,13.25), yaw=-pi/2 적용. 29.5m 수평 시야, map +Y 화면 왼쪽/+X 위. 원본·라벨2PNG 교체, 다른32PNG SHA256 동일 확인. 동일 delivery/index.html 및 ZIP 갱신, 이전 전경은 before_topdown 보존. 촬영 세션 종료, 시험 재개 없음. 공통 코드·원본 모델 수정 없음.


## 2026-10-31 — 선별 미달을 캠페인 재시작 사유에서 제외

사용자 지시로 전량선별 요구를 성능지표로 변경. 공통 선별 액션 SUCCESS와 모든 로봇 복귀/인계/수량검증은 유지하고 input/sorted/remaining/비율을 기록한다. attempt001은13개중8개 선별 후 ROI미검출로 정상 종료했으나 시험기의 별도전량조건으로 실패했음. attempt002의103은 후진제어기의 InvalidPath 방향검사. 근거/미확정 범위/복원은 sim/runs/section_full_cycle_return_20261031_165651/sort_policy_review/REPORT.md. 시뮬시험기3파일 및 기존 회귀시험만 수정, 실물코드 영향 없음. 기존 2026-10-30 전량선별 캠페인 조건을 이 결정으로 대체한다.21테스트PASS. attempt003 중단 없이 fixture 갱신 및 감독만 인수, 실제 다음섹션진입은 미확인. 미커밋·미푸시.


## 2026-10-31 — 후진 경로 검사와 도착 후 방향 정렬 분리

사용자 “수정은해야될거아니야” 승인. c40a036+기존 미커밋 기준. 공통 farm_nav2_controller의 reverse cpp/hpp 및 기존 test_settling_controller.cpp만 변경. 최단경로 선택은 시작 방향만 검사하며, 기존 후진 제어기는 도착 후 yaw 정렬에도 pi/2+0.1 제한을 적용했음. 도착 후에는 유한한 최종 yaw 정렬을 허용하고 주행 중 방향한계, 충돌검사, 도착 허용값, 속도, GoalChecker 성공판정은 유지. 오류에 TRACKING/FINAL_ALIGN 및 angle_rad 기록. 실물·시뮬 공통 적용.

14개 gtest PASS, 별도 /tmp/reverse103_build 빌드 성공. 실행 중 mmap을 보존하기 위해 설치 so는 새 inode로 원자 교체; 현재 실행 시험/ROS는 중단하지 않음. 다음 제어기 프로세스부터 적용. 증거·기존 so 백업: sim/runs/reverse_heading_fix_20261031. 복원은 before.so를 동일 방식으로 설치 경로에 교체하고 이번 소스 diff만 되돌림. 미커밋·미푸시.

한계: attempt002의103은 해당 방향 검사에서 발생한 것이 확정이나 기존 로그에는 분기/각도가 없어 이번에 수정한 도착 후 정렬 분기였는지는 미확정. 따라서 실제 실패 재현 해결 완료/실물 주행 검증 완료로 보고하지 않음. 주행 중103이 재발하면 추가 진단값으로 분석 필요.


### 2026-10-31 — 103 원본 차체 기록과 CPU 재현 추가 확인

원본 drive_diagnostics에는 실제 T_world_base가 있음. 실패 실제좌표(-6.667,11.909)로 코너Y11.5를 약40.9cm 초과한 것이 직접기록으로 확인됨. 직전에는 계속-0.15m/s 명령이 있었으므로 정지명령 후 단순미끄러짐 설명은 부적절. 같은경로 정확한위치 피드백 CPU실행은 통과; 실제실패위치 강제재생은 TRACKING/angle=-1.800683rad로 거절재현. 코너전Y11.359에서 실제명령은후진, 정확한좌표를준제어기는병진정지로 갈라짐. 당시제어입력불일치 증거이며, AMCL/TF 중 단일원인의 확정자료는 없음. 상세 sim/runs/reverse103_repro_20261031/REPORT.md.

공통 reverse 제어기에0.5ROS초 주기의 동일stamp pose/map_pose/carrot/angle/distance/lookahead 진단추가, 거절조건시즉시기록. 동작판정추가변경없음.14개 회귀통과, 별도빌드 및 실행중so매핑보존 원자교체. 다음제어기시작부터적용, 현재시험유지. 앞선 도착후회전 수정은 이번실패해결로 인정하지않음. 미커밋·미푸시.


### 2026-10-31 — SEC01 운송 접근 목표/시작 준비 검사 수정

사용자 “둘다 뭔이슈야 원인파악하고 해결해” 승인. sim/tools/single_cycle_steps.py, probe_handoff_window.py 및 sim/tests/test_full_section_cycle.py만 변경. 4차는 윈도우와 같은 Y로 접근하는 시험 목표가 marker42 미전환 시 수확 차체까지 진행시켰고 수확로봇 실제 변위38.49cm 후 FOOTPRINT_COLLISION/Recovery timeout 발생. 섹션별 대기 목표를 기존 marker 장착값과 접근 거리에서 계산: SEC01 중심 간0.98m. 5차는 운송 Nav2 configure 미완료/ready=false 상태를 액션 서버 연결만 보고 예찰·수확을 진행한 결함. 예찰 전·운송 호출 전 새 RobotStatus.ready 확인과 실패 원문 기록 추가. 공통 로직·실물 설정·도킹 판정은 불변.

23개 관련 검사 통과, py_compile 통과. 현재 6차의 실제 ROS 구독 ready=true 확인. 기존 전체완료 검사 중 예전 미선별 실패 정책 기대4개는 별도 불일치로 기록. 현재 6차 유지; 새 목표/준비 검사는 다음 실행부터. marker42 미전환 세부원인 및 Nav2 configure 내부 중단 호출은 기존 로그로 확정 불가하여 관측 원문 추가. 위험 목표/미준비 요청 결함 수정과 실제 E2E 통과를 구분한다. 상세/수치: sim/runs/pickup_failure_analysis_20261031/REPORT.md. 미커밋·미푸시. 복원: 이번 함수 및 추가 구독/시험 diff만 되돌림.

추가: run_single_cycle.py의 시도별 selected_sim_sources.json에 두 시험 연결 소스의 본문·SHA256도 저장하도록 추가하여 다음 실행 적용본을 식별한다.


### 2026-11-01 — 공통 운송 인계 경로의 후방 진입 보장

사용자 실물·시뮬 공통 수정 명시 승인. farm_navigation/route.py 선택적 방향 제한 + transport_robot/navigation_adapter.py 및 harvest_approach.py에 인계 전용 적용. 목표와 같은 방향으로 진입하고 해당 직선 통로 역방향/목표 초과 통과는 금지. 경로 없음은 거절, 일반 운송/도킹 판정·수치 불변. 공통·SEC01~16 경로 검사33개 통과. 설치3개 Python 파일 교체; 8차를 적용 목적 중단으로 기록하고 캠페인 감독기로 SEC02 재시작. 실물 및 수정 후 도킹 성공 미검증, Nav2 충돌 미검출 별도 과제. 상세 docs/changes/TRANSPORT_REAR_APPROACH_20261101.md, 경로·설치 증거 sim/runs/rear_approach_fix_20261101. 미커밋·미푸시.


### 2026-11-01 — 후방 접근 옵션의 제어권 래퍼 전달 누락 수정

9~14차 6회 모두 ExclusiveNavigator.navigate() got an unexpected keyword argument rear_approach로 실패. 이전 공통 후방 접근 수정의 호출 경로 검증 누락으로 발생한 회귀다. farm_docking/clients.py의 ExclusiveNavigator.navigate가 키워드 옵션을 내부 Navigator에 전달하도록 수정. acquire/try/finally/release 순서와 기존 일반 호출 보존. 사용자의 기존 실물·시뮬 공통 후방 접근 수정 승인 범위 내 보완.

sim/tests/test_pickup_navigation_chain.py는 실제 HarvestApproach→ExclusiveNavigator→TransportNavigator→RouteGraph 호출을 연결하여 경로 계산까지 실행하고 ROS 이동 직전에 종료한다. 전달 성공/경로 오류 시 lease 해제/일반 호출 포함, 후방 경로 검사와 합계26개 PASS. 설치 clients.py 원자 교체 및 설치된 시그니처 확인. 실제 도킹 성공은 아직 확인하지 않음. 15차도 구버전이 로드돼 적용 목적으로 종료했고 operator_interruption.json으로 신규 로봇 고장과 구분. 캠페인 감독기 유지, SEC01 완료 보존. 설치 백업·해시 sim/runs/rear_approach_fix_20261101. 미커밋·미푸시.


### 2026-11-01 — SEC02 수확 완료 상태로 운송 재개 시험 전환

사용자의 시간 절약/빠른 진행 요청과 예찰·수확 재반복 중지 방침에 따라 전체 캠페인에 STOP을 기록. SEC01 성공 보존. sim/tools/run_single_cycle.py의 저장 예찰 재사용을 SEC01 고정에서 등록 섹션으로 확장하고 해당 heading의 윈도우 순서를 검사. 새 예찰 캠페인의 partial_result.json/scout도 정규화하여 기존 재개 도구에 연결. 지도 해시·성공 결과·수량 검사는 유지. 재개 schedule에는 실제 섹션/시뮬시간 대기를 지정하며 추가 예찰/복귀를 요청하지 않는다.

14차 SEC02 수확 완료 partial_result 및 final_scene으로 prepare-only 성공: 집계10, 물리 바구니11. 현재 세션 도착 전용 Action/복원 바구니 검사를 거친 후 실제 운송·인계·선별·복귀 실행. 예찰/팔 재수확 없음. 관련 기존 섹션 검사19개 통과. 실행 경로 sim/runs/sec02_transport_resume_20261101_attempt01, 준비 검증 sec02_transport_resume_20261101_preflight. 전체 신규 사이클 성공으로 합산하지 않는다. 미커밋·미푸시.


### 2026-11-01 — SEC02 가상 덮개 유지 시간 경쟁 수정

사용자 원인 확인·수정·재개 요청. sim mechanical_ros.py와 test_virtual_mechanical.py 변경.
정렬71.52%, 정지/신선도 충족이나 held=.6833초<.8초라 즉시 거절된 증거 확인.
정렬·정지가 이미 유효할 때 현재 세션에서 최대 시뮬2초 새 hold_pass를 대기하며 실제 판정 기준은 유지.
STOP/이동/세션 변경/만료/시간 초과는 거절. 실물·공통 코드 영향 없음.
12개 단위 검사 통과, 설치본 반영. 복원/증거 sim/runs/lid_hold_fix_20261101/REPORT.md.
SEC02 수확 완료 attempt014 재사용 운송 재시험 attempt02 준비. 실제 완료 미검증, 미커밋·미푸시.


### 2026-11-01 — 인계 복귀 회전 정지 후 재보정
사용자 원인 확인·수정·시험 재개 지시. 공통 harvest_robot/handoff_planning.py, handoff_navigation.py 변경.
SEC02 resume attempt02: Spin 성공 후 정지 시 위치1.7mm(한계10mm), 방향0.019540rad(한계0.017453rad)로 실패.
Spin 결과만으로 정지 후1도 정확도를 보장하지 못하며, 기존 align은 잔차 재보정 없이 종료했다.
위치 한도 안에서 방향만 초과한 정지 검사에 typed ArrivalValidationError 사용.
벽 정렬과 같은 최대2회 재계획/충돌검사/회전/정지확인 재보정 적용. 위치/방향 한도 불변.
공통 실물·시뮬 적용, 실물 미검증. 정확한 물리 잔여 회전/센싱 지연 기여는 미분리.
관련38개 검사 통과. 기존 precision-client fixture4개는 node 누락으로 실패해 별도 미해결 기록.
설치 Python 반영, 백업 sim/runs/restore_alignment_fix_20261101. 이 두 파일 이번 diff만 복원 가능.
미커밋·미푸시. SEC02 수확완료 재사용 재시험, 성공 후 SEC03~16 자동 실행 연결 예정.

SEC02 재시험 감독 실행: sim/runs/sec02_restore_resume_20261101/supervisor.py (PID2996827). 실패 시 수확 완료 재사용으로 재시도, passed=true와 종료코드0 확인 후 기존 감독기로 SEC03~16 자동 시작. 초기화 시작 확인; 아직 실제 복귀 성공 미확인.


### 2026-11-01 — SEC02 복구 시험 출발 순서 수정
실패는10cm 위치추정 오차가 아님. final_scene 실제(-3.28579,11.00116), 복귀요청 추정(-3.29384,10.95964), 차이약4.23cm(최종 스냅샷과 요청 시각 미세 차이 포함).
인계복원 SUCCESS 후 IDLE 수확 바구니는 운송 출발 중(-4.333,9.329)→(-3.446,11.459), 운송 복귀 통과 중(-2.987,11.184)로 실제 이동.
수확 자체 이동 액션 없이 운송 통과와 동시 발생한 물리 밀림 증거. 접촉력 로그는 없으므로 접촉 부위는 미확정.
시뮬 시험기 single_cycle_steps.py의 완료 수확 재사용 SEC02 분기만 변경: 수확 복귀 SUCCESS 후 선별장 출발 허가 공개.
실제 스테이션(-2,13.25) 기준 전진6.045m / 후진24.545m로 전진 선택 확인, 후방 운송과 반대 방향으로 이탈.
공통 주행·허용값·추정좌표 불변. 실패한 장면은 이전 시험 종료로 복구 불가하므로 보존 수확 상태에서 복귀 재시험.
출발 순서/복귀 실패 시 허가 차단2개 검사 통과. 증거 sim/runs/sec02_departure_recovery_20261101.
이 변경은 SEC03~16 일반 캠페인 교통 문제 전체 해결을 의미하지 않음. 기존 시험 STOP 후 새 복구 감독 시작 예정. 미커밋·미푸시.

SEC02 출발 순서 복구 감독 PID3199187 시작, attempt_001 초기화 확인. 현재 실패 미복구이며 실제 스테이션 복귀 결과는 검증 중.


### 2026-11-01 — 시험 조건 기록과 재개/신규 분기 동일 적용
사용자 시험조건 기록·재사용 지시. sim/docs/TEST_CONDITIONS.md에 출발·재사용·집계 조건과 검증 한계를 정리하고 sim/AGENTS.md에 시작 전 확인 추가.
SEC02 수확 우선 복귀를 재사용 전용 조건에서 신규/재개 공통으로 수정. 원래 임의 SEC 확장은 하지 않음.
출발 순서6개 검사 통과. run_single_cycle.py는 조건 문서 원문·SHA256도 selected_sim_sources.json에 보존.
진행 중 시험은 변경 전 코드지만 동일 SEC02 재사용 분기로 이미 수확 우선 순서 적용 중. 재시작/중단하지 않음.
실물/공통 주행 수치 영향 없음. 미커밋·미푸시. 복원은 이번 sim 파일 diff만 제거.


### 2026-11-01 — 수확 선행 출발 후 운송 조기 해제
사용자 “수확 먼저 스테이션복귀 출발, 운송 조금 대기 후 출발” 지시.
SEC02 시험기: 수확 복귀 액션 시작 후 현재 세션 RobotStatus의 task_id/map pose/수신 신선도를 확인.
스테이션 진입선(x=station_spawn의 수확 station x, ±0.1m)에 도달하면 운송 해제. 스테이션 도착은 기다리지 않음.
수확 복귀 실패가 먼저 발생하면 운송 해제 금지, 복귀 액션 결과는 최종 확인. 공통코드/주행수치 변경 없음.
출발순서6개 검사 통과, 문법 검사 통과. 실제 새 해제 조건 실행 검증 전.
현재 sec02_departure_recovery_20261101/attempt_001은 이미 읽은 이전 코드(수확 도착까지 대기)로 계속 실행.
새 조건은 다음 프로세스부터 적용하며 현재 시험을 이 변경만으로 리셋하지 않음. 미커밋·미푸시.


### 2026-11-01 — 전 섹션 경로 기반 출발 순서
사용자 특정섹션 한정 제거 지시. sim/tools/cycle_departure_gate.py 추가, single_cycle_steps.py SEC02/overlap 출발분기 제거.
최신 RobotStatus/map 좌표 + 공통 RouteGraph/plan_station_return + 실행 프로필 footprint로 순서 선택.
수확이 운송경로 점유 시 수확 선행, 아니면 운송 선행. 현재 선행 위치가 후행 경로에서 차체 여유 이상 벗어나야 출발.
상호 점유/오래된 관측/오류에는 해제하지 않음. 양쪽 최종 결과 별도 확인. 공통/실물 수치 변경 없음.
19개 단위 검사 통과(16좌표변형 포함). 실제 SEC02 실행프로필/공통경로 연결검사 수확 선행 확인.
TEST_CONDITIONS 갱신, 새 모듈 실행 원문/해시 보존 추가. 전체16SEC 실제 검증 전.
진행 중 attempt001은 기존 수확복귀완료 대기 방식 유지. 자동 재시도 및 SEC03 이후 새 프로세스부터 일반 규칙 적용.
미커밋·미푸시. 복원: 이번 시뮬 시험기 변경만 되돌림.


### 2026-11-01 — 선별장 인계 + 수확 복귀 완료 시 운송 즉시 복귀
사용자 지시 적용. 시뮬 single_cycle_steps.py가 수확 복귀 액션 성공 결과를 현재 시험 토큰으로 기록.
probe_sorter_cycle.py는 실제 unload/정지 확인 후 수확 SUCCESS/docked 증거를 기다리고 운송 복귀 요청.
선별팔 결과는 출발 전 기다리지 않고 병행 후 최종 확인. 전체 SEC 신규/재개 공통, 순수 선별 단독시험은 기존 조건 유지.
허가6개/출발19개 총25검사 통과, 문법검사 통과. 실물 공통코드 변경 없음.
현재 실행 중 프로세스는 이전 코드 유지, 다음 시도부터 적용. 실제 새 분기 E2E 미검증, 미커밋·미푸시.


### 2026-11-01 — SEC03 시험 재개 실행 인자 수정
SEC02 departure_recovery/attempt_001은 passed=true로 완료. 후속 sec03_to_sec16의 1~9차는 주행 이전 준비 실패: run_single_cycle.py의 probe_command에 자료 스냅샷용 probe_sorter_cycle.py 경로가 잘못 추가되어 NotADirectoryError 발생. 해당 인자만 제거. cycle_monitor.py는 중첩 캠페인 status도 조회하도록 수정. 출발/복귀25검사 및 모니터9검사 통과, 문법검사 통과. 감독 PID3199187 유지, 수정 후 attempt_010/SEC03 실행. 실물 코드/판정/허용값 변경 없음. 기존 실패 로그 보존, 미커밋·미푸시. 복원은 이 두 줄 변경만 되돌림.


### 2026-11-02 — Isaac·예찰 양쪽 headless 실제 확인
- 사용자 “둘다 headless로 설정하고 확인” 지시. c40a036+기존 미커밋 기준.
- sim/tools/run_single_cycle.py 예찰 launch 인자에 headless:=true 한 항목 추가. Isaac 기존 true 유지. 공통/실물 코드·검출 판정 불변. 복원은 해당 인자만 제거.
- 실제 worker --headless 및 Isaac headless:=true 확인. 출발 순서 회귀 19개 통과.
- sim/runs/headless_sec04_20261102_073346/attempt_001/scout_result.json: 2026-11-02 07:40:19 KST SEC04 status=4/SUCCESS, 5개 관측 완료, 수확 작업 7개, 예상 과실 12개. 기존 두 번째 관측 Broken pipe 재발 없음. GUI 의존 제거 효과 확인; 과거 worker 종료 직접 원인은 원본 로그 덮어쓰기로 확정 불가.
- 최초 실행은 출력 디렉터리 선생성으로 FileExistsError(시험 시작 전) 발생, 새 attempt_001 경로로 바로잡음. 해당 runner.log 보존.
- 단일 SEC04 전체 사이클 PID926642는 예찰 복귀 후 후속 수확 진행하도록 유지. 전체 사이클 성공 및 marker42 문제 해결은 아직 검증되지 않음. 무제한 재시도 캠페인은 중지 유지. 미커밋·미푸시.


### 2026-11-02 — SEC04 인계 전 정지 차체 밀림 진단·제동 보완
- 사용자 원인 해결·재시험 지시. c40a036+기존 미커밋 기준. headless SEC04 예찰/복귀 및 수확7작업 SUCCESS 뒤 prepare_arm 위치10.1743cm/허용5cm로 실패. 수확 집계8/12, 실제 저장 바구니10개는 별도 보존.
- 운송 접근 대기286.267시뮬초 동안 world 바구니중심12.6829cm/바퀴odom12.6542cm 이동. 명령/바퀴target0. 운송이 멀리 있을 때도 이동: 이번 문제를 추정 오차만으로 설명할 수 없음. 증거 headless_sec04_20261102_073346/attempt_001/idle_drift_diagnosis/evidence.json.
- 기존 wall/align 재보정은 prepare_arm의 WindowEntryReference 검사보다 뒤이므로 이번 위치 오류에는 실행되지 않음. 해당 검사/허용값은 변경하지 않음.
- 독립 CPU/headless 물리300초: baseline22.529mm, damping10배23.041mm, baseline재실행22.529mm. 감쇠 증가는 채택 안 함. 엔코더 위치 joint-drive 제동은 world10.280mm/odom0.064mm. 농장·과실 없는 축소시험이며 전체 해결 아님.
- sim farm_sim_devices/base_sim.py: 정지 시 측정 바퀴각을 latch하고 기존 damping과 수치가 같은 stiffness로 위치 유지(1초 복원 시간상수). 이동명령 시 원래 gain 복원. 차체 pose/GT 주입 없음. harvest.json만 wheel_position_hold=true, 다른 로봇/실물/공통코드 불변. 정지 및 이동 전환 단위검사 포함26개 PASS. 설치 base_sim.py 반영.
- 진단 도구 check_wheel_stop_diagnostic.py에 장시간 정지/위치유지 비교 추가. 설치본 실제 물리검사 후 완료 수확 상태 재사용 시험 예정. 복원: harvest.json wheel_position_hold=false로 비활성화, 이번 base_sim 변경만 되돌려 설치. 미커밋·미푸시.

- 후속 직접 실행: 설치 BaseSim 30초 물리 검사 정상종료, world0.727mm/odom0.058mm. 소스·설치 해시 일치 확인. sec04_idle_recovery_20261102/attempt_001 PID1146921로 수확 재사용 인계 재시험 시작, wheel_position_hold=true 실제 런타임 확인, 현재 마지막 window 도착 재검증 주행 중. 시험 최종 성공은 아직 미확인.

### 2026-11-02 인계 사전 준비 검사
- 사용자 반복 실패 원인 해결·재시험 지시에 따라 sim/tools/single_cycle_steps.py 및 probe_handoff_window.py에 인계 lifecycle ACTIVE·충돌 입력 신선도·장치 연결 검사를 출발 전/인계 직전에 추가. 일반 ready 후 장시간 이동하다 접수 거절되던 상황을 조기 검출. 공통/실물 영향 없음.
- attempt_001: 인계 controller configure 정체, costmap/footprint 입력 0건으로 접수 거절. 내부 configure 정체 원인 미확정.
- attempt_002: 제어기 ACTIVE 및 장치 정상이나 새 사전검사가 metadata.update_time=0을 오래된 지도라고 오판. header.stamp로 수정. 이 실패는 시험 도구 오류이며 차체 밀림 재발로 집계하지 않음.
- test_handoff_preflight.py: 실제 ROS 메시지의 metadata=0/새 header 허용, 오래된 지도 및 footprint 거절. 출발 순서/제동 검사 포함 24 PASS. 복원은 이번 검사 함수 및 두 호출 제거. 물리 안전 임계값 변경 없음.

### 2026-11-02 성공 후 전체시험 자동 재개
- 사용자 명시 지시로 runs/sec04_idle_recovery_20261102/continue_after_success.py 실행. attempt_003 종료/정리 및 인계·수확복귀·하역·선별·운송복귀 성공 확인 후 새 SEC04~16 전체시험을 순차 실행. 기존 run_single_cycle/complete 판정 재사용, 실패 시 맹목 반복 없음. 성공 gate 8가지 검사 통과. 실물/공통 코드 변경 없음. 중단은 STOP_CONTINUATION 파일로 다음 시험 시작 억제.
- 전체시험 전환 누락 점검: 실제 run_single_cycle --section SEC04 --prepare-only로 fresh_settings_audit 생성. harvest.json(정지 제동 포함), 운송 Nav2, 정밀 접근 프로필이 재개시험과 동일. handoff는 출력 경로만 다르며 참조 정책/수치 동일. BaseSim 소스·설치 해시 일치. 전체 섹션/출발 순서/제동/인계 준비 검사43 PASS. 두 headless 인자 및 공용 출발·복귀 gate 실행 분기 확인. 보고서 fresh_settings_audit/report.json. 실제 전체시험 통과와 구분.

### 2026-11-02 모니터 연속시험 추적 복구
- cycle_monitor.py가 status.json/current 및 얕은 attempt 경로만 탐색해 새 fresh_sec04_to_sec16/SEC04를 놓치고 종료된 attempt_003을 표시. continuation_status.json의 trial/source도 읽도록 최소 수정. 시험 제어 변경 없음.
- test_cycle_monitor.py에 재개→새 SEC04→SEC05 자동 추적 검사 추가, 10 PASS. --once 실제 화면에서 현재 W005, 4/7 완료, 로그 갱신0초 확인. 기존 모니터만 교체(PID1220360), 시험 PID1181205 유지. 복원은 이번 continuation 상태 탐색 변경 제거.

### 2026-11-02 벽 접근 범위 초과 보정
- 사용자에게 공통 인계 제어의 제한 보정 접근·재측정·시험 방안을 설명한 뒤 '조치해봐' 명시 승인. 기존 미커밋 수정 보존.
- robot/ros_ws/src/harvest_robot/harvest_robot/{handoff_planning,handoff_navigation,handoff_factory}.py: wall 직전 1회 제한 접근. 정상범위는 기존 처리, 최대 초과3cm/경로4.1cm, 기존 WindowCorrection 0.01m/s와 충돌·정지 검사 재사용. 관측 거리/법선 연속성 및 정지 후 재측정 실패 시 중단. 공통 실물 영향 있음, 실물 설정과 원래20cm 제한 불변.
- sim/tests/test_wall_bounded_approach.py 8개 + 기존 staged/restore navigation 총31 PASS. 해당 세 파일 설치본 반영·해시 일치. 실제 시뮬 검증은 후속 실행으로 별도 기록. 복원은 이번 plan_wall_approach와 선택 콜백 연결만 제거하여 재설치.
- 원인 근거: fresh SEC04 회전 후 벽0.64239m/목표0.4325m → 필요0.20989m > 한도0.2m. 성공 재개는0.61541m. 두 경우 정상 벽 관측을 받았지만 정확한 동일 물리면 여부는 로그만으로 확정하지 않음. 보정 중 재관측 연속성도 검사하여 오인식을 무조건 이동으로 처리하지 않음.
- 최초 재개 attempt_001은 보정 진입 전 초기 배치 방향 오류로 중단: 회전 후 장면을 위치만 이동해 수확 도착 방향과90도 차이. prepare_transport_resume.py에서 초기 배치 시 목표 방향으로 로봇·과실 중심·바구니 corners를 같은 강체변환으로 옮기도록 수정. 실행 중 GT 주입 없음. 실제 실패장면으로 생성검사: yaw/초기xy/12개 적재물의 로봇상대좌표 보존 PASS. 재개는 완전 checkpoint가 아니며 원본 과실 자세는 기존 자산 기준 유지.
- wall_approach_recovery_20261102/attempt_002 PID1266032 재실행, 성공 후 전체시험 연결 PID1266033. 소스 집계9개와 물리 바구니12개 별도 보존. 보정 실동작 및 전체 성공은 아직 대기.


## 공통코드 실패 요약 문서 작성 — 2026-11-02

- 사용자 Markdown 정리 요청에 따라 `COMMON_CODE_FAILURE_SUMMARY.md` 추가. 기준 main/c40a036 및 기존 미커밋 변경 보존.
- 기존 보고의 날짜를 본문 표에서 제외하고 실패 횟수·원인·조치·조치 후 재발 여부를 정리. 환경/설정 문제와 복구 누락을 구분하고 미확정 횟수·실제 분기 미검증을 명시.
- 문서 및 근거 링크 존재 확인. 신규 시험·운영/실물 동작 변경 없음. 이번 문서와 이 기록만 제거하면 복원 가능. 커밋·푸시 없음.


## 현재 작업 상태 커밋·푸시 — 2026-11-02

- 사용자 현재 상태 커밋·푸시 요청. main/c40a036 이후 공통코드·시뮬·검사·문서 변경을 함께 보존. 별도 저장소 Frontend는 변경 없어 제외. COMMON_CODE_FAILURE_SUMMARY.md를 저장하고 포함.
- Python 변경/신규 파일 53개 AST 문법 검사 통과. 선택 회귀검사 40PASS/8FAIL: PrecisionClient 모의 객체 node 누락 4건, 구 출발 순서 검사 cycle_departure_gate 모듈 import 실패 4건. 통합시험 성공 또는 전체 검사 통과로 보고하지 않음.
- 이번 작업은 현재 상태 저장이며 운영 코드 추가 수정·새 주행 시험 없음. 기존 기록과 미해결 항목 보존. 문서만 되돌릴 때 이번 절과 요약 문서만 제거.


## 2026-11-03 — 예찰부터 선별 실행 성공 기록 집계

사용자 전체 성공 횟수 확인 요청. SCOUT_TO_SORT_SUCCESS_AUDIT.md/json 작성. 선별 task_id 중복 제외 후 새 전체 실행4회, 예찰·수확 재사용 완료5회, 선별 액션 성공이나 전체 실패3회. 16행 표는 실측12행과 미확보4행으로 구분. 새 전체 성공은 기존 complete() 검사4건 통과, 원본 링크12개 존재 확인. 기록 부풀림/원본 결과/운영 코드 변경 없음.


## 2026-11-03 — 12개 원본 수량과 4개 명시적 합성 예시 JSON

사용자 요청으로 SCOUT_TO_SORT_16_RECORDS_WITH_SYNTHETIC.json 및 재생성 도구 sim/tools/build_scout_sort_dataset.py 추가. 원본12행 예찰 예측 합계, 실제 바구니 과실 경로 수, 선별 수 추출. 바구니 수와 선별 투입 수12건 일치 확인. 초기 베드 전체 수는9행36개, 스냅샷 없는5/6/10행은null. 13~16행은 필드별 평균 반올림±1 합성값이며 synthetic=true/overall_passed=null 명시. 원본 분류·실패·재사용 구분 유지. 16행/합성4행/출처 파일 존재 검사 통과. 운영 설정·실험 원본 변경 없음.


## 2026-11-03 — JSON SEC별 적황 과실 기준 수정·5번 선별 조사

사용자 요청으로 build_scout_sort_dataset.py 및 SCOUT_TO_SORT_16_RECORDS_WITH_SYNTHETIC.json schema2 갱신. actual_bed_fruit_count를 actual_sec_fruit_count로 교체: 원 초기 스냅샷의 Bed 중심 x 기준 해당 west/east 면 red/yellow만 계산, green 제외. 색별수/면/설정 출처 명시. 스냅샷 없는5/6/10행null 유지. 기존 예찰·바구니·선별12행 수치 불변, 합성4행의 SEC 평균만 재계산. 16행/색합계/기존 투입·선별 수 보존 검사 통과. 5번은 과실 몸체보다 높은 ROI 때문에 잔류9개를 NO_COLOR로 인식, 기존3초 완료 규칙으로 SUCCESS. 과거 저장영상 대조 및 Y+5px 후6번10/10 결과 문서를 JSON에 연결. 새 물리시험이나 운영 설정 변경 없음.


## 2026-11-03 — 파생 16행 JSON의 기존5번 제외

사용자 요청으로 기존5번(ROI 수정 전10/1)을 파생 JSON에서 제외하고 같은 행 번호를 synthetic=true 합성값으로 대체. 원본 및 SUCCESS_AUDIT 보존, excluded_records에 제외 출처·이유 기록. 실측11행/합성5행(5,13~16), 합성 평균은 기존5번 제외 후 재계산. 나머지 실측 수량 및 분류 유지. 재생성 도구 동기화. 16행 번호/분류/원본 선별 수/제외 원본 존재 검증 통과. 운영 변경 없음.
