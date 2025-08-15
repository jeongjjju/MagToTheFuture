// ====================================================================
// Haptic Orchestrator - Actuator Transport Controller (v6 - Direction Fix)
// --------------------------------------------------------------------
// - Receives absolute coordinates (in mm) from Python UI.
// - Moves stepper motors sequentially (X-axis, then Y-axis).
// - Reports current position (in steps) back to the UI.
// - Individual motor speed control.
// - Corrected motor movement direction to match UI.
// ====================================================================

// --- Pin Configuration ---
#define X_DIR_PIN 4
#define X_STEP_PIN 5
#define Y_DIR_PIN 2
#define Y_STEP_PIN 3
#define ENABLE_PIN 8

// --- Calibration ---
const float STEPS_PER_MM_X = 80.0;
const float STEPS_PER_MM_Y = 80.0;

// --- Movement Settings ---
const int Y_STEP_DELAY_US = 20;
const int X_STEP_DELAY_US = 50;

// --- Global State Variables ---
enum Axis { X_AXIS, Y_AXIS };
long current_pos[2] = {0, 0};
long target_pos[2] = {0, 0};
bool is_moving = false;

// --- Serial Communication Buffer ---
const byte numChars = 64;
char receivedChars[numChars];
boolean newData = false;

// --- Position Reporting Timer ---
unsigned long last_report_time = 0;
const long report_interval = 100;

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    ;
  }
  
  pinMode(X_DIR_PIN, OUTPUT);
  pinMode(X_STEP_PIN, OUTPUT);
  pinMode(Y_DIR_PIN, OUTPUT);
  pinMode(Y_STEP_PIN, OUTPUT);
  pinMode(ENABLE_PIN, OUTPUT);

  digitalWrite(ENABLE_PIN, HIGH);
}

void loop() {
  receiveSerialData();
  processSerialData();
  updateMovement();
  reportPosition();
  // delay(1); is removed for max speed
}

// ========================================================
//              Core Logic Functions
// ========================================================

void updateMovement() {
  if (!is_moving) {
    return;
  }

  // --- Move X-axis first ---
  if (current_pos[X_AXIS] != target_pos[X_AXIS]) {
    bool direction = (current_pos[X_AXIS] < target_pos[X_AXIS]);
    stepMotor(X_AXIS, direction);
    return;
  }

  // --- Then move Y-axis ---
  if (current_pos[Y_AXIS] != target_pos[Y_AXIS]) {
    bool direction = (current_pos[Y_AXIS] < target_pos[Y_AXIS]);
    stepMotor(Y_AXIS, direction);
    return;
  }

  // --- Destination Reached ---
  if (current_pos[X_AXIS] == target_pos[X_AXIS] && current_pos[Y_AXIS] == target_pos[Y_AXIS]) {
    is_moving = false;
    digitalWrite(ENABLE_PIN, HIGH);
    Serial.println("OK");
  }
}

void stepMotor(Axis axis, bool positive_dir) {
  int dir_pin, step_pin, step_delay;
  
  if (axis == X_AXIS) {
    dir_pin = X_DIR_PIN;
    step_pin = X_STEP_PIN;
    step_delay = X_STEP_DELAY_US;
    // MODIFIED: UI의 + 방향과 실제 모터의 + 방향을 일치시키기 위해 로직을 반전시켰습니다.
    digitalWrite(dir_pin, positive_dir ? LOW : HIGH); 
  } else { // Y_AXIS
    dir_pin = Y_DIR_PIN;
    step_pin = Y_STEP_PIN;
    step_delay = Y_STEP_DELAY_US;
    // MODIFIED: UI의 + 방향과 실제 모터의 + 방향을 일치시키기 위해 로직을 반전시켰습니다.
    digitalWrite(dir_pin, positive_dir ? LOW : HIGH);
  }

  digitalWrite(step_pin, HIGH);
  delayMicroseconds(step_delay);
  digitalWrite(step_pin, LOW);
  delayMicroseconds(step_delay);

  current_pos[axis] += (positive_dir ? 1 : -1);
}


// ========================================================
//              Serial Communication
// ========================================================

void receiveSerialData() {
  static byte ndx = 0;
  char rc;

  while (Serial.available() > 0 && newData == false) {
    rc = Serial.read();
    if (rc == '\n' || rc == '\r') {
      if (ndx > 0) {
        receivedChars[ndx] = '\0';
        ndx = 0;
        newData = true;
      }
    } else {
      if (ndx < numChars - 1) {
        receivedChars[ndx] = rc;
        ndx++;
      }
    }
  }
}

void processSerialData() {
  if (newData == false) {
    return;
  }

  char* command = strtok(receivedChars, ",");

  if (command != NULL) {
    if (strcmp(command, "R") == 0) {
      Serial.println("Transport Ready");
    } 
    else if (strcmp(command, "H") == 0) {
      current_pos[X_AXIS] = 0;
      current_pos[Y_AXIS] = 0;
      target_pos[X_AXIS] = 0;
      target_pos[Y_AXIS] = 0;
      is_moving = false;
      digitalWrite(ENABLE_PIN, HIGH);
      Serial.println("Homed");
    }
    else if (strcmp(command, "!") == 0) {
      target_pos[X_AXIS] = current_pos[X_AXIS];
      target_pos[Y_AXIS] = current_pos[Y_AXIS];
      is_moving = false;
      digitalWrite(ENABLE_PIN, HIGH);
      Serial.println("STOPPED");
    }
    else if (strcmp(command, "M") == 0) {
      char* x_str = strtok(NULL, ",");
      char* y_str = strtok(NULL, ",");
      if (x_str != NULL && y_str != NULL) {
        float x_mm = atof(x_str);
        float y_mm = atof(y_str);

        target_pos[X_AXIS] = (long)(x_mm * STEPS_PER_MM_X);
        target_pos[Y_AXIS] = (long)(y_mm * STEPS_PER_MM_Y);
        
        is_moving = true;
        digitalWrite(ENABLE_PIN, LOW);
      }
    }
  }
  newData = false;
}

void reportPosition() {
  if (millis() - last_report_time > report_interval) {
    Serial.print("POS,");
    Serial.print(current_pos[X_AXIS]);
    Serial.print(",");
    Serial.println(current_pos[Y_AXIS]);
    last_report_time = millis();
  }
}
