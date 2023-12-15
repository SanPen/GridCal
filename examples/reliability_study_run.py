# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import time
from GridCalEngine.api import *

fname = os.path.join('..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')

circuit_ = FileOpen(fname).open()

# study = ReliabilityStudy(circuit=circuit_, pf_options=PowerFlowOptions())
#
# study.run()


iterator = ReliabilityIterable(grid=circuit_,
                               forced_mttf=10.0,
                               forced_mttr=1.0)

for state, pf_res in iterator:

    if sum(state) < len(state):
        print(state, "\n", np.abs(pf_res.voltage))
        time.sleep(0.1)
