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


def test_opf():
    fname = os.path.join('data', 'grids', 'IEEE39_1W.gridcal')
    print('Reading...')
    main_circuit = FileOpen(fname).open()
    print('Running OPF...', '')
    opf_options = OptimalPowerFlowOptions(verbose=False,
                                          solver=SolverType.DC_OPF)
    opf = OptimalPowerFlowDriver(grid=main_circuit, options=opf_options)
    opf.run()


if __name__ == '__main__':
    test_opf()
