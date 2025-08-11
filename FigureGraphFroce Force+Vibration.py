import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
import os

# --- 1. 기본 설정 ---
# Matplotlib 기본 폰트 및 크기 설정
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 12
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.linestyle'] = '--'
plt.rcParams['grid.alpha'] = 0.7

# 데이터 경로 설정
BASE_DIR = r'G:\MagToTheFuture\0727' 

# 분석할 재질 폴더 및 색상 매핑
MATERIAL_COLORS = {
    'Aluminium': '#1f77b4',
    'Arcylic':   '#ff7f0e',
    'FoamBoard': '#2ca02c',
    'MDF':       '#d62728',
    'PLA':       '#9467bd',
    'Silicon':   '#8c564b',
}
MATERIALS = list(MATERIAL_COLORS.keys())

# 분석할 파일 및 해당 파일의 모드 정보 매핑
FILES_TO_PROCESS = {
    'Force_attraction.csv': {'mode': 'FORCE_RAMP'},
    'Force_repulsion.csv': {'mode': 'FORCE_RAMP'},
    'Force+vibration_attraction.csv': {'mode': 'VIB_RAMP'},
    'Force+vibration_repulsion.csv': {'mode': 'VIB_RAMP'},
    'Thermal.csv': {'mode': 'THERMAL'} # Thermal 파일 추가
}

# 결과 저장 경로
OUTPUT_DIR = os.path.join(BASE_DIR, 'output_plots')
COMPARISON_DIR = os.path.join(OUTPUT_DIR, 'Comparison')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(COMPARISON_DIR, exist_ok=True)

# --- 2. 헬퍼 함수 ---
def poly2(x, a, b, c):
    """2차 다항식 함수"""
    return a * x**2 + b * x + c

def r_squared(y_true, y_pred):
    """R-squared (결정 계수) 계산 함수"""
    ss_res = np.sum((y_true - y_pred)**2)
    ss_tot = np.sum((y_true - np.mean(y_true))**2)
    if ss_tot == 0:
        return 1.0
    return 1 - (ss_res / ss_tot)

def plot_and_save(fig, save_path):
    """그래프를 저장하고 닫는 함수"""
    fig.tight_layout()
    fig.savefig(save_path, dpi=300)
    plt.close(fig)
    print(f"  - 그래프 저장 완료: {save_path}")

# --- 3. 메인 분석 및 시각화 로직 ---
def main():
    print("데이터 시각화 및 분석을 시작합니다.")

    # --- 3.1 개별 그래프 생성 ---
    print("\n--- 1. 개별 재질 그래프 생성 중 ---")
    for material in MATERIALS:
        material_path = os.path.join(BASE_DIR, material)
        output_material_path = os.path.join(OUTPUT_DIR, material)
        os.makedirs(output_material_path, exist_ok=True)
        
        print(f"\n[처리 중: {material}]")

        for file_name, info in FILES_TO_PROCESS.items():
            file_path = os.path.join(material_path, file_name)
            
            if not os.path.exists(file_path):
                print(f"  - 정보: 파일을 찾을 수 없습니다: {file_path}")
                continue

            df = pd.read_csv(file_path)
            
            fig, ax = plt.subplots(figsize=(8, 6))
            title_base = os.path.splitext(file_name)[0].replace('_', ' ').replace('+', ' + ')
            ax.set_title(f'{material} - {title_base}', fontsize=16, weight='bold')

            if info['mode'] == 'THERMAL':
                if 'Time' not in df.columns or 'Thermal' not in df.columns:
                    print(f"  - 정보: '{file_name}'에 'Time' 또는 'Thermal' 열이 없습니다.")
                    plt.close(fig)
                    continue
                x_data = df['Time']
                y_data = df['Thermal']
                ax.set_xlabel('Time (s)', fontsize=14)
                ax.set_ylabel('Thermal Value', fontsize=14)
            else: # FORCE_RAMP, VIB_RAMP
                df_filtered = df[df['Mode'] == info['mode']].copy()
                if df_filtered.empty:
                    print(f"  - 정보: '{file_name}'에서 해당 모드('{info['mode']}')의 데이터를 찾을 수 없습니다.")
                    plt.close(fig)
                    continue
                initial_value = df_filtered['RawLoadCellValue'].iloc[0]
                df_filtered['Normalized_Value'] = df_filtered['RawLoadCellValue'] - initial_value
                x_data = df_filtered['DutyCycle']
                y_data = df_filtered['Normalized_Value']
                ax.set_xlabel('DutyCycle', fontsize=14)
                ax.set_ylabel('Normalized Load Cell Value', fontsize=14)
                ax.set_xlim(0, 255)

            color = MATERIAL_COLORS[material]

            # 이상치 제거 및 2차 함수 피팅
            # ax.plot(x_data, y_data, 'o', color=color, alpha=0.2, markersize=3, label='Raw Data') # 원본 데이터 점 그래프 비활성화
            try:
                Q1 = y_data.quantile(0.25)
                Q3 = y_data.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                outlier_condition = (y_data >= lower_bound) & (y_data <= upper_bound)
                x_data_clean = x_data[outlier_condition]
                y_data_clean = y_data[outlier_condition]

                if len(y_data_clean) < 3:
                    raise RuntimeError("피팅에 필요한 데이터 부족")

                ax.plot(x_data_clean, y_data_clean, '-', color=color, alpha=0.8, linewidth=1.5, label='Filtered Data')
                
                sorted_indices = np.argsort(x_data_clean)
                x_data_sorted = x_data_clean.iloc[sorted_indices]
                y_data_sorted = y_data_clean.iloc[sorted_indices]
                
                popt, _ = curve_fit(poly2, x_data_sorted, y_data_sorted)
                r2 = r_squared(y_data_sorted, poly2(x_data_sorted, *popt))
                
                x_fit = np.linspace(x_data_sorted.min(), x_data_sorted.max(), 400)
                y_fit = poly2(x_fit, *popt)
                
                fit_label = f'Fit: y={popt[0]:.2e}x²+{popt[1]:.2e}x+{popt[2]:.2f}\n$R^2$={r2:.4f}'
                ax.plot(x_fit, y_fit, '--', color='black', linewidth=2, label=fit_label)

            except Exception as e:
                print(f"  - 경고: {file_name} 피팅 실패. ({e})")

            ax.legend()
            save_path = os.path.join(output_material_path, f'{os.path.splitext(file_name)[0]}.png')
            plot_and_save(fig, save_path)

    # --- 3.2 통합 비교 그래프 생성 ---
    print("\n--- 2. 통합 비교 그래프 생성 중 ---")
    for file_name, info in FILES_TO_PROCESS.items():
        fig, ax = plt.subplots(figsize=(10, 7))
        title_base = os.path.splitext(file_name)[0].replace('_', ' ').replace('+', ' + ')
        ax.set_title(f'Material Comparison - {title_base}', fontsize=16, weight='bold')
        
        is_thermal = (info['mode'] == 'THERMAL')
        if is_thermal:
            ax.set_xlabel('Time (s)', fontsize=14)
            ax.set_ylabel('Thermal Value', fontsize=14)
        else:
            ax.set_xlabel('DutyCycle', fontsize=14)
            ax.set_ylabel('Normalized Load Cell Value', fontsize=14)
            ax.set_xlim(0, 255)

        print(f"\n[비교 그래프 생성: {title_base}]")

        for material in MATERIALS:
            file_path = os.path.join(BASE_DIR, material, file_name)
            
            if not os.path.exists(file_path):
                continue

            df = pd.read_csv(file_path)
            
            if is_thermal:
                if 'Time' not in df.columns or 'Thermal' not in df.columns:
                    continue
                x_data = df['Time']
                y_data = df['Thermal']
            else:
                df_filtered = df[df['Mode'] == info['mode']].copy()
                if df_filtered.empty:
                    continue
                initial_value = df_filtered['RawLoadCellValue'].iloc[0]
                df_filtered['Normalized_Value'] = df_filtered['RawLoadCellValue'] - initial_value
                x_data = df_filtered['DutyCycle']
                y_data = df_filtered['Normalized_Value']

            color = MATERIAL_COLORS[material]

            try:
                Q1 = y_data.quantile(0.25)
                Q3 = y_data.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                outlier_condition = (y_data >= lower_bound) & (y_data <= upper_bound)
                x_data_clean = x_data[outlier_condition]
                y_data_clean = y_data[outlier_condition]

                if len(y_data_clean) < 3:
                     raise RuntimeError("피팅에 필요한 데이터 부족")

                sorted_indices = np.argsort(x_data_clean)
                x_data_sorted = x_data_clean.iloc[sorted_indices]
                y_data_sorted = y_data_clean.iloc[sorted_indices]
                
                popt, _ = curve_fit(poly2, x_data_sorted, y_data_sorted)
                r2 = r_squared(y_data_sorted, poly2(x_data_sorted, *popt))
                
                x_fit = np.linspace(x_data_sorted.min(), x_data_sorted.max(), 400)
                y_fit = poly2(x_fit, *popt)
                
                ax.plot(x_fit, y_fit, '-', color=color, linewidth=2.5, label=f'{material} ($R^2$={r2:.3f})')

            except Exception as e:
                print(f"  - 경고: {material} 피팅 실패, 원본 데이터로 표시. ({e})")
                sorted_indices = np.argsort(x_data)
                ax.plot(x_data.iloc[sorted_indices], y_data.iloc[sorted_indices], '--', color=color, linewidth=2, label=f'{material} (No Fit)')

        ax.legend()
        save_path = os.path.join(COMPARISON_DIR, f'Comparison_{os.path.splitext(file_name)[0]}.png')
        plot_and_save(fig, save_path)

    print("\n✅ 모든 분석 및 시각화 작업이 완료되었습니다.")

if __name__ == '__main__':
    main()
