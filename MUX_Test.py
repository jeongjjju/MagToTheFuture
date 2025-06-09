# Jetson Nano에서 여러 개의 TCA9548A MUX를 사용하는 경우 스캔 코드
import smbus
import time

I2C_BUS = 1
MUX_ADDRESSES = [0x70, 0x71, 0x72, 0x73]  # 총 4개의 MUX가 각각 주소를 가짐

bus = smbus.SMBus(I2C_BUS)

def scan_all_muxes():
    print("[INFO] Scanning all MUX chips and channels...")
    for mux_addr in MUX_ADDRESSES:
        print(f"\n[INFO] Checking MUX at address 0x{mux_addr:02X}...")
        try:
            bus.write_byte(mux_addr, 0x00)
            print(f"[OK] MUX detected at 0x{mux_addr:02X}")
            for channel in range(8):
                try:
                    bus.write_byte(mux_addr, 1 << channel)
                    time.sleep(0.05)
                    found_devices = []
                    for addr in range(0x03, 0x77):
                        try:
                            bus.read_byte(addr)
                            found_devices.append(hex(addr))
                        except:
                            continue
                    print(f"  Channel {channel}: found devices -> {found_devices}")
                except Exception as e:
                    print(f"  Channel {channel}: error - {e}")
        except Exception as e:
            print(f"[ERROR] Cannot communicate with MUX at 0x{mux_addr:02X}: {e}")

if __name__ == "__main__":
    scan_all_muxes()
