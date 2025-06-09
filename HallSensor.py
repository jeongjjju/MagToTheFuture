from smbus2 import SMBus
import time

# 각 MUX의 I2C 주소 (보통 0x70 ~ 0x77)
MUX_ADDRESSES = [0x70, 0x71, 0x72, 0x73]

# 각 MUX에 붙은 센서 채널 수
MUX_CHANNELS = 8

# 홀센서 I2C 주소 (예: QMC5883L = 0x0D, HMC5883L = 0x1E)
SENSOR_ADDRESS = 0x0D

# 사용할 I2C 버스 번호 (보통 Jetson에서는 /dev/i2c-1)
I2C_BUS = 1


def select_mux_channel(bus, mux_addr, channel):
    """
    TCA9548A MUX에서 특정 채널을 선택
    """
    if channel > 7:
        raise ValueError("MUX 채널은 0~7이어야 합니다.")
    bus.write_byte(mux_addr, 1 << channel)
    time.sleep(0.01)


def read_dummy_sensor(bus):
    """
    예시: 0x00 레지스터부터 6바이트 읽기 (센서 종류에 맞게 조정 필요)
    """
    try:
        data = bus.read_i2c_block_data(SENSOR_ADDRESS, 0x00, 6)
        return data
    except Exception as e:
        print(f"센서 읽기 실패: {e}")
        return None


def main():
    bus = SMBus(I2C_BUS)
    all_data = []

    for mux_index, mux_addr in enumerate(MUX_ADDRESSES):
        for channel in range(MUX_CHANNELS):
            sensor_index = mux_index * MUX_CHANNELS + channel
            if sensor_index >= 25:
                break

            try:
                select_mux_channel(bus, mux_addr, channel)
                sensor_data = read_dummy_sensor(bus)
                print(f"센서 {sensor_index:02d} @ MUX {mux_addr:#04x}, CH {channel}: {sensor_data}")
                all_data.append(sensor_data)
            except Exception as e:
                print(f"[에러] 센서 {sensor_index}: {e}")
                all_data.append(None)

    bus.close()


if __name__ == "__main__":
    main()
