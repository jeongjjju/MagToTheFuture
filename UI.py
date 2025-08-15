import sys
import math
import random
import serial
import serial.tools.list_ports
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsPathItem, QListWidget, QListWidgetItem, QLabel, QGroupBox,
    QCheckBox, QAbstractItemView, QGraphicsEllipseItem, QTabWidget, QSlider,
    QLineEdit, QComboBox, QFormLayout, QGraphicsPolygonItem, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import (
    QColor, QBrush, QPen, QPainterPath, QFont, QPainter,
    QIntValidator, QCursor, QIcon, QPolygonF, QDoubleValidator
)
from PyQt6.QtCore import Qt, QPointF, QTimer, QSize, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF, QPoint

# --- 상수 정의 ---
DEVICE_WIDTH_MM = 350
DEVICE_HEIGHT_MM = 260
HAPTIC_ICONS = {"force": "🖐️", "vibration": "📳", "heat": "🔥"}
PATCH_COLORS = [
    QColor("#0D6EFD"), QColor("#6F42C1"), QColor("#D63384"),
    QColor("#FD7E14"), QColor("#198754"), QColor("#0DCAF0"),
    QColor("#FFC107")
]
# 아두이노의 스텝 값과 UI의 mm 값을 맞추기 위한 변환 계수
STEPS_PER_MM_X = 80.0
STEPS_PER_MM_Y = 80.0

# --- UI와 실제 움직임 간의 배율 보정 상수 ---
UI_TO_REAL_SCALE_X = 1.75
UI_TO_REAL_SCALE_Y = 8.5


# --- UI 테마 스타일시트 ---
STYLESHEET = """
QWidget {
    background-color: #FFFFFF;
    color: #212529;
    font-family: 'Inter', 'Malgun Gothic', 'Segoe UI', sans-serif;
}
QGroupBox {
    font-size: 14px; font-weight: 500; border: 1px solid #E9ECEF;
    border-radius: 12px; margin-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left;
    padding: 0 10px; margin-left: 10px; color: #495057;
}
QPushButton {
    background-color: #F8F9FA; border: 1px solid #DEE2E6; border-radius: 8px;
    padding: 8px 12px; font-size: 13px; font-weight: 500;
}
QPushButton:hover { background-color: #F1F3F5; }
QPushButton:pressed { background-color: #E9ECEF; }
QPushButton#PrimaryButton {
    background-color: #0D6EFD; color: white; font-weight: bold; border: none;
}
QPushButton#PrimaryButton:hover { background-color: #0B5ED7; }
QPushButton#DangerButton {
    background-color: #DC3545; color: white; border: none;
}
QPushButton#DangerButton:hover { background-color: #BB2D3B; }
QListWidget {
    border: 1px solid #DEE2E6; border-radius: 8px; padding: 5px;
}
QListWidget::item { padding: 12px; }
QListWidget::item:hover { background-color: #F5F5F5; }
QListWidget::item:selected { background-color: #D0E4FF; color: #000; border-radius: 5px; }
QLabel#HintLabel { color: #6C757D; }
QLabel { font-size: 13px; }
QLineEdit, QComboBox {
    border: 1px solid #CED4DA; border-radius: 6px; padding: 6px; min-height: 20px;
}
QTabWidget::pane { border-top: 1px solid #DEE2E6; }
QTabBar::tab {
    padding: 10px 15px; border-bottom: 2px solid transparent; font-weight: 500;
}
QTabBar::tab:selected {
    color: #0D6EFD; border-bottom-color: #0D6EFD; font-weight: 600;
}
"""

class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.duration = 200
        self._track_color = {True: QColor("#0D6EFD"), False: QColor("#CED4DA")}; self._handle_color = QColor("#FFFFFF")
        self._handle_position = 0
        self.animation = QPropertyAnimation(self, b"handle_position", self); self.animation.setDuration(self.duration); self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.stateChanged.connect(self.on_state_changed)
    @pyqtProperty(float)
    def handle_position(self): return self._handle_position
    @handle_position.setter
    def handle_position(self, pos): self._handle_position = pos; self.update()
    def on_state_changed(self, state):
        self.animation.stop(); self.animation.setEndValue(1 if state else 0); self.animation.start()
    def paintEvent(self, e):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing); painter.setPen(Qt.PenStyle.NoPen)
        track_height = 18; handle_size = 12; track_radius = track_height / 2
        track_rect = QRectF(0, (self.height() - track_height) / 2, self.width() - 2, track_height)
        track_color = self._track_color[False].__class__(
            int(self._track_color[False].red() + (self._track_color[True].red() - self._track_color[False].red()) * self.handle_position),
            int(self._track_color[False].green() + (self._track_color[True].green() - self._track_color[False].green()) * self.handle_position),
            int(self._track_color[False].blue() + (self._track_color[True].blue() - self._track_color[False].blue()) * self.handle_position))
        painter.setBrush(track_color); painter.drawRoundedRect(track_rect, track_radius, track_radius)
        handle_y = (self.height() - handle_size) / 2
        handle_x = self.handle_position * (self.width() - track_height) + track_radius - handle_size / 2
        painter.setBrush(self._handle_color); painter.drawEllipse(int(handle_x), int(handle_y), handle_size, handle_size)
    def sizeHint(self): return QSize(40, 22)
    def hitButton(self, pos: QPoint): return self.contentsRect().contains(pos)

class LabeledSlider(QWidget):
    def __init__(self, text, min_val=0, max_val=100, suffix="%"):
        super().__init__()
        layout = QHBoxLayout(self); layout.setContentsMargins(0, 5, 0, 5)
        self.label = QLabel(text); self.slider = QSlider(Qt.Orientation.Horizontal); self.slider.setRange(min_val, max_val)
        self.value_label = QLabel(f"{self.slider.value()}{suffix}"); self.value_label.setMinimumWidth(50)
        layout.addWidget(self.label); layout.addWidget(self.slider); layout.addWidget(self.value_label)
        self.slider.valueChanged.connect(lambda v, s=suffix: self.value_label.setText(f"{v}{s}"))
    def value(self): return self.slider.value()
    def setValue(self, v): self.slider.setValue(v)

class GridScene(QGraphicsScene):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs); self.grid_size = 25; self.grid_color = QColor("#E9ECEF")
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        left = int(rect.left()) - int(rect.left()) % self.grid_size; top = int(rect.top()) - int(rect.top()) % self.grid_size
        lines = []; pen = QPen(self.grid_color)
        for x in range(left, int(rect.right()), self.grid_size): lines.append(QPointF(x, rect.top())); lines.append(QPointF(x, rect.bottom()))
        for y in range(top, int(rect.bottom()), self.grid_size): lines.append(QPointF(rect.left(), y)); lines.append(QPointF(rect.right(), y))
        painter.setPen(pen); painter.drawLines(lines)

class PatchItem(QGraphicsRectItem):
    def __init__(self, patch_id, x, y, color, parent=None):
        super().__init__(0, 0, 20, 30, parent)
        self.patch_id = patch_id
        self.color = color
        self.setPos(x, y); self.setBrush(QBrush(QColor("#FFFFFF"))); self.setPen(QPen(QColor("#ADB5BD"), 2)); self.setZValue(1)
        shadow = QGraphicsDropShadowEffect(); shadow.setBlurRadius(15); shadow.setColor(QColor(0, 0, 0, 80)); shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)
        text = QGraphicsTextItem(f"P{self.patch_id}", self); text.setFont(QFont("Inter", 8, QFont.Weight.Bold)); text.setDefaultTextColor(QColor("#495057")); text.setPos(1, -1)
        poly = QPolygonF([QPointF(10, 25), QPointF(6, 30), QPointF(14, 30)])
        indicator = QGraphicsPolygonItem(poly, self); indicator.setPen(QPen(Qt.PenStyle.NoPen)); indicator.setBrush(QBrush(QColor("#495057")))

    def select(self, is_selected):
        pen_color = self.color if is_selected else QColor("#ADB5BD")
        self.setPen(QPen(pen_color, 2.5 if is_selected else 2))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Haptic Orchestrator - 2 Arduino System")
        self.setGeometry(100, 100, 1600, 900)
        self.setStyleSheet(STYLESHEET)
        self.initialize_state()
        self.setup_ui()
        self.add_patch()
        self.patch_list.setCurrentRow(0)

    def initialize_state(self):
        self.sequence_blocks = []
        self.patch_items = {}
        self.selected_patch_id = None
        self.editing_block_index = None
        self.actuator_arduino = None
        self.transport_arduino = None
        self.is_hardware_running = False
        self.hardware_step_index = 0
        self.hardware_waypoint_index = 0
        self.is_transport_busy = False
        self.last_move_ok = False
        self.moving_patch_id = None
        self.trajectory_points = []
        self.current_trajectory_item = None
        self.is_simulating = False
        self.simulation_items = {}
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.simulation_step)
        self.initial_patch_positions = {}
        self.simulated_patch_states = {}
        self.actuator_pos = QPointF(0, 0)
        self.simulation_state = "IDLE"
        self.transport_read_timer = QTimer(self)
        self.transport_read_timer.timeout.connect(self.read_transport_data)

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        self.setCentralWidget(central_widget)

        left_panel = self.create_composer_panel()
        left_panel.setFixedWidth(400)
        right_panel = self.create_sequence_panel()
        right_panel.setFixedWidth(400)

        self.scene = GridScene(0, 0, DEVICE_WIDTH_MM, DEVICE_HEIGHT_MM)
        self.canvas = QGraphicsView(self.scene)
        self.canvas.setStyleSheet("background-color: #F1F3F5;")
        self.scene.setBackgroundBrush(QBrush(Qt.GlobalColor.white))
        self.canvas.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.canvas.mousePressEvent = self.canvas_mouse_press

        self.real_actuator_item = QGraphicsEllipseItem(-5, -5, 10, 10)
        self.real_actuator_item.setBrush(QBrush(QColor(220, 53, 69, 200))) # Red color
        self.real_actuator_item.setPen(QPen(Qt.PenStyle.NoPen))
        self.real_actuator_item.setZValue(10) # Always on top
        self.scene.addItem(self.real_actuator_item)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(self.canvas, 1)
        main_layout.addWidget(right_panel)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.fit_canvas_to_scene)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.fit_canvas_to_scene)

    def fit_canvas_to_scene(self):
        if self.canvas.scene():
            self.canvas.fitInView(self.canvas.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def create_composer_panel(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        hw_group = QGroupBox("Hardware Control")
        hw_layout = QFormLayout(hw_group)
        self.actuator_port_combo = QComboBox()
        self.transport_port_combo = QComboBox()
        self.refresh_ports_btn = QPushButton("Refresh Ports")
        self.refresh_ports_btn.clicked.connect(self.populate_ports)
        self.connect_btn = QPushButton("Connect All")
        self.connect_btn.setCheckable(True)
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.home_btn = QPushButton("Home Actuator")
        self.home_btn.clicked.connect(self.home_actuator)
        self.status_label = QLabel("Status: Disconnected")
        self.real_pos_label = QLabel("Real Pos: (0, 0)")
        hw_layout.addRow("Actuator Port:", self.actuator_port_combo)
        hw_layout.addRow("Transport Port:", self.transport_port_combo)
        hw_layout.addRow(self.refresh_ports_btn, self.connect_btn)
        hw_layout.addRow(self.home_btn)
        hw_layout.addRow(self.status_label)
        hw_layout.addRow(self.real_pos_label)
        self.populate_ports()

        patch_group = QGroupBox("Patch Control")
        patch_layout = QVBoxLayout(patch_group)
        self.patch_list = QListWidget()
        self.patch_list.setSpacing(5)
        self.patch_list.currentRowChanged.connect(self.on_patch_selected)
        patch_btn_layout = QHBoxLayout()
        self.add_patch_btn = QPushButton("➕ Add New Patch")
        self.add_patch_btn.clicked.connect(self.add_patch)
        self.remove_patch_btn = QPushButton("➖ Remove Selected")
        self.remove_patch_btn.setObjectName("DangerButton")
        self.remove_patch_btn.clicked.connect(self.remove_selected_patch)
        patch_btn_layout.addWidget(self.add_patch_btn)
        patch_btn_layout.addWidget(self.remove_patch_btn)
        patch_layout.addWidget(self.patch_list)
        patch_layout.addLayout(patch_btn_layout)

        composer_group = QGroupBox("Haptic Composer")
        composer_layout = QVBoxLayout(composer_group)
        self.tabs = QTabWidget()

        double_validator = QDoubleValidator()
        double_validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        # Force Tab
        force_tab = QWidget(); force_form = QFormLayout(force_tab); self.f_enabled = ToggleSwitch()
        f_enable_layout = QHBoxLayout(); f_enable_layout.addStretch(); f_enable_layout.addWidget(self.f_enabled); f_enable_layout.setContentsMargins(0,0,0,0)
        self.f_mode = QComboBox(); self.f_mode.addItems(["Attract", "Repel"])
        self.f_mag = LabeledSlider("Magnitude")
        self.f_dur = QLineEdit("3.0"); self.f_dur.setValidator(double_validator)
        force_form.addRow("Enable Force", f_enable_layout)
        force_form.addRow("Mode:", self.f_mode); force_form.addRow(self.f_mag); force_form.addRow("Duration (s):", self.f_dur)

        # Vibration Tab
        vib_tab = QWidget(); vib_form = QFormLayout(vib_tab); self.v_enabled = ToggleSwitch()
        v_enable_layout = QHBoxLayout(); v_enable_layout.addStretch(); v_enable_layout.addWidget(self.v_enabled); v_enable_layout.setContentsMargins(0,0,0,0)
        self.v_mode = QComboBox(); self.v_mode.addItems(["Attract", "Repel"])
        self.v_freq = LabeledSlider("Frequency", 1, 500, "Hz")
        self.v_amp = LabeledSlider("Amplitude"); self.v_dur = QLineEdit("3.0"); self.v_dur.setValidator(double_validator)
        vib_form.addRow("Enable Vibration", v_enable_layout); vib_form.addRow("Mode:", self.v_mode)
        vib_form.addRow(self.v_freq); vib_form.addRow(self.v_amp); vib_form.addRow("Duration (s):", self.v_dur)

        # Heat Tab
        heat_tab = QWidget(); heat_form = QFormLayout(heat_tab); self.h_enabled = ToggleSwitch()
        h_enable_layout = QHBoxLayout(); h_enable_layout.addStretch(); h_enable_layout.addWidget(self.h_enabled); h_enable_layout.setContentsMargins(0,0,0,0)
        self.h_dur = QLineEdit("3.0"); self.h_dur.setValidator(double_validator)
        heat_form.addRow("Enable Heat", h_enable_layout); heat_form.addRow("Duration (s):", self.h_dur)

        self.tabs.addTab(force_tab, "🖐️ Force"); self.tabs.addTab(vib_tab, "📳 Vibration"); self.tabs.addTab(heat_tab, "🔥 Heat")

        self.f_mode.currentTextChanged.connect(self.on_force_mode_changed)
        self.v_mode.currentTextChanged.connect(self.on_vibration_mode_changed)

        self.wait_for_move_cb = QCheckBox("Wait for previous move to complete")
        composer_layout.addWidget(self.tabs)
        composer_layout.addWidget(self.wait_for_move_cb)
        self.add_or_update_haptic_btn = QPushButton("➕ Add Haptic Block")
        self.add_or_update_haptic_btn.clicked.connect(self.add_or_update_haptic_block)
        composer_layout.addWidget(self.add_or_update_haptic_btn)

        main_layout.addWidget(hw_group)
        main_layout.addWidget(patch_group)
        main_layout.addWidget(composer_group)
        main_layout.addStretch(1)

        self.reset_composer_to_defaults()
        return main_widget

    def create_sequence_panel(self):
        main_widget = QWidget(); layout = QVBoxLayout(main_widget); layout.setContentsMargins(0,0,0,0)
        traj_group = QGroupBox("Trajectory Control")
        traj_layout = QFormLayout(traj_group)
        self.move_haptic_combo = QComboBox()
        self.move_haptic_combo.addItems(["None", "Force (Attraction)", "Vibration (Attraction)"])

        add_traj_btn = QPushButton("➡️ Add Drawn Trajectory")
        add_traj_btn.clicked.connect(self.add_trajectory_block)
        clear_traj_btn = QPushButton("🗑️ Clear Current Drawing")
        clear_traj_btn.clicked.connect(self.clear_all_drawn_trajectories)

        traj_btn_layout = QHBoxLayout()
        traj_btn_layout.addWidget(add_traj_btn)
        traj_btn_layout.addWidget(clear_traj_btn)

        traj_layout.addRow("Haptic on Move:", self.move_haptic_combo)
        traj_layout.addRow(traj_btn_layout)
        sequence_group = QGroupBox("Sequence Editor")
        seq_layout = QVBoxLayout(sequence_group); self.sequence_list = QListWidget()
        self.sequence_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.sequence_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.sequence_list.model().rowsMoved.connect(self.on_sequence_moved)
        self.sequence_list.itemDoubleClicked.connect(self.edit_sequence_block)
        btn_layout = QHBoxLayout(); self.delete_block_btn = QPushButton("Delete Selected");
        self.delete_block_btn.setObjectName("DangerButton"); self.delete_block_btn.clicked.connect(self.delete_sequence_block); btn_layout.addStretch(); btn_layout.addWidget(self.delete_block_btn)

        exec_group = QGroupBox("Execution"); exec_layout = QVBoxLayout(exec_group)
        sim_layout = QHBoxLayout()
        self.simulate_btn = QPushButton("▶️ Run Simulation"); self.simulate_btn.setObjectName("PrimaryButton")
        self.simulate_btn.clicked.connect(self.toggle_simulation)
        sim_layout.addWidget(self.simulate_btn)
        hw_layout = QHBoxLayout()
        self.send_to_hw_btn = QPushButton("🚀 Send to Actuator"); self.send_to_hw_btn.clicked.connect(self.run_hardware_sequence)
        self.stop_hw_btn = QPushButton("🛑 Emergency Stop")
        self.stop_hw_btn.setObjectName("DangerButton")
        self.stop_hw_btn.clicked.connect(self.emergency_stop)
        hw_layout.addWidget(self.send_to_hw_btn, 2); hw_layout.addWidget(self.stop_hw_btn, 1)
        exec_layout.addLayout(sim_layout); exec_layout.addLayout(hw_layout)

        seq_layout.addWidget(QLabel("Drag to reorder. Dbl-Click to edit.", objectName="HintLabel")); seq_layout.addWidget(self.sequence_list)
        seq_layout.addLayout(btn_layout); seq_layout.addWidget(exec_group)
        layout.addWidget(traj_group); layout.addWidget(sequence_group); layout.addStretch()
        return main_widget

    def on_force_mode_changed(self, text):
        self.v_mode.blockSignals(True)
        self.v_mode.setCurrentText(text)
        self.v_mode.blockSignals(False)

    def on_vibration_mode_changed(self, text):
        self.f_mode.blockSignals(True)
        self.f_mode.setCurrentText(text)
        self.f_mode.blockSignals(False)

    def reset_composer_to_defaults(self):
        self.f_enabled.setChecked(False)
        self.v_enabled.setChecked(False)
        self.h_enabled.setChecked(False)
        self.f_mode.setCurrentIndex(0)
        self.v_mode.setCurrentIndex(0)
        self.f_mag.setValue(100)
        self.v_amp.setValue(100)
        self.v_freq.setValue(100)
        self.f_dur.setText("3.0")
        self.v_dur.setText("3.0")
        self.h_dur.setText("3.0")
        self.wait_for_move_cb.setChecked(True)
        self.editing_block_index = None
        self.add_or_update_haptic_btn.setText("➕ Add Haptic Block")

    def populate_ports(self):
        self.actuator_port_combo.clear()
        self.transport_port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.actuator_port_combo.addItem(port.device)
            self.transport_port_combo.addItem(port.device)

    def toggle_connection(self):
        if self.connect_btn.isChecked():
            actuator_port = self.actuator_port_combo.currentText()
            transport_port = self.transport_port_combo.currentText()
            if not actuator_port or not transport_port:
                self.status_label.setText("Status: Both ports must be selected")
                self.connect_btn.setChecked(False); return
            if actuator_port == transport_port:
                self.status_label.setText("Status: Ports must be different")
                self.connect_btn.setChecked(False); return
            try:
                self.actuator_arduino = serial.Serial(actuator_port, 115200, timeout=1)
                self.transport_arduino = serial.Serial(transport_port, 115200, timeout=1)
                self.status_label.setText("Status: Ports opened. Checking devices...")
                QTimer.singleShot(2000, self.check_arduino_ready)
            except serial.SerialException as e:
                self.status_label.setText(f"Status: Error opening port: {e}")
                self.close_connections(set_disconnected_status=False)
        else:
            self.close_connections()

    def close_connections(self, set_disconnected_status=True):
        self.transport_read_timer.stop()
        if self.actuator_arduino and self.actuator_arduino.is_open: self.actuator_arduino.close()
        if self.transport_arduino and self.transport_arduino.is_open: self.transport_arduino.close()
        self.actuator_arduino, self.transport_arduino = None, None
        
        if set_disconnected_status:
            self.status_label.setText("Status: Disconnected")

        self.connect_btn.setText("Connect All")
        self.connect_btn.setChecked(False)

    def check_arduino_ready(self):
        try:
            self.status_label.setText("Status: Checking Transport...")
            QApplication.processEvents()
            self.transport_arduino.flushInput()
            self.transport_arduino.write(b"R\n")
            time.sleep(0.5)
            line = self.transport_arduino.readline().decode().strip()
            if "Ready" not in line:
                self.status_label.setText("Status: Transport not Ready!")
                self.close_connections(set_disconnected_status=False)
                return

            self.status_label.setText("Status: Transport OK. Checking Actuator...")
            QApplication.processEvents()

            self.actuator_arduino.flushInput()
            self.actuator_arduino.write(b"R\n")
            time.sleep(0.5)
            line = self.actuator_arduino.readline().decode().strip()
            if "Ready" not in line:
                self.status_label.setText("Status: Actuator not Ready!")
                self.close_connections(set_disconnected_status=False)
                return
            
            self.status_label.setText("Status: All devices connected")
            self.connect_btn.setText("Disconnect All")
            self.transport_read_timer.start(50)

        except Exception as e:
            self.status_label.setText(f"Status: Connection failed ({e})")
            self.close_connections(set_disconnected_status=False)

    def home_actuator(self):
        if self.transport_arduino and self.transport_arduino.is_open:
            print("Sending Home command to transport.")
            self.transport_arduino.write(b"H\n")
        else:
            print("Transport arduino not connected.")

    def read_transport_data(self):
        if not self.transport_arduino or not self.transport_arduino.in_waiting > 0:
            return
        
        try:
            response = self.transport_arduino.readline().decode().strip()
            if not response: return

            if response.startswith("POS,"):
                parts = response.split(',')
                if len(parts) == 3:
                    real_x_pos = float(parts[1]) / STEPS_PER_MM_X
                    real_y_pos = float(parts[2]) / STEPS_PER_MM_Y
                    
                    self.real_pos_label.setText(f"Real Pos: ({real_x_pos:.1f}, {real_y_pos:.1f})")
                    
                    ui_x_pos = real_x_pos / UI_TO_REAL_SCALE_X
                    ui_y_pos = real_y_pos / UI_TO_REAL_SCALE_Y
                    self.real_actuator_item.setPos(ui_x_pos, ui_y_pos)

                    if self.moving_patch_id is not None:
                        patch_to_move = self.patch_items.get(self.moving_patch_id)
                        if patch_to_move:
                            patch_new_pos = QPointF(ui_x_pos, ui_y_pos) - QPointF(10, 15)
                            patch_to_move.setPos(patch_new_pos)


            elif 'OK' in response:
                if self.is_transport_busy:
                    print(f"  - Transport says: {response}. Move complete.")
                    self.last_move_ok = True
            else:
                print(f"Transport says: {response}")
        except Exception as e:
            print(f"Error reading from transport: {e}")

    def emergency_stop(self):
        print("🛑 EMERGENCY STOP TRIGGERED!")
        if self.is_simulating: self.stop_simulation()
        self.stop_hardware_sequence(finished=False)

    def add_patch(self):
        patch_id = 1
        existing_ids = set(self.patch_items.keys())
        while patch_id in existing_ids:
            patch_id += 1

        x = random.uniform(10, DEVICE_WIDTH_MM - 30); y = random.uniform(10, DEVICE_HEIGHT_MM - 40)
        color = PATCH_COLORS[(patch_id - 1) % len(PATCH_COLORS)]
        patch_item = PatchItem(patch_id, x, y, color)
        self.scene.addItem(patch_item)
        self.patch_items[patch_id] = patch_item
        self.initial_patch_positions[patch_id] = QPointF(x, y)
        
        list_item = QListWidgetItem(f"Patch {patch_id}")
        list_item.setData(Qt.ItemDataRole.UserRole, patch_id)
        list_item.setForeground(color)
        self.patch_list.addItem(list_item)
        self.patch_list.setCurrentItem(list_item)

    # MODIFIED: 안정적인 삭제 로직
    def remove_selected_patch(self):
        if self.selected_patch_id is None: return
        
        patch_id_to_remove = self.selected_patch_id
        
        self.patch_list.blockSignals(True)

        self.sequence_blocks = [block for block in self.sequence_blocks if block['patch_id'] != patch_id_to_remove]
        
        patch_to_remove_item = self.patch_items.pop(patch_id_to_remove, None)
        if patch_to_remove_item:
            self.scene.removeItem(patch_to_remove_item)
        
        if patch_id_to_remove in self.initial_patch_positions:
            del self.initial_patch_positions[patch_id_to_remove]
        
        self.update_patch_list()
        self.update_sequence_list()
        self.update_all_patch_visuals()
        
        self.patch_list.blockSignals(False)
        self.on_patch_selected(self.patch_list.currentRow())
        
    def update_patch_list(self):
        last_selected_id = self.selected_patch_id
        
        current_item = self.patch_list.currentItem()
        current_id = current_item.data(Qt.ItemDataRole.UserRole) if current_item else -1

        self.patch_list.clear()
        
        sorted_ids = sorted(self.patch_items.keys())
        new_row_to_select = -1
        
        for i, patch_id in enumerate(sorted_ids):
            color = self.patch_items[patch_id].color
            list_item = QListWidgetItem(f"Patch {patch_id}")
            list_item.setData(Qt.ItemDataRole.UserRole, patch_id)
            list_item.setForeground(color)
            self.patch_list.addItem(list_item)
            if patch_id == current_id:
                new_row_to_select = i

        if self.patch_list.count() > 0:
            if new_row_to_select == -1:
                new_row_to_select = 0
            self.patch_list.setCurrentRow(new_row_to_select)
        else:
            self.patch_list.setCurrentRow(-1)


    def on_patch_selected(self, row):
        if row < 0:
            self.selected_patch_id = None
            if self.editing_block_index is not None: self.reset_composer_to_defaults()
        else:
            item = self.patch_list.item(row)
            if item:
                patch_id = item.data(Qt.ItemDataRole.UserRole)
                self.selected_patch_id = patch_id
        
        for pid, patch_item in self.patch_items.items():
            patch_item.select(pid == self.selected_patch_id)

    def canvas_mouse_press(self, event):
        if self.is_simulating or self.is_hardware_running or not self.selected_patch_id: return
        pos = self.canvas.mapToScene(event.pos())
        if not (0 <= pos.x() <= DEVICE_WIDTH_MM and 0 <= pos.y() <= DEVICE_HEIGHT_MM): return

        if not self.trajectory_points:
            start_pos = self.get_conceptual_patch_center(self.selected_patch_id)
            self.trajectory_points.append(start_pos)

        last_point = self.trajectory_points[-1]
        dx = abs(pos.x() - last_point.x())
        dy = abs(pos.y() - last_point.y())

        if dx > dy:
            new_point = QPointF(pos.x(), last_point.y())
        else:
            new_point = QPointF(last_point.x(), pos.y())

        self.trajectory_points.append(new_point)
        self.draw_current_trajectory()

    def get_conceptual_patch_center(self, patch_id):
        if patch_id not in self.patch_items: return QPointF(0, 0)
        
        # 패치의 현재 시각적 위치를 기준으로 계산
        current_visual_pos = self.patch_items[patch_id].pos()
        return current_visual_pos + QPointF(10, 15)


    def draw_current_trajectory(self):
        if self.current_trajectory_item: self.scene.removeItem(self.current_trajectory_item)
        if len(self.trajectory_points) < 2: return
        color = self.patch_items[self.selected_patch_id].color if self.selected_patch_id else QColor("#0D6EFD")
        pen = QPen(color, 2, Qt.PenStyle.DashLine)
        path = QPainterPath(); path.moveTo(self.trajectory_points[0])
        for point in self.trajectory_points[1:]: path.lineTo(point)
        self.current_trajectory_item = self.scene.addPath(path, pen)

    def clear_all_drawn_trajectories(self):
        if self.current_trajectory_item:
            self.scene.removeItem(self.current_trajectory_item)
            self.current_trajectory_item = None
        self.trajectory_points.clear()

    def add_trajectory_block(self):
        if len(self.trajectory_points) < 2 or not self.selected_patch_id: return
        move_haptic_type = self.move_haptic_combo.currentText()
        
        color = self.patch_items[self.selected_patch_id].color
        pen = QPen(color, 2, Qt.PenStyle.SolidLine)
        path_item = self.scene.addPath(self.current_trajectory_item.path(), pen)

        block = {
            "type": "MOVE",
            "patch_id": self.selected_patch_id,
            "trajectory": list(self.trajectory_points),
            "haptic_on_move": move_haptic_type,
            "path_item": path_item
        }
        
        self.scene.removeItem(self.current_trajectory_item)
        self.current_trajectory_item = None
        self.trajectory_points.clear()
        self.sequence_blocks.append(block)
        self.update_sequence_list()


    def add_or_update_haptic_block(self):
        if not self.selected_patch_id: return
        try:
            config = {
                "force": {"enabled": self.f_enabled.isChecked(), "mode": self.f_mode.currentText(), "magnitude": self.f_mag.value(), "duration": int(float(self.f_dur.text()) * 1000)},
                "vibration": {"enabled": self.v_enabled.isChecked(), "mode": self.v_mode.currentText(), "frequency": self.v_freq.value(), "amplitude": self.v_amp.value(), "duration": int(float(self.v_dur.text()) * 1000)},
                "heat": {"enabled": self.h_enabled.isChecked(), "duration": int(float(self.h_dur.text()) * 1000)},
                "wait_for_move": self.wait_for_move_cb.isChecked()
            }
        except (ValueError, TypeError):
            print("Error: Invalid duration value. Please enter a valid number.")
            return

        if not any(c['enabled'] for name, c in config.items() if name != 'wait_for_move'): return

        if self.editing_block_index is not None:
            self.sequence_blocks[self.editing_block_index]['config'] = config
        else:
            block = {"type": "HAPTIC", "patch_id": self.selected_patch_id, "config": config}
            self.sequence_blocks.append(block)

        self.update_sequence_list()
        self.reset_composer_to_defaults()

    def edit_sequence_block(self, item):
        row = self.sequence_list.row(item); block = self.sequence_blocks[row]
        if block['type'] == 'HAPTIC':
            self.editing_block_index = row; self.add_or_update_haptic_btn.setText("💾 Update Haptic Block")
            config = block['config']
            self.f_enabled.setChecked(config['force']['enabled']); self.f_mode.setCurrentText(config['force']['mode']); self.f_mag.setValue(config['force']['magnitude']); self.f_dur.setText(str(config['force']['duration'] / 1000.0))
            self.v_enabled.setChecked(config['vibration']['enabled']); self.v_mode.setCurrentText(config.get('vibration', {}).get('mode', 'Attract')); self.v_freq.setValue(config['vibration']['frequency']); self.v_amp.setValue(config['vibration']['amplitude']); self.v_dur.setText(str(config['vibration']['duration'] / 1000.0))
            self.h_enabled.setChecked(config['heat']['enabled']); self.h_dur.setText(str(config['heat']['duration'] / 1000.0))
            self.wait_for_move_cb.setChecked(config.get('wait_for_move', True))

            if config['force']['enabled']: self.tabs.setCurrentIndex(0)
            elif config['vibration']['enabled']: self.tabs.setCurrentIndex(1)
            elif config['heat']['enabled']: self.tabs.setCurrentIndex(2)

    def delete_sequence_block(self):
        selected_items = self.sequence_list.selectedItems()
        if not selected_items: return
        rows_to_delete = sorted([self.sequence_list.row(item) for item in selected_items], reverse=True)

        for row in rows_to_delete:
            block_to_delete = self.sequence_blocks[row]
            if block_to_delete.get('type') == 'MOVE' and 'path_item' in block_to_delete:
                path_item = block_to_delete.get('path_item')
                if path_item and path_item.scene():
                    self.scene.removeItem(path_item)
            del self.sequence_blocks[row]
        self.update_sequence_list()
        self.update_all_patch_visuals()


    def on_sequence_moved(self, parent, start, end, dest, row):
        item = self.sequence_blocks.pop(start); self.sequence_blocks.insert(row if row < start else row - 1, item)
        self.update_sequence_list()
        self.update_all_patch_visuals()

    def update_all_patch_visuals(self):
        for patch_id, patch_item in self.patch_items.items():
            if patch_id in self.initial_patch_positions:
                patch_item.setPos(self.initial_patch_positions[patch_id])

        for block in self.sequence_blocks:
            if block['type'] == 'MOVE' and block.get('haptic_on_move', 'None') != 'None':
                patch_id = block['patch_id']
                patch_item = self.patch_items.get(patch_id)
                if patch_item:
                    end_point = block['trajectory'][-1]
                    new_pos = end_point - QPointF(10, 15)
                    patch_item.setPos(new_pos)


    def update_sequence_list(self):
        current_selection_rows = {self.sequence_list.row(item) for item in self.sequence_list.selectedItems()}
        try: self.sequence_list.model().rowsMoved.disconnect()
        except TypeError: pass
        self.sequence_list.clear()

        for i, block in enumerate(self.sequence_blocks):
            patch_id = block['patch_id']
            color = self.patch_items.get(patch_id, PatchItem(0,0,0, QColor("black"))).color
            item = QListWidgetItem()
            if block['type'] == 'MOVE':
                item.setText(f"{i+1}. MOVE P{patch_id} Trajectory")
            else:
                enabled = [name for name, conf in block['config'].items() if isinstance(conf, dict) and conf.get('enabled')]
                icons = " ".join([HAPTIC_ICONS[m] for m in enabled])
                item.setText(f"{i+1}. HAPTIC on P{patch_id} {icons}")
            item.setForeground(color)
            self.sequence_list.addItem(item)

        for row in current_selection_rows:
            if row < self.sequence_list.count(): self.sequence_list.item(row).setSelected(True)
        self.sequence_list.model().rowsMoved.connect(self.on_sequence_moved)

    def toggle_simulation(self):
        if self.is_simulating: self.stop_simulation()
        else: self.start_simulation()

    def start_simulation(self):
        print("Simulation started (logic unchanged).")
        self.is_simulating = True
        self.simulate_btn.setText("⏹️ Stop Simulation")


    def stop_simulation(self):
        print("Simulation stopped.")
        self.is_simulating = False
        self.simulate_btn.setText("▶️ Run Simulation")

    def simulation_step(self): pass
    def execute_current_step(self): pass
    def show_haptic_feedback(self, target_patch, config): pass

    def run_hardware_sequence(self):
        if not self.actuator_arduino or not self.transport_arduino or self.is_hardware_running:
            print("Arduinos not connected or sequence already running."); return
        if not self.sequence_blocks: return
        
        self.update_all_patch_visuals() # 시퀀스 시작 전 최종 위치를 한 번 계산해서 보여줌

        self.is_hardware_running = True
        self.hardware_step_index = 0
        self.send_to_hw_btn.setEnabled(False)
        self.stop_hw_btn.setEnabled(True)
        print("--- Starting Hardware Sequence ---")
        self.send_next_hw_block()

    def send_next_hw_block(self):
        if not self.is_hardware_running or self.hardware_step_index >= len(self.sequence_blocks):
            self.stop_hardware_sequence(finished=True)
            return

        block = self.sequence_blocks[self.hardware_step_index]
        print(f"\nExecuting Block {self.hardware_step_index + 1}/{len(self.sequence_blocks)}: {block['type']}")

        if block['type'] == 'MOVE':
            self.hardware_waypoint_index = 0
            self.send_next_hw_waypoint()

        elif block['type'] == 'HAPTIC':
            patch_id = block['patch_id']
            target_pos = self.get_conceptual_patch_center(patch_id)
            
            scaled_x = target_pos.x() * UI_TO_REAL_SCALE_X
            scaled_y = target_pos.y() * UI_TO_REAL_SCALE_Y
            cmd = f"M,{scaled_x:.2f},{scaled_y:.2f}\n"
            
            self.last_move_ok = False
            self.is_transport_busy = True
            
            print(f"  - Pre-moving to patch {patch_id} at ({target_pos.x():.1f}, {target_pos.y():.1f})")
            print(f"  - Sending to Transport: {cmd.strip()}")
            self.transport_arduino.write(cmd.encode())
            
            QTimer.singleShot(100, self.wait_for_pre_haptic_move)

    def wait_for_pre_haptic_move(self):
        if not self.is_hardware_running: return

        if self.last_move_ok:
            self.is_transport_busy = False
            self.execute_haptic_command()
            return

        QTimer.singleShot(100, self.wait_for_pre_haptic_move)

    def execute_haptic_command(self):
        block = self.sequence_blocks[self.hardware_step_index]
        c = block['config']
        force_mode = 0
        if c['force']['enabled']: force_mode = 1 if c['force']['mode'] == 'Attract' else 2
        vibration_mode = 0
        if c['vibration']['enabled']: vibration_mode = 1 if c.get('vibration', {}).get('mode') == 'Attract' else 2
        mag = int(c['force']['magnitude'] * 2.55) if c['force']['enabled'] else 0
        freq = c['vibration']['frequency'] if c['vibration']['enabled'] else 0
        amp = int(c['vibration']['amplitude'] * 2.55) if c['vibration']['enabled'] else 0
        durations = [d['duration'] for n, d in c.items() if n != 'wait_for_move' and d.get('enabled')]
        max_duration = max(durations) if durations else 0
        heat_on = 1 if c['heat']['enabled'] else 0
        cmd = f"H,{force_mode},{mag},{vibration_mode},{freq},{amp},{max_duration},{heat_on}\n"
        
        print(f"  - Move complete. Sending to Actuator: {cmd.strip()}")
        self.actuator_arduino.write(cmd.encode())
        
        QTimer.singleShot(max_duration + 200, self.proceed_to_next_block)


    def send_next_hw_waypoint(self):
        if not self.is_hardware_running: return
        block = self.sequence_blocks[self.hardware_step_index]
        trajectory = block['trajectory']
        haptic_type = block.get('haptic_on_move', 'None')

        if self.hardware_waypoint_index == 1:
            if haptic_type != 'None':
                self.moving_patch_id = block['patch_id']
                cmd = None
                if haptic_type == "Force (Attraction)":
                    cmd = "H,1,255,0,0,0,0,0\n"
                elif haptic_type == "Vibration (Attraction)":
                    cmd = "H,0,0,1,10,255,0,0\n"
                
                if cmd and self.actuator_arduino:
                    print(f"  - Starting haptics for trajectory: {cmd.strip()}")
                    self.actuator_arduino.write(cmd.encode())

        if self.hardware_waypoint_index >= len(trajectory):
            print("Move block finished.")
            if haptic_type != 'None':
                if self.actuator_arduino:
                    print("  - Stopping haptics-on-move.")
                    self.actuator_arduino.write(b"H,0,0,0,0,0,0,0\n")
                
                patch_id = block['patch_id']
                patch_item = self.patch_items.get(patch_id)
                if patch_item:
                    end_point = trajectory[-1]
                    new_pos = end_point - QPointF(10, 15)
                    self.initial_patch_positions[patch_id] = new_pos # MODIFIED: 영구적으로 위치 업데이트
                    patch_item.setPos(new_pos)
                    print(f"  - Patch {patch_id} position updated to ({new_pos.x():.1f}, {new_pos.y():.1f})")
                
            self.moving_patch_id = None
            
            self.proceed_to_next_block()
            return

        target_point = trajectory[self.hardware_waypoint_index]
        
        scaled_x = target_point.x() * UI_TO_REAL_SCALE_X
        scaled_y = target_point.y() * UI_TO_REAL_SCALE_Y
        
        cmd = f"M,{scaled_x:.2f},{scaled_y:.2f}\n"
        
        self.last_move_ok = False
        self.is_transport_busy = True
        
        print(f"  - Waypoint {self.hardware_waypoint_index}/{len(trajectory)-1}: UI({target_point.x():.1f}, {target_point.y():.1f}) -> Real({scaled_x:.1f}, {scaled_y:.1f})")
        print(f"  - Sending to Transport: {cmd.strip()}")
        self.transport_arduino.write(cmd.encode())
        
        QTimer.singleShot(100, self.wait_for_transport_ok)

    def wait_for_transport_ok(self):
        if not self.is_hardware_running: return

        if self.last_move_ok:
            self.is_transport_busy = False
            self.hardware_waypoint_index += 1
            self.send_next_hw_waypoint()
            return

        QTimer.singleShot(100, self.wait_for_transport_ok)

    def proceed_to_next_block(self):
        if not self.is_hardware_running: return
        self.hardware_step_index += 1
        self.send_next_hw_block()

    def stop_hardware_sequence(self, finished=False):
        self.is_hardware_running = False
        self.moving_patch_id = None
        self.send_to_hw_btn.setEnabled(True)
        self.stop_hw_btn.setEnabled(False)

        if not finished:
            print("Resetting patch positions due to stop.")
            self.update_all_patch_visuals()

        if self.actuator_arduino and self.actuator_arduino.is_open:
            self.actuator_arduino.write(b"H,0,0,0,0,0,0,0\n")

        if self.transport_arduino and self.transport_arduino.is_open:
            if finished:
                print("Sequence finished. Returning to home (0,0).")
                self.transport_arduino.write(b"M,0.00,0.00\n")
            else:
                self.transport_arduino.write(b"!\n")

        status_text = "--- Hardware sequence finished. ---" if finished else "--- Hardware sequence stopped by user. ---"
        print(status_text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
