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
import pandas as pd
import numpy as np
from pathlib import Path

from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import \
    PowerFlowOptions, ReactivePowerControlMode, SolverType
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver


def test_power_flow():
    fname = Path(__file__).parent.parent.parent / \
            'Grids_and_profiles' / 'grids' / 'IEEE 30 Bus with storage.xlsx'

    print('Reading...')
    main_circuit = FileOpen(fname).open()
    options = PowerFlowOptions(SolverType.NR, verbose=False,
                               initialize_with_existing_solution=False,
                               multi_core=False, dispatch_storage=True,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_p=True)
    # exit()
    ####################################################################################################################
    # PowerFlowDriver
    ####################################################################################################################
    print('\n\n')
    power_flow = PowerFlowDriver(main_circuit, options)
    power_flow.run()
    print('\n\n', main_circuit.name)
    print('\t|V|:', abs(power_flow.results.voltage))
    print('\t|Sf|:', abs(power_flow.results.Sf))
    print('\t|loading|:', abs(power_flow.results.loading) * 100)
    print('\tReport')
    print(power_flow.results.get_report_dataframe())

    assert power_flow.results.error < 1e-3


def test_ieee_grids():
    """
    Checks the .RAW files of IEEE grids against the PSS/e results
    This test checks 2 things:
    - PSS/e import fidelity
    - PSS/e vs GridCal results
    :return: Nothing, fails if not ok
    """

    files = [
             ('IEEE 14 bus.raw', 'IEEE 14 bus.sav.xlsx'),
             ('IEEE 30 bus.raw', 'IEEE 30 bus.sav.xlsx'),
             ('IEEE 118 Bus v2.raw', 'IEEE 118 Bus.sav.xlsx'),
            ]

    options = PowerFlowOptions(SolverType.NR, verbose=False,
                               initialize_with_existing_solution=False,
                               multi_core=False, dispatch_storage=True,
                               control_q=ReactivePowerControlMode.NoControl,
                               control_p=True)

    for f1, f2 in files:
        print(f1, end=' ')

        fname = os.path.join('data', f1)
        main_circuit = FileOpen(fname).open()
        power_flow = PowerFlowDriver(main_circuit, options)
        power_flow.run()

        # load the associated results file
        df_v = pd.read_excel(os.path.join('data', f2), sheet_name='Vabs', index_col=0)
        df_p = pd.read_excel(os.path.join('data', f2), sheet_name='Pbranch', index_col=0)

        v_gc = np.abs(power_flow.results.voltage)
        v_psse = df_v.values[:, 0]
        p_gc = power_flow.results.Sf.real
        p_psse = df_p.values[:, 0]
        assert (np.allclose(v_gc, v_psse, atol=1e-3))
        assert (np.allclose(p_gc, p_psse, atol=1e-1))

        print('ok')


if __name__ == '__main__':
    # test_ieee_grids()
    test_power_flow()
