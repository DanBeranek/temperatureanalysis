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
    TABULATED = "Vlastní (Tabulka)"
    ZONAL = "Zónová (Dle výšky)"


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
    times: List[float] = field(default_factory=list)
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
    # Default curve used if position not in any zone
    default_curve: FireCurveConfig = field(
        default_factory=lambda: StandardFireCurveConfig(name="Default", curve_type=StandardCurveType.ISO834)
    )
    zones: List[ZoneConfig] = field(default_factory=list)

    @property
    def type(self) -> FireCurveType:
        return FireCurveType.ZONAL

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["default_curve"] = self.default_curve.to_dict()
        d["zones"] = [z.to_dict() for z in self.zones]
        return d

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> ZonalFireCurveConfig:
        def_c_data = data.get("default_curve")
        if def_c_data:
            def_c = FireCurveConfig.from_dict(def_c_data)
        else:
            def_c = StandardFireCurveConfig(name="Default")

        zones = [ZoneConfig.from_dict(z) for z in data.get("zones", [])]

        return ZonalFireCurveConfig(
            name=data["name"],
            description=data.get("description", ""),
            default_curve=def_c,
            zones=zones
        )


class FireCurveLibrary:
    def __init__(self):
        self.curves: Dict[str, FireCurveConfig] = {}
        self._init_defaults()

    def _init_defaults(self):
        # Add Standard presets
        for std in StandardCurveType:
            c = StandardFireCurveConfig(name=std, curve_type=std, description="Normová křivka")
            self.curves[c.name] = c

    def add(self, curve: FireCurveConfig):
        self.curves[curve.name] = curve

    def get_names(self) -> List[str]:
        return list(self.curves.keys())

    def get_fire_curve(self, name: str) -> Optional[FireCurveConfig]:
        return self.curves.get(name)
