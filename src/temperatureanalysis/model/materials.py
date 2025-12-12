"""
Material Library Management
===========================
Defines the configuration data structures for materials.
These classes hold the PARAMETERS needed to initialize the FEA material classes.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, InitVar
from abc import ABC, abstractmethod
from enum import Enum, StrEnum
from typing import List, Dict, Optional, Union, Any, TYPE_CHECKING
import csv
import logging
import numpy as np

from temperatureanalysis.controller.fea.pre.material import ThermalConductivityBoundary, Concrete

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)

class MaterialType(StrEnum):
    GENERIC = "Vlastní"
    CONCRETE = "Beton (ČSN EN 1992-1-2)"


class TemperatureDependentProperty(StrEnum):
    CONDUCTIVITY = "conductivity"
    SPECIFIC_HEAT_CAPACITY = "specific_heat_capacity"
    DENSITY = "density"

@dataclass
class PropertyMetadata:
    label: str
    unit: str

# Centralized Metadata for UI and Plotting
PROPERTY_METADATA: Dict[TemperatureDependentProperty, PropertyMetadata] = {
    TemperatureDependentProperty.CONDUCTIVITY: PropertyMetadata(label="Tepelná vodivost", unit="W/(m·K)"),
    TemperatureDependentProperty.SPECIFIC_HEAT_CAPACITY: PropertyMetadata(label="Měrná tepelná kapacita", unit="J/(kg·K)"),
    TemperatureDependentProperty.DENSITY: PropertyMetadata(label="Hustota", unit="kg/m³"),
}

@dataclass
class MaterialProperty:
    """
    Represents a single physical property (e.g. conductivity, ...)
    of a material for GENERIC models.
    """
    property_type: TemperatureDependentProperty
    temperatures: List[float] = field(default_factory=list)
    values: List[float] = field(default_factory=list)

    def get_value_at(self, temperature: float) -> float:
        """Interpolate the property value at a given temperature."""
        if not self.temperatures or not self.values:
            raise ValueError(f"No data available for property '{self.property_type}'.")

        return float(
            np.interp(
                temperature,
                self.temperatures,
                self.values,
                left=self.values[0],
                right=self.values[-1]
            )
        )

    @property
    def name(self) -> str:
        return PROPERTY_METADATA[self.property_type].label

    @property
    def unit(self) -> str:
        return PROPERTY_METADATA[self.property_type].unit

    def set_curve(self, temps: List[float], vals: List[float]):
        if not temps or len(temps) != len(vals):
            self.temperatures = []
            self.values = []
            return

        combined = sorted(zip(temps, vals), key=lambda x: x[0])
        self.temperatures, self.values = map(list, zip(*combined))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> MaterialProperty:
        return MaterialProperty(**data)

@dataclass
class ConcreteConfig:
    """
    Configuration for concrete material according to ČSN EN 1992-1-2.
    """
    initial_density: float = 2300.0  # kg/m³
    initial_moisture_content: float = 1.5  # %
    conductivity_boundary: ThermalConductivityBoundary = ThermalConductivityBoundary.UPPER

@dataclass(kw_only=True)
class Material(ABC):
    """
    Abstract base class for material configurations.
    """
    name: str
    description: str = ""

    @property
    @abstractmethod
    def type(self) -> MaterialType:
        pass

    @abstractmethod
    def get_preview_curve(
        self,
        property_name: TemperatureDependentProperty,
        temperature_min: float = 20,
        temperature_max: float = 1200,
        steps: int = 100
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """Get temperature and property value arrays for previewing the property curve."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Base serialization method."""
        return {
            "name": self.name,
            "description": self.description,
            "type": self.type.value
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Material:
        """Factory method to deserialize into correct subclass."""
        mat_type = MaterialType(data.get("type", MaterialType.GENERIC))
        if mat_type == MaterialType.GENERIC:
            return GenericMaterial.from_dict(data)
        elif mat_type == MaterialType.CONCRETE:
            return ConcreteMaterial.from_dict(data)
        else:
            raise ValueError(f"Unknown material type: {mat_type}")


@dataclass(kw_only=True)
class GenericMaterial(Material):
    """Material defined by explicit temperature-dependent properties."""
    conductivity: MaterialProperty = field(
        default_factory=lambda: MaterialProperty(
            property_type=TemperatureDependentProperty.CONDUCTIVITY,
            temperatures=[20.0, 1200.0], values=[1.6, 1.6]
        )
    )

    density: MaterialProperty = field(
        default_factory=lambda: MaterialProperty(
            property_type=TemperatureDependentProperty.DENSITY,
            temperatures=[20.0, 1200.0], values=[2300.0, 2300.0]
        )
    )

    specific_heat_capacity: MaterialProperty = field(
        default_factory=lambda: MaterialProperty(
            property_type=TemperatureDependentProperty.SPECIFIC_HEAT_CAPACITY,
            temperatures=[20.0, 1200.0], values=[900.0, 900.0]
        )
    )

    @property
    def type(self) -> MaterialType:
        return MaterialType.GENERIC

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            TemperatureDependentProperty.CONDUCTIVITY: self.conductivity.to_dict(),
            TemperatureDependentProperty.DENSITY: self.density.to_dict(),
            TemperatureDependentProperty.SPECIFIC_HEAT_CAPACITY: self.specific_heat_capacity.to_dict()
        })
        return base

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> GenericMaterial:
        material = GenericMaterial(
            name=data.get("name", "Unnamed Material"),
            description=data.get("description", ""))

        if TemperatureDependentProperty.CONDUCTIVITY in data:
            material.conductivity = MaterialProperty.from_dict(
                data[TemperatureDependentProperty.CONDUCTIVITY]
            )
        if TemperatureDependentProperty.DENSITY in data:
            material.density = MaterialProperty.from_dict(
                data[TemperatureDependentProperty.DENSITY]
            )
        if TemperatureDependentProperty.SPECIFIC_HEAT_CAPACITY in data:
            material.specific_heat_capacity = MaterialProperty.from_dict(
                data[TemperatureDependentProperty.SPECIFIC_HEAT_CAPACITY]
            )

        return material

    def get_preview_curve(
        self,
        property_type: TemperatureDependentProperty,
        temperature_min: float = 20,
        temperature_max: float = 1200,
        steps: int = 100
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        # Map Enum to instance attribute
        prop = None
        if property_type == TemperatureDependentProperty.CONDUCTIVITY:
            prop = self.conductivity
            temps = self.conductivity.temperatures
        elif property_type == TemperatureDependentProperty.SPECIFIC_HEAT_CAPACITY:
            prop = self.specific_heat_capacity
            temps = self.conductivity.temperatures
        elif property_type == TemperatureDependentProperty.DENSITY:
            prop = self.density
            temps = self.conductivity.temperatures

        if not prop:
            return temps, np.zeros_like(temps)

        values = [prop.get_value_at(t) for t in temps]
        return temps, np.array(values)

    @classmethod
    def from_csv(cls, name: str, filepath: str) -> GenericMaterial:
        mat = cls(name=name, description=f"Imported from {filepath}")

        t_list, k_list, c_list, r_list = [], [], [], []

        try:
            with open(filepath, mode='r', encoding='utf-8-sig') as f:
                line = f.readline()
                delimiter = ';' if ';' in line else ','
                f.seek(0)
                reader = csv.reader(f, delimiter=delimiter)
                for row in reader:
                    if not row or not row[0][0].isdigit(): continue
                    try:
                        t, k, c, r = map(lambda x: float(x.replace(',', '.')), row[:4])
                        t_list.append(t)
                        k_list.append(k)
                        c_list.append(c)
                        r_list.append(r)
                    except (ValueError, IndexError):
                        continue

            mat.conductivity.set_curve(t_list, k_list)
            mat.specific_heat_capacity.set_curve(t_list, c_list)
            mat.density.set_curve(t_list, r_list)

            return mat
        except Exception as e:
            logger.error(f"CSV Import failed: {e}")
            raise IOError(f"Failed to read CSV: {e}")

@dataclass(kw_only=True)
class ConcreteMaterial(Material):
    initial_density: float = ConcreteConfig.initial_density,
    initial_moisture_content: float = ConcreteConfig.initial_moisture_content,
    conductivity_boundary: ThermalConductivityBoundary = ConcreteConfig.conductivity_boundary

    @property
    def type(self) -> MaterialType:
        return MaterialType.CONCRETE

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "initial_density": self.initial_density,
            "initial_moisture_content": self.initial_moisture_content,
            "conductivity_boundary": self.conductivity_boundary.value
        })
        return base

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> ConcreteMaterial:
        return ConcreteMaterial(
            name=data.get("name", "Unnamed Concrete"),
            description=data.get("description", ""),
            initial_density=data.get("initial_density", ConcreteConfig.initial_density),
            initial_moisture_content=data.get("initial_moisture_content", ConcreteConfig.initial_moisture_content),
            conductivity_boundary=ThermalConductivityBoundary(data.get("conductivity_boundary", ConcreteConfig.conductivity_boundary.value))
        )

    def get_preview_curve(
        self,
        property_name: TemperatureDependentProperty,
        temperature_min: float = 20,
        temperature_max: float = 1200,
        steps: int = 100
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        concrete_material = Concrete(
            initial_density=self.initial_density,
            initial_moisture_content=self.initial_moisture_content,
            boundary=self.conductivity_boundary,
            name=self.name
        )

        if property_name == TemperatureDependentProperty.CONDUCTIVITY:
            temps_kelvin = np.linspace(293.15, 1473.15, num=steps)
            vals = np.array([concrete_material.thermal_conductivity(t) for t in temps_kelvin])
        elif property_name == TemperatureDependentProperty.DENSITY:
            temps_kelvin = np.array([293.15, 388.15, 473.15, 673.15, 1473.15])
            vals = np.array([concrete_material.density(t) for t in temps_kelvin])
        elif property_name == TemperatureDependentProperty.SPECIFIC_HEAT_CAPACITY:
            temps_kelvin = np.array([293.15, 373.15, 388.15, 473.15, 673.15, 1473.15])
            vals = np.array([concrete_material.specific_heat_capacity(t) for t in temps_kelvin])
        else:
            raise ValueError(f"Unknown property: {property_name}")

        return (temps_kelvin - 273.15, vals)  # Convert to Celsius for output



class MaterialLibrary:
    """
    Manages a library of materials, including loading from files
    and retrieving material definitions.
    """
    def __init__(self) -> None:
        self.materials: Dict[str, Material] = {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        # Concrete
        concrete = ConcreteMaterial(
            name="Beton (ČSN EN 1992-1-2)",
            description="Standardní beton podle ČSN EN 1992-1-2",
            initial_density=ConcreteConfig.initial_density,
            initial_moisture_content=ConcreteConfig.initial_moisture_content,
            conductivity_boundary=ConcreteConfig.conductivity_boundary
        )

        self.materials[concrete.name] = concrete

    def add_material(self, material: GenericMaterial):
        """Add or update a material in the library."""
        self.materials[material.name] = material

    def get_material(self, name: str) -> Optional[GenericMaterial]:
        """Retrieve a material by name."""
        return self.materials.get(name)

    def get_names(self) -> List[str]:
        """List all material names in the library."""
        return list(self.materials.keys())

