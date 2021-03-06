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

from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver


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

    for solver_type in [SolverType.NR, SolverType.IWAMOTO, SolverType.LM]:

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

            fname = os.path.join('data', 'grids', f1)
            main_circuit = FileOpen(fname).open()
            power_flow = PowerFlowDriver(main_circuit, options)
            power_flow.run()

            # load the associated results file
            df_v = pd.read_excel(os.path.join('data', 'results',  f2), sheet_name='Vabs', index_col=0)
            df_p = pd.read_excel(os.path.join('data', 'results', f2), sheet_name='Pbranch', index_col=0)

            v_gc = np.abs(power_flow.results.voltage)
            v_psse = df_v.values[:, 0]
            p_gc = power_flow.results.Sf.real
            p_psse = df_p.values[:, 0]

            v_ok = np.allclose(v_gc, v_psse, atol=1e-3)
            flow_ok = np.allclose(p_gc, p_psse, atol=1e-0)
            assert (v_ok)
            assert (flow_ok)

        print(solver_type, 'ok')


if __name__ == '__main__':
    test_ieee_grids()
