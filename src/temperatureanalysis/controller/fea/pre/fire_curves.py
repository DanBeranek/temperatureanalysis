from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

import numpy as np
import matplotlib.pyplot as plt

if TYPE_CHECKING:
    import numpy.typing as npt

# ==========================================
# ABSTRACT CLASS FOR FIRE CURVES
# ==========================================
class FireCurve(ABC):
    """
    Abstract base class for fire curves.
    """
    NAME: str = "Fire Curve"

    @abstractmethod
    def get_temperature(
        self,
        time: float | npt.NDArray[np.float64],
        position: Optional[float | npt.NDArray[np.float64]] = None,
    ) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature at a given time.

        Args:
            time: Time in seconds.
            position: Y-coordinate(s) in meters (optional,
                      for position-dependent curves).

        Returns:
            Temperature in Kelvin.
        """
        pass

    def plot(self) -> None:
        """
        Plot the fire curve.
        """
        times = np.linspace(0, 180 * 60, 500)  # 180 minutes in seconds
        temperatures = self.get_temperature(times)

        plt.rcParams["figure.constrained_layout.use"] = True
        fig = plt.figure(figsize=(7, 5))

        plt.plot(times / 60, temperatures - 273.15, 'r', lw=2)

        plt.grid(visible=True, which='major', axis='both', linestyle='-', color='gray', lw=0.5)
        plt.minorticks_on()
        plt.grid(visible=True, which='minor', axis='both', linestyle=':', color='gray', lw=0.5)

        plt.title(f"{self.NAME} Fire Curve")
        plt.xlabel("Time (minutes)")
        plt.ylabel("Temperature (°C)")

        plt.xlim(-5, 185)
        plt.show()

# ==========================================
# STANDARD CURVES (Position Independent)
# ==========================================

class ISO834FireCurve(FireCurve):
    """
    ISO 834 fire curve implementation.
    """
    NAME = "ISO 834, Cellulosic"
    CONVECTIVE_COEFFICIENT = 25.0  # W/m²K

    def get_temperature(
        self,
        time: float | npt.NDArray[np.float64],
        position: Optional[float | npt.NDArray[np.float64]] = None,
    ) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature at a given time.

        Args:
            time: Time in seconds.
            position: Y-coordinate(s) in meters (optional,
                      for position-dependent curves).

        Returns:
            Temperature in Kelvin.
        """
        return 273.15 + 20 + 345 * np.log10(8 * (time/60) + 1)


class HCFireCurve(FireCurve):
    """
    HydroCarbon fire curve implementation.
    """
    NAME = "HydroCarbon"
    CONVECTIVE_COEFFICIENT = 50.0  # W/m²K

    def get_temperature(
        self,
        time: float | npt.NDArray[np.float64],
        position: Optional[float | npt.NDArray[np.float64]] = None,
    ) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature at a given time.

        Args:
            time: Time in seconds.
            position: Y-coordinate(s) in meters (optional,
                      for position-dependent curves).

        Returns:
            Temperature in Kelvin.
        """
        return 273.15 + 20 + 1080 * (1 - 0.325 * np.exp(-0.167 * (time / 60)) - 0.675 * np.exp(-2.5 * (time / 60)))

class HCMFireCurve(FireCurve):
    """
    Modified HydroCarbon fire curve implementation according to ISO 834.
    """
    NAME = "Modified HydroCarbon"
    CONVECTIVE_COEFFICIENT = 50.0  # W/m²K

    def get_temperature(
        self,
        time: float | npt.NDArray[np.float64],
        position: Optional[float | npt.NDArray[np.float64]] = None,
    ) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature at a given time.

        Args:
            time: Time in seconds.
            position: Y-coordinate(s) in meters (optional,
                      for position-dependent curves).

        Returns:
            Temperature in Kelvin.
        """
        return 273.15 + 20 + 1280 * (1 - 0.325 * np.exp(-0.167 * (time / 60)) - 0.675 * np.exp(-2.5 * (time / 60)))

class RABTZTVTrainFireCurve(FireCurve):
    """
    RABT-ZTV (train) fire curve implementation.
    """
    NAME = "RABT-ZTV (train)"
    CONVECTIVE_COEFFICIENT = 50.0  # W/m²K

    TIMES = np.array([0.0, 5.0, 60.0, 170.0]) * 60.0  # Convert minutes to seconds

    TEMPERATURES = 273.15 + np.array([15.0, 1200.0, 1200.0, 15.0])  # Temperatures in Kelvin

    def get_temperature(
        self,
        time: float | npt.NDArray[np.float64],
        position: Optional[float | npt.NDArray[np.float64]] = None,
    ) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature at a given time.

        Args:
            time: Time in seconds.
            position: Y-coordinate(s) in meters (optional,
                      for position-dependent curves).

        Returns:
            Temperature in Kelvin.
        """
        t_array = np.atleast_1d(time)

        temperatures = np.interp(t_array, self.TIMES, self.TEMPERATURES)

        if np.isscalar(time):
            return float(temperatures[0])
        return temperatures

class RABTZTVCarFireCurve(FireCurve):
    """
    RABT-ZTV (car) fire curve implementation.
    """
    NAME = "RABT-ZTV (car)"
    CONVECTIVE_COEFFICIENT = 50.0  # W/m²K

    TIMES = np.array([0.0, 5.0, 30.0, 140.0]) * 60.0  # Convert minutes to seconds

    TEMPERATURES = 273.15 + np.array([15.0, 1200.0, 1200.0, 15.0])  # Temperatures in Kelvin

    def get_temperature(
        self,
        time: float | npt.NDArray[np.float64],
        position: Optional[float | npt.NDArray[np.float64]] = None,
    ) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature at a given time.

        Args:
            time: Time in seconds.
            position: Y-coordinate(s) in meters (optional,
                      for position-dependent curves).

        Returns:
            Temperature in Kelvin.
        """
        t_array = np.atleast_1d(time)

        temperatures = np.interp(t_array, self.TIMES, self.TEMPERATURES)

        if np.isscalar(time):
            return float(temperatures[0])
        return temperatures


class RWSFireCurve(FireCurve):
    """
    RWS (Rijkswaterstaat) fire curve implementation.
    """
    NAME = "RWS (Rijkswaterstaat)"
    CONVECTIVE_COEFFICIENT = 50.0  # W/m²K

    TIMES = np.array([0.0, 3.0, 5.0, 10.0, 30.0, 60.0, 90.0, 120.0, 180.0]) * 60.0  # Convert minutes to seconds

    TEMPERATURES = 273.15 + np.array([20.0, 890.0, 1140.0, 1200.0, 1300.0, 1350.0, 1300.0, 1200.0, 1200.0])  # Temperatures in Kelvin

    def get_temperature(
        self,
        time: float | npt.NDArray[np.float64],
        position: Optional[float | npt.NDArray[np.float64]] = None,
    ) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature at a given time.

        Args:
            time: Time in seconds.
            position: Y-coordinate(s) in meters (optional,
                      for position-dependent curves).

        Returns:
            Temperature in Kelvin.
        """
        t_array = np.atleast_1d(time)

        temperatures = np.interp(t_array, self.TIMES, self.TEMPERATURES)

        if np.isscalar(time):
            return float(temperatures[0])
        return temperatures


class TabulatedFireCurve(FireCurve):
    """
    User-defined fire curve based on tabulated time-temperature points.
    """
    CONVECTIVE_COEFFICIENT = 50.0  # W/m²K

    def __init__(
        self,
        times: list[float] | npt.NDArray[np.float64],
        temperatures: list[float] | npt.NDArray[np.float64],
        name: str = "Tabulated Fire Curve"
    ):
        """
        Args:
            times: Array of time points in seconds.
            temperatures: Array of corresponding temperatures in Kelvin.
            name: Display name for the curve.
        """
        times_arr = np.array(times, dtype=np.float64)
        temps_arr = np.array(temperatures, dtype=np.float64)

        if times_arr.shape != temps_arr.shape:
            raise ValueError("Times and temperatures must have the same length.")

        # Ensure sorted by time
        sorter = np.argsort(times_arr)
        self.times = times_arr[sorter]
        self.temperatures = temps_arr[sorter]
        self.NAME = name

    def get_temperature(
        self,
        time: float | npt.NDArray[np.float64],
        position: Optional[npt.NDArray[np.float64]] = None
    ) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature by linear interpolation.
        """
        t_array = np.atleast_1d(time)
        temps = np.interp(
            t_array, self.times, self.temperatures,
            left=293.15, right=293.15
        )

        if np.isscalar(time):
            return float(temps[0])
        return temps

# ==========================================
# ZONAL DEFINITION
# ==========================================

class Zone:
    """
    Defines a vertical zone in the tunnel (Height/Y-axis based).
    """

    def __init__(self, y_min: float = -np.inf, y_max: float = np.inf):
        """
        Args:
            y_min: Lower height bound.
            y_max: Upper height bound.
        """
        self.y_min = y_min
        self.y_max = y_max

    def contains(self, position: npt.NDArray[np.float64]) -> bool | npt.NDArray[np.bool_]:
        """
        Checks if position is within this height zone.
        Handles both single point (3,) and vectorized points (N, 3).
        Assumes Y is at index 1.
        """
        if position.ndim == 1:
            y = position[1]
        else:
            y = position[:, 1]

        return (y >= self.y_min) & (y <= self.y_max)


class ZonalFireCurve(FireCurve):
    """
    A composite fire curve that applies different curves based on the Y-coordinate.
    """
    NAME = "Zonal Fire Curve"
    CONVECTIVE_COEFFICIENT = 50.0  # W/m²K

    def __init__(self, zones: list[tuple[Zone, FireCurve]]):
        self.zones = zones

    def add_zone(self, zone: Zone, curve: FireCurve):
        self.zones.append((zone, curve))

    def get_temperature(
        self,
        time: float | npt.NDArray[np.float64],
        position: Optional[npt.NDArray[np.float64]] = None
    ) -> float | npt.NDArray[np.float64]:
        """
        Calculates temperature based on spatial zones.

        Note:
        - If position is None, returns default curve temperature.
        - If position is provided, checks zones based on Y-coord.
        """
        if position is None:
            # No position provided, raise error
            raise ValueError("Position must be provided for ZonalFireCurve.")

        # Case: scalar time, single position
        if np.isscalar(time) and position.ndim == 1:
            for zone, curve in self.zones:
                if zone.contains(position):
                    return curve.get_temperature(time, position)
            # If no zone matched, raise error
            raise ValueError("Position does not fall within any defined zone.")

        raise NotImplementedError("Vectorized time/position handling not implemented yet.")

if __name__ == "__main__":
    fire_curves = [
        ISO834FireCurve(),
        HCFireCurve(),
        HCMFireCurve(),
        RABTZTVTrainFireCurve(),
        RABTZTVCarFireCurve(),
        RWSFireCurve()
    ]

    for fire_curve in fire_curves:
        fire_curve.plot()
