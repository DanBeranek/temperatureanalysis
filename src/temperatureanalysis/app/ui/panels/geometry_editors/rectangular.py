from __future__ import annotations

from PySide6.QtCore import Slot

import numpy as np

from temperatureanalysis.app.ui.panels.geometry_editors.base import ParamEditorBase
from temperatureanalysis.app.ui.panels.geometry_editors.registry import register_editor
from temperatureanalysis.app.ui.preview import PreviewDomain


@register_editor
class RectangularEditor(ParamEditorBase):
    KEY = "rectangle"

    def _build_ui(self) -> None:
        self._add_spin("inner_width", "Inner width:", min_value=0.5, max_value=40.0, step=0.05, default=8.0, suffix="m")
        self._add_spin("inner_height", "Inner height:", min_value=0.5, max_value=20.0, step=0.05, default=5.0, suffix="m")
        self._add_spin("wall_thickness", "Wall thickness:", min_value=0.1, max_value=3.0, step=0.01, default=0.6, suffix="m")
        for w in self._spins.values():
            w.valueChanged.connect(self._relay_changed)

    def build_domains(self) -> list[PreviewDomain]:
        w = self.params()["inner_width"]
        h = self.params()["inner_height"]
        t = self.params()["wall_thickness"]

        inner = np.array([
            (-w / 2, -h / 2),
            (+w / 2, -h / 2),
            (+w / 2, +h / 2),
            (-w / 2, +h / 2),
            (-w / 2, -h / 2)
        ])

        outer = np.array([
            (-w / 2 - t, -h / 2 - t),
            (+w / 2 + t, -h / 2 - t),
            (+w / 2 + t, +h / 2 + t),
            (-w / 2 - t, +h / 2 + t),
            (-w / 2 - t, -h / 2 - t)
        ])

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
