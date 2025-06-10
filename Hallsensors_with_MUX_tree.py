# GY-85 MUX 트리 구조 순차 탐색 코드 (재귀적 접근 방식)
import smbus
import time

I2C_BUS = 1
HMC5883L_ADDR = 0x1E
MUX_START_ADDR = 0x70  # 루트 MUX 주소
MUX_TREE_DEPTH = 4

bus = smbus.SMBus(I2C_BUS)

# MUX 채널 선택
def select_mux_channel(mux_addr, channel):
    bus.write_byte(mux_addr, 1 << channel)
    time.sleep(0.01)

# 센서 초기화
def init_hmc5883l():
    bus.write_byte_data(HMC5883L_ADDR, 0x00, 0x70)
    bus.write_byte_data(HMC5883L_ADDR, 0x01, 0xA0)
    bus.write_byte_data(HMC5883L_ADDR, 0x02, 0x00)

# 센서 읽기
def read_hmc5883l():
    data = bus.read_i2c_block_data(HMC5883L_ADDR, 0x03, 6)
    x = data[0] << 8 | data[1]
    z = data[2] << 8 | data[3]
    y = data[4] << 8 | data[5]
    x = x - 65536 if x > 32767 else x
    y = y - 65536 if y > 32767 else y
    z = z - 65536 if z > 32767 else z
    return (x, y, z)

# 재귀적으로 트리 순회하며 데이터 수집
def traverse_mux_tree(current_mux_addr, depth):
    results = []
    if depth > MUX_TREE_DEPTH:
        return results

    for ch in range(8):
        try:
            select_mux_channel(current_mux_addr, ch)
            if ch == 7:
                # 다음 MUX로 진입
                next_mux_addr = current_mux_addr + 1
                results.extend(traverse_mux_tree(next_mux_addr, depth + 1))
            else:
                try:
                    init_hmc5883l()
                    data = read_hmc5883l()
                    results.append(data)
                except:
                    results.append((None, None, None))
        except:
            results.append((None, None, None))
    return results

if __name__ == "__main__":
    print("[INFO] Starting recursive MUX polling loop...")
    try:
        while True:
            data = traverse_mux_tree(MUX_START_ADDR, 1)
            print(data)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("[INFO] Stopped.")
