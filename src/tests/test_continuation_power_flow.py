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

import numpy as np

from GridCal.Engine import *


def test_cpf():
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    main_circuit = FileOpen(fname).open()
    pf_options = PowerFlowOptions(SolverType.NR, verbose=False,
                                  initialize_with_existing_solution=False,
                                  multi_core=False, dispatch_storage=True,
                                  control_q=ReactivePowerControlMode.NoControl,
                                  control_p=True)
    ####################################################################################################################
    # PowerFlowDriver
    ####################################################################################################################
    print('\n\n')
    power_flow = PowerFlowDriver(main_circuit, pf_options)
    power_flow.run()
    print(power_flow.results.get_report_dataframe())

    ####################################################################################################################
    # Voltage collapse
    ####################################################################################################################
    vc_options = ContinuationPowerFlowOptions()

    # just for this test
    numeric_circuit = compile_snapshot_circuit(main_circuit)

    vc_inputs = ContinuationPowerFlowInput(Sbase=numeric_circuit.Sbus,
                                           Vbase=power_flow.results.voltage,
                                           Starget=numeric_circuit.Sbus * 2)

    vc = ContinuationPowerFlowDriver(circuit=main_circuit,
                                     options=vc_options,
                                     inputs=vc_inputs,
                                     pf_options=pf_options)
    vc.run()
    mdl = vc.results.mdl()


if __name__ == '__main__':
    test_cpf()
