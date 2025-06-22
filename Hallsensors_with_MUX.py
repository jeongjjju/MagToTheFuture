# 필요한 라이브러리를 가져옵니다.
import time
import board
import adafruit_tca9548a
import adafruit_mlx90393

# --- 설정: MUX 주소와 사용할 채널 번호를 여기에 지정합니다 ---
MUX_ADDRESS = 0x70
SENSOR_CHANNEL = 4
SENSOR_ADDRESS = 0x18
# -----------------------------------------------------------

print("Initializing I2C bus...")
# Jetson Nano의 기본 I2C 버스를 초기화합니다.
# board.SCL, board.SDA를 사용합니다.
try:
    i2c = board.I2C()
except Exception as e:
    print("Failed to initialize I2C bus.")
    print("Please ensure I2C is enabled on your Jetson Nano using 'sudo /opt/nvidia/jetson-io/jetson-io.py'")
    print(f"Error: {e}")
    exit()

print(f"Looking for MUX at address 0x{MUX_ADDRESS:02X}...")
# TCA9548A MUX 객체를 생성합니다.
try:
    tca = adafruit_tca9548a.TCA9548A(i2c, address=MUX_ADDRESS)
except ValueError:
    print("Failed to find MUX. Check wiring and address.")
    exit()

print(f"Single Sensor Test on MUX CH {SENSOR_CHANNEL}")

# MUX의 지정된 채널에 센서 초기화를 시도합니다.
# tca[SENSOR_CHANNEL]은 해당 채널 전용의 I2C 버스처럼 동작합니다.
try:
    print("Initializing sensor... ")
    mlx = adafruit_mlx90393.MLX90393(tca[SENSOR_CHANNEL], address=SENSOR_ADDRESS)
    
    # 고품질 측정을 위해 센서 내부 필터링을 최대로 설정
    mlx.filter = adafruit_mlx90393.FILTER_7
    mlx.oversampling = adafruit_mlx90393.OSR_3
    
    print("OK")

except (ValueError, OSError) as e:
    print(f"FAILED! Could not find sensor on MUX channel {SENSOR_CHANNEL}.")
    print("Check wiring on the specified channel.")
    print(f"Error: {e}")
    exit() # 센서가 없으면 여기서 멈춤

# 시리얼 플로터용 헤더(범례) 출력
print("\nX-Axis,Y-Axis,Z-Axis")
print("Initialization complete. Starting 10-second interval measurements.")

# 메인 루프 (아두이노의 loop()와 동일)
while True:
    try:
        # 데이터 읽기
        mag_x, mag_y, mag_z = mlx.magnetic

        # 플로터 형식으로 출력
        print(f"{mag_x},{mag_y},{mag_z}")

        # 10초 대기
        time.sleep(10)

    except KeyboardInterrupt:
        # Ctrl+C를 누르면 프로그램을 종료합니다.
        print("\nProgram stopped by user.")
        break
    except (ValueError, OSError) as e:
        # 통신 중 에러가 발생하면 메시지를 출력하고 계속 시도합니다.
        print(f"Error reading sensor: {e}")

