"""실제/가상 카메라의 AprilTag 검출 설정과 메시지 정규화."""
import math


def detector_parameters(tag_sizes: dict[int, float], *, use_sim_time: bool,
                        frame_prefix: str = 'tag_', overrides: dict | None = None) -> dict:
    """태그 배치·시계만 입력받고 같은 검출기 기본값을 사용한다."""
    from farm_navigation.configuration import merge_mappings
    ids = sorted(tag_sizes)
    if not ids or any(not math.isfinite(tag_sizes[i]) or tag_sizes[i] <= 0 for i in ids):
        raise ValueError('유한한 양의 태그 크기가 필요합니다.')
    parameters = {
        'use_sim_time': use_sim_time, 'image_transport': 'raw', 'qos_profile': 'sensor_data',
        'family': '36h11', 'size': float(tag_sizes[ids[0]]), 'tag.ids': ids,
        'tag.frames': [frame_prefix + str(i) for i in ids],
        'tag.sizes': [float(tag_sizes[i]) for i in ids], 'max_hamming': 0,
        'pose_estimation_method': 'pnp', 'detector.threads': 2, 'detector.decimate': 2.0}
    return merge_mappings(parameters, overrides or {})


def detector_parameters_from_assets(assets: dict, *, use_sim_time: bool,
                                   frame_prefix: str = 'tag_', overrides: dict | None = None) -> dict:
    """ROS·USB 입력 모두 같은 등록 태그 ID/크기와 검출 설정을 사용한다."""
    ids = sorted({tag['tag_id'] for tag in assets['tags']})
    sizes = {tag_id: {tag['edge_m'] for tag in assets['tags'] if tag['tag_id'] == tag_id}
             for tag_id in ids}
    if not ids or any(len(values) != 1 for values in sizes.values()):
        raise ValueError('태그가 필요하며 반복 ID의 검출 크기는 모든 구역에서 같아야 합니다.')
    if {tag['family'] for tag in assets['tags']} != {'tag36h11'}:
        raise ValueError('검증된 tag36h11 검출기만 지원합니다.')
    return detector_parameters({i: float(next(iter(sizes[i]))) for i in ids},
                               use_sim_time=use_sim_time, frame_prefix=frame_prefix, overrides=overrides)


def detection_payload(detection: object) -> dict:
    """ROS 검출 코너·품질을 원본 시각 Journal이 공유하는 형식으로 바꾼다."""
    corners = [[float(p.x), float(p.y)] for p in detection.corners]
    margin = float(detection.decision_margin)
    if (len(corners) != 4 or not all(math.isfinite(v) for p in corners for v in p)
            or not math.isfinite(margin)):
        raise ValueError('invalid_detector_quality')
    if type(detection.id) is not int or not isinstance(detection.family, str):
        raise ValueError('unsupported_apriltag_message')
    family = detection.family if detection.family.startswith('tag') else 'tag' + detection.family
    return dict(family=family, id=detection.id, hamming=int(detection.hamming),
                decision_margin=margin, corners_rectified=corners)
