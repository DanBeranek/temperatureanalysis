from __future__ import annotations

from typing import TYPE_CHECKING

from math import sqrt, pi
import numpy as np

if TYPE_CHECKING:
    from numpy import typing as npt

from temperatureanalysis.model.geometry_primitives import Point, Vector, Circle

def deg2rad(degrees: float) -> float:
    return degrees * pi / 180

def circle_to_polyline(
    circle: Circle,
    n_segments: int
) -> np.ndarray:
    """
    Discretize a circle in XY into an (N,2) polyline (closed).

    Args:
        circle: The Circle primitive object.
        n_segments: Number of segments to use for discretization.

    Returns:
        An array of shape (n, 2) containing the (x, y) coordinates of the points along the circle.
    """
    return ellipse_to_polyline(circle.center, circle.radius, circle.radius, n_segments)

def ellipse_to_polyline(
    center: Point,
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
    theta = np.linspace(0.0, 2.0 * np.pi, n_segments, endpoint=False)
    pts = np.c_[center.x + a * np.cos(theta), center.y + b * np.sin(theta)]

    # close the ring
    if not np.allclose(pts[0], pts[-1]):
        pts = np.vstack((pts, pts[0]))

    return pts


def line_circle_intersection(
    point: Point,
    vector: Vector,
    circle: Circle,
    *,
    as_segment: bool = False,
    eps: float = 1e-9
    ) -> list[Point]:
    """
    Compute intersection point(s) between a circle and a 2D line or line segment.

    The line is given in parametric form: P(t) = P0 + t * v, where
    P0 is a point on the line and v is the (nonzero) direction vector.
    If `as_segment=True`, the result is restricted to the segment from P0 to (P0 + v),
    i.e., only solutions with 0 <= t <= 1 are returned.

    Args:
        point: A point (x0, y0) on the line (or the start of the segment if `as_segment=True`).
        vector: The line direction vector (vx, vy). If its length is ~0, the function treats the
           "line" as the single point P0.
        circle: The circle with center (cx, cy), radius (must be non-negative).
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
    x0, y0 = point.x, point.y
    vx, vy = vector.x, vector.y
    cx, cy = circle.center.x, circle.center.y
    r = circle.radius
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
        return [Point(x=x0+t*vx, y=y0+t*vy)]

    sqrt_disc = sqrt(max(0.0, disc))
    t1 = (-b - sqrt_disc) / (2.0 * a)
    t2 = (-b + sqrt_disc) / (2.0 * a)

    ts = [t1, t2]
    if as_segment:
        ts = [t for t in ts if 0.0 - eps <= t <= 1.0 + eps]

    return [Point(x=x0+t*vx, y=y0+t*vy) for t in ts]


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

def line_intersection(p1: Point, p2: Point, p3: Point, p4: Point, eps=1e-12):
    """
    Intersection of two infinite 2D lines:
      L1 through p1->p2, L2 through p3->p4.
    Returns (x, y) if they intersect in a single point, otherwise None (parallel / coincident).

    Points are (x, y).
    """
    x1, y1 = p1.x, p1.y
    x2, y2 = p2.x, p2.y
    x3, y3 = p3.x, p3.y
    x4, y4 = p4.x, p4.y

    # Solve using cross products
    r = (x2 - x1, y2 - y1)
    s = (x4 - x3, y4 - y3)

    def cross(a, b):
        return a[0]*b[1] - a[1]*b[0]

    rxs = cross(r, s)
    q_p = (x3 - x1, y3 - y1)

    if abs(rxs) < eps:
        # parallel (including possibly collinear)
        return None

    t = cross(q_p, s) / rxs  # parameter on L1
    return x1 + t * r[0], y1 + t * r[1]
