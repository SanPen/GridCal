import numpy as np
import scipy.sparse as sp
import GridCalEngine.api as gce
from typing import List, Dict


def build_grid_3bus():

    grid = gce.MultiCircuit()

    b1 = gce.Bus(is_slack=True)
    b2 = gce.Bus(vmax=1.1, vmin=0.9)
    b3 = gce.Bus()

    grid.add_bus(b1)
    grid.add_bus(b2)
    grid.add_bus(b3)

    grid.add_line(gce.Line(bus_from=b1, bus_to=b2, name='line 1-2', r=0.01, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b2, bus_to=b3, name='line 2-3', r=0.01, x=0.05, rate=100))
    grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='line 3-1_1', r=0.01, x=0.05, rate=100))
    # grid.add_line(gce.Line(bus_from=b3, bus_to=b1, name='line 3-1_2', r=0.001, x=0.05, rate=100))

    gen1 = gce.Generator('G1', vset=1.001, Cost=1.0, Cost2=1.1)
    gen2 = gce.Generator('G2', P=10, vset=0.995, Cost=1.0, Cost2=0.5)

    grid.add_load(b3, gce.Load(name='L3', P=50, Q=20))
    grid.add_generator(b1, gen1)
    grid.add_generator(b2, gen2)

    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    print('\n\n', grid.name)
    print('\tConv:', power_flow.results.get_bus_df())
    print('\tConv:', power_flow.results.get_branch_df())

    nc = gce.compile_numerical_circuit_at(grid)

    return grid


def linn5bus_example():

    # declare a circuit object
    grid = gce.MultiCircuit()

    # Add the buses and the generators and loads attached
    bus1 = gce.Bus('Bus 1', Vnom=20)
    # bus1.is_slack = True  # we may mark the bus a slack
    grid.add_bus(bus1)

    # add a generator to the bus 1
    gen1 = gce.Generator('Slack Generator', vset=1.0)
    grid.add_generator(bus1, gen1)

    # add bus 2 with a load attached
    bus2 = gce.Bus('Bus 2', Vnom=20)
    grid.add_bus(bus2)
    grid.add_load(bus2, gce.Load('load 2', P=4, Q=2))

    # add bus 3 with a load attached
    bus3 = gce.Bus('Bus 3', Vnom=20)
    grid.add_bus(bus3)
    grid.add_load(bus3, gce.Load('load 3', P=2, Q=1))

    # add bus 4 with a load attached
    bus4 = gce.Bus('Bus 4', Vnom=20)
    grid.add_bus(bus4)
    grid.add_load(bus4, gce.Load('load 4', P=4, Q=2))

    # add bus 5 with a load attached
    bus5 = gce.Bus('Bus 5', Vnom=20)
    grid.add_bus(bus5)
    grid.add_load(bus5, gce.Load('load 5', P=5, Q=2))

    # add Lines connecting the buses
    grid.add_line(gce.Line(bus1, bus2, 'line 1-2', r=0.05, x=0.11, b=0.02, rate=100))
    grid.add_line(gce.Line(bus1, bus3, 'line 1-3', r=0.05, x=0.11, b=0.02, rate=100))
    grid.add_line(gce.Line(bus1, bus5, 'line 1-5', r=0.03, x=0.08, b=0.02, rate=100))
    grid.add_line(gce.Line(bus2, bus3, 'line 2-3', r=0.04, x=0.09, b=0.02, rate=100))
    grid.add_line(gce.Line(bus2, bus5, 'line 2-5', r=0.04, x=0.09, b=0.02, rate=100))
    grid.add_line(gce.Line(bus3, bus4, 'line 3-4', r=0.06, x=0.13, b=0.03, rate=100))
    grid.add_line(gce.Line(bus4, bus5, 'line 4-5', r=0.04, x=0.09, b=0.02, rate=100))

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

    # g[g_ind[0]:g_ind[1]] = pbal[pqpv]
    # g[g_ind[1]:g_ind[2]] = qbal[pqpv]

    g[g_ind[0]:g_ind[1]] = pbal
    g[g_ind[1]:g_ind[2]] = qbal

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

    vv = e + 1j * f
    sf = (cf @ vv) * np.conj(yf @ vv)
    st = (ct @ vv) * np.conj(yt @ vv)

    h_vu = - e[pqpv] * e[pqpv] - f[pqpv] * f[pqpv] + v_max[pqpv] * v_max[pqpv]
    h_vl = + e[pqpv] * e[pqpv] + f[pqpv] * f[pqpv] - v_min[pqpv] * v_min[pqpv]
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

    gae = sp.csr_matrix((n_x, n_eq), dtype=float)
    g0 = sp.csr_matrix(np.copy(build_g(x, **g_dict)))

    # Compute the gradients as (g(x + h) - g0) / dh
    for i in range(n_x):
        x_it = np.copy(x)
        x_it[i] += dh
        g_it = sp.csr_matrix(build_g(x_it, **g_dict))
        gae[i, :] = (g_it - g0) / dh

    return sp.csr_matrix.transpose(gae)


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

    gai = sp.csr_matrix((n_x, n_ineq), dtype=float)
    h0 = sp.csr_matrix(np.copy(build_h(x, **h_dict)))

    # Compute the gradients as (h(x + h) - h0) / dh
    for i in range(n_x):
        x_it = np.copy(x)
        x_it[i] += dh
        h_it = sp.csr_matrix(build_h(x_it, **h_dict))
        gai[i, :] = (h_it - h0) / dh

    return sp.csr_matrix.transpose(gai)


def build_r1(x: np.ndarray = None,
             x_ind: np.ndarray = None,
             y: np.ndarray = None,
             z: np.ndarray = None,
             gae: sp.spmatrix = None,
             gai: sp.spmatrix = None,
             n_x: int = 0,
             dh: float = 1e-5,
             fobj_dict: Dict = None):
    """
    Build the Lagrangian of the residual
    :param x: vector of unknowns
    :param x_ind: vector of indices to unpack x
    :param y: equality multiplier
    :param z: inequality multiplier
    :param gae: set of equality gradients
    :param gai: set of inequality gradients
    :param n_x: number of unknowns
    :param dh: delta of x to autodifferentiate
    :param fobj_dict: dictionary to pack the objective function parameters
    :return: array of residuals
    """

    gf = np.zeros(n_x, dtype=float)
    f0 = np.copy(compute_fobj(pg=x[x_ind[2]:x_ind[3]], **fobj_dict))

    for i in range(n_x):
        x_it = np.copy(x)
        x_it[i] += dh
        f_it = compute_fobj(pg=x_it[x_ind[2]:x_ind[3]], **fobj_dict)
        gf[i] = (f_it - f0) / dh

    return gf - gae.T @ y - gai.T @ z


def build_r(x: np.ndarray = None,
            x_ind: np.ndarray = None,
            y: np.ndarray = None,
            s: np.ndarray = None,
            z: np.ndarray = None,
            mu: float = 1.0,
            n_eq: int = 0,
            n_ineq: int = 0,
            n_x: int = 0,
            dh: float = 1e-5,
            g_dict: Dict = None,
            h_dict: Dict = None,
            fobj_dict: Dict = None):
    """
    Build the full vector of residuals
    :param x: vector of unknowns
    :param x_ind: vector of indices to unpack x
    :param y: equality multiplier
    :param s: slack variable for inequalities
    :param z: inequality multiplier
    :param mu: barrier parameter
    :param n_eq: number of equalities
    :param n_ineq: number of inequalities
    :param n_x: number of unknowns
    :param dh: delta of x to autodifferentiate
    :param g_dict: dictionary to pack the equalities
    :param h_dict: dictionary to pack the inequalities
    :param fobj_dict: dictionary to pack the objective function parameters
    :return: array of residuals
    """

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

    r1 = build_r1(x=x,
                  x_ind=x_ind,
                  y=y,
                  z=z,
                  gae=gae,
                  gai=gai,
                  n_x=n_x,
                  dh=dh,
                  fobj_dict=fobj_dict)

    r2 = s * z - mu * np.ones(n_ineq)
    r3 = g
    r4 = h - s

    return np.hstack((r1, r2, r3, r4))


def build_j(x: np.ndarray = None,
            x_ind: np.ndarray = None,
            y: np.ndarray = None,
            s: np.ndarray = None,
            z: np.ndarray = None,
            n_eq: int = 0,
            n_ineq: int = 0,
            n_x: int = 0,
            dh: float = 1e-5,
            g_dict: Dict = None,
            h_dict: Dict = None,
            fobj_dict: Dict = None):
    """
    Build the full vector of residuals
    :param x: vector of unknowns
    :param x_ind: vector of indices to unpack x
    :param y: equality multiplier
    :param s: slack variable for inequalities
    :param z: inequality multiplier
    :param n_eq: number of equalities
    :param n_ineq: number of inequalities
    :param n_x: number of unknowns
    :param dh: delta of x to autodifferentiate
    :param g_dict: dictionary to pack the equalities
    :param h_dict: dictionary to pack the inequalities
    :param fobj_dict: dictionary to pack the objective function parameters
    :return: Jacobian matrix

    J1, J2, J3, J4
    J5, J6, J7, J8
    J9, J10, J11, J12
    J13, J14, J15, J16
    """

    gae_0 = build_gae(x=x,
                      g_dict=g_dict,
                      n_eq=n_eq,
                      n_x=n_x,
                      dh=dh)

    gai_0 = build_gai(x=x,
                      h_dict=h_dict,
                      n_ineq=n_ineq,
                      n_x=n_x,
                      dh=dh)

    # J1
    j1 = sp.csr_matrix((n_x, n_x), dtype=float)

    r1_0 = build_r1(x=x,
                    x_ind=x_ind,
                    y=y,
                    z=z,
                    gae=gae_0,
                    gai=gai_0,
                    n_x=n_x,
                    dh=dh,
                    fobj_dict=fobj_dict)

    for i in range(n_x):
        x_it = np.copy(x)
        x_it[i] += dh

        gae_it = build_gae(x=x_it,
                           g_dict=g_dict,
                           n_eq=n_eq,
                           n_x=n_x,
                           dh=dh)

        gai_it = build_gai(x=x_it,
                           h_dict=h_dict,
                           n_ineq=n_ineq,
                           n_x=n_x,
                           dh=dh)

        r1_it = build_r1(x=x_it,
                         x_ind=x_ind,
                         y=y,
                         z=z,
                         gae=gae_it,
                         gai=gai_it,
                         n_x=n_x,
                         dh=dh,
                         fobj_dict=fobj_dict)

        j1[:, i] = (r1_it - r1_0) / dh

    # J2 to J16
    j2 = sp.csr_matrix((n_x, n_ineq), dtype=float)
    j3 = sp.csr_matrix(-gae_0.T)
    j4 = sp.csr_matrix(-gai_0.T)
    j5 = sp.csr_matrix((n_ineq, n_x), dtype=float)
    j6 = sp.diags(z)
    j7 = sp.csr_matrix((n_ineq, n_eq), dtype=float)
    j8 = sp.diags(s)
    j9 = sp.csr_matrix(gae_0)
    j10 = sp.csr_matrix((n_eq, n_ineq), dtype=float)
    j11 = sp.csr_matrix((n_eq, n_eq), dtype=float)
    j12 = sp.csr_matrix((n_eq, n_ineq), dtype=float)
    j13 = sp.csr_matrix(gai_0)
    j14 = - sp.eye(n_ineq, dtype=float)
    j15 = sp.csr_matrix((n_ineq, n_eq), dtype=float)
    j16 = sp.csr_matrix((n_ineq, n_ineq), dtype=float)

    jj_block = [[j1, j2, j3, j4],
                [j5, j6, j7, j8],
                [j9, j10, j11, j12],
                [j13, j14, j15, j16]]

    jj = sp.bmat(jj_block)

    return jj.tocsr()


def solve_opf(grid, dh=1e-5, tol=1e-6, max_iter=100, x0=None, s0=None, y0=None, z0=None, mu0:float = 1.0, verbose: int = 0):
    """
    Main function to solve the OPF, it calls other functions and assembles the IPM
    :param grid: multicircuit where we want to compute the OPF
    :param dh: delta used in the derivatives definition
    :param tol: tolerance to stop the algorithm
    :param max_iter: maximum number of iterations of the algorithm
    :param x0: initial solution
    :param verbose:
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

    err_list = []

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
    n_eq = 2 * nbus
    n_ineq = 2 * npqpv + 2 * nbr + 4 * ngen

    x = np.zeros(n_x)
    g = np.zeros(n_eq)
    h = np.zeros(n_ineq)

    # multipliers, try other initializations maybe
    mu = 1.0
    s = 1.0 * np.ones(n_ineq)
    z = 1.0 * np.ones(n_ineq)
    y = 0.0 * np.ones(n_eq)

    # store x indices to slice
    x_ind = np.array([0,
                      npqpv,
                      2 * npqpv,
                      2 * npqpv + ngen,
                      2 * npqpv + 2 * ngen])

    # Initialize results with a power flow
    if x0 is not None:
        x[:] = x0[:]
        s[:] = s0[:]
        y[:] = y0[:]
        z[:] = z0[:]
        mu = mu0

    else:
        pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
        pf_driver = gce.PowerFlowDriver(grid=grid,
                                        options=pf_options)
        pf_driver.run()

        # ignore power from Z and I of the load
        s0gen = pf_driver.results.Sbus / nc.Sbase - nc.load_data.C_bus_elm @ nc.load_data.S / nc.Sbase
        p0gen = nc.generator_data.C_bus_elm.T @ np.real(s0gen)
        q0gen = nc.generator_data.C_bus_elm.T @ np.imag(s0gen)

        p0gen = nc.generator_data.C_bus_elm.T @ np.zeros(len(s0gen))
        q0gen = nc.generator_data.C_bus_elm.T @ np.zeros(len(s0gen))

        x[x_ind[0]:x_ind[1]] = np.real(pf_driver.results.voltage)[pqpv]  # e
        x[x_ind[1]:x_ind[2]] = np.imag(pf_driver.results.voltage)[pqpv]  # f
        x[x_ind[2]:x_ind[3]] = p0gen  # pgen
        x[x_ind[3]:x_ind[4]] = q0gen  # qgen

    v_sl = nc.Vbus[vd]

    g_ind = np.array([0,
                      nbus,
                      2 * nbus])

    # store h indices to slice
    h_ind = np.array([0,
                      npqpv,
                      2 * npqpv,
                      2 * npqpv + nbr,
                      2 * npqpv + 2 * nbr,
                      2 * npqpv + 2 * nbr + ngen,
                      2 * npqpv + 2 * nbr + 2 * ngen,
                      2 * npqpv + 2 * nbr + 3 * ngen,
                      2 * npqpv + 2 * nbr + 4 * ngen])



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
              'rate_t': nc.branch_data.rates,
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

    fobj_dict = {'cost0': nc.generator_data.cost_0,
                 'cost1': nc.generator_data.cost_1,
                 'cost2': nc.generator_data.cost_2}

    # start loop
    err = 1.0
    f_obj0 = 1e15
    it = 0
    inn_it = 10
    while err > tol and it < max_iter:

        # for kk in range(inn_it):

        r = build_r(x=x,
                    x_ind=x_ind,
                    y=y,
                    s=s,
                    z=z,
                    mu=mu,
                    n_eq=n_eq,
                    n_ineq=n_ineq,
                    n_x=n_x,
                    dh=dh,
                    g_dict=g_dict,
                    h_dict=h_dict,
                    fobj_dict=fobj_dict)

        jj = build_j(x=x,
                     x_ind=x_ind,
                     y=y,
                     s=s,
                     z=z,
                     n_eq=n_eq,
                     n_ineq=n_ineq,
                     n_x=n_x,
                     dh=dh,
                     g_dict=g_dict,
                     h_dict=h_dict,
                     fobj_dict=fobj_dict)

        err = max(abs(r))

        ax = - sp.linalg.spsolve(jj, r)

        dxx = ax[0:n_x]
        dss = ax[n_x:n_x+n_ineq]
        dyy = ax[n_x+n_ineq:n_x+n_ineq+n_eq]
        dzz = ax[n_x+n_ineq+n_eq:n_x+n_ineq+n_eq+n_ineq]

        s_list = []
        for ii in range(n_ineq):
            s_list.append(-0.995 * s[ii] / (dss[ii] + 1e-20))

        s_list_filtered = [num for num in s_list if 0 < num <= 1]
        as_max = min(s_list_filtered, default=1)

        z_list = []
        for ii in range(n_ineq):
            z_list.append(-0.995 * z[ii] / (dzz[ii] + 1e-20))

        z_list_filtered = [num for num in z_list if 0 < num <= 1]
        az_max = min(z_list_filtered, default=1)

        incr = 0.5

        x += as_max * dxx
        s += as_max * dss
        y += az_max * dyy
        z += az_max * dzz

        # Objective function
        f_obj = compute_fobj(pg=x[x_ind[2]:x_ind[3]],
                             cost0=nc.generator_data.cost_0,
                             cost1=nc.generator_data.cost_1,
                             cost2=nc.generator_data.cost_2)

        mu *= 0.5
        it += 1

        err_list.append(err)

        if verbose > 1:
            print('x: ', x)
            print('s: ', s)
            print('z: ', z)
            print('y: ', y)
            print('f: ', f_obj)
            print('err: ', err)
            print('--------------------')

    # Post-process, print a bit better the results

    vv = x[x_ind[0]:x_ind[1]] + 1j * x[x_ind[1]:x_ind[2]]
    vx = nc.Vbus
    vx[pqpv] = vv[:]
    vm = abs(vx)
    va = np.angle(vx) * 180 / np.pi

    ppgen = x[x_ind[2]:x_ind[3]]
    qqgen = x[x_ind[3]:x_ind[4]]

    ssf = (nc.Cf @ vx) * np.conj(nc.Yf @ vx)
    sst = (nc.Ct @ vx) * np.conj(nc.Yt @ vx)

    if verbose > 0:
        print(f'N iter: {it}')
        print(f'Vm: {vm}')
        print(f'Va: {va}')
        print(f'Pg: {ppgen}')
        print(f'Qg: {qqgen}')
        print(f'Sf: {abs(ssf)}')
        print(f'St: {abs(sst)}')

    return x, s, y, z, mu, err_list


def modify_grid(grid:gce.MultiCircuit = None):
    """

    :param grid:
    :return:
    """

    # grid.lines[1].rate = 25
    # grid.get_generators()[0].Cost2 = 0.5
    # grid.buses[1].Vmax = 1.1
    # grid.buses[1].Vmin = 1.09


if __name__ == '__main__':
    # system = build_grid_3bus()
    system = linn5bus_example()
    x0, s0, y0, z0, mu0, err0 = solve_opf(system, verbose=1)
    modify_grid(system)
    # x1, s1, y1, z1, mu1, err1 = solve_opf(system, x0=x0, s0=s0, y0=y0, z0=z0, mu0=mu0, verbose=1)
    x1, s1, y1, z1, mu1, err1 = solve_opf(system, verbose=1)

    print(err0)
    print(err1)

