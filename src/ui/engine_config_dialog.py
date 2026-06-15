import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QPushButton, QLabel, QLineEdit, QSpinBox, QComboBox, QFileDialog,
    QListWidget, QListWidgetItem, QMessageBox, QCheckBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt

class EngineConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Engine Configuration")
        self.resize(600, 500)

        self.engines = {}  # key: engine name, value: dict with path, options
        self.load_config()

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Tab 1: Engine List
        self.tab_engines = QWidget()
        self.tabs.addTab(self.tab_engines, "Engines")
        self._setup_engines_tab()

        # Tab 2: Analysis Defaults
        self.tab_analysis = QWidget()
        self.tabs.addTab(self.tab_analysis, "Analysis")
        self._setup_analysis_tab()

        # Tab 3: Play Against Engine
        self.tab_play = QWidget()
        self.tabs.addTab(self.tab_play, "Play")
        self._setup_play_tab()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.save_config)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _setup_engines_tab(self):
        layout = QHBoxLayout(self.tab_engines)
        self.engine_list = QListWidget()
        self.engine_list.currentItemChanged.connect(self._on_engine_selected)
        layout.addWidget(self.engine_list)

        right_layout = QVBoxLayout()
        self.engine_name_edit = QLineEdit()
        self.engine_name_edit.setPlaceholderText("Engine name")
        self.engine_path_edit = QLineEdit()
        self.engine_path_edit.setPlaceholderText("Path to executable")
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_engine_path)
        right_layout.addWidget(QLabel("Name:"))
        right_layout.addWidget(self.engine_name_edit)
        right_layout.addWidget(QLabel("Path:"))
        right_layout.addWidget(self.engine_path_edit)
        right_layout.addWidget(btn_browse)
        right_layout.addStretch()

        btn_add = QPushButton("Add Engine")
        btn_add.clicked.connect(self._add_engine)
        btn_remove = QPushButton("Remove Engine")
        btn_remove.clicked.connect(self._remove_engine)
        right_layout.addWidget(btn_add)
        right_layout.addWidget(btn_remove)
        layout.addLayout(right_layout)

        self._populate_engine_list()

    def _setup_analysis_tab(self):
        layout = QFormLayout(self.tab_analysis)
        self.analysis_engine_combo = QComboBox()
        self.analysis_engine_combo.addItems(self.engines.keys())
        self.analysis_time_spin = QSpinBox()
        self.analysis_time_spin.setRange(100, 30000)
        self.analysis_time_spin.setValue(5000)
        self.analysis_time_spin.setSuffix(" ms")
        self.analysis_depth_spin = QSpinBox()
        self.analysis_depth_spin.setRange(0, 99)
        self.analysis_depth_spin.setSpecialValueText("Unlimited")
        self.analysis_multipv_spin = QSpinBox()
        self.analysis_multipv_spin.setRange(1, 5)
        self.analysis_multipv_spin.setValue(1)
        layout.addRow("Engine:", self.analysis_engine_combo)
        layout.addRow("Move time:", self.analysis_time_spin)
        layout.addRow("Depth:", self.analysis_depth_spin)
        layout.addRow("MultiPV:", self.analysis_multipv_spin)

    def _setup_play_tab(self):
        layout = QFormLayout(self.tab_play)
        self.play_engine_combo = QComboBox()
        self.play_engine_combo.addItems(self.engines.keys())
        self.play_time_spin = QSpinBox()
        self.play_time_spin.setRange(100, 30000)
        self.play_time_spin.setValue(5000)
        self.play_time_spin.setSuffix(" ms")
        self.play_depth_spin = QSpinBox()
        self.play_depth_spin.setRange(0, 99)
        self.play_depth_spin.setSpecialValueText("Unlimited")
        layout.addRow("Engine:", self.play_engine_combo)
        layout.addRow("Move time:", self.play_time_spin)
        layout.addRow("Depth:", self.play_depth_spin)

    def _populate_engine_list(self):
        self.engine_list.clear()
        for name in self.engines:
            item = QListWidgetItem(name)
            self.engine_list.addItem(item)

    def _on_engine_selected(self, current, previous):
        if current is None:
            return
        name = current.text()
        eng = self.engines.get(name, {})
        self.engine_name_edit.setText(name)
        self.engine_path_edit.setText(eng.get("path", ""))

    def _browse_engine_path(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Engine Executable")
        if path:
            self.engine_path_edit.setText(path)

    def _add_engine(self):
        name = self.engine_name_edit.text().strip()
        path = self.engine_path_edit.text().strip()
        if not name or not path:
            QMessageBox.warning(self, "Error", "Name and path are required.")
            return
        self.engines[name] = {"path": path, "options": {}}
        self._populate_engine_list()
        self.analysis_engine_combo.addItem(name)
        self.play_engine_combo.addItem(name)

    def _remove_engine(self):
        current = self.engine_list.currentItem()
        if not current:
            return
        name = current.text()
        del self.engines[name]
        self._populate_engine_list()
        # Remove from combos
        for combo in (self.analysis_engine_combo, self.play_engine_combo):
            index = combo.findText(name)
            if index >= 0:
                combo.removeItem(index)

    def load_config(self):
        try:
            with open("config/engines.json", "r") as f:
                data = json.load(f)
                self.engines = data.get("engines", {})
        except FileNotFoundError:
            self.engines = {}

    def save_config(self):
        data = {
            "engines": self.engines,
            "analysis_engine": self.analysis_engine_combo.currentText(),
            "analysis_time": self.analysis_time_spin.value(),
            "analysis_depth": self.analysis_depth_spin.value(),
            "analysis_multipv": self.analysis_multipv_spin.value(),
            "play_engine": self.play_engine_combo.currentText(),
            "play_time": self.play_time_spin.value(),
            "play_depth": self.play_depth_spin.value(),
        }
        import os
        os.makedirs("config", exist_ok=True)
        with open("config/engines.json", "w") as f:
            json.dump(data, f, indent=2)
        QMessageBox.information(self, "Saved", "Engine configuration saved.")
        self.accept()