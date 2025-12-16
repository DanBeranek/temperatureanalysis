"""Predefined Tunnel Profiles (Catalog) - Czech Standards."""
from typing import Dict, TypedDict, Optional, List
from enum import StrEnum
from dataclasses import dataclass, field

from temperatureanalysis.model.geometry_primitives import Point, Line, Arc, BoundaryLoop, GeometricEntity, Circle, Vector
from temperatureanalysis.model.geometry_utils import line_circle_intersection, deg2rad


# ------------------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------------------
class TunnelCategory(StrEnum):
    RAIL = "rail"
    ROAD = "road"

class OutlineShape(StrEnum):
    """Describes the geometric shape of a boundary line."""
    CIRCLE = "circle"
    THREE_CENTRE = "3-centre polycentric"
    FIVE_CENTRE = "5-centre polycentric"
    BOX = "box"
    D_SEGMENTAL = "d segmental"

class ProfileGroupKey(StrEnum):
    """Keys for the UI Dropdown Groups."""
    VL5_ROAD = "VL 5 - TUNELY (Silniční)"
    RAIL_SINGLE = "Jednokolejný tunel (Železniční)"
    RAIL_DOUBLE = "Dvoukolejný tunel (Železniční)"
    CUSTOM = "Vlastní definice"

class CustomTunnelShape(StrEnum):
    """High-level user selection tunnel shape."""
    CIRCLE = "Kruh"
    BOX = "Obdélník"

# ------------------------------------------------------------------------------
# Data Structures
# ------------------------------------------------------------------------------
@dataclass(frozen=True)
class TunnelOutline:
    """
    Defines ONE boundary (e.g. just the Inner/Outer boundary).
    """
    shape: OutlineShape

    # Generic container for dimensions.
    # Interpretation depends on shape:
    # - Circle: [radius]
    # - Box: [width, height]
    # - Polycentric: [R1, R2, ...]
    dimensions: list[float]
    center_first: list[float]
    floor_height: float
    angle: Optional[float] = None

    def get_primitives(
        self,
        offset: float = 0.0,
        max_distance_between_points: Optional[float] = None,
        assume_symmetric: bool = False
    ) -> List[GeometricEntity]:
        """
        Generate a list of Arcs/Lines for this specific boundary (CCW direction).
        Always results in an Open Arch (C-shape).
        """
        match self.shape:
            case OutlineShape.CIRCLE:
                return self._generate_arc(
                    offset=offset,
                    max_distance_between_points=max_distance_between_points,
                    assume_symmetric=assume_symmetric
                )
            case OutlineShape.THREE_CENTRE:
                return self._generate_three_centre(
                    offset=offset,
                    max_distance_between_points=max_distance_between_points,
                    assume_symmetric=assume_symmetric
                )
            case OutlineShape.FIVE_CENTRE:
                return self._generate_five_centre(
                    offset=offset,
                    max_distance_between_points=max_distance_between_points,
                    assume_symmetric=assume_symmetric
                )
            case OutlineShape.BOX:
                return self._generate_box(
                    offset=offset,
                    max_distance_between_points=max_distance_between_points,
                    assume_symmetric=assume_symmetric
                )
            case OutlineShape.D_SEGMENTAL:
                return self._generate_d_segments(
                    offset=offset,
                    max_distance_between_points=max_distance_between_points,
                    assume_symmetric=assume_symmetric
                )
            case _:
                return []

    def get_minimum_height(self) -> float:
        """Calculate the minimum height of the tunnel outline from floor to top."""
        primitives = self.get_primitives()
        points_y = [p.start.y for p in primitives] + [p.end.y for p in primitives]
        return min(points_y)

    def get_maximum_height(self) -> float:
        """Calculate the maximum height of the tunnel outline from floor to top."""
        primitives = self.get_primitives()
        points_y = [p.start.y for p in primitives] + [p.end.y for p in primitives]
        return max(points_y)

    def _generate_arc(
        self,
        offset: float,
        assume_symmetric: bool,
        max_distance_between_points: Optional[float] = None,
    ) -> List[Arc]:
        r = self.dimensions[0] + offset
        p_center = Point(self.center_first[0], self.center_first[1])
        circle = Circle(center=p_center, radius=r)
        floor_point = Point(0.0, self.floor_height)

        p_start = line_circle_intersection(
            point=floor_point,
            vector=Point(r, self.floor_height) - floor_point,
            circle=circle,
            as_segment=True
        )[0]

        p_end = line_circle_intersection(
            point=floor_point,
            vector=Point(-r, self.floor_height) - floor_point,
            circle=circle,
            as_segment=True
        )[0]


        p_top = p_center + Vector(0, r)

        primitives = Arc(p_start, p_center, p_top).divide(max_distance_between_points=max_distance_between_points)

        if not assume_symmetric:
            primitives.extend(Arc(p_top, p_center, p_end).divide(max_distance_between_points=max_distance_between_points))

        return primitives

    def _generate_three_centre(
        self,
        offset: float,
        assume_symmetric: bool,
        max_distance_between_points: Optional[float] = None,
    ) -> List[Arc]:
        floor_point = Point(0.0, self.floor_height)

        r1 = self.dimensions[0] + offset
        pc1 = Point(self.center_first[0], self.center_first[1])

        vector_1 = Vector(0, r1).rotate_z(-deg2rad(self.angle/2))
        vector_2 = Vector(0, r1).rotate_z(deg2rad(self.angle/2))

        p2 = pc1 + vector_1
        p3 = pc1 + Vector(0, r1)
        p4 = pc1 + vector_2

        r2 = self.dimensions[1] + offset
        pc2 = p2 - vector_1.normalize() * r2
        pc3 = p4 - vector_2.normalize() * r2

        circle2 = Circle(pc2, r2)
        circle3 = Circle(pc3, r2)

        p1 = line_circle_intersection(floor_point, Point(1000, self.floor_height) - floor_point, circle2, as_segment=True)[0]
        p5 = line_circle_intersection(floor_point, Point(-1000, self.floor_height) - floor_point, circle3, as_segment=True)[0]

        primitives = Arc(p1, pc2, p2).divide(max_distance_between_points=max_distance_between_points)
        primitives.extend(Arc(p2, pc1, p3).divide(max_distance_between_points=max_distance_between_points))


        if not assume_symmetric:
            primitives.extend(Arc(p3, pc1, p4).divide(max_distance_between_points=max_distance_between_points))
            primitives.extend(Arc(p4, pc3, p5).divide(max_distance_between_points=max_distance_between_points))

        return primitives

    def _generate_five_centre(
        self,
        offset: float,
        assume_symmetric: bool,
        max_distance_between_points: Optional[float] = None,
    ) -> List[Arc]:
        floor_point = Point(0.0, self.floor_height)

        r1 = self.dimensions[0] + offset
        pc1 = Point(self.center_first[0], self.center_first[1])

        vector_1 = Vector(0, r1).rotate_z(-deg2rad(self.angle / 2))
        vector_2 = Vector(0, r1).rotate_z(deg2rad(self.angle / 2))

        p3 = pc1 + vector_1
        p4 = pc1 + Vector(0, r1)
        p5 = pc1 + vector_2

        r2 = self.dimensions[1] + offset
        pc2 = p3 - vector_1.normalize()*r2
        pc3 = p5 - vector_2.normalize()*r2

        p2 = pc2 + Vector(r2, 0)
        p6 = pc3 - Vector(r2, 0)

        r3 = p6.distance_to(p2)

        circle2 = Circle(p6, r3)
        circle3 = Circle(p2, r3)

        p1 = line_circle_intersection(floor_point, Point(1000, self.floor_height) - floor_point, circle2, as_segment=True)[0]
        p7 = line_circle_intersection(floor_point, Point(-1000, self.floor_height) - floor_point, circle3, as_segment=True)[0]

        primitives = Arc(p1, p6, p2).divide(max_distance_between_points=max_distance_between_points)
        primitives.extend(Arc(p2, pc2, p3).divide(max_distance_between_points=max_distance_between_points))
        primitives.extend(Arc(p3, pc1, p4).divide(max_distance_between_points=max_distance_between_points))

        if not assume_symmetric:
            primitives.extend(Arc(p4, pc1, p5).divide(max_distance_between_points=max_distance_between_points))
            primitives.extend(Arc(p5, pc3, p6).divide(max_distance_between_points=max_distance_between_points))
            primitives.extend(Arc(p6, p2, p7).divide(max_distance_between_points=max_distance_between_points))

        return primitives

    def _generate_box(
        self,
        offset: float,
        assume_symmetric: bool,
        max_distance_between_points: Optional[float] = None,
    ) -> List[Line]:
        half_w = self.dimensions[0] / 2 + offset
        height = self.dimensions[1] + offset

        p1 = Point(half_w, 0.0)
        p2 = Point(half_w, height)
        p_top = Point(0.0, height)
        p3 = Point(-half_w, height)
        p4 = Point(-half_w, 0.0)

        primitives = Line(p1, p2).divide(max_distance_between_points=max_distance_between_points)
        primitives.extend(Line(p2, p_top).divide(max_distance_between_points=max_distance_between_points))

        if not assume_symmetric:
            primitives.extend(Line(p_top, p3).divide(max_distance_between_points=max_distance_between_points))
            primitives.extend(Line(p3, p4).divide(max_distance_between_points=max_distance_between_points))

        return primitives

    def _generate_d_segments(
        self,
        offset: float,
        assume_symmetric: bool,
        max_distance_between_points: Optional[float] = None,
    ) -> List[GeometricEntity]:
        y = self.floor_height

        r1 = self.dimensions[0] + offset

        cx, cy = self.center_first

        pc = Point(cx, cy)
        p1 = Point(r1, y)
        p2 = Point(r1, cy)
        p3 = Point(0.0, cy+r1)
        p4 = Point(-r1, cy)
        p5 = Point(-r1, y)

        primitives: list[GeometricEntity] = Line(p1, p2).divide(max_distance_between_points=max_distance_between_points)
        primitives.extend(Arc(p2, pc, p3).divide(max_distance_between_points=max_distance_between_points))

        if not assume_symmetric:
            primitives.extend(Arc(p3, pc, p4).divide(max_distance_between_points=max_distance_between_points))
            primitives.extend(Line(p4, p5).divide(max_distance_between_points=max_distance_between_points))

        return primitives

@dataclass(frozen=True)
class TunnelProfile:
    category: TunnelCategory
    description: str
    inner: TunnelOutline
    outer: Optional[TunnelOutline] = None
    rebar_thermocouples: Optional[TunnelOutline] = None
    y_bounds: Optional[List[float]] = None

    def __post_init__(self):
        if self.y_bounds is None:
            min_height = self.inner.get_minimum_height()
            max_height = self.inner.get_maximum_height()
            object.__setattr__(self, 'y_bounds', [min_height, max_height])

    def get_combined_loop(
        self,
        user_thickness: float,
        rebar_depth: float,
        assume_symmetric: bool,
        max_distance_between_points: Optional[float] = None,
    ) -> BoundaryLoop:
        """
        Generate a SINGLE closed C-shape loop defining the concrete domain.
        Sequence: Outer Arcs (CCW) -> Floor Line -> Inner Arcs (CW) -> Close.
        """
        loop = BoundaryLoop()

        # 1. Generate Outer Primitives (CCW)
        if self.outer:
            outer_ents = self.outer.get_primitives(
                offset=user_thickness,
                assume_symmetric=assume_symmetric,
            )
        else:
            outer_ents = self.inner.get_primitives(
                offset=user_thickness,
                assume_symmetric=assume_symmetric
            )

        for e in outer_ents: e.label = "outer"

        # 2. Generate Inner Primitives (CCW)
        inner_ents_ccw = self.inner.get_primitives(
            assume_symmetric=assume_symmetric,
            max_distance_between_points=max_distance_between_points
        )

        if not outer_ents or not inner_ents_ccw:
            return loop

        # 3. Reverse Inner to be CW
        inner_ents_cw = []
        for e in reversed(inner_ents_ccw):
            rev_e = e.reverse()
            rev_e.label = "inner"
            inner_ents_cw.append(rev_e)

        # 4. Stitch boundaries together
        # A. Add outer boundary (Right -> Top -> Left)
        loop.add_entities(outer_ents)

        # B. Connect Left Floor: Outer End -> Inner Start
        # Note: Outer End is Left Floor Outer. Inner Start (CW) is Left Floor Inner.
        # Add a Point in the position of the thermocouple in rebar
        start = outer_ents[-1].end
        end = inner_ents_cw[0].start

        if assume_symmetric:
            vec = Vector(0, rebar_depth)
        else:
            vec = Vector(-rebar_depth, 0)
        middle = end + vec

        loop.add_entities(
            [
                Line(
                    start=start,
                    end=middle,
                    label="outer"
                ),
                Line(
                    start=middle,
                    end=end,
                    label="outer"
                ),
            ]
        )

        # C. Add Inner Boundary (Left Floor -> Top -> Right Floor)
        loop.add_entities(inner_ents_cw)

        # D. Connect Right Floor
        # Add a Point in the position of the thermocouple in rebar
        start = inner_ents_cw[-1].end
        vec = Vector(rebar_depth, 0)
        middle = start + vec
        end = outer_ents[0].start
        loop.add_entities(
            [
                Line(
                    start=start,
                    end=middle,
                    label="outer"
                ),
                Line(
                    start=middle,
                    end=end,
                    label="outer"
                ),
            ]
        )

        return loop

    def get_rebar_primitives(self, rebar_depth: float, assume_symmetric: bool) -> Optional[List[GeometricEntity]]:
        """
        Generate a list of Arcs/Lines for the rebar thermocouple boundary (CCW direction).
        Always results in an Open Arch (C-shape).
        """

        return self.inner.get_primitives(offset=rebar_depth, assume_symmetric=assume_symmetric)

    def get_rebar_points(self, rebar_depth: float, assume_symmetric: bool, max_length: float) -> Optional[List[Point]]:
        """
        Generate a list of Points for the rebar thermocouple locations.
        Always results in an Open Arch (C-shape).
        """

        primitives = self.get_rebar_primitives(rebar_depth=rebar_depth, assume_symmetric=assume_symmetric)
        if not primitives:
            return None
        divided_primitives = []
        for prim in primitives:
            divided_primitives.extend(prim.divide(max_distance_between_points=max_length))

        points = []
        for prim in divided_primitives:
            points.append(prim.start)
        # Add the last point
        points.append(divided_primitives[-1].end)
        return points

# 1. Flat Dictionary for Lookup (Used by Renderer)
RAIL_SINGLE_PROFILES: Dict[str, TunnelProfile] = {
    "Jednokolejný tunel - Konvenční ražba (do 160 km/h)": TunnelProfile(
        category=TunnelCategory.RAIL,
        description="Jednokolejný tunel - Konvenční ražba (do 160 km/h)",
        inner=TunnelOutline(
            shape=OutlineShape.THREE_CENTRE,
            dimensions=[3.7, 5.15],
            center_first=[0.0, 3.1],
            floor_height=-0.15,
            angle=100.0,
        ),
        outer=TunnelOutline(
            shape=OutlineShape.FIVE_CENTRE,
            dimensions=[3.7, 5.15],
            center_first=[0.0, 3.1],
            floor_height=-0.15,
            angle=100.0,
        )
    ),
    "Jednokolejný tunel - Konvenční ražba (od 161 km/h do 230 km/h)": TunnelProfile(
        category=TunnelCategory.RAIL,
        description="Jednokolejný tunel - Konvenční ražba (od 161 km/h do 230 km/h)",
        inner=TunnelOutline(
            shape=OutlineShape.THREE_CENTRE,
            dimensions=[3.9, 5.45],
            center_first=[0.0, 3.25],
            floor_height=-0.15,
            angle=100.0,
        ),
        outer=TunnelOutline(
            shape=OutlineShape.FIVE_CENTRE,
            dimensions=[3.9, 5.45],
            center_first=[0.0, 3.25],
            floor_height=-0.15,
            angle=100.0,
        )
    ),
    "Jednokolejný tunel - Konvenční ražba (od 231 km/h do 300 km/h)": TunnelProfile(
        category=TunnelCategory.RAIL,
        description="Jednokolejný tunel - Konvenční ražba (od 231 km/h do 300 km/h)",
        inner=TunnelOutline(
            shape=OutlineShape.THREE_CENTRE,
            dimensions=[4.2, 5.75],
            center_first=[0.0, 3.5],
            floor_height=-0.15,
            angle=100.0,
        ),
        outer=TunnelOutline(
            shape=OutlineShape.FIVE_CENTRE,
            dimensions=[4.2, 5.75],
            center_first=[0.0, 3.5],
            floor_height=-0.15,
            angle=100.0,
        )
    ),
    "Jednokolejný tunel - Mechanizovaná ražba (do 160 km/h)": TunnelProfile(
        category=TunnelCategory.RAIL,
        description="Jednokolejný tunel - Mechanizovaná ražba (do 160 km/h)",
        inner=TunnelOutline(
            shape=OutlineShape.CIRCLE,
            dimensions=[4.35],
            center_first=[0.0, 2.4],
            floor_height=-0.15,
        ),
    ),
    "Jednokolejný tunel - Mechanizovaná ražba (od 161 km/h do 230 km/h)": TunnelProfile(
        category=TunnelCategory.RAIL,
        description="Jednokolejný tunel - Mechanizovaná ražba (od 161 km/h do 230 km/h)",
        inner=TunnelOutline(
            shape=OutlineShape.CIRCLE,
            dimensions=[4.45],
            center_first=[0.0, 2.55],
            floor_height=-0.15,
        ),
    ),
    "Jednokolejný tunel - Mechanizovaná ražba (od 231 km/h do 300 km/h)": TunnelProfile(
        category=TunnelCategory.RAIL,
        description="Jednokolejný tunel - Mechanizovaná ražba (od 231 km/h do 300 km/h)",
        inner=TunnelOutline(
            shape=OutlineShape.CIRCLE,
            dimensions=[4.7],
            center_first=[0.0, 2.9],
            floor_height=-0.15,
        ),
    ),
}

RAIL_DOUBLE_PROFILES: Dict[str, TunnelProfile] = {
    "Dvoukolejný tunel - Konvenční ražba (do 160 km/h)": TunnelProfile(
        category=TunnelCategory.RAIL,
        description="Dvoukolejný tunel - Konvenční ražba (do 160 km/h)",
        inner=TunnelOutline(
            shape=OutlineShape.CIRCLE,
            dimensions=[5.85],
            center_first=[0.0, 1.75],
            floor_height=-0.15,
        ),
        outer=TunnelOutline(
            shape=OutlineShape.FIVE_CENTRE,
            dimensions=[5.85, 5.85],
            center_first=[0.0, 1.75],
            floor_height=-0.15,
            angle=90,
        )
    ),
    "Dvoukolejný tunel - Konvenční ražba (od 161 km/h do 230 km/h)": TunnelProfile(
        category=TunnelCategory.RAIL,
        description="Dvoukolejný tunel - Konvenční ražba (od 161 km/h do 230 km/h)",
        inner=TunnelOutline(
            shape=OutlineShape.THREE_CENTRE,
            dimensions=[6.2, 5.8],
            center_first=[0.0, 1.55],
            floor_height=-0.15,
            angle=100.0,
        ),
        outer=TunnelOutline(
            shape=OutlineShape.FIVE_CENTRE,
            dimensions=[6.2, 5.8],
            center_first=[0.0, 1.55],
            floor_height=-0.15,
            angle=100.0,
        )
    ),
    "Dvoukolejný tunel - Konvenční ražba (od 231 km/h do 300 km/h)": TunnelProfile(
        category=TunnelCategory.RAIL,
        description="Dvoukolejný tunel - Konvenční ražba (od 231 km/h do 300 km/h)",
        inner=TunnelOutline(
            shape=OutlineShape.THREE_CENTRE,
            dimensions=[6.75, 5.9],
            center_first=[0.0, 1.4],
            floor_height=-0.15,
            angle=140.0,
        ),
        outer=TunnelOutline(
            shape=OutlineShape.FIVE_CENTRE,
            dimensions=[6.75, 5.9],
            center_first=[0.0, 1.4],
            floor_height=-0.15,
            angle=140.0,
        )
    ),
}

ROAD_PROFILES: Dict[str, TunnelProfile] = {
    "Tunel T-7,5, ražený": TunnelProfile(
        category=TunnelCategory.ROAD,
        description="Tunel T-7,5, ražený",
        inner=TunnelOutline(
            shape=OutlineShape.CIRCLE,
            dimensions=[5.1],
            center_first=[0.0, 1.8],
            floor_height=0.0,
            angle=120.0,
        ),
        outer=TunnelOutline(
            shape=OutlineShape.THREE_CENTRE,
            dimensions=[5.1, 6.25],
            center_first=[0.0, 1.8],
            floor_height=0.0,
            angle=120.0,
        )
    ),
    "Tunel T-8,0, ražený": TunnelProfile(
        category=TunnelCategory.ROAD,
        description="Tunel T-8,0, ražený",
        inner=TunnelOutline(
            shape=OutlineShape.CIRCLE,
            dimensions=[5.3],
            center_first=[0.0, 1.6],
            floor_height=0.0,
        ),
        outer=TunnelOutline(
            shape=OutlineShape.THREE_CENTRE,
            dimensions=[5.3, 7.15],
            center_first=[0.0, 1.6],
            floor_height=0.0,
            angle=140.0,
        )
    ),
    "Tunel T-9,0, ražený": TunnelProfile(
        category=TunnelCategory.ROAD,
        description="Tunel T-9,0, ražený",
        inner=TunnelOutline(
            shape=OutlineShape.THREE_CENTRE,
            dimensions=[6.25, 4.75],
            center_first=[0.0, 0.65],
            floor_height=0.0,
            angle=100.0
        ),
        outer=TunnelOutline(
            shape=OutlineShape.THREE_CENTRE,
            dimensions=[6.25, 5.65],
            center_first=[0.0, 0.65],
            floor_height=0.0,
            angle=100.0
        )
    ),
    "Tunel T-9,5, ražený": TunnelProfile(
        category=TunnelCategory.ROAD,
        description="Tunel T-9,5, ražený",
        inner=TunnelOutline(
            shape=OutlineShape.THREE_CENTRE,
            dimensions=[6.75, 4.4],
            center_first=[0.0, 0.15],
            floor_height=0.0,
            angle=100.0
        ),
        outer=TunnelOutline(
            shape=OutlineShape.THREE_CENTRE,
            dimensions=[6.75, 5.15],
            center_first=[0.0, 0.15],
            floor_height=0.0,
            angle=100.0
        )
    ),
    "Tunel T-8,0, hloubený": TunnelProfile(
        category=TunnelCategory.ROAD,
        description="Tunel T-8,0, hloubený",
        inner=TunnelOutline(
            shape=OutlineShape.CIRCLE,
            dimensions=[5.3],
            center_first=[0.0, 1.6],
            floor_height=0.0,
        ),
        outer=TunnelOutline(
            shape=OutlineShape.D_SEGMENTAL,
            dimensions=[5.3],
            center_first=[0.0, 1.6],
            floor_height=0.0,
        )
    ),
}

ALL_PROFILES: dict[str, TunnelProfile] = {
    **RAIL_SINGLE_PROFILES,
    **RAIL_DOUBLE_PROFILES,
    **ROAD_PROFILES
}

PROFILE_GROUPS: dict[str, list[str]] = {
    ProfileGroupKey.VL5_ROAD: list(ROAD_PROFILES.keys()),
    ProfileGroupKey.RAIL_SINGLE: list(RAIL_SINGLE_PROFILES.keys()),
    ProfileGroupKey.RAIL_DOUBLE: list(RAIL_DOUBLE_PROFILES.keys()),
}
