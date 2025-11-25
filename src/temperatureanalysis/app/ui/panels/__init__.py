"""
Auto-import all tunnel type dialog modules to ensure registration side-effects run.

After importing this package, `registry.tunnel_labels()` and `registry.make_tunnel_dialog()`
will know about all available types.
"""
from __future__ import annotations

import importlib
import pkgutil

from temperatureanalysis.app.ui.panels import geometry_editors as _types_pkg

for _module in pkgutil.iter_modules(_types_pkg.__path__, _types_pkg.__name__ + "."):
    importlib.import_module(_module.name)
