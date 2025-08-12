import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from scipy.fft import fft, fftfreq
from scipy.signal import butter, filtfilt, detrend, get_window # 신호 처리를 위한 라이브러리 추가
import os

# --- 1. 기본 설정 ---
# Matplotlib 기본 폰트 및 크기 설정
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['font.size'] = 12
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.linestyle'] = '--'
plt.rcParams['grid.alpha'] = 0.7

# 데이터 경로 설정
BASE_DIR = r'F:\\' 

# 분석할 재질 폴더 및 색상 매핑 (이전 색상으로 복원)
MATERIAL_COLORS = {
    'Aluminium': '#1f77b4',
    'Arcylic':   '#ff7f0e',
    'FoamBoard': '#2ca02c',
    'MDF':       '#d62728',
    'PLA':       '#9467bd',
    'Silicon':   '#8c564b',
}
MATERIALS = list(MATERIAL_COLORS.keys())

# 분석할 모드 및 방향
MODES_TO_ANALYZE = {
    'FORCE_RAMP': {'x_axis': 'DutyCycle', 'x_label': 'Duty Cycle', 'x_lim': (0, 255)},
    'VIB_RAMP': {'x_axis': 'DutyCycle', 'x_label': 'Duty Cycle', 'x_lim': (0, 255)},
    'FREQ_SWEEP': {'x_axis': 'Frequency', 'x_label': 'Frequency (Hz)', 'x_lim': (0, 500)}
}
DIRECTIONS_TO_ANALYZE = ['ATTRACTION', 'REPULSION']

# 결과 저장 경로
OUTPUT_DIR = os.path.join(BASE_DIR, 'output_plots')
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

    for mode, params in MODES_TO_ANALYZE.items():
        for direction in DIRECTIONS_TO_ANALYZE:
            print(f"\n>>> 처리 중: Mode='{mode}', Direction='{direction}'")

            fig_comp, ax_comp = plt.subplots(figsize=(10, 7))
            ax_comp.set_title(f'Comparison: {mode} - {direction}', fontsize=16, weight='bold')
            ax_comp.set_xlabel(params['x_label'], fontsize=14)
            ax_comp.set_ylabel('L01_Value', fontsize=14)
            ax_comp.set_xlim(params['x_lim'])

            # FREQ_SWEEP 모드일 경우, 막대 그래프에 사용할 데이터 프레임 초기화
            if mode == 'FREQ_SWEEP':
                peak_data_for_barchart = {'Frequency': np.arange(10, 501, 10)}

            for material in MATERIALS:
                file_path = os.path.join(BASE_DIR, f"{material}.csv")
                
                if not os.path.exists(file_path):
                    print(f"  - 경고: 파일을 찾을 수 없습니다. 건너뜁니다: {file_path}")
                    continue

                df = pd.read_csv(file_path)
                
                # --- MDF와 Aluminium의 Direction 스왑 로직 ---
                actual_direction = direction
                if material in ['MDF', 'Aluminium']:
                    if direction == 'ATTRACTION':
                        actual_direction = 'REPULSION'
                    else: # direction == 'REPULSION'
                        actual_direction = 'ATTRACTION'
                    print(f"  - 정보: '{material}'의 방향을 '{direction}' -> '{actual_direction}'(으)로 스왑하여 처리합니다.")
                
                df_filtered = df[(df['Mode'] == mode) & (df['Direction'] == actual_direction)].copy()

                if df_filtered.empty:
                    print(f"  - 정보: '{material}'에서 조건(Mode='{mode}', Direction='{actual_direction}')에 맞는 데이터를 찾을 수 없습니다.")
                    continue
                
                df_filtered['L01_Value'] = pd.to_numeric(df_filtered['L01_Value'], errors='coerce')
                df_filtered.dropna(subset=['L01_Value'], inplace=True)

                x_data = df_filtered[params['x_axis']]
                y_data = df_filtered['L01_Value']
                color = MATERIAL_COLORS[material]
                
                material_output_dir = os.path.join(OUTPUT_DIR, material)
                os.makedirs(material_output_dir, exist_ok=True)

                fig_ind, ax_ind = plt.subplots(figsize=(8, 6))
                ax_ind.set_title(f'{material}: {mode} - {direction}', fontsize=16, weight='bold')
                ax_ind.set_xlabel(params['x_label'], fontsize=14)
                ax_ind.set_ylabel('L01_Value', fontsize=14)
                ax_ind.set_xlim(params['x_lim'])
                
                if mode in ['FORCE_RAMP', 'VIB_RAMP']:
                    ax_ind.plot(x_data, y_data, 'o', color=color, alpha=0.2, markersize=3, label='Raw Data (Outliers)')
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
                             raise RuntimeError("Not enough data for fitting")
                        ax_ind.plot(x_data_clean, y_data_clean, '-', color=color, alpha=0.8, linewidth=1.5, label='Filtered Data')
                        sorted_indices = np.argsort(x_data_clean)
                        x_data_sorted = x_data_clean.iloc[sorted_indices]
                        y_data_sorted = y_data_clean.iloc[sorted_indices]
                        popt, _ = curve_fit(poly2, x_data_sorted, y_data_sorted)
                        r2 = r_squared(y_data_sorted, poly2(x_data_sorted, *popt))
                        x_fit = np.linspace(params['x_lim'][0], params['x_lim'][1], 400)
                        y_fit = poly2(x_fit, *popt)
                        fit_label_ind = f'Fit: y={popt[0]:.2e}x²+{popt[1]:.2e}x+{popt[2]:.2f}\n$R^2$={r2:.4f}'
                        ax_ind.plot(x_fit, y_fit, '--', color='black', linewidth=2, label=fit_label_ind)
                        fit_label_comp = f'{material} ($R^2$={r2:.3f})'
                        ax_comp.plot(x_fit, y_fit, '-', color=color, linewidth=2.5, label=fit_label_comp)
                    except RuntimeError as e:
                        print(f"  - 경고: '{material}'의 {mode}, {direction} 데이터 피팅 실패. ({e})")
                        sorted_indices = np.argsort(x_data)
                        ax_comp.plot(x_data.iloc[sorted_indices], y_data.iloc[sorted_indices], '-', color=color, linewidth=2.5, label=f'{material} (No Fit)')

                elif mode == 'FREQ_SWEEP':
                    ax_ind.plot(x_data, y_data, '-', color=color, alpha=0.8, linewidth=1.5, label='Raw Data')
                    ax_comp.plot(x_data, y_data, '-', color=color, linewidth=2, label=material)
                    N = len(y_data)
                    if N > 1:
                        time_us = df_filtered['Timestamp (us)'].to_numpy()
                        T = np.mean(np.diff(time_us)) / 1e6
                        if T > 0:
                            fs = 1.0 / T
                            y_detrended = detrend(y_data)
                            lowcut = 8.0
                            highcut = 505.0
                            nyq = 0.5 * fs
                            low = lowcut / nyq
                            high = highcut / nyq
                            b, a = butter(4, [low, high], btype='band')
                            y_filtered = filtfilt(b, a, y_detrended)
                            window = get_window('hann', N)
                            y_windowed = y_filtered * window
                            yf_processed = fft(y_windowed)
                            xf = fftfreq(N, T)[:N//2]
                            magnitudes = 2.0/N * np.abs(yf_processed[0:N//2])
                            
                            fig_fft_ind, ax_fft_ind = plt.subplots(figsize=(8, 6))
                            ax_fft_ind.set_title(f'FFT (Preprocessed): {material} - {direction}', fontsize=16, weight='bold')
                            ax_fft_ind.set_xlabel('Frequency (Hz)', fontsize=14)
                            ax_fft_ind.set_ylabel('FFT Magnitude', fontsize=14)
                            ax_fft_ind.plot(xf, magnitudes, color=color)
                            ax_fft_ind.set_xlim(0, 505)
                            for freq_marker in range(10, 501, 10):
                                ax_fft_ind.axvline(x=freq_marker, color='grey', linestyle=':', linewidth=0.8, alpha=0.7)
                            fft_save_path = os.path.join(material_output_dir, f'FFT_Processed_{mode}_{direction}.png')
                            plot_and_save(fig_fft_ind, fft_save_path)

                            # --- 피크 값 찾아서 막대 그래프용 데이터로 저장 ---
                            magnitudes_at_targets = []
                            for target_freq in range(10, 501, 10):
                                window_half_width = 2.5
                                freq_min = target_freq - window_half_width
                                freq_max = target_freq + window_half_width
                                indices_in_window = np.where((xf >= freq_min) & (xf <= freq_max))
                                if indices_in_window[0].size > 0:
                                    peak_mag = np.max(magnitudes[indices_in_window])
                                    magnitudes_at_targets.append(peak_mag)
                                else:
                                    magnitudes_at_targets.append(0)
                            peak_data_for_barchart[material] = magnitudes_at_targets

                ax_ind.legend()
                ind_save_path = os.path.join(material_output_dir, f'{mode}_{direction}.png')
                plot_and_save(fig_ind, ind_save_path)

            ax_comp.legend()
            comp_save_path = os.path.join(OUTPUT_DIR, f'Comparison_{mode}_{direction}.png')
            plot_and_save(fig_comp, comp_save_path)

            if mode == 'FREQ_SWEEP':
                # --- 모든 재질 데이터 수집 후 그룹 막대 그래프 생성 ---
                df_peaks = pd.DataFrame(peak_data_for_barchart)
                df_peaks.set_index('Frequency', inplace=True)

                fig_bar, ax_bar = plt.subplots(figsize=(18, 8))
                df_peaks.plot(
                    kind='bar',
                    ax=ax_bar,
                    color=[MATERIAL_COLORS.get(col) for col in df_peaks.columns],
                    width=0.8
                )
                ax_bar.set_title(f'FFT Peak Comparison: {mode} - {direction}', fontsize=16, weight='bold')
                ax_bar.set_xlabel('Frequency (Hz)', fontsize=14)
                ax_bar.set_ylabel('Peak FFT Magnitude', fontsize=14)
                ax_bar.legend(title='Material', bbox_to_anchor=(1.01, 1), loc='upper left')
                ax_bar.tick_params(axis='x', rotation=45)
                
                bar_save_path = os.path.join(OUTPUT_DIR, f'Comparison_FFT_BarChart_{mode}_{direction}.png')
                plot_and_save(fig_bar, bar_save_path)

    print("\n✅ 모든 분석 및 시각화 작업이 완료되었습니다.")

if __name__ == '__main__':
    main()
