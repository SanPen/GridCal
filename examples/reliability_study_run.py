# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import os
import time
from VeraGridEngine.api import *

fname = os.path.join('..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')

circuit_ = FileOpen(fname).open()

nc = compile_numerical_circuit_at(circuit_)

iterator = ReliabilityIterable(grid=circuit_,
                               forced_mttf=10.0,
                               forced_mttr=1.0)

for state, pf_res in iterator:

    if sum(state) < len(state):

        nc.passive_branch_data.active = state

        print(state, "\n", np.abs(pf_res.voltage))
        time.sleep(0.1)
