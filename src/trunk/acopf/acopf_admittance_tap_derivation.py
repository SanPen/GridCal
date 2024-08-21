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
import GridCalEngine.api as gce
from GridCalEngine.DataStructures.numerical_circuit import compile_numerical_circuit_at, NumericalCircuit
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import run_nonlinear_opf
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.enumerations import TapPhaseControl
from scipy import sparse as sp
import numpy as np


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

    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=3)
    run_nonlinear_opf(grid=grid,
                      opf_options=opf_options,
                      pf_options=pf_options,
                      plot_error=True)


def compute_analytic_admittances(nc: NumericalCircuit):
    """

    :param nc:
    :return:
    """
    k_m = nc.k_m
    k_tau = nc.k_tau
    k_mtau = nc.k_mtau

    tapm = nc.branch_data.tap_module
    tapt = nc.branch_data.tap_angle

    Cf = nc.Cf
    Ct = nc.Ct
    ys = 1.0 / (nc.branch_data.R + 1.0j * nc.branch_data.X + 1e-20)

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
    k_m = indices.k_m
    k_tau = indices.k_tau

    # base values
    adm0 = nc.get_admittance_matrices()

    # Modify tap modules
    nc.branch_data.tap_module[k_m] += tol
    adm1 = nc.get_admittance_matrices()
    nc.branch_data.tap_module[k_m] -= tol

    dYf_dm = (adm1.Yf - adm0.Yf) / tol
    dYt_dm = (adm1.Yt - adm0.Yt) / tol
    dY_dm = (adm1.Ybus - adm0.Ybus) / tol

    # modify tap angles
    nc.branch_data.tap_angle[k_tau] += tol
    adm2 = nc.get_admittance_matrices()
    nc.branch_data.tap_angle[k_tau] -= tol

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
    k_m = indices.k_m
    k_tau = indices.k_tau
    k_mtau = indices.k_mtau

    tapm = nc.branch_data.tap_module
    tapt = nc.branch_data.tap_angle

    Cf = nc.Cf
    Ct = nc.Ct
    ys = 1.0 / (nc.branch_data.R + 1.0j * nc.branch_data.X + 1e-20)

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
    k_m = indices.k_m
    k_tau = indices.k_tau

    # Refference
    dY0_dm, dYf0_dm, dYt0_dm, dY0_dt, dYf0_dt, dYt0_dt = compute_finitediff_admittances(nc)

    # Modify the tap module
    nc.branch_data.tap_module[k_m] += tol
    dY_dm, dYf_dm, dYt_dm, dY_dt, dYf_dt, dYt_dt = compute_finitediff_admittances(nc)
    nc.branch_data.tap_module[k_m] -= tol

    dYf_dmdm = (dYf_dm - dYf0_dm) / tol
    dYt_dmdm = (dYt_dm - dYt0_dm) / tol
    dY_dmdm = (dY_dm - dY0_dm) / tol

    dYf_dtdm = (dYf_dt - dYf0_dt) / tol
    dYt_dtdm = (dYt_dt - dYt0_dt) / tol
    dY_dtdm = (dY_dt - dY0_dt) / tol

    # Modify the tap angle
    nc.branch_data.tap_angle[k_tau] += tol
    dY_dm, dYf_dm, dYt_dm, dY_dt, dYf_dt, dYt_dt = compute_finitediff_admittances(nc)
    nc.branch_data.tap_angle[k_tau] -= tol

    dYf_dmdt = (dYf_dm - dYf0_dm) / tol
    dYt_dmdt = (dYt_dm - dYt0_dm) / tol
    dY_dmdt = (dY_dm - dY0_dm) / tol

    dYf_dtdt = (dYf_dt - dYf0_dt) / tol
    dYt_dtdt = (dYt_dt - dYt0_dt) / tol
    dY_dtdt = (dY_dt - dY0_dt) / tol

    return (dY_dmdm, dYf_dmdm, dYt_dmdm, dY_dmdt, dYf_dmdt, dYt_dmdt,
            dY_dtdm, dYf_dtdm, dYt_dtdm, dY_dtdt, dYf_dtdt, dYt_dtdt)


if __name__ == '__main__':
    example_3bus_acopf()
