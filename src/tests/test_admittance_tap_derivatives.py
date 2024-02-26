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
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at
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


def case_5bus():
    """
    Grid from Lynn Powel's book
    """
    # declare a circuit object
    grid = gce.MultiCircuit()

    # Add the buses and the generators and loads attached
    bus1 = gce.Bus('Bus 1', vnom=20)
    # bus1.is_slack = True  # we may mark the bus a slack
    grid.add_bus(bus1)

    # add a generator to the bus 1
    gen1 = gce.Generator('Slack Generator', vset=1.05, Pmin=0, Pmax=1000,
                         Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)

    grid.add_generator(bus1, gen1)

    # add bus 2 with a load attached
    bus2 = gce.Bus('Bus 2', vnom=20)
    grid.add_bus(bus2)
    grid.add_load(bus2, gce.Load('load 2', P=40, Q=20))

    # add bus 3 with a load attached
    bus3 = gce.Bus('Bus 3', vnom=20)
    grid.add_bus(bus3)
    grid.add_load(bus3, gce.Load('load 3', P=25, Q=15))

    # add bus 4 with a load attached
    bus4 = gce.Bus('Bus 4', vnom=20)
    grid.add_bus(bus4)
    grid.add_load(bus4, gce.Load('load 4', P=40, Q=20))

    # add bus 5 with a load attached
    bus5 = gce.Bus('Bus 5', vnom=20)
    grid.add_bus(bus5)
    grid.add_load(bus5, gce.Load('load 5', P=50, Q=20))

    # add Lines connecting the buses
    #grid.add_line(gce.Line(bus1, bus2, 'line 1-2', r=0.05, x=0.11, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus1, bus3, 'line 1-3', r=0.05, x=0.11, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus1, bus5, 'line 1-5', r=0.03, x=0.08, b=0.02, rate=1000))

    tr1 = gce.Transformer2W(bus1, bus2, 'Trafo1', control_mode=TransformerControlType.fixed,
                            tap_module=1.1, tap_phase=0.02, r=0.05, x=0.11, b=0.02)
    grid.add_transformer2w(tr1)
    tr2 = gce.Transformer2W(bus2, bus3, 'Trafo2', control_mode=TransformerControlType.fixed,
                            tap_module=0.98, tap_phase=-0.02, r=0.04, x=0.09, b=0.02)
    grid.add_transformer2w(tr2)
    tr3 = gce.Transformer2W(bus2, bus5, 'Trafo3', control_mode=TransformerControlType.fixed,
                            tap_module=1.02, tap_phase=-0.04, r=0.04, x=0.09, b=0.02)
    grid.add_transformer2w(tr3)
    tr4 = gce.Transformer2W(bus3, bus4, 'Trafo4', control_mode=TransformerControlType.Pf,
                            tap_module=1.05, tap_phase=0.04, r=0.06, x=0.13, b=0.03)
    grid.add_transformer2w(tr4)
    tr5 = gce.Transformer2W(bus4, bus5, 'Trafo5', control_mode=TransformerControlType.fixed,
                            tap_module=0.97, tap_phase=-0.01, r=0.04, x=0.09, b=0.02)
    grid.add_transformer2w(tr5)

    #grid.add_line(gce.Line(bus2, bus3, 'line 2-3', r=0.04, x=0.09, b=0.02, rate=1000))
    #grid.add_line(gce.Line(bus2, bus5, 'line 2-5', r=0.04, x=0.09, b=0.02, rate=1000))
    #grid.add_line(gce.Line(bus3, bus4, 'line 3-4', r=0.06, x=0.13, b=0.03, rate=1000))
    #grid.add_line(gce.Line(bus4, bus5, 'line 4-5', r=0.04, x=0.09, b=0.02, rate=1000))

    nc = gce.compile_numerical_circuit_at(grid)

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
    for l in grid.get_transformers2w():

        l.control_mode = TransformerControlType.PtQt

    nc = gce.compile_numerical_circuit_at(grid)

    return nc


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
    grid.get_transformers2w()[3].control_mode = TransformerControlType.PtQt
    grid.get_transformers2w()[7].control_mode = TransformerControlType.PtQt
    grid.get_transformers2w()[18].control_mode = TransformerControlType.Vt
    grid.get_transformers2w()[21].control_mode = TransformerControlType.PtQt
    grid.get_transformers2w()[36].control_mode = TransformerControlType.Pf

    nc = gce.compile_numerical_circuit_at(grid)

    return nc


def test_case_3bus():

    nc = case_3bus()

    A, B, C, D, E, F = compute_analytic_admittances(nc)
    A_, B_, C_, D_, E_, F_ = compute_finitediff_admittances(nc)

    G, H, I, J, K, L, M, N, O, P, Q, R = compute_analytic_admittances_2dev(nc)
    G_, H_, I_, J_, K_, L_, M_, N_, O_, P_, Q_, R_ = compute_finitediff_admittances_2dev(nc)

    assert np.allclose(A.toarray(), A_.toarray(), atol=1e-1)
    assert np.allclose(B.toarray(), B_.toarray(), atol=1e-1)
    assert np.allclose(C.toarray(), C_.toarray(), atol=1e-1)
    assert np.allclose(D.toarray(), D_.toarray(), atol=1e-1)
    assert np.allclose(E.toarray(), E_.toarray(), atol=1e-1)
    assert np.allclose(F.toarray(), F_.toarray(), atol=1e-1)
    assert np.allclose(G.toarray(), G_.toarray(), atol=1e-1)
    assert np.allclose(H.toarray(), H_.toarray(), atol=1e-1)
    assert np.allclose(I.toarray(), I_.toarray(), atol=1e-1)
    assert np.allclose(J.toarray(), J_.toarray(), atol=1e-1)
    assert np.allclose(K.toarray(), K_.toarray(), atol=1e-1)
    assert np.allclose(L.toarray(), L_.toarray(), atol=1e-1)
    assert np.allclose(M.toarray(), M_.toarray(), atol=1e-1)
    assert np.allclose(N.toarray(), N_.toarray(), atol=1e-1)
    assert np.allclose(O.toarray(), O_.toarray(), atol=1e-1)
    assert np.allclose(P.toarray(), P_.toarray(), atol=1e-1)
    assert np.allclose(Q.toarray(), Q_.toarray(), atol=1e-1)
    assert np.allclose(R.toarray(), R_.toarray(), atol=1e-1)


def test_case_5bus():

    nc = case_5bus()

    A, B, C, D, E, F = compute_analytic_admittances(nc)
    A_, B_, C_, D_, E_, F_ = compute_finitediff_admittances(nc)

    G, H, I, J, K, L, M, N, O, P, Q, R = compute_analytic_admittances_2dev(nc)
    G_, H_, I_, J_, K_, L_, M_, N_, O_, P_, Q_, R_ = compute_finitediff_admittances_2dev(nc)

    assert np.allclose(A.toarray(), A_.toarray(), atol=1e-1)
    assert np.allclose(B.toarray(), B_.toarray(), atol=1e-1)
    assert np.allclose(C.toarray(), C_.toarray(), atol=1e-1)
    assert np.allclose(D.toarray(), D_.toarray(), atol=1e-1)
    assert np.allclose(E.toarray(), E_.toarray(), atol=1e-1)
    assert np.allclose(F.toarray(), F_.toarray(), atol=1e-1)
    assert np.allclose(G.toarray(), G_.toarray(), atol=1e-1)
    assert np.allclose(H.toarray(), H_.toarray(), atol=1e-1)
    assert np.allclose(I.toarray(), I_.toarray(), atol=1e-1)
    assert np.allclose(J.toarray(), J_.toarray(), atol=1e-1)
    assert np.allclose(K.toarray(), K_.toarray(), atol=1e-1)
    assert np.allclose(L.toarray(), L_.toarray(), atol=1e-1)
    assert np.allclose(M.toarray(), M_.toarray(), atol=1e-1)
    assert np.allclose(N.toarray(), N_.toarray(), atol=1e-1)
    assert np.allclose(O.toarray(), O_.toarray(), atol=1e-1)
    assert np.allclose(P.toarray(), P_.toarray(), atol=1e-1)
    assert np.allclose(Q.toarray(), Q_.toarray(), atol=1e-1)
    assert np.allclose(R.toarray(), R_.toarray(), atol=1e-1)


def test_pegase89():

    nc = case_pegase89()

    A, B, C, D, E, F = compute_analytic_admittances(nc)
    A_, B_, C_, D_, E_, F_ = compute_finitediff_admittances(nc)

    G, H, I, J, K, L, M, N, O, P, Q, R = compute_analytic_admittances_2dev(nc)
    G_, H_, I_, J_, K_, L_, M_, N_, O_, P_, Q_, R_ = compute_finitediff_admittances_2dev(nc)

    assert np.allclose(A.toarray(), A_.toarray(), atol=1e-1)
    assert np.allclose(B.toarray(), B_.toarray(), atol=1e-1)
    assert np.allclose(C.toarray(), C_.toarray(), atol=1e-1)
    assert np.allclose(D.toarray(), D_.toarray(), atol=1e-1)
    assert np.allclose(E.toarray(), E_.toarray(), atol=1e-1)
    assert np.allclose(F.toarray(), F_.toarray(), atol=1e-1)
    assert np.allclose(G.toarray(), G_.toarray(), atol=1e-1)
    assert np.allclose(H.toarray(), H_.toarray(), atol=1e-1)
    assert np.allclose(I.toarray(), I_.toarray(), atol=1e-1)
    assert np.allclose(J.toarray(), J_.toarray(), atol=1e-1)
    assert np.allclose(K.toarray(), K_.toarray(), atol=1e-1)
    assert np.allclose(L.toarray(), L_.toarray(), atol=1e-1)
    assert np.allclose(M.toarray(), M_.toarray(), atol=1e-1)
    assert np.allclose(N.toarray(), N_.toarray(), atol=1e-1)
    assert np.allclose(O.toarray(), O_.toarray(), atol=1e-1)
    assert np.allclose(P.toarray(), P_.toarray(), atol=1e-1)
    assert np.allclose(Q.toarray(), Q_.toarray(), atol=1e-1)
    assert np.allclose(R.toarray(), R_.toarray(), atol=1e-1)


def test_case14():

    nc = case14()

    A, B, C, D, E, F = compute_analytic_admittances(nc)
    A_, B_, C_, D_, E_, F_ = compute_finitediff_admittances(nc)

    G, H, I, J, K, L, M, N, O, P, Q, R = compute_analytic_admittances_2dev(nc)
    G_, H_, I_, J_, K_, L_, M_, N_, O_, P_, Q_, R_ = compute_finitediff_admittances_2dev(nc)

    assert np.allclose(A.toarray(), A_.toarray(), atol=1e-1)
    assert np.allclose(B.toarray(), B_.toarray(), atol=1e-1)
    assert np.allclose(C.toarray(), C_.toarray(), atol=1e-1)
    assert np.allclose(D.toarray(), D_.toarray(), atol=1e-1)
    assert np.allclose(E.toarray(), E_.toarray(), atol=1e-1)
    assert np.allclose(F.toarray(), F_.toarray(), atol=1e-1)
    assert np.allclose(G.toarray(), G_.toarray(), atol=1e-1)
    assert np.allclose(H.toarray(), H_.toarray(), atol=1e-1)
    assert np.allclose(I.toarray(), I_.toarray(), atol=1e-1)
    assert np.allclose(J.toarray(), J_.toarray(), atol=1e-1)
    assert np.allclose(K.toarray(), K_.toarray(), atol=1e-1)
    assert np.allclose(L.toarray(), L_.toarray(), atol=1e-1)
    assert np.allclose(M.toarray(), M_.toarray(), atol=1e-1)
    assert np.allclose(N.toarray(), N_.toarray(), atol=1e-1)
    assert np.allclose(O.toarray(), O_.toarray(), atol=1e-1)
    assert np.allclose(P.toarray(), P_.toarray(), atol=1e-1)
    assert np.allclose(Q.toarray(), Q_.toarray(), atol=1e-1)
    assert np.allclose(R.toarray(), R_.toarray(), atol=1e-1)
# pass


#def test_ieee14():


#def test_pegase89():
