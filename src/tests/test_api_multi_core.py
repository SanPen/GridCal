# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import os
import time
from multiprocessing import Pool

from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import SolverType, multi_island_pf, single_island_pf
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions, PowerFlowDriver
from GridCal.Engine.Simulations.PowerFlow.time_series_driver import TimeSeriesResults


def power_flow_worker_args(args):
    """
    Power flow worker to schedule parallel power flows

    args -> t, options: PowerFlowOptions, circuit: Circuit, Vbus, Sbus, Ibus, return_dict


        **t: execution index
        **options: power flow options
        **circuit: circuit
        **Vbus: Voltages to initialize
        **Sbus: Power injections
        **Ibus: Current injections
        **return_dict: parallel module dictionary in wich to return the values
    :return:
    """
    t, options, circuit, Vbus, Sbus, Ibus, return_dict = args

    res = single_island_pf(circuit, Vbus, Sbus, Ibus, options=options, logger=list())

    return t, res


def test_api_multi_core_starmap():
    """
    Test the pool.starmap function together with GridCal
    """

    file_name = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
    batch_size = 100
    grid = FileOpen(file_name).open()
    print('\n\n', grid.name)

    options = PowerFlowOptions(SolverType.NR, verbose=False)
    power_flow = PowerFlowDriver(grid, options)
    power_flow.run()

    # create instances of the of the power flow simulation given the grid
    print('running...')

    pool = Pool()
    results = pool.starmap(multi_island_pf, [(grid, options, 0)] * batch_size)


def test_api_multi_core():
    """
    Test the pool.starmap function together with GridCal
    """

    file_name = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'IEEE39_1W.gridcal')

    grid = FileOpen(file_name).open()

    start_ = 0
    end_ = len(grid.time_profile)

    print('\n\n', grid.name)

    options = PowerFlowOptions(SolverType.NR, verbose=False)

    # create instances of the of the power flow simulation given the grid
    print('running...')

    # compile the multi-circuit
    numerical_circuit = grid.compile(use_opf_vals=False, opf_time_series_results=False)

    # perform the topological computation
    calc_inputs_dict = numerical_circuit.compute_ts(branch_tolerance_mode=options.branch_impedance_tolerance_mode,
                                                    ignore_single_node_islands=options.ignore_single_node_islands)

    pool = Pool()

    # for each partition of the profiles...
    for t_key, calc_inputs in calc_inputs_dict.items():

        # For every island, run the time series
        for island_index, calculation_input in enumerate(calc_inputs):

            # find the original indices
            bus_original_idx = calculation_input.original_bus_idx
            branch_original_idx = calculation_input.original_branch_idx

            # if there are valid profiles...
            if grid.time_profile is not None:

                # declare a results object for the partition
                nt = calculation_input.ntime
                n = calculation_input.nbus
                m = calculation_input.nbr
                results = TimeSeriesResults(n, m, nt, start_, end_)
                last_voltage = calculation_input.Vbus

                return_dict = dict()
                results = list()

                # traverse the time profiles of the partition and simulate each time step
                for it, t in enumerate(calculation_input.original_time_idx):

                    if (t >= start_) and (t < end_):
                        # set the power values
                        # if the storage dispatch option is active, the batteries power is not included
                        # therefore, it shall be included after processing
                        Ysh = calculation_input.Ysh_prof[:, it]
                        Ibus = calculation_input.Ibus_prof[:, it]
                        Sbus = calculation_input.Sbus_prof[:, it]

                        args = (t, options, calculation_input, calculation_input.Vbus, Sbus, Ibus, return_dict)
                        pool.apply_async(power_flow_worker_args, (args,), callback=results.append)

                # join threads
                l = len(results)
                nt = end_ - start_
                while l < nt:
                    print(l / nt * 100, "%")
                    l = len(results)
                    time.sleep(2.0)

                print()


if __name__ == '__main__':

    test_api_multi_core()

    # test_api_multi_core_starmap()
