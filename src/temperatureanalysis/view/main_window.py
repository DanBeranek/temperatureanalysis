"""Main Application Window
=======================
The primary GUI container that holds the Menu Bar, Toolbar, and Central Tabs.

Why is this file needed?
------------------------
1. Layout: It organizes the high-level visual structure of the application.
2. Routing: It connects global actions (like File -> Save) to the appropriate
   controllers.
"""
import os
import tomllib
from datetime import datetime

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QPalette
from PySide6.QtGui import QDesktopServices
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QFrame
from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import QMainWindow
from PySide6.QtWidgets import QMessageBox
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QScrollArea
from PySide6.QtWidgets import QSplitter
from PySide6.QtWidgets import QStackedWidget
from PySide6.QtWidgets import QTabBar
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QWidget

from temperatureanalysis import config
from temperatureanalysis.config import ASSETS_PATH
from temperatureanalysis.model.io import IOManager
from temperatureanalysis.model.state import ProjectState
from temperatureanalysis.view.tabs.tab_bc import BCControlPanel

# Import Control Panels
from temperatureanalysis.view.tabs.tab_geometry import GeometryControlPanel
from temperatureanalysis.view.tabs.tab_materials import MaterialsControlPanel
from temperatureanalysis.view.tabs.tab_mesh import MeshControlPanel
from temperatureanalysis.view.tabs.tab_results import ResultsControlPanel
from temperatureanalysis.view.widgets.plot_3d import PyVistaWidget

VISIBLE_APP_NAME = "CK04000274-V2 | Požár: Tunel"


def get_app_version() -> str:
    """Read application version from pyproject.toml."""
    try:
        # Try to find pyproject.toml relative to the current file
        project_root = os.path.join(os.path.dirname(__file__), "..", "..", "..")
        pyproject_path = os.path.join(project_root, "pyproject.toml")

        if os.path.exists(pyproject_path):
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                return data.get("tool", {}).get("poetry", {}).get("version", "Unknown")
    except Exception:
        pass
    return "Unknown"


def get_app_authors() -> str:
    """Read application authors from pyproject.toml."""
    try:
        project_root = os.path.join(os.path.dirname(__file__), "..", "..", "..")
        pyproject_path = os.path.join(project_root, "pyproject.toml")

        if os.path.exists(pyproject_path):
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                authors = data.get("tool", {}).get("poetry", {}).get("authors", [])
                if authors:
                    return authors[0]  # Return first author
    except Exception:
        pass
    return "Unknown"


class ClickableLogoLabel(QLabel):
    """A clickable logo label that opens a URL when clicked and scales to width."""

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.setCursor(Qt.PointingHandCursor)
        self._original_pixmap = None

        # Allow label to scale
        self.setMinimumWidth(1)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)

    def set_source_pixmap(self, pixmap):
        """Set the source pixmap that will be scaled."""
        self._original_pixmap = pixmap
        if pixmap is None:
            self.clear()
        else:
            self._update_display()

    def resizeEvent(self, event):
        """Handle resize to scale pixmap to current width."""
        if self._original_pixmap:
            self._update_display()
        super().resizeEvent(event)

    def _update_display(self):
        """Scale pixmap to current widget width while maintaining aspect ratio."""
        if self._original_pixmap and not self._original_pixmap.isNull():
            w = self.width()
            if w > 0:
                scaled = self._original_pixmap.scaledToWidth(w, Qt.SmoothTransformation)
                super().setPixmap(scaled)

    def mousePressEvent(self, event):
        """Handle mouse click to open URL."""
        if event.button() == Qt.LeftButton:
            QDesktopServices.openUrl(QUrl(self.url))
        super().mousePressEvent(event)

class MainWindow(QMainWindow):
    def __init__(self, project_state: ProjectState) -> None:
        super().__init__()

        icon_path = os.path.join(ASSETS_PATH, "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QPixmap(icon_path))
        else:
            pass

        self.project: ProjectState = project_state
        self.is_modified: bool = True

        self.update_window_title()
        self.resize(1400, 900)

        # --- MAIN CONTAINER ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        # Vertical Layout: Tabs on Top, Splitter Below
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. TOP TAB BAR ---
        self.tab_bar = QTabBar()
        self.tab_bar.setDrawBase(True)
        self.tab_bar.setShape(QTabBar.RoundedNorth)
        self.tab_bar.setExpanding(True)  # Make tabs fill the width if desired

        # Define Tabs
        self.tab_bar.addTab("1. Geometrie")
        self.tab_bar.addTab("2. Materiály")
        self.tab_bar.addTab("3. Okrajové podmínky")
        self.tab_bar.addTab("4. Mesh")
        self.tab_bar.addTab("5. Výsledky")

        # Styling for better visibility
        self.tab_bar.setStyleSheet("""
                    QTabBar::tab { height: 35px; min-width: 100px; }
                    QTabBar::tab:selected { font-weight: bold; }
                """)

        main_layout.addWidget(self.tab_bar)

        # --- 2. SPLITTER (CONTENT AREA) ---
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- LEFT SIDE: Control Panels (Stacked) + Logo ---
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.controls_stack = QStackedWidget()

        # Instantiate Panels
        self.geom_panel = GeometryControlPanel(self.project)
        self.mat_panel = MaterialsControlPanel(self.project, self)
        self.bc_panel = BCControlPanel(self.project, self)
        self.mesh_panel = MeshControlPanel(self.project)
        self.results_panel = ResultsControlPanel(self.project)

        # Add to Stack (Order must match Tab Bar order)
        self.controls_stack.addWidget(self.geom_panel)  # Index 0
        self.controls_stack.addWidget(self.mat_panel)  # Index 1
        self.controls_stack.addWidget(self.bc_panel)  # Index 2
        self.controls_stack.addWidget(self.mesh_panel)  # Index 3
        self.controls_stack.addWidget(self.results_panel)  # Index 4

        left_layout.addWidget(self.controls_stack)

        # Add TACR logolink at the bottom
        self.logo_label = self._create_tacr_logo()
        left_layout.addWidget(self.logo_label)

        splitter.addWidget(left_container)

        # --- RIGHT SIDE: Shared 3D Visualization ---
        self.visualizer = PyVistaWidget()
        splitter.addWidget(self.visualizer)

        # Set initial proportions (1 part sidebar : 4 parts 3D view)
        splitter.setSizes([350, 1050])

        # --- SIGNAL CONNECTIONS ---
        # 1. Link Tab Bar to Stacked Widget
        self.tab_bar.currentChanged.connect(self.controls_stack.setCurrentIndex)

        # 1. Geometry Changed -> Invalidate Mesh + Update View
        self.geom_panel.data_changed.connect(self.on_data_changed)

        # Materials changed -> set modified
        self.mat_panel.data_changed.connect(lambda: self.set_modified(True))
        self.mat_panel.material_changed.connect(lambda: self.set_modified(True))
        self.mat_panel.material_changed.connect(self._invalidate_results)

        # Boundary conditions changed -> set modified
        self.bc_panel.data_changed.connect(lambda: self.set_modified(True))
        self.bc_panel.boundary_condition_changed.connect(lambda: self.set_modified(True))
        self.bc_panel.boundary_condition_changed.connect(self._invalidate_results)

        # 2. Mesh Generated -> Update View + Set Modified
        self.mesh_panel.mesh_generated.connect(self.on_mesh_generated)

        # 3. Results Updates
        self.results_panel.update_view_requested.connect(self.on_results_update)
        self.results_panel.results_generated.connect(self.on_results_generated)

        # --- ACTIONS & MENUS ---
        self._create_actions()
        self._create_menus()

        # Initial Render
        self.update_visualization()

    def _create_tacr_logo(self) -> QWidget:
        """Create the TACR logolink widget with appropriate theme."""
        # Determine Theme (Dark/Light)
        text_color = self.palette().color(QPalette.WindowText)
        is_dark = text_color.lightness() > 128

        # Choose appropriate logo
        logo_filename = "logolink_dark.svg" if is_dark else "logolink_light.svg"
        logo_path = os.path.join(config.ASSETS_PATH, "logolink", logo_filename)

        # Create clickable logo
        logo_label = ClickableLogoLabel("https://tacr.gov.cz/", self)

        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Use the new method that handles scaling dynamically to panel width
            logo_label.set_source_pixmap(pixmap)
        else:
            logo_label.setText("TAČR")

        logo_label.setContentsMargins(10, 10, 10, 10)
        logo_label.setToolTip("Tento projekt je podporován Technologickou agenturou ČR")

        return logo_label

    def _create_actions(self) -> None:
        # File Actions
        self.act_new = QAction("Nový Projekt", self)
        self.act_new.setShortcut("Ctrl+N")
        self.act_new.triggered.connect(self.on_file_new)

        self.act_open = QAction("Otevřít...", self)
        self.act_open.setShortcut("Ctrl+O")
        self.act_open.triggered.connect(self.on_file_open)

        self.act_save = QAction("Uložit", self)
        self.act_save.setShortcut("Ctrl+S")
        self.act_save.triggered.connect(self.on_file_save)

        self.act_save_as = QAction("Uložit Jako...", self)
        self.act_save_as.setShortcut("Ctrl+Shift+S")
        self.act_save_as.triggered.connect(self.on_file_save_as)

        self.act_exit = QAction("Ukončit", self)
        self.act_exit.triggered.connect(self.close)

        # Simulation Actions
        self.act_export_mesh = QAction("Exportovat síť", self)
        self.act_export_mesh.triggered.connect(self.on_export_mesh_menu)
        self.act_export_mesh.setEnabled(False)  # Disabled until mesh exists

        self.act_export_vtu = QAction("Exportovat výsledky", self)
        self.act_export_vtu.triggered.connect(self.on_export_to_paraview_menu)
        self.act_export_vtu.setEnabled(False)  # Disabled until results exists

        # Help Actions
        self.act_open_manual = QAction("Otevřít manuál", self)
        self.act_open_manual.setShortcut("F1")
        self.act_open_manual.triggered.connect(self.on_open_manual)

        self.act_about = QAction("O aplikaci...", self)
        self.act_about.triggered.connect(self.on_about)

    def _create_menus(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&Soubor")
        file_menu.addAction(self.act_new)
        file_menu.addSeparator()
        file_menu.addAction(self.act_open)
        file_menu.addSeparator()
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.act_exit)

        analysis_menu = menu_bar.addMenu("&Export")
        analysis_menu.addAction(self.act_export_mesh)
        analysis_menu.addAction(self.act_export_vtu)

        help_menu = menu_bar.addMenu("&Nápověda")
        help_menu.addAction(self.act_open_manual)
        help_menu.addAction(self.act_about)

    # --- HELPER METHODS ---
    def update_window_title(self) -> None:
        """Updates the window title based on filename and dirty state."""
        filename = self.project.filepath if self.project.filepath else "Untitled"
        title = f"{VISIBLE_APP_NAME} - [{os.path.basename(filename)}"
        if self.is_modified:
            title += "*"
        title += "]"
        self.setWindowTitle(title)

    def set_modified(self, modified: bool) -> None:
        """Sets the dirty flag and updates title if changed."""
        if self.is_modified != modified:
            self.is_modified = modified
            self.update_window_title()

    def on_data_changed(self) -> None:
        """Slot called when project data changes."""
        # Invalidate Mesh and Results
        self._invalidate_mesh()
        self._invalidate_results()

        # 2. Update UI State
        self.set_modified(True)
        # Re-render scene (since mesh_path is None, mesh layer will disappear)
        self.update_visualization()

    def on_mesh_generated(self, filepath: str) -> None:
        """Slot called when MESH is generated."""
        self.update_visualization(reset_camera=False)
        self.set_modified(True)
        self.act_export_mesh.setEnabled(True)
        self.visualizer.set_mesh_visible(True)

        # Invalidate Results because mesh changed
        self._invalidate_results()

    def on_results_generated(self) -> None:
        """Slot called when RESULTS are generated."""
        self.set_modified(True)
        self.act_export_vtu.setEnabled(True)
        self.visualizer.set_results_visible(True, render=False)

    def on_results_update(
        self,
        mesh_path: str,
        scalars,
        v_min_limit: float | None = None,
        reset_camera: bool = False,
        colormap: str = "fire"
    ) -> None:
        """Called when user scrubs the time slider."""
        celsius_data = np.asarray(self.project.results) - 273.15

        # Use Override if provided, else use Auto Min
        if v_min_limit is not None:
            v_min = float(v_min_limit)
        else:
            v_min = np.min(celsius_data)
        v_max = np.max(celsius_data)
        self.visualizer.update_scene(self.project, scalars, v_min=v_min, v_max=v_max, reset_camera=reset_camera, levels=[500], colormap=colormap)

    def on_export_mesh_menu(self) -> None:
        """Called when clicking Export in the menu bar."""
        # Reuse logic from the panel
        self.mesh_panel.on_export_clicked()

    def on_export_to_paraview_menu(self) -> None:
        """Called when clicking Export to ParaView in the menu bar."""
        # Reuse logic from the panel
        self.results_panel.on_export_clicked()

    # --- FILE SLOTS ---

    def on_file_new(self) -> None:
        # Simple reset
        self.project.reset()

        # Reset dirty flag (updates title)
        self.set_modified(False)
        self.act_export_mesh.setEnabled(False)
        self.act_export_vtu.setEnabled(False)
        # Ensure title says "Untitled" (in case it wasn't modified before)
        self.update_window_title()

        # Refresh UI
        self.refresh_ui_from_state()

    def on_file_open(self) -> None:
        fname, _ = QFileDialog.getOpenFileName(
            self, "Otevřít Projekt", "", "HDF5 Files (*.h5)"
        )
        if fname:
            try:
                IOManager.load_project(self.project, fname)
                self.project.filepath = fname

                # Reset dirty flag
                self.is_modified = False
                # Explicitly update title to show new filename
                self.update_window_title()

                self.refresh_ui_from_state()
            except Exception as e:
                QMessageBox.critical(self, "Chyba", f"Nepodařilo se otevřít soubor:\n{e}")

    def on_file_save(self) -> None:
        if self.project.filepath:
            try:
                IOManager.save_project(self.project, self.project.filepath)
                # Removes asterisk
                self.set_modified(False)
            except Exception as e:
                QMessageBox.critical(self, "Chyba", f"Nepodařilo se uložit soubor:\n{e}")
        else:
            self.on_file_save_as()

    def on_file_save_as(self) -> None:
        fname, _ = QFileDialog.getSaveFileName(
            self, "Uložit Projekt", "", "HDF5 Files (*.h5)"
        )
        if fname:
            # Ensure extension
            if not fname.endswith(".h5"):
                fname += ".h5"

            try:
                IOManager.save_project(self.project, fname)
                self.project.filepath = fname

                # Reset dirty flag
                self.is_modified = False
                # Explicitly update title to show new filename
                self.update_window_title()
            except Exception as e:
                QMessageBox.critical(self, "Chyba", f"Nepodařilo se uložit soubor:\n{e}")

    def refresh_ui_from_state(self) -> None:
        """After loading a file, the State is updated, but the Widgets are old.
        We need to force the Widgets to read from the State again.
        """
        # 0. Clear all visualization caches to prevent artifacts from previous project
        self.visualizer.clear_all_caches()

        # 1. Update Geometry Panel
        self.geom_panel.blockSignals(True)
        try:
            self.geom_panel.load_from_state()
        finally:
            self.geom_panel.blockSignals(False)

        # 2. Reset Mesh Status if needed
        if not self.project.mesh_path:
            self.mesh_panel.reset_status()
            self.act_export_mesh.setEnabled(False)
        else:
            self.mesh_panel.update_status_from_state()
            self.act_export_mesh.setEnabled(True)

        # Load BC Panel
        self.bc_panel.blockSignals(True)
        try:
            self.bc_panel.load_from_state()
        finally:
            self.bc_panel.blockSignals(False)

        # Load Materials Panel
        self.mat_panel.blockSignals(True)
        try:
            self.mat_panel.load_from_state()
        finally:
            self.mat_panel.blockSignals(False)

        # 3. Update Results (will trigger visualization if results exists)
        self.results_panel.load_from_state()

        if self.project.results:
            self.act_export_vtu.setEnabled(True)
        else:
            self.act_export_vtu.setEnabled(False)

        # 4. Update Visualization ONLY if there is no results
        # If results exist, results_panel.load_from_state() -> on_finished() -> emit(update_view)
        # has already run. We don't want to overwrite it with wireframe.
        if not self.project.results:
            self.update_visualization()

    def update_visualization(self, reset_camera: bool = True) -> None:
        # Call the new unified method
        self.visualizer.update_scene(project_state=self.project, reset_camera=reset_camera)

    def on_open_manual(self) -> None:
        """Open the manual PDF file in the system's default PDF viewer."""
        manual_path = os.path.join(config.ASSETS_PATH, "manual.pdf")

        if not os.path.exists(manual_path):
            QMessageBox.warning(
                self,
                "Manuál nenalezen",
                f"Soubor manuálu nebyl nalezen:\n{manual_path}"
            )
            return

        # Open the file with the system's default PDF viewer
        url = QUrl.fromLocalFile(manual_path)
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                "Chyba",
                "Nepodařilo se otevřít manuál v prohlížeči PDF."
            )

    def on_about(self) -> None:
        """Show the About dialog with application information."""
        dialog = QDialog(self)
        dialog.setWindowTitle("O aplikaci")
        dialog.setModal(True)
        dialog.resize(650, 600)  # Set a comfortable default size

        # Main layout for dialog
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        # Content widget inside scroll area
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(25, 25, 25, 25)

        # Header: App name
        app_name_label = QLabel(f"<h2>{VISIBLE_APP_NAME}</h2>")
        layout.addWidget(app_name_label)

        # Version
        version = get_app_version()
        version_label = QLabel(f"<b>Verze:</b> {version}")
        layout.addWidget(version_label)

        # Description
        desc_label = QLabel("Software pro výpočet teplot v nosné konstrukci tunelu při požáru")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Author
        author = get_app_authors()
        author_label = QLabel(f"<b>Autor:</b> {author}")
        author_label.setWordWrap(True)
        layout.addWidget(author_label)

        # Copyright
        current_year = datetime.now().year
        copyright_label = QLabel(f"<b>Copyright:</b> © {current_year} Daniel Beránek")
        layout.addWidget(copyright_label)

        # License
        license_label = QLabel(
            "<b>Licence:</b> Tento software je svobodný software pod licencí GNU GPL v3."
        )
        license_label.setWordWrap(True)
        layout.addWidget(license_label)

        # Source Code (Written Offer)
        source_label = QLabel(
            "<b>Zdrojový kód:</b> Zdrojový kód aplikace je dostupný na vyžádání u autora. "
            "Pro získání zdrojového kódu kontaktujte <a href='mailto:daniel.beranek@fsv.cvut.cz'>daniel.beranek@fsv.cvut.cz</a>"
        )
        source_label.setWordWrap(True)
        layout.addWidget(source_label)

        # Add separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # Funding acknowledgment
        funding_label = QLabel(
            "<b>Financování:</b> Tento software Software pro výpočet teplot v nosné konstrukci tunelu "
            "při požáru (CK04000274-V2) byl vytvořen se státní podporou "
            "Technologické agentury ČR a Ministerstva dopravy v rámci Programu DOPRAVA 2020+."
        )
        funding_label.setWordWrap(True)
        layout.addWidget(funding_label)

        # Project page link
        project_link = QLabel(
            '<b>Stránka projektu:</b> <a href="https://confire.fsv.cvut.cz/projekty/tunely-pri-pozaru/">'
            'https://confire.fsv.cvut.cz/projekty/tunely-pri-pozaru/</a>'
        )
        project_link.setOpenExternalLinks(True)
        project_link.setWordWrap(True)
        layout.addWidget(project_link)

        # TACR link
        tacr_link = QLabel(
            '<b>TAČR:</b> <a href="https://tacr.gov.cz/">https://tacr.gov.cz/</a>'
        )
        tacr_link.setOpenExternalLinks(True)
        layout.addWidget(tacr_link)

        # Add separator line
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator2)

        # Credits - Used Libraries
        credits_label = QLabel(
            "<b>Použité knihovny:</b> PySide6, PyVista, NumPy, SciPy, Gmsh, "
            "h5py, pypardiso, numba, meshio, colorcet, pyqtgraph"
        )
        credits_label.setWordWrap(True)
        layout.addWidget(credits_label)

        # Add stretch to push content to top
        layout.addStretch()

        # Set content widget to scroll area
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # Footer: Close button (outside scroll area, always visible)
        button_layout = QVBoxLayout()
        button_layout.setContentsMargins(25, 10, 25, 15)
        close_button = QPushButton("Zavřít")
        close_button.setDefault(True)
        close_button.clicked.connect(dialog.accept)
        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)

        dialog.exec()

    def closeEvent(self, event, /) -> None:
        """Handle window close event to prompt for saving if modified."""
        # 1. Ask to save if modified
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                "Uložit změny?",
                "Projekt byl změněn. Chcete uložit změny před ukončením?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )

            if reply == QMessageBox.Save:
                self.on_file_save()
                # If save failed (user cancelled file dialog), we abort the exit
                if not self.project.filepath:
                    event.ignore()  # Don't close window
                    return  # Stop here (keep app running)
            elif reply == QMessageBox.Cancel:
                event.ignore()  # Don't close window
                return  # Stop here (keep app running)

        # If we get here, the user wants to close (Discard or Save Success)

        # Clean up Temp Files if any
        IOManager.cleanup_temp_files()

        # 3. Close the PyVista plotter safely
        if self.visualizer and self.visualizer.plotter:
            self.visualizer.plotter.close()

        event.accept() # Actually close the window

    def _invalidate_mesh(self) -> None:
        """Helper to invalidate mesh and update UI."""
        if self.project.mesh_path:
            self.project.mesh_path = None
            self.mesh_panel.reset_status()
            self.act_export_mesh.setEnabled(False)

    def _invalidate_results(self) -> None:
        """Helper to invalidate results and update UI."""
        if self.project.results:
            self.project.results = []
            self.project.time_steps = []
            self.results_panel.reset_status()
            self.act_export_vtu.setEnabled(False)
            self.visualizer.update_scene(project_state=self.project, reset_camera=False)
