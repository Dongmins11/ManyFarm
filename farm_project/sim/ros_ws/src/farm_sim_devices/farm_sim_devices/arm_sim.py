"""arm 시뮬레이션 장치 구현 위치.

Isaac Sim 단일 프로세스 안에서 runtime이 이 모듈을 불러옵니다.
이 파일을 별도 ROS 노드로 실행하거나 Isaac Sim을 추가로 실행하지 않습니다.
현재 장면의 prim/joint 및 Isaac Sim API를 확인한 뒤 구현합니다.
"""


def create_device(*args, **kwargs):
    raise NotImplementedError('arm 시뮬레이션 연결은 아직 구현되지 않았습니다.')
