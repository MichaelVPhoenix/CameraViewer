# Copyright (c) 2025 Mykhailo Pozdnikin (Michael Phoenix). All rights reserved.
# Redistribution, modification, or commercial use without
# explicit permission is strictly prohibited.

import sys
import cv2
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel, \
    QComboBox, QMessageBox, QCheckBox, QShortcut
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap, QKeySequence
from datetime import datetime


class CameraViewer(QMainWindow):
    def __init__(self):
        super().__init__()

        # Core attributes
        self.camera = None
        self.timer = QTimer()
        self.is_frozen = False
        self.frozen_frame = None
        self.flip_horizontal = False
        self.flip_vertical = False
        self.is_fullscreen = False
        self.current_frame = None
        self.normal_geometry = None
        self._hidden_widgets = []

        # Mouse tracking for fullscreen mode
        self.mouse_timer = QTimer()
        self.mouse_timer.timeout.connect(self.hide_controls_in_fullscreen)
        self.mouse_hide_delay = 3000  # 3 seconds

        # --- UI Elements (declare all here, configure later) ---
        # Camera selection
        self.camera_label = QLabel("Camera:")
        self.camera_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh")
        self.connect_btn = QPushButton("Connect (Ctrl+O)")

        # Video area
        self.video_label = QLabel()

        # Flip controls
        self.flip_h_checkbox = QCheckBox("Flip Horizontally (Ctrl+H)")
        self.flip_v_checkbox = QCheckBox("Flip Vertically (Ctrl+V)")

        # Action buttons
        self.freeze_btn = QPushButton("Freeze (Space)")
        self.save_btn = QPushButton("Save Frame (Ctrl+S)")
        self.fullscreen_btn = QPushButton("Fullscreen (F11)")
        self.disconnect_btn = QPushButton("Disconnect (Ctrl+D)")

        # Status label
        self.status_label = QLabel()

        # Initialize UI
        self.init_ui()
        self.setup_connections()
        self.setup_shortcuts()
        self.find_cameras()

    def init_ui(self):
        self.setWindowTitle("USB Camera Viewer with Freeze")
        self.setGeometry(100, 100, 900, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Menubar
        menubar = self.menuBar()
        help_menu = menubar.addMenu("Help")
        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self.show_about)

        # --- Camera selection layout ---
        camera_layout = QHBoxLayout()
        self.camera_label.setMinimumWidth(60)
        camera_layout.addWidget(self.camera_label)

        self.camera_combo.setMinimumWidth(200)
        camera_layout.addWidget(self.camera_combo)

        self.refresh_btn.setMaximumWidth(100)
        self.refresh_btn.clicked.connect(self.find_cameras)
        camera_layout.addWidget(self.refresh_btn)

        self.connect_btn.setMaximumWidth(150)
        camera_layout.addWidget(self.connect_btn)
        camera_layout.addStretch()
        main_layout.addLayout(camera_layout)

        # --- Video display ---
        self.video_label.setStyleSheet("border: 2px solid gray; background-color: black;")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setText("No camera connected")
        self.video_label.setMinimumSize(640, 480)
        main_layout.addWidget(self.video_label)

        # --- Flip controls ---
        flip_layout = QHBoxLayout()
        flip_layout.addWidget(self.flip_h_checkbox)
        flip_layout.addWidget(self.flip_v_checkbox)
        flip_layout.addStretch()
        main_layout.addLayout(flip_layout)

        # --- Action buttons ---
        button_layout = QHBoxLayout()
        self.freeze_btn.setEnabled(False)
        button_layout.addWidget(self.freeze_btn)

        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)

        self.fullscreen_btn.setEnabled(False)
        button_layout.addWidget(self.fullscreen_btn)

        button_layout.addStretch()

        self.disconnect_btn.setEnabled(False)
        button_layout.addWidget(self.disconnect_btn)
        main_layout.addLayout(button_layout)

        # --- Status label ---
        self.status_label.setText("Ready to connect to camera | F11: Fullscreen | Space: Freeze | Ctrl+S: Save")
        self.status_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        main_layout.addWidget(self.status_label)

    def setup_connections(self):
        self.connect_btn.clicked.connect(self.connect_camera)
        self.disconnect_btn.clicked.connect(self.disconnect_camera)
        self.freeze_btn.clicked.connect(self.toggle_freeze)
        self.save_btn.clicked.connect(self.save_frame)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.timer.timeout.connect(self.update_frame)
        self.flip_h_checkbox.toggled.connect(self.toggle_flip_horizontal)
        self.flip_v_checkbox.toggled.connect(self.toggle_flip_vertical)

    def setup_shortcuts(self):
        self.freeze_shortcut = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.freeze_shortcut.activated.connect(self.toggle_freeze)

        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_shortcut.activated.connect(self.save_frame)

        self.connect_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        self.connect_shortcut.activated.connect(self.connect_camera)

        self.disconnect_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        self.disconnect_shortcut.activated.connect(self.disconnect_camera)

        self.fullscreen_shortcut = QShortcut(QKeySequence(Qt.Key_F11), self)
        self.fullscreen_shortcut.activated.connect(self.toggle_fullscreen)

        self.flip_h_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        self.flip_h_shortcut.activated.connect(
            lambda: self.flip_h_checkbox.setChecked(not self.flip_h_checkbox.isChecked()))

        self.flip_v_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        self.flip_v_shortcut.activated.connect(
            lambda: self.flip_v_checkbox.setChecked(not self.flip_v_checkbox.isChecked()))

        self.escape_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.escape_shortcut.activated.connect(self.exit_fullscreen)

    def find_cameras(self):
        self.camera_combo.clear()
        available_cameras = []
        for i in range(6):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    available_cameras.append(f"Camera {i}")
                cap.release()
        if available_cameras:
            self.camera_combo.addItems(available_cameras)
            self.status_label.setText(f"Found {len(available_cameras)} camera(s)")
        else:
            self.camera_combo.addItem("No cameras found")
            self.status_label.setText("No cameras detected")

    def connect_camera(self):
        if self.camera_combo.count() == 0 or self.camera_combo.currentText() == "No cameras found":
            QMessageBox.warning(self, "Warning", "No cameras available!")
            return
        camera_text = self.camera_combo.currentText()
        camera_index = int(camera_text.split()[-1])
        self.camera = cv2.VideoCapture(camera_index)
        if not self.camera.isOpened():
            QMessageBox.critical(self, "Error", f"Failed to open camera {camera_index}")
            self.camera = None
            return
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.camera.set(cv2.CAP_PROP_FPS, 30)
        self.timer.start(33)
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.freeze_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.fullscreen_btn.setEnabled(True)
        self.camera_combo.setEnabled(False)
        self.flip_h_checkbox.setEnabled(True)
        self.flip_v_checkbox.setEnabled(True)
        self.status_label.setText(f"Connected to {camera_text}")
        self.is_frozen = False
        self.frozen_frame = None

    def disconnect_camera(self):
        if self.camera:
            self.timer.stop()
            self.camera.release()
            self.camera = None
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.freeze_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.fullscreen_btn.setEnabled(False)
        self.camera_combo.setEnabled(True)
        self.flip_h_checkbox.setEnabled(False)
        self.flip_v_checkbox.setEnabled(False)
        self.video_label.setText("No camera connected")
        self.video_label.setPixmap(QPixmap())
        self.status_label.setText("Disconnected from camera")
        self.is_frozen = False
        self.frozen_frame = None
        self.freeze_btn.setText("Freeze")

    def update_frame(self):
        if not self.camera or not self.camera.isOpened():
            # Auto-disconnect if camera was lost (e.g. after sleep)
            if self.camera:
                self.disconnect_camera()
                self.status_label.setText("Camera connection lost. Please reconnect.")
            return

        if not self.is_frozen:
            ret, frame = self.camera.read()
            if not ret or frame is None:
                # Same: camera feed died → disconnect
                self.disconnect_camera()
                self.status_label.setText("Camera feed unavailable. Please reconnect.")
                return
            processed_frame = self.apply_flips(frame)
            self.display_frame(processed_frame)
            self.current_frame = processed_frame.copy()
        else:
            if self.frozen_frame is not None:
                self.display_frame(self.frozen_frame)

    def display_frame(self, frame):
        if frame is None or frame.size == 0:
            return
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
        label_size = self.video_label.size()
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)

    def apply_flips(self, frame):
        if self.flip_horizontal and self.flip_vertical:
            return cv2.flip(frame, -1)
        elif self.flip_horizontal:
            return cv2.flip(frame, 1)
        elif self.flip_vertical:
            return cv2.flip(frame, 0)
        return frame

    def toggle_flip_horizontal(self, checked):
        self.flip_horizontal = checked

    def toggle_flip_vertical(self, checked):
        self.flip_vertical = checked

    def toggle_freeze(self):
        if not hasattr(self, 'current_frame'):
            return
        self.timer.stop()  # prevent collisions
        if not self.is_frozen:
            self.frozen_frame = self.current_frame.copy()
            self.is_frozen = True
            self.freeze_btn.setText("Unfreeze (Space)")
            self.status_label.setText("Image frozen - click Unfreeze to resume")
        else:
            self.is_frozen = False
            self.frozen_frame = None
            self.freeze_btn.setText("Freeze (Space)")
            camera_text = self.camera_combo.currentText()
            self.status_label.setText(f"Connected to {camera_text} - live view")
        self.timer.start(33)

    def save_frame(self):
        if self.is_frozen and self.frozen_frame is not None:
            frame_to_save = self.frozen_frame
        elif hasattr(self, 'current_frame'):
            frame_to_save = self.current_frame
        else:
            QMessageBox.warning(self, "Warning", "No frame to save!")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"camera_frame_{timestamp}.jpg"
        success = cv2.imwrite(filename, frame_to_save)
        if success:
            rgb_frame = cv2.cvtColor(frame_to_save, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            pixmap = QPixmap.fromImage(qt_image)
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(pixmap)
            self.status_label.setText(f"Frame saved as {filename} and copied to clipboard")
        else:
            QMessageBox.critical(self, "Error", "Failed to save frame!")

    def toggle_fullscreen(self):
        if not self.is_fullscreen:
            self.enter_fullscreen()
        else:
            self.exit_fullscreen()

    def enter_fullscreen(self):
        if not hasattr(self, 'current_frame') and not self.is_frozen:
            QMessageBox.information(self, "Info", "Connect to a camera first to use fullscreen mode.")
            return
        if self.is_fullscreen:
            return
        self.is_fullscreen = True
        self.normal_geometry = self.geometry()
        self._hidden_widgets = []
        self.showFullScreen()
        for widget in self.centralWidget().findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            if widget is not self.video_label and widget.isVisible():
                self._hidden_widgets.append(widget)
                widget.hide()
        self.video_label.setStyleSheet("border: none; background-color: black;")
        self.setMouseTracking(True)
        self.video_label.setMouseTracking(True)
        self.create_fullscreen_overlay()
        self.setCursor(Qt.ArrowCursor)
        self.mouse_timer.start(self.mouse_hide_delay)

    def exit_fullscreen(self):
        if not self.is_fullscreen:
            return
        self.is_fullscreen = False
        self.setMouseTracking(False)
        self.mouse_timer.stop()
        if hasattr(self, 'fullscreen_overlay'):
            self.fullscreen_overlay.hide()
            self.fullscreen_overlay.deleteLater()
            delattr(self, 'fullscreen_overlay')
        self.setCursor(Qt.ArrowCursor)
        if hasattr(self, '_hidden_widgets'):
            for w in self._hidden_widgets:
                w.show()
            self._hidden_widgets = []
        self.video_label.setStyleSheet("border: 2px solid gray; background-color: black;")
        self.showNormal()
        if hasattr(self, 'normal_geometry'):
            self.setGeometry(self.normal_geometry)

    def create_fullscreen_overlay(self):
        parent = self.centralWidget()
        self.fullscreen_overlay = QWidget(parent)
        self.fullscreen_overlay.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 180);
                border-radius: 10px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 200);
                border: none;
                color: black;
                padding: 8px 15px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 5px;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 255);
            }
        """)
        layout = QHBoxLayout(self.fullscreen_overlay)
        btn = QPushButton("Freeze (Space)", self.fullscreen_overlay)
        btn.clicked.connect(self.toggle_freeze)
        layout.addWidget(btn)
        btn = QPushButton("Save (Ctrl+S)", self.fullscreen_overlay)
        btn.clicked.connect(self.save_frame)
        layout.addWidget(btn)
        btn = QPushButton("Flip H (Ctrl+H)", self.fullscreen_overlay)
        btn.clicked.connect(lambda: self.flip_h_checkbox.setChecked(not self.flip_h_checkbox.isChecked()))
        layout.addWidget(btn)
        btn = QPushButton("Flip V (Ctrl+V)", self.fullscreen_overlay)
        btn.clicked.connect(lambda: self.flip_v_checkbox.setChecked(not self.flip_v_checkbox.isChecked()))
        layout.addWidget(btn)
        btn = QPushButton("Exit (Esc)", self.fullscreen_overlay)
        btn.clicked.connect(self.exit_fullscreen)
        layout.addWidget(btn)
        self.fullscreen_overlay.resize(500, 60)
        self.position_overlay()
        self.fullscreen_overlay.show()

    def position_overlay(self):
        if hasattr(self, 'fullscreen_overlay') and self.fullscreen_overlay and self.is_fullscreen:
            parent = self.centralWidget()
            screen_size = parent.size()
            overlay_size = self.fullscreen_overlay.size()
            x = (screen_size.width() - overlay_size.width()) // 2
            y = screen_size.height() - overlay_size.height() - 50
            self.fullscreen_overlay.move(x, y)

    def hide_controls_in_fullscreen(self):
        if self.is_fullscreen and hasattr(self, 'fullscreen_overlay'):
            self.fullscreen_overlay.hide()
            self.setCursor(Qt.BlankCursor)

    def mouseMoveEvent(self, event):
        if self.is_fullscreen:
            if hasattr(self, 'fullscreen_overlay'):
                self.fullscreen_overlay.show()
                self.position_overlay()
            self.setCursor(Qt.ArrowCursor)
            self.mouse_timer.stop()
            self.mouse_timer.start(self.mouse_hide_delay)
        super().mouseMoveEvent(event)

    def resizeEvent(self, event):
        if self.is_fullscreen and hasattr(self, 'fullscreen_overlay'):
            self.position_overlay()
        super().resizeEvent(event)

    def closeEvent(self, event):
        if self.camera:
            self.disconnect_camera()
        event.accept()

    def show_about(self):
        about_text = """
        <h3>Camera Viewer with Freeze</h3>
        <p>This application allows you to:</p>
        <ul>
            <li>Connect to available cameras</li>
            <li>Freeze and unfreeze the live feed</li>
            <li>Flip the video horizontally or vertically</li>
            <li>Save frames and copy them to the clipboard</li>
            <li>Enter fullscreen mode with overlay controls</li>
        </ul>
        <p style='margin-top:10px;'>
            Copyright © 2025 Michael Phoenix (Mykhailo Pozdnikin). All rights reserved.<br>
            Redistribution, modification, or commercial use without explicit permission is strictly prohibited.
        </p>
        """
        QMessageBox.about(self, "About Camera Viewer", about_text)


def main():
    app = QApplication(sys.argv)
    try:
        cv2.__version__
    except:
        QMessageBox.critical(None, "Error", "OpenCV not found! Please install it with: pip install opencv-python")
        sys.exit(1)
    window = CameraViewer()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
