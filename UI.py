import sys
import math
import random
import serial
import serial.tools.list_ports
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
DEVICE_WIDTH_MM = 380
DEVICE_HEIGHT_MM = 290
HAPTIC_ICONS = {"force": "🖐️", "vibration": "📳", "heat": "🔥"}
PATCH_COLORS = [
    QColor("#0D6EFD"), QColor("#6F42C1"), QColor("#D63384"),
    QColor("#FD7E14"), QColor("#198754"), QColor("#0DCAF0"),
    QColor("#FFC107")
]

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
        super().__init__(); self.setWindowTitle("Haptic Orchestrator - Final"); self.setGeometry(100, 100, 1600, 900); self.setStyleSheet(STYLESHEET)
        self.initialize_state(); self.setup_ui(); self.add_patch(); self.patch_list.setCurrentRow(0)

    def initialize_state(self):
        self.sequence_blocks = []; self.patch_items = {}; self.selected_patch_id = None
        self.trajectory_points = []
        self.current_trajectory_item = None
        self.drawn_trajectory_items = []
        self.is_simulating = False
        self.simulation_items = {}; self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.simulation_step)
        self.next_patch_id = 1
        self.original_patch_positions = {}
        self.simulated_patch_states = {}
        self.actuator_pos = QPointF(0, 0)
        self.simulation_state = "IDLE"
        self.editing_block_index = None
        self.arduino = None
        self.is_hardware_running = False
        self.hardware_step_index = 0
        self.hw_actuator_pos = QPointF(0, 0)
        self.hw_state = "IDLE"

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget); main_layout.setSpacing(15); main_layout.setContentsMargins(15, 15, 15, 15)
        self.setCentralWidget(central_widget)
        left_panel = self.create_composer_panel(); left_panel.setFixedWidth(350)
        right_panel = self.create_sequence_panel(); right_panel.setFixedWidth(350)
        self.scene = GridScene(0, 0, DEVICE_WIDTH_MM, DEVICE_HEIGHT_MM)
        self.canvas = QGraphicsView(self.scene)
        self.canvas.setRenderHint(QPainter.RenderHint.Antialiasing); self.canvas.mousePressEvent = self.canvas_mouse_press
        main_layout.addWidget(left_panel); main_layout.addWidget(self.canvas, 1); main_layout.addWidget(right_panel)

    def resizeEvent(self, event): self.fit_canvas_to_scene(); super().resizeEvent(event)
    def showEvent(self, event): self.fit_canvas_to_scene(); super().showEvent(event)
    def fit_canvas_to_scene(self): self.canvas.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def create_composer_panel(self):
        main_widget = QWidget(); main_layout = QVBoxLayout(main_widget); main_layout.setContentsMargins(0,0,0,0)
        hw_group = QGroupBox("Hardware Control")
        hw_layout = QFormLayout(hw_group)
        self.port_combo = QComboBox(); self.refresh_ports_btn = QPushButton("Refresh Ports"); self.refresh_ports_btn.clicked.connect(self.populate_ports)
        port_layout = QHBoxLayout(); port_layout.addWidget(self.port_combo, 1); port_layout.addWidget(self.refresh_ports_btn)
        self.connect_btn = QPushButton("Connect"); self.connect_btn.setCheckable(True); self.connect_btn.clicked.connect(self.toggle_connection)
        self.status_label = QLabel("Status: Disconnected")
        hw_layout.addRow("COM Port:", port_layout); hw_layout.addRow(self.connect_btn); hw_layout.addRow(self.status_label)
        self.populate_ports()
        patch_group = QGroupBox("Patch Control"); patch_layout = QVBoxLayout(); self.patch_list = QListWidget(); self.patch_list.setSpacing(5); self.patch_list.currentRowChanged.connect(self.on_patch_selected)
        patch_btn_layout = QHBoxLayout()
        self.add_patch_btn = QPushButton("➕ Add New Patch"); self.add_patch_btn.clicked.connect(self.add_patch)
        self.remove_patch_btn = QPushButton("➖ Remove Selected"); self.remove_patch_btn.setObjectName("DangerButton"); self.remove_patch_btn.clicked.connect(self.remove_selected_patch)
        patch_btn_layout.addWidget(self.add_patch_btn); patch_btn_layout.addWidget(self.remove_patch_btn)
        patch_layout.addWidget(self.patch_list); patch_layout.addLayout(patch_btn_layout); patch_group.setLayout(patch_layout)
        composer_group = QGroupBox("Haptic Composer"); composer_layout = QVBoxLayout(composer_group); self.tabs = QTabWidget()
        
        double_validator = QDoubleValidator(); double_validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        # Force Tab
        force_tab = QWidget(); force_form = QFormLayout(force_tab); self.f_enabled = ToggleSwitch()
        f_enable_layout = QHBoxLayout(); f_enable_layout.addStretch(); f_enable_layout.addWidget(self.f_enabled); f_enable_layout.setContentsMargins(0,0,0,0)
        self.f_mode = QComboBox(); self.f_mode.addItems(["Attract", "Repel"]) #<-- 수정: "Lateral" 제거
        self.f_mag = LabeledSlider("Magnitude")
        self.f_dur = QLineEdit("3.0"); self.f_dur.setValidator(double_validator)
        force_form.addRow("Enable Force", f_enable_layout)
        force_form.addRow("Mode:", self.f_mode); force_form.addRow(self.f_mag); force_form.addRow("Duration (s):", self.f_dur)
        
        # Vibration Tab
        vib_tab = QWidget(); vib_form = QFormLayout(vib_tab); self.v_enabled = ToggleSwitch()
        v_enable_layout = QHBoxLayout(); v_enable_layout.addStretch(); v_enable_layout.addWidget(self.v_enabled); v_enable_layout.setContentsMargins(0,0,0,0)
        self.v_mode = QComboBox(); self.v_mode.addItems(["Attract", "Repel"]) #<-- 수정: "Lateral" 제거
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
        
        composer_layout.addWidget(self.tabs)
        self.add_or_update_haptic_btn = QPushButton("➕ Add Haptic Block")
        self.add_or_update_haptic_btn.clicked.connect(self.add_or_update_haptic_block)
        composer_layout.addWidget(self.add_or_update_haptic_btn)

        main_layout.addWidget(hw_group); main_layout.addWidget(patch_group); main_layout.addWidget(composer_group); main_layout.addStretch()
        
        self.reset_composer_to_defaults()
        return main_widget

    def create_sequence_panel(self):
        main_widget = QWidget(); layout = QVBoxLayout(main_widget); layout.setContentsMargins(0,0,0,0)
        traj_group = QGroupBox("Trajectory Control")
        traj_layout = QVBoxLayout(traj_group); add_traj_btn = QPushButton("➡️ Add Drawn Trajectory")
        add_traj_btn.clicked.connect(self.add_trajectory_block); clear_traj_btn = QPushButton("🗑️ Clear All Drawn")
        clear_traj_btn.clicked.connect(self.clear_all_drawn_trajectories); traj_layout.addWidget(add_traj_btn); traj_layout.addWidget(clear_traj_btn)
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
        self.editing_block_index = None
        self.add_or_update_haptic_btn.setText("➕ Add Haptic Block")

    def populate_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports: self.port_combo.addItem(port.device)

    def toggle_connection(self):
        if self.connect_btn.isChecked():
            port = self.port_combo.currentText()
            if not port: self.status_label.setText("Status: No port selected"); self.connect_btn.setChecked(False); return
            try:
                self.arduino = serial.Serial(port, 115200, timeout=1)
                QTimer.singleShot(2000, self.check_arduino_ready)
            except serial.SerialException as e:
                self.status_label.setText(f"Status: Error"); self.connect_btn.setChecked(False); self.arduino = None
        else:
            if self.arduino and self.arduino.is_open: self.arduino.close()
            self.arduino = None; self.status_label.setText("Status: Disconnected"); self.connect_btn.setText("Connect")

    def check_arduino_ready(self):
        if not self.arduino: return
        try:
            self.arduino.flushInput()
            self.arduino.write(b"R\n")
            line = self.arduino.readline().decode('utf-8').strip()
            if "Ready" in line:
                self.status_label.setText(f"Status: Connected"); self.connect_btn.setText("Disconnect")
            else:
                self.status_label.setText("Status: No response"); self.connect_btn.setChecked(False); self.arduino.close(); self.arduino = None
        except serial.SerialException as e:
            self.status_label.setText(f"Status: Port Error"); self.connect_btn.setChecked(False); self.arduino = None

    def emergency_stop(self):
        print("🛑 EMERGENCY STOP TRIGGERED!")
        if self.is_simulating: self.stop_simulation()
        if self.is_hardware_running:
            self.is_hardware_running = False
            self.send_to_hw_btn.setText("🚀 Send to Actuator")
        if self.arduino and self.arduino.is_open:
            stop_cmd = "H,0,0,0,0,0,0,0\n"
            self.arduino.write(stop_cmd.encode('utf-8'))

    def add_patch(self):
        patch_id = self.next_patch_id; self.next_patch_id += 1
        x = random.uniform(10, DEVICE_WIDTH_MM - 30); y = random.uniform(10, DEVICE_HEIGHT_MM - 40)
        color = PATCH_COLORS[(patch_id - 1) % len(PATCH_COLORS)]
        patch_item = PatchItem(patch_id, x, y, color); self.scene.addItem(patch_item); self.patch_items[patch_id] = patch_item
        list_item = QListWidgetItem(f"Patch {patch_id}"); list_item.setData(Qt.ItemDataRole.UserRole, patch_id); list_item.setForeground(color)
        self.patch_list.addItem(list_item)
    
    def remove_selected_patch(self):
        if self.selected_patch_id is None: return
        blocks_to_delete = [block for block in self.sequence_blocks if block['patch_id'] == self.selected_patch_id]
        for block in blocks_to_delete:
            if block['type'] == 'MOVE' and 'path_item' in block: self.scene.removeItem(block['path_item'])
        self.sequence_blocks = [block for block in self.sequence_blocks if block['patch_id'] != self.selected_patch_id]
        self.update_sequence_list()
        patch_to_remove = self.patch_items.pop(self.selected_patch_id)
        self.scene.removeItem(patch_to_remove)
        current_row = self.patch_list.currentRow()
        self.patch_list.takeItem(current_row)
        self.selected_patch_id = None
    
    def on_patch_selected(self, row):
        if row < 0:
            self.selected_patch_id = None
            if self.editing_block_index is not None: self.reset_composer_to_defaults()
        else:
            list_item = self.patch_list.item(row)
            patch_id = list_item.data(Qt.ItemDataRole.UserRole)
            self.selected_patch_id = patch_id
        for pid, item in self.patch_items.items(): item.select(pid == self.selected_patch_id)

    def canvas_mouse_press(self, event):
        if self.is_simulating or not self.selected_patch_id: return
        pos = self.canvas.mapToScene(event.pos())
        if not self.trajectory_points:
            start_pos = self.get_conceptual_patch_center(self.selected_patch_id)
            self.trajectory_points.append(start_pos)
        if 0 <= pos.x() <= DEVICE_WIDTH_MM and 0 <= pos.y() <= DEVICE_HEIGHT_MM:
            self.trajectory_points.append(pos); self.draw_current_trajectory()

    def get_conceptual_patch_center(self, patch_id):
        if patch_id not in self.patch_items: return QPointF(0, 0)
        patch_item = self.patch_items[patch_id]
        last_known_center = patch_item.pos() + QPointF(patch_item.boundingRect().width() / 2, patch_item.boundingRect().height() / 2)
        for block in self.sequence_blocks:
            if block['patch_id'] == patch_id and block['type'] == 'MOVE':
                last_known_center = block['trajectory'][-1]
        return last_known_center

    def draw_current_trajectory(self):
        if self.current_trajectory_item: self.scene.removeItem(self.current_trajectory_item)
        if not self.trajectory_points: return
        color = self.patch_items[self.selected_patch_id].color if self.selected_patch_id else QColor("#0D6EFD")
        pen = QPen(color, 2, Qt.PenStyle.DashLine)
        path = QPainterPath(); path.moveTo(self.trajectory_points[0])
        for point in self.trajectory_points[1:]: path.lineTo(point)
        self.current_trajectory_item = self.scene.addPath(path, pen)

    def clear_all_drawn_trajectories(self):
        if self.current_trajectory_item: self.scene.removeItem(self.current_trajectory_item); self.current_trajectory_item = None
        for block in self.sequence_blocks:
            if block['type'] == 'MOVE' and 'path_item' in block:
                if block['path_item'].scene(): self.scene.removeItem(block['path_item'])
        self.trajectory_points.clear()

    def add_trajectory_block(self):
        if len(self.trajectory_points) < 2 or not self.selected_patch_id: return
        block = {"type": "MOVE", "patch_id": self.selected_patch_id, "trajectory": list(self.trajectory_points), "path_item": self.current_trajectory_item}
        self.sequence_blocks.append(block)
        self.current_trajectory_item = None; self.trajectory_points.clear(); self.update_sequence_list()

    def add_or_update_haptic_block(self):
        if not self.selected_patch_id: return
        try:
            config = {
                "force": {"enabled": self.f_enabled.isChecked(), "mode": self.f_mode.currentText(), "magnitude": self.f_mag.value(), "duration": int(float(self.f_dur.text()) * 1000)},
                "vibration": {"enabled": self.v_enabled.isChecked(), "mode": self.v_mode.currentText(), "frequency": self.v_freq.value(), "amplitude": self.v_amp.value(), "duration": int(float(self.v_dur.text()) * 1000)},
                "heat": {"enabled": self.h_enabled.isChecked(), "duration": int(float(self.h_dur.text()) * 1000)}
            }
        except (ValueError,TypeError):
            print("Error: Invalid duration value. Please enter a valid number.")
            return

        if not any(c['enabled'] for c in config.values()): return
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
            if config['force']['enabled']: self.tabs.setCurrentIndex(0)
            elif config['vibration']['enabled']: self.tabs.setCurrentIndex(1)
            elif config['heat']['enabled']: self.tabs.setCurrentIndex(2)

    def delete_sequence_block(self):
        selected_items = self.sequence_list.selectedItems()
        if not selected_items: return
        rows_to_delete = sorted([self.sequence_list.row(item) for item in selected_items], reverse=True)
        for row in rows_to_delete:
            block_to_delete = self.sequence_blocks[row]
            if block_to_delete['type'] == 'MOVE' and 'path_item' in block_to_delete:
                if block_to_delete['path_item'].scene(): self.scene.removeItem(block_to_delete['path_item'])
            self.sequence_list.takeItem(row); del self.sequence_blocks[row]
        self.update_sequence_list()

    def on_sequence_moved(self, parent, start, end, dest, row):
        item = self.sequence_blocks.pop(start); self.sequence_blocks.insert(row if row < start else row - 1, item); self.update_sequence_list()

    def update_sequence_list(self):
        try: self.sequence_list.model().rowsMoved.disconnect()
        except TypeError: pass
        self.sequence_list.clear()
        for i, block in enumerate(self.sequence_blocks):
            patch_id = block['patch_id']; color = self.patch_items[patch_id].color; item = QListWidgetItem()
            if block['type'] == 'MOVE': item.setText(f"{i+1}. MOVE P{patch_id} Trajectory")
            else:
                enabled = [name for name, conf in block['config'].items() if conf['enabled']]
                icons = " ".join([HAPTIC_ICONS[m] for m in enabled]); item.setText(f"{i+1}. HAPTIC on P{patch_id} {icons}")
            item.setForeground(color); self.sequence_list.addItem(item)
        self.sequence_list.model().rowsMoved.connect(self.on_sequence_moved)

    def toggle_simulation(self):
        if self.is_simulating: self.stop_simulation()
        else: self.start_simulation()

    def start_simulation(self):
        if not self.sequence_blocks: return
        self.is_simulating = True; self.simulate_btn.setText("⏹️ Stop Simulation")
        self.current_step_index = 0
        self.original_patch_positions.clear(); self.simulated_patch_states.clear()
        for patch_id, patch_item in self.patch_items.items():
            self.original_patch_positions[patch_id] = patch_item.pos()
            self.simulated_patch_states[patch_id] = patch_item.pos()
        actuator = QGraphicsEllipseItem(0, 0, 30, 30); actuator.setBrush(QBrush(QColor(220, 53, 69, 180))); actuator.setPen(QPen(Qt.PenStyle.NoPen)); actuator.setZValue(3)
        actuator.setPos(self.actuator_pos - QPointF(15, 15))
        self.simulation_items = {'actuator': actuator, 'haptic_icons': []}
        self.scene.addItem(actuator)
        self.run_next_sequence_step()

    def stop_simulation(self):
        self.is_simulating = False; self.animation_timer.stop(); self.simulate_btn.setText("▶️ Run Simulation")
        for key, item in self.simulation_items.items():
            if key == 'haptic_icons':
                for icon in item:
                    if icon.scene(): self.scene.removeItem(icon)
            elif item.scene(): self.scene.removeItem(item)
        self.simulation_items.clear()
        for patch_id, pos in self.original_patch_positions.items():
            if patch_id in self.patch_items: self.patch_items[patch_id].setPos(pos)
        self.actuator_pos = QPointF(0, 0)

    def run_next_sequence_step(self):
        if self.current_step_index >= len(self.sequence_blocks): self.stop_simulation(); return
        step = self.sequence_blocks[self.current_step_index]; patch_id = step['patch_id']
        if patch_id not in self.patch_items: self.stop_simulation(); return
        patch_center = self.simulated_patch_states[patch_id] + QPointF(10, 15)
        if step['type'] == 'MOVE': self.travel_target = step['trajectory'][0]
        elif step['type'] == 'HAPTIC': self.travel_target = patch_center
        self.simulation_state = "TRAVELING"; self.animation_timer.start(20)

    def simulation_step(self):
        if not self.is_simulating: return
        actuator = self.simulation_items['actuator']; actuator_center = actuator.pos() + QPointF(15, 15)
        if self.simulation_state == "TRAVELING":
            dx, dy = self.travel_target.x() - actuator_center.x(), self.travel_target.y() - actuator_center.y()
            distance = math.hypot(dx, dy)
            if distance < 6: self.actuator_pos = self.travel_target; self.execute_current_step()
            else:
                speed = 8; new_pos = actuator.pos() + QPointF(dx / distance * speed, dy / distance * speed)
                actuator.setPos(new_pos); self.actuator_pos = new_pos + QPointF(15, 15)
        elif self.simulation_state == "MOVING":
            step = self.sequence_blocks[self.current_step_index]
            patch_to_move = self.patch_items[step['patch_id']]; trajectory = step['trajectory']
            if self.current_waypoint_index >= len(trajectory):
                self.simulated_patch_states[step['patch_id']] = patch_to_move.pos()
                self.current_step_index += 1; self.run_next_sequence_step(); return
            target_pos = trajectory[self.current_waypoint_index]
            dx, dy = target_pos.x() - actuator_center.x(), target_pos.y() - actuator_center.y()
            distance = math.hypot(dx, dy)
            if distance < 6: self.current_waypoint_index += 1
            else:
                speed = 5; new_pos = actuator.pos() + QPointF(dx / distance * speed, dy / distance * speed)
                actuator.setPos(new_pos); patch_to_move.setPos(new_pos - QPointF(5, 0)); self.actuator_pos = new_pos + QPointF(15, 15)

    def execute_current_step(self):
        step = self.sequence_blocks[self.current_step_index]; patch_id = step['patch_id']
        patch_item = self.patch_items[patch_id]
        if step['type'] == 'MOVE':
            self.simulation_state = "MOVING"; self.current_waypoint_index = 1
        elif step['type'] == 'HAPTIC':
            self.animation_timer.stop(); config = step['config']
            self.show_haptic_feedback(patch_item, config)
            max_duration = max(d['duration'] for d in config.values() if d['enabled']) if any(d['enabled'] for d in config.values()) else 100
            self.current_step_index += 1; QTimer.singleShot(max_duration, self.run_next_sequence_step)

    def show_haptic_feedback(self, target_patch, config):
        for icon in self.simulation_items.get('haptic_icons', []):
            if icon.scene(): self.scene.removeItem(icon)
        self.simulation_items['haptic_icons'] = []
        offset_x = 25
        for modality, details in config.items():
            if details['enabled']:
                haptic_icon = QGraphicsTextItem(); haptic_icon.setFont(QFont("Arial", 24)); haptic_icon.setZValue(4)
                haptic_icon.setPlainText(HAPTIC_ICONS.get(modality, "?")); haptic_icon.setPos(target_patch.pos() + QPointF(offset_x, 0))
                self.scene.addItem(haptic_icon); self.simulation_items['haptic_icons'].append(haptic_icon)
                QTimer.singleShot(details['duration'], haptic_icon.hide); offset_x += 25
    
    def run_hardware_sequence(self):
        if not self.arduino or not self.arduino.is_open or self.is_hardware_running:
            print("Arduino not connected or sequence already running."); return
        if not self.sequence_blocks: return
        self.is_hardware_running = True; self.hardware_step_index = 0
        self.hw_actuator_pos = QPointF(0, 0)
        self.send_to_hw_btn.setText("⏹️ Stop Hardware")
        self.send_next_hw_step()

    def send_next_hw_step(self):
        if not self.is_hardware_running: return
        if self.hardware_step_index >= len(self.sequence_blocks):
            print("Sequence finished. Stopping haptics and returning to origin.")
            stop_cmd = "H,0,0,0,0,0,0,0\n"
            self.arduino.write(stop_cmd.encode('utf-8'))
            QTimer.singleShot(200, self.return_hw_to_origin)
            return
            
        self.hw_state = "TRAVELING"
        block = self.sequence_blocks[self.hardware_step_index]
        patch_id = block['patch_id']
        target_pos = QPointF(0,0)

        if block['type'] == 'MOVE':
            target_pos = block['trajectory'][0]
        elif block['type'] == 'HAPTIC':
            patch_item = self.patch_items[patch_id]
            target_pos = patch_item.pos() + QPointF(10, 15)

        cmd_str = f"M,{target_pos.x()},{target_pos.y()}\n"
        print(f"Sending travel command: {cmd_str.strip()}")
        self.arduino.write(cmd_str.encode('utf-8'))
        self.hw_actuator_pos = target_pos
        QTimer.singleShot(100, self.wait_for_hw_ok)

    def return_hw_to_origin(self):
        if not self.arduino or not self.arduino.is_open: return
        final_cmd = "M,0.0,0.0\n"
        self.arduino.write(final_cmd.encode('utf-8'))
        self.hw_state = "RETURNING_HOME"
        QTimer.singleShot(100, self.wait_for_hw_ok)

    def wait_for_hw_ok(self):
        if not self.arduino or not self.arduino.is_open or not self.is_hardware_running: return
        if self.arduino.in_waiting > 0:
            response = self.arduino.readline().decode('utf-8').strip()
            print(f"Received: {response}")
            if "OK" in response:
                if self.hw_state == "TRAVELING":
                    self.execute_hw_action()
                elif self.hw_state == "ACTION":
                    block = self.sequence_blocks[self.hardware_step_index]
                    duration = 0
                    if block['type'] == 'HAPTIC':
                        c = block['config']
                        durations = [d['duration'] for d in c.values() if d['enabled']]
                        duration = max(durations) if durations else 0
                    
                    print(f"Action received. Waiting for {duration}ms before next step.") #<-- 디버깅용 프린트
                    QTimer.singleShot(duration, self.proceed_to_next_step)

                elif self.hw_state == "RETURNING_HOME":
                    self.is_hardware_running = False
                    self.send_to_hw_btn.setText("🚀 Send to Actuator")
                    print("Hardware sequence finished.")
        else:
            QTimer.singleShot(100, self.wait_for_hw_ok)
    
    def proceed_to_next_step(self):
        if not self.is_hardware_running: return
        print("Proceeding to next step...") #<-- 디버깅용 프린트
        self.hardware_step_index += 1
        self.send_next_hw_step()

    def execute_hw_action(self):
        self.hw_state = "ACTION"
        block = self.sequence_blocks[self.hardware_step_index]
        cmd_str = ""
        if block['type'] == 'MOVE':
            target_pos = block['trajectory'][-1]
            cmd_str = f"M,{target_pos.x()},{target_pos.y()}\n"
            self.hw_actuator_pos = target_pos
        elif block['type'] == 'HAPTIC':
            c = block['config']
            force_mode = 0
            if c['force']['enabled']:
                if c['force']['mode'] == 'Attract': force_mode = 1
                elif c['force']['mode'] == 'Repel': force_mode = 2
                else: force_mode = 3
            vibration_mode = 0
            if c['vibration']['enabled']:
                if c.get('vibration', {}).get('mode', 'Attract') == 'Attract': vibration_mode = 1
                elif c.get('vibration', {}).get('mode', 'Attract') == 'Repel': vibration_mode = 2
                else: vibration_mode = 3
            mag = int(c['force']['magnitude'] * 2.55) if c['force']['enabled'] else 0
            freq = c['vibration']['frequency'] if c['vibration']['enabled'] else 0
            amp = int(c['vibration']['amplitude'] * 2.55) if c['vibration']['enabled'] else 0
            
            durations = [d['duration'] for d in c.values() if d['enabled']]
            max_duration = max(durations) if durations else 0
            heat_on_flag = 1 if c['heat']['enabled'] else 0
            
            cmd_str = f"H,{force_mode},{mag},{vibration_mode},{freq},{amp},{max_duration},{heat_on_flag}\n"
        
        if cmd_str:
            print(f"Sending action command: {cmd_str.strip()}")
            self.arduino.write(cmd_str.encode('utf-8'))
            QTimer.singleShot(100, self.wait_for_hw_ok)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())