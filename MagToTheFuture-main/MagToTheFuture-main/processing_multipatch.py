import os
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.preprocessing import StandardScaler
import joblib
import matplotlib.pyplot as plt

data_dir = './data'
model_dir = './models'
os.makedirs(data_dir, exist_ok=True)
os.makedirs(model_dir, exist_ok=True)

# 여러 쌍 정의: (device_geometry_file, training_data_file)
data_pairs = [
    ('device_geometry_20250807_single.csv', 'training_data_20250807_single.csv'),
    ('device_geometry_20250807_multi.csv', 'training_data_20250807_multi.csv'),
    ('device_geometry_20250807_triple.csv', 'training_data_20250807_triple.csv'),
]

# 시각화 저장 여부(코너 좌표 정합 확인용)
PLOT_PER_PAIR = True   # True이면 각 쌍별 플롯 저장

def build_orthonormal_axes_2d(geometry_df, origin_label='Corner_2',
                              xref_label='Corner_1', zref_label='Corner_3'):
    """
    geometry_df: columns ['label','pos_x','pos_y','pos_z'] 가정
    반환: (origin(dict-like), u_x(np.array[2]), u_z(np.array[2]), Lx(float), Lz(float))
    """
    geo = geometry_df.set_index('label')

    origin  = geo.loc[origin_label]
    corner1 = geo.loc[xref_label]
    corner3 = geo.loc[zref_label]

    v_x = np.array([corner1['pos_x'] - origin['pos_x'],
                    corner1['pos_z'] - origin['pos_z']], dtype=float)
    v_z = np.array([corner3['pos_x'] - origin['pos_x'],
                    corner3['pos_z'] - origin['pos_z']], dtype=float)

    if np.linalg.norm(v_x) == 0 or np.linalg.norm(v_z) == 0:
        raise ValueError("The length of the Corner vector is 0. Please check the geometry CSV.")

    u_x = v_x / np.linalg.norm(v_x)
    v_z_orth = v_z - (v_z @ u_x) * u_x
    if np.linalg.norm(v_z_orth) == 0:
        raise ValueError("The x-axis and z-axis vectors are parallel. Please select a different corner.")
    u_z = v_z_orth / np.linalg.norm(v_z_orth)

    Lx = v_x @ u_x
    Lz = v_z @ u_z
    if Lx < 0:
        u_x = -u_x; Lx = -Lx
    if Lz < 0:
        u_z = -u_z; Lz = -Lz

    return origin, u_x, u_z, float(Lx), float(Lz)

def proj_xz(x, z, origin, u_x, u_z):
    tx = x - origin['pos_x']
    tz = z - origin['pos_z']
    new_x = tx * u_x[0] + tz * u_x[1]
    new_z = tx * u_z[0] + tz * u_z[1]
    return new_x, new_z

def transform_tracker(df, origin, u_x, u_z):
    new_x, new_z = zip(*[
        proj_xz(x, z, origin, u_x, u_z)
        for x, z in zip(df['tracker_pos_x'].to_numpy(),
                        df['tracker_pos_z'].to_numpy())
    ])
    df_out = df.copy()
    df_out['tracker_pos_x'] = np.array(new_x)
    df_out['tracker_pos_z'] = np.array(new_z)
    df_out['tracker_pos_y'] = df['tracker_pos_y'] - origin['pos_y']
    return df_out

def transform_sensors(df, origin, u_x, u_z):
    sensor_cols = [c for c in df.columns if c.startswith('S_')]
    bases = sorted(set(['_'.join(c.split('_')[:-1]) for c in sensor_cols]))
    out = df.copy()
    for base in bases:
        xcol = f'{base}_x'
        zcol = f'{base}_z'
        if xcol in out.columns and zcol in out.columns:
            X = out[xcol].to_numpy()
            Z = out[zcol].to_numpy()
            new = np.array([proj_xz(x, z, origin, u_x, u_z) for x, z in zip(X, Z)])
            out[xcol] = new[:, 0]
            out[zcol] = new[:, 1]
    return out

def plot_corners_2d(origin, u_x, u_z, geometry_df, save_path):
    geo = geometry_df.set_index('label')
    labels = ['Corner_1', 'Corner_2', 'Corner_3', 'Corner_4']
    pts = []
    for lab in labels:
        p = geo.loc[lab]
        x2, z2 = proj_xz(p['pos_x'], p['pos_z'], origin, u_x, u_z)
        pts.append((lab, x2, z2))

    plt.figure(figsize=(7, 7))
    xs = [p[1] for p in pts]; zs = [p[2] for p in pts]
    plt.scatter(xs, zs, c='red', s=80, zorder=5, label='Transformed Corner Coordinates')
    for lab, x2, z2 in pts:
        plt.text(x2 + 0.01, z2 - 0.01, lab, fontsize=11)
    plt.axhline(0, color='black', linestyle='--', linewidth=1)
    plt.axvline(0, color='black', linestyle='--', linewidth=1)
    plt.title('Transformed New Coordinate System (2D Orthonormal Axes)')
    plt.xlabel('New X-axis'); plt.ylabel('New Z-axis')
    plt.gca().set_aspect('equal', adjustable='box')
    plt.grid(True, alpha=0.4); plt.legend(); plt.tight_layout()
    plt.savefig(save_path); plt.close()

# 파일명에서 패치 개수 라벨링
def get_patch_label(filename: str) -> int:
    fname = filename.lower()
    if '_single' in fname:  return 1
    if '_multi'  in fname:  return 2
    if '_triple' in fname:  return 3
    raise ValueError(f"Cannot parse the patch count from the filename (_single/_multi/_triple): {filename}")

if __name__ == "__main__":
    processed_data_list = []

    for geometry_filename, data_filename in data_pairs:
        print(f"[Processing] data={data_filename}  geom={geometry_filename}")
        geom_path = os.path.join(data_dir, geometry_filename)
        data_path = os.path.join(data_dir, data_filename)

        try:
            device_geometry = pd.read_csv(geom_path)
            training_data = pd.read_csv(data_path)
        except FileNotFoundError as e:
            print(f"  -> Error: {e}")
            continue

        try:
            origin, u_x, u_z, Lx, Lz = build_orthonormal_axes_2d(device_geometry)
        except ValueError as e:
            print(f"  -> Geometry error: {e}")
            continue

        processed = transform_tracker(training_data, origin, u_x, u_z)
        processed = transform_sensors(processed, origin, u_x, u_z)

        # 패치 개수 라벨 추가 (파일명 기준)
        try:
            processed['patch_count'] = get_patch_label(data_filename)
        except ValueError as e:
            print(f"  -> Label error: {e}")
            continue

        processed_data_list.append(processed)

        if PLOT_PER_PAIR:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            plot_path = os.path.join(data_dir, f'coord_system_{os.path.splitext(data_filename)[0]}_{ts}.png')
            plot_corners_2d(origin, u_x, u_z, device_geometry, plot_path)
            print(f"  -> Saved coord plot: {plot_path}")

    if not processed_data_list:
        raise RuntimeError("No processed data. Please check the input files.")

    final_data = pd.concat(processed_data_list, ignore_index=True)

    # 센서만 표준화
    scaler = StandardScaler()
    sensor_columns = [c for c in final_data.columns if c.startswith('S_')]
    final_data[sensor_columns] = scaler.fit_transform(final_data[sensor_columns])

    # 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv    = os.path.join(data_dir,  f'processed_training_data_{timestamp}.csv')
    output_scaler = os.path.join(model_dir, f'sensor_scaler_{timestamp}.joblib')

    final_data.to_csv(output_csv, index=False)
    joblib.dump(scaler, output_scaler)

    print(f"[Done] Merged & processed data: {output_csv}")
    print(f"[Done] Scaler saved:          {output_scaler}")
