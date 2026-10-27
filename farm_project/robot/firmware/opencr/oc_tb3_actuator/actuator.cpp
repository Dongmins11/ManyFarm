// =====================================================================
//  actuator.cpp  —  운송로봇 바구니 액추에이터 모듈 구현
// =====================================================================
#include "actuator.h"
#include "drv_pwm.h"   // OpenCR 코어의 PWM 드라이버 (Servo 라이브러리 대신 직접 사용)

// ---------- 기본 설정값 (시험 후 'dump' 출력값으로 교체) ----------
//  각도는 "닫힘 기준" (0 = 닫힘, + = 열림).  zero = 닫힘일 때 서보 raw 각도, dir = 열리는 방향
//                     usmin usmax  lo    hi    close open  mode         spd  unit fwd back dwell zero  dir  sfwd sback sopen stime
static const ServoCfg LID_DEF  = { 500, 2500, 0.f, 170.f, 0.f,  90.f, MODE_JOG,    60.f, 6.f, 3, 1, 150, 90.f, -1, 100, 50, -400, 1350 };  // 360° 서보: open = spin -400 1350 / close = spin 400 1350 (10-27: 1500→1350, 닫힐 때 부딪힘 수정 후 실측)
static const ServoCfg GATE_DEF = { 500, 2500, 0.f, 120.f, 0.f,  90.f, MODE_SMOOTH, 60.f, 6.f, 3, 1, 150, 90.f, +1, 100,  0, -400, 1200 };  // 360° 서보, 끊어치기 없음: open = spin -400 1200 / close = spin 400 1200 (2026-10-23 닫힘 출발 기준 재확인)

ServoAxis act_lid ("lid",  ACT_PIN_LID,  LID_DEF);
ServoAxis act_gate("gate", ACT_PIN_GATE, GATE_DEF);
TiltMotor act_tilt;

static Print* g_evt_out = nullptr;           // 비동기 회신 출력 포트 (act_poll 이 마지막 명령 포트로 설정)

void act_event(const char* a, const char* b, const char* c) {
  if (!g_evt_out) return;
  g_evt_out->print(a);
  if (b) { g_evt_out->print(' '); g_evt_out->print(b); }
  if (c) { g_evt_out->print(' '); g_evt_out->print(c); }
  g_evt_out->println();
}

// =====================================================================
//  ServoAxis
// =====================================================================
ServoAxis::ServoAxis(const char* name, uint8_t pin, const ServoCfg& def)
  : cfg(def), name_(name), pin_(pin) {}

void ServoAxis::begin() {
  drv_pwm_set_freq(pin_, ACT_SERVO_HZ);
  drv_pwm_setup(pin_);               // 초기 펄스 0 → 전원 켜도 서보가 튀지 않음
  drv_pwm_set_duty(pin_, 12, 0);
  released_ = true;
  t_last_ = millis();
}

void ServoAxis::writeDeg(float deg) {
  float raw = constrain(toRaw(deg), 0.0f, 180.0f);      // 닫힘 기준 → 서보 raw 각도
  float us = cfg.us_min + (cfg.us_max - cfg.us_min) * (raw / 180.0f);
  // 12bit 해상도: 20 ms 주기를 4096 등분 (약 4.9 us 단위)
  // (16bit 는 TIM2(D6) 에서 drv_pwm 내부 계산이 넘쳐서 쓰지 않음)
  uint32_t duty = (uint32_t)(us * 4096.0f / 20000.0f + 0.5f);
  drv_pwm_set_duty(pin_, 12, duty);
}

void ServoAxis::home(float deg) {
  deg = constrain(deg, cfg.lim_lo, cfg.lim_hi);
  cur_ = wp_ = target_ = start_ = deg;
  homed_ = true;
  released_ = false;
  st_ = ST_IDLE;
  writeDeg(deg);
}

void ServoAxis::homeRaw(float raw) {
  raw = constrain(raw, 0.0f, 180.0f);
  float deg = fromRaw(raw);                 // 교정용: 소프트 리미트 무시
  cur_ = wp_ = target_ = start_ = deg;
  homed_ = true;
  released_ = false;
  st_ = ST_IDLE;
  writeDeg(deg);
}

bool ServoAxis::moveTo(float deg) {
  if (!homed_) return false;
  return startMove(constrain(deg, cfg.lim_lo, cfg.lim_hi));
}

bool ServoAxis::moveRaw(float raw) {
  if (!homed_) return false;
  return startMove(fromRaw(constrain(raw, 0.0f, 180.0f)));   // 교정용: 소프트 리미트 무시
}

bool ServoAxis::zeroHere() {
  if (!homed_) return false;
  float raw = toRaw(cur_);
  cfg.zero_deg = raw;                       // 지금 서보 raw 각도 = 닫힘
  cur_ = wp_ = target_ = start_ = 0.0f;
  st_ = ST_IDLE;
  return true;
}

bool ServoAxis::startMove(float deg) {
  if (released_) { released_ = false; writeDeg(cur_); }
  start_ = cur_;
  target_ = deg;
  next_back_ = false;
  t_last_ = millis();
  if (cur_ == target_) { st_ = ST_IDLE; return true; }
  if (cfg.mode == MODE_JOG) planNext();
  else wp_ = target_;
  st_ = ST_MOVE;
  return true;
}

// JOG: 다음 경유점 계산.  전진 fwd칸 → 후퇴 back칸 → 전진 … 마지막 전진은 목표에서 딱 멈춤
void ServoAxis::planNext() {
  float dir = (target_ > cur_) ? 1.0f : -1.0f;
  if (!next_back_) {
    float nx = cur_ + dir * cfg.fwd * cfg.unit_deg;
    if (dir * (nx - target_) >= 0) nx = target_;       // 목표 도달 → 후퇴 없이 끝
    else next_back_ = true;
    wp_ = nx;
  } else {
    float nx = cur_ - dir * cfg.back * cfg.unit_deg;
    if (dir * (nx - start_) < 0) nx = start_;            // 시작점보다 뒤로는 안 감
    wp_ = nx;
    next_back_ = false;
  }
}

// 360° 서보 끊어치기:  [전진 sfwd ms] → [후진 sback ms] → 반복.  순수 전진 시간이 ms 가 되면 정지
void ServoAxis::spinPhase(uint32_t now, bool back) {
  int off = back ? -spin_off_ : spin_off_;
  int us = constrain(1500 + off, 500, 2500);
  drv_pwm_set_duty(pin_, 12, (uint32_t)(us * 4096.0f / 20000.0f + 0.5f));
  spin_back_ = back;
  uint32_t d = back ? cfg.sback_ms : (uint32_t)min((int32_t)cfg.sfwd_ms, spin_left_);
  if (!back) spin_left_ -= d; else spin_left_ += d;   // 후진한 만큼 다시 가야 함
  spin_end_ = now + d;
}

void ServoAxis::spin(int offset_us, uint32_t ms) {
  if (busy()) act_event("STOPPED", name_);  // 이전 동작을 새 명령이 덮어씀
  st_ = ST_IDLE;
  released_ = false;
  spinning_ = true;
  spin_off_ = offset_us;
  spin_left_ = (int32_t)ms;
  spin_t0_ = millis();
  spinPhase(spin_t0_, false);
}

void ServoAxis::stop() {
  bool was = busy();
  if (spinning_) release();                  // 연속회전: 정지점이 개체마다 달라서 펄스를 끊어서 멈춤
  else { target_ = wp_ = cur_; st_ = ST_IDLE; }
  if (was) act_event("STOPPED", name_);
}

void ServoAxis::abort() {
  bool was = busy();
  release();
  if (was) act_event("STOPPED", name_);
}

void ServoAxis::release() {
  drv_pwm_set_duty(pin_, 12, 0);
  released_ = true;
  spinning_ = false;
  st_ = ST_IDLE;
}

void ServoAxis::update(uint32_t now) {
  uint32_t dt = now - t_last_;
  t_last_ = now;
  if (spinning_) {                            // 360° 끊어치기 진행
    if (now - spin_t0_ > 20000UL) { release(); act_event("ERR", name_, "timeout"); return; }  // 안전 상한 20초
    if ((int32_t)(now - spin_end_) >= 0) {
      if (!spin_back_ && spin_left_ <= 0) { release(); act_event("DONE", name_, act_); return; }  // 마지막 전진 끝 → 정지 + 완료 회신
      if (!spin_back_ && cfg.sback_ms > 0) spinPhase(now, true);  // 전진 끝 → 후진
      else spinPhase(now, false);                                 // 후진 끝(또는 연속) → 전진
    }
    return;
  }
  if (!homed_ || released_) return;

  switch (st_) {
    case ST_MOVE:
      if (cfg.mode == MODE_JOG) {
        // 끊어치기: 경유점으로 한 번에 펄스 변경 (서보 최고속으로 이동) → 쉬는 동안 도착
        cur_ = wp_;
        writeDeg(cur_);
        st_ = ST_DWELL;
        dwell_end_ = now + cfg.dwell_ms;
      } else {
        float step = cfg.speed_dps * dt / 1000.0f;
        float d = wp_ - cur_;
        if (fabsf(d) <= step) cur_ = wp_;
        else cur_ += (d > 0 ? step : -step);
        writeDeg(cur_);
        if (cur_ == wp_) { st_ = ST_IDLE; act_event("DONE", name_, act_); }
      }
      break;
    case ST_DWELL:
      if ((int32_t)(now - dwell_end_) >= 0) {
        if (cur_ == target_) { st_ = ST_IDLE; act_event("DONE", name_, act_); }
        else { planNext(); st_ = ST_MOVE; }
      }
      break;
    default:
      break;
  }
}

void ServoAxis::printStatus(Print& out) const {
  out.print(name_);
  out.print(": pos=");    out.print(cur_, 1);
  out.print(" target=");  out.print(target_, 1);
  out.print(" (raw=");    out.print(toRaw(cur_), 1); out.print(")");
  out.print(" state=");   out.print(!homed_ ? "NOT_HOMED" : released_ ? "RELEASED" : (st_ == ST_IDLE ? "IDLE" : "MOVING"));
  out.print(" mode=");    out.println(cfg.mode == MODE_JOG ? "jog" : "smooth");
}

void ServoAxis::printCfg(Print& out) const {
  out.print("// "); out.print(name_); out.println(" : 이 줄을 actuator.cpp 기본값에 붙여넣기");
  out.print("{ ");
  out.print(cfg.us_min); out.print(", "); out.print(cfg.us_max); out.print(", ");
  out.print(cfg.lim_lo, 1); out.print("f, "); out.print(cfg.lim_hi, 1); out.print("f, ");
  out.print(cfg.close_deg, 1); out.print("f, "); out.print(cfg.open_deg, 1); out.print("f, ");
  out.print(cfg.mode == MODE_JOG ? "MODE_JOG, " : "MODE_SMOOTH, ");
  out.print(cfg.speed_dps, 1); out.print("f, "); out.print(cfg.unit_deg, 1); out.print("f, ");
  out.print(cfg.fwd); out.print(", "); out.print(cfg.back); out.print(", ");
  out.print(cfg.dwell_ms); out.print(", ");
  out.print(cfg.zero_deg, 1); out.print("f, "); out.print(cfg.dir > 0 ? "+1" : "-1"); out.print(", ");
  out.print(cfg.sfwd_ms); out.print(", "); out.print(cfg.sback_ms); out.print(", ");
  out.print(cfg.sopen_us); out.print(", "); out.print(cfg.stime_ms); out.println(" }");
}

// =====================================================================
//  TiltMotor (리니어 액추에이터 12V 100mm + L298N)
// =====================================================================
void TiltMotor::begin() {
  pinMode(ACT_PIN_IN1, OUTPUT);
  pinMode(ACT_PIN_IN2, OUTPUT);
  digitalWrite(ACT_PIN_IN1, LOW);
  digitalWrite(ACT_PIN_IN2, LOW);
  drv_pwm_set_freq(ACT_PIN_ENA, ACT_TILT_PWM_HZ);   // analogWrite 첫 호출 전에 주파수 지정
  analogWrite(ACT_PIN_ENA, 0);
  st_ = M_IDLE;
  t_last_ = millis();
}

void TiltMotor::apply(int dir, float duty_pct) {
  if (invert) dir = -dir;           // 배선 극성 반대 보정
  if (dir > 0)      { digitalWrite(ACT_PIN_IN1, HIGH); digitalWrite(ACT_PIN_IN2, LOW);  }
  else if (dir < 0) { digitalWrite(ACT_PIN_IN1, LOW);  digitalWrite(ACT_PIN_IN2, HIGH); }
  else              { digitalWrite(ACT_PIN_IN1, LOW);  digitalWrite(ACT_PIN_IN2, LOW);  }
  analogWrite(ACT_PIN_ENA, (uint32_t)(duty_pct * 255.0f / 100.0f + 0.5f));
}

const char* TiltMotor::run(int dir, uint8_t duty_pct, uint32_t run_ms) {
  if (!enabled)                 return "tilt locked (use 'tilt enable')";
  if (dir == 0)                 return "bad direction";
  if (st_ != M_IDLE && dir != dir_) return "busy: stop first before changing direction";
  if (st_ != M_IDLE)            return "busy";
  if (duty_pct > max_duty_pct)  duty_pct = max_duty_pct;
  if (run_ms > max_run_ms)      run_ms = max_run_ms;
  dir_ = dir;
  goal_ = duty_pct;
  duty_ = 0;
  t_start_ = t_last_ = millis();
  run_end_ = t_start_ + ramp_ms + run_ms;
  stopped_ = false;
  st_ = M_UP;
  apply(dir_, 0);
  return nullptr;
}

const char* TiltMotor::dump() {
  const char* err = run(+1, max_duty_pct, dump_up_ms);
  if (!err) dump_down_pending_ = true;
  return err;
}

void TiltMotor::stop() {
  if (st_ == M_IDLE || stopped_) return;
  dump_down_pending_ = false;      // 사용자가 멈추면 자동 내림 취소
  if (st_ == M_WAIT) { estop(); return; }
  stopped_ = true;                 // 램프 다운 끝나도 DONE 안 보냄
  if (st_ == M_UP || st_ == M_RUN) st_ = M_DOWN;
  act_event("STOPPED", "tilt");
}

void TiltMotor::halt() {
  dump_down_pending_ = false;
  stopped_ = false;
  apply(0, 0);
  duty_ = 0;
  st_ = M_IDLE;
}

void TiltMotor::estop() {
  bool was = (st_ != M_IDLE) && !stopped_;
  halt();
  if (was) act_event("STOPPED", "tilt");
}

void TiltMotor::update(uint32_t now) {
  uint32_t dt = now - t_last_;
  t_last_ = now;
  if (st_ == M_IDLE) return;

  if (st_ == M_WAIT) {                                      // 쏟기: 위에서 정지 중 (모터 OFF)
    if ((int32_t)(now - wait_end_) >= 0) {
      st_ = M_IDLE;
      if (run(-1, max_duty_pct, dump_down_ms)) { halt(); act_event("ERR", "tilt", "dump_down"); }
    }
    return;
  }

  // 안전장치: 램프 포함 전체 시간이 상한 + 여유를 넘으면 즉시 정지
  if (now - t_start_ > max_run_ms + 2UL * ramp_ms + 200UL) { halt(); act_event("ERR", "tilt", "timeout"); return; }

  float rate = (ramp_ms > 0) ? (float)goal_ * dt / ramp_ms : 1000.0f;
  switch (st_) {
    case M_UP:
      duty_ += rate;
      if (duty_ >= goal_) { duty_ = goal_; st_ = M_RUN; }
      break;
    case M_RUN:
      if ((int32_t)(now - run_end_) >= 0) st_ = M_DOWN;
      break;
    case M_DOWN:
      duty_ -= rate;
      if (duty_ <= 0) {
        bool next = dump_down_pending_;
        bool user_stop = stopped_;
        halt();                                             // 정지 (pending·stopped 지움)
        if (next) { st_ = M_WAIT; wait_end_ = now + dump_wait_ms; }  // 쏟기: 올림 끝 → 대기 → 내림
        else if (!user_stop) act_event("DONE", "tilt", act_);       // 정상 종료 → 완료 회신
        return;
      }
      break;
    default: break;
  }
  apply(dir_, duty_);
}

void TiltMotor::printStatus(Print& out) const {
  out.print("tilt: ");
  out.print(enabled ? "ENABLED" : "LOCKED");
  out.print(" state=");
  out.print(st_ == M_IDLE ? "IDLE" : st_ == M_UP ? "RAMP_UP" : st_ == M_RUN ? "RUN" : st_ == M_WAIT ? "DUMP_WAIT" : "RAMP_DOWN");
  out.print(" dir=");  out.print(dir_ > 0 ? "up" : dir_ < 0 ? "down" : "-");
  out.print(" duty="); out.print(duty_, 0); out.print("%");
  out.print(" (max "); out.print(max_duty_pct); out.print("%, ramp ");
  out.print(ramp_ms); out.print("ms, maxrun "); out.print(max_run_ms); out.print("ms, invert ");
  out.print(invert ? 1 : 0); out.print(", dump up "); out.print(dump_up_ms);
  out.print("ms / wait "); out.print(dump_wait_ms); out.print("ms / down "); out.print(dump_down_ms); out.println("ms)");
}

// =====================================================================
//  공통
// =====================================================================
void act_begin() {
  act_lid.begin();
  act_gate.begin();
  act_tilt.begin();
}

void act_update() {
  uint32_t now = millis();
  act_lid.update(now);
  act_gate.update(now);
  act_tilt.update(now);
}

void act_stop_all() {
  act_lid.stop();
  act_gate.stop();
  act_tilt.estop();
}

void act_help(Print& out) {
  // 짧은 영문 도움말 (펌웨어 크기 절약). 자세한 설명은 README.md 참고
  out.println(F("== transport_01 actuator =="));
  out.println(F("lid|gate open|close  | lid|gate spin <+-us> <ms> | lid|gate stop|release"));
  out.println(F("tilt up|down [duty%] [ms] (def 100 9000) | tilt dump | tilt stop|enable|disable"));
  out.println(F("set lid|gate sopen|stime|sfwd|sback <v> | set tilt dumpup|dumpwait|dumpdown|invert|maxduty|ramp|maxrun <v>"));
  out.println(F("stop | release | status | dump | ping | help"));
  out.println(F("reply: OK(accepted) DONE <name> <act> / STOPPED <name> / ERR <name> timeout / PONG / READY"));
}

static void lower(char* s) { for (; *s; ++s) if (*s >= 'A' && *s <= 'Z') *s += 32; }

static void printAll(Print& out) {
  act_lid.printStatus(out);
  act_gate.printStatus(out);
  act_tilt.printStatus(out);
}

static void servoCmd(ServoAxis& ax, char* a1, char* a2, char* a3, Print& out) {
  if (!a1) { ax.printStatus(out); return; }
  if (!strcmp(a1, "home")) {
    float d = a2 ? atof(a2) : ax.cfg.close_deg;
    ax.home(d);
    out.print("OK "); out.print(ax.name()); out.print(" home="); out.println(ax.pos(), 1);
    return;
  }
  if (!strcmp(a1, "raw")) {
    if (!a2) { out.println("ERR usage: raw home <r> | raw <r>"); return; }
    if (!strcmp(a2, "home")) {
      if (!a3) { out.println("ERR usage: raw home <r>"); return; }
      ax.homeRaw(atof(a3));
      out.print("OK "); out.print(ax.name()); out.print(" raw home -> "); ax.printStatus(out);
      return;
    }
    if (!ax.moveRaw(atof(a2))) { out.print("ERR "); out.print(ax.name()); out.println(" not homed -> 'raw home <r>' 먼저"); return; }
    out.print("OK "); out.print(ax.name()); out.print(" raw -> "); out.println(constrain((float)atof(a2), 0.0f, 180.0f), 1);
    return;
  }
  if (!strcmp(a1, "spin")) {                  // 360° 서보: lid spin <+/-us> <ms>
    int off = a2 ? atoi(a2) : 200;
    uint32_t ms = a3 ? (uint32_t)constrain(atol(a3), 0L, 6000L) : 2000;
    ax.setAction("spin");
    ax.spin(off, ms);
    out.print("OK "); out.print(ax.name()); out.print(" spin "); out.print(off); out.print("us ");
    out.print(ms); out.print("ms net, 전진 "); out.print(ax.cfg.sfwd_ms); out.print("ms / 후진 ");
    out.print(ax.cfg.sback_ms); out.println("ms 반복 (끝나면 자동 정지)");
    return;
  }
  if (!strcmp(a1, "zero")) {
    if (ax.busy()) { out.println("ERR 움직이는 중 → 멈춘 뒤 zero"); return; }
    if (!ax.zeroHere()) { out.println("ERR not homed"); return; }
    out.print("OK "); out.print(ax.name()); out.print(" zero = raw "); out.print(ax.cfg.zero_deg, 1);
    out.println("  (지금 위치 = 닫힘 0)");
    return;
  }
  if (!strcmp(a1, "stop"))    { ax.stop();    out.print("OK "); out.print(ax.name()); out.println(" stop");    return; }
  if (!strcmp(a1, "release")) { ax.abort(); out.print("OK "); out.print(ax.name()); out.println(" release"); return; }

  // 360° 서보 (sopen ≠ 0): open/close = 시간 기반 끊어치기. home 필요 없음
  if (ax.cfg.sopen_us != 0 && (!strcmp(a1, "open") || !strcmp(a1, "close"))) {
    bool op = !strcmp(a1, "open");
    int off = op ? ax.cfg.sopen_us : -ax.cfg.sopen_us;
    ax.setAction(op ? "open" : "close");     // 완료 시 'DONE <name> open|close'
    ax.spin(off, ax.cfg.stime_ms);
    out.print("OK "); out.print(ax.name()); out.print(" "); out.print(a1);
    out.print(" = spin "); out.print(off); out.print(" "); out.print(ax.cfg.stime_ms);
    out.println(" (끝나면 자동 정지)");
    return;
  }

  ax.setAction(!strcmp(a1, "open") ? "open" : !strcmp(a1, "close") ? "close" : "move");
  float goal;
  if (!strcmp(a1, "open"))       goal = ax.cfg.open_deg;
  else if (!strcmp(a1, "close")) goal = ax.cfg.close_deg;
  else if ((a1[0] >= '0' && a1[0] <= '9') || a1[0] == '-' || a1[0] == '.') goal = atof(a1);
  else { out.print("ERR unknown: "); out.println(a1); return; }

  if (!ax.moveTo(goal)) {
    out.print("ERR "); out.print(ax.name());
    out.println(" not homed -> 닫혀 있으면 'home', 교정 중이면 'raw home <r>'");
    return;
  }
  out.print("OK "); out.print(ax.name()); out.print(" -> "); out.println(ax.target(), 1);
}

static void setCmd(char* who, char* key, char* val, Print& out) {
  if (!who || !key || !val) { out.println("ERR usage: set lid|gate|tilt <key> <val>"); return; }
  if (!strcmp(who, "tilt")) {
    long v = atol(val);
    if      (!strcmp(key, "maxduty")) act_tilt.max_duty_pct = constrain(v, 0, 100);
    else if (!strcmp(key, "ramp"))    act_tilt.ramp_ms      = constrain(v, 0, 5000);
    else if (!strcmp(key, "maxrun"))  act_tilt.max_run_ms   = constrain(v, 0, 30000);
    else if (!strcmp(key, "invert"))  { act_tilt.estop(); act_tilt.invert = (v != 0); }
    else if (!strcmp(key, "dumpup"))   act_tilt.dump_up_ms   = constrain(v, 0, 15000);
    else if (!strcmp(key, "dumpdown")) act_tilt.dump_down_ms = constrain(v, 0, 15000);
    else if (!strcmp(key, "dumpwait")) act_tilt.dump_wait_ms = constrain(v, 0, 10000);
    else { out.print("ERR key: "); out.println(key); return; }
    act_tilt.printStatus(out);
    return;
  }
  ServoAxis* ax = !strcmp(who, "lid") ? &act_lid : !strcmp(who, "gate") ? &act_gate : nullptr;
  if (!ax) { out.print("ERR who: "); out.println(who); return; }
  ServoCfg& c = ax->cfg;
  float f = atof(val);
  if      (!strcmp(key, "open"))  c.open_deg  = f;
  else if (!strcmp(key, "close")) c.close_deg = f;
  else if (!strcmp(key, "lo"))    c.lim_lo    = f;
  else if (!strcmp(key, "hi"))    c.lim_hi    = f;
  else if (!strcmp(key, "speed")) c.speed_dps = constrain(f, 1.0f, 600.0f);
  else if (!strcmp(key, "unit"))  c.unit_deg  = constrain(f, 0.5f, 90.0f);
  else if (!strcmp(key, "dwell")) c.dwell_ms  = constrain((long)f, 0L, 5000L);
  else if (!strcmp(key, "usmin")) c.us_min    = constrain((long)f, 400L, 2600L);
  else if (!strcmp(key, "usmax")) c.us_max    = constrain((long)f, 400L, 2600L);
  else if (!strcmp(key, "sfwd") || !strcmp(key, "sback")) {
    long v = constrain(atol(val), 0L, 2000L);
    uint16_t sf = !strcmp(key, "sfwd") ? v : c.sfwd_ms;
    uint16_t sb = !strcmp(key, "sback") ? v : c.sback_ms;
    if (sf <= sb) { out.println("ERR sfwd 는 sback 보다 커야 함"); return; }
    c.sfwd_ms = sf; c.sback_ms = sb;
  }
  else if (!strcmp(key, "sopen")) { ax->abort(); c.sopen_us = constrain(atol(val), -1000L, 1000L); }
  else if (!strcmp(key, "stime")) c.stime_ms = constrain(atol(val), 0L, 6000L);
  else if (!strcmp(key, "dir") || !strcmp(key, "zero")) {
    ax->stop();
    float raw = ax->toRaw(ax->pos());               // 지금 서보 위치는 그대로 유지
    if (!strcmp(key, "dir")) {
      long v = atol(val);
      if (v != 1 && v != -1) { out.println("ERR dir: 1 | -1"); return; }
      c.dir = (int8_t)v;
    } else c.zero_deg = constrain(f, 0.0f, 180.0f);
    if (ax->homed()) ax->homeRaw(raw);
  }
  else if (!strcmp(key, "mode")) {
    if (!strcmp(val, "jog")) c.mode = MODE_JOG;
    else if (!strcmp(val, "smooth")) c.mode = MODE_SMOOTH;
    else { out.println("ERR mode: smooth|jog"); return; }
  }
  else if (!strcmp(key, "fwd") || !strcmp(key, "back")) {
    long v = constrain(atol(val), 0L, 20L);
    uint8_t fwd = !strcmp(key, "fwd") ? v : c.fwd;
    uint8_t bk  = !strcmp(key, "back") ? v : c.back;
    if (fwd <= bk) { out.println("ERR fwd 는 back 보다 커야 함 (안 그러면 앞으로 못 감)"); return; }
    c.fwd = fwd; c.back = bk;
  }
  else { out.print("ERR key: "); out.println(key); return; }
  ax->printCfg(out);
}

void act_command(char* line, Print& out) {
  lower(line);
  char* cmd = strtok(line, " \t");
  if (!cmd) return;
  char* a1 = strtok(nullptr, " \t");
  char* a2 = strtok(nullptr, " \t");
  char* a3 = strtok(nullptr, " \t");

  if      (!strcmp(cmd, "help") || !strcmp(cmd, "?")) act_help(out);
  else if (!strcmp(cmd, "status")) printAll(out);
  else if (!strcmp(cmd, "dump"))   { act_lid.printCfg(out); act_gate.printCfg(out); act_tilt.printStatus(out); }
  else if (!strcmp(cmd, "stop"))   { act_stop_all(); out.println("OK stop all"); }
  else if (!strcmp(cmd, "release")){ act_lid.abort(); act_gate.abort(); out.println("OK release servos"); }
  else if (!strcmp(cmd, "ping"))   out.println("PONG");
  else if (!strcmp(cmd, "lid"))    servoCmd(act_lid,  a1, a2, a3, out);
  else if (!strcmp(cmd, "gate"))   servoCmd(act_gate, a1, a2, a3, out);
  else if (!strcmp(cmd, "set"))    setCmd(a1, a2, a3, out);
  else if (!strcmp(cmd, "tilt")) {
    if (!a1) { act_tilt.printStatus(out); return; }
    if      (!strcmp(a1, "enable"))  { act_tilt.enabled = true;  out.println("OK tilt enabled"); }
    else if (!strcmp(a1, "disable")) { act_tilt.estop(); act_tilt.enabled = false; out.println("OK tilt locked"); }
    else if (!strcmp(a1, "stop"))    { act_tilt.stop(); out.println("OK tilt stop (ramp down)"); }
    else if (!strcmp(a1, "dump")) {
      if (!act_tilt.busy()) act_tilt.setAction("dump");
      const char* err = act_tilt.dump();
      if (err) { out.print("ERR "); out.println(err); }
      else { out.print("OK tilt dump: up "); out.print(act_tilt.dump_up_ms); out.print("ms -> wait ");
             out.print(act_tilt.dump_wait_ms); out.print("ms -> down ");
             out.print(act_tilt.dump_down_ms); out.println("ms"); }
    }
    else if (!strcmp(a1, "up") || !strcmp(a1, "down")) {
      int dir = !strcmp(a1, "up") ? +1 : -1;
      uint8_t duty = a2 ? (uint8_t)constrain(atol(a2), 0L, 100L) : 100;
      uint32_t ms  = a3 ? (uint32_t)constrain(atol(a3), 0L, 30000L) : act_tilt.manual_ms;
      if (!act_tilt.busy()) act_tilt.setAction(dir > 0 ? "up" : "down");
      const char* err = act_tilt.run(dir, duty, ms);
      if (err) { out.print("ERR "); out.println(err); }
      else { out.print("OK tilt "); out.print(a1); out.print(" "); out.print(duty); out.print("% "); out.print(ms); out.println("ms"); }
    }
    else { out.print("ERR unknown: "); out.println(a1); }
  }
  else { out.print("ERR unknown command: "); out.println(cmd); }
}

void act_poll(Stream& io) {
  static char buf[96];
  static uint8_t n = 0;
  while (io.available()) {
    char c = (char)io.read();
    if (c == '\r' || c == '\n') {
      if (n > 0) { buf[n] = 0; g_evt_out = &io; act_command(buf, io); n = 0; }   // 회신은 명령이 온 포트로
    } else if (n < sizeof(buf) - 1) {
      buf[n++] = c;
    }
  }
}
