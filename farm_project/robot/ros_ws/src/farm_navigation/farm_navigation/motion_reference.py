"""동일 odom 발행 세션 식별. 좌표 변환·이동은 수행하지 않는다."""
import hashlib
import json

def session_identity(boot_id, publishers):
    """같은 호스트 부팅과 odom 발행자 인스턴스만 허용한다."""
    if len(publishers) != 1:
        raise RuntimeError('odom 발행자가 하나여야 합니다.')
    endpoint = publishers[0]
    gid = bytes(endpoint.endpoint_gid).hex()
    if not boot_id.strip() or not gid or set(gid) == {'0'}:
        raise RuntimeError('odom 세션 식별 불가')
    value = [boot_id.strip(), endpoint.node_namespace, endpoint.node_name, gid]
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()

