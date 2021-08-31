import GridCal.Engine as gc
from ortools.linear_solver import pywraplp
import numpy as np
import pandas as pd
from scipy.sparse.csc import csc_matrix


def lpDot(mat, arr):
    """
    CSC matrix-vector or CSC matrix-matrix dot product (A x b)
    :param mat: CSC sparse matrix (A)
    :param arr: dense vector or matrix of object type (b)
    :return: vector or matrix result of the product
    """
    n_rows, n_cols = mat.shape

    # check dimensional compatibility
    assert (n_cols == arr.shape[0])

    # check that the sparse matrix is indeed of CSC format
    if mat.format == 'csc':
        mat_2 = mat
    else:
        # convert the matrix to CSC sparse
        mat_2 = csc_matrix(mat)

    if len(arr.shape) == 1:
        """
        Uni-dimensional sparse matrix - vector product
        """
        res = np.zeros(n_rows, dtype=arr.dtype)
        for i in range(n_cols):
            for ii in range(mat_2.indptr[i], mat_2.indptr[i + 1]):
                j = mat_2.indices[ii]  # row index
                res[j] += mat_2.data[ii] * arr[i]  # C.data[ii] is equivalent to C[i, j]
    else:
        """
        Multi-dimensional sparse matrix - matrix product
        """
        cols_vec = arr.shape[1]
        res = np.zeros((n_rows, cols_vec), dtype=arr.dtype)

        for k in range(cols_vec):  # for each column of the matrix "vec", do the matrix vector product
            for i in range(n_cols):
                for ii in range(mat_2.indptr[i], mat_2.indptr[i + 1]):
                    j = mat_2.indices[ii]  # row index
                    res[j, k] += mat_2.data[ii] * arr[i, k]  # C.data[ii] is equivalent to C[i, j]
    return res


def lpExpand(mat, arr):
    """
    CSC matrix-vector or CSC matrix-matrix dot product (A x b)
    :param mat: CSC sparse matrix (A)
    :param arr: dense vector or matrix of object type (b)
    :return: vector or matrix result of the product
    """
    n_rows, n_cols = mat.shape

    # check dimensional compatibility
    assert (n_cols == arr.shape[0])

    # check that the sparse matrix is indeed of CSC format
    if mat.format == 'csc':
        mat_2 = mat
    else:
        # convert the matrix to CSC sparse
        mat_2 = csc_matrix(mat)

    if len(arr.shape) == 1:
        """
        Uni-dimensional sparse matrix - vector product
        """
        res = np.zeros(n_rows, dtype=arr.dtype)
        for i in range(n_cols):
            for ii in range(mat_2.indptr[i], mat_2.indptr[i + 1]):
                j = mat_2.indices[ii]  # row index
                res[j] = arr[i]  # C.data[ii] is equivalent to C[i, j]
    else:
        """
        Multi-dimensional sparse matrix - matrix product
        """
        cols_vec = arr.shape[1]
        res = np.zeros((n_rows, cols_vec), dtype=arr.dtype)

        for k in range(cols_vec):  # for each column of the matrix "vec", do the matrix vector product
            for i in range(n_cols):
                for ii in range(mat_2.indptr[i], mat_2.indptr[i + 1]):
                    j = mat_2.indices[ii]  # row index
                    res[j, k] = arr[i, k]  # C.data[ii] is equivalent to C[i, j]
    return res


def get_inter_areas_branches(nbr, F, T, buses_areas_1, buses_areas_2):
    """
    Get the inter-area branches.
    :param buses_areas_1: Area from
    :param buses_areas_2: Area to
    :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
    """
    lst: List[Tuple[int, float]] = list()
    for k in range(nbr):
        if F[k] in buses_areas_1 and T[k] in buses_areas_2:
            lst.append((k, 1.0))
        elif F[k] in buses_areas_2 and T[k] in buses_areas_1:
            lst.append((k, -1.0))
    return lst


def get_generators_connectivity(Cgen, buses_in_a1, buses_in_a2):
    """

    :param Cgen:
    :param buses_in_a1:
    :param buses_in_a2:
    :return:
    """
    assert isinstance(Cgen, csc_matrix)

    gens_in_a1 = list()
    gens_in_a2 = list()
    gens_out = list()
    for j in range(Cgen.shape[1]):  # for each bus
        for ii in range(Cgen.indptr[j], Cgen.indptr[j + 1]):
            i = Cgen.indices[ii]
            if i in buses_in_a1:
                gens_in_a1.append((i, j))  # i: bus idx, j: gen idx
            elif i in buses_in_a2:
                gens_in_a2.append((i, j))  # i: bus idx, j: gen idx
            else:
                gens_out.append((i, j))  # i: bus idx, j: gen idx

    return gens_in_a1, gens_in_a2, gens_out


def compose_branches_df(num, solver_power_vars, overloads1, overloads2):

    data = list()
    for k in range(num.nbr):
        val = solver_power_vars[k].solution_value() * num.Sbase
        row = [
            num.branch_data.branch_names[k],
            val,
            val / nc.Rates[k],
            overloads1[k].solution_value(),
            overloads2[k].solution_value()
        ]
        data.append(row)

    cols = ['Name', 'Power (MW)', 'Loading', 'SlackF', 'SlackT']
    return pd.DataFrame(data, columns=cols)


def compose_generation_df(num, generation, dgen_arr, Pgen_arr):

    data = list()
    for i, (var, dgen, pgen) in enumerate(zip(generation, dgen_arr, Pgen_arr)):
        if not isinstance(var, float):
            data.append([str(var),
                         '',
                         var.Lb() * nc.Sbase,
                         var.solution_value() * nc.Sbase,
                         pgen * nc.Sbase,
                         dgen.solution_value() * nc.Sbase,
                         var.Ub() * nc.Sbase])

    cols = ['Name', 'Bus', 'LB', 'Power (MW)', 'Set (MW)', 'Delta (MW)', 'UB']
    return pd.DataFrame(data=data, columns=cols)

# ----------------------------------------------------------------------------------------------------------------------
# Net transfer capacity optimization program 2021
# ----------------------------------------------------------------------------------------------------------------------

# fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/PGOC_6bus(from .raw).gridcal'
# fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/Grid4Bus-OPF.gridcal'
# fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118 Bus - ntc_areas.gridcal'
fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'
# fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/PGOC_6bus_modNTC.gridcal'

# fname = r'C:\Users\penversa\Git\Github\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'
# fname = r'C:\Users\penversa\Git\Github\GridCal\Grids_and_profiles\grids\IEEE14 - ntc areas.gridcal'
# fname = r'D:\ReeGit\github\GridCal\Grids_and_profiles\grids\PGOC_6bus_modNTC.gridcal'

grid = gc.FileOpen(fname).open()
nc = gc.compile_snapshot_opf_circuit(grid)
print('Problem loaded:')
print('\tNodes:', nc.nbus)
print('\tBranches:', nc.nbr)

# compute information about areas --------------------------------------------------------------------------------------

area_from_idx = 0
area_to_idx = 1
areas = grid.get_bus_area_indices()

# get the area bus indices
areas = areas[nc.original_bus_idx]
a1 = np.where(areas == area_from_idx)[0]
a2 = np.where(areas == area_to_idx)[0]

# get the inter-area branches and their sign
inter_area_branches = get_inter_areas_branches(nc.nbr, nc.branch_data.F, nc.branch_data.T, a1, a2)

# time index
t = 0

# declare the solver ---------------------------------------------------------------------------------------------------
solver = pywraplp.Solver.CreateSolver('CBC')


# create generation delta functions ------------------------------------------------------------------------------------
Cgen = nc.generator_data.C_bus_gen.tocsc()
gen_cost = nc.generator_data.generator_cost[:, t]
Pgen = nc.generator_data.generator_p[:, t] / nc.Sbase
Pmax = nc.generator_data.generator_installed_p / nc.Sbase
gens1, gens2, gens_out = get_generators_connectivity(Cgen, a1, a2)
generation = np.zeros(nc.generator_data.ngen, dtype=object)
dgen1 = list()
dgen2 = list()
delta = list()
generation1 = list()
generation2 = list()
Pgen1 = list()
Pgen2 = list()
for bus_idx, gen_idx in gens1:
    name = 'Gen_up_bus{}'.format(bus_idx)
    generation[gen_idx] = solver.NumVar(0, Pmax[gen_idx], name)
    dg = solver.NumVar(0, Pmax[gen_idx] - Pgen[gen_idx], name + '_delta')
    solver.Add(dg == generation[gen_idx] - Pgen[gen_idx])
    dgen1.append(dg)
    delta.append(dg)
    generation1.append(generation[gen_idx])
    Pgen1.append(Pgen[gen_idx])

for bus_idx, gen_idx in gens2:
    name = 'Gen_down_bus{}'.format(bus_idx)
    generation[gen_idx] = solver.NumVar(0, Pmax[gen_idx], name)
    dg = solver.NumVar(-Pgen[gen_idx], 0, name + '_delta')
    solver.Add(dg == generation[gen_idx] - Pgen[gen_idx])
    dgen2.append(dg)
    delta.append(dg)
    generation2.append(generation[gen_idx])
    Pgen2.append(Pgen[gen_idx])

# set the generation in the non inter-area ones
for bus_idx, gen_idx in gens_out:
    generation[gen_idx] = Pgen[gen_idx]

area_balance_slack = solver.NumVar(0, 99999, 'Area_slack')
solver.Add(solver.Sum(dgen1) + solver.Sum(dgen2) == area_balance_slack, 'Area equality')


# create the angles ----------------------------------------------------------------------------------------------------
Cf = nc.Cf.tocsc()
Ct = nc.Ct.tocsc()
angles = np.array([solver.NumVar(-6.28, 6.28, 'theta' + str(i)) for i in range(nc.nbus)])
# angles_f = lpExpand(Cf, angles)
# angles_t = lpExpand(Ct, angles)

# Set the slack angles = 0 ---------------------------------------------------------------------------------------------
for i in nc.vd:
    solver.Add(angles[i] == 0, "Slack_angle_zero")

# create the phase shift angles ----------------------------------------------------------------------------------------
tau = dict()
for i in range(nc.branch_data.nbr):
    if nc.branch_data.control_mode[i] == gc.TransformerControlType.Pt:  # is a phase shifter
        tau[i] = solver.NumVar(nc.branch_data.theta_min[i], nc.branch_data.theta_max[i], 'tau' + str(i))

# define the power injection -------------------------------------------------------------------------------------------
gen_injections = lpExpand(Cgen, generation)
load_fixed_injections = nc.load_data.get_injections_per_bus()[:, t].real / nc.Sbase  # with sign already
Pinj = gen_injections + load_fixed_injections

# nodal balance --------------------------------------------------------------------------------------------------------

# power balance in the non slack nodes: eq.13
node_balance = lpDot(nc.Bbus, angles)

node_balance_slack_1 = [solver.NumVar(0, 99999, 'balance_slack1_' + str(i)) for i in range(nc.nbus)]
node_balance_slack_2 = [solver.NumVar(0, 99999, 'balance_slack2_' + str(i)) for i in range(nc.nbus)]

# equal the balance to the generation: eq.13,14 (equality)
i = 0
for balance, power in zip(node_balance, Pinj):
    solver.Add(balance == power + node_balance_slack_1[i] - node_balance_slack_2[i], "Node_power_balance_" + str(i))
    i += 1

# branch flow ----------------------------------------------------------------------------------------------------------

pftk = list()
rates = nc.Rates / nc.Sbase
overload1 = np.empty(nc.nbr, dtype=object)
overload2 = np.empty(nc.nbr, dtype=object)
for i in range(nc.nbr):

    _f = nc.branch_data.F[i]
    _t = nc.branch_data.T[i]
    pftk.append(solver.NumVar(-rates[i], rates[i], 'pftk_' + str(i)))

    # compute the branch susceptance
    bk = (1.0 / complex(nc.branch_data.R[i], nc.branch_data.X[i])).imag

    if i in tau.keys():
        # branch power from-to eq.15
        solver.Add(pftk[i] == bk * (angles[_t] - angles[_f] - tau[i]), 'phase_shifter_power_flow_' + str(i))
    else:
        # branch power from-to eq.15
        solver.Add(pftk[i] == bk * (angles[_t] - angles[_f]), 'branch_power_flow_' + str(i))

    # rating restriction in the sense from-to: eq.17
    overload1[i] = solver.NumVar(0, 9999, 'overload1_' + str(i))
    solver.Add(pftk[i] <= (rates[i] + overload1[i]), "ft_rating_" + str(i))

    # rating restriction in the sense to-from: eq.18
    overload2[i] = solver.NumVar(0, 9999, 'overload2_' + str(i))
    solver.Add((-rates[i] - overload2[i]) <= pftk[i], "tf_rating_" + str(i))

# objective function ---------------------------------------------------------------------------------------------------

# maximize the power from->to
flows_ft = np.zeros(len(inter_area_branches), dtype=object)
for i, (k, sign) in enumerate(inter_area_branches):
    flows_ft[i] = sign * pftk[k]

flow_from_a1_to_a2 = solver.Sum(flows_ft)

# include the cost of generation
# gen_cost_f = solver.Sum(gen_cost * delta)

node_balance_slack_f = solver.Sum(node_balance_slack_1) + solver.Sum(node_balance_slack_2)

overload_slack_f = solver.Sum(overload1) + solver.Sum(overload2)

# objective function
solver.Minimize(
                # - 1.0 * flow_from_a1_to_a2
                - 1.0 * solver.Sum(dgen1)
                + 1.0 * area_balance_slack
                # + 1.0 * gen_cost_f
                + 1e0 * node_balance_slack_f
                + 1e0 * overload_slack_f
                )

# Solve ----------------------------------------------------------------------------------------------------------------
status = solver.Solve()

# print results --------------------------------------------------------------------------------------------------------
if status == pywraplp.Solver.OPTIMAL:
    print('Solution:')
    print('Objective value =', solver.Objective().Value())

    print('\nPower flow:')
    print(compose_branches_df(nc, pftk, overload1, overload2))

    print('\nPower flow inter-area:')
    total_pw = 0
    for k, sign in inter_area_branches:
        total_pw += sign * pftk[k].solution_value()
        print(nc.branch_data.branch_names[k], ':', pftk[k].solution_value() * nc.Sbase, 'MW')
    print('Total exchange:', flow_from_a1_to_a2.solution_value() * nc.Sbase, 'MW')

    print('\nGenerators:')
    print(compose_generation_df(nc, generation1, dgen1, Pgen1))
    print(compose_generation_df(nc, generation2, dgen2, Pgen2))
    print()
    print('node balance slack:', node_balance_slack_f.solution_value())
    print('Reference node:', nc.vd)
    for i, (var1, var2) in enumerate(zip(node_balance_slack_1, node_balance_slack_2)):
        print('node slack {0}'.format(i), var1.solution_value(), var2.solution_value())

    print('area balance slack:', area_balance_slack.solution_value())

else:
    print('The problem does not have an optimal solution.')
# [END print_solution]

# [START advanced]
print('\nAdvanced usage:')
print('Problem solved in %f milliseconds' % solver.wall_time())
print('Problem solved in %d iterations' % solver.iterations())

print()

