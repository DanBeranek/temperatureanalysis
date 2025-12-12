from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from typing import TYPE_CHECKING, Optional

import numpy as np

from temperatureanalysis.controller.fea.pre.material_helpers import (
    concrete_props_batch, steel_props_batch
)

from temperatureanalysis.controller.fea.utils import kelvin_to_celsius
from temperatureanalysis.model.materials import ThermalConductivityBoundary

if TYPE_CHECKING:
    import numpy.typing as npt


class Material(ABC):
    """Abstract base class for materials used in temperature analysis."""

    def __init__(
        self,
        name:str,
        color: str,
        initial_density: float
    ):
        """Initialize the material with an initial density.

        Args:
            name: The name of the material.
            color: The color of the material, used for visualization.
            initial_density: Initial density of the material in kg/m³.
        """
        self.name = name
        self.color = color
        self.initial_density = initial_density

    @abstractmethod
    def thermal_conductivity(self, temperature_K: float) -> float:
        """Calculate the thermal conductivity of the material at a given temperature in Kelvin.

        Args:
            temperature_K (float): Temperature in Kelvin.

        Returns:
            float: Thermal conductivity in W/(m·K).
        """
        pass

    @abstractmethod
    def density(self, temperature_K: float) -> float:
        """Calculate the density of the material at a given temperature in Kelvin.

        Args:
            temperature_K (float): Temperature in Kelvin.

        Returns:
            float: Density in kg/m³.
        """
        pass


    @abstractmethod
    def specific_heat_capacity(self, temperature_K: float) -> float:
        """Calculate the specific heat capacity of the material at a given temperature in Kelvin.

        Args:
            temperature_K (float): Temperature in Kelvin.

        Returns:
            float: Specific heat capacity in J/(kg·K).
        """
        pass

    def volumetric_heat_capacity(self, temperature_K: float) -> float:
        """Calculate the volumetric heat capacity of the material at a given temperature in Kelvin.

        Args:
            temperature_K (float): Temperature in Kelvin.

        Returns:
            float: Volumetric heat capacity in J/(m³·K).
        """
        return self.density(temperature_K) * self.specific_heat_capacity(temperature_K)

class GenericTabulatedMaterial(Material):
    """
    Generic material defined by tabulated properties.
    """
    def __init__(
        self,
        name: str,
        color: str,
        densities: npt.NDArray[np.float64],
        temperatures_K: npt.NDArray[np.float64],
        thermal_conductivities: npt.NDArray[np.float64],
        specific_heat_capacities: npt.NDArray[np.float64]
    ):
        super().__init__(name, color, densities[0])

        if not (
            len(temperatures_K) == len(densities) == len(thermal_conductivities) == len(specific_heat_capacities)
        ):
            raise ValueError("All input arrays must have the same length.")

        if not np.all(np.diff(temperatures_K) > 0):
            raise ValueError("Temperature array must be strictly increasing.")

        if np.any(densities <= 0):
            raise ValueError("Densities must be positive.")

        if np.any(thermal_conductivities <= 0):
            raise ValueError("Thermal conductivities must be positive.")

        if np.any(specific_heat_capacities <= 0):
            raise ValueError("Specific heat capacities must be positive.")

        if len(temperatures_K) < 2:
            raise ValueError("At least two data points are required for interpolation.")

        self.temperatures_K = temperatures_K
        self.densities = densities
        self.thermal_conductivities = thermal_conductivities
        self.specific_heat_capacities = specific_heat_capacities

    def thermal_conductivity(self, temperature_K: float) -> float:
        return np.interp(
            x=temperature_K,
            xp=self.temperatures_K,
            fp=self.thermal_conductivities,
            left=self.thermal_conductivities[0],
            right=self.thermal_conductivities[-1]
        )

    def density(self, temperature_K: float) -> float:
        return np.interp(
            x=temperature_K,
            xp=self.temperatures_K,
            fp=self.densities,
            left=self.densities[0],
            right=self.densities[-1]
        )

    def specific_heat_capacity(self, temperature_K: float) -> float:
        return np.interp(
            x=temperature_K,
            xp=self.temperatures_K,
            fp=self.specific_heat_capacities,
            left=self.specific_heat_capacities[0],
            right=self.specific_heat_capacities[-1]
        )


class Concrete(Material):
    """
    Concrete material for temperature analysis.

    Attributes:
        boundary: Boundary selection for thermal conductivity.
        u: Initial moisture content of the concrete from 0.0 to 1.0.
    """
    def __init__(
        self,
        initial_density: float = 2300.0,
        initial_moisture_content: float = 0.0,
        boundary: ThermalConductivityBoundary = ThermalConductivityBoundary.UPPER,
        name: str = "Concrete",
        color: str = "gray"
    ):
        self.boundary = boundary
        self.u = initial_moisture_content

        # Moisture bump for specific heat capacity
        u_V = np.array([0.0, 1.5, 3.0, 10.0])
        d_V = np.array([900.0, 1470.0, 2020.0, 5600.0]) - 900.0
        self.d: float = np.interp(self.u, u_V, d_V)

        super().__init__(
            name=name,
            color=color,
            initial_density=initial_density
        )

    def thermal_conductivity(self, temperature_K: float) -> float:
        """
        Calculate the thermal conductivity of concrete at a given temperature in Kelvin.

        Args:
            temperature_K (float): Temperature in Kelvin.

        Returns:
            float: Thermal conductivity in W/(m·K).
        """
        temp_C = kelvin_to_celsius(temperature_K)

        if self.boundary == ThermalConductivityBoundary.UPPER:
            if temp_C <= 1200.0:
                return 2 - 0.2451 * (temp_C / 100.0) + 0.0107 * (temp_C / 100.0) ** 2
            # temp_C > 1200.0
            return 0.5996

        # Lower boundary
        if temp_C <= 1200.0:
            return 1.36 - 0.136 * (temp_C / 100.0) + 0.0057 * (temp_C / 100.0) ** 2
        # temp_C > 1200.0
        return 0.5488

    def density(self, temperature_K: float) -> float:
        """Calculate the density of the concrete at a given temperature in Kelvin.

        Args:
            temperature_K (float): Temperature in Kelvin.

        Returns:
            float: Density in kg/m³.
        """
        temp_C = kelvin_to_celsius(temperature_K)

        if temp_C <= 115.0:
            return self.initial_density
        if temp_C <= 200.0:
            return self.initial_density * (1 - 0.02 * (temp_C - 115.0) / 85.0)
        if temp_C <= 400.0:
            return self.initial_density * (0.98 - 0.03 * (temp_C - 200.0) / 200.0)
        # else:
        return self.initial_density * (0.95 - 0.07 * (temp_C - 400.0) / 800.0)


    def specific_heat_capacity(self, temperature_K: float) -> float:
        """Calculate the specific heat capacity of the concrete at a given temperature in Kelvin.

        Args:
            temperature_K (float): Temperature in Kelvin.

        Returns:
            float: Specific heat capacity in J/(kg·K).
        """
        temp_C = kelvin_to_celsius(temperature_K)

        d = self.d

        if temp_C <= 100.0:
            return 900.0
        if temp_C <= 115.0:
            return 900.0 + d
        if temp_C <= 200.0:
            return 900.0 + d - ( (900.0 + d - 1000.0) / 85.0 ) * (temp_C - 115.0)
        if temp_C <= 400.0:
            return 1000.0 + (temp_C - 200.0) / 2.0
        # else:
        return 1100.0

    def props_batch(self, T_K: npt.NDArray[np.float64]) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Vectorized material properties for concrete.

        Args:
            T_K: Temperatures in Kelvin at Gauss points, shape (n,).

        Returns:
            k:    Thermal conductivity per T (W/(m·K)), shape (n,).
            rhoc: Volumetric heat capacity ρc_p(T) (J/(m³·K)), shape (n,).
        """
        use_upper = (self.boundary == ThermalConductivityBoundary.UPPER)
        return concrete_props_batch(T_K, self.initial_density, use_upper, self.d)


class Steel(Material):
    """
    Steel material for temperature analysis.
    """
    def __init__(
        self,
        name: str = "Steel",
        color: str = "black",
        initial_density: float = 7850.0):
        """Initialize the steel material with an initial density.

        Args:
            name: The name of the material.
            color: The color of the material, used for visualization.
            initial_density: Initial density of steel in kg/m³.
        """
        super().__init__(
            name=name,
            color=color,
            initial_density=initial_density
        )

    def thermal_conductivity(self, temperature_K: float) -> float:
        """Calculate the thermal conductivity of steel at a given temperature in Kelvin.

        Args:
            temperature_K (float): Temperature in Kelvin.

        Returns:
            float: Thermal conductivity in W/(m·K).
        """
        temp_C = kelvin_to_celsius(temperature_K)

        if temp_C <= 800.0:
            return 54.0 - 3.33 * temp_C / 100.0
        return 27.3

    def density(self, temperature_K: float) -> float:
        """Calculate the density of steel at a given temperature in Kelvin.

        Args:
            temperature_K (float): Temperature in Kelvin.

        Returns:
            float: Density in kg/m³.
        """
        return self.initial_density

    def specific_heat_capacity(self, temperature_K: float) -> float:
        """Calculate the specific heat capacity of steel at a given temperature in Kelvin.

        Args:
            temperature_K (float): Temperature in Kelvin.

        Returns:
            float: Specific heat capacity in J/(kg·K).
        """
        temp_C = kelvin_to_celsius(temperature_K)
        if temp_C <= 600.0:
            return self.initial_density * (425.0 + 7.73 * temp_C / 10.0 - 1.69 * (temp_C ** 2.0) / 1000.0 + 2.22 * (
                    temp_C ** 3) / 1_000_000.0)
        elif temp_C <= 735.0:
            return self.initial_density * (666.0 - (13_002.0 / (temp_C - 738.0)))
        elif temp_C <= 900.0:
            return self.initial_density * (545.0 + 17_820.0 / (temp_C - 731.0))
        else:
            return self.initial_density * 650.0

    def props_batch(self, T_K: npt.NDArray[np.float64]) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        """
        Vectorized material properties for steel.

        Args:
            T_K: Temperatures in Kelvin at Gauss points, shape (n,).

        Returns:
            k:    Thermal conductivity per T (W/(m·K)), shape (n,).
            rhoc: Volumetric heat capacity ρc_p(T) (J/(m³·K)), shape (n,).
        """
        return steel_props_batch(T_K, self.initial_density)
