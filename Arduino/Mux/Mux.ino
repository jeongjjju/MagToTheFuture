#include <Wire.h>
#include <Adafruit_MLX90393.h>
#include <Adafruit_Sensor.h>

// I2C 멀티플렉서 설정
const int SENSORS_PER_MUX = 8;
const byte muxAddresses[] = {0x70, 0x71, 0x72};
const int NUM_MUXES = sizeof(muxAddresses) / sizeof(muxAddresses[0]);

// 센서 배열과 연결 상태 배열
Adafruit_MLX90393 sensors[NUM_MUXES][SENSORS_PER_MUX];
bool is_connected[NUM_MUXES][SENSORS_PER_MUX];
sensors_event_t event;

// 시리얼 통신 속도
const long SERIAL_SPEED = 1000000;

// 모든 센서 데이터를 담을 버퍼 (넉넉하게 1024 바이트 할당)
char dataBuffer[1024];

/**
 * @brief TCA9548A 멀티플렉서 채널 선택
 * @param muxAddress 멀티플렉서의 I2C 주소
 * @param channel 선택할 채널 번호 (0-7)
 * @param bus 사용할 TwoWire 인스턴스 (Wire, Wire1, Wire2 등)
 */
void tcaSelect(byte muxAddress, uint8_t channel, TwoWire *bus) {
    if (channel > 7) return;
    bus->beginTransmission(muxAddress);
    bus->write(1 << channel);
    bus->endTransmission();
}

/**
 * @brief 하나의 멀티플렉서에 연결된 모든 센서를 읽고 버퍼에 추가
 * @param muxIndex 멀티플렉서 인덱스 (0, 1, 2)
 * @param bus 사용할 TwoWire 인스턴스
 */
void readMuxSensors(int muxIndex, TwoWire *bus) {
    char tempBuffer[64]; // 한 센서 데이터를 위한 임시 버퍼

    for (int i = 0; i < SENSORS_PER_MUX; i++) {
        if (is_connected[muxIndex][i]) {
            tcaSelect(muxAddresses[muxIndex], i, bus);
            if (sensors[muxIndex][i].getEvent(&event)) {
                // snprintf를 사용하여 버퍼 끝에 데이터를 추가
                snprintf(tempBuffer, sizeof(tempBuffer), ",S_%x_%d,%.2f,%.2f,%.2f", 
                         muxAddresses[muxIndex], i, event.magnetic.x, event.magnetic.y, event.magnetic.z);
            } else {
                snprintf(tempBuffer, sizeof(tempBuffer), ",S_%x_%d,R_FAIL,R_FAIL,R_FAIL", 
                         muxAddresses[muxIndex], i);
            }
        } else {
            snprintf(tempBuffer, sizeof(tempBuffer), ",S_%x_%d,FAIL,FAIL,FAIL", 
                     muxAddresses[muxIndex], i);
        }
        strcat(dataBuffer, tempBuffer);
    }
}

void setup() {
    Serial.begin(SERIAL_SPEED);
    while (!Serial) {}

    Wire.begin();
    Wire1.begin();
    Wire2.begin();

    // I2C 클럭 속도 설정
    Wire.setClock(1000000L);
    Wire1.setClock(1000000L);
    Wire2.setClock(1000000L);

    // 모든 멀티플렉서와 센서 초기화
    for (int j = 0; j < NUM_MUXES; j++) {
        TwoWire* bus = (j == 0) ? &Wire : (j == 1) ? &Wire1 : &Wire2;
        for (int i = 0; i < SENSORS_PER_MUX; i++) {
            tcaSelect(muxAddresses[j], i, bus);
            is_connected[j][i] = sensors[j][i].begin_I2C(0x18, bus);
            if (is_connected[j][i]) {
                sensors[j][i].setGain(MLX90393_GAIN_1_33X);
            }
        }
    }

    Serial.println("START");
}

void loop() {
    // 버퍼 초기화
    dataBuffer[0] = '\0';
    
    // 첫 센서 데이터는 앞에 콤마가 없도록 별도로 처리
    if (is_connected[0][0]) {
        tcaSelect(muxAddresses[0], 0, &Wire);
        if (sensors[0][0].getEvent(&event)) {
            snprintf(dataBuffer, sizeof(dataBuffer), "S_%x_%d,%.2f,%.2f,%.2f", 
                     muxAddresses[0], 0, event.magnetic.x, event.magnetic.y, event.magnetic.z);
        } else {
            snprintf(dataBuffer, sizeof(dataBuffer), "S_%x_%d,R_FAIL,R_FAIL,R_FAIL", 
                     muxAddresses[0], 0);
        }
    } else {
        snprintf(dataBuffer, sizeof(dataBuffer), "S_%x_%d,FAIL,FAIL,FAIL", 
                 muxAddresses[0], 0);
    }

    // 나머지 센서 데이터를 버퍼에 추가
    for (int j = 0; j < NUM_MUXES; j++) {
        TwoWire* bus = (j == 0) ? &Wire : (j == 1) ? &Wire1 : &Wire2;
        int start_channel = (j == 0) ? 1 : 0; // 첫 번째 MUX의 첫 채널은 이미 처리됨
        for (int i = start_channel; i < SENSORS_PER_MUX; i++) {
            if (is_connected[j][i]) {
                tcaSelect(muxAddresses[j], i, bus);
                if (sensors[j][i].getEvent(&event)) {
                    snprintf(dataBuffer + strlen(dataBuffer), sizeof(dataBuffer) - strlen(dataBuffer), ",S_%x_%d,%.2f,%.2f,%.2f", 
                             muxAddresses[j], i, event.magnetic.x, event.magnetic.y, event.magnetic.z);
                } else {
                    snprintf(dataBuffer + strlen(dataBuffer), sizeof(dataBuffer) - strlen(dataBuffer), ",S_%x_%d,R_FAIL,R_FAIL,R_FAIL", 
                             muxAddresses[j], i);
                }
            } else {
                snprintf(dataBuffer + strlen(dataBuffer), sizeof(dataBuffer) - strlen(dataBuffer), ",S_%x_%d,FAIL,FAIL,FAIL", 
                         muxAddresses[j], i);
            }
        }
    }

    Serial.println(dataBuffer);
}
