"""
Input/Output Manager (HDF5)
Handles saving and loading the ProjectState to .h5 files.
"""
import json
import logging
import os
import shutil
import tempfile
import uuid

import h5py
import numpy as np
from typing import Optional
from dataclasses import asdict
import logging
from importlib.metadata import version, PackageNotFoundError

import pyvista as pv

from temperatureanalysis.model.state import ProjectState, BoxParams, CircleParams, PredefinedParams
from temperatureanalysis.model.profiles import CustomTunnelShape, ProfileGroupKey
from temperatureanalysis.model.materials import Material, MaterialType, ConcreteMaterial, GenericMaterial

# Get module logger
logger = logging.getLogger(__name__)

try:
    APP_VERSION = version("temperatureanalysis")
except PackageNotFoundError:
    APP_VERSION = "0.0.0-dev"

class IOManager:
    # Track temporary files created during load
    _TEMP_FILES: list[str] = []

    @staticmethod
    def cleanup_temp_files() -> None:
        """Deletes all temporary files created during the session."""
        logger.info(f"Cleaning up {len(IOManager._TEMP_FILES)} temporary mesh files.")
        for temp_path in IOManager._TEMP_FILES:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.debug(f"Deleted temp file: {temp_path}")
            except Exception as e:
                logger.warning(f"Could not delete temp file '{temp_path}': {e}")
        IOManager._TEMP_FILES.clear()

    @staticmethod
    def save_project(state: ProjectState, filepath: str) -> None:
        logger.info(f"Saving project to: {filepath}")
        try:
            with h5py.File(filepath, "w") as f:
                f.attrs["version"] = APP_VERSION
                f.attrs["project_name"] = state.project_name

                # --- 1. SAVE GEOMETRY ---
                grp_geo = f.create_group("geometry")

                # 1.1 Save the high-level type identifier
                # We use the class name of the parameters as the strict type identifier
                param_type_name = state.geometry.parameters.__class__.__name__
                grp_geo.attrs["parameters_class"] = param_type_name
                grp_geo.attrs["group_key"] = str(state.geometry.group_key)

                # 1.2. Save the parameters
                # asdict converts the dataclass to a dict {width: 10, ...}
                # We save ONLY these fields.
                params_dict = asdict(state.geometry.parameters)

                grp_params = grp_geo.create_group("parameters")
                for key, val in params_dict.items():
                    grp_params.attrs[key] = val

                # --- 2. SAVE MATERIALS ---
                grp_mats = f.create_group("materials")
                # Save library
                lib_data = {
                    name: mat.to_dict()
                    for name, mat in state.material_library.materials.items()
                }
                lib_json = json.dumps(lib_data)

                # Use dataset if data exceeds HDF5 attribute size limit (64KB)
                if len(lib_json) > 60000:  # Safety margin
                    logger.info(f"Material library is large ({len(lib_json)} bytes), using dataset")
                    grp_mats.create_dataset("material_library", data=np.void(lib_json.encode('utf-8')))
                else:
                    grp_mats.attrs["material_library_json"] = lib_json

                # Save selected material
                if state.selected_material:
                    # Save the full state of the selected material to be safe
                    sel_json = json.dumps(state.selected_material.to_dict())
                    if len(sel_json) > 60000:
                        grp_mats.create_dataset("selected_material", data=np.void(sel_json.encode('utf-8')))
                    else:
                        grp_mats.attrs["selected_material"] = sel_json

                # --- 3. SAVE ANALYSIS SETTINGS ---
                grp_sim = f.create_group("analysis_settings")
                grp_sim.attrs["time_step"] = state.time_step
                grp_sim.attrs["total_time_minutes"] = state.total_time_minutes

                # --- 4. SAVE RESULTS ---
                if state.results and state.time_steps:
                    grp_res = f.create_group("results")
                    # Save time steps
                    grp_res.create_dataset("time_steps", data=np.array(state.time_steps))

                    # Save temperature data
                    # Stack list of 1D arrays into a 2D matrix (Timesteps x Nodes)
                    # This assumes all frames have same node count (fixed mesh)
                    if len(state.results) > 0:
                        try:
                            # Stack: (T, N)
                            data_matrix = np.vstack(state.results)
                            grp_res.create_dataset("temperatures", data=data_matrix, compression="gzip")
                            logger.debug(f"Saved {len(state.results)} result frames.")
                        except Exception as e:
                            logger.error(f"Failed to stack results for saving: {e}")

                # --- 5. SAVE MESH (BINARY) ---
                if state.mesh_path and os.path.exists(state.mesh_path):
                    logger.debug(f"Saving mesh binary from {state.mesh_path}")
                    IOManager._save_mesh_binary(f, state.mesh_path)

            logger.info(f"Project saved to: {filepath}")

        except Exception as e:
            logger.exception(f"Failed to save project: {e}")
            raise e

    @staticmethod
    def load_project(state: ProjectState, filepath: str) -> None:
        logger.info(f"Loading project from: {filepath}")
        if not h5py.is_hdf5(filepath):
            msg = f"File '{filepath}' is not a valid HDF5 file."
            logger.error(msg)
            raise ValueError(msg)

        try:
            with h5py.File(filepath, "r") as f:
                # reset the state to clear existing data
                state.reset()

                if "project_name" in f.attrs:
                    state.project_name = str(f.attrs["project_name"])

                # --- 1. LOAD GEOMETRY ---
                if "geometry" in f:
                    grp_geo = f["geometry"]

                    # 1.1 Identify which parameter class to use
                    param_class_name = grp_geo.attrs.get("parameters_class", "BoxParams")

                    # 1.2 Load raw values
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

                    # 1.3 Instantiate and Assign
                    if param_class_name == "BoxParams":
                        state.geometry.parameters = BoxParams(**loaded_values)
                        state.geometry.shape_type = CustomTunnelShape.BOX
                        state.geometry.custom_shape = CustomTunnelShape.BOX
                        state.geometry.group_key = ProfileGroupKey.CUSTOM

                    elif param_class_name == "CircleParams":
                        state.geometry.parameters = CircleParams(**loaded_values)
                        state.geometry.shape_type = CustomTunnelShape.CIRCLE
                        state.geometry.custom_shape = CustomTunnelShape.CIRCLE
                        state.geometry.group_key = ProfileGroupKey.CUSTOM

                    elif param_class_name == "PredefinedParams":
                        state.geometry.parameters = PredefinedParams(**loaded_values)
                        # Correctly map to PREDEFINED enum
                        state.geometry.shape_type = None
                        state.geometry.custom_shape = None
                        state.geometry.group_key = grp_geo.attrs.get("group_key", ProfileGroupKey.VL5_ROAD)

                # --- LOAD MATERIALS ---
                if "materials" in f:
                    grp_mats = f["materials"]

                    # Load material library (check both dataset and attribute)
                    lib_json = None
                    if "material_library" in grp_mats:
                        # Large data stored as dataset
                        lib_json = bytes(grp_mats["material_library"][()]).decode('utf-8')
                    elif "material_library_json" in grp_mats.attrs:
                        # Small data stored as attribute
                        lib_json = grp_mats.attrs["material_library_json"]

                    if lib_json:
                        try:
                            lib_data = json.loads(lib_json)
                            state.material_library.materials.clear()
                            for name, mat_dict in lib_data.items():
                                # get class type from dict
                                mat_type = mat_dict.get("type")
                                if mat_type == MaterialType.CONCRETE:
                                    mat = ConcreteMaterial.from_dict(mat_dict)
                                elif mat_type == MaterialType.GENERIC:
                                    mat = GenericMaterial.from_dict(mat_dict)
                                state.material_library.materials[name] = mat
                            logger.debug(f"Loaded {len(state.material_library.materials)} materials into library.")
                        except Exception as e:
                            logger.error(f"Failed to load material library: {e}")

                    # Load selected material (check both dataset and attribute)
                    sel_json = None
                    if "selected_material" in grp_mats:
                        # Large data stored as dataset
                        sel_json = bytes(grp_mats["selected_material"][()]).decode('utf-8')
                    elif "selected_material" in grp_mats.attrs:
                        # Small data stored as attribute
                        sel_json = grp_mats.attrs["selected_material"]

                    if sel_json:
                        try:
                            sel_dict = json.loads(sel_json)
                            mat_type = sel_dict.get("type")
                            if mat_type == MaterialType.CONCRETE:
                                state.selected_material = ConcreteMaterial.from_dict(sel_dict)
                            elif mat_type == MaterialType.GENERIC:
                                state.selected_material = GenericMaterial.from_dict(sel_dict)
                            logger.debug(f"Selected material loaded: {state.selected_material.name}")
                        except Exception as e:
                            logger.error(f"Failed to load selected material: {e}")


                # --- LOAD ANALYSIS SETTINGS ---
                if "analysis_settings" in f:
                    grp_sim = f["analysis_settings"]
                    if "time_step" in grp_sim.attrs:
                        state.time_step = float(grp_sim.attrs["time_step"])
                    if "total_time_minutes" in grp_sim.attrs:
                        state.total_time_minutes = float(grp_sim.attrs["total_time_minutes"])

                # --- LOAD RESULTS ---
                state.results = []
                state.time_steps = []

                if "results" in f:
                    grp_res = f["results"]
                    if "time_steps" in grp_res:
                        state.time_steps = grp_res["time_steps"][:].tolist()

                    if "temperatures" in grp_res:
                        matrix = grp_res["temperatures"][:]
                        # Split 2D matrix back into list of 1D arrays for the app
                        state.results = [row for row in matrix]
                        logger.debug(f"Loaded {len(state.results)} result frames.")

                # --- 2. LOAD MESH ---
                mesh_temp_path = IOManager._load_mesh_binary(f)
                if mesh_temp_path:
                    state.mesh_path = mesh_temp_path
                    logger.debug(f"Mesh successfully loaded from temp file: {mesh_temp_path}")
                else:
                    logger.warning(f"No mesh loaded.")

            logger.info(f"Project loaded from: {filepath}")

        except Exception as e:
            logger.exception(f"Failed to load project: {e}")
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

            logger.info(f"Mesh saved ({len(data_np)} bytes).")

        except Exception as e:
            logger.exception(f"Warning: Could not save mesh binary: {e}")

    @staticmethod
    def _load_mesh_binary(h5_file: h5py.File) -> Optional[str]:
        """Extracts binary blob to temp file."""
        if "mesh_file_blob" not in h5_file:
            logger.debug(f"No mesh binary found in HDF5.")
            return None

        try:
            dset = h5_file["mesh_file_blob"]
            binary_data = dset[:].tobytes()
            ext = dset.attrs.get("extension", ".msh")

            # Create temp file
            unique_name = f"mesh_{uuid.uuid4().hex}{ext}"
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, unique_name)

            with open(temp_path, "wb") as mf:
                logger.debug(f"Saving temporary mesh file to temp file: {temp_path}")
                mf.write(binary_data)

            IOManager._TEMP_FILES.append(temp_path)

            return temp_path

        except Exception as e:
            logger.warning(f"Warning: Could not load mesh binary: {e}")
            return None

    # ---- EXPORT HELPERS ----
    @staticmethod
    def export_mesh_file(source_path: str, dest_path: str) -> None:
        """
        Copies the temporary mesh file to a user-defined destination.
        """
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source mesh file not found: {source_path}")

        try:
            shutil.copy2(source_path, dest_path)
            logger.info(f"Mesh exported to: {dest_path}")
        except Exception as e:
            logger.exception("Failed to export mesh file")
            raise e

    @staticmethod
    def export_results_to_vtu(state: ProjectState, parent_dir: str) -> str:
        """
        Exports results as a series of .vtu files and a .pvd linker file.
        Files are named: case_t{seconds}.vtu
        """
        if not state.mesh_path or not state.results:
            raise ValueError("No mesh or results to export.")

        output_dir = os.path.join(parent_dir, "results")
        os.makedirs(output_dir, exist_ok=True)

        logger.info(f"Exporting {len(state.results)} frames to {output_dir}...")

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Load the base mesh once
        base_mesh = pv.read(state.mesh_path)

        # PVD Header
        pvd_lines = [
            '<?xml version="1.0"?>',
            '<VTKFile type="Collection" version="0.1" byte_order="LittleEndian" compressor="vtkZLibDataCompressor">',
            '  <Collection>'
        ]

        for i, (t_sec, temp_data) in enumerate(zip(state.time_steps, state.results)):
            # Calculate seconds for filename
            filename = f"case_t{t_sec:.0f}.vtu"
            filepath = os.path.join(output_dir, filename)

            # Create a copy (shallow copy is fine since we modify point data)
            mesh_frame = base_mesh.copy()

            # Convert to Celsius
            celsius_data = temp_data - 273.15
            mesh_frame.point_data["Temperature [C]"] = celsius_data
            mesh_frame.point_data["Temperature [K]"] = temp_data

            # Add Time field (useful for filters)
            mesh_frame.field_data["TimeValue"] = [t_sec]

            # Save VTU
            mesh_frame.save(filepath)

            # Add to PVD
            pvd_lines.append(f'    <DataSet timestep="{t_sec}" group="" part="0" file="{filename}"/>')

        # Close PVD
        pvd_lines.append('  </Collection>')
        pvd_lines.append('</VTKFile>')

        # Save PVD
        pvd_path = os.path.join(output_dir, "simulation_results.pvd")
        with open(pvd_path, "w") as f:
            f.write("\n".join(pvd_lines))

        logger.info(f"Export complete. Load '{pvd_path}' in ParaView.")

        return output_dir
