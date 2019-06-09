# Copyright (c) 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE_MATPOWER file.

# Copyright 1996-2015 PSERC. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file.

# Copyright (c) 2016-2017 by University of Kassel and Fraunhofer Institute for Wind Energy and
# Energy System Technology (IWES), Kassel. All rights reserved. Use of this source code is governed
# by a BSD-style license that can be found in the LICENSE file.

# The file has been modified from Pypower.
# The function mu() has been added to the solver in order to provide an optimal iteration control
#
# Copyright (c) 2018 Santiago Peñate Vera
#
# This file retains the BSD-Style license


from numpy import angle
import scipy
scipy.ALLOW_THREADS = True
import numpy as np

np.set_printoptions(precision=8, suppress=True, linewidth=320)


########################################################################################################################
#  MAIN
########################################################################################################################
if __name__ == "__main__":
    from GridCal.Engine.All import *
    from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import ContinuousNR
    import pandas as pd

    pd.set_option('display.max_rows', 500)
    pd.set_option('display.max_columns', 500)
    pd.set_option('display.width', 1000)

    grid = MultiCircuit()
    # grid.load_file('lynn5buspq.xlsx')
    # grid.load_file('IEEE30.xlsx')
    grid.load_file('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 145 Bus.xlsx')
    grid.time_profile = None
    nc = grid.compile()

    islands = nc.compute()

    circuit = islands[0]

    print('\nYbus:\n', circuit.Ybus.todense())
    print('\nYseries:\n', circuit.Yseries.todense())
    print('\nYshunt:\n', circuit.Ysh)
    print('\nSbus:\n', circuit.Sbus)
    print('\nIbus:\n', circuit.Ibus)
    print('\nVbus:\n', circuit.Vbus)
    print('\ntypes:\n', circuit.types)
    print('\npq:\n', circuit.pq)
    print('\npv:\n', circuit.pv)
    print('\nvd:\n', circuit.ref)

    import time
    print('Continuous Newton (F.Milano)')
    start_time = time.time()
    # Ybus, Sbus, V0, Ibus, pv, pq, tol, max_it=15
    V1, converged_, err, S = ContinuousNR(Ybus=circuit.Ybus,
                                          Sbus=circuit.Sbus,
                                          V0=circuit.Vbus,
                                          Ibus=circuit.Ibus,
                                          pv=circuit.pv,
                                          pq=circuit.pq,
                                          tol=1e-9,
                                          max_it=5)

    print("--- %s seconds ---" % (time.time() - start_time))
    # print_coeffs(C, W, R, X, H)

    print('error: \t', err)

    # check the HELM solution: v against the NR power flow
    print('\nNR standard')
    options = PowerFlowOptions(SolverType.IWAMOTO, verbose=False, tolerance=1e-9, control_q=False)
    power_flow = PowerFlow(grid, options)

    start_time = time.time()
    power_flow.run()
    print("--- %s seconds ---" % (time.time() - start_time))
    vnr = power_flow.results.voltage

    print('error: \t', power_flow.results.error)

    # check

    data = np.c_[np.abs(V1), np.abs(vnr), angle(V1), angle(vnr),  np.abs(V1 - vnr)]
    cols = ['|V|', '|V| benchmark', 'angle', 'angle benchmark', 'Diff']
    df = pd.DataFrame(data, columns=cols)

    print()
    print(df)