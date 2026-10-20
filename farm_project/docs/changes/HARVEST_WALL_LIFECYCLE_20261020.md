# 벽 시험 콜백 종료 순서 보완 — 2026-10-20

## 증거와 한계
- 로봇 plan은 통과했지만 프로세스 종료 시 `cannot use Destroyable because destruction was requested`가 2회 출력됐다.
- 기존 `ros_cleanup_complete`는 종료 함수 반환 여부만 반영했다. 프로세스 끝에서 출력되는 미회수 Future 예외까지 검증하지 못했다.
- 기존 코드는 MultiThreadedExecutor.spin과 shutdown을 서로 다른 스레드에서 실행했다. 실제 예외가 발생한 엔티티/콜백은 현재 출력만으로 특정할 수 없다.

## 수정 범위
- wall_shutdown.py: ManagedSpin에서 단일 실행기의 spin_once를 관리한다. 정지 요청과 wake → spin 스레드 join → executor.shutdown → 클라이언트/노드 제거 순서다.
- 실행 중 콜백 예외는 저장하고 check 및 종료 결과에 실패로 전달한다. 스레드/실행기 종료가 확인되지 않으면 객체를 제거하지 않는다.
- wall_trial_runtime.py와 wall_observer_node.py: 이 관리 실행기를 사용하고 실행기 실패를 확인한다.
- 두 프로세스의 콜백은 수신·전달 작업이며, 벽 계산 및 TF 조회는 관측기 주 흐름, Action/서비스 대기는 감독 주 흐름에 있다. 별도 콜백 풀 없이 동작할 수 있도록 구성한다.
- 공통 Nav2Client, MotionMonitor, PoseProvider 구현·모터·곡선·주행·벽 제어 설정은 수정하지 않는다.

## 검증
- 로컬 단위 검사 8개: 진행 중 콜백 종료 순서, 미종료 시 제거 차단, 콜백 예외 실패 보고, shutdown 실패, closer 실패, 관리되지 않는 스레드 차단, 40회 반복 종료, 적용 범위.
- 패키지 smoke_ros.py: 격리 namespace에서 odom/scan 구독, 서비스, 모의 FollowPath Goal/Feedback/Result, 계속 발행 중 클라이언트 종료를 8회 수행한다. 모터 토픽이나 실물 Action에 연결하지 않는다.
- strict_run.py: 자식 프로세스가 완전히 종료된 후 반환 코드와 stderr의 미회수 예외/Destroyable/Traceback/abort를 확인한다. 종료 경고를 무시해 PASS로 처리하지 않는다.
- 작성 환경에는 ROS가 없으므로 실제 ROS 검사 완료를 주장하지 않는다. PC에서 먼저 통과해야 로봇 배포하며, 로봇에서도 같은 검사 및 무이동 plan을 검사한다.
- 실물 정렬 성능 및 실행 중 입력 시각 영향은 별도 검증 대상이다.
