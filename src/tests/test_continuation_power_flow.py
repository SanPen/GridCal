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

import numpy as np

from GridCalEngine.api import *
from tests.zip_file_mgmt import open_data_frame_from_zip


def test_cpf():
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(SolverType.NR,
                                  verbose=False,
                                  initialize_with_existing_solution=False,
                                  dispatch_storage=True,
                                  control_q=ReactivePowerControlMode.NoControl,
                                  control_p=False)

    Vmbase = open_data_frame_from_zip(file_name_zip=os.path.join('data', 'results', 'Results_IEEE39_1W.zip'),
                                      file_name='Power flow Bus voltage module.csv').values[:, 0]
    Vabase = open_data_frame_from_zip(file_name_zip=os.path.join('data', 'results', 'Results_IEEE39_1W.zip'),
                                      file_name='Power flow Bus voltage angle.csv').values[:, 0]
    Pbase = open_data_frame_from_zip(file_name_zip=os.path.join('data', 'results', 'Results_IEEE39_1W.zip'),
                                     file_name='Power flow Bus active power.csv').values[:, 0]
    Qbase = open_data_frame_from_zip(file_name_zip=os.path.join('data', 'results', 'Results_IEEE39_1W.zip'),
                                     file_name='Power flow Bus reactive power.csv').values[:, 0]

    Vbase = Vmbase * np.exp(1j * np.deg2rad(Vabase))
    Sbase = (Pbase + 1j + Qbase) / 100.0

    ####################################################################################################################
    # Voltage collapse
    ####################################################################################################################
    vc_options = ContinuationPowerFlowOptions()

    vc_inputs = ContinuationPowerFlowInput(Sbase=Sbase,
                                           Vbase=Vbase,
                                           Starget=Sbase * 2)

    vc = ContinuationPowerFlowDriver(circuit=main_circuit,
                                     options=vc_options,
                                     inputs=vc_inputs,
                                     pf_options=pf_options)
    vc.run()

    data = open_data_frame_from_zip(file_name_zip=os.path.join('data', 'results', 'Results_IEEE39_1W.zip'),
                                    file_name='Voltage collapse Bus voltage.csv')

    assert np.abs(np.abs(vc.results.voltages)[:500] - data.values[:500]).max() < 0.1

    data = open_data_frame_from_zip(file_name_zip=os.path.join('data', 'results', 'Results_IEEE39_1W.zip'),
                                    file_name='Voltage collapse Branch active power "from".csv')

    assert np.abs(np.real(vc.results.Sf)[:500] - data.values[:500]).max()


if __name__ == '__main__':
    test_cpf()
