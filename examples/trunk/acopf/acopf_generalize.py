import numpy as np
import scipy.sparse as sp
import GridCalEngine.api as gce
from typing import List


def build_grid_3bus():

    grid = gce.MultiCircuit()

    b1 = gce.Bus(is_slack=True)
    b2 = gce.Bus()
    b3 = gce.Bus()

    grid.add_bus(b1)
    grid.add_bus(b2)
    grid.add_bus(b3)

    grid.add_line(gce.Line(bus_from=b1, bus_to=b2, name='line 1-2', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b2, bus_to=b3, name='line 2-3', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='line 3-1_1', r=0.001, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='line 3-1_2', r=0.001, x=0.05, rate=100))

    grid.add_load(b3, gce.Load(name='L3', P=50, Q=20))
    grid.add_generator(b1, gce.Generator('G1', vset=1.001))
    grid.add_generator(b2, gce.Generator('G2', P=10, vset=0.995))

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    print('\n\n', grid.name)
    print('\tConv:', power_flow.results.get_bus_df())
    print('\tConv:', power_flow.results.get_branch_df())

    nc = gce.compile_numerical_circuit_at(grid)

    return grid


def compute_f_obj(pg: np.ndarray = None,
                  cost0: np.ndarray = None,
                  cost1: np.ndarray = None,
                  cost2: np.ndarray = None):
    """
    Compute the objective function considering the quadratic cost function of generation
    Cost = cost0 + cost1 * Pg + cost2 * Pg^2
    :param pg: array of generation active powers [pu]
    :param cost0: base costs [€]
    :param cost1: linear cost term [€/pu]
    :param cost2: quadratic cost term [€/pu^2]
    :return: a float representing the resulting cost
    """

    fout = np.sum(cost0 + cost1 * pg + pg * cost2 * pg)

    return fout


def g_pq(g_bus: np.ndarray = None,
         b_bus: np.ndarray = None,
         cg_bus: sp.spmatrix = None,
         cl_bus: sp.spmatrix = None,
         sl: np.ndarray = None,
         il: np.ndarray = None,
         yl: np.ndarray = None,
         sbase: float = 100,
         pqpv: np.ndarray = None,
         vd: np.ndarray = None,
         e: np.ndarray = None,
         f: np.ndarray = None,
         pgen: np.ndarray = None,
         qgen: np.ndarray = None):
    """
    Compute the equalities (P and Q balances) and extract the slack generation powers
    :param g_bus: real part of the bus admittance matrix
    :param b_bus: imaginary part of the bus admittance matrix
    :param cg_bus: generators connectivity matrix
    :param cl_bus: loads connectivity matrix
    :param sl: load complex power in MVA
    :param il: load complex current in equivalent MVA
    :param yl: load complex admittance in equivalent MVA
    :param sbase: system base power in MVA
    :param pqpv: array of PQ and PV nodes
    :param vd: array of slack buses, in principle only one
    :param e: real part of the voltages, unknown
    :param f: imaginary part of the voltages, unknown
    :param pgen: active generation power, unknown
    :param qgen: reactive generation power, unknown
    :return: P and Q residual vectors indicating the error, and P and Q from the slack
    """

    # Branches
    pbbus = e * (g_bus @ e) + f * (g_bus @ f) - e * (b_bus @ f) + f * (b_bus @ e)
    qbbus = - e * (b_bus @ e) - f * (b_bus @ f) - e * (g_bus @ f) + f * (g_bus @ e)

    # Generation
    pgbus = cg_bus * pgen
    qgbus = cg_bus * qgen

    # Loads
    pl_bus = cl_bus * np.real(sl) / sbase
    ql_bus = cl_bus * np.imag(sl) / sbase
    irl_bus = cl_bus * np.real(il) / sbase
    iil_bus = cl_bus * np.imag(il) / sbase
    gl_bus = cl_bus * np.real(yl) / sbase
    bl_bus = cl_bus * np.imag(yl) / sbase

    plbus = pl_bus + e * irl_bus + f * iil_bus + gl_bus * (e * e + f * f)
    qlbus = ql_bus - e * iil_bus + f * irl_bus - bl_bus * (e * e + f * f)

    # Total balance
    pbal = pgbus - plbus - pbbus
    qbal = qgbus - qlbus - qbbus

    # Slack powers assuming the balance is perfectly kept at 0
    pgslack = plbus[vd] + pbbus[vd]
    qgslack = qlbus[vd] + qbbus[vd]

    return pbal[pqpv], qbal[pqpv], pgslack, qgslack


def h_voltage_upper(vmax: np.ndarray = None,
                    e: np.ndarray = None,
                    f: np.ndarray = None):
    """
    Upper voltage inequality
    :param vmax: array of maximum bus voltages
    :param e: real part of the voltages, unknown
    :param f: imaginary part of the voltages, unknown
    :return: vector of the errors
    """
    return - e * e - f * f + vmax * vmax


def h_voltage_lower(vmin: np.ndarray = None,
                    e: np.ndarray = None,
                    f: np.ndarray = None):
    """
    Lower voltage inequality
    :param vmin: array of minimum bus voltages
    :param e: real part of the voltages, unknown
    :param f: imaginary part of the voltages, unknown
    :return: vector of the errors
    """
    return + e * e + f * f - vmin * vmin


def h_pqgen_upper(pmax: np.ndarray = None,
                  pgen: np.ndarray = None,
                  sbase: float = 100):
    """
    Maximum generation power inequality
    :param pmax: array of maximum generation powers
    :param pgen: generation power, unknown
    :param sbase: base power, in MVA
    :return: vector of the errors
    """
    return - pgen + pmax / sbase


def h_pqgen_lower(pmin: np.ndarray = None,
                  pgen: np.ndarray = None,
                  sbase: float = 100):
    """
    Minimum generation power inequality
    :param pmin: array of minimum generation powers
    :param pgen: generation active power, unknown
    :param sbase: base power, in MVA
    :return: vector of the errors
    """
    return + pgen - pmin / sbase


def h_branch_from_to(rate: np.ndarray = None,
                     cf: sp.spmatrix = None,
                     yf: sp.spmatrix = None,
                     sbase: float = 100,
                     e: np.ndarray = None,
                     f: np.ndarray = None):
    """
    Maximum apparent power seen from one side
    :param rate: maximum power the branch admits, in MVA
    :param cf: connectivity matrix
    :param yf: admittance matrix seen from one side
    :param sbase: base power, in MVA
    :param e: real part of the voltages, unknown
    :param f: imaginary part of the voltages, unknown
    :return: vector of the errors
    """
    sf = (cf @ (e + 1j * f)) * np.conj(yf @ (e + 1j * f))

    return - abs(sf)**2 + (rate / sbase)**2


def solve_opf(grid, h=1e-5, tol=1e-6, max_iter=50):
    """
    Main function to solve the OPF, it calls other functions and assembles the IPM
    :param grid: multicircuit where we want to compute the OPF
    :param h: delta used in the derivatives definition
    :param tol: tolerance to stop the algorithm
    :param max_iter: maximum number of iterations of the algorithm
    :return: the vectors of solutions
    """
    nc = gce.compile_numerical_circuit_at(grid)

    # Initialize unknowns
    pqpv = nc.pqpv
    vd = nc.vd
    npqpv = len(pqpv)
    nbus = nc.nbus
    ngen = nc.ngen
    nbr = nc.nbr
    sbase = nc.Sbase

    e = np.real(nc.Vbus)
    f = np.imag(nc.Vbus)
    # introduce some variability
    e[0] = 1.005
    e[2] = 0.995
    f[0] = 0.001
    f[1] = -0.003
    f[2] = 0.0015

    pgen = nc.generator_data.p / sbase
    qgen = np.zeros(ngen)

    # Equalities: g = [g_p, g_q]
    # First associate the slack bus type to identify the slack generators
    ones_vd = np.zeros(nbus)
    ones_vd[vd] = 1
    id_slack0 = nc.generator_data.C_bus_elm.T @ ones_vd
    id_slack = []
    for i, v in enumerate(id_slack0):
        if v == 1:
            id_slack.append(i)

    # Get power mismatch and slack generation
    g_p, g_q, pgen[id_slack], qgen[id_slack] = g_pq(g_bus=np.real(nc.Ybus),
                                                    b_bus=np.imag(nc.Ybus),
                                                    cg_bus=nc.generator_data.C_bus_elm,
                                                    cl_bus=nc.load_data.C_bus_elm,
                                                    sl=nc.load_data.S,
                                                    il=nc.load_data.I,
                                                    yl=nc.load_data.Y,
                                                    sbase=sbase,
                                                    pqpv=pqpv,
                                                    vd=vd,
                                                    e=e,
                                                    f=f,
                                                    pgen=pgen,
                                                    qgen=qgen)

    # Inequalities h = [h_vu, h_vl, h_sf, h_st, h_pmax, h_pmin, h_qmax, h_qmin]

    h_vu = h_voltage_upper(vmax=nc.bus_data.Vmax,
                           e=e,
                           f=f)

    h_vl = h_voltage_lower(vmin=nc.bus_data.Vmin,
                           e=e,
                           f=f)

    h_sf = h_branch_from_to(rate=nc.branch_data.rates,
                            cf=nc.Cf,
                            yf=nc.Yf,
                            sbase=sbase,
                            e=e,
                            f=f)

    # would be redundant with sf, change a bit the limits
    h_st = h_branch_from_to(rate=nc.branch_data.rates * 1.01,
                            cf=nc.Ct,
                            yf=nc.Yt,
                            sbase=sbase,
                            e=e,
                            f=f)

    h_pmax = h_pqgen_upper(pmax=nc.generator_data.pmax,
                           pgen=pgen,
                           sbase=sbase)

    h_pmin = h_pqgen_lower(pmin=nc.generator_data.pmin,
                           pgen=pgen,
                           sbase=sbase)

    h_qmax = h_pqgen_upper(pmax=nc.generator_data.qmax,
                           pgen=qgen,
                           sbase=sbase)

    h_qmin = h_pqgen_lower(pmin=nc.generator_data.qmin,
                           pgen=qgen,
                           sbase=sbase)

    # Objective function
    f_obj = compute_f_obj(pg=pgen,
                          cost0=nc.generator_data.cost_0,
                          cost1=nc.generator_data.cost_1,
                          cost2=nc.generator_data.cost_2)

    # Build IPM
    n_x = 2 * npqpv + 2 * gen
    n_eq = 2 * npqpv
    n_ineq = 2 * nbus + 2 * nbr + 4 * ngen

    x = np.zeros(n_x)
    g = np.zeros(n_eq)
    h = np.zeros(n_ineq)

    # store x indices to slice
    x_ind = [0,
             npqpv,
             2 * npqpv,
             2 * npqpv + ngen,
             2 * npqpv + 2 * ngen]

    x[x_ind[0], x_ind[1]] = e
    x[x_ind[1], x_ind[2]] = f
    x[x_ind[2], x_ind[3]] = pgen
    x[x_ind[3], x_ind[4]] = qgen

    # store g indices to slice
    g_ind = [0,
             npqpv,
             2*npqpv]

    g[g_ind[0]:g_ind[1]] = g_p
    g[g_ind[1]:g_ind[2]] = g_q

    # store h indices to slice
    h_ind = [0,
             nbus,
             2*nbus,
             2*nbus+nbr,
             2*nbus+2*nbr,
             2*nbus+2*nbr+ngen,
             2*nbus+2*nbr+2*ngen,
             2*nbus+2*nbr+3*ngen,
             2*nbus+2*nbr+4*nbus]

    h[h_ind[0]:h_ind[1]] = h_vu
    h[h_ind[1]:h_ind[2]] = h_vl
    h[h_ind[2]:h_ind[3]] = h_sf
    h[h_ind[3]:h_ind[4]] = h_st
    h[h_ind[4]:h_ind[5]] = h_pmax
    h[h_ind[5]:h_ind[6]] = h_pmin
    h[h_ind[6]:h_ind[7]] = h_qmax
    h[h_ind[7]:h_ind[8]] = h_qmin

    # multipliers, try other initializations maybe
    mu = 1.0
    s = np.ones(n_ineq)
    z = np.ones(n_ineq)
    y = np.ones(n_ineq)

    return 0


if __name__ == '__main__':
    system = build_grid_3bus()
    solve_opf(system)

