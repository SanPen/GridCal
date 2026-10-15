from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import VeraGridEngine.api as vg
from VeraGridEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType
from VeraGridEngine.IO.file_open import FileOpenOptions
from VeraGridEngine.IO.file_save import FileSave, FileSavingOptions, FileType
from VeraGridEngine.Simulations import PowerFlowOptions
from VeraGridEngine.Simulations.driver_template import DriverToSave
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import CGMESVersions, SimulationTypes, SolverType


def create_file_save_options(boundary_zip_path: str) -> FileSavingOptions:
    options = FileSavingOptions(file_type=FileType.CGMES)
    options.cgmes_one_file_per_profile = False
    options.cgmes_profiles = [
        CgmesProfileType.EQ,
        CgmesProfileType.OP,
        CgmesProfileType.TP,
        CgmesProfileType.SV,
        CgmesProfileType.SSH,
    ]
    options.cgmes_version = CGMESVersions.v2_4_15
    options.cgmes_boundary_set = boundary_zip_path
    return options


def create_file_open_options() -> FileOpenOptions:
    return FileOpenOptions(
        cgmes_map_areas_like_raw=True,
        cgmes_try_to_map_dc_to_hvdc_line=True,
        psse_adjust_taps_to_discrete_positions=True,
        file_type=FileType.CGMES,
        cgmes_version=CGMESVersions.v2_4_15,
    )


def get_power_flow_options() -> PowerFlowOptions:
    return PowerFlowOptions(
        solver_type=SolverType.NR,
        retry_with_other_methods=False,
        control_taps_modules=False,
        control_taps_phase=False,
        control_remote_voltage=False,
        ignore_single_node_islands=True,
    )


def main() -> None:
    root = Path(__file__).resolve().parent
    cgmes_path = root / "micro_grid_NL_T1.zip"
    boundary_path = root / "micro_grid_BD.zip"
    export_path = root / "micro_grid_NL_T1_roundtrip.zip"
    logger = Logger()

    circuit_1 = vg.FileOpen(file_name=[str(cgmes_path), str(boundary_path)], options=create_file_open_options()).open()
    circuit_1.buses.sort(key=lambda obj: obj.name)
    numerical_circuit_1 = vg.compile_numerical_circuit_at(circuit_1)
    power_flow_results = vg.power_flow(circuit_1, get_power_flow_options())

    pf_session_data = DriverToSave(
        name="powerflow results",
        tpe=SimulationTypes.PowerFlow_run,
        results=power_flow_results,
        logger=logger,
    )
    save_options = create_file_save_options(str(boundary_path))
    save_options.sessions_data.append(pf_session_data)
    FileSave(circuit=circuit_1, file_name=str(export_path), options=save_options).save()

    circuit_2 = vg.FileOpen(file_name=[str(export_path), str(boundary_path)], options=create_file_open_options()).open()
    circuit_2.buses.sort(key=lambda obj: obj.name)
    if circuit_1.buses[0].name != circuit_2.buses[0].name:
        circuit_2.buses.append(circuit_2.buses.pop(0))
    numerical_circuit_2 = vg.compile_numerical_circuit_at(circuit_2)

    ok, logger = circuit_1.compare_circuits(circuit_2)
    if not ok:
        logger.print()
    ok, logger = numerical_circuit_1.compare(nc_2=numerical_circuit_2, tol=1e-4)
    assert ok, logger

    print("ok")
    print(f"fixture={cgmes_path}")
    print(f"boundary={boundary_path}")
    print(f"export={export_path}")
    print(f"buses={len(circuit_1.buses)}")


if __name__ == "__main__":
    main()
