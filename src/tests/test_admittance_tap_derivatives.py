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
from GridCalEngine.enumerations import TransformerControlType
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import ac_optimal_power_flow, NonlinearOPFResults
from trunk.acopf.acopf_admittance_tap_derivation import (compute_finitediff_admittances,
                                                         compute_finitediff_admittances_2dev,
                                                         compute_analytic_admittances,
                                                         compute_analytic_admittances_2dev)





def case_3bus():
    """

    :return:
    """

    grid = gce.MultiCircuit()

    b1 = gce.Bus(is_slack=True)
    b2 = gce.Bus()
    b3 = gce.Bus()

    grid.add_bus(b1)
    grid.add_bus(b2)
    grid.add_bus(b3)

    # grid.add_line(gce.Line(bus_from=b1, bus_to=b2, name='line 1-2', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b2, bus_to=b3, name='line 2-3', r=0.001, x=0.05, rate=100))
    # grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='line 3-1_1', r=0.001, x=0.05, rate=100))
    # grid.add_line(Line(bus_from=b3, bus_to=b1, name='line 3-1_2', r=0.001, x=0.05, rate=100))

    grid.add_load(b3, gce.Load(name='L3', P=50, Q=20))
    grid.add_generator(b1, gce.Generator('G1', vset=1.00, Cost=1.0, Cost2=2.0))
    grid.add_generator(b2, gce.Generator('G2', P=10, vset=0.995, Cost=1.0, Cost2=3.0))

    tr1 = gce.Transformer2W(b1, b2, 'Trafo1', control_mode=TransformerControlType.Pf,
                            tap_module=1.1, tap_phase=0.02, r=0.001, x=0.05)
    grid.add_transformer2w(tr1)

    tr2 = gce.Transformer2W(b3, b1, 'Trafo1', control_mode=TransformerControlType.PtQt,
                            tap_module=1.05, tap_phase=-0.02, r=0.001, x=0.05)
    grid.add_transformer2w(tr2)

    nc = compile_numerical_circuit_at(circuit=grid)

    return nc

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

    return nc


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


def case_pegase89() -> NonlinearOPFResults:
    """
    Pegase89
    """
    cwd = os.getcwd()
    print(cwd)
    # Go back two directories
    new_directory = os.path.abspath(os.path.join(cwd, '..', '..'))
    file_path = os.path.join(new_directory, 'Grids_and_profiles', 'grids', 'case89pegase.m')

    grid = gce.FileOpen(file_path).open()
    nc = gce.compile_numerical_circuit_at(grid)

    return nc


def test_case_3bus():

    nc = case_3bus()

    A, B, C, D, E, F = compute_analytic_admittances(nc)
    A_, B_, C_, D_, E_, F_ = compute_finitediff_admittances(nc)

    G, H, I, J, K, L, M, N, O, P, Q, R = compute_analytic_admittances_2dev(nc)
    G_, H_, I_, J_, K_, L_, M_, N_, O_, P_, Q_, R_ = compute_finitediff_admittances_2dev(nc)

    assert np.allclose(A.toarray(), A_.toarray(), atol=1e-2)
    assert np.allclose(B.toarray(), B_.toarray(), atol=1e-2)
    assert np.allclose(C.toarray(), C_.toarray(), atol=1e-2)
    assert np.allclose(D.toarray(), D_.toarray(), atol=1e-2)
    assert np.allclose(E.toarray(), E_.toarray(), atol=1e-2)
    assert np.allclose(F.toarray(), F_.toarray(), atol=1e-2)
    assert np.allclose(G.toarray(), G_.toarray(), atol=1e-2)
    assert np.allclose(H.toarray(), H_.toarray(), atol=1e-2)
    assert np.allclose(I.toarray(), I_.toarray(), atol=1e-2)
    assert np.allclose(J.toarray(), J_.toarray(), atol=1e-2)
    assert np.allclose(K.toarray(), K_.toarray(), atol=1e-2)
    assert np.allclose(L.toarray(), L_.toarray(), atol=1e-2)
    assert np.allclose(M.toarray(), M_.toarray(), atol=1e-2)
    assert np.allclose(N.toarray(), N_.toarray(), atol=1e-2)
    assert np.allclose(O.toarray(), O_.toarray(), atol=1e-2)
    assert np.allclose(P.toarray(), P_.toarray(), atol=1e-2)
    assert np.allclose(Q.toarray(), Q_.toarray(), atol=1e-2)
    assert np.allclose(R.toarray(), R_.toarray(), atol=1e-2)


def test_pegase89():

    nc = case_pegase89()

    A, B, C, D, E, F = compute_analytic_admittances(nc)
    A_, B_, C_, D_, E_, F_ = compute_finitediff_admittances(nc)

    G, H, I, J, K, L, M, N, O, P, Q, R = compute_analytic_admittances_2dev(nc)
    G_, H_, I_, J_, K_, L_, M_, N_, O_, P_, Q_, R_ = compute_finitediff_admittances_2dev(nc)

    assert np.allclose(A.toarray(), A_.toarray(), atol=1e-2)
    assert np.allclose(B.toarray(), B_.toarray(), atol=1e-2)
    assert np.allclose(C.toarray(), C_.toarray(), atol=1e-2)
    assert np.allclose(D.toarray(), D_.toarray(), atol=1e-2)
    assert np.allclose(E.toarray(), E_.toarray(), atol=1e-2)
    assert np.allclose(F.toarray(), F_.toarray(), atol=1e-2)
    assert np.allclose(G.toarray(), G_.toarray(), atol=1e-2)
    assert np.allclose(H.toarray(), H_.toarray(), atol=1e-2)
    assert np.allclose(I.toarray(), I_.toarray(), atol=1e-2)
    assert np.allclose(J.toarray(), J_.toarray(), atol=1e-2)
    assert np.allclose(K.toarray(), K_.toarray(), atol=1e-2)
    assert np.allclose(L.toarray(), L_.toarray(), atol=1e-2)
    assert np.allclose(M.toarray(), M_.toarray(), atol=1e-2)
    assert np.allclose(N.toarray(), N_.toarray(), atol=1e-2)
    assert np.allclose(O.toarray(), Q_.toarray(), atol=1e-2)
    assert np.allclose(P.toarray(), P_.toarray(), atol=1e-2)
    assert np.allclose(Q.toarray(), Q_.toarray(), atol=1e-2)
    assert np.allclose(R.toarray(), R_.toarray(), atol=1e-2)


# pass


#def test_ieee14():


#def test_pegase89():
