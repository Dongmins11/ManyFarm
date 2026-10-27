// =====================================================================
//  actuator.h  —  운송로봇(transport_01) 바구니 액추에이터 모듈 (OpenCR 1.0)
//
//  - 서보① 윗덮개(D5) : 슬라이드 덮개. 끼임 방지용 "3보 전진 1보 후퇴" 끊어치기(JOG)
//  - 서보② 앞문  (D6) : 기본 등속 이동(SMOOTH), 필요하면 JOG로 전환 가능
//  - 틸트 리니어 액추에이터 12V 100mm (D7 IN1 / D8 IN2 / D9 ENA PWM) : 소프트 시작/정지, 시간 기반, 기본 잠금
//
//  * delay() 없이 millis() 기반 → 나중에 TB3 펌웨어 loop()에 act_update()만 넣으면 됨
//  * 명령은 텍스트 한 줄 (act_poll 로 아무 Stream 에서나 받음: 지금은 USB, 나중엔 Serial1)
// =====================================================================
#pragma once
#include <Arduino.h>

// ---------- 핀 (배선도 v2) ----------
#define ACT_PIN_LID    5   // 서보① 윗덮개  (TIM1_CH1)
#define ACT_PIN_GATE   6   // 서보② 앞문    (TIM2_CH3)
#define ACT_PIN_IN1    7   // L298N IN1
#define ACT_PIN_IN2    8   // L298N IN2
#define ACT_PIN_ENA    9   // L298N ENA     (TIM9_CH2, PWM)

#define ACT_SERVO_HZ      50     // 서보 주기 20 ms
#define ACT_TILT_PWM_HZ   1000   // L298N PWM 주파수 (OpenCR 기본 50 kHz 는 L298N 에 너무 높음)

enum ServoMode : uint8_t { MODE_SMOOTH = 0, MODE_JOG = 1 };

// ---------- 서보 설정값 (명령 'set' 으로 실시간 변경) ----------
//  각도 기준 = "닫힘 기준 각도"  :  0 = 완전히 닫힘,  + 방향 = 열림
//  서보 실제 각도(raw, 0~180) = zero_deg + dir × 기준각도
struct ServoCfg {
  int      us_min;     // 서보 raw 0도 일 때 펄스 [us]
  int      us_max;     // 서보 raw 180도 일 때 펄스 [us]
  float    lim_lo;     // 소프트 리미트 하한 [닫힘 기준 deg]
  float    lim_hi;     // 소프트 리미트 상한 [닫힘 기준 deg]
  float    close_deg;  // 닫힘 각도 (보통 0)
  float    open_deg;   // 열림 각도 (닫힘에서 몇 도)
  uint8_t  mode;       // MODE_SMOOTH / MODE_JOG
  float    speed_dps;  // SMOOTH 이동 속도 [deg/s]
  float    unit_deg;   // JOG 1칸 [deg]
  uint8_t  fwd;        // JOG 전진 칸 수
  uint8_t  back;       // JOG 후퇴 칸 수
  uint16_t dwell_ms;   // JOG 동작 사이 쉬는 시간 [ms]
  float    zero_deg;   // 닫힘일 때 서보 raw 각도 ('zero' 명령으로 저장)
  int8_t   dir;        // 열리는 방향: raw 각도가 커질 때 열리면 +1, 작아질 때 열리면 -1
  uint16_t sfwd_ms;    // 360° 서보 끊어치기: 전진 시간 [ms]
  uint16_t sback_ms;   // 360° 서보 끊어치기: 후진 시간 [ms] (0 이면 끊지 않고 연속)
  int16_t  sopen_us;   // 360° 서보 open/close: 열기 방향 펄스 오프셋 [us] (닫기는 부호 반대). 0 = 일반 각도 서보
  uint16_t stime_ms;   // 360° 서보 open/close: 순수 전진 시간 [ms]
};

class ServoAxis {
public:
  ServoAxis(const char* name, uint8_t pin, const ServoCfg& def);
  void begin();                // PWM 준비만 (펄스 0 = 서보 안 움직임)
  void home(float deg);        // "지금 위치는 (닫힘 기준) deg" 선언 → 그 각도로 펄스 출력 시작
  bool moveTo(float deg);      // 닫힘 기준 각도로 이동. false = home 전
  void homeRaw(float raw);     // 교정용: 서보 raw 각도로 home
  bool moveRaw(float raw);     // 교정용: 서보 raw 각도로 이동 (소프트 리미트 무시, 0~180 만 제한)
  bool zeroHere();             // 지금 위치를 닫힘(0)으로 저장
  void spin(int offset_us, uint32_t ms);  // 360° 서보: 1500us±offset, 순수 전진 ms 만큼 (sfwd 전진 / sback 후진 반복), 끝나면 펄스 끊고 정지
  float toRaw(float deg) const   { return cfg.zero_deg + cfg.dir * deg; }
  float fromRaw(float raw) const { return (raw - cfg.zero_deg) * cfg.dir; }
  void stop();                 // 그 자리에서 멈춤 (힘은 유지). 동작 중이었으면 'STOPPED <name>'
  void release();              // 펄스 끊기 (힘 빠짐). 내부용 (회신 없음)
  void abort();                // 사용자 release: 동작 중이었으면 'STOPPED <name>' 후 펄스 끊기
  void setAction(const char* a) { act_ = a; }   // 완료 회신에 쓸 동작 이름 (open/close/spin/move)
  void update(uint32_t now);
  bool busy() const    { return st_ != ST_IDLE || spinning_; }
  bool homed() const   { return homed_; }
  float pos() const    { return cur_; }
  float target() const { return target_; }
  const char* name() const { return name_; }
  void printStatus(Print& out) const;
  void printCfg(Print& out) const;
  ServoCfg cfg;
private:
  void writeDeg(float deg);
  void planNext();
  bool startMove(float goal);
  const char* name_;
  uint8_t pin_;
  bool homed_ = false, released_ = true;
  enum { ST_IDLE, ST_MOVE, ST_DWELL } st_ = ST_IDLE;
  float cur_ = 0, wp_ = 0, target_ = 0, start_ = 0;
  bool next_back_ = false;
  bool spinning_ = false;
  bool spin_back_ = false;     // 지금 후진 구간인지
  int  spin_off_ = 0;          // 전진 방향 펄스 오프셋 [us]
  int32_t spin_left_ = 0;      // 남은 순수 전진 시간 [ms]
  uint32_t spin_end_ = 0;      // 현재 구간 끝 시각
  uint32_t spin_t0_ = 0;       // 시작 시각 (안전 상한용)
  void spinPhase(uint32_t now, bool back);
  uint32_t t_last_ = 0, dwell_end_ = 0;
  const char* act_ = "move";
};

class TiltMotor {
public:
  void begin();
  // dir: +1 = 올림(IN1 H, IN2 L) / -1 = 내림. 실제 방향은 M1/M2 극성에 따라 다름 → 시험 후 결정
  const char* run(int dir, uint8_t duty_pct, uint32_t run_ms);  // nullptr = OK, 아니면 오류 메시지
  const char* dump();  // 쏟기: up dump_up_ms → dump_wait_ms 정지 → down dump_down_ms
  void stop();     // 램프 다운 후 정지. 동작 중이었으면 'STOPPED tilt'
  void estop();    // 즉시 정지 (IN1=IN2=LOW, ENA=0). 동작 중이었으면 'STOPPED tilt'
  void setAction(const char* a) { act_ = a; }   // 완료 회신에 쓸 동작 이름 (up/down/dump)
  void update(uint32_t now);
  bool busy() const { return st_ != M_IDLE; }
  void printStatus(Print& out) const;
  bool     enabled      = true;    // 부팅 시 바로 사용 가능 ('tilt disable' 로 잠금)
  uint8_t  max_duty_pct = 100;     // 리니어는 PWM 낮추면 힘 부족 → 100%
  uint16_t ramp_ms      = 300;
  uint32_t max_run_ms   = 15000;   // 1회 최대 구동 시간. 100mm ÷ 8mm/s ≈ 12.5초 + 여유 (끝은 내장 리미트)
  bool     invert       = false;   // 실물 배선 기준 정방향 (2026-10-21 확인). 방향 반대면 'set tilt invert 1'
  uint32_t manual_ms    = 9000;    // tilt up/down 숫자 없이 입력했을 때 시간
  uint32_t dump_up_ms   = 8000;    // 쏟기 올림 시간 (시험값)
  uint32_t dump_wait_ms = 2000;    // 쏟기 위에서 멈춤 시간
  uint32_t dump_down_ms = 9000;    // 쏟기 내림 시간 (올림보다 1초 길게 → 맨 아래 확실히 도착)
private:
  void apply(int dir, float duty_pct);
  void halt();     // 즉시 정지 (회신 없음, 내부용)
  const char* act_ = "up";
  bool stopped_ = false;            // 사용자 stop 으로 램프 다운 중 → 끝나도 DONE 안 보냄
  enum { M_IDLE, M_UP, M_RUN, M_DOWN, M_WAIT } st_ = M_IDLE;
  int dir_ = 0;
  float duty_ = 0;
  uint8_t goal_ = 0;
  bool dump_down_pending_ = false;  // 쏟기: 올림 끝나면 대기 후 내림
  uint32_t wait_end_ = 0;
  uint32_t t_last_ = 0, t_start_ = 0, run_end_ = 0;
};

extern ServoAxis act_lid;
extern ServoAxis act_gate;
extern TiltMotor act_tilt;

void act_begin();
void act_update();
void act_stop_all();
void act_command(char* line, Print& out);   // 한 줄 명령 처리
void act_poll(Stream& io);                   // Stream 에서 글자 모아 줄 단위로 act_command 호출
void act_help(Print& out);
// 비동기 회신 (동작 완료 등). 마지막으로 명령을 받은 포트로 한 줄 출력: "<a> <b> <c>"
//   DONE <lid|gate|tilt> <open|close|spin|move|up|down|dump>  /  STOPPED <name>  /  ERR <name> <이유>
void act_event(const char* a, const char* b = nullptr, const char* c = nullptr);
