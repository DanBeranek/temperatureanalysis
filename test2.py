from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QListWidget, QStackedWidget,
    QWidget, QVBoxLayout, QToolBar, QStatusBar, QProgressBar, QPlainTextEdit,
    QSplitter, QLabel, QScrollArea, QFormLayout
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

class Inspector(QWidget):
    def __init__(self):
        super().__init__()
        form = QFormLayout()
        form.addRow("Name:", QLabel("—"))
        scroller = QScrollArea()
        inner = QWidget()
        inner.setLayout(form)
        scroller.setWidget(inner)
        scroller.setWidgetResizable(True)
        lay = QVBoxLayout(self)
        lay.addWidget(scroller)

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fire Heat Analysis")

        # Toolbar
        tb = QToolBar(); self.addToolBar(tb)
        act_run = QAction("Run", self); tb.addAction(act_run)

        # Left nav
        nav = QListWidget(); nav.addItems([
            "Project","Geometry","Materials","Fire & BCs","Mesh","Solver","Scenarios","Results","Report"
        ])

        # Center stack
        stack = QStackedWidget()
        for name in [ "Project","Geometry","Materials","Fire & BCs","Mesh","Solver","Scenarios","Results","Report" ]:
            w = QWidget(); w.setLayout(QVBoxLayout()); w.layout().addWidget(QLabel(f"{name} view"))
            stack.addWidget(w)
        nav.currentRowChanged.connect(stack.setCurrentIndex)
        nav.setCurrentRow(1)

        # Right inspector dock
        insp = Inspector()
        insp_dock = QDockWidget("Properties"); insp_dock.setWidget(insp); self.addDockWidget(Qt.RightDockWidgetArea, insp_dock)

        # Bottom console dock
        console = QPlainTextEdit(); console.setReadOnly(True)
        cons_dock = QDockWidget("Console"); cons_dock.setWidget(console)
        self.addDockWidget(Qt.BottomDockWidgetArea, cons_dock)

        # Splitter central (Left | Center)
        left_center = QSplitter()
        left_center.addWidget(nav)
        left_center.addWidget(stack)
        left_center.setStretchFactor(1, 1)
        self.setCentralWidget(left_center)

        # Status
        sb = QStatusBar(); prog = QProgressBar(); prog.setMaximumWidth(180)
        sb.addPermanentWidget(prog); self.setStatusBar(sb)

if __name__ == "__main__":
    app = QApplication([])
    win = Main(); win.resize(1280, 800); win.show()
    app.exec()
