import serial
import os
import time
from collections import deque

# --- 설정 및 변수 선언 (이전과 동일) ---
SERIAL_PORT = 'COM9'
BAUD_RATE = 1000000
NUM_ROWS = 4
NUM_COLS = 6
# ... (이하 모든 설정 및 변수 선언은 이전 코드와 동일) ...
sensor_layout = [
    ['S_72_7', 'S_72_3', 'S_71_7', 'S_71_3', 'S_70_7', 'S_70_3'],
    ['S_72_6', 'S_72_2', 'S_71_6', 'S_71_2', 'S_70_6', 'S_70_2'],
    ['S_72_5', 'S_72_1', 'S_71_5', 'S_71_1', 'S_70_5', 'S_70_1'],
    ['S_72_4', 'S_72_0', 'S_71_4', 'S_71_0', 'S_70_4', 'S_70_0']
]
sensor_ids_ordered = []
for mux_addr in [0x70, 0x71, 0x72]:
    for i in range(8):
        sensor_ids_ordered.append(f"S_{hex(mux_addr)[2:]}_{i}")
latest_z_values = {sensor_id: 0.0 for sensor_id in sensor_ids_ordered}

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
# --------------------------------------------------

# --- 시리얼 포트 연결 ---
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    ser.flushInput()
    time.sleep(2) 
    print(f"성공: {SERIAL_PORT} 포트에 연결되었습니다.")
except serial.SerialException as e:
    print(f"오류: {SERIAL_PORT} 포트를 열 수 없습니다. 포트 번호를 확인하거나 다른 프로그램이 사용 중인지 확인하세요.")
    print(e)
    exit()

# ▼▼▼ [수정된 부분] Teensy가 준비될 때까지 대기하는 코드 ▼▼▼
print("\nTeensy의 준비 신호를 기다리는 중...")
print("보드 리셋 시 캘리브레이션이 진행됩니다. 잠시 기다려주세요...")
while True:
    try:
        line = ser.readline().decode('utf-8').strip()
        if line: # 빈 줄이 아니면 Teensy가 보내는 메시지를 그대로 출력
            print(f"Teensy: {line}")
        if line == "START":
            print("\n>>> 시작 신호 수신! 실시간 모니터링을 시작합니다. <<<")
            time.sleep(1) # 메시지를 읽을 시간을 줌
            break # 대기 루프 탈출
    except UnicodeDecodeError:
        pass # 가끔 발생하는 통신 오류는 무시
# --------------------------------------------------


# --- 메인 루프 (이전과 동일) ---
try:
    while True:
        try:
            line = ser.readline().decode('utf-8').strip()
            if line:
                parts = line.split(',')
                if len(parts) == 4 and parts[0] in sensor_ids_ordered:
                    sensor_id, _, _, z_val = parts # Z값만 사용
                    latest_z_values[sensor_id] = float(z_val)
        except (UnicodeDecodeError):
            print("데이터 수신 오류 발생. 건너뜁니다.")
            continue
        except Exception as e:
            print(f"알 수 없는 오류 발생: {e}")
            continue

        clear_screen()
        
        print("--- 24-Channel Real-time Sensor Values (Z-axis) ---")
        print(f"업데이트 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("----------------------------------------------------")
        
        for r in range(NUM_ROWS):
            row_str = ""
            for c in range(NUM_COLS):
                sensor_id = sensor_layout[r][c]
                z_value = latest_z_values[sensor_id]
                row_str += f"{z_value:10.2f}"
            print(row_str)
        
        print("----------------------------------------------------")
        print("종료하려면 Ctrl+C를 누르세요.")
        
except KeyboardInterrupt:
    print("\n프로그램을 종료합니다.")
finally:
    ser.close()
    print(f"{SERIAL_PORT} 포트를 닫았습니다.")