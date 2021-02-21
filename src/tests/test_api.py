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

import numpy as np

from GridCal.Engine import *


def test_api():
    fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
    print('Reading...')
    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(SolverType.NR, verbose=False,
                                  initialize_with_existing_solution=False,
                                  multi_core=False, dispatch_storage=True,
                                  control_q=ReactivePowerControlMode.NoControl,
                                  control_p=True)
    ####################################################################################################################
    # PowerFlowDriver
    ####################################################################################################################
    print('\n\n')
    power_flow = PowerFlowDriver(main_circuit, pf_options)
    power_flow.run()
    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(power_flow.results.voltage))
    print('\t|Sf|:', abs(power_flow.results.Sf))
    print('\t|loading|:', abs(power_flow.results.loading) * 100)
    print('\tReport')
    print(power_flow.results.get_report_dataframe())
    ####################################################################################################################
    # Short circuit
    ####################################################################################################################
    print('\n\n')
    print('Short Circuit')
    sc_options = ShortCircuitOptions(bus_index=[16])
    # grid, options, pf_options:, pf_results:
    sc = ShortCircuitDriver(grid=main_circuit, options=sc_options, pf_options=pf_options, pf_results=power_flow.results)
    sc.run()
    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(main_circuit.short_circuit_results.voltage))
    print('\t|Sf|:', abs(main_circuit.short_circuit_results.Sf))
    print('\t|loading|:',
          abs(main_circuit.short_circuit_results.loading) * 100)
    ####################################################################################################################
    # Time Series
    ####################################################################################################################
    print('Running TS...', '')
    ts = TimeSeries(grid=main_circuit, options=pf_options, start_=0, end_=96)
    ts.run()
    ts_numeric_circuit = compile_time_circuit(main_circuit)
    ts_analysis = TimeSeriesResultsAnalysis(ts_numeric_circuit, ts.results)
    ####################################################################################################################
    # OPF
    ####################################################################################################################
    print('Running OPF...', '')
    # opf_options = OptimalPowerFlowOptions(verbose=False,
    #                                       solver=SolverType.DC_OPF,
    #                                       mip_solver=False)
    # opf = OptimalPowerFlow(grid=main_circuit, options=opf_options)
    # opf.run()
    ####################################################################################################################
    # OPF Time Series
    ####################################################################################################################
    print('Running OPF-TS...', '')
    # opf_options = OptimalPowerFlowOptions(verbose=False,
    #                                       solver=SolverType.NELDER_MEAD_OPF,
    #                                       mip_solver=False)
    # opf_ts = OptimalPowerFlowTimeSeries(grid=main_circuit, options=opf_options,
    #                                     start_=0, end_=96)
    # opf_ts.run()
    ####################################################################################################################
    # Voltage collapse
    ####################################################################################################################
    vc_options = ContinuationPowerFlowOptions()
    # just for this test
    numeric_circuit = compile_snapshot_circuit(main_circuit)
    numeric_inputs = split_into_islands(numeric_circuit)

    Sbase = np.zeros(len(main_circuit.buses), dtype=complex)
    Vbase = np.zeros(len(main_circuit.buses), dtype=complex)
    for c in numeric_inputs:
        Sbase[c.original_bus_idx] = c.Sbus
        Vbase[c.original_bus_idx] = c.Vbus
    unitary_vector = -1 + 2 * np.random.random(len(main_circuit.buses))
    vc_inputs = ContinuationPowerFlowInput(Sbase=Sbase,
                                           Vbase=Vbase,
                                           Starget=Sbase * (1 + unitary_vector))
    vc = ContinuationPowerFlowDriver(circuit=main_circuit, options=vc_options,
                                     inputs=vc_inputs, pf_options=pf_options)
    vc.run()
    mdl = vc.results.mdl()
    # mdl.plot()
    # from matplotlib import pyplot as plt
    # plt.show()
    ####################################################################################################################
    # Monte Carlo
    ####################################################################################################################
    print('Running MC...')
    mc_sim = MonteCarlo(main_circuit, pf_options, mc_tol=1e-5,
                        max_mc_iter=1000)
    mc_sim.run()
    lst = np.array(list(range(mc_sim.results.n)), dtype=int)
    # mc_sim.results.plot(ResultTypes.BusVoltageAverage, indices=lst, names=lst)
    ####################################################################################################################
    # Latin Hypercube
    ####################################################################################################################
    print('Running LHC...')
    lhs_sim = LatinHypercubeSampling(main_circuit, pf_options,
                                     sampling_points=100)
    lhs_sim.run()
    ####################################################################################################################
    # Cascading
    ####################################################################################################################
    # print('Running Cascading...')
    # cascade = Cascading(main_circuit.copy(), pf_options,
    #                     max_additional_islands=5,
    #                     cascade_type_=CascadeType.LatinHypercube,
    #                     n_lhs_samples_=10)
    # cascade.run()
    # cascade.perform_step_run()
    # cascade.perform_step_run()
    # cascade.perform_step_run()
    # cascade.perform_step_run()


if __name__ == '__main__':
    test_api()
