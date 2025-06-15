import smbus
import time

bus = smbus.SMBus(1)  # Jetson Nano의 I2C-1 버스 사용
mux_addresses = [0x70, 0x71, 0x72, 0x73]

def select_mux_channel(mux_addr, channel):
    bus.write_byte(mux_addr, 1 << channel)
    time.sleep(0.01)

def scan_mux_channel(mux_addr, channel):
    select_mux_channel(mux_addr, channel)
    print(f"[SCAN] MUX 0x{mux_addr:02X} CH{channel}:")
    found = False
    for addr in range(0x03, 0x77):
        try:
            bus.write_quick(addr)
            print(f"  → Found device at 0x{addr:02X}")
            found = True
        except OSError:
            continue
    if not found:
        print("  (none)")

print("[INFO] Starting Jetson Nano I2C MUX scan...")
for mux in mux_addresses:
    for ch in range(8):
        try:
            scan_mux_channel(mux, ch)
        except Exception as e:
            print(f"[ERROR] MUX 0x{mux:02X} CH{ch}: {e}")
print("[DONE]")
