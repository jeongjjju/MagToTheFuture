// ===================================================
//  PyQt GUI 연동용 햅틱 제어 코드 (PWM 주파수 수정)
// ===================================================

// --- 핀 설정 ---
const int ENABLE = 10;
const int DIR1 = 8;
const int DIR2 = 9;
const int HEATER_PIN = 6;

// --- 햅틱 상태 변수 ---
int force_mode = 0, magnitude = 0, vibration_mode = 0, frequency = 0, amplitude = 0;
bool is_heat_on = false;
unsigned long haptic_stop_time = 0;
unsigned long last_vib_switch_time = 0;
bool vib_is_on_state = false;

void setup() {
  Serial.begin(115200);
  pinMode(ENABLE, OUTPUT);
  pinMode(DIR1, OUTPUT);
  pinMode(DIR2, OUTPUT);
  pinMode(HEATER_PIN, OUTPUT);
  
  // --- 수정된 부분 시작 ---
  // 9번, 10번 핀의 PWM 주파수를 약 31Hz로 변경합니다. (Timer1 Prescaler 변경)
  TCCR1B = TCCR1B & B11111000 | B00000101;
  // --- 수정된 부분 끝 ---

  stopAllHaptics();
}

void loop() {
  parseGUICommand();
  updateHaptics();
}

// ========================================================
//              메인 로직 함수들
// ========================================================

void parseGUICommand() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    if (command.length() == 0) return;
    char cmd_type = command.charAt(0);

    if (cmd_type == 'R') {
      Serial.println("Haptic Ready");
      return;
    }
    
    if (cmd_type == 'H') {
      int p[7];
      sscanf(command.c_str(), "H,%d,%d,%d,%d,%d,%d,%d", &p[0], &p[1], &p[2], &p[3], &p[4], &p[5], &p[6]);
      force_mode = p[0]; magnitude = p[1]; vibration_mode = p[2];
      frequency = p[3]; amplitude = p[4]; long duration = p[5];
      is_heat_on = (p[6] == 1);
      
      if (duration > 0) {
        haptic_stop_time = millis() + duration;
      } else {
        haptic_stop_time = 0;
        if (magnitude == 0 && amplitude == 0 && !is_heat_on) {
          stopAllHaptics();
        }
      }
      Serial.println("OK: Haptic command received.");
    }
  }
}

void updateHaptics() {
  if (haptic_stop_time > 0 && millis() >= haptic_stop_time) {
    stopAllHaptics();
    return;
  }
  
  digitalWrite(HEATER_PIN, is_heat_on);

  int final_direction_mode = 0;
  if (magnitude > 0) final_direction_mode = force_mode;
  else if (amplitude > 0) final_direction_mode = vibration_mode;

  if (final_direction_mode == 1) { digitalWrite(DIR1, HIGH); digitalWrite(DIR2, LOW); }
  else if (final_direction_mode == 2) { digitalWrite(DIR1, LOW); digitalWrite(DIR2, HIGH); }
  else { digitalWrite(DIR1, LOW); digitalWrite(DIR2, LOW); }

  int base_pwm = magnitude;
  int peak_pwm = map(amplitude, 0, 255, base_pwm, 255);

  if (frequency > 0 && amplitude > 0) {
    long switch_interval = 500000 / (long)frequency;
    if (micros() - last_vib_switch_time >= switch_interval) {
      vib_is_on_state = !vib_is_on_state;
      analogWrite(ENABLE, vib_is_on_state ? peak_pwm : base_pwm);
      last_vib_switch_time = micros();
    }
  } else {
    analogWrite(ENABLE, base_pwm);
  }
}

void stopAllHaptics() {
  force_mode = 0; magnitude = 0; vibration_mode = 0;
  frequency = 0; amplitude = 0; is_heat_on = false;
  haptic_stop_time = 0;
  digitalWrite(ENABLE, 0);
  digitalWrite(HEATER_PIN, LOW);
  digitalWrite(DIR1, LOW);
  digitalWrite(DIR2, LOW);
}