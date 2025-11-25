from __future__ import annotations

from PySide6.QtCore import Slot

import numpy as np

from temperatureanalysis.app.ui.panels.geometry_editors.base import ParamEditorBase
from temperatureanalysis.app.ui.panels.geometry_editors.registry import register_editor
from temperatureanalysis.app.ui.panels.geometry_editors.math_utils import arc_points
from temperatureanalysis.app.ui.preview import PreviewDomain


@register_editor
class DSectionEditor(ParamEditorBase):
    KEY = "d_section"

    def _build_ui(self) -> None:
        self._add_spin("inner_width", "Inner width:", min_value=0.5, max_value=40.0, step=0.05, default=8.0, suffix="m")
        self._add_spin("leg_height", "Leg height:", min_value=0.5, max_value=20.0, step=0.05, default=5.0, suffix="m")
        self._add_spin("wall_thickness", "Wall thickness:", min_value=0.1, max_value=3.0, step=0.01, default=0.4, suffix="m")
        for w in self._spins.values():
            w.valueChanged.connect(self._relay_changed)

    def build_domains(self) -> list[PreviewDomain]:
        w = self.params()["inner_width"]
        leg_height = self.params()["leg_height"]
        t = self.params()["wall_thickness"]

        h = w / 2 + leg_height

        p1i = (-w / 2, -leg_height / 2)
        p2i = (+w / 2, -leg_height / 2)
        p3i = (+w / 2, 0.0)
        p4i = (-w / 2, 0.0)
        arc_points_inner = arc_points((0.0, 0.0), w / 2, p3i, p4i, n_points=180)

        p1o = (-w / 2 - t, -leg_height / 2 - t)
        p2o = (+w / 2 + t, -leg_height / 2 - t)
        p3o = (+w / 2 + t, 0.0)
        p4o = (-w / 2 - t, 0.0)
        arc_points_outer = arc_points((0.0, 0.0), w / 2 + t, p3o, p4o, n_points=180)

        inner = np.vstack((p1i, p2i, p3i, arc_points_inner, p4i, p1i))
        outer = np.vstack((p1o, p2o, p3o, arc_points_outer, p4o, p1o))

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
