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
# fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'
# fname = r'C:\Users\penversa\Git\Github\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'
# fname = r'C:\Users\penversa\Git\Github\GridCal\Grids_and_profiles\grids\IEEE14 - ntc areas.gridcal'
fname = r'D:\ReeGit\github\GridCal\Grids_and_profiles\grids\IEEE14 - ntc areas.gridcal'

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

# create the angles ----------------------------------------------------------------------------------------------------
angles = np.array([solver.NumVar(-6.28, 6.28, 'theta' + str(i)) for i in range(nc.nbus)])
angles_pqpv = angles[nc.pqpv]


# power balance in the non slack nodes: eq.13
node_balance = lpDot(nc.Bbus, angles)

# create power injections ----------------------------------------------------------------------------------------------
P = nc.Sbus.real  # already in p.u.
Pinj = np.zeros(nc.nbus, dtype=object)
for i in range(nc.nbus):
    Pinj[i] = P[i]


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
    name = 'Gen_up_{}'.format(gen_idx)
    generation[gen_idx] = solver.NumVar(0, Pmax[gen_idx], name)
    dg = solver.NumVar(0, Pmax[gen_idx] - Pgen[gen_idx], name + '_delta')
    solver.Add(dg == generation[gen_idx] - Pgen[gen_idx])
    dgen1.append(dg)
    delta.append(dg)
    generation1.append(generation[gen_idx])
    Pgen1.append(Pgen[gen_idx])
    # add generation deltas: eq.10
    Pinj[bus_idx] += dg

for bus_idx, gen_idx in gens2:
    name = 'Gen_down_{}'.format(gen_idx)
    generation[gen_idx] = solver.NumVar(0, Pmax[gen_idx], name)
    dg = solver.NumVar(-Pgen[gen_idx], 0, name + '_delta')
    solver.Add(dg == generation[gen_idx] - Pgen[gen_idx])
    dgen2.append(dg)
    delta.append(dg)
    generation2.append(generation[gen_idx])
    Pgen2.append(Pgen[gen_idx])
    # add generation deltas: eq.10
    Pinj[bus_idx] += dg

# set the generation in the non inter-area ones
for bus_idx, gen_idx in gens_out:
    generation[gen_idx] = Pgen[gen_idx]



# equal the balance to the generation: eq.13,14 (equality)
i = 0
for balance, power in zip(node_balance, Pinj):
    solver.Add(balance == power, "Node_power_balance_" + str(i))
    i += 1

total_power_slack = solver.NumVar(0, 99999, 'Total_slack')
solver.Add(solver.Sum(dgen1) + solver.Sum(dgen2) == total_power_slack, 'Balance equality')

# area1_power_slack = solver.NumVar(0, 99999, 'Area1_slack')
# solver.Add(solver.Sum(dgen1) == area1_power_slack, 'Area1 Balance')

# area2_power_slack = solver.NumVar(0, 99999, 'Area2_slack')
# solver.Add(solver.Sum(dgen2) == area2_power_slack, 'Area2 Balance')



# include the cost of generation
gen_cost_f = solver.Sum(gen_cost * delta)


# objective function ---------------------------------------------------------------------------------------------------

solver.Minimize(
                + 1.0 * total_power_slack
                # + 1.0 * gen_cost_f
                )

# Solve ----------------------------------------------------------------------------------------------------------------
status = solver.Solve()

# print results --------------------------------------------------------------------------------------------------------
if status == pywraplp.Solver.OPTIMAL:
    print('Solution:')
    print('Objective value =', solver.Objective().Value())

    print('\nGenerators:')
    print(compose_generation_df(nc, generation1, dgen1, Pgen1))
    print(compose_generation_df(nc, generation2, dgen2, Pgen2))

else:
    print('The problem does not have an optimal solution.')
# [END print_solution]

# [START advanced]
print('\nAdvanced usage:')
print('Problem solved in %f milliseconds' % solver.wall_time())
print('Problem solved in %d iterations' % solver.iterations())

print()

