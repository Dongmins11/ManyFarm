// =====================================================================
//  oc_tb3_actuator.ino  —  TB3 순정 주행 펌웨어(Waffle) + 바구니 액추에이터 (OpenCR 1.0)
//
//  - 주행: TurtleBot3Core (순정과 동일, USB = turtlebot3_node 전용)
//  - 액추에이터 명령: Serial1 (D0 RX / D1 TX) ← 라즈베리파이 UART (U1/U2), 115200
//    명령어는 oc_actuator_test 와 동일 (help, ping, lid ..., gate ..., tilt ..., set ..., status, dump)
//    회신: 접수 'OK ...' / 완료 'DONE <lid|gate|tilt> <동작>' / 중단 'STOPPED <이름>' / 오류 'ERR ...'
// =====================================================================
#include <TurtleBot3_ROS2.h>
#include "actuator.h"

void setup()
{
  TurtleBot3Core::begin("Waffle");   // 순정과 동일
  Serial1.begin(115200);             // 액추에이터 명령 채널 (UART)
  act_begin();                       // 서보 펄스 0 → 부팅해도 안 움직임
  Serial1.println("READY");          // 부팅 완료 알림 (라즈베리파이 브리지 노드가 확인)
}

void loop()
{
  TurtleBot3Core::run();             // 순정 주행 처리
  act_poll(Serial1);                 // UART 명령 받기
  act_update();                      // 서보·액추에이터 상태머신 (delay 없음)
}
