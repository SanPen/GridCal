import os
import GridCalEngine.api as gce
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.Simulations.OPF.NumericalMethods.ac_opf import run_nonlinear_opf, ac_optimal_power_flow
from GridCalEngine.enumerations import TransformerControlType
from scipy.sparse import csc_matrix as csc
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

    tr1 = gce.Transformer2W(b1, b2, 'Trafo1', control_mode=TransformerControlType.Pf,
                            tap_module=1.1, tap_phase=0.02, r=0.001, x=0.05)
    grid.add_transformer2w(tr1)

    tr2 = gce.Transformer2W(b3, b1, 'Trafo1', control_mode=TransformerControlType.PtQt,
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

    pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR, verbose=3)
    run_nonlinear_opf(grid=grid, pf_options=pf_options, plot_error=True)


def compute_analytic_admittances(nc):
    k_m = np.r_[nc.k_m, nc.k_mtau]  # TODO: Decide if we have to concatenate here or in NumericalCircuit definition
    k_tau = np.r_[nc.k_tau, nc.k_mtau]
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


def compute_finitediff_admittances(nc, tol=1e-6):

    k_m = np.r_[nc.k_m, nc.k_mtau]
    k_tau = np.r_[nc.k_tau, nc.k_mtau]

    Ybus0 = nc.Ybus
    Yf0 = nc.Yf
    Yt0 = nc.Yt

    nc.branch_data.tap_module[k_m] += tol
    nc.reset_calculations()

    dYfdm = (nc.Yf - Yf0) / tol
    dYtdm = (nc.Yt - Yt0) / tol
    dYbusdm = (nc.Ybus - Ybus0) / tol

    nc.branch_data.tap_module[k_m] -= tol

    nc.branch_data.tap_angle[k_tau] += tol
    nc.reset_calculations()

    dYfdt = (nc.Yf - Yf0) / tol
    dYtdt = (nc.Yt - Yt0) / tol
    dYbusdt = (nc.Ybus - Ybus0) / tol

    nc.branch_data.tap_angle[k_tau] -= tol
    nc.reset_calculations()

    return dYbusdm, dYfdm, dYtdm, dYbusdt, dYfdt, dYtdt


def compute_analytic_admittances_2dev(nc):

    k_m = np.r_[nc.k_m, nc.k_mtau]
    k_tau = np.r_[nc.k_tau, nc.k_mtau]
    k_mtau = nc.k_mtau

    tapm = nc.branch_data.tap_module
    tapt = nc.branch_data.tap_angle

    Cf = nc.Cf
    Ct = nc.Ct
    ys = 1.0 / (nc.branch_data.R + 1.0j * nc.branch_data.X + 1e-20)

    # Second partial derivative with respect to tap module
    mp = tapm[k_m]
    tau = tapt[k_m]
    ylin = ys[k_m]

    Cf_m = nc.Cf[:, :]
    Ct_m = nc.Ct[:, :]

    dYffdmdm = np.zeros(len(tapm), dtype=complex)
    dYftdmdm = np.zeros(len(tapm), dtype=complex)
    dYtfdmdm = np.zeros(len(tapm), dtype=complex)
    dYttdmdm = np.zeros(len(tapm), dtype=complex)

    dYffdmdm[k_m] = 6 * ylin / (mp * mp * mp * mp)
    dYftdmdm[k_m] = -2 * ylin / (mp * mp * mp * np.exp(-1.0j * tau))
    dYtfdmdm[k_m] = -2 * ylin / (mp * mp * mp * np.exp(1.0j * tau))

    dYfdmdm = (sp.diags(dYffdmdm) * Cf_m + sp.diags(dYftdmdm) * Ct_m)
    dYtdmdm = (sp.diags(dYtfdmdm) * Cf_m + sp.diags(dYttdmdm) * Ct_m)

    dYbusdmdm = (Cf_m.T * dYfdmdm + Ct_m.T * dYtdmdm)

    # Second partial derivative with respect to tap angle
    mp = tapm[k_tau]
    tau = tapt[k_tau]
    ylin = ys[k_tau]

    dYffdtdt = np.zeros(len(tapm), dtype=complex)
    dYftdtdt = np.zeros(len(tapm), dtype=complex)
    dYtfdtdt = np.zeros(len(tapm), dtype=complex)
    dYttdtdt = np.zeros(len(tapm), dtype=complex)

    dYftdtdt[k_tau] = ylin / (mp * np.exp(-1.0j * tau))
    dYtfdtdt[k_tau] = ylin / (mp * np.exp(1.0j * tau))

    dYfdtdt = sp.diags(dYffdtdt) * Cf + sp.diags(dYftdtdt) * Ct
    dYtdtdt = sp.diags(dYtfdtdt) * Cf + sp.diags(dYttdtdt) * Ct

    dYbusdtdt = Cf.T * dYfdtdt + Ct.T * dYtdtdt

    # Second partial derivative with respect to both tap module and angle
    mp = tapm[k_mtau]
    tau = tapt[k_mtau]
    ylin = ys[k_mtau]

    dYffdmdt = np.zeros(len(tapm), dtype=complex)
    dYftdmdt = np.zeros(len(tapm), dtype=complex)
    dYtfdmdt = np.zeros(len(tapm), dtype=complex)
    dYttdmdt = np.zeros(len(tapm), dtype=complex)

    dYftdmdt[k_mtau] = 1j * ylin / (mp * mp * np.exp(-1.0j * tau))
    dYtfdmdt[k_mtau] = -1j * ylin / (mp * mp * np.exp(1.0j * tau))

    dYfdmdt = sp.diags(dYffdmdt) * Cf + sp.diags(dYftdmdt) * Ct
    dYtdmdt = sp.diags(dYtfdmdt) * Cf + sp.diags(dYttdmdt) * Ct

    dYbusdmdt = Cf.T * dYfdmdt + Ct.T * dYtdmdt

    dYfdtdm = dYfdmdt.copy()
    dYtdtdm = dYtdmdt.copy()
    dYbusdtdm = dYbusdmdt.copy()

    return (dYbusdmdm, dYfdmdm, dYtdmdm, dYbusdmdt, dYfdmdt, dYtdmdt,
            dYbusdtdm, dYfdtdm, dYtdtdm, dYbusdtdt, dYfdtdt, dYtdtdt)


def compute_finitediff_admittances_2dev(nc, tol=1e-6):

    k_m = np.r_[nc.k_m, nc.k_mtau]
    k_tau = np.r_[nc.k_tau, nc.k_mtau]

    dYb0dm, dYf0dm, dYt0dm, dYb0dt, dYf0dt, dYt0dt = compute_finitediff_admittances(nc)

    nc.branch_data.tap_module[k_m] += tol
    nc.reset_calculations()

    dYbdm, dYfdm, dYtdm, dYbdt, dYfdt, dYtdt = compute_finitediff_admittances(nc)

    dYfdmdm = (dYfdm - dYf0dm) / tol
    dYtdmdm = (dYtdm - dYt0dm) / tol
    dYbusdmdm = (dYbdm - dYb0dm) / tol

    dYfdtdm = (dYfdt - dYf0dt) / tol
    dYtdtdm = (dYtdt - dYt0dt) / tol
    dYbusdtdm = (dYbdt - dYb0dt) / tol

    nc.branch_data.tap_module[k_m] -= tol

    nc.branch_data.tap_angle[k_tau] += tol
    nc.reset_calculations()

    dYbdm, dYfdm, dYtdm, dYbdt, dYfdt, dYtdt = compute_finitediff_admittances(nc)

    dYfdmdt = (dYfdm - dYf0dm) / tol
    dYtdmdt = (dYtdm - dYt0dm) / tol
    dYbusdmdt = (dYbdm - dYb0dm) / tol

    dYfdtdt = (dYfdt - dYf0dt) / tol
    dYtdtdt = (dYtdt - dYt0dt) / tol
    dYbusdtdt = (dYbdt - dYb0dt) / tol

    nc.branch_data.tap_angle[k_tau] -= tol
    nc.reset_calculations()

    return (dYbusdmdm, dYfdmdm, dYtdmdm, dYbusdmdt, dYfdmdt, dYtdmdt,
            dYbusdtdm, dYfdtdm, dYtdtdm, dYbusdtdt, dYfdtdt, dYtdtdt)


if __name__ == '__main__':
    example_3bus_acopf()
