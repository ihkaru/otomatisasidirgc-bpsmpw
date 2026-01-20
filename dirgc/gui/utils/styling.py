
import os
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtCore import Qt
from qfluentwidgets import CaptionLabel

RESPONSIVE_BREAKPOINT = 980
FOOTER_STYLE = "color: #6B6B6B;"
CAPTION_STYLE = "color: #6B6B6B;"

def apply_app_font(app):
    font_path = os.path.join("assets", "fonts", "Poppins-Regular.ttf")
    if os.path.exists(font_path):
        QFontDatabase.addApplicationFont(font_path)
    families = QFontDatabase().families()
    if "Poppins" in families:
        app.setFont(QFont("Poppins", 10))
    else:
        app.setFont(QFont("Segoe UI Variable", 10))

def build_footer_label():
    footer = CaptionLabel(
        "Made with ❤️and ☕ - Novanni Indi Pradana - IPDS BPS 6502"
    )
    footer.setAlignment(Qt.AlignCenter)
    footer.setStyleSheet(FOOTER_STYLE)
    return footer
