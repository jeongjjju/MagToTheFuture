# Jetson Nano I2C에서 MUX 및 HMC5883L 연결 확인용 코드
import smbus
import time

I2C_BUS = 1
MUX_ADDRESS = 0x70  # 기본 TCA9548A 주소
HMC5883L_ADDRESS = 0x1E  # HMC5883L 자기장 센서 주소

bus = smbus.SMBus(I2C_BUS)

def scan_mux_channels():
    print("[INFO] Scanning MUX channels for connected sensors...")
    for mux_channel in range(8):
        try:
            bus.write_byte(MUX_ADDRESS, 1 << mux_channel)
            time.sleep(0.05)
            devices = []
            for addr in range(0x03, 0x77):
                try:
                    bus.write_quick(addr)
                    devices.append(hex(addr))
                except:
                    continue
            print(f"MUX channel {mux_channel}: found devices -> {devices}")
        except Exception as e:
            print(f"MUX channel {mux_channel}: communication error - {e}")

if __name__ == "__main__":
    try:
        print("[INFO] Checking for MUX at address 0x70...")
        bus.write_byte(MUX_ADDRESS, 0x00)  # 단순히 write 동작 확인
        print("[OK] MUX detected at 0x70. Proceeding to scan channels.")
        scan_mux_channels()
    except Exception as e:
        print(f"[ERROR] MUX not found at address 0x70. I2C error: {e}")
