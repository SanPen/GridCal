# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
import pandas as pd
import numpy as np

from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver


def test_ieee_grids():
    """
    Checks the .RAW files of IEEE grids against the PSS/e results
    This test checks 2 things:
    - PSS/e import fidelity
    - PSS/e vs GridCal results
    :return: Nothing if ok, fails if not
    """

    files = [
        ('IEEE 14 bus.raw', 'IEEE 14 bus.sav.xlsx'),
        ('IEEE 30 bus.raw', 'IEEE 30 bus.sav.xlsx'),
        ('IEEE 118 Bus v2.raw', 'IEEE 118 Bus.sav.xlsx'),
    ]

    for solver_type in [SolverType.NR, SolverType.IWAMOTO, SolverType.LM, SolverType.FASTDECOUPLED]:

        print(solver_type)

        options = PowerFlowOptions(solver_type,
                                   verbose=False,
                                   initialize_with_existing_solution=False,
                                   multi_core=False,
                                   dispatch_storage=True,
                                   control_q=ReactivePowerControlMode.NoControl,
                                   control_p=True,
                                   retry_with_other_methods=False)

        for f1, f2 in files:
            print(f1, end=' ')

            fname = os.path.join('data', 'grids', 'RAW', f1)
            main_circuit = FileOpen(fname).open()
            power_flow = PowerFlowDriver(main_circuit, options)
            power_flow.run()

            # load the associated results file
            df_v = pd.read_excel(os.path.join('data', 'results', f2), sheet_name='Vabs', index_col=0)
            df_p = pd.read_excel(os.path.join('data', 'results', f2), sheet_name='Pbranch', index_col=0)

            v_gc = np.abs(power_flow.results.voltage)
            v_psse = df_v.values[:, 0]
            p_gc = power_flow.results.Sf.real
            p_psse = df_p.values[:, 0]

            # br_codes = [e.code for e in main_circuit.get_branches_wo_hvdc()]
            # p_gc_df = pd.DataFrame(data=p_gc, columns=[0], index=br_codes)
            # pf_diff_df = p_gc_df - df_p

            v_ok = np.allclose(v_gc, v_psse, atol=1e-2)
            flow_ok = np.allclose(p_gc, p_psse, atol=1e-0)
            # flow_ok = (np.abs(pf_diff_df.values) < 1e-3).all()

            if not v_ok:
                print('power flow voltages test for {} failed'.format(fname))
            if not flow_ok:
                print('power flow flows test for {} failed'.format(fname))

            assert v_ok
            assert flow_ok

        print(solver_type, 'ok')


def test_dc_pf_ieee14():
    """
    Test the DC power flow with tap module
    :return:
    """
    options = PowerFlowOptions(SolverType.DC,
                               verbose=False,
                               initialize_with_existing_solution=False,
                               multi_core=False,
                               dispatch_storage=True,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_p=True,
                               retry_with_other_methods=False)

    fname = os.path.join('data', 'grids', 'case14.m')
    main_circuit = FileOpen(fname).open()
    power_flow = PowerFlowDriver(main_circuit, options)
    power_flow.run()

    # Data from Matpower 8
    Pf_test = np.array([147.8386,
                        71.1614,
                        70.0146,
                        55.1519,
                        40.9721,
                        -24.1854,
                        -61.7465,
                        6.7283,
                        7.6074,
                        17.2513,
                        0,
                        28.3612,
                        5.7717,
                        9.6413,
                        -3.2283,
                        1.5074,
                        5.2587,
                        28.3612,
                        16.5518,
                        42.7870,
                        ])

    assert np.allclose(power_flow.results.Sf.real, Pf_test, atol=1e-3)


def test_dc_pf_ieee14_ps():
    """
    Test the DC power flow with phase shifter and tap module
    :return:
    """
    options = PowerFlowOptions(SolverType.DC,
                               verbose=False,
                               initialize_with_existing_solution=False,
                               multi_core=False,
                               dispatch_storage=True,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_p=True,
                               retry_with_other_methods=False)

    fname = os.path.join('data', 'grids', 'case14_ps.m')
    main_circuit = FileOpen(fname).open()
    power_flow = PowerFlowDriver(main_circuit, options)
    power_flow.run()

    # Data from Matpower 8
    Pf_test = np.array([141.7788,
                        77.2212,
                        64.8753,
                        44.3963,
                        50.8072,
                        -29.3247,
                        23.8991,
                        67.8736,
                        16.5880,
                        48.6659,
                        0,
                        -97.1080,
                        -55.3736,
                        -30.7538,
                        -64.3736,
                        10.4880,
                        45.6538,
                        -97.1080,
                        40.4806,
                        144.3275,
                        ])

    assert np.allclose(power_flow.results.Sf.real, Pf_test, atol=1e-3)


if __name__ == '__main__':
    test_ieee_grids()
