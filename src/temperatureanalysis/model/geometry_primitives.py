"""
Geometric Primitives for Gmsh and File I/O.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Union, TYPE_CHECKING
import numpy as np
import math

if TYPE_CHECKING:
    import numpy.typing as npt

@dataclass
class Vector:
    """
    A vector in 3D space representing direction and magnitude.
    """
    x: float
    y: float
    z: float = 0.0

    def __add__(self, other: Vector) -> Vector:
        return Vector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vector) -> Vector:
        return Vector(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> Vector:
        return Vector(self.x * scalar, self.y * scalar, self.z * scalar)

    def __truediv__(self, scalar: float) -> Vector:
        if scalar == 0.0: raise ZeroDivisionError
        return Vector(self.x / scalar, self.y / scalar, self.z / scalar)

    def __neg__(self) -> Vector:
        return Vector(-self.x, -self.y, -self.z)

    @property
    def magnitude(self) -> float:
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalize(self) -> Vector:
        mag = self.magnitude
        if mag == 0.0: return Vector(0.0, 0.0, 0.0)
        return self / mag

    def dot(self, other: Vector) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vector) -> Vector:
        return Vector(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x
        )

    def rotate_z(self, angle_rad: float) -> Vector:
        """Rotate vector around Z axis."""
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return Vector(
            self.x * cos_a - self.y * sin_a,
            self.x * sin_a + self.y * cos_a,
            self.z
        )

    def to_array(self) -> npt.NDArray[np.float64]:
        return np.array([self.x, self.y, self.z])

    def angle_to(self, other: Vector) -> float:
        """Returns the angle in radians between this vector and another."""
        return math.atan2(self.cross(other).magnitude, self.dot(other))


@dataclass
class Point:
    """A simple geometric point in 3D space."""
    x: float
    y: float
    z: float = 0.0
    lc: float = 0.5  # Mesh characteristic length at this point
    id: Optional[int] = None  # Assigned later by Gmsh

    def __add__(self, other: Union[Vector, Point]) -> Point:
        # Point + Vector = Point (Translation)
        if isinstance(other, Vector):
            return Point(self.x + other.x, self.y + other.y, self.z + other.z)
        raise TypeError("Can only add a Vector to a Point.")

    def __sub__(self, other: Union[Vector, Point]) -> Union[Vector, Point]:
        # Point - Point = Vector (Direction)
        if isinstance(other, Point):
            return Vector(self.x - other.x, self.y - other.y, self.z - other.z)
        # Point - Vector = Point (Inverse translation)
        if isinstance(other, Vector):
            return Point(self.x - other.x, self.y - other.y, self.z - other.z, self.lc)
        raise TypeError("Can only subtract a Vector or Point to a Point.")

    def distance_to(self, other: Point) -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2)

    def to_array(self) -> npt.NDArray[np.float64]:
        return np.array([self.x, self.y, self.z])

@dataclass
class Line:
    """A straight line between two points."""
    start: Point
    end: Point
    id: Optional[int] = None  # Assigned later by Gmsh
    label: Optional[str] = None
    lc: Optional[float] = None  # Override mesh size for this line

    def reverse(self) -> Line:
        return Line(start=self.end, end=self.start)

    def discretize(self, max_length: Optional[float] = None) -> npt.NDArray[np.float64]:
        if max_length is None:
            return np.array([self.start.to_array(), self.end.to_array()])

        resolution = max(2, math.ceil((self.length / max_length) / 2) * 2)  # Ensure at least 2 points and even number
        return np.linspace(self.start.to_array(), self.end.to_array(), resolution)

    def divide(
        self,
        max_distance_between_points: Optional[float] = None
    ) -> list[Line]:
        """Divides the line into smaller lines based on max distance between points."""
        if max_distance_between_points is None:
            return [self]

        points = self.discretize(max_length=max_distance_between_points)
        lines = []
        for p1, p2 in zip(points[:-1], points[1:]):
            line = Line(
                start=Point(x=p1[0], y=p1[1], z=p1[2]),
                end=Point(x=p2[0], y=p2[1], z=p2[2]),
                lc=self.lc,
                label=self.label
            )
            lines.append(line)
        return lines

    def to_vector(self) -> Vector:
        return self.end - self.start

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)

@dataclass
class Circle:
    """
    Mathematical helper for intersection calculations.
    Not a renderable entity in the BoundaryLoop.
    """
    center: Point
    radius: float

@dataclass
class Arc:
    """A circular arc defined by start, center and end."""
    start: Point
    center: Point
    end: Point
    id: Optional[int] = None  # Assigned later by Gmsh
    label: Optional[str] = None
    lc: Optional[float] = None  # Override mesh size for this line

    def reverse(self) -> Arc:
        return Arc(center=self.center, start=self.end, end=self.start)

    @property
    def radius(self) -> float:
        return (self.start - self.center).magnitude

    def discretize(self, max_length: Optional[float] = None) -> npt.NDArray[np.float64]:
        """
        Generates points along the arc from `start` to `end` via `center`.
        Handles the 'shortest path' logic standard in CAD kernels.
        """
        if max_length is not None:
            resolution = self._get_number_of_segments(max_length=max_length)
        else:
            resolution = 100

        p_s = self.start.to_array()
        p_e = self.end.to_array()
        p_c = self.center.to_array()

        # Vectors from center
        v_s = p_s - p_c
        v_e = p_e - p_c

        radius = np.linalg.norm(v_s)

        # Angles in global frame (-pi, pi)
        ang_s = np.arctan2(v_s[1], v_s[0])
        ang_e = np.arctan2(v_e[1], v_e[0])

        # Calculate angular difference
        diff = ang_e - ang_s

        # Normalize diff to (-pi, pi) for shortest path logic
        # Iff diff > pi, we should go the other way (subtract 2pi)
        # Iff diff < -pi, add 2pi
        while diff <= -np.pi:
            diff += 2 * np.pi
        while diff > np.pi:
            diff -= 2 * np.pi

        angles = np.linspace(ang_s, ang_s + diff, resolution)

        x = p_c[0] + radius * np.cos(angles)
        y = p_c[1] + radius * np.sin(angles)
        z = np.zeros_like(x)

        return np.array([x, y, z]).T

    def divide(
        self,
        max_distance_between_points: Optional[float] = None
    ) -> list[Arc]:
        """Divides the arc into smaller arcs based on max distance between points."""
        if max_distance_between_points is None:
            return [self]

        points = self.discretize(max_length=max_distance_between_points)
        arcs = []
        for p1, p2 in zip(points[:-1], points[1:]):
            arc = Arc(
                start=Point(x=p1[0], y=p1[1], z=p1[2]),
                center=self.center,
                end=Point(x=p2[0], y=p2[1], z=p2[2]),
                lc=self.lc,
                label=self.label
            )
            arcs.append(arc)
        return arcs



    def _get_number_of_segments(self, max_length: float) -> int:
        """Helper to calculate number of segments based on max distance."""
        vec_start = self.start - self.center
        vec_end = self.end - self.center
        angle_rad = vec_start.angle_to(vec_end)

        length = 2 * math.pi * self.radius / (2 * math.pi) * abs(angle_rad)
        return max(2, math.ceil((length / max_length) / 2) * 2)  # Ensure at least 2 points and even number

# Union type for list handling
GeometricEntity = Union[Line, Arc]

@dataclass
class BoundaryLoop:
    """
    A single closed loop defining the solid domain.
    For a tunnel, this includes Outer Arcs + Bottom Line + Inner Arcs + Bottom Line.
    """
    entities: List[GeometricEntity] = field(default_factory=list)

    def add_entities(self, new_entities: List[GeometricEntity]) -> None:
        self.entities.extend(new_entities)

    def close_loop(self) -> None:
        """
        Automatically adds a line from the last point back to the first point
        if they are not coincident.
        """
        if not self.entities:
            return

        first_point = self.entities[0].start
        last_point = self.entities[-1].end


        if first_point.distance_to(last_point) > 1e-6:
            self.entities.append(Line(start=first_point, end=last_point))

    # def get_discrete_points(self, step_degree: float = 2.0) -> npt.NDArray[np.float64]:
    #     """
    #     Helper to convert primitives back to dense points for PyVista visualization.
    #     """
    #     points = []
    #     for entity in self.entities:
    #         if isinstance(entity, Line):
    #             points.append(entity.start.to_array())
    #             # Note: We don't add end point here to avoid duplicates,
    #             # except for the very last segment in the loop logic.
    #         if isinstance(entity, Arc):
    #             # Discretize Arc
    #             p_start = entity.start.to_array()
    #             p_end = entity.end.to_array()
    #             p_center = entity.center.to_array()
    #
    #             # Vector calculations to find angles...
    #             pass # TODO
    #
    #     return np.array(points)
