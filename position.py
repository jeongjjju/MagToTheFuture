import serial
import numpy as np
import time
import os
import threading
import sys

# --- 설정 ---
# Teensy가 연결된 COM 포트와 통신 속도를 설정합니다.
ARDUINO_PORT = 'COM9'  
BAUD_RATE = 1000000
TOTAL_SENSORS = 24

# --- 전역 변수 ---
# 추적할 패치 개수를 관리하는 변수
num_patches_to_track = 1
# 스레드 종료를 위한 이벤트
stop_event = threading.Event()

# --- 사용자 입력 처리 ---
def input_listener():
    """
    사용자가 Enter 키를 누르는 것을 감지하는 스레드 함수.
    """
    global num_patches_to_track
    while not stop_event.is_set():
        input() # Enter 키 입력을 기다림
        if num_patches_to_track < 3: # 최대 3개까지 추적
            num_patches_to_track += 1
            print(f"\n[Info] 추적할 패치 개수가 {num_patches_to_track}개로 변경되었습니다. 계속하려면 Enter를 누르세요.")
        else:
            print("\n[Info] 최대 3개까지만 추적할 수 있습니다.")

# --- 센서 물리적 위치 설정 ---
def initialize_sensor_positions():
    """
    사용자가 제공한 이미지 레이아웃에 따라 24개 센서의 물리적 (x, y) 좌표와
    센서 ID 레이아웃을 반환합니다.
    """
    positions = {}
    layout = [
        ['S_72_7', 'S_72_3', 'S_71_7', 'S_71_3', 'S_70_7', 'S_70_3'],
        ['S_72_6', 'S_72_2', 'S_71_6', 'S_71_2', 'S_70_6', 'S_70_2'],
        ['S_72_5', 'S_72_1', 'S_71_5', 'S_71_1', 'S_70_5', 'S_70_1'],
        ['S_72_4', 'S_72_0', 'S_71_4', 'S_71_0', 'S_70_4', 'S_70_0']
    ]
    return layout

# --- 데이터 처리 및 예측 ---
def parse_serial_data(line, total_sensors):
    """
    시리얼로 들어온 한 줄의 데이터를 파싱하여 센서 ID와 Z축 자기장 값을 딕셔너리로 반환합니다.
    """
    sensor_z_values = {}
    parts = line.strip().split(',')
    
    expected_length = total_sensors * 4
    if len(parts) != expected_length:
        return None

    for i in range(0, len(parts), 4):
        try:
            sensor_id = parts[i]
            z_val = float(parts[i+3])
            sensor_z_values[sensor_id] = z_val
        except (ValueError, IndexError):
            continue
            
    return sensor_z_values

def find_strongest_sensors(sensor_z_values, num_peaks, layout):
    """
    Z축 자기장 절대값이 가장 큰 센서들을 num_peaks 개수만큼 찾습니다.
    한 번 찾은 피크 주변의 센서들은 다음 검색에서 제외합니다.
    """
    if not sensor_z_values:
        return []

    peaks = []
    # 원본 데이터를 훼손하지 않기 위해 복사본 사용
    search_space = sensor_z_values.copy()

    for _ in range(num_peaks):
        if not search_space:
            break

        # 현재 탐색 공간에서 가장 강한 센서 찾기
        strongest_id = max(search_space, key=lambda k: abs(search_space[k]))
        peaks.append(strongest_id)

        # 찾은 센서와 그 주변 센서들을 다음 탐색 공간에서 제거
        # 1. 찾은 센서의 위치(row, col) 찾기
        peak_r, peak_c = -1, -1
        for r, row_data in enumerate(layout):
            if strongest_id in row_data:
                peak_r, peak_c = r, row_data.index(strongest_id)
                break
        
        # 2. 주변 센서 제거 (3x3 영역)
        if peak_r != -1:
            for r_offset in range(-1, 2):
                for c_offset in range(-1, 2):
                    r_idx, c_idx = peak_r + r_offset, peak_c + c_offset
                    if 0 <= r_idx < len(layout) and 0 <= c_idx < len(layout[0]):
                        sensor_to_remove = layout[r_idx][c_idx]
                        if sensor_to_remove in search_space:
                            del search_space[sensor_to_remove]
    return peaks

def display_grid(peak_sensors, layout, sensor_z_values):
    """
    감지된 피크들의 위치를 6x4 그리드에 숫자로 표시합니다.
    """
    os.system('cls' if os.name == 'nt' else 'clear')

    # 그리드에 표시할 내용을 담을 2D 배열 초기화
    grid_display = [['.' for _ in row] for row in layout]

    # 각 피크의 위치를 숫자로 표시
    for i, peak_id in enumerate(peak_sensors):
        for r, row_data in enumerate(layout):
            if peak_id in row_data:
                c = row_data.index(peak_id)
                grid_display[r][c] = str(i + 1)
                break
    
    # 그리드 출력
    print(f"--- Tracking {len(peak_sensors)} Patches ---")
    for r in range(len(layout)):
        row_str = "| " + " ".join(grid_display[r]) + " |"
        print(row_str)
    print("--------------------------")
    
    # 각 피크의 상세 정보 출력
    for i, peak_id in enumerate(peak_sensors):
        z_value = sensor_z_values.get(peak_id, 0)
        print(f"Patch {i+1}: {peak_id} (Z: {z_value:.2f} uT)")
    print("\nPress Enter to add another patch (max 3)...")


# --- 메인 실행 로직 ---
def main():
    layout = initialize_sensor_positions()
    
    # 사용자 입력을 받기 위한 스레드 시작
    listener = threading.Thread(target=input_listener, daemon=True)
    listener.start()
    
    try:
        ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
        print(f"{ARDUINO_PORT}에 연결되었습니다. Teensy 초기화 대기 중...")
    except serial.SerialException as e:
        print(f"오류: {ARDUINO_PORT}에 연결할 수 없습니다. 포트 번호를 확인하세요. 오류: {e}")
        return

    while not stop_event.is_set():
        try:
            line = ser.readline().decode('utf-8').strip()
            if line == "START":
                print("\nTeensy와 동기화 완료! 실시간 좌표 예측을 시작합니다.")
                break
        except UnicodeDecodeError:
            continue
    
    try:
        while not stop_event.is_set():
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', 'ignore').strip()
                
                if not line.startswith("S_"):
                    continue
                
                sensor_z_values = parse_serial_data(line, TOTAL_SENSORS)
                
                if sensor_z_values:
                    global num_patches_to_track
                    peak_ids = find_strongest_sensors(sensor_z_values, num_patches_to_track, layout)
                    display_grid(peak_ids, layout, sensor_z_values)

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 종료되었습니다.")
    finally:
        stop_event.set()
        ser.close()
        print("\n시리얼 포트 연결이 종료되었습니다.")


if __name__ == '__main__':
    main()
