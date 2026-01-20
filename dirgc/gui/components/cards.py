
from PyQt5.QtWidgets import QFormLayout, QVBoxLayout
from qfluentwidgets import CardWidget, SubtitleLabel
from PyQt5.QtCore import Qt

def build_card(title, widget_builder_func=None):
    card = CardWidget()
    card_layout = QVBoxLayout(card)
    card_layout.addWidget(SubtitleLabel(title))
    if widget_builder_func:
        widget_builder_func(card_layout)
    return card, card_layout

def setup_form_layout():
    form = QFormLayout()
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(8)
    form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return form
