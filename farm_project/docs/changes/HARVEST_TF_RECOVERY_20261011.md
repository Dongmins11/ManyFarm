

<!-- HARVEST_TF_RECOVERY_20261011 -->
## 수확 TF 오류 복구 대기 — 2026-10-11

- 승인: 사용자가 TF 장애 시 정지 상태로 최대 10초 대기·회복 후 재개에 “그렇게 해보자”라고 승인.
- 기준: harvest_receiver_compat 적용 소스 복사본. 로봇 13:02 주행 로그에서 SECTION_APPROACH TF_ERROR 확인. 현재 PC Git HEAD/미커밋 변경은 직접 조회하지 않았으며 배포 시 기존 파일 SHA256을 검사한다.
- 공통 farm_navigation의 nav2_client/navigator/pose_provider/navigation_types 및 새 tf_recovery.py, 수확 실물 harvest_real.yaml 수정.
- 기본 복구 OFF. 수확 실물 설정만 ON/10초. 예찰·시뮬은 기존 정책 유지. Action 형식·카메라·태그 검출·보정·경로 좌표는 유지.
- Nav2 FollowPath가 ABORTED + TF_ERROR로 종료 응답을 준 경우만 재시도. 미확정/취소/장애물/진행 실패는 자동 재시도하지 않는다. error_code도 실패 로그에 남긴다.
- 자신의 Nav2 Goal 종료 확인 후 cmd_vel_nav와 cmd_vel에 0을 반복 발행. 최신 0.1초 전 map→base TF 연결과 최신 odom의 정지를 확인하면 같은 경로를 재전송한다. 기존 goal_timeout_s도 전체 재시도에 적용한다.
- TF 오류 응답 이후 연속 복구 구간 최대 10초. 실제 제어 Feedback이 다시 발생한 뒤 새 TF 오류가 발생하면 새로운 구간으로 본다. Feedback 없는 반복 실패는 제한을 초기화하지 않는다.
- 외부 HarvestTask는 계속 실행 중이며 성공을 조작하지 않는다. 기다리는 중에도 취소·종료 검사. TF_RECOVERY_WAIT/RESUME/TIMEOUT을 rosout에 기록한다.
- 직접 검증: verify.py 7개 오프라인 검사 통과 (2.4초 회복, 10초 만료, 취소, 반복 TF 실패 제한, 다른 오류 즉시 실패, 설정 검증, 운영 Nav2Client TF 분류·동일 경로 재전송). ROS I/O는 대역. compileall 통과.
- 전체 기존 통합 시험은 복사본에 지도 YAML 등 런타임 자산이 없어 실행 완료하지 못했다. 실제 로봇 colcon·주행·정지 응답 시간은 미검증. 지연 원인 자체를 해결하는 변경은 아니다.
- 반영: 전달 패키지만 생성. commit/push·로봇 배포·빌드 미실행. 적용 도구가 문서에 이 내용을 추가한다.
- 되돌리기: 실물 환경 navigation.tf_recovery_enabled를 false로 설정 후 launch 재시작. 완전 복원은 PC vmany_backups의 적용·배포 백업을 사용한다.
