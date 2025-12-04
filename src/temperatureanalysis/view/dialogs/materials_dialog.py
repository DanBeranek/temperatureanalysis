"""
Modal Dialog for Material Properties
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox


class MaterialsDialog(QDialog):
    def __init__(self, project_state, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Správce Materiálů")
        self.resize(800, 600)
        self.project = project_state

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Material properties graph and table will go here."))

        # Standard Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
