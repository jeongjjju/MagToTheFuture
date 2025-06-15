import smbus
import time

bus = smbus.SMBus(1)  # Jetson Nano I2C-1
MUX_ADDR = 0x70       # 스캔할 MUX 주소만 바꿔서 사용 가능 (예: 0x70 ~ 0x73)

def select_mux_channel(channel):
    if channel < 0 or channel > 7:
        return
    bus.write_byte(MUX_ADDR, 1 << channel)
    time.sleep(0.01)

def is_device_present():
    for addr in range(0x03, 0x77):
        try:
            bus.write_quick(addr)
            return True  # 아무 장치든 응답이 있으면 연결된 것으로 간주
        except OSError:
            continue
    return False

print(f"[INFO] Checking device presence on MUX 0x{MUX_ADDR:02X}...")

for ch in range(8):
    select_mux_channel(ch)
    status = is_device_present()
    print(f"  CH{ch}: {'[CONNECTED]' if status else '[EMPTY]'}")

print("[DONE]")
