"""관측 결과 처리 방식 선택. 런치·ROS 파라미터가 아닌 코드에서 변경합니다."""
from enum import Enum


class SurveyPolicy(Enum):
    # 기존 방식: 누적 중앙값으로 좌표 갱신, 고정 윈도우의 소속 재검사.
    MEDIAN_REVALIDATE = 'median_revalidate'
    # 비교 방식: 최초 좌표와 기존 소속 유지. 새 과실 등록·추가는 계속 수행.
    FIRST_POSITION_KEEP_MEMBERSHIP = 'first_position_keep_membership'


# 이 한 줄을 바꾼 뒤 프로세스를 재시작하세요. sim/real 모두 동일하게 적용됩니다.
# 한 Survey가 진행되는 도중 정책이 바뀌지 않도록 생성 시 선택값을 저장합니다.
ACTIVE_SURVEY_POLICY = SurveyPolicy.MEDIAN_REVALIDATE
