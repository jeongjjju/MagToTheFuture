#include <Wire.h>
#include <Adafruit_MLX90393.h>
#include <Adafruit_Sensor.h>

// --- Configuration ---
const byte muxAddress = 0x71; // I2C address of the multiplexer
const int sensorChannel = 2;  // Channel number of the sensor
const long SERIAL_SPEED = 1000000;

// Sensor objects
Adafruit_MLX90393 sensor;
sensors_event_t event;
bool is_connected = false;

// --- Helper Function ---
void tcaSelect(byte muxAddress, uint8_t channel, TwoWire *bus) {
  if (channel > 7) return;
  bus->beginTransmission(muxAddress);
  bus->write(1 << channel);
  bus->endTransmission();
}

void setup() {
  Serial.begin(SERIAL_SPEED);
  while (!Serial) {}

  Wire.begin();
  Wire.setClock(1000000L);

  // Initialize the single sensor
  tcaSelect(muxAddress, sensorChannel, &Wire);
  is_connected = sensor.begin_I2C(0x18, &Wire);
  if (is_connected) {
    sensor.setGain(MLX90393_GAIN_1_33X);
  }

  Serial.println("START");
}

void loop() {
  char buffer[128];

  if (is_connected) {
    tcaSelect(muxAddress, sensorChannel, &Wire);
    if (sensor.getEvent(&event)) {
      sprintf(buffer, "S_71_2,%.2f,%.2f,%.2f", event.magnetic.x, event.magnetic.y, event.magnetic.z);
    } else {
      sprintf(buffer, "S_71_2,R_FAIL,R_FAIL,R_FAIL");
    }
  } else {
    sprintf(buffer, "S_71_2,FAIL,FAIL,FAIL");
  }
  Serial.println(buffer);
}
