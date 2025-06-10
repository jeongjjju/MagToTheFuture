# 디버깅용: GY-85 MUX 트리 구조에서 MUX 선택 경로를 추적하며 데이터 수집
import smbus
import time

I2C_BUS = 1
HMC5883L_ADDR = 0x1E
MUX_START_ADDR = 0x70
MUX_TREE_DEPTH = 4

bus = smbus.SMBus(I2C_BUS)

def select_mux_channel(mux_addr, channel):
    print(f"[MUX] Selecting MUX 0x{mux_addr:02X} channel {channel}")
    bus.write_byte(mux_addr, 1 << channel)
    time.sleep(0.01)

def init_hmc5883l():
    bus.write_byte_data(HMC5883L_ADDR, 0x00, 0x70)
    bus.write_byte_data(HMC5883L_ADDR, 0x01, 0xA0)
    bus.write_byte_data(HMC5883L_ADDR, 0x02, 0x00)

def read_hmc5883l():
    data = bus.read_i2c_block_data(HMC5883L_ADDR, 0x03, 6)
    x = data[0] << 8 | data[1]
    z = data[2] << 8 | data[3]
    y = data[4] << 8 | data[5]
    x = x - 65536 if x > 32767 else x
    y = y - 65536 if y > 32767 else y
    z = z - 65536 if z > 32767 else z
    return (x, y, z)

def traverse_mux_tree(current_mux_addr, depth):
    results = []
    if depth > MUX_TREE_DEPTH:
        return results

    for ch in range(8):
        try:
            select_mux_channel(current_mux_addr, ch)
            if ch == 7:
                next_mux_addr = current_mux_addr + 1
                print(f"[MUX] Descending to next MUX at 0x{next_mux_addr:02X}")
                results.extend(traverse_mux_tree(next_mux_addr, depth + 1))
            else:
                try:
                    print(f"[SENSOR] Trying sensor at MUX 0x{current_mux_addr:02X} CH{ch}")
                    init_hmc5883l()
                    data = read_hmc5883l()
                    results.append(data)
                    print(f"[SENSOR] Success: {data}")
                except Exception as e:
                    print(f"[SENSOR] Fail: {e}")
                    results.append((None, None, None))
        except Exception as e:
            print(f"[MUX] Channel select fail: {e}")
            results.append((None, None, None))
    return results

if __name__ == "__main__":
    print("[INFO] Starting recursive MUX polling with trace...")
    try:
        while True:
            data = traverse_mux_tree(MUX_START_ADDR, 1)
            print("[RESULT]", data)
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("[INFO] Stopped.")
