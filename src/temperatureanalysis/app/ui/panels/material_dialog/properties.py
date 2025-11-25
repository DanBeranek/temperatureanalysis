from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from temperatureanalysis.fea.pre.material import ThermalConductivityBoundary, Concrete


@dataclass(frozen=True)
class TemperatureDependentProperty:
    """A temperature-dependent property curve."""
    name: str
    label: str
    unit: str
    temperature_celsius: Sequence[float]
    values: Sequence[float]


@dataclass(frozen=True)
class TemperatureDependentMaterial:
    """A temperature-dependent material."""
    name: str
    label: str
    description: str
    initial_density: float
    thermal_conductivity: TemperatureDependentProperty  # W/(m·K)
    density: TemperatureDependentProperty  # kg/m³
    specific_heat_capacity: TemperatureDependentProperty  # J/(kg·K)

    # Concrete-specific properties
    thermal_conductivity_boundary: ThermalConductivityBoundary | None = None
    initial_moisture_content: float | None = None

    @classmethod
    def from_inputs(
        cls,
        name: str,
        label: str,
        description: str,
        initial_density: float,
        thermal_conductivity_boundary: ThermalConductivityBoundary | None = None,
        initial_moisture_content: float | None = None
    ) -> TemperatureDependentMaterial:
        concrete = Concrete(
            initial_density=initial_density,
            boundary=thermal_conductivity_boundary,
            initial_moisture_content=initial_moisture_content
        )

        # density
        temperatures_kelvin_density = np.array([293.15, 388.15, 473.15, 673.15, 1473.15])
        density = []
        for T in temperatures_kelvin_density:
            density.append(concrete.density(temperature_K=T))
        density = np.array(density)

        # specific heat capacity
        temperatures_kelvin_specific_heat_capacity = np.array(
            [293.15, 373.15, 388.15, 473.15, 673.15, 1473.15]
        )
        specific_heat_capacity = []
        for T in temperatures_kelvin_specific_heat_capacity:
            specific_heat_capacity.append(concrete.specific_heat_capacity(temperature_K=T))
        specific_heat_capacity = np.array(specific_heat_capacity)

        # thermal conductivity
        temperatures_kelvin_thermal_conductivity = np.linspace(293.15, 1473.15, num=50)
        thermal_conductivity = []
        for T in temperatures_kelvin_thermal_conductivity:
            thermal_conductivity.append(concrete.thermal_conductivity(temperature_K=T))
        thermal_conductivity = np.array(thermal_conductivity)

        return cls(
            name=name,
            label=label,
            description=description,
            initial_density=initial_density,
            thermal_conductivity_boundary=thermal_conductivity_boundary,
            initial_moisture_content=initial_moisture_content,
            thermal_conductivity=TemperatureDependentProperty(
                name="thermal_conductivity",
                label="Thermal Conductivity",
                unit="W/(m·K)",
                temperature_celsius=temperatures_kelvin_thermal_conductivity - 273.15,
                values=thermal_conductivity
            ),
            density=TemperatureDependentProperty(
                name="density",
                label="Density",
                unit="kg/m³",
                temperature_celsius=temperatures_kelvin_density - 273.15,
                values=density
            ),
            specific_heat_capacity=TemperatureDependentProperty(
                name="specific_heat_capacity",
                label="Specific Heat Capacity",
                unit="J/(kg·K)",
                temperature_celsius=temperatures_kelvin_specific_heat_capacity - 273.15,
                values=specific_heat_capacity
            )
        )
