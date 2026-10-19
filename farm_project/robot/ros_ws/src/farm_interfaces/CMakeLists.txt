cmake_minimum_required(VERSION 3.8)
project(farm_interfaces)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(action_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/RobotPose.msg"
  "msg/RobotStatus.msg"
  "msg/HarvestTask.msg"
  "action/ScoutArea.action"
  "action/HarvestTask.action"
  "action/ReturnToStation.action"
  "action/DockTransfer.action"
  "action/Discharge.action"
  "srv/TransferEvent.srv"
  "srv/GetHarvestTasks.srv"
  DEPENDENCIES geometry_msgs action_msgs
)

ament_export_dependencies(rosidl_default_runtime)

install(DIRECTORY examples DESTINATION share/${PROJECT_NAME})
install(FILES VALIDATION.md DESTINATION share/${PROJECT_NAME})

ament_package()
