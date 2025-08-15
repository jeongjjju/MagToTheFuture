import serial
import numpy as np
import openvr
import pandas as pd
from datetime import datetime
import time
import os
import threading
import queue
import msvcrt

# --- 설정 ---
ARDUINO_PORT = 'COM9' # Teensy COM port
BAUD_RATE = 1000000
MAX_RECORDS = 100000 # 미리 할당할 데이터 행의 최대 개수

# --- 스레드 간 데이터 공유 및 제어 ---
data_queue = queue.Queue()
stop_thread = threading.Event()
start_data_collection = threading.Event()

# User input states
record_geometry_mode = False

# --- 헬퍼 함수 ---
def serial_reader_optimized(ser, q, stop_event):
    """
    최적화된 시리얼 리더 스레드 함수. 한 번에 대량의 데이터를 읽어 I/O 오버헤드를 줄입니다.
    """
    print("최적화된 시리얼 리더 스레드 시작.")
    buffer = b''
    while not stop_event.is_set():
        try:
            if ser.in_waiting > 0:
                buffer += ser.read(ser.in_waiting)
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if line:
                        q.put(line.decode('utf-8', 'ignore').strip())
        except (serial.SerialException, TypeError):
            break
        
        time.sleep(0.0001)
    print("최적화된 시리얼 리더 스레드 종료.")

def input_listener_non_blocking():
    """
    데이터 수집 중 'g'를 눌러 지오메트리 기록 모드를 시작합니다.
    """
    global record_geometry_mode
    global start_data_collection
    
    while not stop_thread.is_set():
        if msvcrt.kbhit():
            key = msvcrt.getch().decode('utf-8')
            if key == 'g':
                print("\n\n--- 지오메트리 기록 모드 활성화. 데이터 수집이 잠시 중단됩니다. ---")
                start_data_collection.clear() # 데이터 수집 중단
                record_geometry_mode = True
                
        time.sleep(0.1)

def get_tracker_pose():
    """
    하나의 VIVE 트래커의 현재 위치 및 회전 행렬을 반환합니다.
    """
    poses = vr_system.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount)
    if tracker_id is not None and poses[tracker_id].bPoseIsValid:
        matrix = poses[tracker_id].mDeviceToAbsoluteTracking
        pos = [matrix[0][3], matrix[1][3], matrix[2][3]]
        return pos, matrix
    return None, None

def get_euler_angles_from_matrix(m):
    """회전 행렬에서 Roll, Pitch, Yaw 오일러 각도를 계산합니다."""
    yaw = np.degrees(np.arctan2(m[1][0], m[0][0]))
    pitch = np.degrees(np.arctan2(-m[2][0], np.sqrt(m[2][1]**2 + m[2][2]**2)))
    roll = np.degrees(np.arctan2(m[2][1], m[2][2]))
    return roll, pitch, yaw
    
def get_quaternion_from_matrix(m):
    """회전 행렬에서 쿼터니언(x, y, z, w)을 계산합니다."""
    trace = m[0][0] + m[1][1] + m[2][2]
    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (m[2][1] - m[1][2]) * s
        y = (m[0][2] - m[2][0]) * s
        z = (m[1][0] - m[0][1]) * s
    else:
        if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
            s = 2.0 * np.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2])
            w = (m[2][1] - m[1][2]) / s
            x = 0.25 * s
            y = (m[0][1] + m[1][0]) / s
            z = (m[0][2] + m[2][0]) / s
        elif m[1][1] > m[2][2]:
            s = 2.0 * np.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2])
            w = (m[0][2] - m[2][0]) / s
            x = (m[0][1] + m[1][0]) / s
            y = 0.25 * s
            z = (m[1][2] + m[2][1]) / s
        else:
            s = 2.0 * np.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1])
            w = (m[1][0] - m[0][1]) / s
            x = (m[0][2] + m[2][0]) / s
            y = (m[1][2] + m[2][1]) / s
            z = 0.25 * s
    return [x, y, z, w]

def record_area_points(tracker_id, area_label, geom_data_list):
    """지정된 트래커를 사용하여 에리어의 꼭짓점 위치를 기록합니다."""
    print(f"\n>>> 트래커 {tracker_id}를 사용하여 '{area_label}'의 꼭짓점을 기록합니다.")
    for i in range(1, 5):
        input(f"    - 트래커를 '{area_label} Corner_{i}' 위치에 놓고 Enter를 누르세요...")
        pos, _ = get_tracker_pose()
        if pos:
            print(f"      - 기록 완료: (X={pos[0]:.4f}, Y={pos[1]:.4f}, Z={pos[2]:.4f})")
            geom_data_list.append({
                'tracker_id': tracker_id, 
                'area_label': area_label, 
                'corner': f'Corner_{i}', 
                'pos_x': pos[0], 
                'pos_y': pos[1], 
                'pos_z': pos[2]
            })
        else:
            print("      - 오류: 트래커 위치를 읽을 수 없습니다. 건너뜁니다.")
    print(f"\n--- '{area_label}' 기록 완료! ---")

def save_to_csv(data_array, col_order, num_records, geom_data):
    """수집된 데이터를 CSV 파일로 저장합니다."""
    if len(geom_data) > 0:
        print("\n고정 좌표(geometry) 데이터 저장 중...")
        df_geom = pd.DataFrame(geom_data)
        geom_filename = f"device_geometry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_geom.to_csv(geom_filename, index=False)
        print(f"'{geom_filename}' 파일이 저장되었습니다.")

    if num_records > 0:
        print("\n실시간 수집 데이터 저장 중...")
        df_ts = pd.DataFrame(data_array[:num_records], columns=col_order)
        ts_filename = f"training_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_ts.to_csv(ts_filename, index=False)
        print(f"'{ts_filename}' 파일에 총 {num_records}개의 시간대 데이터가 저장되었습니다.")

# --- OpenVR 및 시리얼 포트 초기화 ---
try:
    print("OpenVR 초기화 시도..."); vr_system = openvr.init(openvr.VRApplication_Other)
    ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=0.1)
except Exception as e: 
    print(f"오류: 초기화 실패. 에러: {e}"); exit()

tracker_id = None
for i in range(openvr.k_unMaxTrackedDeviceCount):
    if vr_system.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_GenericTracker:
        tracker_id = i
        print(f"VIVE 트래커를 찾았습니다. 장치 ID: {tracker_id}")
        break
if tracker_id is None:
    print("오류: VIVE 트래커를 찾을 수 없습니다. 종료합니다."); ser.close(); openvr.shutdown(); exit()

# --- 데이터 구조 정의 ---
column_order = [
    'timestamp', 
    'tracker_pos_x', 'tracker_pos_y', 'tracker_pos_z',
    'tracker_rot_roll', 'tracker_rot_pitch', 'tracker_rot_yaw',
    'tracker_rot_quat_x', 'tracker_rot_quat_y', 'tracker_rot_quat_z', 'tracker_rot_quat_w',
    'sensor_x', 'sensor_y', 'sensor_z'
]

time_series_data_array = np.zeros((MAX_RECORDS, len(column_order)))
record_index = 0

# --- 메인 실행 로직 ---
reader_thread = None
input_thread = None
geometry_data = []

try:
    print("\n--- Teensy 동기화 대기 중 ---")
    while True:
        line = ser.readline().decode('utf-8', 'ignore').strip()
        if line == "START":
            print("--- ✅ 동기화 완료! 'g'를 눌러 꼭짓점 기록 시작, 'Ctrl+C'로 종료 ---")
            break

    reader_thread = threading.Thread(target=serial_reader_optimized, args=(ser, data_queue, stop_thread))
    reader_thread.start()
    input_thread = threading.Thread(target=input_listener_non_blocking, daemon=True)
    input_thread.start()
    
    start_data_collection.set()

    while not stop_thread.is_set():
        if record_geometry_mode:
            record_area_points(tracker_id, "Patch_1_Corners", geometry_data)
            record_geometry_mode = False
            start_data_collection.set()
            print("\n--- 꼭짓점 기록 완료. 다시 데이터 수집을 시작합니다. ---")
            
        if not start_data_collection.is_set():
            time.sleep(0.1)
            continue
            
        if record_index >= MAX_RECORDS:
            print("\n최대 기록 개수에 도달하여 수집을 중단합니다.")
            stop_thread.set()
            break
        
        try:
            line = data_queue.get_nowait()
        except queue.Empty:
            time.sleep(0.001)
            continue

        if not line.startswith("S_71_2"):
            continue
            
        parts = line.split(',')
        if len(parts) != 4: 
            continue

        sensor_id, cx_str, cy_str, cz_str = parts
        try:
            sensor_x = float(cx_str)
            sensor_y = float(cy_str)
            sensor_z = float(cz_str)
        except ValueError:
            sensor_x, sensor_y, sensor_z = 0.0, 0.0, 0.0

        pos, matrix = get_tracker_pose()
        
        status_line = f"데이터 수집 중... [{record_index + 1}/{MAX_RECORDS}] | 트래커: {'OK' if pos else 'N/A'}"
        print(status_line, end='\r')
        
        if pos:
            roll, pitch, yaw = get_euler_angles_from_matrix(matrix)
            quaternion = get_quaternion_from_matrix(matrix)
            
            row_data = [
                time.time(), 
                pos[0], pos[1], pos[2], 
                roll, pitch, yaw,
                quaternion[0], quaternion[1], quaternion[2], quaternion[3],
                sensor_x, sensor_y, sensor_z
            ]
            
            time_series_data_array[record_index] = row_data
            record_index += 1
    
except KeyboardInterrupt:
    print("\n\n프로그램이 사용자에 의해 강제 중단되었습니다.")
finally:
    stop_thread.set()
    if reader_thread:
        reader_thread.join()
    if input_thread:
        input_thread.join()
    
    save_to_csv(time_series_data_array, column_order, record_index, geometry_data)
    
    ser.close()
    if 'vr_system' in locals() and vr_system is not None:
        openvr.shutdown()
    print("시리얼 포트와 OpenVR을 종료했습니다.")
