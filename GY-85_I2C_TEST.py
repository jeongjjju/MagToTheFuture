# GY-85 I2C 테스트 코드 (Jetson Nano)
# GY-85 = ADXL345 (0x53), ITG3200 (0x68), HMC5883L (0x1E)
# 이 코드는 연결 여부를 확인하기 위한 간단한 디바이스 탐지 및 읽기 코드입니다.

from smbus2 import SMBus
import time

bus = SMBus(1)

DEVICES = {
    0x53: "ADXL345 (3축 가속도계)",
    0x68: "ITG3200 (자이로스코프)",
    0x1E: "HMC5883L (지자기 센서)"
}

print("[I2C GY-85 센서 확인]")
for addr, name in DEVICES.items():
    try:
        bus.write_quick(addr)
        print(f"✅ {name} 감지됨 @ 0x{addr:02X}")
    except:
        print(f"❌ {name} 없음 또는 응답 없음 @ 0x{addr:02X}")

print("\n[간단한 데이터 읽기 - ADXL345]")
try:
    bus.write_byte_data(0x53, 0x2D, 0x08)  # 측정 모드 활성화
    time.sleep(0.1)
    data = bus.read_i2c_block_data(0x53, 0x32, 6)  # X/Y/Z 2바이트씩
    x = int.from_bytes(data[0:2], byteorder='little', signed=True)
    y = int.from_bytes(data[2:4], byteorder='little', signed=True)
    z = int.from_bytes(data[4:6], byteorder='little', signed=True)
    print(f"가속도 X:{x}, Y:{y}, Z:{z}")
except Exception as e:
    print(f"ADXL345 데이터 읽기 실패: {e}")

bus.close()
