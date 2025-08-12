#include <Wire.h>
#include <Adafruit_MLX90393.h>
#include <Adafruit_Sensor.h>

// --- 설정값 ---
const int SENSORS_PER_MUX = 8;
const long SERIAL_SPEED = 1000000;

// --- 각 MUX(I2C 버스)별 객체 분리 ---
// MUX 0x70 -> Wire (핀 18, 19)
Adafruit_MLX90393 sensors_mux0[SENSORS_PER_MUX];
bool is_connected_mux0[SENSORS_PER_MUX];
sensors_event_t event_mux0;

// MUX 0x71 -> Wire1 (핀 17, 16)
Adafruit_MLX90393 sensors_mux1[SENSORS_PER_MUX];
bool is_connected_mux1[SENSORS_PER_MUX];
sensors_event_t event_mux1;

// MUX 0x72 -> Wire2 (핀 24, 25)
Adafruit_MLX90393 sensors_mux2[SENSORS_PER_MUX];
bool is_connected_mux2[SENSORS_PER_MUX];
sensors_event_t event_mux2;

// --- 캘리브레이션을 위한 오프셋 변수 ---
float mag_offset_x[3][SENSORS_PER_MUX] = {0};
float mag_offset_y[3][SENSORS_PER_MUX] = {0};
float mag_offset_z[3][SENSORS_PER_MUX] = {0};

// --- MUX 주소 정의 ---
const byte muxAddress0 = 0x70;
const byte muxAddress1 = 0x71;
const byte muxAddress2 = 0x72;

// --- 함수 정의 ---
void tcaSelect(byte muxAddress, uint8_t channel, TwoWire *bus) {
  if (channel > 7) return;
  bus->beginTransmission(muxAddress);
  bus->write(1 << channel);
  bus->endTransmission();
}

void setup() {
  Serial.begin(SERIAL_SPEED);
  
  // 3개의 I2C 포트 시작
  Wire.begin();
  Wire1.begin();
  Wire2.begin();

  // 각 버스 속도 설정
  Wire.setClock(1000000L);
  Wire1.setClock(1000000L);
  Wire2.setClock(1000000L);
  
  delay(2000); // 시리얼 포트 안정화 시간

  Serial.println("Initializing All Sensors on 3 separate I2C buses...");

  // 각 MUX 초기화
  for (int i = 0; i < SENSORS_PER_MUX; i++) {
    tcaSelect(muxAddress0, i, &Wire); delay(10);
    if (sensors_mux0[i].begin_I2C(0x18, &Wire)) {
      is_connected_mux0[i] = true;
      sensors_mux0[i].setGain(MLX90393_GAIN_1_33X);
    } else { is_connected_mux0[i] = false; }
  }
  for (int i = 0; i < SENSORS_PER_MUX; i++) {
    tcaSelect(muxAddress1, i, &Wire1); delay(10);
    if (sensors_mux1[i].begin_I2C(0x18, &Wire1)) {
      is_connected_mux1[i] = true;
      sensors_mux1[i].setGain(MLX90393_GAIN_1_33X);
    } else { is_connected_mux1[i] = false; }
  }
  for (int i = 0; i < SENSORS_PER_MUX; i++) {
    tcaSelect(muxAddress2, i, &Wire2); delay(10);
    if (sensors_mux2[i].begin_I2C(0x18, &Wire2)) {
      is_connected_mux2[i] = true;
      sensors_mux2[i].setGain(MLX90393_GAIN_1_33X);
    } else { is_connected_mux2[i] = false; }
  }
  
  // --- 자동 캘리브레이션 시작 ---
  Serial.println("\n--- Starting Automatic Sensor Calibration ---");
  Serial.print("Calibrating... ");
  const int SAMPLES = 10; // 평균을 낼 샘플 수

  for (int mux_idx = 0; mux_idx < 3; mux_idx++) {
    for (int sensor_idx = 0; sensor_idx < SENSORS_PER_MUX; sensor_idx++) {
      float temp_x = 0, temp_y = 0, temp_z = 0;
      TwoWire* bus = (mux_idx == 0) ? &Wire : (mux_idx == 1) ? &Wire1 : &Wire2;
      byte mux_addr = (mux_idx == 0) ? muxAddress0 : (mux_idx == 1) ? muxAddress1 : muxAddress2;
      Adafruit_MLX90393* sensor_array = (mux_idx == 0) ? sensors_mux0 : (mux_idx == 1) ? sensors_mux1 : sensors_mux2;
      sensors_event_t* event = (mux_idx == 0) ? &event_mux0 : (mux_idx == 1) ? &event_mux1 : &event_mux2;

      // 연결된 센서만 캘리브레이션 진행
      bool is_conn = (mux_idx == 0) ? is_connected_mux0[sensor_idx] : (mux_idx == 1) ? is_connected_mux1[sensor_idx] : is_connected_mux2[sensor_idx];
      if (is_conn) {
        for (int s = 0; s < SAMPLES; s++) {
          tcaSelect(mux_addr, sensor_idx, bus);
          delay(2);
          if (sensor_array[sensor_idx].getEvent(event)) {
            temp_x += event->magnetic.x;
            temp_y += event->magnetic.y;
            temp_z += event->magnetic.z;
          }
          delay(10);
        }
        mag_offset_x[mux_idx][sensor_idx] = temp_x / SAMPLES;
        mag_offset_y[mux_idx][sensor_idx] = temp_y / SAMPLES;
        mag_offset_z[mux_idx][sensor_idx] = temp_z / SAMPLES;
      }
      Serial.print("."); // 진행 상황 표시
    }
  }
  Serial.println("\n--- Calibration Complete! ---");
  
  Serial.println("\nStarting Calibrated measurements for all 24 sensors.");
  Serial.println("SensorID,Calib_X,Calib_Y,Calib_Z");

  // 파이썬에게 데이터 전송 시작을 알리는 신호
  Serial.println("START");
}

void loop() {
  // MUX 0 (0x70) on Wire
  for (int i = 0; i < SENSORS_PER_MUX; i++) {
    Serial.print("S_70_" + String(i) + ",");
    if (is_connected_mux0[i]) {
      tcaSelect(muxAddress0, i, &Wire);
      if (sensors_mux0[i].getEvent(&event_mux0)) {
        float cal_x = event_mux0.magnetic.x - mag_offset_x[0][i];
        float cal_y = event_mux0.magnetic.y - mag_offset_y[0][i];
        float cal_z = event_mux0.magnetic.z - mag_offset_z[0][i];
        Serial.print(cal_x, 2); Serial.print(",");
        Serial.print(cal_y, 2); Serial.print(",");
        Serial.println(cal_z, 2);
      } else { Serial.println("R_FAIL,R_FAIL,R_FAIL"); }
    } else { Serial.println("FAIL,FAIL,FAIL"); }
  }

  // MUX 1 (0x71) on Wire1
  for (int i = 0; i < SENSORS_PER_MUX; i++) {
    Serial.print("S_71_" + String(i) + ",");
    if (is_connected_mux1[i]) {
      tcaSelect(muxAddress1, i, &Wire1);
      if (sensors_mux1[i].getEvent(&event_mux1)) {
        float cal_x = event_mux1.magnetic.x - mag_offset_x[1][i];
        float cal_y = event_mux1.magnetic.y - mag_offset_y[1][i];
        float cal_z = event_mux1.magnetic.z - mag_offset_z[1][i];
        Serial.print(cal_x, 2); Serial.print(",");
        Serial.print(cal_y, 2); Serial.print(",");
        Serial.println(cal_z, 2);
      } else { Serial.println("R_FAIL,R_FAIL,R_FAIL"); }
    } else { Serial.println("FAIL,FAIL,FAIL"); }
  }
  
  // MUX 2 (0x72) on Wire2
  for (int i = 0; i < SENSORS_PER_MUX; i++) {
    Serial.print("S_72_" + String(i) + ",");
    if (is_connected_mux2[i]) {
      tcaSelect(muxAddress2, i, &Wire2);
      if (sensors_mux2[i].getEvent(&event_mux2)) {
        float cal_x = event_mux2.magnetic.x - mag_offset_x[2][i];
        float cal_y = event_mux2.magnetic.y - mag_offset_y[2][i];
        float cal_z = event_mux2.magnetic.z - mag_offset_z[2][i];
        Serial.print(cal_x, 2); Serial.print(",");
        Serial.print(cal_y, 2); Serial.print(",");
        Serial.println(cal_z, 2);
      } else { Serial.println("R_FAIL,R_FAIL,R_FAIL"); }
    } else { Serial.println("FAIL,FAIL,FAIL"); }
  }
}