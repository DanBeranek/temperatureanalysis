from __future__ import annotations
from temperatureanalysis.app.ui.panels.geometry_editors.base import ParamEditorBase

_REGISTRY: dict[str, type[ParamEditorBase]] = {}

def register_editor(cls: type[ParamEditorBase]) -> type[ParamEditorBase]:
    """Class decorator to register an editor by its KEY."""
    key = getattr(cls, "KEY", None)
    if not key:
        raise ValueError(f"{cls.__name__} must define KEY")
    _REGISTRY[key] = cls
    return cls

def create_editor(key: str, parent=None) -> ParamEditorBase:
    cls = _REGISTRY.get(key)
    if not cls:
        raise KeyError(f"No editor registered for key '{key}'")
    return cls(parent)

def list_keys() -> list[str]:
    return list(_REGISTRY.keys())
