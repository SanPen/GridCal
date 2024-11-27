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
# fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', '12Bus AC-DC test grid Raiyan_Josep.gridcal')
fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', '12Bus AC-DC Josep v4.gridcal')
# fname = os.path.join("..", "..", "..", "tests", 'data', 'grids', '12Bus AC-DC Josep v3.gridcal')

grid = gce.open_file(fname)

# # Set the controls--------------------------------------------------------------------------------------------------
#
# # DC slack & P from AC->DC to evacuate the generation
# grid.vsc_devices[0].control1 = gce.ConverterControlType.Vm_dc
# grid.vsc_devices[0].control1_val = 1.0
# grid.vsc_devices[0].control2 = gce.ConverterControlType.Pac
# grid.vsc_devices[0].control2_val = grid.generators[0].P
#
# # P from AC->DC to evacuate the generation
# grid.vsc_devices[1].control2 = gce.ConverterControlType.Pac
# grid.vsc_devices[1].control2_val = grid.generators[1].P
#
# # P DC->AC to provide the load
# grid.vsc_devices[2].control1 = gce.ConverterControlType.Pdc
# grid.vsc_devices[2].control1_val = grid.loads[0].P
#
# # P DC->AC to provide the load
# grid.vsc_devices[3].control2 = gce.ConverterControlType.Pdc
# grid.vsc_devices[3].control2_val = grid.loads[1].P
# ------------------------------------------------------------------------------------------------------------------

options = PowerFlowOptions(SolverType.NR,
                           verbose=0,
                           control_q=False,
                           retry_with_other_methods=False,
                           control_taps_phase=True,
                           control_taps_modules=True,
                           max_iter=80)

results = gce.power_flow(grid, options)

assert results.converged
