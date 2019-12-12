from sklearn.neighbors import KNeighborsRegressor
import numpy as np

from GridCal.Engine import PowerFlowOptions, PowerFlowDriver, FileOpen, SolverType, ReactivePowerControlMode, \
    TapsControlMode, BranchImpedanceMode, SampledTimeSeries
from GridCal.Engine.Simulations.Stochastic.lhs_driver import LatinHypercubeSampling


def run(fname):

    circuit = FileOpen(fname).open()

    options = PowerFlowOptions(solver_type=SolverType.NR,
                               retry_with_other_methods=False,
                               verbose=False,
                               initialize_with_existing_solution=False,
                               tolerance=1e-4,
                               max_iter=5,
                               max_outer_loop_iter=10,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_taps=TapsControlMode.NoControl,
                               multi_core=False,
                               dispatch_storage=False,
                               control_p=False,
                               apply_temperature_correction=False,
                               branch_impedance_tolerance_mode=BranchImpedanceMode.Specified,
                               q_steepness_factor=30,
                               distributed_slack=False,
                               ignore_single_node_islands=False,
                               correction_parameter=1e-4)

    driver = SampledTimeSeries(grid=circuit, options=options, number_of_steps=100)
    driver.run()

    # compose the train set
    nc = circuit.compile()
    Pbus = nc.get_power_injections().real.T

    model = KNeighborsRegressor(n_neighbors=2)
    model.fit(driver.results.S.real, np.abs(driver.results.voltage))
    V_pred = model.predict(Pbus)

    model = KNeighborsRegressor(n_neighbors=2)
    model.fit(driver.results.S.real, driver.results.Sbranch.real)
    Sbr_pred = model.predict(Pbus)

    return V_pred, Sbr_pred


if __name__ == '__main__':
    from matplotlib import pyplot as plt
    from GridCal.Engine import FileOpen, SolverType, TimeSeries

    # run('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/lynn5buspv.xlsx')
    # run('/home/santi/Descargas/Equivalent.gridcal')
    fname = r'C:\Users\PENVERSA\Git\GridCal\Grids_and_profiles\grids\IEEE39_1W.gridcal'

    # predict using LHS
    print('Running LHS TS...')
    Vpred, Sbrpred = run(fname)

    print('Running TS...')
    main_circuit = FileOpen(fname).open()
    pf_options_ = PowerFlowOptions(solver_type=SolverType.NR)
    ts_driver = TimeSeries(grid=main_circuit, options=pf_options_)
    ts_driver.run()

    print('Plotting...')
    fig = plt.figure()
    ax1 = fig.add_subplot(221)
    ax1.set_title('Newton-Raphson based flow')
    ax1.plot(ts_driver.results.Sbranch.real)

    ax2 = fig.add_subplot(222)
    ax2.set_title('PTDF based flow')
    ax2.plot(Sbrpred)

    ax3 = fig.add_subplot(223)
    ax3.set_title('Difference')
    diff = ts_driver.results.Sbranch.real - Sbrpred
    ax3.plot(diff)

    fig2 = plt.figure()
    ax1 = fig2.add_subplot(221)
    ax1.set_title('Newton-Raphson based voltage')
    ax1.plot(np.abs(ts_driver.results.voltage))

    ax2 = fig2.add_subplot(222)
    ax2.set_title('PTDF based voltage')
    ax2.plot(Vpred)

    ax3 = fig2.add_subplot(223)
    ax3.set_title('Difference')
    diff = np.abs(ts_driver.results.voltage) - Vpred
    ax3.plot(diff)

    plt.show()