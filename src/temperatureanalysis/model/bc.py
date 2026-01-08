"""
Boundary Conditions Data Model
==============================
Defines configuration structures for Fire Curves (Standard, Tabulated, Zonal).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import StrEnum
from typing import List, Dict, Optional, Any, Union
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class FireCurveType(StrEnum):
    STANDARD = "Standardní (Normová)"
    TABULATED = "Vlastní (jednozónová)"
    ZONAL = "Vlastní (vícezónová)"

class StandardCurveType(StrEnum):
    ISO834 = "ISO 834, Cellulosic"
    HC = "HydroCarbon"
    HCM = "Modified HydroCarbon"
    RABT_TRAIN = "RABT-ZTV (train)"
    RABT_CAR = "RABT-ZTV (car)"
    RWS = "RWS (Rijkswaterstaat)"

@dataclass
class FireCurveConfig(ABC):
    name: str
    description: str = ""

    @property
    @abstractmethod
    def type(self) -> FireCurveType:
        pass

    def is_standard_curve(self) -> bool:
        """Returns True if this is a read-only standard curve."""
        return self.type == FireCurveType.STANDARD

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "description": self.description, "type": self.type.value}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> FireCurveConfig:
        t = data.get("type")
        if t == FireCurveType.STANDARD: return StandardFireCurveConfig.from_dict(data)
        if t == FireCurveType.TABULATED: return TabulatedFireCurveConfig.from_dict(data)
        if t == FireCurveType.ZONAL: return ZonalFireCurveConfig.from_dict(data)
        # Default fallback
        return StandardFireCurveConfig(name="Unknown", curve_type=StandardCurveType.ISO834)

@dataclass
class StandardFireCurveConfig(FireCurveConfig):
    curve_type: StandardCurveType = StandardCurveType.ISO834

    @property
    def type(self) -> FireCurveType: return FireCurveType.STANDARD

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["curve_type"] = self.curve_type.value
        return d

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> StandardFireCurveConfig:
        return StandardFireCurveConfig(
            name=data["name"],
            description=data.get("description", ""),
            curve_type=StandardCurveType(data.get("curve_type", StandardCurveType.ISO834))
        )

@dataclass
class TabulatedFireCurveConfig(FireCurveConfig):
    # Times in Seconds
    times: List[float] = field(default_factory=list)
    # Temperatures in Celsius (for UI convenience, Solver converts if needed)
    temperatures: List[float] = field(default_factory=list)

    @property
    def type(self) -> FireCurveType: return FireCurveType.TABULATED

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["times"] = self.times
        d["temperatures"] = self.temperatures
        return d

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> TabulatedFireCurveConfig:
        return TabulatedFireCurveConfig(
            name=data["name"],
            description=data.get("description", ""),
            times=data.get("times", []),
            temperatures=data.get("temperatures", [])
        )

@dataclass
class ZoneConfig:
    y_min: float
    y_max: float
    curve: FireCurveConfig  # Nested curve definition for this zone

    def to_dict(self) -> Dict[str, Any]:
        return {
            "y_min": self.y_min,
            "y_max": self.y_max,
            "curve": self.curve.to_dict()
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> ZoneConfig:
        return ZoneConfig(
            y_min=data.get("y_min", 0.0),
            y_max=data.get("y_max", 10.0),
            curve=FireCurveConfig.from_dict(data.get("curve", {}))
        )

@dataclass
class ZonalFireCurveConfig(FireCurveConfig):
    """
    Zonal fire curve configuration.
    Zones must cover the entire geometry - no default curve for uncovered areas.
    Each zone can only use Tabulated curves (not Standard curves).
    """
    zones: List[ZoneConfig] = field(default_factory=list)

    @property
    def type(self) -> FireCurveType: return FireCurveType.ZONAL

    def validate_coverage(self, geometry_height: float) -> tuple[bool, str]:
        """
        Validates that zones cover the entire height without gaps.

        Args:
            geometry_height: Total height of the tunnel geometry

        Returns:
            (is_valid, error_message) tuple
        """
        if not self.zones:
            return False, "Zónová křivka musí obsahovat alespoň jednu zónu."

        # Sort zones by y_min
        sorted_zones = sorted(self.zones, key=lambda z: z.y_min)

        # Check if coverage starts at 0
        if sorted_zones[0].y_min > 0.01:  # Small tolerance for floating point
            return False, f"Chybí pokrytí od Y=0 do Y={sorted_zones[0].y_min:.2f}m"

        # Check for gaps between zones
        for i in range(len(sorted_zones) - 1):
            current_max = sorted_zones[i].y_max
            next_min = sorted_zones[i + 1].y_min

            if next_min - current_max > 0.01:  # Gap detected
                return False, f"Mezera mezi zónami: Y={current_max:.2f}m až Y={next_min:.2f}m"

            if current_max - next_min > 0.01:  # Overlap detected
                logger.warning(f"Překrývající se zóny: Y={next_min:.2f}m až Y={current_max:.2f}m")

        # Check if coverage reaches geometry height
        if sorted_zones[-1].y_max < geometry_height - 0.01:
            return False, f"Chybí pokrytí od Y={sorted_zones[-1].y_max:.2f}m do Y={geometry_height:.2f}m"

        return True, ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["zones"] = [z.to_dict() for z in self.zones]
        return d

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> ZonalFireCurveConfig:
        zones = [ZoneConfig.from_dict(z) for z in data.get("zones", [])]

        return ZonalFireCurveConfig(
            name=data["name"],
            description=data.get("description", ""),
            zones=zones
        )

class FireCurveLibrary:
    def __init__(self):
        self.curves: Dict[str, FireCurveConfig] = {}
        self._init_defaults()

    def _init_defaults(self):
        # Add Standard presets (read-only curves)
        for std in StandardCurveType:
            c = StandardFireCurveConfig(name=std.value, curve_type=std, description="Normová křivka")
            self.curves[c.name] = c

    def add(self, curve: FireCurveConfig):
        self.curves[curve.name] = curve

    def delete(self, name: str) -> bool:
        """
        Delete a curve from the library.
        Returns False if curve cannot be deleted (e.g., standard curve).
        """
        if name in self.curves:
            curve = self.curves[name]
            if curve.is_standard_curve():
                logger.warning(f"Cannot delete standard curve: {name}")
                return False
            del self.curves[name]
            return True
        return False

    def is_deletable(self, name: str) -> bool:
        """Check if a curve can be deleted (not a standard curve)."""
        if name in self.curves:
            return not self.curves[name].is_standard_curve()
        return False

    def get_names(self) -> List[str]:
        return list(self.curves.keys())

    def get_fire_curve(self, name: str) -> Optional[FireCurveConfig]:
        return self.curves.get(name)
