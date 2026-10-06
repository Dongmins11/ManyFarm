# 로봇 Base의 합의된 기준점 위치. 주행 목표/상태에 쓰는 프로젝트 공통 형식.
string frame_id
geometry_msgs/Point position

# position: m, yaw: rad. yaw는 frame_id 좌표계의 +Z 축 기준.
float64 yaw
