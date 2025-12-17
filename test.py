# main.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Tuple, Protocol, List
import sys
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPen, QBrush, QColor, QPainterPath, QPainter
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QDialog, QHBoxLayout,
    QComboBox, QStackedWidget, QFormLayout, QDoubleSpinBox, QLabel, QDialogButtonBox,
    QGraphicsView, QGraphicsScene, QGraphicsPathItem, QGraphicsLineItem
)

# ------------------------------
# Shape protocol + dataclasses
# ------------------------------

class TunnelShape(Protocol):
    name: str
    def parameters_widget(self) -> QWidget: ...
    def set_value_changed_callback(self, cb) -> None: ...
    def to_dict(self) -> Dict: ...
    def outline_path(self) -> QPainterPath: ...
    def bounds_hint(self) -> QRectF: ...

@dataclass
class RectTunnelParams:
    width: float = 8.0      # m
    height: float = 5.0     # m
    corner_radius: float = 0.5  # m

class RectTunnelWidget(QWidget):
    name = "Rectangle"

    def __init__(self, params: RectTunnelParams | None = None, parent=None):
        super().__init__(parent)
        self.params = params or RectTunnelParams()
        self._on_change = None

        form = QFormLayout(self)
        self.sp_width = QDoubleSpinBox()
        self.sp_width.setRange(0.1, 1e3); self.sp_width.setDecimals(3); self.sp_width.setValue(self.params.width); self.sp_width.setSuffix(" m")
        self.sp_height = QDoubleSpinBox()
        self.sp_height.setRange(0.1, 1e3); self.sp_height.setDecimals(3); self.sp_height.setValue(self.params.height); self.sp_height.setSuffix(" m")
        self.sp_radius = QDoubleSpinBox()
        self.sp_radius.setRange(0.0, 100.0); self.sp_radius.setDecimals(3); self.sp_radius.setValue(self.params.corner_radius); self.sp_radius.setSuffix(" m")

        for w in (self.sp_width, self.sp_height, self.sp_radius):
            w.valueChanged.connect(self._emit_change)

        form.addRow("Inner width", self.sp_width)
        form.addRow("Inner height", self.sp_height)
        form.addRow("Corner radius", self.sp_radius)

    def set_value_changed_callback(self, cb):
        self._on_change = cb

    def _emit_change(self, *_):
        self.params.width = float(self.sp_width.value())
        self.params.height = float(self.sp_height.value())
        # Clamp radius to half of min(width, height) just in case
        max_r = max(0.0, 0.5 * min(self.params.width, self.params.height) - 1e-9)
        self.params.corner_radius = min(float(self.sp_radius.value()), max_r)
        if self._on_change: self._on_change()

    # TunnelShape API
    def parameters_widget(self) -> QWidget:
        return self

    def to_dict(self) -> Dict:
        return {"type": self.name, **asdict(self.params)}

    def outline_path(self) -> QPainterPath:
        w, h, r = self.params.width, self.params.height, self.params.corner_radius
        # Build a rounded-rectangle centered at origin (x right, y up)
        # GraphicsView uses y down, we'll flip in the view transform, so we keep y-up here.
        x0, y0 = -w/2, -h/2
        rect = QRectF(x0, y0, w, h)
        path = QPainterPath()
        if r <= 1e-9:
            path.addRect(rect)
            return path

        # Manually make rounded rect to be explicit:
        path.moveTo(x0 + r, y0)
        path.lineTo(x0 + w - r, y0)
        path.quadTo(x0 + w, y0, x0 + w, y0 + r)
        path.lineTo(x0 + w, y0 + h - r)
        path.quadTo(x0 + w, y0 + h, x0 + w - r, y0 + h)
        path.lineTo(x0 + r, y0 + h)
        path.quadTo(x0, y0 + h, x0, y0 + h - r)
        path.lineTo(x0, y0 + r)
        path.quadTo(x0, y0, x0 + r, y0)
        path.closeSubpath()
        return path

    def bounds_hint(self) -> QRectF:
        pad = 0.1 * max(self.params.width, self.params.height)
        return self.outline_path().boundingRect().adjusted(-pad, -pad, pad, pad)

@dataclass
class CircTunnelParams:
    diameter: float = 7.0  # m

class CircTunnelWidget(QWidget):
    name = "Circle"

    def __init__(self, params: CircTunnelParams | None = None, parent=None):
        super().__init__(parent)
        self.params = params or CircTunnelParams()
        self._on_change = None

        form = QFormLayout(self)
        self.sp_d = QDoubleSpinBox()
        self.sp_d.setRange(0.1, 1e3); self.sp_d.setDecimals(3); self.sp_d.setValue(self.params.diameter); self.sp_d.setSuffix(" m")
        self.sp_d.valueChanged.connect(self._emit_change)
        form.addRow("Inner diameter", self.sp_d)

    def set_value_changed_callback(self, cb):
        self._on_change = cb

    def _emit_change(self, *_):
        self.params.diameter = float(self.sp_d.value())
        if self._on_change: self._on_change()

    def parameters_widget(self) -> QWidget:
        return self

    def to_dict(self) -> Dict:
        return {"type": self.name, **asdict(self.params)}

    def outline_path(self) -> QPainterPath:
        d = self.params.diameter
        r = d / 2
        rect = QRectF(-r, -r, d, d)
        path = QPainterPath()
        path.addEllipse(rect)
        return path

    def bounds_hint(self) -> QRectF:
        pad = 0.1 * self.params.diameter
        return self.outline_path().boundingRect().adjusted(-pad, -pad, pad, pad)

# ------------------------------
# Preview view
# ------------------------------

class PreviewView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(self.renderHints() | QPainter.Antialiasing | QPainter.TextAntialiasing)  # Antialiasing | TextAntialiasing
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # y-up: flip the y-axis
        self.scale(1.0, -1.0)

        # Items
        self.grid_items: List[QGraphicsLineItem] = []
        self.axis_items: List[QGraphicsLineItem] = []
        self.path_item = QGraphicsPathItem()
        self.path_item.setPen(QPen(QColor(0, 0, 0), 0))  # cosmetic pen
        self.path_item.setBrush(QBrush(QColor(220, 220, 220, 255)))
        self.scene.addItem(self.path_item)

    def draw_grid(self, bounds: QRectF, major=1.0, minor=0.5):
        # Clear old grid
        for it in self.grid_items + self.axis_items:
            self.scene.removeItem(it)
        self.grid_items.clear()
        self.axis_items.clear()

        # Major/minor grid within bounds
        x0 = int(bounds.left() // minor) * minor
        x1 = int(bounds.right() // minor + 1) * minor
        y0 = int(bounds.top() // minor) * minor
        y1 = int(bounds.bottom() // minor + 1) * minor

        minor_pen = QPen(QColor(200, 200, 200), 0)
        major_pen = QPen(QColor(170, 170, 170), 0)
        axis_pen  = QPen(QColor(120, 120, 120), 0)
        axis_pen.setWidthF(0)

        def add_line(x1, y1, x2, y2, pen):
            li = self.scene.addLine(x1, y1, x2, y2, pen)
            self.grid_items.append(li)

        # Vertical lines
        x = x0
        while x <= x1:
            pen = major_pen if abs((x / major) - round(x / major)) < 1e-9 else minor_pen
            add_line(x, y0, x, y1, pen)
            x += minor

        # Horizontal lines
        y = y0
        while y <= y1:
            pen = major_pen if abs((y / major) - round(y / major)) < 1e-9 else minor_pen
            add_line(x0, y, x1, y, pen)
            y += minor

        # Axes
        self.axis_items.append(self.scene.addLine(bounds.left(), 0, bounds.right(), 0, axis_pen))
        self.axis_items.append(self.scene.addLine(0, bounds.top(), 0, bounds.bottom(), axis_pen))

    def update_shape(self, path: QPainterPath, bounds_hint: QRectF):
        self.path_item.setPath(path)
        # Expand bounds to include grid padding
        br = path.boundingRect()
        pad = max(1.0, 0.1 * max(br.width(), br.height()))
        view_rect = br.adjusted(-pad, -pad, pad, pad)
        self.draw_grid(view_rect)
        # fit the view (since we flipped Y, use absolute rect)
        self.fitInView(view_rect, Qt.KeepAspectRatio)


# ------------------------------
# Dialog
# ------------------------------

class TunnelDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Tunnel")
        self.resize(900, 500)

        # Left: controls (type + params), Right: preview
        left = QVBoxLayout()
        type_row = QHBoxLayout()

        type_row.addWidget(QLabel("Tunnel type"))
        self.cb_type = QComboBox()
        self.cb_type.addItems(["Rectangle", "Circle"])  # extend here
        type_row.addWidget(self.cb_type, 1)
        type_row.addStretch(1)
        left.addLayout(type_row)

        self.pages = QStackedWidget()
        self.rect_page = RectTunnelWidget()
        self.circ_page = CircTunnelWidget()
        for p in (self.rect_page, self.circ_page):
            p.set_value_changed_callback(self._update_preview)

        self.pages.addWidget(self.rect_page)
        self.pages.addWidget(self.circ_page)
        left.addWidget(self.pages, 1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        left.addWidget(btns)

        self.preview = PreviewView()

        root = QHBoxLayout(self)
        root.addLayout(left, 0)
        root.addWidget(self.preview, 1)

        # wire type switching
        self.cb_type.currentIndexChanged.connect(self._switch_type)

        # initial
        self._switch_type(self.cb_type.currentIndex())

    def _shape(self) -> TunnelShape:
        idx = self.cb_type.currentIndex()
        return self.rect_page if idx == 0 else self.circ_page

    def _switch_type(self, idx: int):
        self.pages.setCurrentIndex(idx)
        self._update_preview()

    def _update_preview(self):
        shape = self._shape()
        self.preview.update_shape(shape.outline_path(), shape.bounds_hint())

    def result_payload(self) -> Dict:
        """Call after exec_ == Accepted to get data for your preprocessor."""
        return self._shape().to_dict()


# ------------------------------
# Example host window
# ------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FEA Preprocessor – Heat/Fire")
        btn = QPushButton("Add Tunnel…")
        btn.clicked.connect(self.open_tunnel_dialog)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(btn)
        self.setCentralWidget(w)

    def open_tunnel_dialog(self):
        dlg = TunnelDialog(self)
        if dlg.exec() == QDialog.Accepted:
            payload = dlg.result_payload()
            # Here you would convert to your internal geometry_editors (mesh seed, etc.)
            # For this demo we just print:
            print("User selected:", payload)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.resize(800, 400)
    mw.show()
    sys.exit(app.exec())
