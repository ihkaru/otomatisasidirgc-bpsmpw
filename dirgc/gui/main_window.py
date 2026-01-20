
from PyQt5.QtGui import QIcon
from qfluentwidgets import FluentWindow, NavigationItemPosition, FluentIcon as FIF
from dirgc.gui.pages.run_page import RunPage
from dirgc.gui.pages.sso_page import SsoPage
from dirgc.gui.state.settings_manager import SettingsManager

class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Otomatisasi DIRGC 6502")
        self.resize(1100, 750)
        
        # Determine start position
        # We can center it or save/load geometry
        
        self.sso_page = SsoPage(self)
        self.run_page = RunPage(sso_page=self.sso_page, parent=self)
        
        self.init_navigation()

    def init_navigation(self):
        self.addSubInterface(
            self.run_page,
            FIF.PLAY,
            "Run Automation",
            NavigationItemPosition.TOP
        )
        self.addSubInterface(
            self.sso_page,
            FIF.PEOPLE,
            "SSO Credentials",
            NavigationItemPosition.TOP
        )
        
        # Settings page could be added here later
        
        self.navigationInterface.setCurrentItem(self.run_page.objectName())

    def closeEvent(self, event):
        # We could save window geometry here
        event.accept()
