
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from qfluentwidgets import StrongBodyLabel, CaptionLabel, CardWidget, SubtitleLabel

class OptionRow(QWidget):
    def __init__(self, title, description, switch, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        text_block = QWidget()
        text_layout = QVBoxLayout(text_block)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        title_label = StrongBodyLabel(title)
        desc_label = CaptionLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #6B6B6B;")

        text_layout.addWidget(title_label)
        text_layout.addWidget(desc_label)

        layout.addWidget(text_block, stretch=1)
        layout.addWidget(switch)
