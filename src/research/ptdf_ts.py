
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn import neighbors

from GridCal.Engine import PowerFlowOptions, FileOpen, SolverType, ReactivePowerControlMode, \
    TapsControlMode, BranchImpedanceMode, TimeSeries, PtdfTimeSeries, CDF, LatinHypercubeSampling


def knn_interp(X, Y, perc):

    k_split = int(X.shape[0] * perc)
    X_train = X[:k_split]
    Y_train = Y[:k_split]
    X_test = X[k_split:]
    Y_test = Y[k_split:]

    n_neighbors = 5
    model = neighbors.KNeighborsRegressor(n_neighbors)

    print('Fitting...')
    model.fit(X_train, Y_train)

    print('Predicting...')
    Y_predict = model.predict(X_test)

    print('Scoring...')
    score = model.score(X_test, Y_test)

    print('Score:', score)

    Y_predict


def run(fname):

    circuit = FileOpen(fname).open()

    pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                                  retry_with_other_methods=False,
                                  verbose=False,
                                  initialize_with_existing_solution=False,
                                  tolerance=1e-6,
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

    nc = circuit.compile_time_series()

    ts_driver = TimeSeries(circuit, pf_options)
    ts_driver.run()

    ptdf_driver = PtdfTimeSeries(circuit, pf_options, power_delta=10)
    ptdf_driver.run()

    npoints = int(len(circuit.time_profile) * 1)
    lhs_driver = LatinHypercubeSampling(circuit, pf_options, sampling_points=npoints)
    lhs_driver.run()

    P = nc.get_power_injections().real.T
    Q = nc.get_power_injections().imag.T
    Pbr_ts = ts_driver.results.Sbranch.real

    Pbr_ptdf = ptdf_driver.results.Sbranch.real
    P_lhs = lhs_driver.results.S_points.real
    Q_lhs = lhs_driver.results.S_points.imag
    Pbr_lhs = lhs_driver.results.Sbr_points.real

    # KNN
    n_neighbors = 3
    model = neighbors.KNeighborsRegressor(n_neighbors)
    # model.fit(P[:40], Pbr_ts[:40])
    # model.fit(P_lhs, Pbr_lhs)  # just the LHS for training
    # X = np.r_[np.c_[P_lhs, Q], np.c_[P, Q]]
    # Y = np.r_[Pbr_lhs, Pbr_ts]

    X = np.c_[P, Q][:60]
    Y = Pbr_ts[:60]

    model.fit(X, Y)  # LHS + TS for training ("dreaming")
    Pbr_knn = model.predict(np.c_[P, Q])

    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111)
    i = 10  # branch index
    ax.plot(Pbr_ts[i, :], label='Real flow', linewidth=5, c='orange')
    ax.plot(Pbr_ptdf[i, :], label='PTDF', c='b', linestyle='--')
    ax.plot(Pbr_knn[i, :], label='KNN', c='k', linestyle=':')
    ax.set_xlabel('Time')
    ax.set_ylabel('MW')
    fig.legend()
    plt.show()

if __name__ == '__main__':

    run(r'/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE_30_new.xlsx')