from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np
import matplotlib.pyplot as plt

if TYPE_CHECKING:
    import numpy.typing as npt


class FireCurve(ABC):
    """
    Abstract base class for fire curves.
    """
    NAME: str = "Fire Curve"

    @abstractmethod
    def get_temperature(self, time: float | npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature at a given time.

        Args:
            time: Time in seconds.

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


class ISO834FireCurve(FireCurve):
    """
    ISO 834 fire curve implementation.
    """
    NAME = "ISO 834, Cellulosic"

    def get_temperature(self, time: float | npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature according to the ISO 834 fire curve.

        Args:
            time: Time in seconds.

        Returns:
            Temperature in K at time t.
        """
        return 273.15 + 20 + 345 * np.log10(8 * (time/60) + 1)


class HCFireCurve(FireCurve):
    """
    HydroCarbon fire curve implementation.
    """
    NAME = "HydroCarbon"

    def get_temperature(self, time: float | npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature according to the HydroCarbon fire curve.

        Args:
            time: Time in seconds.

        Returns:
            Temperature in K at time t.
        """
        return 273.15 + 20 + 1080 * (1 - 0.325 * np.exp(-0.167 * (time / 60)) - 0.675 * np.exp(-2.5 * (time / 60)))

class HCMFireCurve(FireCurve):
    """
    Modified HydroCarbon fire curve implementation according to ISO 834.
    """
    NAME = "Modified HydroCarbon"

    def get_temperature(self, time: float | npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature according to the HCM fire curve.

        Args:
            time: Time in seconds.

        Returns:
            Temperature in K at time t.
        """
        return 273.15 + 20 + 1280 * (1 - 0.325 * np.exp(-0.167 * (time / 60)) - 0.675 * np.exp(-2.5 * (time / 60)))

class RABTZTVTrainFireCurve(FireCurve):
    """
    RABT-ZTV (train) fire curve implementation.
    """
    NAME = "RABT-ZTV (train)"

    TIMES = np.array([0.0, 5.0, 60.0, 170.0]) * 60.0  # Convert minutes to seconds

    TEMPERATURES = 273.15 + np.array([15.0, 1200.0, 1200.0, 15.0])  # Temperatures in Kelvin

    def get_temperature(self, time: float | npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature according to the RABT-ZTV (train) fire curve.

        Args:
            time: Time in seconds.

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

    TIMES = np.array([0.0, 5.0, 30.0, 140.0]) * 60.0  # Convert minutes to seconds

    TEMPERATURES = 273.15 + np.array([15.0, 1200.0, 1200.0, 15.0])  # Temperatures in Kelvin

    def get_temperature(self, time: float | npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature according to the RABT-ZTV (train) fire curve.

        Args:
            time: Time in seconds.

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

    TIMES = np.array([0.0, 3.0, 5.0, 10.0, 30.0, 60.0, 90.0, 120.0, 180.0]) * 60.0  # Convert minutes to seconds

    TEMPERATURES = 273.15 + np.array([20.0, 890.0, 1140.0, 1200.0, 1300.0, 1350.0, 1300.0, 1200.0, 1200.0])  # Temperatures in Kelvin

    def get_temperature(self, time: float | npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
        """
        Get the temperature according to the RWS (Rijkswaterstaat)) fire curve.

        Args:
            time: Time in seconds.

        Returns:
            Temperature in Kelvin.
        """
        t_array = np.atleast_1d(time)

        temperatures = np.interp(t_array, self.TIMES, self.TEMPERATURES)

        if np.isscalar(time):
            return float(temperatures[0])
        return temperatures


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
