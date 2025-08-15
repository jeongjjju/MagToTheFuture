import pandas as pd
import numpy as np
import joblib
import torch
import time
from models import MLP, PresenceDetector
from warnings import filterwarnings

filterwarnings('ignore')

data_dir = './data'
model_dir = './models'
device_geometry_file = f'{data_dir}/device_geometry_no_tracker.csv' # inference 시점의 geometry 파일
scaler_file = f'{model_dir}/sensor_scaler_20250727_224824.joblib'
position_model_file = f'{model_dir}/hall_sensor_model_20250727_224824.pth'
presence_model_file = f'{model_dir}/presence_detector_20250727_224824.pth'

try:
    device_geometry = pd.read_csv(device_geometry_file)
    geometry = device_geometry.set_index('label')
    origin = geometry.loc['Corner_2']
    corner1 = geometry.loc['Corner_1']
    corner3 = geometry.loc['Corner_3']
    vec_x = corner1[['pos_x', 'pos_z']] - origin[['pos_x', 'pos_z']]
    vec_z = corner3[['pos_x', 'pos_z']] - origin[['pos_x', 'pos_z']]
    u_x = vec_x / np.linalg.norm(vec_x)
    u_z = vec_z / np.linalg.norm(vec_z)

    scaler = joblib.load(scaler_file)

    input_size = 72
    output_size = 3
    position_model = MLP(input_size, output_size)
    position_model.load_state_dict(torch.load(position_model_file))
    position_model.eval()

    presence_model = PresenceDetector(input_size)
    presence_model.load_state_dict(torch.load(presence_model_file))
    presence_model.eval()
except FileNotFoundError as e:
    print(f"Error: {e}. Please put the required files in the {data_dir} folder.")
    exit()

print("Loading completed. Starting real-time inference.")
print("-" * 40)

def preprocess_input(raw_sensor_data, u_x, u_z, scaler):
    processed_data = raw_sensor_data.copy()
    num_sensors = len(processed_data) // 3
    
    for i in range(num_sensors):
        x_idx, z_idx = i * 3, i * 3 + 2
        original_x = raw_sensor_data[x_idx]
        original_z = raw_sensor_data[z_idx]
        
        processed_data[x_idx] = original_x * u_x['pos_x'] + original_z * u_x['pos_z']
        processed_data[z_idx] = original_x * u_z['pos_x'] + original_z * u_z['pos_z']

    scaled_data = scaler.transform(processed_data.reshape(1, -1))
    
    return scaled_data

def get_new_sensor_data():
    #### 실제 환경에서는 이 부분을 하드웨어 데이터 수집 코드로 대체해야 함 ####
    if int(time.time()) % 10 < 5:
        # 자석 없음 (배경 노이즈)
        return np.random.randn(72) * 0.1
    else:
        # 자석 있음 (강한 신호)
        return np.random.rand(72) * 5 - 2.5



try:
    while True:
        raw_data = get_new_sensor_data()
        sensor_magnitudes = []
        for i in range(24):
            x = raw_data[i * 3]
            y = raw_data[i * 3 + 1]
            z = raw_data[i * 3 + 2]
            mag = np.sqrt(x**2 + y**2 + z**2)
            sensor_magnitudes.append(mag)

        print(sensor_magnitudes)

        # preprocessed_data = preprocess_input(raw_data, u_x, u_z, scaler)
        
        # input_tensor = torch.FloatTensor(preprocessed_data)

        # with torch.no_grad():
        #     presence_prob = presence_model(input_tensor).item()

        # if presence_prob > 0.8:
        #     with torch.no_grad():
        #         predicted_pos_transformed = position_model(input_tensor).numpy().flatten()
        #         print(f"Predicted position: {predicted_pos_transformed}")

                # (선택 사항) 결과를 원래 좌표계로 역변환
                # x_prime, y_prime, z_prime = predicted_pos_transformed
                # rev_rotated_x = x_prime * u_x['pos_x'] + z_prime * u_z['pos_x']
                # rev_rotated_z = x_prime * u_x['pos_z'] + z_prime * u_z['pos_z']
                # final_x = rev_rotated_x + origin['pos_x']
                # final_y = y_prime + origin['pos_y']
                # final_z = rev_rotated_z + origin['pos_z']
                
                # print(f"[{time.strftime('%H:%M:%S')}] Predicted Position (Original Coords): "
                #       f"X={final_x:.3f}, Y={final_y:.3f}, Z={final_z:.3f}")
            time.sleep(3)
        else:
            print("No presence detected.")

        time.sleep(1/3)

except KeyboardInterrupt:
    print("\nInference terminated.")