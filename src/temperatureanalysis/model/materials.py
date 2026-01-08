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

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)

class ThermalConductivityBoundary(StrEnum):
    """Boundary selection for thermal conductivity in concrete materials."""
    LOWER = "lower"
    UPPER = "upper"

class MaterialType(StrEnum):
    GENERIC = "Vlastní"
    CONCRETE = "Beton (ČSN EN 1992-1-2 ed. 2)"


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
    TemperatureDependentProperty.DENSITY: PropertyMetadata(label="Objemová hmotnost", unit="kg/m³"),
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
        elif property_type == TemperatureDependentProperty.SPECIFIC_HEAT_CAPACITY:
            prop = self.specific_heat_capacity
        elif property_type == TemperatureDependentProperty.DENSITY:
            prop = self.density

        if not prop:
            return np.array([]), np.array([])

        # Use the property's own temperatures, not conductivity's!
        temps = np.array(prop.temperatures)
        values = np.array(prop.values)
        return temps, values

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
            "conductivity_boundary": self.conductivity_boundary
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

    # --- EUROCODE CALCULATION METHODS (ČSN EN 1992-1-2) ---

    def _calculate_thermal_conductivity(self, temp_celsius: float) -> float:
        """
        Calculate thermal conductivity according to Eurocode 2.

        Args:
            temp_celsius: Temperature in Celsius

        Returns:
            Thermal conductivity in W/(m·K)
        """
        if self.conductivity_boundary == ThermalConductivityBoundary.UPPER:
            if temp_celsius <= 1200.0:
                return 2 - 0.2451 * (temp_celsius / 100.0) + 0.0107 * (temp_celsius / 100.0) ** 2
            return 0.5996
        else:  # LOWER boundary
            if temp_celsius <= 1200.0:
                return 1.36 - 0.136 * (temp_celsius / 100.0) + 0.0057 * (temp_celsius / 100.0) ** 2
            return 0.5488

    def _calculate_density(self, temp_celsius: float) -> float:
        """
        Calculate density according to Eurocode 2.

        Args:
            temp_celsius: Temperature in Celsius

        Returns:
            Density in kg/m³
        """
        if temp_celsius <= 115.0:
            return self.initial_density
        if temp_celsius <= 200.0:
            return self.initial_density * (1 - 0.02 * (temp_celsius - 115.0) / 85.0)
        if temp_celsius <= 400.0:
            return self.initial_density * (0.98 - 0.03 * (temp_celsius - 200.0) / 200.0)
        return self.initial_density * (0.95 - 0.07 * (temp_celsius - 400.0) / 800.0)

    def _calculate_specific_heat(self, temp_celsius: float) -> float:
        """
        Calculate specific heat capacity according to Eurocode 2.

        Args:
            temp_celsius: Temperature in Celsius

        Returns:
            Specific heat capacity in J/(kg·K)
        """
        # Moisture bump for specific heat capacity
        u_V = np.array([0.0, 1.5, 3.0, 10.0])
        d_V = np.array([900.0, 1470.0, 2020.0, 5600.0]) - 900.0
        d = float(np.interp(self.initial_moisture_content, u_V, d_V))  # moisture bump

        if temp_celsius <= 100.0:
            return 900.0
        if temp_celsius <= 115.0:
            return 900.0 + d
        if temp_celsius <= 200.0:
            return 900.0 + d - ((900.0 + d - 1000.0) / 85.0) * (temp_celsius - 115.0)
        if temp_celsius <= 400.0:
            return 1000.0 + (temp_celsius - 200.0) / 2.0
        # else:
        return 1100.0

    def get_preview_curve(
        self,
        property_name: TemperatureDependentProperty,
        temperature_min: float = 20,
        temperature_max: float = 1200,
        steps: int = 100
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Generate preview curve for plotting in the UI.
        Uses Eurocode 2 (ČSN EN 1992-1-2) formulas.
        """
        if property_name == TemperatureDependentProperty.CONDUCTIVITY:
            temps_celsius = np.linspace(20, 1200, num=steps)
            vals = np.array([self._calculate_thermal_conductivity(t) for t in temps_celsius])
        elif property_name == TemperatureDependentProperty.DENSITY:
            temps_celsius = np.array([20, 115, 200, 400, 1200])
            vals = np.array([self._calculate_density(t) for t in temps_celsius])
        elif property_name == TemperatureDependentProperty.SPECIFIC_HEAT_CAPACITY:
            temps_celsius = np.array([20, 100, 115, 200, 400, 1200])
            vals = np.array([self._calculate_specific_heat(t) for t in temps_celsius])
        else:
            raise ValueError(f"Unknown property: {property_name}")

        return (temps_celsius, vals)



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
            name="Beton (ČSN EN 1992-1-2 ed.2)",
            description="Standardní beton podle ČSN EN 1992-1-2 ed.2",
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

