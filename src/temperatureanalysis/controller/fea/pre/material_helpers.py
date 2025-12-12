# material_helpers.py
from __future__ import annotations

import numpy as np
import numpy.typing as npt
import numba as nb

def lininterp_scalar(u: float, xp: tuple[float, ...], fp: tuple[float, ...]) -> float:
    """
    Lightweight linear interpolation for a single scalar.

    Args:
        u:  Query value.
        xp: Monotone x breakpoints (e.g., (0.0, 1.5, 3.0, 10.0)).
        fp: Corresponding y values.

    Returns:
        Interpolated value at u, clamped to the end segments.
    """
    if u <= xp[0]:
        return fp[0]
    for i in range(len(xp) - 1):
        x0, x1 = xp[i], xp[i + 1]
        if u <= x1:
            t = (u - x0) / (x1 - x0)
            return (1.0 - t) * fp[i] + t * fp[i + 1]
    return fp[-1]

# ---- JIT’d concrete & steel material kernels (scalar + batched) ----

@nb.njit(cache=True, fastmath=True)
def concrete_k_lower(T_C: float) -> float:
    """Lower-bound thermal conductivity k(T) for concrete (°C → W/mK)."""
    if T_C <= 1200.0:
        x = T_C * 0.01
        return 1.36 - 0.136 * x + 0.0057 * (x * x)
    return 0.5488

@nb.njit(cache=True, fastmath=True)
def concrete_k_upper(T_C: float) -> float:
    """Upper-bound thermal conductivity k(T) for concrete (°C → W/mK)."""
    if T_C <= 1200.0:
        x = T_C * 0.01
        return 2.0 - 0.2451 * x + 0.0107 * (x * x)
    return 0.5996

@nb.njit(cache=True, fastmath=True)
def concrete_density(T_C: float, rho0: float) -> float:
    """Concrete density ρ(T) in kg/m³ (piecewise)."""
    if T_C <= 115.0:
        return rho0
    if T_C <= 200.0:
        return rho0 * (1.0 - 0.02 * (T_C - 115.0) / 85.0)
    if T_C <= 400.0:
        return rho0 * (0.98 - 0.03 * (T_C - 200.0) / 200.0)
    return rho0 * (0.95 - 0.07 * (T_C - 400.0) / 800.0)

@nb.njit(cache=True, fastmath=True)
def concrete_cp(T_C: float, d_bump: float) -> float:
    """
    Concrete specific heat capacity c_p(T) in J/(kg·K).

    Args:
        T_C: Temperature in °C.
        d_bump: Moisture-dependent bump (pre-interpolated, constant per material).
    """
    if T_C <= 100.0:
        return 900.0
    if T_C <= 115.0:
        return 900.0 + d_bump
    if T_C <= 200.0:
        return 900.0 + d_bump - ((900.0 + d_bump - 1000.0) / 85.0) * (T_C - 115.0)
    if T_C <= 400.0:
        return 1000.0 + 0.5 * (T_C - 200.0)
    return 1100.0

@nb.njit(cache=True, fastmath=True)
def steel_k(T_C: float) -> float:
    """Steel thermal conductivity k(T) in W/(m·K)."""
    if T_C <= 800.0:
        return 54.0 - 0.0333 * T_C  # 3.33*(T/100) = 0.0333*T
    return 27.3

@nb.njit(cache=True, fastmath=True)
def steel_cp(T_C: float) -> float:
    """Steel specific heat capacity c_p(T) in J/(kg·K)."""
    if T_C <= 600.0:
        return 425.0 + 0.773 * T_C - 0.00169 * (T_C * T_C) + 2.22e-6 * (T_C * T_C * T_C)
    elif T_C <= 735.0:
        return 666.0 - (13002.0 / (T_C - 738.0))
    elif T_C <= 900.0:
        return 545.0 + (17820.0 / (T_C - 731.0))
    else:
        return 650.0

@nb.njit(cache=True, fastmath=True)
def concrete_props_batch(
    T_K: npt.NDArray[np.float64],
    rho0: float,
    use_upper_k: bool,
    d_bump: float
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """
    Batched concrete properties.

    Args:
        T_K:          Temperatures in Kelvin, shape (n,).
        rho0:         Initial density of the material (kg/m³).
        use_upper_k:  If True, use upper-bound k(T); otherwise lower-bound.
        d_bump:       Moisture bump for c_p(T), constant per material.

    Returns:
        k:    Thermal conductivity per T (W/(m·K)), shape (n,).
        rhoc: Volumetric heat capacity ρc_p(T) (J/(m³·K)), shape (n,).
    """
    n = T_K.size
    k = np.empty(n, np.float64)
    rhoc = np.empty(n, np.float64)
    for i in range(n):
        T_C = T_K[i] - 273.15
        ki = concrete_k_upper(T_C) if use_upper_k else concrete_k_lower(T_C)
        rho = concrete_density(T_C, rho0)
        cp = concrete_cp(T_C, d_bump)
        k[i] = ki
        rhoc[i] = rho * cp
    return k, rhoc

@nb.njit(cache=True, fastmath=True)
def steel_props_batch(
    T_K: npt.NDArray[np.float64],
    rho0: float
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """
    Batched steel properties.

    Args:
        T_K:  Temperatures in Kelvin, shape (n,).
        rho0: Density in kg/m³ (assumed constant).

    Returns:
        k:    Thermal conductivity per T (W/(m·K)), shape (n,).
        rhoc: Volumetric heat capacity ρc_p(T) (J/(m³·K)), shape (n,).
    """
    n = T_K.size
    k = np.empty(n, np.float64)
    rhoc = np.empty(n, np.float64)
    for i in range(n):
        T_C = T_K[i] - 273.15
        ki = steel_k(T_C)
        cp = steel_cp(T_C)
        k[i] = ki
        rhoc[i] = rho0 * cp
    return k, rhoc


@nb.njit(cache=True, fastmath=True)
def generic_props_batch(
    T_K: npt.NDArray[np.float64],
    rho_xp: npt.NDArray[np.float64], rho_fp: npt.NDArray[np.float64],
    k_xp: npt.NDArray[np.float64], k_fp: npt.NDArray[np.float64],
    cp_xp: npt.NDArray[np.float64], cp_fp: npt.NDArray[np.float64]
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """
    Batched properties for generic tabulated material using linear interpolation.

    Returns:
        k:    Thermal conductivity per T (W/(m·K)), shape (n,).
        rhoc: Volumetric heat capacity ρc_p(T) (J/(m³·K)), shape (n,).
    """
    # Numba supports np.interp on arrays.
    # Note: Default behavior of np.interp matches the 'left'/'right' clamping
    # required (returns fp[0] or fp[-1] if out of bounds).

    k = np.interp(T_K, k_xp, k_fp)
    rho = np.interp(T_K, rho_xp, rho_fp)
    cp = np.interp(T_K, cp_xp, cp_fp)

    # Calculate volumetric heat capacity in-place (fused multiply)
    rhoc = rho * cp

    return k, rhoc
