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

# --- Configuration ---
ARDUINO_PORT = 'COM9'
BAUD_RATE = 1000000
TOTAL_SENSORS = 24
MAX_RECORDS = 100000
NUM_TRACKERS = 2

# --- Inter-thread data sharing and control ---
data_queue = queue.Queue()
stop_thread = threading.Event()

# User input states
record_geometry_mode = False
patch1_inference_enabled = False
patch2_inference_enabled = False

# --- Helper Functions ---
def serial_reader_optimized(ser, q, stop_event):
    """
    Optimized thread function to continuously read data from the serial port.
    It reads a large chunk of available data at once to reduce I/O overhead.
    """
    print("Optimized serial reader thread started.")
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
    print("Optimized serial reader thread finished.")

def input_listener_non_blocking():
    """
    Thread function to listen for non-blocking key presses.
    'g' to start geometry recording, 'o' to toggle inference.
    """
    global record_geometry_mode, patch1_inference_enabled, patch2_inference_enabled
    while not stop_thread.is_set():
        if msvcrt.kbhit():
            key = msvcrt.getch().decode('utf-8')
            if key == 'g':
                record_geometry_mode = True
                print("\n\n--- Geometry recording mode activated. Press 'q' to exit this mode. ---")
            elif key == 'o':
                patch1_inference_enabled = not patch1_inference_enabled
                patch2_inference_enabled = not patch2_inference_enabled
                print(f"\n--- Inference toggled: Patch 1 Enabled: {patch1_inference_enabled}, Patch 2 Enabled: {patch2_inference_enabled} ---")
            elif key == 'q':
                record_geometry_mode = False
                print("\n--- Geometry recording mode deactivated. ---")
            
def get_tracker_poses(tracker_ids):
    """
    Returns the current position and rotation matrix for multiple VIVE trackers.
    Returns a dictionary of poses, keyed by tracker ID.
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
    """Calculates Roll, Pitch, and Yaw Euler angles from a rotation matrix."""
    yaw = np.degrees(np.arctan2(m[1][0], m[0][0]))
    pitch = np.degrees(np.arctan2(-m[2][0], np.sqrt(m[2][1]**2 + m[2][2]**2)))
    roll = np.degrees(np.arctan2(m[2][1], m[2][2]))
    return roll, pitch, yaw
    
def get_quaternion_from_matrix(m):
    """Calculates the Quaternion (x, y, z, w) from a rotation matrix."""
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
    """Records the corner position for a given area using a specific tracker."""
    print(f"\n>>> Recording for {area_label} using Tracker {tracker_id}. Press 'q' to stop.")
    for i in range(4):
        input(f"    - Place Tracker {tracker_id} at '{area_label} Corner_{i+1}' and press Enter...")
        poses = get_tracker_poses([tracker_id])
        pos = poses.get(tracker_id, {}).get('pos')
        if pos:
            print(f"      - Recorded: (X={pos[0]:.4f}, Y={pos[1]:.4f}, Z={pos[2]:.4f})")
            geom_data_list.append({'tracker_id': tracker_id, 'area_label': area_label, 'corner': f'Corner_{i+1}', 'pos_x': pos[0], 'pos_y': pos[1], 'pos_z': pos[2]})
        else:
            print("      - Error: Could not read tracker position. Skipping this point.")

def save_to_csv(data_array, col_order, num_records, geom_data):
    """Saves collected data to CSV files."""
    if len(geom_data) > 0:
        print("\nSaving geometry (fixed coordinates) data...")
        df_geom = pd.DataFrame(geom_data)
        geom_filename = f"device_geometry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_geom.to_csv(geom_filename, index=False)
        print(f"File '{geom_filename}' saved.")

    if num_records > 0:
        print("\nSaving real-time collected data...")
        df_ts = pd.DataFrame(data_array[:num_records], columns=col_order)
        ts_filename = f"training_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_ts.to_csv(ts_filename, index=False)
        print(f"Total {num_records} time-series data points saved to '{ts_filename}'.")

# --- OpenVR and Serial Port Initialization ---
try:
    print("Attempting to initialize OpenVR..."); vr_system = openvr.init(openvr.VRApplication_Other)
    ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=0.1)
except Exception as e: 
    print(f"Error: Initialization failed. Error: {e}"); exit()

tracker_ids = []
for i in range(openvr.k_unMaxTrackedDeviceCount):
    if vr_system.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_GenericTracker:
        tracker_ids.append(i)
        if len(tracker_ids) == NUM_TRACKERS:
            break
if len(tracker_ids) < NUM_TRACKERS:
    print(f"Error: {NUM_TRACKERS} VIVE trackers required, but only {len(tracker_ids)} found. Exiting."); ser.close(); openvr.shutdown(); exit()
print(f"VIVE trackers found. Device IDs: {tracker_ids}")

# --- Data Structure Definition ---
column_order = ['timestamp', 'patch1_inference_enabled', 'patch2_inference_enabled']
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

# --- Main Execution Logic ---
reader_thread = None
input_thread = None
geometry_data = []

try:
    print("\n--- Waiting for Teensy synchronization ---")
    while True:
        line = ser.readline().decode('utf-8', 'ignore').strip()
        if line == "START":
            print("--- ✅ Synchronization complete! Press 'g' to start geometry mode, 'o' to toggle inference, 'Ctrl+C' to stop. ---")
            break

    reader_thread = threading.Thread(target=serial_reader_optimized, args=(ser, data_queue, stop_thread))
    reader_thread.start()
    input_thread = threading.Thread(target=input_listener_non_blocking, daemon=True)
    input_thread.start()
    
    while not stop_thread.is_set():
        if record_geometry_mode:
            print("\n\n--- Geometry Recording Mode ---")
            print("Press '1' to set Area 1 for Tracker 1")
            print("Press '2' to set Area 2 for Tracker 2")
            print("Press 'q' to exit this mode")
            
            # Non-blocking input for geometry mode
            while record_geometry_mode:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8')
                    if key == '1':
                        record_area_points(tracker_ids[0], "Area_1", geometry_data)
                    elif key == '2':
                        record_area_points(tracker_ids[1], "Area_2", geometry_data)
                    elif key == 'q':
                        record_geometry_mode = False
                        print("\n--- Geometry recording mode deactivated. ---")
                        break
                time.sleep(0.1)

        if record_index >= MAX_RECORDS:
            print("\nMaximum record count reached, stopping collection.")
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
            print(f"Warning: Unexpected data length. Expected {TOTAL_SENSORS * 4} parts, got {len(parts)}. Skipping this line.")
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
            
            status_line = f"Collecting data... [{record_index + 1}/{MAX_RECORDS}] | T1: {'OK' if tracker_ids[0] in tracker_poses else 'N/A'}, T2: {'OK' if tracker_ids[1] in tracker_poses else 'N/A'}"
            print(status_line, end='\r')
            
            row_data = [
                time.time(), 
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
                    # Append zeros if tracker data is missing
                    row_data.extend([0.0] * 10)
            
            sensor_values = []
            for sid in sensor_ids_ordered:
                sensor_data = temp_sensor_readings.get(sid, {'x': 0, 'y': 0, 'z': 0})
                sensor_values.extend([sensor_data['x'], sensor_data['y'], sensor_data['z']])
            row_data.extend(sensor_values)
            
            time_series_data_array[record_index] = row_data
            record_index += 1
    
    # 2단계: 꼭짓점 좌표 기록 (프로그램 종료 전)
    print("\n\n--- Geometry recording mode activated. Press 'q' to exit this mode. ---")
    while True:
        print("\nPress '1' to set Area 1 for Tracker 1")
        print("Press '2' to set Area 2 for Tracker 2")
        print("Press 'q' to exit this mode and save files")
        key = msvcrt.getch().decode('utf-8')
        if key == '1':
            record_area_points(tracker_ids[0], "Area_1", geometry_data)
        elif key == '2':
            record_area_points(tracker_ids[1], "Area_2", geometry_data)
        elif key == 'q':
            break

except KeyboardInterrupt:
    print("\n\nProgram forcibly stopped by user.")
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
    print("Serial port and OpenVR have been closed.")
