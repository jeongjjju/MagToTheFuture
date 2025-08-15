import sys
import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox
from PyQt6.QtCore import QTimer

class MotorTester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Motor Control & Position Test")
        self.setGeometry(200, 200, 400, 250)
        
        self.arduino = None
        
        # --- UI 구성 ---
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        self.setCentralWidget(central_widget)

        # 포트 선택
        self.port_combo = QComboBox()
        self.populate_ports()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setCheckable(True)
        self.connect_btn.clicked.connect(self.toggle_connection)
        
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("COM Port:"))
        port_layout.addWidget(self.port_combo, 1)
        port_layout.addWidget(self.connect_btn)
        main_layout.addLayout(port_layout)

        # 상태 및 위치 표시
        self.status_label = QLabel("Status: Disconnected")
        self.position_label = QLabel("Position: X=0, Y=0")
        self.position_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.position_label)

        # 제어 버튼
        up_btn = QPushButton("Up (w)")
        down_btn = QPushButton("Down (s)")
        left_btn = QPushButton("Left (a)")
        right_btn = QPushButton("Right (d)")
        stop_btn = QPushButton("Stop (q)")
        
        # 버튼을 누르고 있을 때만 명령 전송
        up_btn.pressed.connect(lambda: self.send_command('w'))
        down_btn.pressed.connect(lambda: self.send_command('s'))
        left_btn.pressed.connect(lambda: self.send_command('a'))
        right_btn.pressed.connect(lambda: self.send_command('d'))
        
        # 버튼에서 떼면 정지 명령 전송
        up_btn.released.connect(lambda: self.send_command('q'))
        down_btn.released.connect(lambda: self.send_command('q'))
        left_btn.released.connect(lambda: self.send_command('q'))
        right_btn.released.connect(lambda: self.send_command('q'))
        stop_btn.clicked.connect(lambda: self.send_command('q'))

        # 레이아웃 배치
        grid = QVBoxLayout()
        grid.addWidget(up_btn)
        h_layout = QHBoxLayout()
        h_layout.addWidget(left_btn)
        h_layout.addWidget(stop_btn)
        h_layout.addWidget(right_btn)
        grid.addLayout(h_layout)
        grid.addWidget(down_btn)
        
        main_layout.addStretch()
        main_layout.addLayout(grid)
        main_layout.addStretch()

        # 시리얼 데이터 수신을 위한 타이머
        self.serial_timer = QTimer(self)
        self.serial_timer.timeout.connect(self.read_serial_data)

    def populate_ports(self):
        self.port_combo.clear()
        for port in serial.tools.list_ports.comports():
            self.port_combo.addItem(port.device)

    def toggle_connection(self):
        if self.connect_btn.isChecked():
            port = self.port_combo.currentText()
            try:
                self.arduino = serial.Serial(port, 115200, timeout=0.1)
                self.serial_timer.start(50) # 50ms 마다 데이터 확인
                self.status_label.setText(f"Status: Connected to {port}")
                self.connect_btn.setText("Disconnect")
            except serial.SerialException as e:
                self.status_label.setText("Status: Connection Failed!")
                self.connect_btn.setChecked(False)
        else:
            self.serial_timer.stop()
            if self.arduino:
                self.send_command('q') # 연결 끊기 전 정지
                self.arduino.close()
                self.arduino = None
            self.status_label.setText("Status: Disconnected")
            self.connect_btn.setText("Connect")

    def send_command(self, cmd):
        if self.arduino and self.arduino.is_open:
            self.arduino.write(cmd.encode())
            print(f"Sent: {cmd}") # 디버깅용

    def read_serial_data(self):
        if self.arduino and self.arduino.in_waiting > 0:
            try:
                line = self.arduino.readline().decode('utf-8').strip()
                if line.startswith("POS,"):
                    parts = line.split(',')
                    if len(parts) == 3:
                        x, y = parts[1], parts[2]
                        self.position_label.setText(f"Position: X={x}, Y={y}")
                elif line:
                     print(f"Arduino says: {line}") # 다른 메시지 출력
            except Exception as e:
                pass # 디코딩 오류 등은 무시
                
    def closeEvent(self, event):
        self.serial_timer.stop()
        if self.arduino:
            self.send_command('q')
            self.arduino.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MotorTester()
    window.show()
    sys.exit(app.exec())