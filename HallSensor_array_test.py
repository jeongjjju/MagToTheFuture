import serial
import numpy as np
import openvr
import pandas as pd
from datetime import datetime
import time
import os

# --- 설정 ---
ARDUINO_PORT = 'COM5'
BAUD_RATE = 1000000
TOTAL_SENSORS = 24

# --- 데이터 저장을 위한 리스트 ---
data_log = []

# --- OpenVR 및 시리얼 포트 초기화 ---
try:
    print("OpenVR 초기화 시도... (SteamVR이 실행 중이어야 합니다)")
    openvr.init(openvr.VRApplication_Other)
except Exception as e:
    print(f"오류: OpenVR 초기화 실패. 에러: {e}"); exit()

try:
    ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
    print("\n--- 아두이노 동기화 대기 중 ---")
    while True:
        line = ser.readline().decode('utf-8', 'ignore').strip()
        if line: print(f"Arduino: {line}")
        if "SensorID" in line: print("\n--- ✅ 동기화 완료! ---"); break
except Exception as e:
    print(f"오류: 아두이노 포트({ARDUINO_PORT})를 열 수 없습니다. 에러: {e}"); openvr.shutdown(); exit()

tracker_id = None
for i in range(openvr.k_unMaxTrackedDeviceCount):
    if openvr.VRSystem().getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_GenericTracker:
        tracker_id = i; print(f"VIVE 트래커를 찾았습니다. 장치 ID: {tracker_id}"); break
if tracker_id is None:
    print("오류: VIVE 트래커를 찾을 수 없습니다."); ser.close(); openvr.shutdown(); exit()

def get_euler_angles_from_matrix(m):
    yaw = np.degrees(np.arctan2(m[1][0], m[0][0]))
    pitch = np.degrees(np.arctan2(-m[2][0], np.sqrt(m[2][1]**2 + m[2][2]**2)))
    roll = np.degrees(np.arctan2(m[2][1], m[2][2]))
    return roll, pitch, yaw

# --- 메인 실행 및 종료 처리 ---
try:
    print("\n데이터 수집을 시작합니다. 중단하려면 Ctrl+C를 누르세요.")
    temp_sensor_readings = {} 
    
    while True:
        line = ser.readline().decode('utf-8', 'ignore').strip()
        if not line or "FAILED" in line or "SensorID" in line: continue

        parts = line.split(',')
        if len(parts) == 4:
            sensor_id, cx, cy, cz = parts
            temp_sensor_readings[sensor_id] = {'x': float(cx), 'y': float(cy), 'z': float(cz)}

            if len(temp_sensor_readings) == TOTAL_SENSORS:
                poses = openvr.VRSystem().getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount)
                tracker_pose = poses[tracker_id]

                if tracker_pose.bPoseIsValid:
                    m = tracker_pose.mDeviceToAbsoluteTracking
                    pos = [m[0][3], m[1][3], m[2][3]]
                    roll, pitch, yaw = get_euler_angles_from_matrix(m)
                    
                    record = {'timestamp': time.time(),
                              'pos_x': pos[0], 'pos_y': pos[1], 'pos_z': pos[2],
                              'rot_roll': roll, 'rot_pitch': pitch, 'rot_yaw': yaw}
                    
                    for i in range(TOTAL_SENSORS):
                        mux_addr = 0x70 + (i // 8)
                        channel = i % 8
                        sid = f"S_{mux_addr:x}_{channel}"
                        sensor_data = temp_sensor_readings.get(sid, {'x': 0, 'y': 0, 'z': 0})
                        record[f'{sid}_x'] = sensor_data['x']
                        record[f'{sid}_y'] = sensor_data['y']
                        record[f'{sid}_z'] = sensor_data['z']
                    
                    data_log.append(record)
                    print(f"데이터 기록 중... 현재 {len(data_log)}개 행 수집됨.", end='\r')

                # 임시 저장소 비우기
                temp_sensor_readings = {}
                
                # ★★★ 1000개씩 끊어 저장하는 기능 삭제 ★★★

except KeyboardInterrupt:
    print("\n\n프로그램이 사용자에 의해 중단되었습니다.")
finally:
    if data_log:
        print("\nCSV 파일로 저장 중...")
        df = pd.DataFrame(data_log)
        
        # ★★★ 원하는 순서대로 열(Column) 목록을 직접 생성 ★★★
        column_order = ['timestamp', 'pos_x', 'pos_y', 'pos_z', 'rot_roll', 'rot_pitch', 'rot_yaw']
        for i in range(TOTAL_SENSORS):
            mux_addr = 0x70 + (i // 8)
            channel = i % 8
            sid = f"S_{mux_addr:x}_{channel}"
            column_order.append(f'{sid}_x')
            column_order.append(f'{sid}_y')
            column_order.append(f'{sid}_z')
            
        # DataFrame의 열 순서를 위에서 정의한 순서로 재정렬
        df = df[column_order]

        # 파일 이름 생성 및 저장
        filename = f"training_data_wide_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False)
        print(f"'{filename}' 파일에 총 {len(df)}개의 시간대 데이터가 저장되었습니다.")
    else:
        print("수집된 데이터가 없어 파일을 저장하지 않습니다.")

    ser.close()
    openvr.shutdown()
    print("시리얼 포트와 OpenVR을 종료했습니다.")