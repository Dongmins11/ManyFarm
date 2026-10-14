<!-- HARVEST_VERIFIED_BASELINE_20261011 -->
## 수확 실물 성공 상태 고정 — 2026-10-11 17:51 KST

- 사용자 확인: 중간 위치에서 회전 없이 목표로 이동했고 관제 웹에 작업 완료가 표시됨. 단일 요청 성공이며 반복 신뢰성, 태그 보정 정확도, 실제 수확 동작까지 검증한 것은 아님.
- 사용자 지시: 현재 성공한 코드·설정을 반드시 유지. 이후 코드·설정·실행 옵션 변경은 이유와 범위를 설명하고 사용자 확인 후 적용. 조회·로그 분석부터 진행.
- 통신 ROS_DOMAIN_ID=77 / rmw_fastrtps_cpp, 태그 카메라 별도 환경 유지. navigation.tf_recovery_enabled=false (timeout_s=10.0 값은 남아 있으나 비활성). 이전 문서의 TF 복구 ON 설명보다 이 상태가 최신.
- SEC_01 work_corridor_nodes=[10,14]. 구간 내 위치·방향 및 전방 목표 조건을 만족하면 SECTION_RESUME로 진입점 복귀를 건너뛰고 현재 위치에서 작업 목표로 이동. 구간 밖 기존 진입 및 충돌 감지 유지.
- 중간 출발 관련 4개 파일은 성공 후 로봇에서 받은 harvest_working_20261011.tar.gz와 전달 v2의 SHA256이 일치함. PC의 미커밋 관제 호환·상태 발행·TF 복구 소스 및 기존 테스트는 보존.
- launch 중복 방지와 제한 시간 진단 도구를 로봇 적용본으로 보존. Wi-Fi/DDS 정체와 TF 끊김의 재발 방지는 해결 완료로 판정하지 않음.
- Git: Robot3FinalProject/main, feat/apriltag-localization, 사용자 출력 HEAD 25cdf88 + 미커밋 변경 기준. PC 경로 /home/eunbi/vmany/main/farm_project. 로봇 /home/vic/vmany/main/farm_project는 Git 미연결. PC VS Code에서 기존 Fix: 형식으로 커밋·push 예정; 이 문서 생성 시점 원격 반영 미완료.
- 승인 범위: 성공한 로봇 소스·설정을 PC에 백업하고 Git에 보존. PC 문서는 최신 이력을 보존하며 로봇의 오래된 문서로 덮어쓰지 않음. 로봇 실행·설정 변경 없음. 시뮬 신규 변경 없음; 앞선 Action 규격 변경의 다중 구역 영향은 기존 호환 문서 참조.
- 패키지 적용 전 PC 파일 해시 확인 및 저장소 밖 백업. PC 재빌드 불필요. 복원은 적용 시 표시된 backup의 restore_manifest.json과 원본 파일을 기준으로 해당 파일만 복원. Git pull/reset 및 로봇 재배포는 이번 백업 작업에 포함하지 않음.
