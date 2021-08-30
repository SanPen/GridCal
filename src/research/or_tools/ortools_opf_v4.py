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


def get_generators_connectivity(Cgen):

    assert isinstance(Cgen, csc_matrix)

    gens_in_a1 = list()
    gens_in_a2 = list()
    for j in range(Cgen.shape[1]):
        for ii in range(Cgen.indptr[j], Cgen.indptr[j + 1]):
            i = Cgen.indices[ii]
            if i in a1:
                gens_in_a1.append((i, j))  # i: bus idx, j: gen idx
            elif i in a2:
                gens_in_a2.append((i, j))  # i: bus idx, j: gen idx

    return gens_in_a1, gens_in_a2


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

def compose_generation_df(num, generation):

    data = list()
    for i, var in enumerate(generation):
        if not isinstance(var, float):
            data.append([str(var), '', var.Lb() * nc.Sbase, var.solution_value() * nc.Sbase, var.Ub() * nc.Sbase])
        else:
            data.append([num.generator_data.generator_names[i], '', 0, num.generator_data.generator_p[i, t], 0])

    cols = ['Name', 'Bus', 'LB', 'Power (MW)', 'UB']
    return pd.DataFrame(data=data, columns=cols)

# ----------------------------------------------------------------------------------------------------------------------
# Net transfer capacity optimization program 2021
# ----------------------------------------------------------------------------------------------------------------------

# fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/PGOC_6bus(from .raw).gridcal'
# fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118 Bus - ntc_areas.gridcal'
fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'
# fname = r'C:\Users\penversa\Git\Github\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'
# fname = r'D:\ReeGit\github\GridCal\Grids_and_profiles\grids\PGOC_6bus(from .raw).gridcal'

grid = gc.FileOpen(fname).open()
nc = gc.compile_snapshot_opf_circuit(grid)
print('Problem loaded:')
print('\tNodes:', nc.nbus)
print('\tBranches:', nc.nbr)

threshold = 0.02

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


# compute the branch exchange sensitivity (alpha)-----------------------------------------------------------------------

# declare the linear analysis
linear = gc.LinearAnalysis(grid=grid,
                           distributed_slack=False,
                           correct_values=False)
linear.run()

dP = gc.compute_dP(ptdf=linear.PTDF,
                   P0=nc.Sbus.real,
                   Pinstalled=nc.bus_installed_power,
                   idx1=a1,
                   idx2=a2,
                   bus_types=nc.bus_types.astype(int),
                   dT=100,
                   mode=1)  # mode 1: based on installed power

alpha = gc.compute_alpha(ptdf=linear.PTDF,
                         P0=nc.Sbus.real,
                         Pinstalled=nc.bus_installed_power,
                         idx1=a1,
                         idx2=a2,
                         bus_types=nc.bus_types.astype(int),
                         dT=100,
                         mode=1)

# pick constants -------------------------------------------------------------------------------------------------------
P = nc.Sbus.real  # already in p.u.
Cgen = nc.generator_data.C_bus_gen.tocsc()
Cf = nc.Cf.tocsc()
Ct = nc.Ct.tocsc()
rates = nc.Rates / nc.Sbase
gen_cost = nc.generator_data.generator_cost[:, t]

# declare the solver ---------------------------------------------------------------------------------------------------
solver = pywraplp.Solver.CreateSolver('CBC')

# create the angles ----------------------------------------------------------------------------------------------------
angles = np.array([solver.NumVar(-6.28, 6.28, 'theta' + str(i)) for i in range(nc.nbus)])
angles_pqpv = angles[nc.pqpv]
angles_sl = angles[nc.vd]
angles_f = lpExpand(Cf, angles)
angles_t = lpExpand(Ct, angles)

# Set the slack angles = 0 ---------------------------------------------------------------------------------------------
for i in nc.vd:
    solver.Add(angles[i] == 0, "Slack_angle_zero")

# create the phase shift angles ----------------------------------------------------------------------------------------
tau = dict()
for i in range(nc.branch_data.nbr):
    if nc.branch_data.control_mode[i] == gc.TransformerControlType.Pt:  # is a phase shifter
        tau[i] = solver.NumVar(nc.branch_data.theta_min[i], nc.branch_data.theta_max[i], 'tau' + str(i))

# create generation delta functions ------------------------------------------------------------------------------------
margin_up = (nc.generator_data.generator_installed_p - nc.generator_data.generator_p[:, t]) / nc.Sbase
margin_down = nc.generator_data.generator_p[:, t] / nc.Sbase
gens_in_a1, gens_in_a2 = get_generators_connectivity(Cgen)

area_exchange = solver.NumVar(0, 9999, 'Area exchange')
Pinj = P + dP / 100 * area_exchange


# nodal balance --------------------------------------------------------------------------------------------------------

# power balance in the non slack nodes: eq.13
node_balance = lpDot(nc.Bbus, angles)

kirchoff_slacks = list()

# equal the balance to the generation: eq.13,14 (equality)
i = 0
for balance, power in zip(node_balance, Pinj):
    kirchoff_slacks.append(solver.NumVar(0, 9999, 'krch_{}'.format(i)))
    solver.Add(balance == power + kirchoff_slacks[i], "Node_power_balance_" + str(i))
    i += 1

# branch flow ----------------------------------------------------------------------------------------------------------
pftk = [solver.NumVar(-9999, 9999, 'pftk_' + str(i)) for i in range(nc.nbr)]
overload1 = np.empty(nc.nbr, dtype=object)
overload2 = np.empty(nc.nbr, dtype=object)
for i in range(nc.nbr):

    # compute the branch susceptance
    bk = (1.0 / complex(nc.branch_data.R[i], nc.branch_data.X[i])).imag

    if i in tau.keys():
        # branch power from-to eq.15
        solver.Add(pftk[i] == bk * (angles_f[i] - angles_t[i] - tau[i]), 'phase_shifter_power_flow_' + str(i))
    else:
        # branch power from-to eq.15
        solver.Add(pftk[i] == bk * (angles_f[i] - angles_t[i]), 'branch_power_flow_' + str(i))

    # rating restriction in the sense from-to: eq.17
    overload1[i] = solver.NumVar(0, 9999, 'overload1_' + str(i))
    overload2[i] = solver.NumVar(0, 9999, 'overload2_' + str(i))

    # if abs(alpha[i]) > threshold:
    #     solver.Add((-rates[i] - overload2[i]) <= pftk[i], "tf_rating_" + str(i))
    #     solver.Add(pftk[i] <= (rates[i] + overload1[i]), "ft_rating_" + str(i))


# objective function ---------------------------------------------------------------------------------------------------

# maximize the power from->to
flows_ft = np.zeros(len(inter_area_branches), dtype=object)
i = 0
for k, sign in inter_area_branches:
    flows_ft[i] = sign * pftk[k]
    i += 1
flow_from_a1_to_a2 = solver.Sum(flows_ft)

# reduce the overload slacks
overload_sum = solver.Sum(overload1) + solver.Sum(overload2)

# objective function
solver.Minimize(
                # - 1.0 * flow_from_a1_to_a2
                - 1.0 * area_exchange
                + 1e4 * overload_sum
                + 1.0 * solver.Sum(kirchoff_slacks)
                )

# Solve ----------------------------------------------------------------------------------------------------------------
status = solver.Solve()

# save the problem in LP format to debug
lp_content = solver.ExportModelAsLpFormat(obfuscated=False)
# lp_content = solver.ExportModelAsMpsFormat(obfuscated=False, fixed_format=True)
file2write = open("ortools_v4.lp", 'w')
file2write.write(lp_content)
file2write.close()

# print results --------------------------------------------------------------------------------------------------------
if status != pywraplp.Solver.INFEASIBLE:
    print(status)
    print('Solution:')
    print('Objective value =', solver.Objective().Value())
    print('\nPower flow:')
    print(compose_branches_df(nc, pftk, overload1, overload2))

    print('\nPower flow:')
    for var in kirchoff_slacks:
        print(str(var), var.solution_value() * nc.Sbase, 'MW')

    print('\nArea exchange:', area_exchange.solution_value() * nc.Sbase, 'MW')

    print('\nPower flow inter-area:')
    total_pw = 0
    for k, sign in inter_area_branches:
        total_pw += sign * pftk[k].solution_value()
        print(nc.branch_data.branch_names[k], pftk[k].solution_value() * nc.Sbase, 'MW')

    print('\nTotal power from-to', total_pw * nc.Sbase, 'MW')
    print(str(area_power_slack), area_power_slack.solution_value() * nc.Sbase, 'MW')
else:
    print('The problem does not have an optimal solution.')
# [END print_solution]

# [START advanced]
print('\nAdvanced usage:')
print('Problem solved in %f milliseconds' % solver.wall_time())
print('Problem solved in %d iterations' % solver.iterations())

print()
