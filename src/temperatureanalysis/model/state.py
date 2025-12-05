"""
Project State (Data Model)
==========================
This module defines the central data structure for the running application.

Why is this file needed?
------------------------
1. State Management: It holds the current geometry, loaded materials, and
   active results in one place (Singleton pattern).
2. Persistence: This object is what gets serialized when saving a project.
3. Decoupling: Views read from this object; Controllers write to this object.

Classes:
    GeometryData: Data class for shape parameters.
    ProjectState: The main container class.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Dict, Any, Optional, Union, TYPE_CHECKING

import numpy as np

from temperatureanalysis.controller.mesher import MeshStats
from temperatureanalysis.model.profiles import ProfileGroupKey, CustomTunnelShape, TunnelProfile, ALL_PROFILES, \
    TunnelOutline, OutlineShape, TunnelCategory

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


@dataclass
class BoxParams:
    width: float = 8.0
    height: float = 5.0
    thickness: float = 0.5

@dataclass
class CircleParams:
    radius: float = 6.0
    center_y: float = 4.0
    thickness: float = 0.5

@dataclass
class PredefinedParams:
    profile_name: str = "Tunel T-7,5, ražený"
    thickness: float = 0.4

# Union for type hinting
GeometryParams = Union[BoxParams, CircleParams, PredefinedParams]

@dataclass
class GeometryData:
    """
    Holds the geometry configuration.
    Logic:
    1. Check 'group_key'
    2. If CUSTOM -> check 'custom_shape' -> Use BoxParams/CircleParams
    3. If NOT CUSTOM -> Use PredefinedParams
    """
    # High-level group selection (Road/Rail/Custom)
    group_key: ProfileGroupKey = ProfileGroupKey.VL5_ROAD

    # Sub-selection for Custom mode (Box/Circle) - Ignored if group_key != CUSTOM
    custom_shape: Optional[CustomTunnelShape] = None

    # The actual numerical data
    parameters: GeometryParams = field(default_factory=PredefinedParams)

    def set_custom_box(self) -> None:
        self.group_key = ProfileGroupKey.CUSTOM
        self.custom_shape = CustomTunnelShape.BOX
        if not isinstance(self.parameters, BoxParams):
            self.parameters = BoxParams()

    def set_custom_circle(self) -> None:
        self.group_key = ProfileGroupKey.CUSTOM
        self.custom_shape = CustomTunnelShape.CIRCLE
        if not isinstance(self.parameters, CircleParams):
            self.parameters = CircleParams()

    def set_predefined(self, group: ProfileGroupKey) -> None:
        """Switch to a predefined group (Rail/Road)."""
        self.group_key = group
        self.custom_shape = None  # Not used
        if not isinstance(self.parameters, PredefinedParams):
            # Reset to a safe default if switching from Custom
            self.parameters = PredefinedParams()

    def get_resolved_profile(self) -> Optional[TunnelProfile]:
        """Resolve Profile based on selection."""
        if self.group_key in [ProfileGroupKey.VL5_ROAD, ProfileGroupKey.RAIL_SINGLE, ProfileGroupKey.RAIL_DOUBLE]:
            if self.parameters.profile_name in ALL_PROFILES:
                return ALL_PROFILES[self.parameters.profile_name]
        else:
            return self._create_custom_profile()
        return None

    def _create_custom_profile(self) -> TunnelProfile:
        """
        Factory method to convert Custom GUI params into a standard TunnelProfile.
        """
        params = self.parameters
        shape_type = self.custom_shape

        if shape_type == CustomTunnelShape.BOX:
            # Box: Width and Height are the main dimensions
            w = getattr(params, "width", 10.0)
            h = getattr(params, "height", 5.0)

            outline = TunnelOutline(
                shape=OutlineShape.BOX,
                # Box dimensions definition: [Width, Height]
                dimensions=[w, h],
                center_first=[0.0, 0.0],
                floor_height=0.0
            )

        else: # CustomTunnelShape.CIRCLE
            # Circle: Radius is the main dimension
            r = getattr(params, "radius", 6.0)
            cy = getattr(params, "center_y", 4.0)

            outline = TunnelOutline(
                shape=OutlineShape.CIRCLE,
                dimensions=[r],
                # Center the circle at Y=R so it sits on the floor (Y=0)
                center_first=[0.0, cy],
                floor_height=0.0
            )

        # Wrap in a TunnelProfile container
        # Note: 'outer' is None, so the system will automatically
        # calculate it as (Inner + Thickness) during loop generation.
        return TunnelProfile(
            category=TunnelCategory.RAIL, # Generic placeholder
            description="Custom Shape",
            inner=outline,
            outer=None
        )


@dataclass
class ProjectState:
    """
    Singleton-like class that holds the entire state of the open project.
    Pass this instance to your Controllers and Views.
    """
    project_name: str = "Untitled Project"
    filepath: Optional[str] = None

    geometry: GeometryData = field(default_factory=GeometryData)
    materials: Dict[str, Any] = field(default_factory=dict)

    time_step: float = 30.0
    total_time_minutes: float = 180.0

    mesh_path: Optional[str] = None

    results: list[npt.NDArray] = field(default_factory=list)
    time_steps: list[float] = field(default_factory=list)


    def reset(self) -> None:
        """Clear all data for a new project"""
        self.project_name = "Untitled Project"
        self.filepath = None
        self.geometry = GeometryData()
        self.materials = {}
        self.mesh_path = None
        self.results = []
        self.time_steps = []
        self.time_step = 30.0
        self.total_time_minutes = 180.0
        logger.info("Project state has been reset.")
