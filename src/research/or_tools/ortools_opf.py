import GridCal.Engine as gc
from ortools.linear_solver import pywraplp
import numpy as np


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


def get_inter_areas_branches(nbr, F, T, areas_1, areas_2):
    """
    Get the inter-area branches.
    :param a1: Area from
    :param a2: Area to
    :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
    """
    lst: List[Tuple[int, float]] = list()
    for k in range(nbr):
        if F[k] in areas_1 and T[k] in areas_2:
            lst.append((k, 1.0))
        elif F[k] in areas_2 and T[k] in areas_1:
            lst.append((k, -1.0))
    return lst


fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118 Bus - ntc_areas.gridcal'
# fname = r'C:\Users\penversa\Git\Github\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'
# fname = r'D:\ReeGit\github\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

grid = gc.FileOpen(fname).open()

area_from_idx = 0
area_to_idx = 2
areas = grid.get_bus_area_indices()

nc = gc.compile_snapshot_circuit(grid)

# get the area bus indices
areas = areas[nc.original_bus_idx]
a1 = np.where(areas == area_from_idx)[0]
a2 = np.where(areas == area_to_idx)[0]

# get the inter-area branches and their sign
inter_area_branches = get_inter_areas_branches(nc.nbr, nc.branch_data.F, nc.branch_data.T, a1, a2)

# pick constants
Bpqpv = nc.Bpqpv
Bsl = nc.Bbus[nc.vd, :]
P = nc.Sbus.real  # already in p.u.
Cgen = nc.generator_data.C_bus_gen.tocsc()
Cf = nc.Cf.tocsc()
Ct = nc.Ct.tocsc()
rates = nc.Rates / nc.Sbase

# time index
t = 0

# declare the solver
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
dgen_per_bus = np.zeros(nc.nbus, dtype=object)
gen_indices_per_bus = lpExpand(Cgen, np.arange(nc.generator_data.ngen))
Pinj = np.zeros(nc.nbus, dtype=object)

# generators in area 1 (increase generation)
for i1 in a1:
    ig = gen_indices_per_bus[i1]
    dgen_per_bus[i1] = solver.NumVar(0, int(margin_up[ig]), 'dGen_up_' + str(i1))

    # add generation deltas: eq.10
    Pinj[i1] = P[i1] + dgen_per_bus[i1]

# generators in area 2 (decrease generation)
for i2 in a2:
    ig = gen_indices_per_bus[i2]
    dgen_per_bus[i2] = solver.NumVar(-int(margin_down[ig]), 0, 'dGen_down_' + str(i2))

    # add generation deltas: eq.10
    Pinj[i2] = P[i2] + dgen_per_bus[i2]


# nodal balance --------------------------------------------------------------------------------------------------------
node_balance = np.empty(nc.nbus, dtype=object)

# power balance in the non slack nodes: eq.13
node_balance[nc.pqpv] = lpDot(Bpqpv, angles_pqpv)

# power balance in the slack nodes: eq.14
node_balance[nc.vd] = lpDot(Bsl, angles)

# equal the balance to the generation: eq.13,14 (equality)
i = 0
for balance, power in zip(node_balance, Pinj):
    solver.Add(balance == power, "Node_power_balance_" + str(i))
    i += 1

# branch flow ----------------------------------------------------------------------------------------------------------
pftk = np.empty(nc.nbr, dtype=object)
overload1 = np.empty(nc.nbr, dtype=object)
overload2 = np.empty(nc.nbr, dtype=object)
for i in range(nc.nbr):

    # compute the branch susceptance
    bk = (1.0 / complex(nc.branch_data.R[i], nc.branch_data.X[i])).imag

    if i in tau.keys():
        tau_k = tau[i]
    else:
        tau_k = 0

    # branch power from-to eq.15
    pftk[i] = bk * (angles_f[i] - angles_t[i] - tau_k)

    # # rating restriction in the sense from-to: eq.17
    overload1[i] = solver.NumVar(0, 9999, 'overload1_' + str(i))
    solver.Add(pftk[i] <= (rates[i] + overload1[i]), "ft_rating_" + str(i))
    #
    # # rating restriction in the sense to-from: eq.18
    overload2[i] = solver.NumVar(0, 9999, 'overload2_' + str(i))
    solver.Add((-rates[i] - overload2[i]) <= pftk[i], "tf_rating_" + str(i))


# objective function ---------------------------------------------------------------------------------------------------

flow_from_a1_to_a2 = 0
for k, sign in inter_area_branches:
    flow_from_a1_to_a2 += pftk[k] * sign
overload_sum = sum(overload1) + sum(overload2)

solver.Maximize(flow_from_a1_to_a2 - overload_sum)

# Solve ----------------------------------------------------------------------------------------------------------------
status = solver.Solve()

# save the problem in LP format to debug
lp_content = solver.ExportModelAsLpFormat(obfuscated=False)
# lp_content = solver.ExportModelAsMpsFormat(obfuscated=False, fixed_format=True)
file2write = open("ortools.lp", 'w')
file2write.write(lp_content)
file2write.close()

# print results --------------------------------------------------------------------------------------------------------
if status == pywraplp.Solver.OPTIMAL:
    print('Solution:')
    print('Objective value =', solver.Objective().Value())
    print('Power flow:')
    for x in pftk:
        print(x.solution_value())

    print('Power flow inter-area:')
    for k, sign in inter_area_branches:
        print(pftk[k].solution_value())

else:
    print('The problem does not have an optimal solution.')
# [END print_solution]

# [START advanced]
print('\nAdvanced usage:')
print('Problem solved in %f milliseconds' % solver.wall_time())
print('Problem solved in %d iterations' % solver.iterations())

print()
