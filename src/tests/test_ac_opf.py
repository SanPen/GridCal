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
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import ac_optimal_power_flow, NonlinearOPFResults


def case9() -> NonlinearOPFResults:
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
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, tolerance=1e-8)
    return ac_optimal_power_flow(nc=nc, pf_options=pf_options)


def case14() -> NonlinearOPFResults:
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
    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, tolerance=1e-8)
    return ac_optimal_power_flow(nc=nc, pf_options=pf_options)


def test_ieee9():
    vm_test = [1.09995, 1.097362, 1.086627, 1.094186, 1.084424, 1.099999, 1.089488, 1.099999, 1.071731]
    va_test = [0.0, 0.0854008, 0.05670578, -0.0429894, -0.0695051, 0.0105133, -0.0208879, 0.0157974, -0.0805577]
    Pg_test = [0.897986, 1.343206, 0.941874]
    Qg_test = [0.129387, 0.00047729, -0.226197]
    res = case9()
    assert np.allclose(res.Vm, vm_test, atol=1e-3)
    assert np.allclose(res.Va, va_test, atol=1e-3)
    assert np.allclose(res.Pg, Pg_test, atol=1e-3)
    assert np.allclose(res.Qg, Qg_test, atol=1e-3)
    # pass


def test_ieee14():
    vm_test = [1.05999995, 1.04075308, 1.01562523, 1.01446086, 1.01636258,
               1.05999951, 1.04634682, 1.05999962, 1.043699, 1.03913656,
               1.04600928, 1.04482001, 1.0399485, 1.02388846]
    va_test = [0.0, -0.07020258, -0.17323969, -0.15123061, -0.12965054,
               -0.22146884, -0.19526525, -0.18177315, -0.22684304, -0.23095753,
               -0.22848023, -0.23619049, -0.23706053, -0.24912998]
    Pg_test = [1.943300, 0.3671917, 0.2874277, 0.00000105, 0.08495043]
    Qg_test = [0.00000288, 0.2368517, 0.2412688, 0.1154574, 0.08273013]
    res = case14()
    assert np.allclose(res.Vm, vm_test, atol=1e-3)
    assert np.allclose(res.Va, va_test, atol=1e-3)
    assert np.allclose(res.Pg, Pg_test, atol=1e-3)
    assert np.allclose(res.Qg, Qg_test, atol=1e-3)



