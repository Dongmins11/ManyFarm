"""펌웨어 미연결 기본값. 가상 하역/수량을 실제 결과로 반환하지 않는다."""
class UnavailableDevice:
    def available(self) -> bool: return False
    def run(self, request, operation, check):
        raise RuntimeError('기구 브릿지 미연결: '+operation)
    def stop(self) -> None: pass
