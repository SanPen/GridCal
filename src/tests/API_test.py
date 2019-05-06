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

from GridCal.Engine.IO.file_handler import *
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import ReactivePowerControlMode
from GridCal.Engine.Simulations.ShortCircuit.short_circuit_driver import *
from GridCal.Engine.Simulations.PowerFlow.time_series_driver import *
from GridCal.Engine.Simulations.OPF.opf_driver import *
from GridCal.Engine.Simulations.OPF.opf_time_series_driver import *
from GridCal.Engine.Simulations.ContinuationPowerFlow.voltage_collapse_driver import *
from GridCal.Engine.Simulations.Stochastic.monte_carlo_driver import *
from GridCal.Engine.Simulations.Stochastic.lhs_driver import *
from GridCal.Engine.Simulations.Stochastic.blackout_driver import *
from GridCal.Engine.Simulations.Optimization.optimization_driver import *

from GridCal.Engine.grid_analysis import *

if __name__ == '__main__':

    fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')

    print('Reading...')
    main_circuit = FileOpen(fname).open()
    options = PowerFlowOptions(SolverType.NR, verbose=False,
                               initialize_with_existing_solution=False,
                               multi_core=False, dispatch_storage=True,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_p=True)

    ####################################################################################################################
    # PowerFlow
    ####################################################################################################################
    print('\n\n')
    power_flow = PowerFlow(main_circuit, options)
    power_flow.run()

    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(power_flow.results.voltage))
    print('\t|Sbranch|:', abs(power_flow.results.Sbranch))
    print('\t|loading|:', abs(power_flow.results.loading) * 100)
    print('\tReport')
    print(power_flow.results.get_report_dataframe())

    ####################################################################################################################
    # Short circuit
    ####################################################################################################################
    print('\n\n')
    print('Short Circuit')
    sc_options = ShortCircuitOptions(bus_index=[16])
    sc = ShortCircuit(main_circuit, sc_options, power_flow.results)
    sc.run()

    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(main_circuit.short_circuit_results.voltage))
    print('\t|Sbranch|:', abs(main_circuit.short_circuit_results.Sbranch))
    print('\t|loading|:', abs(main_circuit.short_circuit_results.loading) * 100)

    ####################################################################################################################
    # Time Series
    ####################################################################################################################
    print('Running TS...', '')
    ts = TimeSeries(grid=main_circuit, options=options, start_=0, end_=96)
    ts.run()

    numeric_circuit = main_circuit.compile()
    ts_analysis = TimeSeriesResultsAnalysis(numeric_circuit, ts.results)

    ####################################################################################################################
    # OPF
    ####################################################################################################################
    print('Running OPF...', '')
    opf_options = OptimalPowerFlowOptions(verbose=False, load_shedding=True, generation_shedding=True,
                                          solver=SolverType.DC_OPF, realistic_results=False)
    opf = OptimalPowerFlow(grid=main_circuit, options=opf_options)
    opf.run()

    ####################################################################################################################
    # OPF Time Series
    ####################################################################################################################
    print('Running OPF-TS...', '')
    opf_options = OptimalPowerFlowOptions(verbose=False, load_shedding=False, generation_shedding=True,
                                          control_batteries=True, solver=SolverType.NELDER_MEAD_OPF, realistic_results=False)
    opf_ts = OptimalPowerFlowTimeSeries(grid=main_circuit, options=opf_options, start_=0, end_=96)
    opf_ts.run()

    ####################################################################################################################
    # Voltage collapse
    ####################################################################################################################
    vc_options = VoltageCollapseOptions()

    # just for this test
    numeric_circuit = main_circuit.compile()
    numeric_inputs = numeric_circuit.compute()
    Sbase = zeros(len(main_circuit.buses), dtype=complex)
    Vbase = zeros(len(main_circuit.buses), dtype=complex)
    for c in numeric_inputs:
        Sbase[c.original_bus_idx] = c.Sbus
        Vbase[c.original_bus_idx] = c.Vbus

    unitary_vector = -1 + 2 * np.random.random(len(main_circuit.buses))

    # unitary_vector = random.random(len(grid.buses))
    vc_inputs = VoltageCollapseInput(Sbase=Sbase,
                                     Vbase=Vbase,
                                     Starget=Sbase * (1+unitary_vector))
    vc = VoltageCollapse(circuit=main_circuit, options=vc_options, inputs=vc_inputs)
    vc.run()
    vc.results.plot()

    ####################################################################################################################
    # Monte Carlo
    ####################################################################################################################
    print('Running MC...')
    mc_sim = MonteCarlo(main_circuit, options, mc_tol=1e-5, max_mc_iter=1000000)
    mc_sim.run()
    lst = np.array(list(range(mc_sim.results.n)), dtype=int)
    mc_sim.results.plot(ResultTypes.BusVoltageAverage, indices=lst, names=lst)

    ####################################################################################################################
    # Latin Hypercube
    ####################################################################################################################
    print('Running LHC...')
    lhs_sim = LatinHypercubeSampling(main_circuit, options, sampling_points=100)
    lhs_sim.run()

    ####################################################################################################################
    # Cascading
    ####################################################################################################################
    print('Running Cascading...')
    cascade = Cascading(main_circuit.copy(), options,
                        max_additional_islands=5,
                        cascade_type_=CascadeType.LatinHypercube,
                        n_lhs_samples_=10)
    cascade.run()

    cascade.perform_step_run()
    cascade.perform_step_run()
    cascade.perform_step_run()
    cascade.perform_step_run()

    ####################################################################################################################
    # Fuck up the voltage
    ####################################################################################################################
    print('Run optimization to f**k up the voltage')
    options = PowerFlowOptions(SolverType.LM, verbose=False, initialize_with_existing_solution=False)
    opt = Optimize(main_circuit, options, max_iter=100)
    opt.run()
    opt.plot()

    # plt.show()
    print('\nDone!')
