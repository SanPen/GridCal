import os

import numpy as np

from GridCalEngine.IO import FileSave
from GridCalEngine.Simulations import PowerFlowOptions
from GridCalEngine.enumerations import SimulationTypes
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Simulations.results_template import DriverToSave
from GridCalEngine.IO.file_handler import FileSavingOptions
import GridCalEngine.api as gc


def run_import_export_test(import_path: str, export_fname: str):
    logger = Logger()
    # CGMES model import to MultiCircuit
    circuit = gc.open_file(import_path)

    # pf_options = PowerFlowOptions()
    pf_results = gc.power_flow(circuit)

    pf_session_data = DriverToSave(name="powerflow results",
                                   tpe=SimulationTypes.PowerFlow_run,
                                   results=pf_results,
                                   logger=logger)
    options = FileSavingOptions()
    options.sessions_data.append(pf_session_data)

    raw_export = FileSave(circuit=circuit,
                          file_name=export_fname,
                          options=options)
    raw_export.save_raw()

    circuit2 = gc.open_file(export_fname)
    # compare_inputs(circuit, circuit2)

    ok, logger = circuit.compare_circuits(circuit2)

    if not ok:
        logger.print()

    assert ok


def test_raw_roundtrip():
    """

    :return:
    """
    script_path = os.path.abspath(__file__)
    # test_grid_name = 'IEEE 14 bus.raw'
    test_grid_name = 'IEEE 30 bus.raw'

    raw_relative_path = os.path.join('..', 'data', 'grids', 'RAW', test_grid_name)
    raw_path = os.path.abspath(os.path.join(os.path.dirname(script_path), raw_relative_path))

    export_relative_path = os.path.join('export_result', test_grid_name)
    export_name = os.path.abspath(os.path.join(os.path.dirname(script_path), export_relative_path))
    if not os.path.exists(os.path.dirname(export_name)):
        os.makedirs(os.path.dirname(export_name))

    run_import_export_test(import_path=raw_path, export_fname=export_name)
