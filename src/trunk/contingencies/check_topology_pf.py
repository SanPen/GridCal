# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
import numpy as np
import pandas as pd
from GridCalEngine.api import *
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
np.set_printoptions(linewidth=100000)

folder = os.path.join('..', '..', 'tests', 'data')
fname = os.path.join(folder, 'grids', 'Matpower', 'case14.m')
res_file = os.path.join(folder, 'results', 'IEEE14_con_results_matpower.xlsx')

main_circuit = FileOpen(fname).open()
nc = compile_numerical_circuit_at(main_circuit, t_idx=None)
pf_options = PowerFlowOptions(SolverType.NR, retry_with_other_methods=False, verbose=2)

vm_df = pd.read_excel(res_file, sheet_name='Vm', index_col=0)
va_df = pd.read_excel(res_file, sheet_name='Va', index_col=0)
Pf_df = pd.read_excel(res_file, sheet_name='Pf', index_col=0)
Qf_df = pd.read_excel(res_file, sheet_name='Qf', index_col=0)

for k in [2]:  # range(nc.passive_branch_data.nelm)
    nc.passive_branch_data.active[k] = 0

    res = multi_island_pf_nc(nc=nc, options=pf_options)

    try:
        vm_expected = vm_df.values[:, k]
        va_expected = va_df.values[:, k]
        vm = np.abs(res.voltage)
        va = np.angle(res.voltage, deg=True)

        assert np.allclose(vm, vm_expected, atol=1e-3)
        assert np.allclose(va, va_expected, atol=1e-3)
    except AttributeError:
        print()

    nc.passive_branch_data.active[k] = 1
