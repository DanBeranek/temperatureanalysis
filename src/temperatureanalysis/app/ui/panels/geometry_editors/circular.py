from __future__ import annotations

from PySide6.QtCore import Slot

import numpy as np

from temperatureanalysis.app.ui.panels.geometry_editors.base import ParamEditorBase
from temperatureanalysis.app.ui.panels.geometry_editors.registry import register_editor
from temperatureanalysis.app.ui.panels.geometry_editors.math_utils import circle_to_polyline, line_circle_intersection, arc_points
from temperatureanalysis.app.ui.preview import PreviewDomain


@register_editor
class CircularEditor(ParamEditorBase):
    KEY = "circle"

    def _build_ui(self) -> None:
        self._add_spin("diameter", "Inner diameter:", min_value=1.0, max_value=20.0, step=0.05, default=8.0, suffix="m")
        self._add_spin("wall-thickness", "Wall thickness:", min_value=0.1, max_value=3, step=0.01, default=0.6, suffix="m")
        self._add_spin("tk-x", "TK X:", default=0.5, suffix="m")
        self._add_spin("tk-y", "TK Y:", default=2.6, suffix="m")
        self._add_spin("track-width", "Track width:", min_value=0.0, max_value=10.0, step=0.1, default=3.0, suffix="m")
        self._add_spin("track-bottom", "Track bottom:", default=-0.4, suffix="m")
        self._add_spin("left-height", "Left height:", default=0.15, suffix="m")
        self._add_spin("right-height", "Right height:", default=-0.14, suffix="m")
        self._add_spin("left-slope", "Left slope:", min_value=0.0, max_value=70.0, step=0.1, default=3.0, suffix="%")
        self._add_spin("right-slope", "Right slope:", min_value=0.0, max_value=70.0, step=0.1, default=3.0, suffix="%")
        for w in self._spins.values():
            w.valueChanged.connect(self._relay_changed)

    def build_domains(self) -> list[PreviewDomain]:
        d = self.params()["diameter"]
        t = self.params()["wall-thickness"]
        cx = self.params()["tk-x"]
        cy = self.params()["tk-y"]
        tw = self.params()["track-width"]
        tb = self.params()["track-bottom"]
        lh = self.params()["left-height"]
        rh = self.params()["right-height"]
        ls = self.params()["left-slope"] / 100.0
        rs = self.params()["right-slope"] / 100.0

        r_inner = d / 2
        r_outer = r_inner + t

        # loops
        outer = circle_to_polyline((cx, cy), r_outer, 180)
        inner = circle_to_polyline((cx, cy), r_inner, 180)

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

        # Lining

        # Invert
        p2 = (-tw / 2, lh)
        p3 = (-tw / 2, tb)
        p4 = (+tw / 2, tb)
        p5 = (+tw / 2, rh)

        p_left = (-tw / 2 - 4 * r_inner, lh + 4 * ls * r_inner)
        p_right = (+tw / 2 + 4 * r_inner, rh + 4 * rs * r_inner)

        p1 = line_circle_intersection(p2, (p_left[0] - p2[0], p_left[1] - p2[1]), (cx, cy), r_inner, as_segment=True)[0]
        p6 = line_circle_intersection(p5, (p_right[0] - p5[0], p_right[1] - p5[1]), (cx, cy), r_inner, as_segment=True)[
            0]

        points_on_arc = arc_points((cx, cy), r_inner, p1, p6, clockwise=False, n_points=50)

        invert = np.vstack([p1, points_on_arc, p6, p5, p4, p3, p2, p1])

        layers.append(
            PreviewDomain(
                name='invert',
                label=self.tr("Invert"),
                outer=invert,
                fill_color="#888c41",
                edge_color="black",
                edge_width=2,
                opacity=1.0
            )
        )

        return layers
