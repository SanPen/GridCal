import numpy as np
import scipy.sparse as sp
import GridCalEngine.api as gce
from typing import List, Dict


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


def compute_fobj(pg: np.ndarray = None,
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


def build_g(x: np.ndarray = None,
            x_ind: np.ndarray = None,
            g: np.ndarray = None,
            g_ind: np.ndarray = None,
            g_bus: np.ndarray = None,
            b_bus: np.ndarray = None,
            cg_bus: sp.spmatrix = None,
            cl_bus: sp.spmatrix = None,
            sl: np.ndarray = None,
            il: np.ndarray = None,
            yl: np.ndarray = None,
            sbase: float = 100.0,
            pqpv: np.ndarray = None,
            vd: np.ndarray = None,
            v_sl: np.ndarray = None,
            nbus: int = 0):

    """
    Compute the equalities (P and Q balances)
    :param x: vector of unknowns, unpack into e, f, pgen, qgen
    :param x_ind: vector of indices to unpack x
    :param g: vector of equality residuals, pack from gp, gq
    :param g_ind: vector of indices to pack g
    :param g_bus: real part of the bus admittance matrix
    :param b_bus: imaginary part of the bus admittance matrix
    :param cg_bus: generators connectivity matrix
    :param cl_bus: loads connectivity matrix
    :param sl: load complex power in MVA
    :param il: load complex current in equivalent MVA
    :param yl: load complex admittance in equivalent MVA
    :param sbase: system base power in MVA
    :param pqpv: array of PQ and PV nodes
    :param vd: array of slack nodes
    :param v_sl: voltages of slack buses
    :param nbus: number of buses
    :return: updated vector g
    """

    e = np.empty(nbus)
    f = np.empty(nbus)

    e[pqpv] = x[x_ind[0]:x_ind[1]]
    f[pqpv] = x[x_ind[1]:x_ind[2]]
    e[vd] = np.real(v_sl[:])
    f[vd] = np.imag(v_sl[:])
    pgen = x[x_ind[2]:x_ind[3]]
    qgen = x[x_ind[3]:x_ind[4]]

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
    # pgslack = plbus[vd] + pbbus[vd]
    # qgslack = qlbus[vd] + qbbus[vd]

    g[g_ind[0]:g_ind[1]] = pbal[pqpv]
    g[g_ind[1]:g_ind[2]] = qbal[pqpv]

    return g


def build_h(x: np.ndarray = None,
            x_ind: np.ndarray = None,
            h: np.ndarray = None,
            h_ind: np.ndarray = None,
            v_max: np.ndarray = None,
            v_min: np.ndarray = None,
            rate_f: np.ndarray = None,
            rate_t: np.ndarray = None,
            cf: sp.spmatrix = None,
            ct: sp.spmatrix = None,
            yf: sp.spmatrix = None,
            yt: sp.spmatrix = None,
            p_max: np.ndarray = None,
            p_min: np.ndarray = None,
            q_max: np.ndarray = None,
            q_min: np.ndarray = None,
            sbase: float = 100.0,
            pqpv: np.ndarray = None,
            vd: np.ndarray = None,
            v_sl: np.ndarray = None,
            nbus: int = 0):

    """
    Build the vector of inequalities
    :param x: vector of unknowns, unpack into e, f, pgen, qgen
    :param x_ind: vector of indices to unpack x
    :param h: vector of inequality residuals
    :param h_ind: vector of indices to pack h
    :param v_max: maximum bus voltages
    :param v_min: minimum bus voltages
    :param rate_f: maximum from apparent power supported by branches
    :param rate_t: maximum to apparent power supported by branches
    :param cf: branch connectivity matrix from side
    :param ct: branch connectivity matrix to side
    :param yf: from admittance matrix
    :param yt: to admittance matrix
    :param p_max: maximum active power generation
    :param p_min: minimum active power generation
    :param q_max: maximum reactive power generation
    :param q_min: minimum reactive power generation
    :param sbase: system base power in MVA
    :param pqpv: array of PQ and PV nodes
    :param vd: array of slack nodes
    :param v_sl: voltages of slack buses
    :param nbus: number of buses
    :return: updated vector h
    """

    e = np.empty(nbus)
    f = np.empty(nbus)

    e[pqpv] = x[x_ind[0]:x_ind[1]]
    f[pqpv] = x[x_ind[1]:x_ind[2]]
    e[vd] = np.real(v_sl[:])
    f[vd] = np.imag(v_sl[:])
    pgen = x[x_ind[2]:x_ind[3]]
    qgen = x[x_ind[3]:x_ind[4]]

    sf = (cf @ (e + 1j * f)) * np.conj(yf @ (e + 1j * f))
    st = (ct @ (e + 1j * f)) * np.conj(yt @ (e + 1j * f))

    h_vu = - e * e - f * f + v_max * v_max
    h_vl = + e * e + f * f - v_min * v_min
    h_sf = - abs(sf)**2 + (rate_f / sbase)**2
    h_st = - abs(st)**2 + (rate_t / sbase)**2
    h_pmax = - pgen + p_max / sbase
    h_pmin = + pgen - p_min / sbase
    h_qmax = - qgen + q_max / sbase
    h_qmin = + qgen - q_min / sbase

    h[h_ind[0]:h_ind[1]] = h_vu
    h[h_ind[1]:h_ind[2]] = h_vl
    h[h_ind[2]:h_ind[3]] = h_sf
    h[h_ind[3]:h_ind[4]] = h_st
    h[h_ind[4]:h_ind[5]] = h_pmax
    h[h_ind[5]:h_ind[6]] = h_pmin
    h[h_ind[6]:h_ind[7]] = h_qmax
    h[h_ind[7]:h_ind[8]] = h_qmin

    return h


def build_gae(x: np.ndarray = None,
              g_dict: Dict = None,
              n_eq: int = 0,
              n_x: int = 0,
              dh: float = 1e-5):
    """
    Build the concatenation of g gradients
    :param x: vector of unknowns
    :param g_dict: dictionary of constant data to pass to g
    :param n_eq: number of equalities
    :param n_x: number of unknowns
    :param dh: step parameter
    :return: matrix Ae of size n_eq x n_x containing the gradients
    """

    gae = np.zeros((n_eq, n_x), dtype=float)
    g0 = np.copy(build_g(x, **g_dict))

    # Compute the gradients as (g(x + h) - g0) / dh
    for i in range(n_x):
        x_it = np.copy(x)
        x_it[i] += dh
        g_it = build_g(x_it, **g_dict)
        gae[:, i] = (g_it - g0) / dh

    return gae


def build_gai(x: np.ndarray = None,
              h_dict: Dict = None,
              n_ineq: int = 0,
              n_x: int = 0,
              dh: float = 1e-5):
    """
    Build the concatenation of h gradients
    :param x: vector of unknowns
    :param h_dict: dictionary of constant data to pass to h
    :param n_ineq: number of inequalities
    :param n_x: number of unknowns
    :param dh: step parameter
    :return: matrix Ai of size n_ineq x n_x containing the gradients
    """

    gai = np.zeros((n_ineq, n_x), dtype=float)
    h0 = np.copy(build_h(x, **h_dict))

    # Compute the gradients as (h(x + h) - h0) / dh
    for i in range(n_x):
        x_it = np.copy(x)
        x_it[i] += dh
        h_it = build_h(x_it, **h_dict)
        gai[:, i] = (h_it - h0) / dh

    return gai


def solve_opf(grid, dh=1e-5, tol=1e-6, max_iter=50):
    """
    Main function to solve the OPF, it calls other functions and assembles the IPM
    :param grid: multicircuit where we want to compute the OPF
    :param dh: delta used in the derivatives definition
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

    # Associate the slack bus type to identify the slack generators
    ones_vd = np.zeros(nbus)
    ones_vd[vd] = 1
    id_slack0 = nc.generator_data.C_bus_elm.T @ ones_vd
    id_slack = []
    for i, v in enumerate(id_slack0):
        if v == 1:
            id_slack.append(i)

    # Initialize IPM
    n_x = 2 * npqpv + 2 * ngen
    n_eq = 2 * npqpv
    n_ineq = 2 * nbus + 2 * nbr + 4 * ngen

    x = np.zeros(n_x)
    g = np.zeros(n_eq)
    h = np.zeros(n_ineq)

    # store x indices to slice
    x_ind = np.array([0,
                      npqpv,
                      2 * npqpv,
                      2 * npqpv + ngen,
                      2 * npqpv + 2 * ngen])

    x[x_ind[0]:x_ind[1]] = np.real(nc.Vbus)[pqpv]  # e
    x[x_ind[1]:x_ind[2]] = np.imag(nc.Vbus)[pqpv]  # f
    x[x_ind[2]:x_ind[3]] = nc.generator_data.p / nc.Sbase  # pgen
    x[x_ind[3]:x_ind[4]] = np.zeros(ngen)  # qgen

    v_sl = nc.Vbus[vd]

    # store g indices to slice
    g_ind = np.array([0,
                      npqpv,
                      2 * npqpv])

    # store h indices to slice
    h_ind = np.array([0,
                      nbus,
                      2 * nbus,
                      2 * nbus + nbr,
                      2 * nbus + 2 * nbr,
                      2 * nbus + 2 * nbr + ngen,
                      2 * nbus + 2 * nbr + 2 * ngen,
                      2 * nbus + 2 * nbr + 3 * ngen,
                      2 * nbus + 2*nbr+4*nbus])

    # multipliers, try other initializations maybe
    mu = 1.0
    s = np.ones(n_ineq)
    z = np.ones(n_ineq)
    y = np.ones(n_ineq)

    # Pack the keyword arguments into a dictionary
    g_dict = {'x_ind': x_ind,
              'g': g,
              'g_ind': g_ind,
              'g_bus': np.real(nc.Ybus),
              'b_bus': np.imag(nc.Ybus),
              'cg_bus': nc.generator_data.C_bus_elm,
              'cl_bus': nc.load_data.C_bus_elm,
              'sl': nc.load_data.S,
              'il': nc.load_data.I,
              'yl': nc.load_data.Y,
              'sbase': nc.Sbase,
              'pqpv': pqpv,
              'vd': vd,
              'v_sl': v_sl,
              'nbus': nbus}

    h_dict = {'x_ind': x_ind,
              'h': h,
              'h_ind': h_ind,
              'v_max': nc.bus_data.Vmax,
              'v_min': nc.bus_data.Vmin,
              'rate_f': nc.branch_data.rates,
              'rate_t': nc.branch_data.rates * 1.01,
              'cf': nc.Cf,
              'ct': nc.Ct,
              'yf': nc.Yf,
              'yt': nc.Yt,
              'p_max': nc.generator_data.pmax,
              'p_min': nc.generator_data.pmin,
              'q_max': nc.generator_data.qmax,
              'q_min': nc.generator_data.qmin,
              'sbase': nc.Sbase,
              'pqpv': pqpv,
              'vd': vd,
              'v_sl': v_sl,
              'nbus': nbus}

    # start loop
    err = 1.0
    it = 0
    while err > tol and it < max_iter:

        g = build_g(x, **g_dict)
        h = build_h(x, **h_dict)

        gae = build_gae(x=x,
                        g_dict=g_dict,
                        n_eq=n_eq,
                        n_x=n_x,
                        dh=dh)

        gai = build_gai(x=x,
                        h_dict=h_dict,
                        n_ineq=n_ineq,
                        n_x=n_x,
                        dh=dh)

        # r = build_r(s=s,
        #             z=z,
        #             mu=mu,
        #             g=g,
        #             h=h)

        # Objective function
        f_obj = compute_fobj(pg=x[x_ind[2]:x_ind[3]],
                             cost0=nc.generator_data.cost_0,
                             cost1=nc.generator_data.cost_1,
                             cost2=nc.generator_data.cost_2)

        it += 1

    return 0


if __name__ == '__main__':
    system = build_grid_3bus()
    solve_opf(system)

