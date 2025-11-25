from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QDoubleSpinBox,
    QComboBox, QPushButton, QTabWidget, QWidget, QLabel, QCheckBox, QSizePolicy, QDialogButtonBox
)
from PySide6.QtCore import Qt

import pyqtgraph as pg

from temperatureanalysis.app.ui.panels.material_dialog.properties import TemperatureDependentProperty, \
    TemperatureDependentMaterial
from temperatureanalysis.fea.pre.material import ThermalConductivityBoundary


class MaterialEditorDialog(QDialog):
    """

    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("Material Editor"))

        screen = self.screen() or self.windowHandle().screen()
        if screen:
            geometry = screen.availableGeometry()
            self.setMinimumHeight(int(geometry.height() * 0.8))

        self._material = TemperatureDependentMaterial.from_inputs(
            name="concrete",
            label=self.tr("Concrete"),
            description="",
            initial_density=2300.0,
            thermal_conductivity_boundary=ThermalConductivityBoundary.UPPER,
            initial_moisture_content=0.0
        )

        root = QVBoxLayout(self)

        # Top form
        form = QFormLayout()
        self.label = QLineEdit(self._material.label)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.rho0 = QDoubleSpinBox()
        self.rho0.setRange(0.0, 10_000)
        self.rho0.setSuffix(" kg/m³")
        self.rho0.setValue(self._material.initial_density)
        self.rho0.setSingleStep(50.0)
        self.rho0.setDecimals(2)
        self.rho0.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.initial_moisture = QDoubleSpinBox()
        self.initial_moisture.setRange(0.0, 3.0)
        self.initial_moisture.setSingleStep(0.1)
        self.initial_moisture.setSuffix(" %")
        self.initial_moisture.setValue(self._material.initial_moisture_content)
        self.initial_moisture.setDecimals(2)
        self.initial_moisture.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.k_bound = QComboBox()
        self.k_bound.addItems(
            [
                self.tr(ThermalConductivityBoundary.UPPER.capitalize()),
                self.tr(ThermalConductivityBoundary.LOWER.capitalize()),
             ]
        )
        self.k_bound.setCurrentText(self._material.thermal_conductivity_boundary.capitalize())

        form.addRow(self.tr("Name:"), self.label)
        form.addRow(self.tr("Initial Density:"), self.rho0)
        form.addRow(self.tr("Initial Moisture Content:"), self.initial_moisture)
        form.addRow(self.tr("Thermal Conductivity Boundary:"), self.k_bound)

        root.addLayout(form)

        self._plots: list[pg.PlotWidget] = []
        self._curves: dict[str, pg.PlotDataItem] = {}

        # helper to build one plot
        def _make_plot(
            title_left: str, x, y, key: str
        ) -> pg.PlotWidget:
            w = pg.PlotWidget(background="w")
            w.showGrid(x=True, y=True, alpha=0.3)
            w.getAxis("left").setPen("k")
            w.getAxis("bottom").setPen("k")
            w.getAxis("left").setTextPen("k")
            w.getAxis("bottom").setTextPen("k")
            w.setLabel("left", title_left)
            w.setLabel("bottom", self.tr("Temperature (°C)"))
            curve = w.plot(x, y, pen=pg.mkPen("k", width=2))
            self._curves[key] = curve
            self._plots.append(w)
            root.addWidget(w)
            return w

        _make_plot(f"{self._material.density.label} ({self._material.density.unit})",
                   self._material.density.temperature_celsius, self._material.density.values, "rho")
        _make_plot(f"{self._material.specific_heat_capacity.label} ({self._material.specific_heat_capacity.unit})",
                   self._material.specific_heat_capacity.temperature_celsius,
                   self._material.specific_heat_capacity.values, "cp")
        _make_plot(f"{self._material.thermal_conductivity.label} ({self._material.thermal_conductivity.unit})",
                   self._material.thermal_conductivity.temperature_celsius, self._material.thermal_conductivity.values,
                   "k")

        # --- Wire input changes -> recompute -> update plots
        self.label.textChanged.connect(self._on_inputs_changed)
        self.rho0.valueChanged.connect(self._on_inputs_changed)
        self.initial_moisture.valueChanged.connect(self._on_inputs_changed)
        self.k_bound.currentTextChanged.connect(self._on_inputs_changed)

        # ---- Buttons (OK / Cancel)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        # optional: set default
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)

        self.buttonBox.accepted.connect(self._on_accept)
        self.buttonBox.rejected.connect(self.reject)

        root.addWidget(self.buttonBox)

    # Called when user clicks OK or presses Enter
    def _on_accept(self):
        # ensure latest curves/inputs are reflected
        self._material = self._recompute_material()
        self.accept()

    # Public accessor to get the edited/new material after exec()
    def result_material(self):
        return self._material


    # ---------- helpers ----------
    def _current_k_bound(self) -> ThermalConductivityBoundary:
        txt = self.k_bound.currentText().strip().lower()
        return ThermalConductivityBoundary.UPPER if txt == "upper" else ThermalConductivityBoundary.LOWER

    def _recompute_material(self) -> TemperatureDependentMaterial:
        # build a fresh material from current widget values
        return TemperatureDependentMaterial.from_inputs(
            name=self.label.text().lower() or "material",
            label=self.label.text().strip() or "material",
            description="",
            initial_density=float(self.rho0.value()),
            thermal_conductivity_boundary=self._current_k_bound(),
            initial_moisture_content=float(self.initial_moisture.value()),
        )

    def _on_inputs_changed(self, *_):
        self._material = self._recompute_material()
        self._update_plots_and_labels()

    def _update_plots_and_labels(self):
        # update Y labels (in case units/labels depend on inputs)
        self._plots[0].setLabel("left", f"{self._material.density.label} ({self._material.density.unit})")
        self._plots[1].setLabel("left",
                                f"{self._material.specific_heat_capacity.label} ({self._material.specific_heat_capacity.unit})")
        self._plots[2].setLabel("left",
                                f"{self._material.thermal_conductivity.label} ({self._material.thermal_conductivity.unit})")

        # update curves (setData is fast and flicker-free)
        rho = self._material.density
        self._curves["rho"].setData(rho.temperature_celsius, rho.values)

        cp = self._material.specific_heat_capacity
        self._curves["cp"].setData(cp.temperature_celsius, cp.values)

        k = self._material.thermal_conductivity
        self._curves["k"].setData(k.temperature_celsius, k.values)



