# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import os
from VeraGridEngine.api import *
from VeraGridEngine.Utils.zip_file_mgmt import open_data_frame_from_zip


def test_cpf():
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(SolverType.NR, verbose=0, control_q=False)

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

    vc = ContinuationPowerFlowDriver(grid=main_circuit,
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
