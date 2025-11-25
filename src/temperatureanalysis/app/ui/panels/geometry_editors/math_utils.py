from __future__ import annotations

from math import sqrt

import numpy as np
from numpy import typing as npt


def circle_to_polyline(
    center: tuple[float, float],
    radius: float,
    n_segments: int
) -> np.ndarray:
    """
    Discretize a circle in XY into an (N,2) polyline (closed).

    Args:
        center: (x, y) coordinates of the circle center.
        radius: Radius of the circle.
        n_segments: Number of segments to use for discretization.

    Returns:
        An array of shape (n, 2) containing the (x, y) coordinates of the points along the circle.
    """
    return ellipse_to_polyline(center, radius, radius, n_segments)

def ellipse_to_polyline(
    center: tuple[float, float],
    a: float,
    b: float,
    n_segments: int
) -> np.ndarray:
    """
    Discretize an ellipse in XY into an (N,2) polyline (closed).

    Args:
        center: (x, y) coordinates of the ellipse center.
        a: Semi-major axis length.
        b: Semi-minor axis length.
        n_segments: Number of segments to use for discretization.

    Returns:
        An array of shape (n, 2) containing the (x, y) coordinates of the points along the ellipse.
    """
    cx, cy = center
    theta = np.linspace(0.0, 2.0 * np.pi, n_segments, endpoint=False)
    pts = np.c_[cx + a * np.cos(theta), cy + b * np.sin(theta)]

    # close the ring
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack((pts, pts[0]))

    return pts


def line_circle_intersection(
    P0: tuple[float, float],
    v: tuple[float, float],
    C: tuple[float, float],
    r: float,
    *,
    as_segment: bool = False,
    eps: float = 1e-9
    ) -> list[tuple[float, float]]:
    """
    Compute intersection point(s) between a circle and a 2D line or line segment.

    The line is given in parametric form: P(t) = P0 + t * v, where
    P0 is a point on the line and v is the (nonzero) direction vector.
    If `as_segment=True`, the result is restricted to the segment from P0 to (P0 + v),
    i.e., only solutions with 0 <= t <= 1 are returned.

    Args:
        P0: A point (x0, y0) on the line (or the start of the segment if `as_segment=True`).
        v: The line direction vector (vx, vy). If its length is ~0, the function treats the
           "line" as the single point P0.
        C: The circle center (cx, cy).
        r: The circle radius (must be non-negative).
        as_segment: If True, return only intersections whose parameter t lies in [0, 1] (within `eps`).
                    Default is False (infinite line).
        eps: Numerical tolerance for zero checks and inclusive interval tests. Default 1e-9.

    Returns:
        A list containing 0, 1, or 2 intersection points. For tangency (discriminant ~ 0),
        a single point is returned.

    Notes:
        - Solves ||P0 + t*v - C||^2 = r^2, yielding a quadratic a t^2 + b t + c = 0 where:
          a = v·v
          b = 2 v·(P0 - C)
          c = ||P0 - C||^2 - r^2
    - If `a` ~ 0, the direction is degenerate; in that case it returns [P0] if P0 lies
      on the circle (within `eps`), otherwise [].
    """
    x0, y0 = P0
    vx, vy = v
    cx, cy = C
    a = vx * vx + vy * vy

    # degenerate direction: treat as point-circle intersection
    if abs(a) < eps:
        on_circle = abs((x0 - cx) ** 2 + (y0 - cy) ** 2 - r ** 2) <= eps
        return [(x0, y0)] if on_circle else []

    b = 2.0 * (vx * (x0 - cx) + vy * (y0 - cy))
    c = (x0 - cx) ** 2 + (y0 - cy) ** 2 - r * r
    disc = b * b - 4.0 * a * c

    # No real intersection
    if disc < -eps:
        return []

    # One or two intersection
    if abs(disc) <= eps:
        t = -b / (2.0 * a)

        if as_segment and not (0.0 - eps <= t <= 1.0 + eps):
            return []
        return [(x0 + t * vx, y0 + t * vy)]

    sqrt_disc = sqrt(max(0.0, disc))
    t1 = (-b - sqrt_disc) / (2.0 * a)
    t2 = (-b + sqrt_disc) / (2.0 * a)

    ts = [t1, t2]
    if as_segment:
        ts = [t for t in ts if 0.0 - eps <= t <= 1.0 + eps]

    return [(x0 + t * vx, y0 + t * vy) for t in ts]


def arc_points(
    C: tuple[float, float],
    r: float,
    A: tuple[float, float],
    B: tuple[float, float],
    *,
    clockwise: bool = False,
    n_points: int = 100
    ) -> npt.NDArray[np.float64]:
    """
    Generate points along a circular arc from point A to point B around center C.

    Args:
        C: Circle center (cx, cy).
        r: Circle radius (must be positive).
        A: Start point (ax, ay) on the circle.
        B: End point (bx, by) on the circle.
        clockwise: If True, generate the arc in clockwise direction; otherwise counter-clockwise.
        n_points: Number of points to generate along the arc (including endpoints).

    Returns:
        Array of shape (n_points, 2) containing the (x, y) coordinates of the points along the arc.
    """
    cx, cy = C
    ax, ay = A
    bx, by = B

    # Angles of A and B with respect to center C
    theta_a = np.arctan2(ay - cy, ax - cx)
    theta_b = np.arctan2(by - cy, bx - cx)

    if clockwise:
        if theta_b > theta_a:
            theta_b -= 2 * np.pi
    else:
        if theta_b < theta_a:
            theta_b += 2 * np.pi

    # Generate angles
    angles = np.linspace(theta_a, theta_b, n_points)

    x = cx + r * np.cos(angles)
    y = cy + r * np.sin(angles)

    return np.column_stack((x, y))
