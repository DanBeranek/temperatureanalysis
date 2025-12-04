"""
Modal Dialog for Boundary Conditions
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox


class BCDialog(QDialog):
    def __init__(self, project_state, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Okrajové Podmínky (Požární Křivky)")
        self.resize(800, 600)
        self.project = project_state

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Temperature-Time curves and BC assignments go here."))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
