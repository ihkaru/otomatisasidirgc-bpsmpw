
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from qfluentwidgets import setTheme, Theme, setThemeColor
from dirgc.gui.utils.styling import apply_app_font
from dirgc.gui.main_window import MainWindow

def main():
    # High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    
    # Theme & Styling
    setTheme(Theme.LIGHT)
    setThemeColor('#0078D4') # Brand color
    apply_app_font(app)
    
    w = MainWindow()
    w.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    from PyQt5.QtCore import Qt # Import locally if needed or top level
    main()
