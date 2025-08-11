import sys
import math
import random
import qtawesome as qta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsPathItem, QListWidget, QListWidgetItem, QLabel, QGroupBox,
    QCheckBox, QAbstractItemView, QGraphicsEllipseItem, QTabWidget, QSlider,
    QLineEdit, QComboBox, QFormLayout, QGraphicsPolygonItem, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import (
    QColor, QBrush, QPen, QPainterPath, QFont, QPainter,
    QIntValidator, QCursor, QIcon, QPolygonF # <-- Add QCursor here
)
from PyQt6.QtCore import Qt, QPointF, QTimer, QSize, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF

# --- 상수 정의 ---
DEVICE_WIDTH_MM = 350
DEVICE_HEIGHT_MM = 270
# HAPTIC_ICONS = {"force": "🖐️", "vibration": "📳", "heat": "🔥"} # 시퀀스 리스트 표시용

# --- UI 테마 스타일시트 (Inter 글꼴 적용) ---
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
    """모던 토글 스위치 커스텀 위젯"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # 2. 누락된 self.duration 정의 추가
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
    # def hitButton(self, pos: QPointF): return self.contentsRect().contains(pos.toPointF())
    # def hitButton(self, pos: QPointF): return self.contentsRect().contains(pos.toPoint())
    def hitButton(self, pos: QPointF): return self.contentsRect().contains(pos)

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
    def __init__(self, patch_id, x, y, parent=None):
        super().__init__(0, 0, 50, 50, parent); self.setPos(x, y); self.setBrush(QBrush(QColor("#FFFFFF"))); self.setPen(QPen(QColor("#ADB5BD"), 2)); self.setZValue(1)
        # 3. 그림자 효과 복원
        shadow = QGraphicsDropShadowEffect(); shadow.setBlurRadius(15); shadow.setColor(QColor(0, 0, 0, 80)); shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)
        text = QGraphicsTextItem(f"P{patch_id}", self); text.setFont(QFont("Inter", 10, QFont.Weight.Bold)); text.setDefaultTextColor(QColor("#495057")); text.setPos(5, 2)
        poly = QPolygonF([QPointF(25, 40), QPointF(20, 50), QPointF(30, 50)])
        indicator = QGraphicsPolygonItem(poly, self); indicator.setPen(QPen(Qt.PenStyle.NoPen)); indicator.setBrush(QBrush(QColor("#495057")))
    def select(self, is_selected):
        self.setPen(QPen(QColor("#0D6EFD") if is_selected else QColor("#ADB5BD"), 2.5 if is_selected else 2))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Haptic Orchestrator - Professional"); self.setGeometry(100, 100, 1600, 900); self.setStyleSheet(STYLESHEET)
        self.initialize_state(); self.setup_ui(); self.add_patch(); self.patch_list.setCurrentRow(0)

    def initialize_state(self):
        self.sequence_blocks = []; self.patch_items = {}; self.selected_patch_id = None
        self.trajectory_points = []; self.trajectory_path_item = None; self.is_simulating = False
        self.simulation_items = {}; self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.simulation_step)
        # 4. HAPTIC_ICONS를 인스턴스 변수로 초기화
        self.HAPTIC_ICONS = {"force": "🖐️", "vibration": "📳", "heat": "🔥"}

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
        patch_group = QGroupBox("Patch Control"); patch_layout = QVBoxLayout(); self.patch_list = QListWidget(); self.patch_list.setSpacing(5); self.patch_list.currentRowChanged.connect(self.on_patch_selected)
        self.add_patch_btn = QPushButton(" Add New Patch"); 
        self.add_patch_btn.setIcon(QIcon('fa5s.plus'))
        self.add_patch_btn.clicked.connect(self.add_patch)
        patch_layout.addWidget(self.patch_list); patch_layout.addWidget(self.add_patch_btn); patch_group.setLayout(patch_layout)
        composer_group = QGroupBox("Haptic Composer"); composer_layout = QVBoxLayout(composer_group); tabs = QTabWidget()
        
        # --- Force Tab ---
        force_tab = QWidget(); force_form = QFormLayout(force_tab); self.f_enabled = ToggleSwitch(); self.f_enabled.setChecked(True)
        self.f_mode = QComboBox(); self.f_mode.addItems(["Attract", "Repel", "Lateral"]); self.f_mag = LabeledSlider("Magnitude"); self.f_mag.setValue(80)
        self.f_dur = QLineEdit("1500"); self.f_dur.setValidator(QIntValidator()); force_form.addRow("Enable Force", self.f_enabled)
        force_form.addRow("Mode:", self.f_mode); force_form.addRow(self.f_mag); force_form.addRow("Duration (ms):", self.f_dur)
        
        # --- Vibration Tab ---
        vib_tab = QWidget(); vib_form = QFormLayout(vib_tab); self.v_enabled = ToggleSwitch(); self.v_freq = LabeledSlider("Frequency", 20, 200, "Hz"); self.v_freq.setValue(100)
        self.v_amp = LabeledSlider("Amplitude"); self.v_amp.setValue(50); self.v_dur = QLineEdit("1500"); self.v_dur.setValidator(QIntValidator())
        vib_form.addRow("Enable Vibration", self.v_enabled); vib_form.addRow(self.v_freq); vib_form.addRow(self.v_amp); vib_form.addRow("Duration (ms):", self.v_dur)

        # --- Heat Tab ---
        heat_tab = QWidget(); heat_form = QFormLayout(heat_tab); self.h_enabled = ToggleSwitch()
        self.h_dur = QLineEdit("3000"); self.h_dur.setValidator(QIntValidator()); heat_form.addRow("Enable Heat", self.h_enabled); heat_form.addRow("Duration (ms):", self.h_dur)

        tabs.addTab(force_tab, QIcon('fa5s.bolt'), "Force"); tabs.addTab(vib_tab, QIcon('fa5s.wave-square'), "Vibration"); tabs.addTab(heat_tab, QIcon('fa5s.fire'), "Heat")
        composer_layout.addWidget(tabs); add_haptic_btn = QPushButton(" Add Haptic Block"); add_haptic_btn.setIcon(QIcon('fa5s.plus-circle')); add_haptic_btn.clicked.connect(self.add_haptic_block)
        composer_layout.addWidget(add_haptic_btn)
        main_layout.addWidget(patch_group); main_layout.addWidget(composer_group); main_layout.addStretch()
        return main_widget

    def create_sequence_panel(self):
        main_widget = QWidget(); layout = QVBoxLayout(main_widget); layout.setContentsMargins(0,0,0,0)
        traj_group = QGroupBox("Trajectory Control")
        traj_layout = QVBoxLayout(traj_group); add_traj_btn = QPushButton(" Add Drawn Trajectory"); add_traj_btn.setIcon(QIcon('fa5s.route'))
        add_traj_btn.clicked.connect(self.add_trajectory_block); clear_traj_btn = QPushButton(" Clear Drawn"); clear_traj_btn.setIcon(QIcon('fa5s.eraser'))
        clear_traj_btn.clicked.connect(self.clear_drawn_trajectory); traj_layout.addWidget(add_traj_btn); traj_layout.addWidget(clear_traj_btn)
        sequence_group = QGroupBox("Sequence Editor")
        seq_layout = QVBoxLayout(sequence_group); self.sequence_list = QListWidget(); self.sequence_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.sequence_list.model().rowsMoved.connect(self.on_sequence_moved)
        btn_layout = QHBoxLayout(); self.delete_block_btn = QPushButton(); self.delete_block_btn.setIcon(QIcon('fa5s.trash-alt'))
        self.delete_block_btn.setObjectName("DangerButton"); self.delete_block_btn.clicked.connect(self.delete_sequence_block); btn_layout.addStretch(); btn_layout.addWidget(self.delete_block_btn)
        self.simulate_btn = QPushButton(" Run Simulation"); self.simulate_btn.setIcon(QIcon('fa5s.play')); self.simulate_btn.setObjectName("PrimaryButton"); self.simulate_btn.clicked.connect(self.toggle_simulation)
        seq_layout.addWidget(QLabel("Drag to reorder. Click to select.", objectName="HintLabel")); seq_layout.addWidget(self.sequence_list)
        seq_layout.addLayout(btn_layout); seq_layout.addWidget(self.simulate_btn)
        layout.addWidget(traj_group); layout.addWidget(sequence_group); layout.addStretch()
        return main_widget
    
    # --- 이하 로직 함수들은 이전 버전과 대부분 동일 ---
    def add_patch(self):
        patch_id = len(self.patch_items) + 1; x = random.uniform(20, DEVICE_WIDTH_MM - 70); y = random.uniform(20, DEVICE_HEIGHT_MM - 70)
        patch_item = PatchItem(patch_id, x, y); self.scene.addItem(patch_item); self.patch_items[patch_id] = patch_item; self.patch_list.addItem(f"Patch {patch_id}")
    def on_patch_selected(self, row):
        if row < 0: self.selected_patch_id = None; return
        self.selected_patch_id = row + 1
        for patch_id, item in self.patch_items.items(): item.select(patch_id == self.selected_patch_id)
    def canvas_mouse_press(self, event):
        if self.is_simulating: return
        pos = self.canvas.mapToScene(event.pos())
        if 0 <= pos.x() <= DEVICE_WIDTH_MM and 0 <= pos.y() <= DEVICE_HEIGHT_MM:
            self.trajectory_points.append(pos); self.draw_trajectory()
    def draw_trajectory(self):
        if self.trajectory_path_item: self.scene.removeItem(self.trajectory_path_item)
        if not self.trajectory_points: return
        path = QPainterPath(); path.moveTo(self.trajectory_points[0])
        for point in self.trajectory_points[1:]: path.lineTo(point)
        self.trajectory_path_item = self.scene.addPath(path, QPen(QColor("#0D6EFD"), 2, Qt.PenStyle.DashLine))
    def clear_drawn_trajectory(self):
        if self.trajectory_path_item: self.scene.removeItem(self.trajectory_path_item)
        self.trajectory_path_item = None; self.trajectory_points.clear()
    def add_trajectory_block(self):
        if len(self.trajectory_points) < 1 or not self.selected_patch_id: return
        block = {"type": "MOVE", "patch_id": self.selected_patch_id, "trajectory": list(self.trajectory_points)}
        self.sequence_blocks.append(block); self.clear_drawn_trajectory(); self.update_sequence_list()
    def add_haptic_block(self):
        if not self.selected_patch_id: return
        config = {"force": {"enabled": self.f_enabled.isChecked(), "mode": self.f_mode.currentText(), "magnitude": self.f_mag.value(), "duration": int(self.f_dur.text())},
                  "vibration": {"enabled": self.v_enabled.isChecked(), "frequency": self.v_freq.value(), "amplitude": self.v_amp.value(), "duration": int(self.v_dur.text())},
                  "heat": {"enabled": self.h_enabled.isChecked(), "duration": int(self.h_dur.text())}}
        if not any(c['enabled'] for c in config.values()): return
        block = {"type": "HAPTIC", "patch_id": self.selected_patch_id, "config": config}
        self.sequence_blocks.append(block); self.update_sequence_list()
    def delete_sequence_block(self):
        row = self.sequence_list.currentRow()
        if row > -1: self.sequence_list.takeItem(row); del self.sequence_blocks[row]; self.update_sequence_list()
    def on_sequence_moved(self, parent, start, end, dest, row):
        item = self.sequence_blocks.pop(start); self.sequence_blocks.insert(row if row < start else row - 1, item); self.update_sequence_list()
    def update_sequence_list(self):
        try: self.sequence_list.model().rowsMoved.disconnect()
        except TypeError: pass
        self.sequence_list.clear()
        for i, block in enumerate(self.sequence_blocks):
            patch_id = block['patch_id']
            if block['type'] == 'MOVE': text = f"{i+1}. MOVE to P{patch_id} Trajectory"
            else:
                enabled = [name for name, conf in block['config'].items() if conf['enabled']]
                icons = " ".join([self.HAPTIC_ICONS[m] for m in enabled])
                text = f"{i+1}. HAPTIC on P{patch_id} {icons}"
            self.sequence_list.addItem(QListWidgetItem(text))
        self.sequence_list.model().rowsMoved.connect(self.on_sequence_moved)
    def toggle_simulation(self):
        if self.is_simulating: self.stop_simulation()
        else: self.start_simulation()
    def start_simulation(self):
        if not self.sequence_blocks: return
        self.is_simulating = True; self.simulate_btn.setText(" Stop Simulation"); self.simulate_btn.setIcon(QIcon('fa5s.stop'))
        self.current_step_index = 0
        actuator = QGraphicsEllipseItem(0, 0, 30, 30); actuator.setBrush(QBrush(QColor(220, 53, 69, 180))); actuator.setPen(QPen(Qt.PenStyle.NoPen)); actuator.setZValue(3)
        sim_patch = PatchItem(0, 0, 0); sim_patch.setZValue(2); sim_patch.setOpacity(0.8)
        haptic_icon = QGraphicsTextItem(); haptic_icon.setFont(QFont("Arial", 24)); haptic_icon.setZValue(4); haptic_icon.hide()
        self.simulation_items = {'actuator': actuator, 'sim_patch': sim_patch, 'haptic_icon': haptic_icon}
        for item in self.simulation_items.values(): self.scene.addItem(item)
        self.run_next_sequence_step()
    def stop_simulation(self):
        self.is_simulating = False; self.animation_timer.stop(); self.simulate_btn.setText(" Run Simulation"); self.simulate_btn.setIcon(QIcon('fa5s.play'))
        for item in self.simulation_items.values():
            if item.scene(): self.scene.removeItem(item)
        self.simulation_items.clear()
    def run_next_sequence_step(self):
        if self.current_step_index >= len(self.sequence_blocks): self.stop_simulation(); return
        step = self.sequence_blocks[self.current_step_index]; patch_id = step['patch_id']; target_patch = self.patch_items[patch_id]
        if step['type'] == 'MOVE':
            self.current_waypoint_index = 0
            start_pos = target_patch.pos() if self.current_step_index == 0 else self.simulation_items['actuator'].pos()
            self.simulation_items['actuator'].setPos(start_pos); self.simulation_items['sim_patch'].setPos(start_pos)
            self.animation_timer.start(20)
        elif step['type'] == 'HAPTIC':
            self.animation_timer.stop(); self.simulation_items['actuator'].setPos(target_patch.pos()); self.simulation_items['sim_patch'].setPos(target_patch.pos())
            enabled = [name for name, conf in step['config'].items() if conf['enabled']]
            self.show_haptic_feedback(enabled); self.current_step_index += 1; QTimer.singleShot(1500, self.run_next_sequence_step)
    def simulation_step(self):
        if not self.is_simulating or self.current_step_index >= len(self.sequence_blocks): return
        step = self.sequence_blocks[self.current_step_index]
        if step['type'] != 'MOVE': self.animation_timer.stop(); return
        trajectory = step['trajectory']
        if self.current_waypoint_index >= len(trajectory): self.current_step_index += 1; self.run_next_sequence_step(); return
        target_pos = trajectory[self.current_waypoint_index]; actuator = self.simulation_items['actuator']; actuator_center = actuator.pos() + QPointF(15, 15)
        dx, dy = target_pos.x() - actuator_center.x(), target_pos.y() - actuator_center.y(); distance = math.hypot(dx, dy)
        if distance < 6: self.current_waypoint_index += 1
        else:
            speed = 5; new_pos = actuator.pos() + QPointF(dx / distance * speed, dy / distance * speed)
            actuator.setPos(new_pos); self.simulation_items['sim_patch'].setPos(new_pos)
    def show_haptic_feedback(self, modalities):
        icon_text = " ".join([self.HAPTIC_ICONS.get(m, "?") for m in modalities]); haptic_icon = self.simulation_items['haptic_icon']
        haptic_icon.setPlainText(icon_text); haptic_icon.setPos(self.simulation_items['sim_patch'].pos() + QPointF(55, 0))
        haptic_icon.show(); QTimer.singleShot(1000, haptic_icon.hide)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())