"""Dialog for plotting thermocouple temperature histories."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QPushButton, QScrollArea, QWidget, QLabel, QFileDialog
)
from PySide6.QtCore import Qt, Signal

if TYPE_CHECKING:
    import numpy.typing as npt
    from temperatureanalysis.controller.fea.analysis.node import Node


logger = logging.getLogger(__name__)


class ThermocoupleSelectionWidget(QWidget):
    """Widget for selecting thermocouples in a category."""

    # Signal emitted when selection changes
    selection_changed = Signal()

    def __init__(self, category_name: str, thermocouples: dict[str, Node]) -> None:
        """Initialize the selection widget.

        Args:
            category_name: Display name for the category (e.g., "Ox", "Vx")
            thermocouples: Dict mapping thermocouple names to Node objects
        """
        super().__init__()
        self.category_name = category_name
        self.thermocouples = thermocouples
        self.checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)

        # Header with toggle all
        header_layout = QHBoxLayout()
        header_label = QLabel(f"<b>{category_name}</b>")
        header_layout.addWidget(header_label)

        self.toggle_all_btn = QPushButton("Vše Zapnout")
        self.toggle_all_btn.setMaximumWidth(120)
        self.toggle_all_btn.clicked.connect(self._toggle_all)
        header_layout.addWidget(self.toggle_all_btn)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Create checkboxes for each thermocouple
        for tc_name in sorted(thermocouples.keys()):
            # Extract the short name (e.g., "O1" from "THERMOCOUPLE_O1")
            display_name = tc_name.replace("THERMOCOUPLE_", "")
            checkbox = QCheckBox(display_name)
            checkbox.setChecked(True)  # Default: all selected
            checkbox.stateChanged.connect(self._on_checkbox_changed)
            self.checkboxes[tc_name] = checkbox
            layout.addWidget(checkbox)

        layout.addStretch()

    def _on_checkbox_changed(self) -> None:
        """Emit signal when any checkbox changes."""
        self.selection_changed.emit()

    def _toggle_all(self) -> None:
        """Toggle all checkboxes on or off."""
        # Check if any are unchecked
        any_unchecked = any(not cb.isChecked() for cb in self.checkboxes.values())

        # If any are unchecked, check all; otherwise uncheck all
        new_state = any_unchecked

        for checkbox in self.checkboxes.values():
            checkbox.setChecked(new_state)

        # Update button text
        self.toggle_all_btn.setText("Vše Vypnout" if new_state else "Vše Zapnout")

    def get_selected(self) -> dict[str, Node]:
        """Get the selected thermocouples.

        Returns:
            Dict mapping thermocouple names to Node objects for selected items
        """
        return {
            name: self.thermocouples[name]
            for name, checkbox in self.checkboxes.items()
            if checkbox.isChecked()
        }


class ThermocouplePlotDialog(QDialog):
    """Dialog for displaying and customizing thermocouple temperature history plots."""

    # Color cycle for different thermocouples
    COLORS = [
        '#1f77b4',  # Blue
        '#ff7f0e',  # Orange
        '#2ca02c',  # Green
        '#d62728',  # Red
        '#9467bd',  # Purple
        '#8c564b',  # Brown
        '#e377c2',  # Pink
        '#7f7f7f',  # Gray
        '#bcbd22',  # Olive
        '#17becf',  # Cyan
    ]

    def __init__(
        self,
        thermocouples: dict[str, Node],
        results: list[npt.NDArray[np.float64]],
        time_steps: list[float],
        critical_temp: float,
        parent: QWidget | None = None
    ) -> None:
        """Initialize the thermocouple plot dialog.

        Args:
            thermocouples: Dict mapping thermocouple names to Node objects
            results: List of temperature arrays (one per time step) in Kelvin
            time_steps: List of time values in seconds
            critical_temp: Critical temperature threshold in Celsius
            parent: Parent widget
        """
        super().__init__(parent)
        self.thermocouples = thermocouples
        self.results = results
        self.time_steps = time_steps
        self.critical_temp = critical_temp

        self.setWindowTitle("Graf Teplot Termočlánků")
        self.resize(1200, 700)

        # Categorize thermocouples
        self.ox_thermocouples: dict[str, Node] = {}
        self.vx_thermocouples: dict[str, Node] = {}

        for name, node in thermocouples.items():
            # Extract identifier from name (e.g., "O1" from "THERMOCOUPLE_O1")
            identifier = name.replace("THERMOCOUPLE - ", "")
            if identifier.startswith("O"):
                self.ox_thermocouples[name] = node
            elif identifier.startswith("V"):
                self.vx_thermocouples[name] = node
            else:
                logger.warning(f"Unknown thermocouple category: {name}")

        # Build UI
        self._build_ui()

        # Initial plot
        self._update_plot()

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        main_layout = QHBoxLayout(self)

        # Left panel: Selection controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(250)

        # Title
        title = QLabel("<h3>Výběr Termočlánků</h3>")
        title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(title)

        # Scrollable area for checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Ox category
        if self.ox_thermocouples:
            self.ox_widget = ThermocoupleSelectionWidget("Ox", self.ox_thermocouples)
            self.ox_widget.selection_changed.connect(self._update_plot)
            scroll_layout.addWidget(self.ox_widget)

        # Vx category
        if self.vx_thermocouples:
            self.vx_widget = ThermocoupleSelectionWidget("Vx", self.vx_thermocouples)
            self.vx_widget.selection_changed.connect(self._update_plot)
            scroll_layout.addWidget(self.vx_widget)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        left_layout.addWidget(scroll)

        # Export button
        export_btn = QPushButton("Exportovat jako obrázek...")
        export_btn.clicked.connect(self._export_image)
        left_layout.addWidget(export_btn)

        # Close button
        close_btn = QPushButton("Zavřít")
        close_btn.clicked.connect(self.accept)
        left_layout.addWidget(close_btn)

        main_layout.addWidget(left_panel)

        # Right panel: Plot
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # PyQtGraph plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('bottom', 'Čas [min]', color='black')
        self.plot_widget.setLabel('left', 'Teplota [°C]', color='black')
        self.plot_widget.setTitle('Historie Teplot Termočlánků', color='black', size='14pt')
        self.plot_widget.getAxis('bottom').setPen('k')
        self.plot_widget.getAxis('left').setPen('k')
        self.plot_widget.getAxis('bottom').setTextPen('k')
        self.plot_widget.getAxis('left').setTextPen('k')
        self.plot_widget.addLegend(offset=(10, 10))

        right_layout.addWidget(self.plot_widget)

        main_layout.addWidget(right_panel)

    def _update_plot(self) -> None:
        """Update the plot with selected thermocouples."""
        # Get selected thermocouples from both categories
        selected = {}
        if hasattr(self, 'ox_widget'):
            selected.update(self.ox_widget.get_selected())
        if hasattr(self, 'vx_widget'):
            selected.update(self.vx_widget.get_selected())

        # Clear plot
        self.plot_widget.clear()

        if not selected:
            # Show message if nothing selected
            text_item = pg.TextItem('Vyberte alespoň jeden termočlánek', color='gray', anchor=(0.5, 0.5))
            text_item.setPos(0.5, 0.5)
            self.plot_widget.addItem(text_item)
            self.plot_widget.setXRange(0, 1)
            self.plot_widget.setYRange(0, 1)
            return

        # Re-add legend after clearing
        self.plot_widget.addLegend(offset=(10, 10))

        # Convert time to minutes
        time_min = np.array(self.time_steps) / 60.0

        # Plot each selected thermocouple
        color_idx = 0
        for tc_name in sorted(selected.keys()):
            node = selected[tc_name]
            node_idx = node.uid  # Use node.uid which is the zero-based index

            # Extract temperature history for this node
            temps_kelvin = np.array([self.results[i][node_idx] for i in range(len(self.results))])
            temps_celsius = temps_kelvin - 273.15

            # Get display name (e.g., "O1" from "THERMOCOUPLE_O1")
            display_name = tc_name.replace("THERMOCOUPLE_", "")

            # Plot with color cycling
            color = self.COLORS[color_idx % len(self.COLORS)]
            pen = pg.mkPen(color=color, width=2)

            # Add symbols for better visibility
            symbol_spacing = max(1, len(time_min) // 20)
            self.plot_widget.plot(
                time_min, temps_celsius,
                pen=pen,
                name=display_name,
                symbol='o',
                symbolSize=4,
                symbolBrush=color,
                symbolPen=None,
                symbolSpacing=symbol_spacing
            )

            color_idx += 1

        # Add critical temperature line
        crit_line = pg.InfiniteLine(
            pos=self.critical_temp,
            angle=0,
            pen=pg.mkPen(color='r', width=2, style=pg.QtCore.Qt.DashLine),
            label=f'Kritická teplota ({self.critical_temp:.0f} °C)',
            labelOpts={'position': 0.95, 'color': 'r', 'fill': (255, 255, 255, 150)}
        )
        self.plot_widget.addItem(crit_line)

        # Auto-range to fit all data
        self.plot_widget.autoRange()

    def _export_image(self) -> None:
        """Export the current plot as an image file."""
        # Ask user for file path
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Uložit graf jako obrázek",
            "thermocouple_plot.png",
            "PNG obrázek (*.png);;JPEG obrázek (*.jpg);;SVG vektorový obrázek (*.svg)"
        )

        if not file_path:
            return

        try:
            # Create exporter
            exporter = ImageExporter(self.plot_widget.plotItem)

            # Set export parameters for high quality
            exporter.parameters()['width'] = 1920  # High resolution

            # Export to file
            exporter.export(file_path)

            logger.info(f"Plot exported to {file_path}")

        except Exception as e:
            logger.exception("Failed to export plot")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Chyba exportu", f"Nepodařilo se exportovat graf:\n{str(e)}")
