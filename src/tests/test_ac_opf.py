# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import ac_optimal_power_flow


def case9():
    """
    Test case9 from matpower
    :return:
    """
    cwd = os.getcwd()
    print(cwd)

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..'))
    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case9.m')

    grid = gce.FileOpen(file_path).open()
    nc = gce.compile_numerical_circuit_at(grid)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    vm, va, Pg, Qg, lam_p, lam_q = ac_optimal_power_flow(nc=nc, pf_options=pf_options, verbose=0)

    return vm, va, Pg, Qg


def case14():
    """
    Test case14 from matpower
    :return:
    """
    cwd = os.getcwd()
    print(cwd)

    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..'))
    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case14.m')

    grid = gce.FileOpen(file_path).open()
    nc = gce.compile_numerical_circuit_at(grid)
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
    vm, va, Pg, Qg, lam_p, lam_q = ac_optimal_power_flow(nc=nc, pf_options=pf_options, verbose=0)

    return vm, va, Pg, Qg


def test_ieee9():
    vm_test = [1.0991, 1.0974, 1.0866, 1.0935, 1.0839, 1.0999, 1.0893, 1.0999, 1.0712]
    va_test = [0.0, 0.0853, 0.0566, -0.0431, -0.0696, 0.0104, -0.021, 0.0157, -0.0807]
    Pg_test = [0.898, 1.3432, 0.9419]
    Qg_test = [0.1253, 0.0031, -0.2237]
    vm, va, Pg, Qg = case9()
    assert np.allclose(vm, vm_test, atol=1e-3)
    assert np.allclose(va, va_test, atol=1e-3)
    assert np.allclose(Pg, Pg_test, atol=1e-3)
    assert np.allclose(Qg, Qg_test, atol=1e-3)
    # pass


def test_ieee14():
    vm_test = [1.06, 1.0407, 1.0155, 1.0144, 1.0163, 1.0598, 1.0462,
               1.0599, 1.0435, 1.039, 1.0458, 1.0446, 1.0398, 1.0237]
    va_test = [0.0, -0.0702, -0.1733, -0.1512, -0.1296, -0.2214, -0.1953,
               -0.1819, -0.2269, -0.231, -0.2285, -0.2362, -0.2371, -0.2492]
    Pg_test = [1.9434, 0.3672, 0.2873, 0.0004, 0.0846]
    Qg_test = [0.0011, 0.2368, 0.2411, 0.1149, 0.0827]
    vm, va, Pg, Qg = case14()
    assert np.allclose(vm, vm_test, atol=1e-3)
    assert np.allclose(va, va_test, atol=1e-3)
    assert np.allclose(Pg, Pg_test, atol=1e-3)
    assert np.allclose(Qg, Qg_test, atol=1e-3)



