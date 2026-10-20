# 초기 위치 없는 정지 수집 수정 — 2026-10-20

원인: 수집기의 footprint 필수 조건과 매 프레임 map TF 최대3초 대기가 초기 위치 없는
런치 재시작 상황과 맞지 않았다. 기존14개 시험은 벽 계산이며 이 실행 경로를 검증하지 않았다.
사용자 수정·검증 승인에 따라 수집기만 수정한다. 기존 정상 주행과 후진 곡선 파일은 변경하지 않는다.

필수: scan, 해당 시각 센서→base TF 및 odom→base TF, 신선한 odom, 기존 MotionMonitor 정지 확인.
선택: map TF와 costmap published footprint. 별도 공통 PoseProvider에20ms 조회 제한을 설정해
선택 입력의 부재로 매 프레임3초씩 기다리지 않는다. OS 스케줄링에 따른 실제 시간 초과는 가능하다.
미수신/오래된 footprint/TF 실패는 누락 이유와 프레임 수에 기록한다. 외곽 형상이나 간격을 추측하지 않는다.
map 초기 위치를 발행하거나 Nav2 lifecycle/파라미터를 수정하지 않는다. 주행 준비 완료는 아니다.
기록을 이상적인 목표 자세로 자동 승인하지 않는다. KeyboardInterrupt에도 결과·부분 스캔 보존.

검증: 배포 수집기 main() 자체에 모의 ROS Node/TF/odom/scan을 주입해16개 시나리오,
5개 unittest method 통과. map+footprint 없음/개별 없음/오래됨/잘못된 형상/footprint TF 없음,
정상 입력, scan/odom 만료, scan 없음, 센서 TF 없음, 중복 시각, 시작/도중 이동, 사용자 중단.
중단 시 이미 기록한 프레임 보존도 검사했다. 기존 벽 분석14개 및 구문·속도/Goal 미발행 정적검사 통과.
모의 시험은 실제 DDS, TF 버퍼 시간 동작, ROS 실행, Nav2 bringup 검증을 대체하지 않는다.
ROS 미설치 환경이므로 실제 수집은 로봇에서 별도 확인해야 한다.

배포 전 PC·로봇 기존 수집기의 SHA를 이전 전달본과 비교하고 원본을 PC에 백업한다.
수집기 한 파일만 교체한다. 공통 MotionMonitor/PoseProvider는 설치본 그대로 재사용, 재빌드 없음.
원격 Git/커밋 없음. PC 변경은 사용자 VS Code에서 커밋. 롤백은 PC에 보관한 수집기 원본으로 가능하나
구버전은 초기 위치 없는 측정에 적합하지 않다.

추가 연결 확인: 실제 런치의 /harvest_01/tf 및 /harvest_01/tf_static으로 수집기 TF를 remap한다.
기존 수집기에는 이 remap이 빠져 있었다. CLI --tf-topic/--tf-static-topic으로 환경별 지정 가능.
모의 main 시험에서 두 remap 전달도 확인했다. 실제 ROS TF 연결은 현장에서 확인한다.
