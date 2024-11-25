import os
import pandas as pd
import numpy as np

from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
import GridCalEngine.api as gce

"""
Check that a transformer can regulate the voltage at a bus
"""
fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', '5Bus_LTC_FACTS_Fig4.7.gridcal')

grid = gce.open_file(fname)
bus_dict = grid.get_bus_index_dict()
ctrl_idx = bus_dict[grid.transformers2w[0].regulation_bus]


for control_taps_modules in [True, False]:
    for solver_type in [SolverType.NR, SolverType.LM, SolverType.PowellDogLeg]:
        options = PowerFlowOptions(solver_type,
                                   verbose=2,
                                   control_q=False,
                                   retry_with_other_methods=False,
                                   control_taps_modules=control_taps_modules,
                                   control_taps_phase=False,
                                   control_remote_voltage=False,
                                   apply_temperature_correction=False)

        results = gce.power_flow(grid, options)

        vm = np.abs(results.voltage)

        assert results.converged

        # check that the bus voltage module is the the transformer voltage set point
        ok = np.isclose(vm[ctrl_idx], grid.transformers2w[0].vset, atol=options.tolerance)

        if control_taps_modules:
            assert ok
        else:
            assert not ok
