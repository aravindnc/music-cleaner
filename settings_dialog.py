from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, 
                             QSlider, QCheckBox, QGroupBox, QFormLayout)
from PySide6.QtCore import Qt, Signal

class SettingsDialog(QDialog):
    """Clean, focused Settings Dialog for MusicCleaner."""

    settings_saved = Signal(dict)

    def __init__(self, current_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ MusicCleaner Settings")
        self.resize(460, 360)
        self.setMinimumSize(400, 300)
        self.settings = dict(current_settings)

        self.init_ui()

    def init_ui(self):
        # Base Dark Styling
        self.setStyleSheet("""
            QDialog, QWidget {
                background-color: #121214;
                color: #e0e0e0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #2a2a30;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #00adb5;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #25252b;
                color: #ffffff;
                border: 1px solid #3a3a42;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #32323a;
                border-color: #00adb5;
            }
            QPushButton#save_btn {
                background-color: #00adb5;
                color: #000000;
            }
            QPushButton#save_btn:hover {
                background-color: #00c4ce;
            }
            QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #25252b;
                color: #ffffff;
                border: 1px solid #3a3a42;
                border-radius: 4px;
                padding: 5px 8px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #2a2a30;
                height: 6px;
                background: #25252b;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #00adb5;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #00adb5;
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #3a3a42;
                background-color: #25252b;
            }
            QCheckBox::indicator:checked {
                background-color: #00adb5;
                border-color: #00adb5;
            }
        """)

        layout = QVBoxLayout(self)

        # 1. Playback Group
        audio_group = QGroupBox("🎵 Audio & Playback Controls")
        audio_form = QFormLayout(audio_group)
        audio_form.setSpacing(12)

        # Startup Volume
        vol_layout = QHBoxLayout()
        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_spin = QSpinBox()
        self.vol_spin.setRange(0, 100)
        self.vol_spin.setSuffix("%")

        val_vol = int(self.settings.get('volume', 80))
        self.vol_slider.setValue(val_vol)
        self.vol_spin.setValue(val_vol)
        self.vol_slider.valueChanged.connect(self.vol_spin.setValue)
        self.vol_spin.valueChanged.connect(self.vol_slider.setValue)

        vol_layout.addWidget(self.vol_slider)
        vol_layout.addWidget(self.vol_spin)
        audio_form.addRow("Startup Volume:", vol_layout)

        self.preview_mode_combo = QComboBox()
        self.preview_mode_combo.addItems([
            "Loudest Peak (Chorus)",
            "Start of song (0:00)",
            "Custom Offset (sec)",
            "Middle + 30s",
            "Random point"
        ])
        mode_val = self.settings.get('preview_mode', 'Loudest Peak (Chorus)')
        if mode_val in [self.preview_mode_combo.itemText(i) for i in range(self.preview_mode_combo.count())]:
            self.preview_mode_combo.setCurrentText(mode_val)

        audio_form.addRow("Song Start Position Mode:", self.preview_mode_combo)

        # Custom Start Position (sec)
        self.custom_start_spin = QDoubleSpinBox()
        self.custom_start_spin.setRange(0.0, 300.0)
        self.custom_start_spin.setSingleStep(5.0)
        self.custom_start_spin.setSuffix(" sec")
        self.custom_start_spin.setValue(float(self.settings.get('custom_start_sec', 0.0)))
        audio_form.addRow("Custom Start Time (for every song):", self.custom_start_spin)

        # Auto-skip Timer
        auto_skip_layout = QHBoxLayout()
        self.auto_skip_cb = QCheckBox("Auto-advance after preview duration:")
        self.auto_skip_cb.setChecked(str(self.settings.get('auto_skip_enabled', 'False')).lower() == 'true')
        self.auto_skip_spin = QSpinBox()
        self.auto_skip_spin.setRange(3, 120)
        self.auto_skip_spin.setSuffix(" sec")
        self.auto_skip_spin.setValue(int(self.settings.get('auto_skip_sec', 15)))

        auto_skip_layout.addWidget(self.auto_skip_cb)
        auto_skip_layout.addWidget(self.auto_skip_spin)
        audio_form.addRow("Auto Preview Skip:", auto_skip_layout)

        layout.addWidget(audio_group)

        # 2. Curation Group
        action_group = QGroupBox("🗑️ Curation Options")
        action_form = QFormLayout(action_group)
        action_form.setSpacing(12)

        self.delete_mode_combo = QComboBox()
        self.delete_mode_combo.addItem("Move to Recycle Bin (Safe / Undoable)", "recycle_bin")
        self.delete_mode_combo.addItem("Permanent Delete (Irreversible)", "permanent")
        
        del_val = self.settings.get('delete_mode', 'recycle_bin')
        idx = self.delete_mode_combo.findData(del_val)
        if idx >= 0:
            self.delete_mode_combo.setCurrentIndex(idx)

        action_form.addRow("Delete Action Behavior:", self.delete_mode_combo)
        layout.addWidget(action_group)

        layout.addStretch()

        # Dialog Action Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("save_btn")
        self.cancel_btn = QPushButton("Cancel")

        self.save_btn.clicked.connect(self.on_save)
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def on_save(self):
        new_settings = {
            'volume': str(self.vol_spin.value()),
            'preview_mode': self.preview_mode_combo.currentText(),
            'custom_start_sec': str(self.custom_start_spin.value()),
            'auto_skip_enabled': str(self.auto_skip_cb.isChecked()),
            'auto_skip_sec': str(self.auto_skip_spin.value()),
            'delete_mode': self.delete_mode_combo.currentData(),
        }
        self.settings.update(new_settings)
        self.settings_saved.emit(self.settings)
        self.accept()
