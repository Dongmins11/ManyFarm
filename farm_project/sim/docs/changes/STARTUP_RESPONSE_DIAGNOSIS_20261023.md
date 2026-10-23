# 반복 시작 준비 실패: 응답 손실 경로 확인 (2026-10-23)

기준 HEAD0832b6f 및 미커밋 작업 상태. 사용자 반복 발생 지적에 따른 저장 로그/설치 헤더/동일 릴리스 공식 소스 확인. 운영 코드·설정 변경/새 시뮬 실행/커밋/푸시 없음.

## 확인한 사실

- 2차 SEC05 attempt1: scout bt_navigator Configuring1792660947.0858 →두 navigator 생성→1792660947.2649 `failed to send response ... /change_state ... client will not receive response`. lifecycle_manager는 Configuring bt_navigator1792660946.7672에서 전체 시험 제한까지 대기. ‘BT 내부 계산이300초 걸렸다’고 단정할 수 없고 응답 송신 실패가 직접 확인됐다.
- 같은 메시지가1차 SEC15 planner/change_state,1차SEC14 attempt2 velocity_smoother/get_state,10/20캠페인AMCL/change_state,최근no_wait 준비실패 map_server/change_state 및 harvest bt_navigator/change_state에도 존재. 단일 노드/팔 모델/특정SEC에 국한되지 않는다. 검색 결과 동명JSON에 보존. 경고가 있는 모든 실행이 최종 실패한 것으로 집계하지 않는다.
- rmw_fastrtps_shared_cpp 설치8.4.4,FastDDS2.14.6,Nav2 lifecycle1.3.12. 동일8.4.4 공식 rmw_response.cpp에서 정확한 문자열은 요청한 클라이언트의 응답 구독자를 제한시간 안에 매칭하지 못해 MAYBE를 반환할 때 RMW_RET_TIMEOUT으로 나온다. 응답 메시지는 실제 write에 도달하지 않는다. 주행계산/시뮬시간 타임아웃과 다른 계층이다.
- Nav2동일1.3.12 LifecycleServiceClient의 인자 없는change_state는 응답용invoke를 기한 없이 기다린다. 설치service_client.hpp의 해당overload도 spin_until_future_complete에timeout이 없다. 응답송신1회실패가300초전체준비실패로 커지는 경로가 있다.
- 2차SEC16 attempt2는 다른 형태: scout bt_navigator가Creating이후configure없고 manager는get_state검색147회. SHM port7000잠금오류가여러노드에동반되지만성공로그에도존재하므로근본원인동일/SHM단독원인확정불가. 실제정체스택/서비스discovery계측필요.

## 판단 및 미확정

반복 준비실패 중 일부는 ROS 서비스 응답의 DDS발견/매칭 실패와 무기한응답대기 결합으로 좁혔다. 모든 시작오류가 같은 원인이라는 주장은 하지 않는다. 왜 응답구독자 매칭이 늦는지(동시시작부하/중복참여자/전송/발견지연)는 추가 통제비교 필요. 기존10초bond_timeout은 이configure응답대기의상한이아니다.

후속은 운영값을 바로 바꾸기보다 동일 Domain13/SUBNET에서 초기화단계별 GetState·ChangeState응답/프로세스스택을 수집하고, 동시기동 대 분산기동 및 기본전송 대 UDP전용의시험전용비교다. UDP성능/관제연결검증없이전역적용/미들웨어교체/SHM일괄삭제는하지않는다. 재시도는 상태를 재조회하여 이미적용된전이를중복요청하지않도록해야한다. 공통launch변경은구체안제시후확인규칙적용. 현시점 해결완료아님.

공식 동일버전근거:
- https://raw.githubusercontent.com/ros2/rmw_fastrtps/8.4.4/rmw_fastrtps_shared_cpp/src/rmw_response.cpp (116~141)
- https://raw.githubusercontent.com/ros-navigation/navigation2/1.3.12/nav2_util/src/lifecycle_service_client.cpp (70~80)
- 로컬 /opt/ros/jazzy/include/nav2_util/nav2_util/service_client.hpp


## 추가 통제 재현: 발견 수신 버퍼 포화 경로 확인

사용자 “확인해봐 이유가있겠지”에 따라 운영 코드/설정을 바꾸지 않고 시험 도구만 작성했다. Domain13/SUBNET 유지. 원본 `sim/runs/startup_discovery_20261023`, 도구 reproduce.py/full_startup.py/network_monitor.py, 집계 controlled_summary.json. 모든 Nav2 프로세스는 설치된 실제 map_server/lifecycle_manager 바이너리다. 대체 업무 로직/가짜 서비스/GT 입력은 없다.

### 단계별 분리

1. 가벼운 구성: map_server+관리자2쌍 동시기동12묶음(24쌍) 전부 성공.
2. 운영 전체 CPU/headless Isaac+예찰+수확+태그 구성4회 정상 기동(17.64~18.65초), 이번4회에는 준비 실패가 재현되지 않았다. 즉 모든 일반 시작이 실패하는 결정적 오류는 아니다. 전체 기동 중 실제 Domain13의 DDS 발견용 소켓 드롭을 기록했다. 이를 포착하기 위한 시간 범위의 호스트 UDP 수신버퍼 드롭은 존재하지만 전부 실패와 일치하지 않는다.
3. Isaac/GPU/물리 없이16쌍 동시기동6묶음96쌍에서1쌍이 같은 응답 손실로 실패.32쌍 부하에서 빈도가 높아져 아래 인과 비교를 수행했다.

|32쌍 동시기동 ×6묶음|준비 실패 쌍 /192|응답 송신 실패 경고|관측 구간 호스트 UDP 수신버퍼 드롭|
|---|---:|---:|---:|
|기본 전송/기본 버퍼|20|20|204,247|
|기본 전송/수신 버퍼만 확대|0|0|0|
|UDPv4 전용/기본 버퍼|4|4|166,434|

위 수치는 부하 재현 시험이며 실제 운영의 실패율20/192를 의미하지 않는다. 실행 순서는 기본→버퍼→UDP, 무작위 교차 시험은 아니다. UDP 비교에서도 같은 오류가 발생해 SHM 경고만으로 설명할 수 없음이 확인됐다. 기본 전송은 UDP+SHM을 그대로 유지했다.

### 정확한 상태와 스택

- 기본32쌍 첫묶음 startup_probe_12는 지도읽기 완료 후 응답 송신에 실패. 별도 GetState 요청은 정상 응답하며 상태inactive(초기화 완료)를 반환했다. 관리자는 여전히 Configuring에 멈춰 있었다.
- 해당 manager의 GDB 스택 `burst32/00/stack44.log`에서 LifecycleServiceClient::change_state →ServiceClient::invoke→spin_until_future_complete 응답대기 확인. 서버 스택 `stack12.log` 및 independent_state.log 보존. 초기화 내부 계산의 교착으로 오인하면 안 된다.
- 처음16쌍 재현의 디버거 attach는 ptrace_scope 때문에 거부됐다. 이후 시험용 자식 프로세스에서 부모/부모의 디버거 자식만 ptrace할 수 있게 PR_SET_PTRACER를 지정해 위 스택을 수집했다. 시스템 ptrace 설정을 바꾸지 않았고, 모든 해당 시험 프로세스 종료. 최초 독립 상태 조회는0번정상노드를 조회한 것이어서 증거로 사용하지 않는다.32쌍부터 실제 실패노드를 조회했다.

### 버퍼 포화와 응답 누락 연결

기본 DDS 발견 소켓의 커널 수신 상한은212,992바이트(약208KiB)였고, 동시 참여자/서비스 발견 패킷이 몰릴 때 수신버퍼 드롭이 누적됐다. 실패 회차의 소켓별 drops와 실제 소유 PID/포트는각회 sockets.txt, 호스트 UDP 전후는 udp_before/after.txt에 있다. Domain13 기본 메타트래픽 멀티캐스트10650, 참여자 유니캐스트10660+2×ID 소켓을 구분했다. 전송 데이터 소켓/외부 소켓과 혼동하지 않는다.

시험 XML은 FastDDS 기본 participant의 `rtps.listenSocketBufferSize=2097152`만 지정했다. Linux에서 커널 계산상 수신 상한은4,194,304바이트로 확인됨(소켓 버퍼 계수2배). 호스트 rmem_max=4,194,304, 기본rmem_default=212,992는 읽기만 했으며 sysctl/전역 쉘/ROS 기동 설정 변경 없음. 동일한128개 관측 DDS 발견 소켓이기본212992→확대4194304로 바뀜을 socket_buffers.json에 기록했다. SHM·서비스QoS·Nav2 파라미터·주행/성공 판정·물리 세팅은 그대로였다.

동일 FastDDS8.4.4 경로는 요청 수신자와 응답 구독자의 발견/매칭을 별도로 처리한다. 서버가 요청을 받을 수 있어도 응답 구독자 매칭이 제한시간(이 재현 로그에서 지도읽기 완료→오류 약0.105초) 내 완성되지 않으면 `client will not receive response`를 내며 응답을 쓰지 않는다. 이후 발견이 회복돼 새 GetState가 성공해도 과거 ChangeState 응답을 다시 전송하지 않으며, Nav2 관리자의 기한 없는 응답대기로 정체가 남는다.

따라서 이번에 직접 재현한 ‘configure 응답누락’ 유형은 **동시 기동의 발견 패킷 집중 + 작은 UDP 수신 버퍼 + 짧은 응답 상대 매칭 대기 + Nav2 무기한 응답 대기**가 결합한 경로로 확인했다. 물리 계산/팔 모델/베드 좌표가 없어도 발생한다. 일반 기동에서의 최초 촉발 요인을 매회 단정할 수는 없지만, 동일 오류와 정체 상태를 재현하고 버퍼만 바꾸어 제거한 증거다.

### 실제 전체 구성에 후보 적용

시험 프로세스 환경에만 FASTRTPS_DEFAULT_PROFILES_FILE을 전달해 CPU/headless 전체 구성2회 기동. 두 로봇 Nav2 모두18.079/18.681초 내active, 응답송신경고 없음. baseline4회도성공했으므로 일반기동실패율개선의 통계입증은 아니다. 주행/수확 Action은 보내지 않았으며 카메라·주행 처리량 비교나 실물 검증을 했다고 주장하지 않는다. 기존 운영 launch나 실물 설정에는 아직 적용하지 않았다.

### 조치 범위와 남은 과제

권장 첫 조치는 시뮬 기동 범위에만 DDS 수신 버퍼 프로파일을 연결해 발견 패킷 손실을 줄이는 것. SHM 전체 비활성/전역sysctl 변경/300초 증가를 우선안으로 삼지 않는다. 응답 대기에도 상한·상태 재조회 기반 복구가 필요하지만 공통 Nav2 lifecycle 처리 변경은 별도 설계/확인 대상이다. 이미inactive인데configure를 무조건 재요청하는 방식은 사용하지 않는다.

SEC16의 ‘Creating 이후 get_state 서비스가 발견되지 않음’ 유형은이번에동일스택을확보한사례가아니므로모든기존준비실패의근본원인확정/완전해결로확대하지않는다. 후보설정으로장기기동을검증하면서해당형태재발시스택/발견상태를수집해야한다. 이번 작업은원인분리와시험설정검증,운영수정/커밋/푸시없음.
