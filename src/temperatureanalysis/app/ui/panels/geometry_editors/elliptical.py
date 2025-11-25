from __future__ import annotations

from PySide6.QtCore import Slot

import numpy as np

from temperatureanalysis.app.ui.panels.geometry_editors.base import ParamEditorBase
from temperatureanalysis.app.ui.panels.geometry_editors.registry import register_editor
from temperatureanalysis.app.ui.panels.geometry_editors.math_utils import ellipse_to_polyline
from temperatureanalysis.app.ui.preview import PreviewDomain


@register_editor
class EllipticalEditor(ParamEditorBase):
    KEY = "ellipse"

    def _build_ui(self) -> None:
        self._add_spin("inner_width", "Inner width:", min_value=0.5, max_value=40.0, step=0.05, default=3.0, suffix="m")
        self._add_spin("inner_height", "Inner height:", min_value=0.5, max_value=20.0, step=0.05, default=5.0, suffix="m")
        self._add_spin("wall_thickness", "Wall thickness:", min_value=0.1, max_value=3.0, step=0.01, default=0.4, suffix="m")
        self._add_spin("center_x", "Center X:")
        self._add_spin("center_y", "Center Y:")
        for w in self._spins.values():
            w.valueChanged.connect(self._relay_changed)

    def build_domains(self) -> list[PreviewDomain]:
        w = self.params()["inner_width"]
        h = self.params()["inner_height"]
        t = self.params()["wall_thickness"]
        cx = self.params()["center_x"]
        cy = self.params()["center_y"]

        a_inner = w / 2
        b_inner = h / 2
        a_outer = a_inner + t
        b_outer = b_inner + t

        inner = ellipse_to_polyline((cx, cy), a_inner, b_inner, 180)
        outer = ellipse_to_polyline((cx, cy), a_outer, b_outer, 180)

        layers: list[PreviewDomain] = [PreviewDomain(
            name='lining',
            label=self.tr("Lining"),
            outer=outer,
            holes=[inner],
            fill_color="#808080",
            edge_color="black",
            edge_width=2,
            opacity=1.0
        )]

        return layers
