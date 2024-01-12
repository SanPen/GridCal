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

import numpy as np
import GridCalEngine.api as gce
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import ac_optimal_power_flow

def test_ieee9():
    arr1 = [1.0991, 1.0974, 1.0866, 1.0935, 1.0839, 1.0999, 1.0893, 1.0999, 1.0712, 0.0853, 0.0566, -0.0431, -0.0696,
            0.0104, -0.021, 0.0157, -0.0807, 0.898, 1.3432, 0.9419, 0.1253, 0.0031, -0.2237]
    arr2 = case9()
    assert np.allclose(arr1, arr2, atol=1e-3)
    pass


def test_ieee14():
    arr1 = [ 1.06, 1.0407, 1.0155, 1.0144, 1.0163, 1.0598, 1.0462, 1.0599, 1.0435, 1.039, 1.0458, 1.0446, 1.0398,
             1.0237, -0.0702, -0.1733, -0.1512, -0.1296, -0.2214, -0.1953, -0.1819, -0.2269, -0.231, -0.2285, -0.2362,
             -0.2371, -0.2492, 1.9434, 0.3672, 0.2873, 0.0004, 0.0846, 0.0011, 0.2368, 0.2411, 0.1149, 0.0827]
    arr2 = case14()
    assert np.allclose(arr1, arr2, atol=1e-3)
    pass



def case9():

    import os
    cwd = os.getcwd()
    print(cwd)

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))
    file_path = os.path.join(new_directory, 'GridCal', 'Grids_and_profiles', 'grids', 'case9.m')

    grid = gce.FileOpen(file_path).open()
    nc = gce.compile_numerical_circuit_at(grid)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    x =  ac_optimal_power_flow(nc=nc, pf_options=pf_options, verbose=0)
    return x

def case14():

    import os
    cwd = os.getcwd()
    print(cwd)

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..', '..'))
    file_path = os.path.join(new_directory, 'GridCal', 'Grids_and_profiles', 'grids', 'case14.m')

    grid = gce.FileOpen(file_path).open()
    nc = gce.compile_numerical_circuit_at(grid)
    nc.rates[:] = 10000  # TODO: remove when the parser understands 0 rate means it is not limited, instead of 0.
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    x = ac_optimal_power_flow(nc=nc, pf_options=pf_options, verbose=0)
    return x


if __name__ == '__main__':
    test_ieee9()
    # test_ieee14()