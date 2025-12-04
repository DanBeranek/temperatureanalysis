from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSlider
from PySide6.QtCore import Qt


class ResultsControlPanel(QWidget):
    def __init__(self, project_state):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Analýza Výsledků"))
        layout.addWidget(QLabel("Časový krok:"))

        slider = QSlider(Qt.Horizontal)
        layout.addWidget(slider)

        layout.addStretch()
