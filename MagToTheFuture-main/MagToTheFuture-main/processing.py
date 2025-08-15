import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import joblib
import os

data_dir = r'C:\Users\HCIS\Desktop\박정주\MagToTheFuture'
model_dir = r'C:\Users\HCIS\Desktop\박정주\MagToTheFuture\models'

# 여러 쌍 정의: (device_geometry_file, training_data_file)
data_pairs = [
    # ('device_geometry_no_tracker.csv', 'training_data_no_tracker.csv'),
    # ('device_geometry_with_tracker.csv', 'training_data_with_tracker.csv'),
    ('area_multi_device_geometry_20250808_214316.csv', 'area_multi_training_data_20250808_214316.csv')
]

processed_data_list = []

for geometry_filename, data_filename in data_pairs:
    print(f"Processing: {data_filename} using {geometry_filename}")
    
    try:
        device_geometry_path = os.path.join(data_dir, geometry_filename)
        training_data_path = os.path.join(data_dir, data_filename)
        
        device_geometry = pd.read_csv(device_geometry_path)
        training_data = pd.read_csv(training_data_path)

    except FileNotFoundError as e:
        print(f"오류: 파일을 찾을 수 없습니다. '{e.filename}'")
        print("data 폴더에 파일이 정확히 있는지 확인해주세요.")
        continue
    except Exception as e:
        print(f"파일을 읽는 중 오류가 발생했습니다: {e}")
        continue

    try:
        geometry = device_geometry.set_index('label')
    except KeyError:
        print(f"오류: '{geometry_filename}' 파일에 'label' 컬럼이 없습니다.")
        print("CSV 파일의 첫 번째 열 헤더를 'label'로 수정해주세요.")
        continue
        
    origin = geometry.loc['Corner_2']
    corner1 = geometry.loc['Corner_1']
    corner3 = geometry.loc['Corner_3']

    vec_x_raw = corner1[['pos_x', 'pos_y', 'pos_z']] - origin[['pos_x', 'pos_y', 'pos_z']]
    vec_z_raw = corner3[['pos_x', 'pos_y', 'pos_z']] - origin[['pos_x', 'pos_y', 'pos_z']]

    u_x = vec_x_raw / np.linalg.norm(vec_x_raw)
    vec_y_raw = np.cross(vec_z_raw, vec_x_raw)
    u_y = vec_y_raw / np.linalg.norm(vec_y_raw)
    u_z = np.cross(u_x, u_y)

    processed_data = training_data.copy()

    translated_x = training_data['tracker_pos_x'] - origin['pos_x']
    translated_y = training_data['tracker_pos_y'] - origin['pos_y']
    translated_z = training_data['tracker_pos_z'] - origin['pos_z']
    
    processed_data['tracker_pos_x'] = translated_x * u_x[0] + translated_y * u_x[1] + translated_z * u_x[2]
    processed_data['tracker_pos_y'] = translated_x * u_y[0] + translated_y * u_y[1] + translated_z * u_y[2]
    processed_data['tracker_pos_z'] = translated_x * u_z[0] + translated_y * u_z[1] + translated_z * u_z[2]

    sensor_columns = [col for col in training_data.columns if col.startswith('S_')]
    sensor_bases = sorted(set(['_'.join(col.split('_')[:-1]) for col in sensor_columns]))

    for base in sensor_bases:
        orig_x_col, orig_z_col = f'{base}_x', f'{base}_z'
        if orig_x_col in processed_data.columns and orig_z_col in processed_data.columns:
            new_sensor_x = processed_data[orig_x_col] * u_x[0] + processed_data[orig_z_col] * u_x[2]
            new_sensor_z = processed_data[orig_x_col] * u_z[0] + processed_data[orig_z_col] * u_z[2]
            
            processed_data[orig_x_col] = new_sensor_x
            processed_data[orig_z_col] = new_sensor_z

    is_tracker = 0 if 'no_tracker' in data_filename else 1
    processed_data['is_tracker'] = is_tracker
    processed_data_list.append(processed_data)

final_data = pd.concat(processed_data_list, ignore_index=True)

scaler = StandardScaler()
sensor_columns_to_scale = [col for col in final_data.columns if col.startswith('S_')]
if sensor_columns_to_scale:
    final_data[sensor_columns_to_scale] = scaler.fit_transform(final_data[sensor_columns_to_scale])

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_csv = f'{data_dir}/processed_training_data_{timestamp}.csv'
output_scaler = f'{model_dir}/sensor_scaler_{timestamp}.joblib'
output_plot_file = f'{data_dir}/coordinate_system_{timestamp}.png'

final_data.to_csv(output_csv, index=False)
joblib.dump(scaler, output_scaler)

print(f"All merged and processed data saved to: {output_csv}")
print(f"Scaler saved to: {output_scaler}")

print("Starting 3D coordinate system visualization.")
fig = plt.figure(figsize=(10, 10))
ax = fig.add_subplot(111, projection='3d')

for label in ['Corner_1', 'Corner_2', 'Corner_3', 'Corner_4']:
    if label in geometry.index:
        point_orig = geometry.loc[label]
        translated = point_orig - origin
        
        new_x = np.dot(translated, u_x)
        new_y = np.dot(translated, u_y)
        new_z = np.dot(translated, u_z)
        
        ax.scatter(new_x, new_y, new_z, c='red', s=100, label=f'Transformed {label}' if label == 'Corner_1' else "")
        ax.text(new_x, new_y, new_z, label, fontsize=12)

axis_length = 0.5
ax.quiver(0, 0, 0, u_x[0]*axis_length, u_x[1]*axis_length, u_x[2]*axis_length, color='blue', label='New X-axis')
ax.quiver(0, 0, 0, u_y[0]*axis_length, u_y[1]*axis_length, u_y[2]*axis_length, color='green', label='New Y-axis')
ax.quiver(0, 0, 0, u_z[0]*axis_length, u_z[1]*axis_length, u_z[2]*axis_length, color='purple', label='New Z-axis')

ax.set_title('Transformed New 3D Coordinate System', fontsize=16)
ax.set_xlabel('New X-axis', fontsize=12)
ax.set_ylabel('New Y-axis', fontsize=12)
ax.set_zlabel('New Z-axis', fontsize=12)
ax.legend()
ax.grid(True)

plt.savefig(output_plot_file)
print(f"3D coordinate system image has been saved to '{output_plot_file}' file.")