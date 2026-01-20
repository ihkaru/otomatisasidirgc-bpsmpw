
import os
import json
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QBoxLayout, QFormLayout, 
    QPlainTextEdit, QFileDialog
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from qfluentwidgets import (
    TitleLabel, BodyLabel, SubtitleLabel, PushButton, PrimaryPushButton, 
    LineEdit, SwitchButton, SpinBox, InfoBar, InfoBarPosition
)

from dirgc.settings import DEFAULT_EXCEL_FILE, LAST_RUN_STATE_FILE
from dirgc.run_logs import get_last_processed_row
from dirgc.gui.components.cards import build_card
from dirgc.gui.components.option_row import OptionRow
from dirgc.gui.workers.run_worker import RunWorker
from dirgc.gui.state.settings_manager import SettingsManager
from dirgc.gui.state.run_config import RunConfig
from dirgc.gui.utils.dialogs import DialogHelper
from dirgc.gui.utils.styling import build_footer_label, RESPONSIVE_BREAKPOINT

class RunPage(QWidget):
    def __init__(self, sso_page=None, parent=None):
        super().__init__(parent)
        self.setObjectName("runPage")
        self._worker = None
        self._sso_page = sso_page
        self._recent_excels = SettingsManager.load().get("recent_excels", [])

        # UI Setup
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        layout.addWidget(TitleLabel("Run DIRGC"))
        layout.addWidget(BodyLabel("Atur file, opsi, lalu jalankan proses."))

        content = QWidget()
        self._content_layout = QBoxLayout(QBoxLayout.LeftToRight, content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(16)

        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(16)
        left_layout.addWidget(self._build_files_card())
        left_layout.addWidget(self._build_options_card())
        left_layout.addStretch()

        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)
        right_layout.addWidget(self._build_run_card())
        right_layout.addWidget(self._build_log_card(), stretch=1)

        self._content_layout.addWidget(left_col, stretch=2)
        self._content_layout.addWidget(right_col, stretch=3)

        layout.addWidget(content, stretch=1)
        layout.addWidget(build_footer_label())

        self._is_stacked = False
        self._update_layout_mode(self.width())
        self._load_settings()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_layout_mode(event.size().width())

    def _update_layout_mode(self, width):
        stacked = width < RESPONSIVE_BREAKPOINT
        if stacked == self._is_stacked:
            return
        direction = QBoxLayout.TopToBottom if stacked else QBoxLayout.LeftToRight
        self._content_layout.setDirection(direction)
        self._is_stacked = stacked

    def _build_files_card(self):
        def build(layout):
            form = QFormLayout()
            form.setHorizontalSpacing(12)
            form.setVerticalSpacing(8)
            form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            
            self.excel_input = LineEdit()
            self.excel_input.setPlaceholderText("data/Direktori_SBR_20260114.xlsx")
            self.excel_input.editingFinished.connect(self._on_excel_edit_finished)
            
            browse_btn = PushButton("Browse")
            browse_btn.clicked.connect(lambda: self._browse_file(self.excel_input, "Excel (*.xlsx *.xls)"))
            
            # Recent files handling (simplified)
            # We could add a combobox here if needed like original app
            
            form.addRow("Excel File:", self.excel_input)
            form.addRow("", browse_btn)
            layout.addLayout(form)
            
        card, _ = build_card("Files", build)
        return card

    def _build_options_card(self):
        def build(layout):
            self.manual_switch = SwitchButton("Off")
            self.headless_switch = SwitchButton("Off")
            self.keep_open_switch = SwitchButton("Off")
            
            self.range_switch = SwitchButton("Off")
            self.range_switch.checkedChanged.connect(self._toggle_range)
            
            self.start_spin = SpinBox()
            self.start_spin.setRange(1, 999999)
            self.start_spin.setValue(1)
            self.end_spin = SpinBox()
            self.end_spin.setRange(1, 999999)
            self.end_spin.setValue(100)
            
            range_controls = QHBoxLayout()
            range_controls.addWidget(self.start_spin)
            range_controls.addWidget(BodyLabel("to"))
            range_controls.addWidget(self.end_spin)
            
            self.idle_spin = SpinBox()
            self.idle_spin.setRange(60, 3600)
            self.idle_spin.setValue(300)
            self.idle_spin.setSuffix(" s")
            
            self.web_timeout_spin = SpinBox()
            self.web_timeout_spin.setRange(5, 300)
            self.web_timeout_spin.setValue(10)
            self.web_timeout_spin.setSuffix(" s")

            layout.addWidget(OptionRow("Manual Only", "Skip auto-fill/submit", self.manual_switch))
            layout.addWidget(OptionRow("Headless", "Run background", self.headless_switch))
            layout.addWidget(OptionRow("Keep Open", "Don't close browser", self.keep_open_switch))
            
            layout.addWidget(OptionRow("Limit Range", "Start - End rows", self.range_switch))
            layout.addLayout(range_controls)
            
            layout.addWidget(OptionRow("Idle Timeout", "Stop if idle", self.idle_spin))
            layout.addWidget(OptionRow("Web Timeout", "Wait for loading", self.web_timeout_spin))

        card, _ = build_card("Options", build)
        return card

    def _build_run_card(self):
        def build(layout):
            self.status_label = SubtitleLabel("Status: idle")
            
            buttons = QHBoxLayout()
            self.start_button = PrimaryPushButton("Start Run")
            self.start_button.clicked.connect(self._confirm_start)
            
            self.stop_button = PushButton("Stop")
            self.stop_button.clicked.connect(self._confirm_stop)
            self.stop_button.setEnabled(False)
            
            buttons.addWidget(self.start_button)
            buttons.addWidget(self.stop_button)
            
            layout.addWidget(self.status_label)
            layout.addLayout(buttons)
            
        card, _ = build_card("Control", build)
        return card

    def _build_log_card(self):
        def build(layout):
            self.log_output = QPlainTextEdit()
            self.log_output.setReadOnly(True)
            self.log_output.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
            
            layout.addWidget(self.log_output)
            
            # Action buttons
            actions = QHBoxLayout()
            open_logs_btn = PushButton("Buka Folder Logs")
            open_logs_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath("logs"))))
            clear_logs_btn = PushButton("Bersihkan Log")
            clear_logs_btn.clicked.connect(self.log_output.clear)
            
            actions.addWidget(open_logs_btn)
            actions.addWidget(clear_logs_btn)
            layout.addLayout(actions)

        card, _ = build_card("Logs", build)
        # Hack to make log output expand
        # Log card usually needs to stretch
        return card

    def _confirm_start(self):
        # Resume Logic
        last_row = 0
        if os.path.exists(LAST_RUN_STATE_FILE):
             try:
                 with open(LAST_RUN_STATE_FILE, "r") as f:
                     state = json.load(f)
                     last_row = int(state.get("last_row", 0))
             except Exception:
                 pass
        
        if last_row == 0:
            last_row = get_last_processed_row()

        if last_row > 0:
            result = DialogHelper.resume_dialog(self, last_row)
            if result == "resume":
                self.range_switch.setChecked(True)
                next_start = last_row + 1
                self.start_spin.setValue(next_start)
                if next_start > self.end_spin.value():
                     self.end_spin.setValue(self.end_spin.maximum())
                if self.end_spin.value() < next_start:
                     self.end_spin.setValue(next_start)
                self._start_run()
                return
            elif result == "manual":
                self._start_run()
                return
            else: # cancel
                return

        if DialogHelper.confirm(self, "Mulai proses", "Mulai proses sekarang?"):
            self._start_run()

    def _start_run(self):
        self._save_settings()
        
        config = RunConfig(
            headless=self.headless_switch.isChecked(),
            manual_only=self.manual_switch.isChecked(),
            excel_file=self.excel_input.text() or DEFAULT_EXCEL_FILE,
            start_row=self.start_spin.value(),
            end_row=self.end_spin.value(),
            idle_timeout_ms=self.idle_spin.value() * 1000,
            web_timeout_s=self.web_timeout_spin.value(),
            range_enabled=self.range_switch.isChecked(),
            keep_open=self.keep_open_switch.isChecked()
        )

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Status: running")
        self.log_output.appendPlainText("=== START RUN ===")
        
        self._worker = RunWorker(config, self._sso_page)
        self._worker.log_emitted.connect(self._append_log)
        self._worker.finished.connect(self._run_finished)
        self._worker.start()

    def _confirm_stop(self):
        if DialogHelper.confirm(self, "Hentikan", "Yakin stop?"):
             if self._worker:
                 self._worker.request_stop()
                 self.status_label.setText("Status: stopping")
                 self.stop_button.setEnabled(False)

    def _run_finished(self):
        self.status_label.setText("Status: finished")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.log_output.appendPlainText("=== FINISHED ===")

    def _append_log(self, text):
        self.log_output.appendPlainText(text)

    def _browse_file(self, input_widget, filter):
        path, _ = QFileDialog.getOpenFileName(self, "Select", "", filter)
        if path:
            input_widget.setText(path)
            self._save_settings()

    def _on_excel_edit_finished(self):
        self._save_settings()

    def _toggle_range(self):
        enabled = self.range_switch.isChecked()
        self.start_spin.setEnabled(enabled)
        self.end_spin.setEnabled(enabled)

    def _load_settings(self):
        data = SettingsManager.load()
        # simplified load logic mapping...
        # ... (Assuming similar logic to app.py but cleaner)
        if "options" in data:
            opts = data["options"]
            self.manual_switch.setChecked(opts.get("manual_only", False))
            self.headless_switch.setChecked(opts.get("headless", False))
            self.keep_open_switch.setChecked(opts.get("keep_open", False))
            self.range_switch.setChecked(opts.get("range_enabled", False))
            self.start_spin.setValue(opts.get("start_row", 1))
            self.end_spin.setValue(opts.get("end_row", 100))
            self.idle_spin.setValue(opts.get("idle_timeout_s", 300))
            self.web_timeout_spin.setValue(opts.get("web_timeout_s", 10))
        
        path = data.get("excel_path")
        if path:
            self.excel_input.setText(path)
            
        self._toggle_range()

    def _save_settings(self):
        data = SettingsManager.load()
        data["excel_path"] = self.excel_input.text()
        data["options"] = {
            "manual_only": self.manual_switch.isChecked(),
            "headless": self.headless_switch.isChecked(),
            "keep_open": self.keep_open_switch.isChecked(),
            "range_enabled": self.range_switch.isChecked(),
            "start_row": self.start_spin.value(),
            "end_row": self.end_spin.value(),
            "idle_timeout_s": self.idle_spin.value(),
            "web_timeout_s": self.web_timeout_spin.value(),
        }
        SettingsManager.save(data)
