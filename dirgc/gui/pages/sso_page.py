
import json
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFormLayout
from PyQt5.QtCore import Qt
from qfluentwidgets import (
    SwitchButton, LineEdit, PasswordLineEdit, 
    TitleLabel, BodyLabel, PrimaryPushButton, InfoBar
)
from dirgc.settings import DEFAULT_CREDENTIALS_FILE

class SsoPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ssoPage")
        self.username_input = LineEdit()
        self.username_input.setPlaceholderText("Username SSO")
        self.password_input = PasswordLineEdit()
        self.password_input.setPlaceholderText("Password SSO")
        self.use_switch = SwitchButton("Off")
        
        self._init_ui()
        self._load_credentials_from_file()
        
        # Connect signals for auto-save
        self.username_input.textChanged.connect(self._save_credentials_to_file)
        self.password_input.textChanged.connect(self._save_credentials_to_file)
        self.use_switch.checkedChanged.connect(self._save_credentials_to_file)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(TitleLabel("SSO Login"))
        layout.addWidget(BodyLabel("Masukkan akun SSO untuk login otomatis."))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.addRow("Username:", self.username_input)
        form.addRow("Password:", self.password_input)
        form.addRow("Gunakan SSO:", self.use_switch)

        layout.addLayout(form)
        layout.addStretch(1)

        self.use_switch.checkedChanged.connect(self._toggle_inputs)
        self._toggle_inputs(self.use_switch.isChecked())

    def _toggle_inputs(self, checked):
        state = "On" if checked else "Off"
        self.use_switch.setText(state)
        self.username_input.setEnabled(checked)
        self.password_input.setEnabled(checked)

    def get_credentials(self):
        if not self.use_switch.isChecked():
            return None
        
        user = self.username_input.text()
        pwd = self.password_input.text()
        if not user or not pwd:
            return None
        return {"username": user, "password": pwd}

    def _load_credentials_from_file(self):
        if os.path.exists(DEFAULT_CREDENTIALS_FILE):
             try:
                 with open(DEFAULT_CREDENTIALS_FILE, 'r') as f:
                     data = json.load(f)
                     user = data.get("username", "")
                     pwd = data.get("password", "")
                     
                     if user:
                         self.username_input.setText(user)
                         self.password_input.setText(pwd)
                         self.use_switch.setChecked(True)
             except Exception:
                 pass

    def _save_credentials_to_file(self):
        if not self.use_switch.isChecked():
            # Should we delete the file if switch is off? Or just not use it?
            # Existing logic was just return logic mostly.
            # But let's save what is there.
            pass
        
        user = self.username_input.text().strip()
        pwd = self.password_input.text()
        
        # We save even if switch is off, so it is remembered next time
        if not user: 
            return

        data = {"username": user, "password": pwd}
        try:
            os.makedirs(os.path.dirname(DEFAULT_CREDENTIALS_FILE), exist_ok=True)
            with open(DEFAULT_CREDENTIALS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
