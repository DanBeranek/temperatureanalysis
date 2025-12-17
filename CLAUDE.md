# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TemperatureAnalysis is a PySide6-based GUI application for thermal analysis of tunnel structures during fire events. The application provides geometry definition, material configuration, mesh generation, finite element analysis (FEA) solver, and visualization of temperature distributions over time.

## Development Commands

### Environment Setup
```bash
# Install with Poetry
poetry install

# Activate virtual environment (if not using poetry shell)
poetry shell

# For development from project root
python run.py
```

### Testing
```bash
# Run all tests
nox -s tests

# Run tests for specific Python version
nox -s tests-3.11

# Run single test file
pytest tests/test_functions.py

# Run tests with coverage
nox -s coverage
```

### Code Quality
```bash
# Run all pre-commit checks
nox -s pre-commit

# Run individual tools
ruff check --fix src tests
black src tests

# Type checking
nox -s mypy
```

### Documentation
```bash
# Build documentation
nox -s docs-build

# Serve documentation with live reload
nox -s docs
```

## Architecture

### MVC Pattern

The application follows a traditional **Model-View-Controller** pattern:

```
src/temperatureanalysis/
├── model/                  # Data Layer
│   ├── state.py           # ProjectState singleton (central application state)
│   ├── materials.py       # MaterialLibrary, Material classes, property metadata
│   ├── geometry.py        # Geometry definitions (GeometryData, BoxParams, CircleParams)
│   ├── geometry_primitives.py  # Point, Line, Arc, BoundaryLoop
│   ├── profiles.py        # Predefined tunnel profiles (Rail/Road categories)
│   └── io.py             # Project serialization/deserialization (save/load)
│
├── view/                   # Presentation Layer
│   ├── main_window.py     # Primary GUI container (menu bar + 5 workflow tabs)
│   ├── tabs/              # Five workflow stages
│   │   ├── tab_geometry.py       # Stage 1: Define geometry
│   │   ├── tab_materials.py      # Stage 2: Configure materials
│   │   ├── tab_bc.py            # Stage 3: Boundary conditions
│   │   ├── tab_mesh.py          # Stage 4: Mesh generation
│   │   └── tab_results.py       # Stage 5: Visualization/results
│   ├── dialogs/
│   │   ├── dialog_material.py    # Material editor dialog
│   │   └── bc_dialog.py         # Boundary condition dialog
│   └── widgets/
│       ├── plot_3d.py           # PyVista integration (3D visualization)
│       ├── plot_2d.py           # 2D plotting (matplotlib/pyqtgraph)
│       └── grid_manager.py      # VTK mesh management
│
└── controller/             # Business Logic Layer
    ├── mesher.py         # Gmsh integration for mesh generation
    ├── workers.py        # Threading/async support
    └── fea/              # Complete FEA Subsystem (see below)
```

**State Management**: The `ProjectState` singleton in `model/state.py` is the single source of truth for all application data (geometry, materials, mesh, results).

### Entry Points

- **Development**: `run.py` - Bootstrap script that adds `src/` to path (REQUIRED for development)
- **Main**: `src/temperatureanalysis/main.py` - Creates QApplication, ProjectState, and MainWindow
- **Installed**: `temperatureanalysis` command (via pyproject.toml script entry point)

### FEA Subsystem

Located in `controller/fea/`, this is a complete finite element analysis implementation:

- **Pre-processing** (`pre/`):
  - `mesh.py`: Mesh loading from Gmsh
  - `material.py`: Material property definitions (Concrete, Steel classes)
  - `material_helpers.py`: Property calculation functions
  - `fire_curves.py`: Temperature-time curves (ISO834, Hydrocarbon, etc.)

- **Analysis** (`analysis/`):
  - `model.py`: FEA model assembly (stiffness/mass matrices)
  - `node.py`: Node and thermocouple classes
  - `gauss.py`: Gaussian quadrature
  - `finite_elements/`: Element implementations
    - Base class: `finite_element.py`
    - Triangle elements: `tri3.py`, `tri6.py`
    - Quadrilateral elements: `quad4.py`, `quad8.py`
    - Edge elements: `edges.py`

- **Solvers** (`solvers/`):
  - `solver.py`: Transient heat transfer solver
  - Uses sparse matrix operations with pypardiso for performance

- **Post-processing** (`post/`):
  - Visualization with PyVista/VTK
  - Temperature history plots

### Key Data Flows

**Geometry Definition**:
1. User selects geometry type in `tab_geometry.py`:
   - Predefined tunnel profile (Road/Rail categories from `profiles.py`)
   - Custom Box (width, height, thickness)
   - Custom Circle (radius, center_y, thickness)
2. Parameters stored in `GeometryData` (BoxParams, CircleParams, or PredefinedParams)
3. Mesh generated via Gmsh in `controller/mesher.py`
4. Mesh file path stored in `ProjectState.mesh_path`

**Material Configuration**:
1. Material library managed in `model/materials.py`
2. Two types: `GenericTabulatedMaterial` (custom curves) or `ConcreteMaterial` (EN 1992-1-2)
3. Properties: conductivity, specific heat capacity, density (all temperature-dependent)
4. Materials assigned to geometry regions before meshing

**FEA Workflow**:
1. Mesh + materials → FEA Model assembly (`controller/fea/analysis/model.py`)
2. Transient solver with implicit time stepping (`controller/fea/solvers/solver.py`)
3. Results (temperature at each time step) stored in `ProjectState.results`
4. Visualization in `tab_results.py` using PyVista widgets

**5-Stage Workflow**:
```
GEOMETRY → MATERIALS → BCS → MESH → SOLVER/RESULTS
```
Each stage gates the next (cannot proceed without completing prerequisites).

## Technology Stack

- **GUI Framework**: PySide6 (Qt for Python) 6.9.2+
- **Numerical Computing**: NumPy 1.24+, SciPy 1.16.0+, Numba 0.61.2+ (JIT compilation)
- **Meshing**: Gmsh 4.14.0+, meshio 5.3.5+
- **Visualization**: PyVista 0.46.2+, PyVistaQt 0.11.3+, matplotlib 3.10.3+, pyqtgraph 0.13.7+
- **Linear Algebra**: pypardiso 0.4.6+ (sparse direct solver, falls back to SciPy if unavailable)
- **Data Storage**: HDF5 (h5py 3.15.1+), NumExpr 2.14.1+
- **CLI**: Click 8.0.1+
- **Color Maps**: colorcet 3.1.0+

## Important Conventions

### Code Style
- **Linter**: Ruff (replaces flake8, isort, etc.) - strict rule set
- **Formatter**: Black
- **Type Hints**: Required everywhere (enforced by mypy with strict mode)
- **Docstring Style**: Google format
- **Pre-commit**: All checks must pass before commit
- **Test Coverage**: Minimum 50% (configured in pyproject.toml)

### File Organization
- UI tabs for workflow stages: `view/tabs/`
- Material/BC dialogs: `view/dialogs/`
- Visualization widgets: `view/widgets/`
- FEA solver components: `controller/fea/`
- Geometry profiles: `model/profiles.py` with `ALL_PROFILES` registry
- Tests use pytest with `pythonpath = ["src"]` configuration

### Working with State
- `ProjectState` singleton (`model/state.py`) is the single source of truth
- Holds: geometry, material_library, mesh_path, results, time_steps
- Supports serialization/deserialization for save/load (via `model/io.py`)
- Uses Qt signals for state change notifications

### Meshing Workflow
1. Geometry defined in UI → parameters in `GeometryData`
2. `controller/mesher.py` constructs Gmsh geometry programmatically
3. Physical groups assigned for materials and boundary conditions
4. Mesh exported as `.msh` file
5. Loaded by FEA system via `controller/fea/pre/mesh.py`
6. `MeshStats` dataclass tracks node/element counts

### Material System
- **GUI Layer**: `model/materials.py` - Material definitions for UI
- **FEA Layer**: `controller/fea/pre/material.py` - Concrete, Steel classes with property calculations
- Properties stored as **tabulated curves** (temperature → property value)
- Two material types:
  - `GenericTabulatedMaterial`: Custom temperature-dependent properties
  - `ConcreteMaterial`: EN 1992-1-2 standard with siliceous/calcareous variants

### Testing Notes
- Tests use pytest with coverage tracking
- Run single test: `pytest tests/test_functions.py`
- Coverage requirement: 50% minimum
- Type checking runs on both src and tests
- Use `pythonpath = ["src"]` in pytest configuration

## Language and Localization

The application UI is in **Czech language** by default:
- Visible app name: "Tunel: Požár" (Tunnel: Fire)
- UI labels use Czech terminology (e.g., "Geometrie", "Materiály", "Síť")
- Translation files not currently in use (hardcoded Czech strings)

## Development Notes

### Running the Application
**CRITICAL**: Always use `python run.py` for development. The `run.py` script is essential because it adds `src/` to the Python path, allowing imports like `from temperatureanalysis.model...` to resolve correctly.

Do NOT run `python -m temperatureanalysis` during development.

### Commented-Out Example Code
The `main.py` file contains extensive commented-out FEA solver code at the bottom. This shows example usage patterns for:
- Creating fire curves (ISO834, Hydrocarbon)
- Loading meshes with material/BC assignments
- Running transient analysis with progress callbacks
- Plotting temperature distributions over time
- Visualizing thermocouple temperature histories

These examples are valuable reference material when working with the FEA subsystem.

### Performance Optimizations
- Numba JIT compilation for element calculations (heat capacity matrices)
- pypardiso sparse direct solver for speed (falls back to SciPy sparse.linalg if unavailable)
- Precomputed sparsity patterns in FEA solver
- Progress callbacks for long-running operations

### PyInstaller Support
The `config.py` module handles frozen executable environments via `sys._MEIPASS` detection for asset/resource loading.

## Development Status

The project is in active development:
- Current branch: `dev` (feature development)
- Main branch: `main` (stable releases)
- Recent work focuses on:
  - Material system refactoring (GenericTabulatedMaterial)
  - UI improvements (material dialogs, visualization controls)
  - Mesh handling enhancements (GridManager, VTK utilities)
  - Solver robustness (progress callbacks, error handling)
