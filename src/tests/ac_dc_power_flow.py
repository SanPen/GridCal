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

import GridCalEngine.api as gce


def test_1():
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/fubm_caseHVDC_vt.gridcal'
    fname = os.path.join('data', 'grids', 'fubm_caseHVDC_vt.gridcal')
    grid = gce.open_file(fname)

    results = gce.power_flow(grid)

    # print(results.get_bus_df())
    # print()
    # print(results.get_branch_df())
    # print("Error:", results.error)
    vm = np.abs(results.voltage)
    expected_vm = np.array([1.010000, 1.0, 0.995883, 1.0, 1.013787, 1.02])
    assert np.allclose(vm, expected_vm, rtol=1e-4)
