from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from PySide6.QtCore import QObject, Signal

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from temperatureanalysis.app.ui.panels.material_dialog.properties import TemperatureDependentMaterial
    from temperatureanalysis.app.ui.preview import PreviewDomain


class Stage(IntEnum):
    """The main stages of the workflow."""
    GEOMETRY = 0
    MATERIALS = 1
    BCS = 2
    MESH = 3
    SOLVER = 4
    RESULTS = 5

@dataclass
class GeometryModel:
    """Holds the current geometry_editors as drawable layers."""
    domains: list[PreviewDomain] = field(default_factory=list)

@dataclass
class MaterialsModel:
    """Domain → material mapping, and the readable domain names list."""
    materials: list[TemperatureDependentMaterial] = field(default_factory=list)
    domain_material_map: dict[PreviewDomain, TemperatureDependentMaterial] = field(default_factory=dict)

@dataclass
class BCsModel:
    """Boundary → Fire Curve mapping, and the readable boundary names list."""
    boundaries: list[str] = field(default_factory=list)
    fire_curve_map: dict[str, str] = field(default_factory=dict)

@dataclass
class MeshResult:
    """Basic mesh metrics for the Mesh tab."""
    n_nodes: int = 0
    n_elements: int = 0
    quality_min: float = 0.0
    quality_avg: float = 0.0

class Store(QObject):
    """Central state store with signals for panel/preview sync."""
    geometry_changed = Signal(object)
    materials_changed = Signal(object)
    bcs_changed = Signal(object)
    mesh_changed = Signal(object)

    gating_changed = Signal(int)
    _highest_allowed_stage = Stage.GEOMETRY

    def __init__(self) -> None:
        super().__init__()
        self.geometry_store = GeometryModel()
        self.material_store = MaterialsModel()
        self.bcs_store = BCsModel()
        self.mesh_store = MeshResult()

    def highest_allowed_stage(self) -> int:
        return self._highest_allowed_stage

    def _set_allowed_up_to(self, stage: Stage) -> None:
        if stage != self._highest_allowed_stage:
            self._highest_allowed_stage = stage
            self.gating_changed.emit(self._highest_allowed_stage)

    def invalidate_from(self, stage: Stage) -> None:
        if stage <= Stage.MATERIALS:
            self.material_store = MaterialsModel()
            self.materials_changed.emit(self.material_store)
        if stage <= Stage.BCS:
            self.bcs_store = BCsModel()
            self.bcs_changed.emit(self.bcs_store)
        if stage <= Stage.MESH:
            self.mesh_store = MeshResult()
            self.mesh_changed.emit(self.mesh_store)
        if stage <= Stage.SOLVER:
            pass
        if stage <= Stage.RESULTS:
            pass

        self._set_allowed_up_to(Stage(stage - 1))

    def set_domains(self, domains: list[PreviewDomain]) -> None:
        self.geometry_store.domains = domains
        self.geometry_changed.emit(self.geometry_store)
        self._set_allowed_up_to(Stage.MATERIALS)

    def set_materials(self, m: MaterialsModel) -> None:
        self.material_store = m
        self.materials_changed.emit(self.material_store)
        self._set_allowed_up_to(Stage.BCS)

    def add_material(self, material: TemperatureDependentMaterial) -> None:
        if material.name in [m.name for m in self.material_store.materials]:
            raise ValueError(f"Material with name '{material.name}' already exists.")
        self.material_store.materials.append(material)
        self.materials_changed.emit(self.material_store)
        self.invalidate_from(stage=Stage.BCS)

    def update_material(self, material: TemperatureDependentMaterial) -> None:
        for i, m in enumerate(self.material_store.materials):
            if m.name == material.name:
                self.material_store.materials[i] = material
                self.materials_changed.emit(self.material_store)
                self.invalidate_from(stage=Stage.BCS)
                return
        raise ValueError(f"Material with name '{material.name}' not found.")

    def assign_material_to_domain(self, domain: PreviewDomain, material: TemperatureDependentMaterial) -> None:
        self.material_store.domain_material_map[domain] = material
        self.materials_changed.emit(self.material_store)
        self.invalidate_from(stage=Stage.BCS)


    def set_bcs(self, b: BCsModel) -> None:
        self.bcs_store = b
        self.bcs_changed.emit(self.bcs_store)
        self._set_allowed_up_to(Stage.MESH)

    def set_mesh(self, m: MeshResult) -> None:
        self.mesh_store = m
        self.mesh_changed.emit(self.mesh_store)
        self._set_allowed_up_to(Stage.SOLVER)
