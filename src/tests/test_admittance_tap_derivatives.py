# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import numpy as np
import VeraGridEngine.api as gce
from scipy import sparse as sp
from VeraGridEngine.enumerations import TapPhaseControl, TapModuleControl
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Simulations.OPF.ac_opf_worker import run_nonlinear_opf
from VeraGridEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions


def example_3bus_acopf():
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

    tr1 = gce.Transformer2W(b1, b2, 'Trafo1', tap_phase_control_mode=TapPhaseControl.Pf,
                            tap_module=1.1, tap_phase=0.02, r=0.001, x=0.05)
    grid.add_transformer2w(tr1)

    tr2 = gce.Transformer2W(b3, b1, 'Trafo1', tap_phase_control_mode=TapPhaseControl.Pf,
                            tap_module=1.05, tap_phase=-0.02, r=0.001, x=0.05)
    grid.add_transformer2w(tr2)

    nc = compile_numerical_circuit_at(circuit=grid)

    A, B, C, D, E, F = compute_analytic_admittances(nc)

    A_, B_, C_, D_, E_, F_ = compute_finitediff_admittances(nc)

    G, H, I, J, K, L, M, N, O, P, Q, R = compute_analytic_admittances_2dev(nc)

    G_, H_, I_, J_, K_, L_, M_, N_, O_, P_, Q_, R_ = compute_finitediff_admittances_2dev(nc)

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()
    # print('\n\n', grid.name)
    # print('\tConv:\n', power_flow.results.get_bus_df())
    # print('\tConv:\n', power_flow.results.get_branch_df())
    opf_options = OptimalPowerFlowOptions()

    run_nonlinear_opf(grid=grid,
                      opf_options=opf_options,
                      plot_error=True)


def compute_analytic_admittances(nc: NumericalCircuit):
    """

    :param nc:
    :return:
    """
    indices = nc.get_simulation_indices()
    k_m, k_tau, k_mtau = indices.get_branch_controls_indices()

    tapm = nc.active_branch_data.tap_module
    tapt = nc.active_branch_data.tap_angle

    Cf = nc.passive_branch_data.Cf
    Ct = nc.passive_branch_data.Ct
    ys = 1.0 / (nc.passive_branch_data.R + 1.0j * nc.passive_branch_data.X + 1e-20)

    # First partial derivative with respect to tap module
    mp = tapm[k_m]
    tau = tapt[k_m]
    ylin = ys[k_m]

    dYffdm = np.zeros(len(tapm), dtype=complex)
    dYftdm = np.zeros(len(tapm), dtype=complex)
    dYtfdm = np.zeros(len(tapm), dtype=complex)
    dYttdm = np.zeros(len(tapm), dtype=complex)

    dYffdm[k_m] = -2 * ylin / (mp * mp * mp)
    dYftdm[k_m] = ylin / (mp * mp * np.exp(-1.0j * tau))
    dYtfdm[k_m] = ylin / (mp * mp * np.exp(1.0j * tau))

    dYfdm = sp.diags(dYffdm) * Cf + sp.diags(dYftdm) * Ct
    dYtdm = sp.diags(dYtfdm) * Cf + sp.diags(dYttdm) * Ct

    dYbusdm = Cf.T * dYfdm + Ct.T * dYtdm  # Cf_m.T and Ct_m.T included earlier

    # First partial derivative with respect to tap angle
    mp = tapm[k_tau]
    tau = tapt[k_tau]
    ylin = ys[k_tau]

    dYffdt = np.zeros(len(tapm), dtype=complex)
    dYftdt = np.zeros(len(tapm), dtype=complex)
    dYtfdt = np.zeros(len(tapm), dtype=complex)
    dYttdt = np.zeros(len(tapm), dtype=complex)

    dYftdt[k_tau] = -1j * ylin / (mp * np.exp(-1.0j * tau))
    dYtfdt[k_tau] = 1j * ylin / (mp * np.exp(1.0j * tau))

    dYfdt = sp.diags(dYffdt) * Cf + sp.diags(dYftdt) * Ct
    dYtdt = sp.diags(dYtfdt) * Cf + sp.diags(dYttdt) * Ct

    dYbusdt = Cf.T * dYfdt + Ct.T * dYtdt

    return dYbusdm, dYfdm, dYtdm, dYbusdt, dYfdt, dYtdt


def compute_finitediff_admittances(nc: NumericalCircuit, tol=1e-5):
    """

    :param nc: NumericalCircuit
    :param tol: tolerance
    :return:
    """
    indices = nc.get_simulation_indices()
    k_m, k_tau, k_mtau = indices.get_branch_controls_indices()

    # base values
    adm0 = nc.get_admittance_matrices()

    # Modify tap modules
    nc.active_branch_data.tap_module[k_m] += tol
    adm1 = nc.get_admittance_matrices()
    nc.active_branch_data.tap_module[k_m] -= tol

    dYf_dm = (adm1.Yf - adm0.Yf) / tol
    dYt_dm = (adm1.Yt - adm0.Yt) / tol
    dY_dm = (adm1.Ybus - adm0.Ybus) / tol

    # modify tap angles
    nc.active_branch_data.tap_angle[k_tau] += tol
    adm2 = nc.get_admittance_matrices()
    nc.active_branch_data.tap_angle[k_tau] -= tol

    dYf_dt = (adm2.Yf - adm0.Yf) / tol
    dYt_dt = (adm2.Yt - adm0.Yt) / tol
    dY_dt = (adm2.Ybus - adm0.Ybus) / tol

    return dY_dm, dYf_dm, dYt_dm, dY_dt, dYf_dt, dYt_dt


def compute_analytic_admittances_2dev(nc: NumericalCircuit):
    """

    :param nc:
    :return:
    """
    indices = nc.get_simulation_indices()
    k_m, k_tau, k_mtau = indices.get_branch_controls_indices()

    tapm = nc.active_branch_data.tap_module
    tapt = nc.active_branch_data.tap_angle

    Cf = nc.passive_branch_data.Cf
    Ct = nc.passive_branch_data.Ct
    ys = 1.0 / (nc.passive_branch_data.R + 1.0j * nc.passive_branch_data.X + 1e-20)

    # Second partial derivative with respect to tap module
    mp = tapm[k_m]
    tau = tapt[k_m]
    ylin = ys[k_m]

    # primitived
    dyff_dmdm = np.zeros(nc.nbr, dtype=complex)
    dyft_dmdm = np.zeros(nc.nbr, dtype=complex)
    dytf_dmdm = np.zeros(nc.nbr, dtype=complex)
    dytt_dmdm = np.zeros(nc.nbr, dtype=complex)

    dyff_dmdm[k_m] = 6 * ylin / (mp * mp * mp * mp)
    dyft_dmdm[k_m] = -2 * ylin / (mp * mp * mp * np.exp(-1.0j * tau))
    dytf_dmdm[k_m] = -2 * ylin / (mp * mp * mp * np.exp(1.0j * tau))

    dYf_dmdm = (sp.diags(dyff_dmdm) * Cf + sp.diags(dyft_dmdm) * Ct)
    dYt_dmdm = (sp.diags(dytf_dmdm) * Cf + sp.diags(dytt_dmdm) * Ct)

    dY_dmdm = (Cf.T * dYf_dmdm + Ct.T * dYt_dmdm)

    # Second partial derivative with respect to tap angle
    mp = tapm[k_tau]
    tau = tapt[k_tau]
    ylin = ys[k_tau]

    # primitives
    dyff_dtdt = np.zeros(nc.nbr, dtype=complex)
    dyft_dtdt = np.zeros(nc.nbr, dtype=complex)
    dytf_dtdt = np.zeros(nc.nbr, dtype=complex)
    dytt_dtdt = np.zeros(nc.nbr, dtype=complex)

    dyft_dtdt[k_tau] = ylin / (mp * np.exp(-1.0j * tau))
    dytf_dtdt[k_tau] = ylin / (mp * np.exp(1.0j * tau))

    dYf_dtdt = sp.diags(dyff_dtdt) * Cf + sp.diags(dyft_dtdt) * Ct
    dYt_dtdt = sp.diags(dytf_dtdt) * Cf + sp.diags(dytt_dtdt) * Ct

    dY_dtdt = Cf.T * dYf_dtdt + Ct.T * dYt_dtdt

    # Second partial derivative with respect to both tap module and angle
    mp = tapm[k_mtau]
    tau = tapt[k_mtau]
    ylin = ys[k_mtau]

    # primitives
    dyffdmdt = np.zeros(nc.nbr, dtype=complex)
    dyft_dmdt = np.zeros(nc.nbr, dtype=complex)
    dytf_dmdt = np.zeros(nc.nbr, dtype=complex)
    dyttdmdt = np.zeros(nc.nbr, dtype=complex)

    dyft_dmdt[k_mtau] = 1j * ylin / (mp * mp * np.exp(-1.0j * tau))
    dytf_dmdt[k_mtau] = -1j * ylin / (mp * mp * np.exp(1.0j * tau))

    dYf_dmdt = sp.diags(dyffdmdt) * Cf + sp.diags(dyft_dmdt) * Ct
    dYt_dmdt = sp.diags(dytf_dmdt) * Cf + sp.diags(dyttdmdt) * Ct

    dY_dmdt = Cf.T * dYf_dmdt + Ct.T * dYt_dmdt

    dYf_dtdm = dYf_dmdt.copy()
    dYt_dtdm = dYt_dmdt.copy()
    dY_dtdm = dY_dmdt.copy()

    return (dY_dmdm, dYf_dmdm, dYt_dmdm, dY_dmdt, dYf_dmdt, dYt_dmdt,
            dY_dtdm, dYf_dtdm, dYt_dtdm, dY_dtdt, dYf_dtdt, dYt_dtdt)


def compute_finitediff_admittances_2dev(nc: NumericalCircuit, tol=1e-5):
    """

    :param nc:
    :param tol:
    :return:
    """
    indices = nc.get_simulation_indices()
    k_m, k_tau, k_mtau = indices.get_branch_controls_indices()

    # Reference
    dY0_dm, dYf0_dm, dYt0_dm, dY0_dt, dYf0_dt, dYt0_dt = compute_finitediff_admittances(nc)

    # Modify the tap module
    nc.active_branch_data.tap_module[k_m] += tol
    dY_dm, dYf_dm, dYt_dm, dY_dt, dYf_dt, dYt_dt = compute_finitediff_admittances(nc)
    nc.active_branch_data.tap_module[k_m] -= tol

    dYf_dmdm = (dYf_dm - dYf0_dm) / tol
    dYt_dmdm = (dYt_dm - dYt0_dm) / tol
    dY_dmdm = (dY_dm - dY0_dm) / tol

    dYf_dtdm = (dYf_dt - dYf0_dt) / tol
    dYt_dtdm = (dYt_dt - dYt0_dt) / tol
    dY_dtdm = (dY_dt - dY0_dt) / tol

    # Modify the tap angle
    nc.active_branch_data.tap_angle[k_tau] += tol
    dY_dm, dYf_dm, dYt_dm, dY_dt, dYf_dt, dYt_dt = compute_finitediff_admittances(nc)
    nc.active_branch_data.tap_angle[k_tau] -= tol

    dYf_dmdt = (dYf_dm - dYf0_dm) / tol
    dYt_dmdt = (dYt_dm - dYt0_dm) / tol
    dY_dmdt = (dY_dm - dY0_dm) / tol

    dYf_dtdt = (dYf_dt - dYf0_dt) / tol
    dYt_dtdt = (dYt_dt - dYt0_dt) / tol
    dY_dtdt = (dY_dt - dY0_dt) / tol

    return (dY_dmdm, dYf_dmdm, dYt_dmdm, dY_dmdt, dYf_dmdt, dYt_dmdt,
            dY_dtdm, dYf_dtdm, dYt_dtdm, dY_dtdt, dYf_dtdt, dYt_dtdt)


def case_3bus() -> NumericalCircuit:
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

    tr1 = gce.Transformer2W(b1, b2, 'Trafo1', tap_phase_control_mode=TapPhaseControl.Pf,
                            tap_module=1.1, tap_phase=0.02, r=0.001, x=0.05)
    grid.add_transformer2w(tr1)

    tr2 = gce.Transformer2W(b3, b1, 'Trafo1',
                            tap_phase_control_mode=TapPhaseControl.Pt, tap_phase=-0.02,
                            tap_module_control_mode=TapModuleControl.Qt, tap_module=1.05,
                            r=0.001, x=0.05)
    grid.add_transformer2w(tr2)

    nc = compile_numerical_circuit_at(circuit=grid)

    return nc


def case_5bus() -> NumericalCircuit:
    """
    Grid from Lynn Powel's book
    """
    # declare a circuit object
    grid = gce.MultiCircuit()

    # Add the buses and the generators and loads attached
    bus1 = gce.Bus(name='Bus 1', Vnom=20)
    # bus1.is_slack = True  # we may mark the bus a slack
    grid.add_bus(bus1)

    # add a generator to the bus 1
    gen1 = gce.Generator(name='Slack Generator', vset=1.05, Pmin=0, Pmax=1000,
                         Qmin=-1000, Qmax=1000, Cost=15, Cost2=0.0)

    grid.add_generator(bus1, gen1)

    # add bus 2 with a load attached
    bus2 = gce.Bus(name='Bus 2', Vnom=20)
    grid.add_bus(bus2)
    grid.add_load(bus2, gce.Load(name='load 2', P=40, Q=20))

    # add bus 3 with a load attached
    bus3 = gce.Bus(name='Bus 3', Vnom=20)
    grid.add_bus(bus3)
    grid.add_load(bus3, gce.Load(name='load 3', P=25, Q=15))

    # add bus 4 with a load attached
    bus4 = gce.Bus(name='Bus 4', Vnom=20)
    grid.add_bus(bus4)
    grid.add_load(bus4, gce.Load('load 4', P=40, Q=20))

    # add bus 5 with a load attached
    bus5 = gce.Bus(name='Bus 5', Vnom=20)
    grid.add_bus(bus5)
    grid.add_load(bus5, gce.Load(name='load 5', P=50, Q=20))

    # add Lines connecting the buses
    # grid.add_line(gce.Line(bus1, bus2, 'line 1-2', r=0.05, x=0.11, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus1, bus3, name='line 1-3', r=0.05, x=0.11, b=0.02, rate=1000))
    grid.add_line(gce.Line(bus1, bus5, name='line 1-5', r=0.03, x=0.08, b=0.02, rate=1000))

    tr1 = gce.Transformer2W(bus1, bus2, name='Trafo1',
                            tap_module=1.1, tap_phase=0.02, r=0.05, x=0.11, b=0.02)
    grid.add_transformer2w(tr1)
    tr2 = gce.Transformer2W(bus2, bus3, name='Trafo2',
                            tap_module=0.98, tap_phase=-0.02, r=0.04, x=0.09, b=0.02)
    grid.add_transformer2w(tr2)
    tr3 = gce.Transformer2W(bus2, bus5, name='Trafo3',
                            tap_module=1.02, tap_phase=-0.04, r=0.04, x=0.09, b=0.02)
    grid.add_transformer2w(tr3)
    tr4 = gce.Transformer2W(bus3, bus4, name='Trafo4', tap_phase_control_mode=TapPhaseControl.Pf,
                            tap_module=1.05, tap_phase=0.04, r=0.06, x=0.13, b=0.03)
    grid.add_transformer2w(tr4)
    tr5 = gce.Transformer2W(bus4, bus5, name='Trafo5',
                            tap_module=0.97, tap_phase=-0.01, r=0.04, x=0.09, b=0.02)
    grid.add_transformer2w(tr5)

    # grid.add_line(gce.Line(bus2, bus3, 'line 2-3', r=0.04, x=0.09, b=0.02, rate=1000))
    # grid.add_line(gce.Line(bus2, bus5, 'line 2-5', r=0.04, x=0.09, b=0.02, rate=1000))
    # grid.add_line(gce.Line(bus3, bus4, 'line 3-4', r=0.06, x=0.13, b=0.03, rate=1000))
    # grid.add_line(gce.Line(bus4, bus5, 'line 4-5', r=0.04, x=0.09, b=0.02, rate=1000))

    nc = gce.compile_numerical_circuit_at(grid)

    return nc


def case9() -> NumericalCircuit:
    """
    Test case9 from matpower
    :return:
    """
    cwd = os.getcwd()
    print(cwd)

    # Go back two directories
    file_path = os.path.join('data', 'grids', 'case9.m')

    grid = gce.FileOpen(file_path).open()
    nc = gce.compile_numerical_circuit_at(grid)

    return nc


def case14() -> NumericalCircuit:
    """
    Test case14 from matpower
    :return:
    """
    cwd = os.getcwd()
    print(cwd)

    # Go back two directories
    file_path = os.path.join('data', 'grids', 'case14.m')

    grid = gce.FileOpen(file_path).open()
    for l in grid.get_transformers2w():
        l.set_tap_controls(TapPhaseControl.Pt, TapModuleControl.Qt)

    nc = gce.compile_numerical_circuit_at(grid)

    return nc


def case_pegase89() -> NumericalCircuit:
    """
    Pegase89
    """
    cwd = os.getcwd()
    print(cwd)
    # Go back two directories
    file_path = os.path.join('data', 'grids', 'case89pegase.m')

    grid = gce.FileOpen(file_path).open()
    grid.get_transformers2w()[3].set_tap_controls(TapPhaseControl.Pt, TapModuleControl.Qt)
    grid.get_transformers2w()[7].set_tap_controls(TapPhaseControl.Pt, TapModuleControl.Qt)
    grid.get_transformers2w()[18].set_tap_controls(TapPhaseControl.fixed, TapModuleControl.Vm)
    grid.get_transformers2w()[21].set_tap_controls(TapPhaseControl.Pt, TapModuleControl.Qt)
    grid.get_transformers2w()[36].set_tap_controls(TapPhaseControl.Pf, TapModuleControl.fixed)

    nc = gce.compile_numerical_circuit_at(grid)

    return nc


def test_case_3bus() -> None:
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


def test_case_5bus() -> None:
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


def test_pegase89() -> None:
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


def test_case14() -> None:
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
