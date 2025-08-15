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
ARDUINO_PORT = 'COM9'
BAUD_RATE = 1000000
TOTAL_SENSORS = 24
MAX_RECORDS = 100000
NUM_TRACKERS = 2

# --- 스레드 간 데이터 공유 및 제어 ---
data_queue = queue.Queue()
stop_thread = threading.Event()
start_data_collection = threading.Event()

# User input states
patch1_inference_enabled = False
patch2_inference_enabled = False
patch1_area_id = 0
patch2_area_id = 0

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
    데이터 수집 중 'g'를 눌러 지오메트리 모드를 시작하거나, 'o'로 추론 상태를 토글합니다.
    """
    global patch1_inference_enabled, patch2_inference_enabled
    global start_data_collection
    
    while not stop_thread.is_set():
        if msvcrt.kbhit():
            key = msvcrt.getch().decode('utf-8')
            if key == 'o':
                patch1_inference_enabled = not patch1_inference_enabled
                patch2_inference_enabled = not patch2_inference_enabled
                print(f"\n--- 추론 상태 토글: 패치 1: {patch1_inference_enabled}, 패치 2: {patch2_inference_enabled} ---")
            elif key == 'g':
                print("\n\n--- 지오메트리 기록 모드 활성화. 데이터 수집이 잠시 중단됩니다. ---")
                start_data_collection.clear() # 데이터 수집 중단
        time.sleep(0.1)

def get_tracker_poses(tracker_ids):
    """
    여러 VIVE 트래커의 현재 위치 및 회전 행렬을 반환합니다.
    """
    poses = vr_system.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount)
    tracker_data = {}
    for tracker_id in tracker_ids:
        if poses[tracker_id].bPoseIsValid:
            matrix = poses[tracker_id].mDeviceToAbsoluteTracking
            pos = [matrix[0][3], matrix[1][3], matrix[2][3]]
            tracker_data[tracker_id] = {'pos': pos, 'matrix': matrix}
    return tracker_data

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
        poses = get_tracker_poses([tracker_id])
        pos = poses.get(tracker_id, {}).get('pos')
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

def handle_geometry_recording(tracker_ids, geometry_data):
    """
    사용자 입력을 받아 영역 ID를 지정하고 꼭짓점 좌표를 기록하는 함수.
    """
    global patch1_area_id, patch2_area_id, start_data_collection
    
    print("\n\n--- 지오메트리 기록 모드 ---")
    current_patch_index = 0
    
    while True:
        try:
            tracker_id_to_use = tracker_ids[current_patch_index]
            patch_label = f"패치 {current_patch_index + 1}"
            
            prompt = f"\n>>> [{patch_label}] 영역을 지정하세요 (1-9 입력) 또는 꼭짓점 기록 (Enter), 종료 (q): "
            user_input = input(prompt).strip()
            
            if user_input.lower() == 'q':
                break
            
            if user_input.isdigit() and 1 <= int(user_input) <= 9:
                area_id = int(user_input)
                if current_patch_index == 0:
                    patch1_area_id = area_id
                    print(f"[{patch_label}] 영역 ID: {area_id} 기록")
                else:
                    patch2_area_id = area_id
                    print(f"[{patch_label}] 영역 ID: {area_id} 기록")
                
                # 다음 패치로 순환
                current_patch_index = (current_patch_index + 1) % NUM_TRACKERS
            
            elif user_input == '': # Enter 키 입력
                print("\n--- 꼭짓점 기록 모드 시작 ---")
                record_area_points(tracker_ids[0], "Patch_1_Corners", geometry_data)
                
            else:
                print("잘못된 입력입니다. 1-9 사이의 숫자, Enter, 또는 'q'를 입력하세요.")
        
        except KeyboardInterrupt:
            print("\n지오메트리 기록이 중단됩니다.")
            break
    
    print("\n--- 지오메트리 모드 종료 ---")
    start_data_collection.set() # 데이터 수집 재개

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

tracker_ids = []
for i in range(openvr.k_unMaxTrackedDeviceCount):
    if vr_system.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_GenericTracker:
        tracker_ids.append(i)
        if len(tracker_ids) == NUM_TRACKERS:
            break
if len(tracker_ids) < NUM_TRACKERS:
    print(f"오류: {NUM_TRACKERS}개의 VIVE 트래커가 필요하지만, {len(tracker_ids)}개만 찾았습니다. 종료합니다."); ser.close(); openvr.shutdown(); exit()
print(f"VIVE 트래커를 찾았습니다. 장치 ID: {tracker_ids}")

# --- 데이터 구조 정의 ---
column_order = ['timestamp', 'patch1_area_id', 'patch2_area_id', 'patch1_inference_enabled', 'patch2_inference_enabled']
for i in range(NUM_TRACKERS):
    column_order.extend([
        f'tracker{i+1}_pos_x', f'tracker{i+1}_pos_y', f'tracker{i+1}_pos_z',
        f'tracker{i+1}_rot_roll', f'tracker{i+1}_rot_pitch', f'tracker{i+1}_rot_yaw',
        f'tracker{i+1}_rot_quat_x', f'tracker{i+1}_rot_quat_y', f'tracker{i+1}_rot_quat_z', f'tracker{i+1}_rot_quat_w'
    ])

sensor_column_names = []
sensor_ids_ordered = []
for i in range(TOTAL_SENSORS):
    mux_addr, channel = 0x70 + (i // 8), i % 8
    sid = f"S_{mux_addr:x}_{channel}"
    sensor_ids_ordered.append(sid)
    sensor_column_names.extend([f'{sid}_x', f'{sid}_y', f'{sid}_z'])
column_order.extend(sensor_column_names)

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
            print("--- ✅ 동기화 완료! 'g'를 눌러 지오메트리 모드 시작, 'o'로 추론 상태 토글, 'Ctrl+C'로 종료 ---")
            break

    reader_thread = threading.Thread(target=serial_reader_optimized, args=(ser, data_queue, stop_thread))
    reader_thread.start()
    input_thread = threading.Thread(target=input_listener_non_blocking, daemon=True)
    input_thread.start()
    
    start_data_collection.set()

    while not stop_thread.is_set():
        if not start_data_collection.is_set():
            handle_geometry_recording(tracker_ids, geometry_data)
            
        if record_index >= MAX_RECORDS:
            print("\n최대 기록 개수에 도달하여 수집을 중단합니다.")
            stop_thread.set()
            break
        
        try:
            line = data_queue.get_nowait()
        except queue.Empty:
            time.sleep(0.001)
            continue

        if not line.startswith("S_"):
            continue
            
        parts = line.split(',')
        if len(parts) != TOTAL_SENSORS * 4: 
            continue

        temp_sensor_readings = {}
        for i in range(0, len(parts), 4):
            sensor_id, cx_str, cy_str, cz_str = parts[i:i+4]
            try:
                temp_sensor_readings[sensor_id] = {'x': float(cx_str), 'y': float(cy_str), 'z': float(cz_str)}
            except ValueError:
                temp_sensor_readings[sensor_id] = {'x': 0, 'y': 0, 'z': 0}
        
        if len(temp_sensor_readings) == TOTAL_SENSORS:
            tracker_poses = get_tracker_poses(tracker_ids)
            
            status_line = f"데이터 수집 중... [{record_index + 1}/{MAX_RECORDS}] | T1: {'OK' if tracker_ids[0] in tracker_poses else 'N/A'}, T2: {'OK' if tracker_ids[1] in tracker_poses else 'N/A'}"
            print(status_line, end='\r')
            
            row_data = [
                time.time(), 
                patch1_area_id, 
                patch2_area_id, 
                int(patch1_inference_enabled), 
                int(patch2_inference_enabled)
            ]
            
            for tracker_id in tracker_ids:
                if tracker_id in tracker_poses:
                    pos = tracker_poses[tracker_id]['pos']
                    matrix = tracker_poses[tracker_id]['matrix']
                    roll, pitch, yaw = get_euler_angles_from_matrix(matrix)
                    quaternion = get_quaternion_from_matrix(matrix)
                    row_data.extend([
                        pos[0], pos[1], pos[2], 
                        roll, pitch, yaw,
                        quaternion[0], quaternion[1], quaternion[2], quaternion[3]
                    ])
                else:
                    row_data.extend([0.0] * 10)
            
            sensor_values = []
            for sid in sensor_ids_ordered:
                sensor_data = temp_sensor_readings.get(sid, {'x': 0, 'y': 0, 'z': 0})
                sensor_values.extend([sensor_data['x'], sensor_data['y'], sensor_data['z']])
            row_data.extend(sensor_values)
            
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
