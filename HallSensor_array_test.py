import serial
import numpy as np
import openvr
import pandas as pd
from datetime import datetime
import time
import os
import threading
import queue

# --- Configuration ---
ARDUINO_PORT = 'COM9' # Teensy COM port
BAUD_RATE = 1000000
TOTAL_SENSORS = 24
MAX_RECORDS = 100000 # Max number of rows to pre-allocate

# --- Inter-thread data sharing and control ---
data_queue = queue.Queue()
start_geometry_phase = threading.Event()
stop_thread = threading.Event()

# --- Helper Functions ---
def serial_reader(ser, q, stop_event):
    """
    Thread function to continuously read data from the serial port and put it into a queue.
    The optimized Teensy code now sends all sensor data in a single line.
    """
    print("Serial reader thread started.")
    while not stop_event.is_set():
        try:
            line = ser.readline().decode('utf-8', 'ignore').strip()
            if line:
                q.put(line)
        except (serial.SerialException, TypeError):
            break
    print("Serial reader thread finished.")

def input_listener():
    """Thread function to wait for the user to press Enter."""
    input("\nCollecting data... Press Enter to start recording corner coordinates.")
    start_geometry_phase.set()

def get_tracker_pose():
    """
    Returns the current position and rotation matrix of the VIVE tracker.
    """
    poses = vr_system.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount)
    if tracker_id is not None and poses[tracker_id].bPoseIsValid:
        matrix = poses[tracker_id].mDeviceToAbsoluteTracking
        pos = [matrix[0][3], matrix[1][3], matrix[2][3]]
        return pos, matrix
    return None, None

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

def record_point(label, geom_data_list):
    """Records the corner position for a given label."""
    while True:
        input(f"\n>>> Place the tracker at the '{label}' position and press Enter...")
        pos, _ = get_tracker_pose()
        if pos:
            print(f"Recorded '{label}' position: (X={pos[0]:.4f}, Y={pos[1]:.4f}, Z={pos[2]:.4f})")
            geom_data_list.append({'label': label, 'pos_x': pos[0], 'pos_y': pos[1], 'pos_z': pos[2]})
            break
        else:
            print("Error: Could not read tracker position. Please try again.")

def save_to_csv(data_array, col_order, num_records, geom_data):
    """Saves collected data to CSV files."""
    # Save geometry data
    if len(geom_data) > 0:
        print("\nSaving geometry (fixed coordinates) data...")
        df_geom = pd.DataFrame(geom_data)
        geom_filename = f"device_geometry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_geom.to_csv(geom_filename, index=False)
        print(f"File '{geom_filename}' saved.")

    # Save time-series data
    if num_records > 0:
        print("\nSaving real-time collected data...")
        df_ts = pd.DataFrame(data_array[:num_records], columns=col_order)
        ts_filename = f"training_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_ts.to_csv(ts_filename, index=False)
        print(f"Total {num_records} time-series data points saved to '{ts_filename}'.")

# --- OpenVR and Serial Port Initialization ---
try:
    print("Attempting to initialize OpenVR..."); vr_system = openvr.init(openvr.VRApplication_Other)
    ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
except Exception as e: 
    print(f"Error: Initialization failed. Error: {e}"); exit()

tracker_id = None
for i in range(openvr.k_unMaxTrackedDeviceCount):
    if vr_system.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_GenericTracker:
        tracker_id = i
        print(f"VIVE tracker found. Device ID: {tracker_id}")
        break
if tracker_id is None:
    print("Error: VIVE tracker not found."); ser.close(); openvr.shutdown(); exit()

# --- Data Structure Definition ---
column_order = [
    'timestamp', 
    'tracker_pos_x', 'tracker_pos_y', 'tracker_pos_z',
    'tracker_rot_roll', 'tracker_rot_pitch', 'tracker_rot_yaw',
    'tracker_rot_quat_x', 'tracker_rot_quat_y', 'tracker_rot_quat_z', 'tracker_rot_quat_w'
]
sensor_column_names = []
sensor_ids_ordered = []
# This loop generates the ordered list of sensor IDs and column names
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
geometry_data = []
try:
    print("\n--- Waiting for Teensy synchronization ---")
    while True:
        line = ser.readline().decode('utf-8', 'ignore').strip()
        if line == "START":
            print("--- ✅ Synchronization complete! ---")
            break

    # Start threads
    reader_thread = threading.Thread(target=serial_reader, args=(ser, data_queue, stop_thread))
    reader_thread.start()
    listener_thread = threading.Thread(target=input_listener, daemon=True)
    listener_thread.start()
    
    # Stage 1: Collect time-series data
    while not start_geometry_phase.is_set():
        if record_index >= MAX_RECORDS:
            print("\nMaximum record count reached, stopping collection.")
            start_geometry_phase.set() # Automatically move to the next stage
            break
        
        try:
            line = data_queue.get_nowait()
        except queue.Empty:
            continue

        # Check if the line is valid sensor data from the optimized Teensy code
        if not line.startswith("S_"):
            continue
            
        # Parse the single, long line of sensor data
        parts = line.split(',')
        if len(parts) != TOTAL_SENSORS * 4: # Each sensor has an ID and 3 values
            print(f"Warning: Unexpected data length. Expected {TOTAL_SENSORS * 4} parts, got {len(parts)}. Skipping this line.")
            continue

        temp_sensor_readings = {}
        # The new parsing logic to read all 24 sensors from one line
        for i in range(0, len(parts), 4):
            sensor_id, cx, cy, cz = parts[i:i+4]
            try:
                temp_sensor_readings[sensor_id] = {'x': float(cx), 'y': float(cy), 'z': float(cz)}
            except ValueError:
                # If a conversion fails (e.g., 'FAIL' or 'R_FAIL'), store as 0
                temp_sensor_readings[sensor_id] = {'x': 0, 'y': 0, 'z': 0}
        
        if len(temp_sensor_readings) == TOTAL_SENSORS:
            pos, matrix = get_tracker_pose()
            
            # Show the current number of records in real-time
            status_line = f"Collecting data... [{record_index + 1}/{MAX_RECORDS}] | Tracker: {'OK' if pos else 'N/A'}"
            print(status_line, end='\r')
            
            if pos:
                roll, pitch, yaw = get_euler_angles_from_matrix(matrix)
                quaternion = get_quaternion_from_matrix(matrix)
                
                row_data = [
                    time.time(), 
                    pos[0], pos[1], pos[2], 
                    roll, pitch, yaw,
                    quaternion[0], quaternion[1], quaternion[2], quaternion[3]
                ]
                sensor_values = []
                # Reconstruct the sensor data in the correct order for the CSV row
                for sid in sensor_ids_ordered:
                    sensor_data = temp_sensor_readings.get(sid, {'x': 0, 'y': 0, 'z': 0})
                    sensor_values.extend([sensor_data['x'], sensor_data['y'], sensor_data['z']])
                row_data.extend(sensor_values)
                
                time_series_data_array[record_index] = row_data
                record_index += 1
    
    # Stage 2: Record corner coordinates
    print("\n\n--- Stopping real-time data collection and starting corner coordinate recording. ---")
    for i in range(4):
        record_point(f'Corner_{i+1}', geometry_data)
    print("\n--- ✅ All coordinates recorded! ---")

except KeyboardInterrupt:
    print("\n\nProgram forcibly stopped by user.")
finally:
    stop_thread.set()
    if reader_thread:
        reader_thread.join()
    
    save_to_csv(time_series_data_array, column_order, record_index, geometry_data)
    
    ser.close()
    if 'vr_system' in locals() and vr_system is not None:
        openvr.shutdown()
    print("Serial port and OpenVR have been closed.")
