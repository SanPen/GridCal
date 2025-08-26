# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os

import numpy as np
from GridCalEngine.IO.cim.cgmes.cgmes_enums import CgmesProfileType
from GridCalEngine.IO.file_handler import FileSavingOptions, FileOpenOptions, FileSave
from GridCalEngine.Simulations import PowerFlowOptions
from GridCalEngine.Simulations.results_template import DriverToSave
from GridCalEngine.enumerations import CGMESVersions, SolverType, SimulationTypes
from GridCalEngine.basic_structures import Logger
import GridCalEngine.api as gce


import_path = "/home/santi/Escritorio/Redes/CGMES/wrong_round_trip_example/DACF_20250216_00_IGM_35.raw"
export_fname = "/home/santi/Escritorio/Redes/CGMES/wrong_round_trip_example/DACF_20250216_00_IGM_35_cgmes_from_gridcal.zip"
boundary_set = "/home/santi/Escritorio/Redes/CGMES/wrong_round_trip_example/20241201T0000Z__ENTSOE_BD.zip"
logger_result_file = "/home/santi/Escritorio/Redes/CGMES/wrong_round_trip_example/gridcal_comparison_logger.xlsx"

# Open -----------------------------------------------------------------------------------------------------------------
print("Processing raw file ...")
logger = Logger()
# CGMES model import to MultiCircuit
fileOpenOptions = FileOpenOptions(cgmes_map_areas_like_raw=True)

circuit = gce.FileOpen(file_name=import_path, options=fileOpenOptions).open()
nc_1 = gce.compile_numerical_circuit_at(circuit)

# Set the bus numbers for PSSe
for i, bus in enumerate(circuit.buses):
    bus.code = f"{i + 1}"

# run power flow
pf_options = PowerFlowOptions()
pf_res_1 = gce.power_flow(circuit, pf_options)

pf_session_data = DriverToSave(name="powerflow results",
                               tpe=SimulationTypes.PowerFlow_run,
                               results=pf_res_1,
                               logger=logger)

# Export ---------------------------------------------------------------------------------------------------------------
print("Exporting ...")
# save the grid in CGMES mode
gce.save_cgmes_file(grid=circuit,
                    filename=export_fname,
                    cgmes_boundary_set_path=boundary_set,
                    cgmes_version=CGMESVersions.v2_4_15,
                    pf_results=pf_res_1)

# Round trip -----------------------------------------------------------------------------------------------------------
print("Opening the saved cgmes file ...")
circuit_2 = gce.FileOpen(file_name=export_fname, options=FileOpenOptions()).open()
nc_2 = gce.compile_numerical_circuit_at(circuit_2)
pf_res_2 = gce.power_flow(circuit_2, pf_options)


ok, logger = circuit.compare_circuits(circuit_2)
if not ok:
    logger.print()
    logger.to_xlsx(logger_result_file)

# ok, logger = nc_1.compare(nc_2=nc_2, tol=1e-6)
# !!! ------------------------------------------------------------
#
# Due to different modelling in RAW nad CGMES instead of comparing numerical circuits,
# electrical arrays and power flow results are compared
#
# !!! ------------------------------------------------------------

# Comparing ------------------------------------------------------------------------------------------------------------
# print("Comparing ...")
# # Compare Y and S arrays
# ADM_1 = nc_1.get_admittance_matrices().Ybus.toarray()
# ADM_2 = nc_2.get_admittance_matrices().Ybus.toarray()
# adm_ok = np.allclose(ADM_1, ADM_2, atol=1e-5)
# if adm_ok:
#     print("\nAdmitance Ybus matrices are the same!")
# else:
#     print("\nAdmittance Ybus matrices are NOT the same!")
#     print(ADM_1)
#     print(ADM_2)
#
# # Compare power flow voltages
# pf_ok = np.allclose(np.abs(pf_res_1.voltage), np.abs(pf_res_2.voltage), atol=1e-5)
# if pf_ok:
#     print("\nPower flow results are the same!")
# else:
#     print("\nPower flow results are NOT the same!")
#     print(np.abs(pf_res_1.voltage))
#     print(np.abs(pf_res_2.voltage))
