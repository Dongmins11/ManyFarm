# 전체 시뮬 기동 DDS 수신 버퍼 기본 적용 (2026-10-23)

승인: 사용자 “그래 좋아 잘했어 수정해”. 기준 HEAD0832b6f 및 기존 미커밋 변경 보존. 조사 근거 STARTUP_RESPONSE_DIAGNOSIS_20261023.md의 재현 결과를 시뮬 전체 진입점에 연결했다.

## 최소 변경

- `sim/ros_ws/src/farm_sim_config/config/fastdds_discovery.xml`: 시험에서 검증한 participant listenSocketBufferSize=2097152바이트. 프로파일 이름만 시험용에서운영용으로 변경. 전송·서비스QoS 기본 유지. 기존setup.py의config glob으로패키징되므로setup수정없음.
- `sim/ros_ws/src/farm_sim_runtime/launch/all.launch.py`: 외부DDS프로파일이없을때기본파일을선택하고FASTRTPS_DEFAULT_PROFILES_FILE을설정한뒤기존모든포함launch실행. scoped GroupAction으로호출자의launch환경복원. ROS_DOMAIN_ID/발견범위는바꾸지않음.
- 외부FASTRTPS_DEFAULT_PROFILES_FILE/FASTDDS_DEFAULT_PROFILES_FILE은보존하고기본버퍼미적용로그표시. 파일누락은기동전명확한오류. 개별scout/harvest/isaac launch직접기동에는기본프로파일을추가하지않았다. 현재캠페인이사용하는all.launch.py가적용진입점이다.
- `sim/tests/test_dds_launch_profile.py`4개: 자식환경전달/호출자복원, 외부프로파일두종보존,파일누락,버퍼이외설정불변. 기존test_tag_capture_launch.py의2개전체조립시험은환경을제공하는시험컨텍스트와GroupAction내부include검사로조정. 로봇별태그스위치/물리인자전달검사는유지.
- 실물/공통코드·sysctl·전역쉘환경·준비제한300초·기동순서·미들웨어종류·Nav2성공판정변경없음. 새의존성없음.

## 검증

신규4개+기존태그launch5개+fleet진입점2개=11개PASS. 최초시험은ROS_LOG_DIR가쓰기금지기본.ros/log를가리켜실패했고/tmp시험로그경로로재실행. 기존전체조립mock2개는GroupAction변경에맞게갱신후통과. 운영실패로집계하지않음.

실제CPU/headless전체스택을일반명령으로2회기동했다. 실행전외부DDS프로파일환경변수없음,새all.launch.py가기본프로파일선택로그를출력했다. Domain13/SUBNET, 양로봇Nav2active각18.690/18.080초, lifecycle응답송신실패경고0. 첫회차관측DDS발견소켓64개모두수신상한4,194,304바이트. 별도시험환경변수주입이아닌운영진입점자동적용을확인했다.

원본 `sim/runs/startup_discovery_20261023/full_integrated/00`, `01`: contract.json,observation.json,sockets.txt,stack.log,artifacts. 전체결과summary.json. 주행/예찰/수확Goal을보내지않았으므로장기기동/주행성능/수확성공률검증과구분한다. 기존조사의192쌍부하결과는이번운영연결후재실행한결과가아니다.

## 남은 범위와 복원

이조치는발견수신버퍼유실경로에대한수정이며모든시작오류/Creating정체를완전해결했다고선언하지않는다. 외부프로파일이있으면자동기본값을덮어쓰지않으므로로그와외부버퍼설정확인필요. Nav2의무기한응답대기/상태재조회복구는미변경.

복원은all.launch.py의프로파일설정/scoped환경부분을이전버전으로되돌리면된다.XML만삭제하면파일누락오류가나므로참조와함께복원한다. 문서갱신,미커밋/미푸시. 검증후실행프로세스종료.
