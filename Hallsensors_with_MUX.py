# Jetson Nano + GY-85 (HMC5883L) 센서 실시간 데이터 수집 코드 (MUX 트리 구조 가정)
import smbus
import time

I2C_BUS = 1
MUX_ADDRESSES = [0x70, 0x71, 0x72, 0x73]  # 트리형 MUX 연결
HMC5883L_ADDR = 0x1E

bus = smbus.SMBus(I2C_BUS)

# MUX에서 특정 채널 선택
def select_mux_channel(mux_addr, channel):
    bus.write_byte(mux_addr, 1 << channel)
    time.sleep(0.01)

# HMC5883L 초기화
def init_hmc5883l():
    try:
        bus.write_byte_data(HMC5883L_ADDR, 0x00, 0x70)  # Config A
        bus.write_byte_data(HMC5883L_ADDR, 0x01, 0xA0)  # Config B
        bus.write_byte_data(HMC5883L_ADDR, 0x02, 0x00)  # Mode: continuous
    except Exception as e:
        print(f"[WARN] Sensor init error: {e}")

# 데이터 읽기
def read_hmc5883l():
    try:
        data = bus.read_i2c_block_data(HMC5883L_ADDR, 0x03, 6)
        x = data[0] << 8 | data[1]
        z = data[2] << 8 | data[3]
        y = data[4] << 8 | data[5]
        x = x - 65536 if x > 32767 else x
        y = y - 65536 if y > 32767 else y
        z = z - 65536 if z > 32767 else z
        return (x, y, z)
    except:
        return None

if __name__ == "__main__":
    print("[INFO] Starting GY-85 magnetometer polling loop...")
    try:
        while True:
            readings = []
            for mux_addr in MUX_ADDRESSES:
                for channel in range(7):  # 0~6까지는 센서
                    select_mux_channel(mux_addr, channel)
                    init_hmc5883l()
                    reading = read_hmc5883l()
                    readings.append(reading if reading else (None, None, None))
            print(readings)  # 28개 센서 값 (없으면 None)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("[INFO] Stopped polling loop.")