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

    Cf_m = Cf[k_m, :]
    Ct_m = Ct[k_m, :]

    dYffdm = -2 * ylin / (mp * mp * mp)
    dYftdm = ylin / (mp * mp * np.exp(-1.0j * tau))
    dYtfdm = ylin / (mp * mp * np.exp(1.0j * tau))
    dYttdm = np.zeros(len(k_m))

    dYfdm = Cf_m.T * (sp.diags(dYffdm) * Cf_m + sp.diags(dYftdm) * Ct_m)  # TODO: Check, unsure about the Cf_m.T, but seems necesary to get the same dimensions.
    dYtdm = Ct_m.T * (sp.diags(dYtfdm) * Cf_m + sp.diags(dYttdm) * Ct_m)  # TODO: Same

    dYbusdm = dYfdm + dYtdm  # Cf_m.T and Ct_m.T included earlier

    # First partial derivative with respect to tap angle
    mp = tapm[k_tau]
    tau = tapt[k_tau]
    ylin = ys[k_tau]

    Cf_tau = Cf[k_tau, :]
    Ct_tau = Ct[k_tau, :]

    dYffdt = np.zeros(len(k_tau))
    dYftdt = -1j * ylin / (mp * np.exp(-1.0j * tau))
    dYtfdt = 1j * ylin / (mp * np.exp(1.0j * tau))
    dYttdt = np.zeros(len(k_tau))

    dYfdt = Cf_tau.T * (sp.diags(dYffdt) * Cf_tau + sp.diags(dYftdt) * Ct_tau)  # TODO: Incorrect order
    dYtdt = Ct_tau.T * (sp.diags(dYtfdt) * Cf_tau + sp.diags(dYttdt) * Ct_tau)  # TODO: Incorrect order

    dYbusdt = dYfdt + dYtdt  # TODO: Check same as in module derivatives.

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

    Cf_m = nc.Cf[k_m, :]
    Ct_m = nc.Ct[k_m, :]

    dYffdmdm = 6 * ylin / (mp * mp * mp * mp)
    dYftdmdm = -2 * ylin / (mp * mp * mp * np.exp(-1.0j * tau))
    dYtfdmdm = -2 * ylin / (mp * mp * mp * np.exp(1.0j * tau))
    dYttdmdm = np.zeros(len(k_m))

    dYfdmdm = (sp.diags(dYffdmdm) * Cf_m + sp.diags(dYftdmdm) * Ct_m)
    dYtdmdm = (sp.diags(dYtfdmdm) * Cf_m + sp.diags(dYttdmdm) * Ct_m)

    dYbusdmdm = (Cf_m.T * dYfdmdm + Ct_m.T * dYtdmdm)

    # Second partial derivative with respect to tap angle
    mp = tapm[k_tau]
    tau = tapt[k_tau]
    ylin = ys[k_tau]

    Cf_tau = Cf[k_tau, :]
    Ct_tau = Ct[k_tau, :]

    dYffdtdt = np.zeros(len(k_tau))
    dYftdtdt = ylin / (mp * np.exp(-1.0j * tau))
    dYtfdtdt = ylin / (mp * np.exp(1.0j * tau))
    dYttdtdt = np.zeros(len(k_tau))

    dYfdtdt = sp.diags(dYffdtdt) * Cf_tau + sp.diags(dYftdtdt) * Ct_tau
    dYtdtdt = sp.diags(dYtfdtdt) * Cf_tau + sp.diags(dYttdtdt) * Ct_tau

    dYbusdtdt = Cf_tau.T * dYfdtdt + Ct_tau.T * dYtdtdt

    # Second partial derivative with respect to both tap module and angle
    mp = tapm[k_mtau]
    tau = tapt[k_mtau]
    ylin = ys[k_mtau]

    Cf_mtau = Cf[k_mtau, :]
    Ct_mtau = Ct[k_mtau, :]

    dYffdmdt = np.zeros(len(k_mtau))
    dYftdmdt = 1j * ylin / (mp * mp * np.exp(-1.0j * tau))
    dYtfdmdt = -1j * ylin / (mp * mp * np.exp(1.0j * tau))
    dYttdmdt = np.zeros(len(k_mtau))

    dYfdmdt = sp.diags(dYffdmdt) * Cf_mtau + sp.diags(dYftdmdt) * Ct_mtau
    dYtdmdt = sp.diags(dYtfdmdt) * Cf_mtau + sp.diags(dYttdmdt) * Ct_mtau

    dYbusdmdt = Cf_tau.T * dYfdmdt + Ct_tau.T * dYtdmdt

    dYfdtdm = dYfdmdt.copy()
    dYtdtdm = dYtdmdt.copy()
    dYbusdtdm = dYbusdmdt.copy()

    return (dYbusdmdm, dYfdmdm, dYtdmdm, dYbusdmdt, dYfdmdt, dYtdmdt,
            dYbusdtdm, dYfdtdm, dYtdtdm, dYbusdtdt, dYfdtdt, dYtdtdt)

'''
def compute_analytic_admittances_2dev(nc):

    k_m = np.r_[nc.k_qf_m, nc.k_qt_m, nc.k_vt_m]
    tapm = nc.branch_data.tap_module
    k_tau = nc.k_pf_tau
    tapt = nc.branch_data.tap_angle

    F = nc.branch_data.F
    T = nc.branch_data.T
    Cf = nc.Cf
    Ct = nc.Ct
    ys = 1.0 / (nc.branch_data.R + 1.0j * nc.branch_data.X + 1e-20)

    admittance = nc.compute_admittance()
    Ybus = admittance.Ybus
    M, N = Cf.shape

    dYfdmdm = []
    dYtdmdm = []
    dYbusdmdm = []

    dYfdmdt = []
    dYtdmdt = []
    dYbusdmdt = []

    dYfdtdm = []
    dYtdtdm = []
    dYbusdtdm = []

    dYfdtdt = []
    dYtdtdt = []
    dYbusdtdt = []

    for l, line in enumerate(tapm_lines):
        i = F[line]
        j = T[line]
        mp = tapm[line]
        tau = tapt[line]
        ylin = ys[line]

        dYffdmdm = np.zeros(M, dtype=complex)
        dYftdmdm = np.zeros(M, dtype=complex)
        dYtfdmdm = np.zeros(M, dtype=complex)
        dYttdmdm = np.zeros(M, dtype=complex)

        dYffdmdm[line] = 6 * ylin / (mp * mp * mp * mp)
        dYftdmdm[line] = -2 * ylin / (mp * mp * mp * np.exp(-1.0j * tau))
        dYtfdmdm[line] = -2 * ylin / (mp * mp * mp * np.exp(1.0j * tau))
        dYttdmdm[line] = 0

        dYfdmdm.append(sp.diags(dYffdmdm) * Cf + sp.diags(dYftdmdm) * Ct)
        dYtdmdm.append(sp.diags(dYtfdmdm) * Cf + sp.diags(dYttdmdm) * Ct)

        dYbusdmdm.append(Cf.T * dYfdmdm[l] + Ct.T * dYtdmdm[l])

        if line in tapt_lines:
            dYffdmdt = np.zeros(M, dtype=complex)
            dYftdmdt = np.zeros(M, dtype=complex)
            dYtfdmdt = np.zeros(M, dtype=complex)
            dYttdmdt = np.zeros(M, dtype=complex)

            dYffdmdt[line] = 0
            dYftdmdt[line] = 1j * ylin / (mp * mp * np.exp(-1.0j * tau))
            dYtfdmdt[line] = -1j * ylin / (mp * mp * np.exp(1.0j * tau))
            dYttdmdt[line] = 0

            dYfdmdt.append(sp.diags(dYffdmdt) * Cf + sp.diags(dYftdmdt) * Ct)
            dYtdmdt.append(sp.diags(dYtfdmdt) * Cf + sp.diags(dYttdmdt) * Ct)

            dYbusdmdt.append(Cf.T * dYfdmdt[l] + Ct.T * dYtdmdt[l])

            dYfdtdm.append((sp.diags(dYffdmdt) * Cf + sp.diags(dYftdmdt) * Ct).T)
            dYtdtdm.append((sp.diags(dYtfdmdt) * Cf + sp.diags(dYttdmdt) * Ct).T)

            dYbusdtdm.append((Cf.T * dYfdmdt[l] + Ct.T * dYtdmdt[l]).T)

    for l, line in enumerate(tapt_lines):
        i = F[line]
        j = T[line]
        mp = tapm[line]
        tau = tapt[line]
        ylin = ys[line]

        dYffdtdt = np.zeros(M, dtype=complex)
        dYftdtdt = np.zeros(M, dtype=complex)
        dYtfdtdt = np.zeros(M, dtype=complex)
        dYttdtdt = np.zeros(M, dtype=complex)

        dYffdtdt[line] = 0
        dYftdtdt[line] = ylin / (mp * np.exp(-1.0j * tau))
        dYtfdtdt[line] = ylin / (mp * np.exp(1.0j * tau))
        dYttdtdt[line] = 0

        dYfdtdt.append(sp.diags(dYffdtdt) * Cf + sp.diags(dYftdtdt) * Ct)
        dYtdtdt.append(sp.diags(dYtfdtdt) * Cf + sp.diags(dYttdtdt) * Ct)

        dYbusdtdt.append(Cf.T * dYfdtdt[l] + Ct.T * dYtdtdt[l])

    dYfdtdm = dYfdmdt.T
    dYtdtdm = dYtdmdt.T
    dYbusdtdm = dYbusdmdt.T

    return (dYbusdmdm, dYfdmdm, dYtdmdm, dYbusdmdt, dYfdmdt, dYtdmdt,
            dYbusdtdm, dYfdtdm, dYtdtdm, dYbusdtdt, dYfdtdt, dYtdtdt)

'''

if __name__ == '__main__':
    example_3bus_acopf()
