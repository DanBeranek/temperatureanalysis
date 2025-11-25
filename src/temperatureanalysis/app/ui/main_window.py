"""
Your current main window, split out and made fully translatable with live switching.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSettings, QSize, Slot, QT_TRANSLATE_NOOP, QCoreApplication
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QListWidget, QStackedWidget, QWidget,
    QVBoxLayout, QLabel, QDockWidget, QScrollArea, QFormLayout, QPlainTextEdit,
    QToolBar, QStatusBar, QProgressBar, QFileDialog, QMessageBox, QPushButton, QApplication,
    QDialog, QComboBox, QDialogButtonBox, QHBoxLayout, QDoubleSpinBox, QTabBar, QTabWidget
)
from datetime import datetime

from temperatureanalysis.app.state import Store, Stage


from temperatureanalysis.app.application import install_translator, VISIBLE_APP_NAME
from temperatureanalysis.app.ui.panels.geometry import GeometryPanel
from temperatureanalysis.app.ui.panels.material import MaterialPanel
from temperatureanalysis.app.ui.panels.placeholder_panel import PlaceholderPanel
from temperatureanalysis.app.ui.workarea import WorkArea

# Section keys (stable). Display text is translated in retranslate_ui().
SECTION_KEYS = ["geometry_editors", "materials", "bcs", "mesh", "solver", "results"]

SECTION_LABELS = {
    "geometry_editors": QT_TRANSLATE_NOOP("Sections", "Geometry"),
    "materials": QT_TRANSLATE_NOOP("Sections", "Materials"),
    "bcs": QT_TRANSLATE_NOOP("Sections", "Boundary Conditions"),
    "mesh": QT_TRANSLATE_NOOP("Sections", "Mesh"),
    "solver": QT_TRANSLATE_NOOP("Sections", "Solver"),
    "results": QT_TRANSLATE_NOOP("Sections", "Results"),
}

class Console(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

    def _log(self, level: str, msg: str) -> None:
        self.appendPlainText(f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')} [{level}] {msg}")

    def info(self, msg: str) -> None:
        self._log("info", msg)

    def warn(self, msg: str) -> None:
        self._log("warn", msg)

    def error(self, msg: str) -> None:
        self._log("error", msg)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(VISIBLE_APP_NAME)
        self.resize(1400, 900)

        # Global store
        self.store = Store()

        # ---- Central: TabBar on top + WorkArea below ----
        central = QWidget(self)
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self.tabs = QTabBar(central)
        self.tabs.setExpanding(True)
        self.tabs.setMovable(False)
        self.tabs.setTabsClosable(False)
        self.tabs.setDrawBase(True)
        self.tabs.setShape(QTabBar.Shape.RoundedNorth)
        v.addWidget(self.tabs, 0)

        self.work_area = WorkArea(central)
        v.addWidget(self.work_area, 1)

        self.setCentralWidget(central)

        self.panels = [
            GeometryPanel(self.store, parent=self),
            MaterialPanel(self.store, parent=self),
        ] + [
            PlaceholderPanel(self.store, parent=self) for _ in SECTION_KEYS[2:]
        ]

        for p in self.panels:
            self.work_area.panel_stack.addWidget(p)

        self._stage_order = [
            Stage.GEOMETRY, Stage.MATERIALS, Stage.BCS, Stage.MESH, Stage.SOLVER, Stage.RESULTS
        ]
        for key in SECTION_KEYS:
            self.tabs.addTab(self.tr(SECTION_LABELS[key]))
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # React to gating updates from the store
        self.store.gating_changed.connect(self._apply_gating)
        self._apply_gating(self.store.highest_allowed_stage())
        self.tabs.setCurrentIndex(self._stage_order.index(Stage.GEOMETRY))

        self.store.geometry_changed.connect(lambda *_: self._refresh_if(Stage.GEOMETRY))
        self.store.materials_changed.connect(lambda *_: self._refresh_if(Stage.MATERIALS))
        self.store.bcs_changed.connect(lambda *_: self._refresh_if(Stage.BCS))
        self.store.mesh_changed.connect(lambda *_: self._refresh_if(Stage.MESH))

        self._render_preview_for_stage(Stage.GEOMETRY)

    def _apply_gating(self, highest_allowed: int) -> None:
        """Enable/disable tabs based on the highest allowed stage."""
        for i, stage in enumerate(self._stage_order):
            allowed = i <= highest_allowed
            self.tabs.setTabEnabled(i, allowed)

    def _on_tab_changed(self, idx: int) -> None:
        if not self.tabs.isTabEnabled(idx):
            # find nearest enabled tab (usually the current)
            for i in range(len(self._stage_order) - 1, -1, -1):
                if self.tabs.isTabEnabled(i):
                    self.tabs.setCurrentIndex(i)
                    break
            return
            # switch panel stack
        self.work_area.set_panel_index(idx)
        self._render_preview_for_stage(self._current_stage())

    def _refresh_if(self, stage: Stage) -> None:
        """If the given stage is the current one, refresh the preview."""
        if stage == self._current_stage():
            self._render_preview_for_stage(stage)

    def _current_stage(self) -> Stage:
        return self._stage_order[self.tabs.currentIndex()]

    def _render_preview_for_stage(self, stage: Stage) -> None:
        """
        Update the 2D preview based on the current stage.
        """
        preview = self.work_area.preview

        match stage:
            case Stage.GEOMETRY:
                preview.set_preview(self.store.geometry_store.domains)

            case Stage.MATERIALS:
                preview.set_preview(self.store.geometry_store.domains)

            case Stage.BCS:
                layers = self._layers_for_bcs_view()
                preview.set_preview(layers)

            case _:
                preview.set_preview([])

    def _layers_for_materials_view(self):
        """
        Return layers colored/highlighted per material-domain mapping.
        For now just return geometry; later, recolor according to self.store.materials.material_map.
        """
        return self.store.geometry_store.domains

    def _layers_for_bcs_view(self):
        """
        Return layers with certain outlines thickened/colored per BC assignment.
        For now just return geometry; later, modify edge_width/colors for assigned outlines.
        """
        return self.store.geometry_store.domains





    # # ---------- Language menu / retranslate ----------
    #
    # def _build_language_menu(self):
    #     menubar = self.menuBar()
    #     self.menuLanguage = menubar.addMenu(self.tr("Language"))
    #     self.menuLanguage.clear()
    #
    #     def add(lang_code: str, label: str):
    #         act = QAction(label, self)
    #         act.triggered.connect(lambda _=False, c=lang_code: self.set_language(c))
    #         self.menuLanguage.addAction(act)
    #
    #     add("en", "English")
    #     add("cs", "Čeština")
    #
    # def _build_help_menu(self):
    #     menubar = self.menuBar()
    #     self.menuHelp = menubar.addMenu(self.tr("Help"))
    #     self.menuHelp.clear()
    #
    #     act_about = QAction(self.tr("About"), self)
    #     act_about.triggered.connect(self.on_about)
    #     self.menuHelp.addAction(act_about)
    #
    # def _fill_nav(self):
    #     self.nav.clear()
    #     for key in SECTION_KEYS:
    #         label = QCoreApplication.translate("Sections", SECTION_LABELS[key])
    #         self.nav.addItem(label)
    #
    # def retranslate_ui(self):
    #     """Refresh all user-visible strings after language change."""
    #     app = QApplication.instance()
    #     app.setApplicationDisplayName(self.tr("Tunel požár"))
    #
    #     self.setWindowTitle(self.tr("Fire Heat Analysis"))
    #     self.dockInspector.setWindowTitle(self.tr("Properties"))
    #     self.dockConsole.setWindowTitle(self.tr("Console"))
    #
    #     # Toolbar/action text
    #     self.findChild(QToolBar).setWindowTitle(self.tr("Main"))
    #     self.actNew.setText(self.tr("New"))
    #     self.actOpen.setText(self.tr("Open…"))
    #     self.actSave.setText(self.tr("Save"))
    #     self.actRun.setText(self.tr("Run"))
    #     self.actStop.setText(self.tr("Stop"))
    #     self.actRerun.setText(self.tr("Re-run"))
    #     self.actNewTunnel.setText(self.tr("New Tunnel"))
    #
    #     # Menus
    #     self.menuLanguage.setTitle(self.tr("Language"))
    #     self.menuHelp.setTitle(self.tr("Help"))
    #     # (menu actions were plain labels—fine as-is)
    #
    #     # Pages & nav
    #     for p in self._pages:
    #         p.retranslate()
    #     current = self.nav.currentRow()
    #     self._fill_nav_labels()
    #     self.nav.setCurrentRow(current)
    #
    #     # Console placeholder (if you want to update it)
    #     self.console.setPlaceholderText(self.tr("Log output will appear here…"))
    #
    # def set_language(self, code: str):
    #     ok = install_translator(QApplication.instance(), code)
    #     if ok:
    #         QSettings().setValue("ui/language", code)
    #         self.retranslate_ui()
    #         self.console.info(self.tr("Language set to {code}").format(code=code))
    #     else:
    #         self.console.warn(self.tr("No translation loaded for {code}").format(code=code))
    #
    # # ---------- File ops (stubs) ----------
    #
    # @Slot()
    # def on_open(self):
    #     path, _ = QFileDialog.getOpenFileName(
    #         self,
    #         self.tr("Open Project"),
    #         "",
    #         self.tr("Project (*.json *.yaml);;All Files (*)"),
    #     )
    #     if not path:
    #         return
    #     self.console.info(self.tr("Opened project: {path}").format(path=path))
    #
    # @Slot()
    # def on_save(self):
    #     path, _ = QFileDialog.getSaveFileName(
    #         self,
    #         self.tr("Save Project As"),
    #         "",
    #         self.tr("Project (*.json);;All Files (*)"),
    #     )
    #     if not path:
    #         return
    #     self.console.info(self.tr("Saved project: {path}").format(path=path))
    #
    # # ---------- Solver controls (stubs) ----------
    #
    # @Slot()
    # def on_run(self, restart: bool):
    #     self.console.info(
    #         self.tr("Running simulation…") if not restart else self.tr("Re-running last simulation…")
    #     )
    #     self.progress.setValue(0)
    #     # TODO: hook your worker thread; emit progress to setValue
    #     self.progress.setValue(42)
    #
    # @Slot()
    # def on_stop(self):
    #     self.console.warn(self.tr("Stop requested."))
    #
    # # ---------- About ----------
    #
    # @Slot()
    # def on_about(self):
    #     QMessageBox.about(
    #         self,
    #         self.tr("About {app}").format(app=QApplication.applicationDisplayName()),
    #         self.tr(
    #             "{app}.\n"
    #             "Organization: {org}\n"
    #             "Version: {ver}"
    #         ).format(
    #             app=QApplication.applicationDisplayName(),
    #             org=self.tr("CTU in Prague, Faculty of Civil Engineering"),
    #             ver=self._version(),
    #         ),
    #     )
    #
    # @Slot()
    # def on_new_tunnel(self):
    #     dlg = TunnelTypeDialog(parent=self)
    #     if dlg.exec() == QDialog.Accepted:
    #         editor = make_tunnel_dialog(dlg.selected_key(), parent=self)
    #         if editor.exec() == QDialog.Accepted:
    #             params: dict[str, float] = editor.params() if hasattr(editor, "params") else {}
    #             # TODO: store params to your project model / current document, e.g.:
    #             # self.project.set_tunnel_config(tkey, params)
    #             self.console.info(self.tr("Tunnel saved ({n} params)").format(n=len(params)))
    #         else:
    #             self.console.info(self.tr("Tunnel generator canceled."))
    #     else:
    #         self.console.info(self.tr("New tunnel canceled."))
    #
    # def _version(self) -> str:
    #     try:
    #         from importlib.metadata import version
    #         return version("temperatureanalysis")
    #     except Exception:
    #         return "dev"
    #
    # # ---------- Close/save UI state ----------
    # def closeEvent(self, e):
    #     self._settings.setValue("win/geo", self.saveGeometry())
    #     self._settings.setValue("win/state", self.saveState())
    #     super().closeEvent(e)
