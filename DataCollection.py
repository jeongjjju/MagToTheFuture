import serial
import numpy as np
import openvr
import pandas as pd
from datetime import datetime
import time
import os
import threading
import queue
import re # 파일명 파싱을 위해 re 모듈 추가

# --- Configuration ---
ARDUINO_PORT = 'COM9'  # Teensy COM 포트
BAUD_RATE = 1000000
TOTAL_SENSORS = 24
MAX_RECORDS = 100000  # 미리 할당할 최대 행 수
# 저장 경로 지정 (Windows 경로를 위해 raw string 'r' 사용)
SAVE_PATH = r"C:\Users\Administrator\Desktop\MagToTheFuture\0814"

# --- 스레드 간 데이터 공유 및 제어 ---
data_queue = queue.Queue()
start_tracker2_recording = threading.Event()
start_geometry_phase = threading.Event()
stop_thread = threading.Event()

# --- Helper Functions ---
def serial_reader(ser, q, stop_event):
    """시리얼 포트에서 지속적으로 데이터를 읽어 큐에 넣는 스레드 함수."""
    print("시리얼 리더 스레드 시작.")
    while not stop_event.is_set():
        try:
            line = ser.readline().decode('utf-8', 'ignore').strip()
            if line:
                q.put(line)
        except (serial.SerialException, TypeError):
            break
    print("시리얼 리더 스레드 종료.")

def input_listener():
    """사용자 입력을 기다리는 스레드 함수 (2단계 진행)"""
    input("\n데이터 수집 중... 첫 번째 Enter를 누르면 트래커 2의 데이터 기록을 시작합니다.")
    start_tracker2_recording.set()
    print("\n✅ 트래커 2 데이터 기록 시작!")
    
    input("두 번째 Enter를 누르면 실시간 데이터 수집을 멈추고 꼭짓점 좌표 기록을 시작합니다.")
    start_geometry_phase.set()

def get_tracker_pose(tracker_id):
    """주어진 ID의 VIVE 트래커의 현재 위치와 회전 행렬을 반환합니다."""
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

def record_point(label, geom_data_list, tracker_id_to_use):
    """주어진 레이블에 대한 꼭짓점 위치를 기록합니다."""
    while True:
        input(f"\n>>> 트래커 1을 '{label}' 위치에 놓고 Enter를 누르세요...")
        pos, _ = get_tracker_pose(tracker_id_to_use)
        if pos:
            print(f"'{label}' 위치 기록됨: (X={pos[0]:.4f}, Y={pos[1]:.4f}, Z={pos[2]:.4f})")
            geom_data_list.append({'label': label, 'pos_x': pos[0], 'pos_y': pos[1], 'pos_z': pos[2]})
            break
        else:
            print("오류: 트래커 위치를 읽을 수 없습니다. 다시 시도해 주세요.")

def get_next_run_number(path):
    """디렉토리를 스캔하여 다음 실행 번호를 결정합니다."""
    os.makedirs(path, exist_ok=True)  # 디렉토리가 없으면 생성
    max_num = 0
    p = re.compile(r'DualPatchData_(\d+)\.csv$')
    for f in os.listdir(path):
        match = p.search(f)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    return max_num + 1

def save_to_csv(data_array, col_order, num_records, geom_data):
    """수집된 데이터를 지정된 경로와 파일명 규칙에 따라 CSV 파일로 저장합니다."""
    run_number = get_next_run_number(SAVE_PATH)
    base_filename = f"DualPatchData_{run_number}"
    print(f"\n데이터 저장 준비 중... 실행 번호: {run_number}")

    # 꼭짓점 좌표 데이터 저장
    if len(geom_data) > 0:
        print("\n꼭짓점 좌표 데이터 저장 중...")
        df_geom = pd.DataFrame(geom_data)
        geom_filename = f"device_geometry_{base_filename}.csv"
        full_path = os.path.join(SAVE_PATH, geom_filename)
        df_geom.to_csv(full_path, index=False)
        print(f"'{full_path}' 파일 저장 완료.")

    # 시계열 데이터 저장
    if num_records > 0:
        print("\n실시간 수집 데이터 저장 중...")
        df_ts = pd.DataFrame(data_array[:num_records], columns=col_order)
        ts_filename = f"training_data_{base_filename}.csv"
        full_path = os.path.join(SAVE_PATH, ts_filename)
        df_ts.to_csv(full_path, index=False)
        print(f"총 {num_records}개의 시계열 데이터가 '{full_path}'에 저장되었습니다.")

# --- OpenVR 및 시리얼 포트 초기화 ---
try:
    print("OpenVR 초기화 시도 중..."); vr_system = openvr.init(openvr.VRApplication_Other)
    ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
except Exception as e: 
    print(f"오류: 초기화 실패. 오류: {e}"); exit()

tracker_ids = []
for i in range(openvr.k_unMaxTrackedDeviceCount):
    if vr_system.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_GenericTracker:
        tracker_ids.append(i)
        print(f"VIVE 트래커 발견. 장치 ID: {i}")
if len(tracker_ids) < 2:
    print(f"오류: 2개의 VIVE 트래커를 찾지 못했습니다 (찾은 개수: {len(tracker_ids)})."); ser.close(); openvr.shutdown(); exit()
print(f"트래커 1 ID: {tracker_ids[0]}, 트래커 2 ID: {tracker_ids[1]}")

# --- 데이터 구조 정의 ---
column_order = ['timestamp']
tracker1_cols = [
    'tracker1_pos_x', 'tracker1_pos_y', 'tracker1_pos_z',
    'tracker1_rot_roll', 'tracker1_rot_pitch', 'tracker1_rot_yaw',
    'tracker1_rot_quat_x', 'tracker1_rot_quat_y', 'tracker1_rot_quat_z', 'tracker1_rot_quat_w'
]
tracker2_cols = [
    'tracker2_pos_x', 'tracker2_pos_y', 'tracker2_pos_z',
    'tracker2_rot_roll', 'tracker2_rot_pitch', 'tracker2_rot_yaw',
    'tracker2_rot_quat_x', 'tracker2_rot_quat_y', 'tracker2_rot_quat_z', 'tracker2_rot_quat_w'
]
column_order.extend(tracker1_cols)
column_order.extend(tracker2_cols)

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
geometry_data = []
try:
    print("\n--- Teensy 동기화 대기 중 ---")
    while True:
        line = ser.readline().decode('utf-8', 'ignore').strip()
        if line == "START":
            print("--- ✅ 동기화 완료! ---")
            break

    reader_thread = threading.Thread(target=serial_reader, args=(ser, data_queue, stop_thread))
    reader_thread.start()
    listener_thread = threading.Thread(target=input_listener, daemon=True)
    listener_thread.start()
    
    while not start_geometry_phase.is_set():
        if record_index >= MAX_RECORDS:
            print("\n최대 기록 수에 도달하여 수집을 중단합니다.")
            start_geometry_phase.set()
            break
        
        try:
            line = data_queue.get_nowait()
        except queue.Empty:
            continue

        if not line.startswith("S_"):
            continue
            
        parts = line.split(',')
        if len(parts) != TOTAL_SENSORS * 4:
            print(f"경고: 데이터 길이가 일치하지 않습니다. 예상: {TOTAL_SENSORS * 4}, 실제: {len(parts)}. 이 라인을 건너뜁니다.")
            continue

        temp_sensor_readings = {}
        for i in range(0, len(parts), 4):
            sensor_id, cx, cy, cz = parts[i:i+4]
            try:
                temp_sensor_readings[sensor_id] = {'x': float(cx), 'y': float(cy), 'z': float(cz)}
            except ValueError:
                temp_sensor_readings[sensor_id] = {'x': 0, 'y': 0, 'z': 0}
        
        if len(temp_sensor_readings) == TOTAL_SENSORS:
            pos1, matrix1 = get_tracker_pose(tracker_ids[0])
            
            if start_tracker2_recording.is_set():
                pos2, matrix2 = get_tracker_pose(tracker_ids[1])
            else:
                pos2, matrix2 = None, None

            t1_status = 'OK' if pos1 else 'N/A'
            t2_status = 'OK' if pos2 else ('Waiting...' if not start_tracker2_recording.is_set() else 'N/A')
            status_line = f"수집 중... [{record_index + 1}/{MAX_RECORDS}] | 트래커1: {t1_status} | 트래커2: {t2_status}"
            print(status_line, end='\r')
            
            if pos1:
                roll1, pitch1, yaw1 = get_euler_angles_from_matrix(matrix1)
                quat1 = get_quaternion_from_matrix(matrix1)
                tracker1_data = [pos1[0], pos1[1], pos1[2], roll1, pitch1, yaw1, quat1[0], quat1[1], quat1[2], quat1[3]]
                
                if pos2 and matrix2:
                    roll2, pitch2, yaw2 = get_euler_angles_from_matrix(matrix2)
                    quat2 = get_quaternion_from_matrix(matrix2)
                    tracker2_data = [pos2[0], pos2[1], pos2[2], roll2, pitch2, yaw2, quat2[0], quat2[1], quat2[2], quat2[3]]
                else:
                    tracker2_data = [0] * 10

                sensor_values = []
                for sid in sensor_ids_ordered:
                    sensor_data = temp_sensor_readings.get(sid, {'x': 0, 'y': 0, 'z': 0})
                    sensor_values.extend([sensor_data['x'], sensor_data['y'], sensor_data['z']])
                
                row_data = [time.time()] + tracker1_data + tracker2_data + sensor_values
                
                time_series_data_array[record_index] = row_data
                record_index += 1
    
    print("\n\n--- 실시간 데이터 수집을 중단하고 꼭짓점 좌표 기록을 시작합니다. ---")
    for i in range(4):
        record_point(f'Corner_{i+1}', geometry_data, tracker_ids[0])
    print("\n--- ✅ 모든 좌표 기록 완료! ---")

except KeyboardInterrupt:
    print("\n\n사용자에 의해 프로그램이 강제 종료되었습니다.")
finally:
    stop_thread.set()
    if reader_thread:
        reader_thread.join()
    
    save_to_csv(time_series_data_array, column_order, record_index, geometry_data)
    
    ser.close()
    if 'vr_system' in locals() and vr_system is not None:
        openvr.shutdown()
    print("시리얼 포트와 OpenVR 연결이 종료되었습니다.")
