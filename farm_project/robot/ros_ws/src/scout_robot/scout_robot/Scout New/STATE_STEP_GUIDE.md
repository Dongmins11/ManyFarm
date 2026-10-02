# State 실행 방식

```text
enter → 실제 행동 요청 → 반환
완료 → Controller 큐 → 현재 State인지 검사 → State 완료 함수
전환 요청 → Controller → 이전 exit → 다음 enter
```

StateController가 현재 상태를 소유합니다. Mission은 목표·진행 데이터와 결과를 관리합니다.
정상 exit는 상태의 콜백 수명을 끝내며, 매번 주행을 취소하지 않습니다.
취소·오류는 Controller가 진행을 차단하고 실제 동작 종료와 자원 정리를 확인한 다음 결과를 반환합니다.

[단계별 행동·AnyState·늦은 응답 처리 상세](scout_new/STATE_ARCHITECTURE.md)
