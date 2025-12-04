"""
Input/Output Manager (HDF5)
Handles saving and loading the ProjectState to .h5 files.
"""
import os
import tempfile

import h5py
import numpy as np
from typing import Optional
from dataclasses import asdict
from importlib.metadata import version, PackageNotFoundError

from temperatureanalysis.model.state import (
    ProjectState, GeometryData, BoxParams, CircleParams, PredefinedParams
)
# Import TunnelShape to handle Enum conversion
from temperatureanalysis.model.profiles import CustomTunnelShape

try:
    APP_VERSION = version("temperatureanalysis")
except PackageNotFoundError:
    APP_VERSION = "0.0.0-dev"

class IOManager:
    @staticmethod
    def save_project(state: ProjectState, filepath: str) -> None:
        try:
            with h5py.File(filepath, "w") as f:
                f.attrs["version"] = APP_VERSION
                f.attrs["project_name"] = state.project_name

                # --- SAVE GEOMETRY ---
                grp_geo = f.create_group("geometry")

                # 1. Save the high-level type identifier
                # We use the class name of the parameters as the strict type identifier
                param_type_name = state.geometry.parameters.__class__.__name__
                grp_geo.attrs["parameters_class"] = param_type_name

                # 2. Save the parameters
                # asdict converts the dataclass to a dict {width: 10, ...}
                # We save ONLY these fields.
                params_dict = asdict(state.geometry.parameters)

                grp_params = grp_geo.create_group("parameters")
                for key, val in params_dict.items():
                    grp_params.attrs[key] = val

                # 3. Save Mesh as binary blob
                if state.mesh_path and os.path.exists(state.mesh_path):
                    IOManager._save_mesh_binary(f, state.mesh_path)

            print(f"Project saved to: {filepath}")

        except Exception as e:
            print(f"Failed to save project: {e}")
            raise e

    @staticmethod
    def load_project(state: ProjectState, filepath: str) -> None:
        if not h5py.is_hdf5(filepath):
            raise ValueError("File is not a valid HDF5 file.")

        try:
            with h5py.File(filepath, "r") as f:
                if "project_name" in f.attrs:
                    state.project_name = str(f.attrs["project_name"])

                # --- 1. LOAD GEOMETRY ---
                if "geometry" in f:
                    grp_geo = f["geometry"]

                    # 1. Identify which parameter class to use
                    param_class_name = grp_geo.attrs.get("parameters_class", "BoxParams")

                    # 2. Load raw values
                    loaded_values = {}
                    if "parameters" in grp_geo:
                        grp_params = grp_geo["parameters"]
                        for key in grp_params.attrs.keys():
                            # HDF5 often saves as numpy types, convert to native python
                            val = grp_params.attrs[key]
                            if isinstance(val, bytes):
                                val = val.decode('utf-8')
                            elif hasattr(val, 'item'):
                                val = val.item()
                            loaded_values[key] = val

                    # 3. Instantiate and Assign
                    if param_class_name == "BoxParams":
                        state.geometry.parameters = BoxParams(**loaded_values)
                        state.geometry.shape_type = CustomTunnelShape.BOX

                    elif param_class_name == "CircleParams":
                        state.geometry.parameters = CircleParams(**loaded_values)
                        state.geometry.shape_type = CustomTunnelShape.CIRCLE

                    elif param_class_name == "PredefinedParams":
                        state.geometry.parameters = PredefinedParams(**loaded_values)
                        # Correctly map to PREDEFINED enum
                        state.geometry.shape_type = None

                # --- 2. LOAD MESH ---
                mesh_temp_path = IOManager._load_mesh_binary(f)
                if mesh_temp_path:
                    state.mesh_path = mesh_temp_path

                state.results_file = filepath

            print(f"Project loaded from: {filepath}")

        except Exception as e:
            print(f"Failed to load project: {e}")
            raise e

    # --- BINARY MESH HELPERS ---

    @staticmethod
    def _save_mesh_binary(h5_file: h5py.File, mesh_path: str) -> None:
        """Reads file bytes and saves to HDF5 Opaque dataset."""
        try:
            with open(mesh_path, "rb") as mf:
                binary_data = mf.read()

            # Create a uint8 dataset (byte array)
            # dt = h5py.special_dtype(vlen=bytes) or just numpy uint8
            data_np = np.frombuffer(binary_data, dtype=np.uint8)
            h5_file.create_dataset("mesh_file_blob", data=data_np, compression="gzip")

            # Save original extension to know if it was .msh or .vtu
            ext = os.path.splitext(mesh_path)[1]
            h5_file["mesh_file_blob"].attrs["extension"] = ext

            print(f"Mesh saved ({len(data_np)} bytes).")

        except Exception as e:
            print(f"Warning: Could not save mesh binary: {e}")

    @staticmethod
    def _load_mesh_binary(h5_file: h5py.File) -> Optional[str]:
        """Extracts binary blob to temp file."""
        if "mesh_file_blob" not in h5_file:
            return None

        try:
            dset = h5_file["mesh_file_blob"]
            binary_data = dset[:].tobytes()
            ext = dset.attrs.get("extension", ".msh")

            # Create temp file
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"loaded_project_mesh{ext}")

            with open(temp_path, "wb") as mf:
                mf.write(binary_data)

            print(f"Mesh extracted to: {temp_path}")
            return temp_path

        except Exception as e:
            print(f"Warning: Could not load mesh binary: {e}")
            return None
