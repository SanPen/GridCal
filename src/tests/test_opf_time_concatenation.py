# GridCal
# Copyright (C) 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import os
from GridCalEngine.api import *


def test_opf_ts_batt():
    fname = os.path.join('data', 'grids', 'IEEE39_1W_batt.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()

    print('Running OPF-TS...', '')

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          multi_core=False,
                                          dispatch_storage=True,
                                          control_q=ReactivePowerControlMode.NoControl,
                                          control_p=True,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=False,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          time_grouping=TimeGrouping.Daily,
                                          mip_solver=MIPSolvers.GLOP,
                                          generate_report=True)

    # run the opf time series
    opf_ts = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit,
                                              options=opf_options,
                                              time_indices=main_circuit.get_all_time_indices())
    opf_ts.run()

    p_rise_lim = main_circuit.batteries[0].Pmax
    p_redu_lim = main_circuit.batteries[0].Pmin

    batt_energy = opf_ts.results.battery_energy[:, 0]

    tol = power_flow_options.tolerance
    # no dt calculated as it is always 1.0 hours
    for i in range(1, len(batt_energy)):
        assert batt_energy[i-1] + p_rise_lim + tol >= batt_energy[i] >= batt_energy[i-1] + p_redu_lim - tol


def test_opf_ts_hydro():
    fname = os.path.join('data', 'grids', 'IEEE39_1W_hydro.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()

    print('Running OPF-TS...', '')

    power_flow_options = PowerFlowOptions(SolverType.NR,
                                          verbose=False,
                                          initialize_with_existing_solution=False,
                                          multi_core=False,
                                          dispatch_storage=True,
                                          control_q=ReactivePowerControlMode.NoControl,
                                          control_p=True,
                                          retry_with_other_methods=False)

    opf_options = OptimalPowerFlowOptions(verbose=False,
                                          solver=SolverType.LINEAR_OPF,
                                          power_flow_options=power_flow_options,
                                          time_grouping=TimeGrouping.Daily,
                                          mip_solver=MIPSolvers.GLOP,
                                          generate_report=True)

    # run the opf time series
    opf_ts = OptimalPowerFlowTimeSeriesDriver(grid=main_circuit,
                                              options=opf_options,
                                              time_indices=main_circuit.get_all_time_indices())
    opf_ts.run()

    p_path0_max = main_circuit.fluid_paths[0].max_flow
    p_path0_min = main_circuit.fluid_paths[0].min_flow

    l_node0 = opf_ts.results.fluid_node_current_level[:, 0]

    tol = power_flow_options.tolerance
    # no dt calculated as it is always 1.0 hours
    for i in range(1, len(l_node0)):
        assert l_node0[i-1] - p_path0_max * 3600 + tol <= l_node0[i] <= l_node0[i-1] + p_path0_min * 3600 - tol
