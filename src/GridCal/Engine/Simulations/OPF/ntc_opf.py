# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

"""
This file implements a DC-OPF for time series
That means that solves the OPF problem for a complete time series at once
"""
from enum import Enum
from typing import List, Dict, Tuple
import numpy as np
from GridCal.Engine.Core.snapshot_opf_data import SnapshotOpfData
from GridCal.Engine.Simulations.OPF.opf_templates import Opf, MIPSolvers
from GridCal.Engine.Devices.enumerations import TransformerControlType, ConverterControlType, HvdcControlType, GenerationNtcFormulation
from GridCal.Engine.basic_structures import Logger

try:
    from ortools.linear_solver import pywraplp
except ModuleNotFoundError:
    print('ORTOOLS not found :(')

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


def extract(arr, make_abs=False):  # override this method to call ORTools instead of PuLP
    """
    Extract values fro the 1D array of LP variables
    :param arr: 1D array of LP variables
    :param make_abs: substitute the result by its abs value
    :return: 1D numpy array
    """

    if isinstance(arr, list):
        arr = np.array(arr)

    val = np.zeros(arr.shape)
    for i in range(val.shape[0]):
        if isinstance(arr[i], float) or isinstance(arr[i], int):
            val[i] = arr[i]
        else:
            val[i] = arr[i].solution_value()
    if make_abs:
        val = np.abs(val)

    return val

def save_lp(solver, file_name="ntc_opf_problem.lp"):
    """
    Save problem in LP format
    :param file_name: name of the file (.lp or .mps supported)
    """
    # save the problem in LP format to debug
    if file_name.lower().endswith('.lp'):
        lp_content = solver.ExportModelAsLpFormat(obfuscated=False)
    elif file_name.lower().endswith('.mps'):
        lp_content = solver.ExportModelAsMpsFormat(obfuscated=False, fixed_format=True)
    else:
        raise Exception('Unsupported file format')
    file2write = open(file_name, 'w')
    file2write.write(lp_content)
    file2write.close()


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
            val / num.Rates[k],
            overloads1[k].solution_value(),
            overloads2[k].solution_value()
        ]
        data.append(row)

    cols = ['Name', 'Power (MW)', 'Loading', 'SlackF', 'SlackT']
    return pd.DataFrame(data, columns=cols)


def compose_generation_df(nc, generation, dgen_arr, Pgen_arr):

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


def formulate_optimal_generation(solver: pywraplp.Solver,
                                 generator_active, dispatchable, generator_cost,
                                 generator_names, Sbase, logger, inf,
                                 ngen, Cgen, Pgen, Pmax, Pmin, a1, a2, t=0):
    """

    :param solver:
    :param generator_active:
    :param dispatchable:
    :param generator_cost:
    :param generator_names:
    :param Sbase:
    :param logger:
    :param inf:
    :param ngen:
    :param Cgen:
    :param Pgen:
    :param Pmax:
    :param Pmin:
    :param a1:
    :param a2:
    :param t:
    :return:
    """
    gens1, gens2, gens_out = get_generators_connectivity(Cgen, a1, a2)
    gen_cost = generator_cost[:, t] * Sbase  # pass from $/MWh to $/p.u.h
    generation = np.zeros(ngen, dtype=object)
    delta = np.zeros(ngen, dtype=object)
    delta_slack_1 = np.zeros(ngen, dtype=object)
    delta_slack_2 = np.zeros(ngen, dtype=object)

    dgen1 = list()
    dgen2 = list()

    generation1 = list()
    generation2 = list()

    Pgen1 = list()
    Pgen2 = list()

    gen_a1_idx = list()
    gen_a2_idx = list()

    for bus_idx, gen_idx in gens1:

        if generator_active[gen_idx] and dispatchable[gen_idx]:
            name = 'Gen_up_{0}@bus{1}_{2}'.format(gen_idx, bus_idx, generator_names[gen_idx])

            if Pmin[gen_idx] >= Pmax[gen_idx]:
                logger.add_error('Pmin >= Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

            generation[gen_idx] = solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
            delta[gen_idx] = solver.NumVar(0, inf, name + '_delta')
            # delta_slack_1[gen_idx] = solver.NumVar(0, inf, name + '_delta_slack_up')
            delta_slack_2[gen_idx] = solver.NumVar(0, inf, name + '_delta_slack_down')

            solver.Add(generation[gen_idx] == Pgen[gen_idx] + delta[gen_idx] - delta_slack_2[gen_idx], 'Delta_up_gen{}'.format(gen_idx))

            dgen1.append(delta[gen_idx])

        else:
            generation[gen_idx] = Pgen[gen_idx]
            delta[gen_idx] = 0

        generation1.append(generation[gen_idx])
        Pgen1.append(Pgen[gen_idx])
        gen_a1_idx.append(gen_idx)

    for bus_idx, gen_idx in gens2:

        if generator_active[gen_idx] and dispatchable[gen_idx]:
            name = 'Gen_down_{0}@bus{1}_{2}'.format(gen_idx, bus_idx, generator_names[gen_idx])

            if Pmin[gen_idx] >= Pmax[gen_idx]:
                logger.add_error('Pmin >= Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

            generation[gen_idx] = solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
            delta[gen_idx] = solver.NumVar(0, inf, name + '_delta')

            delta_slack_1[gen_idx] = solver.NumVar(0, inf, name + '_delta_slack_up')
            # delta_slack_2[gen_idx] = solver.NumVar(0, inf, name + '_delta_slack_down')

            solver.Add(generation[gen_idx] == Pgen[gen_idx] - delta[gen_idx] + delta_slack_1[gen_idx], 'Delta_down_gen{}'.format(gen_idx))

            dgen2.append(delta[gen_idx])

        else:
            generation[gen_idx] = Pgen[gen_idx]
            delta[gen_idx] = 0

        generation2.append(generation[gen_idx])
        Pgen2.append(Pgen[gen_idx])
        gen_a2_idx.append(gen_idx)

    # set the generation in the non inter-area ones
    for bus_idx, gen_idx in gens_out:
        if generator_active[gen_idx]:
            generation[gen_idx] = Pgen[gen_idx]

    # enforce area equality
    power_shift = solver.NumVar(0, inf, 'power_shift')
    solver.Add(solver.Sum(dgen1) == power_shift, 'power_shift_assignment')
    solver.Add(solver.Sum(dgen1) == solver.Sum(dgen2), 'Area equality_2')

    return generation, delta, gen_a1_idx, gen_a2_idx, power_shift, dgen1, gen_cost, delta_slack_1, delta_slack_2


def check_optimal_generation(generator_active, generator_names, dispatchable, Cgen, Pgen, a1, a2,
                             generation, delta, logger: Logger):
    """

    :param generator_active:
    :param generator_names:
    :param dispatchable:
    :param Cgen:
    :param Pgen:
    :param a1:
    :param a2:
    :param generation:
    :param delta:
    :param logger:
    :return:
    """
    gens1, gens2, gens_out = get_generators_connectivity(Cgen, a1, a2)

    dgen1 = list()
    dgen2 = list()

    for bus_idx, gen_idx in gens1:
        if generator_active[gen_idx] and dispatchable[gen_idx]:
            res = generation[gen_idx] == Pgen[gen_idx] + delta[gen_idx]
            dgen1.append(delta[gen_idx])

            if not res:
                logger.add_divergence('Delta up condition not met '
                                      '(generation[gen_idx] == Pgen[gen_idx] + delta[gen_idx])',
                                      generator_names[gen_idx], generation[gen_idx] - Pgen[gen_idx], delta[gen_idx])

    for bus_idx, gen_idx in gens2:
        if generator_active[gen_idx] and dispatchable[gen_idx]:
            res = generation[gen_idx] == Pgen[gen_idx] - delta[gen_idx]
            dgen2.append(delta[gen_idx])

            if not res:
                logger.add_divergence('Delta down condition not met '
                                      '(generation[gen_idx] == Pgen[gen_idx] - delta[gen_idx])',
                                      generator_names[gen_idx], generation[gen_idx] - Pgen[gen_idx], delta[gen_idx])

    # check area equality
    sum_a1 = sum(dgen1)
    sum_a2 = sum(dgen2)
    res = sum_a1 == sum_a2

    if not res:
        logger.add_divergence('Area equality not met', 'grid', sum_a1, sum_a2)


def formulate_proportional_generation(solver: pywraplp.Solver,
                                      generator_active, generator_dispatchable, generator_cost,
                                      generator_names, Sbase, logger, inf,
                                      ngen, Cgen, Pgen, Pmax, Pmin, a1, a2, t=0):
    """

    :param solver:
    :param generator_active:
    :param generator_dispatchable:
    :param generator_cost:
    :param generator_names:
    :param Sbase:
    :param logger:
    :param inf:
    :param ngen:
    :param Cgen:
    :param Pgen:
    :param Pmax:
    :param Pmin:
    :param a1:
    :param a2:
    :param t:
    :param add_slacks:
    :return:
    """
    gens1, gens2, gens_out = get_generators_connectivity(Cgen, a1, a2)
    gen_cost = generator_cost[:, t] * Sbase  # pass from $/MWh to $/p.u.h
    generation = np.zeros(ngen, dtype=object)
    delta = np.zeros(ngen, dtype=object)
    delta_slack_1 = np.zeros(ngen, dtype=object)
    delta_slack_2 = np.zeros(ngen, dtype=object)

    dgen1 = list()
    dgen2 = list()

    generation1 = list()
    generation2 = list()

    Pgen1 = list()
    Pgen2 = list()

    gen_a1_idx = list()
    gen_a2_idx = list()

    sum_gen_1 = 0
    for bus_idx, gen_idx in gens1:
        if generator_active[gen_idx] and generator_dispatchable[gen_idx] and Pgen[gen_idx] > 0:
            sum_gen_1 += Pgen[gen_idx]

    sum_gen_2 = 0
    for bus_idx, gen_idx in gens2:
        if generator_active[gen_idx] and generator_dispatchable[gen_idx] and Pgen[gen_idx] > 0:
            sum_gen_2 += Pgen[gen_idx]

    power_shift = solver.NumVar(0, inf, 'Area_slack')

    for bus_idx, gen_idx in gens1:

        if generator_active[gen_idx]:

            if generator_dispatchable[gen_idx] and Pgen[gen_idx] > 0:

                name = 'Gen_up_{0}@bus{1}_{2}'.format(gen_idx, bus_idx, generator_names[gen_idx])

                if Pmin[gen_idx] >= Pmax[gen_idx]:
                    logger.add_error('Pmin >= Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

                generation[gen_idx] = solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
                delta[gen_idx] = solver.NumVar(0, inf, name + '_delta')
                delta_slack_1[gen_idx] = solver.NumVar(0, inf, 'Delta_slack_up_' + name)
                delta_slack_2[gen_idx] = solver.NumVar(0, inf, 'Delta_slack_down_' + name)

                prop = round(abs(Pgen[gen_idx] / sum_gen_1), 6)
                solver.Add(delta[gen_idx] == prop * power_shift, 'Delta_equal_to_proportional_power_shift_' + name)
                solver.Add(generation[gen_idx] == Pgen[gen_idx] + delta[gen_idx] + delta_slack_1[gen_idx] - delta_slack_2[gen_idx], 'Generation_due_to_forced_delta_' + name)

            else:
                generation[gen_idx] = Pgen[gen_idx]
                delta[gen_idx] = 0

            dgen1.append(delta[gen_idx])
            generation1.append(generation[gen_idx])
            Pgen1.append(Pgen[gen_idx])
            gen_a1_idx.append(gen_idx)

    for bus_idx, gen_idx in gens2:

        if generator_active[gen_idx]:

            if generator_dispatchable[gen_idx] and Pgen[gen_idx] > 0:

                name = 'Gen_down_{0}@bus{1}_{2}'.format(gen_idx, bus_idx, generator_names[gen_idx])

                if Pmin[gen_idx] >= Pmax[gen_idx]:
                    logger.add_error('Pmin >= Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

                generation[gen_idx] = solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
                delta[gen_idx] = solver.NumVar(0, inf, name + '_delta')
                delta_slack_1[gen_idx] = solver.NumVar(0, inf, name + '_delta_slack_up')
                delta_slack_2[gen_idx] = solver.NumVar(0, inf, name + '_delta_slack_down')

                prop = round(abs(Pgen[gen_idx] / sum_gen_2), 6)
                solver.Add(delta[gen_idx] == prop * power_shift, 'Delta_down_gen{}'.format(gen_idx))
                solver.Add(generation[gen_idx] == Pgen[gen_idx] - delta[gen_idx] + delta_slack_1[gen_idx] - delta_slack_2[gen_idx], 'Gen_down_gen{}'.format(gen_idx))

            else:
                generation[gen_idx] = Pgen[gen_idx]
                delta[gen_idx] = 0

            dgen2.append(delta[gen_idx])
            generation2.append(generation[gen_idx])
            Pgen2.append(Pgen[gen_idx])
            gen_a2_idx.append(gen_idx)

    # set the generation in the non inter-area ones
    for bus_idx, gen_idx in gens_out:
        if generator_active[gen_idx]:
            generation[gen_idx] = Pgen[gen_idx]

    return generation, delta, gen_a1_idx, gen_a2_idx, power_shift, dgen1, gen_cost, delta_slack_1, delta_slack_2


def check_proportional_generation(generator_active, dispatchable, generator_cost,
                                  generator_names, Sbase, logger: Logger,
                                  Cgen, Pgen, a1, a2, t, generation, delta, power_shift):
    """

    :param solver:
    :param generator_active:
    :param dispatchable:
    :param generator_cost:
    :param generator_names:
    :param Sbase:
    :param logger:
    :param inf:
    :param ngen:
    :param Cgen:
    :param Pgen:
    :param Pmax:
    :param Pmin:
    :param a1:
    :param a2:
    :param t:
    :param add_slacks:
    :return:
    """
    gens1, gens2, gens_out = get_generators_connectivity(Cgen, a1, a2)
    gen_cost = generator_cost[:, t] * Sbase  # pass from $/MWh to $/p.u.h

    dgen1 = list()
    dgen2 = list()

    sum_gen_1 = 0
    for bus_idx, gen_idx in gens1:
        if generator_active[gen_idx] and dispatchable[gen_idx] and Pgen[gen_idx] > 0:
            sum_gen_1 += Pgen[gen_idx]

    sum_gen_2 = 0
    for bus_idx, gen_idx in gens2:
        if generator_active[gen_idx] and dispatchable[gen_idx] and Pgen[gen_idx] > 0:
            sum_gen_2 += Pgen[gen_idx]

    # check area 1
    for bus_idx, gen_idx in gens1:

        if generator_active[gen_idx] and dispatchable[gen_idx] and Pgen[gen_idx] > 0:

            prop = abs(Pgen[gen_idx] / sum_gen_1)
            res = delta[gen_idx] == prop * power_shift
            if not res:
                logger.add_divergence("Delta up equal to it's share of the power shift "
                                      "(delta[i] == prop * power_shift)",
                                      generator_names[gen_idx], delta[gen_idx], prop * power_shift)

            res = generation[gen_idx] == Pgen[gen_idx] + delta[gen_idx]
            if not res:
                logger.add_divergence('Delta up condition not met (generation[i] == Pgen[i] + delta[i])',
                                      generator_names[gen_idx], generation[gen_idx], Pgen[gen_idx] + delta[gen_idx])

            dgen1.append(delta[gen_idx])

    # check area 2
    for bus_idx, gen_idx in gens2:

        if generator_active[gen_idx] and dispatchable[gen_idx] and Pgen[gen_idx] > 0:

            prop = abs(Pgen[gen_idx] / sum_gen_2)
            res = delta[gen_idx] == prop * power_shift
            if not res:
                logger.add_divergence("Delta down equal to it's share of the power shift "
                                      "(delta[i] == prop * power_shift)",
                                      generator_names[gen_idx], delta[gen_idx], -prop * power_shift)

            res = generation[gen_idx] == Pgen[gen_idx] - delta[gen_idx]
            if not res:
                logger.add_divergence('Delta down condition not met '
                                      '(generation[i] == Pgen[i] - delta[i])',
                                      generator_names[gen_idx], generation[gen_idx], Pgen[gen_idx] + delta[gen_idx])

            dgen2.append(delta[gen_idx])

    # check area equality
    sum_a1 = sum(dgen1)
    sum_a2 = sum(dgen2)
    res = sum_a1 == sum_a2

    if not res:
        logger.add_divergence('Area equality not met', 'grid', sum_a1, sum_a2)


def formulate_angles(solver: pywraplp.Solver, nbus, vd, bus_names, angle_min, angle_max, logger: Logger,
                     set_ref_to_zero=True):
    """

    :param solver:
    :param nbus:
    :param vd:
    :param bus_names:
    :param angle_min:
    :param angle_max:
    :param logger:
    :param set_ref_to_zero:
    :return:
    """
    theta = np.zeros(nbus, dtype=object)

    for i in range(nbus):

        if angle_min[i] > angle_max[i]:
            logger.add_error('Theta min > Theta max', 'Bus {0}'.format(i), angle_min[i])

        theta[i] = solver.NumVar(angle_min[i],
                                 angle_max[i],
                                 'theta_{0}_{1}'.format(i, bus_names[i]))

    if set_ref_to_zero:
        for i in vd:
            solver.Add(theta[i] == 0, "reference_bus_angle_zero_{0}_{1}".format(i, bus_names[i]))

    return theta


def formulate_power_injections(load_injections_per_bus, Cgen, generation, Sbase, t=0):
    """

    :param Cgen:
    :param generation:
    :param t:
    :return:
    """
    gen_injections = lpExpand(Cgen, generation)
    load_fixed_injections = load_injections_per_bus[:, t].real / Sbase  # with sign already

    return gen_injections + load_fixed_injections


def formulate_node_balance(solver: pywraplp.Solver, Bbus, angles, Pinj, bus_active, bus_names):
    """

    :param solver:
    :param nbus:
    :param Bbus:
    :param angles:
    :param Pinj:
    :param bus_active:
    :param bus_names:
    :return:
    """
    node_balance = lpDot(Bbus, angles)

    # equal the balance to the generation: eq.13,14 (equality)
    i = 0
    for balance, power in zip(node_balance, Pinj):
        if bus_active[i] and not isinstance(balance, int):  # balance is 0 for isolated buses
            solver.Add(balance == power, "Node_power_balance_{0}_{1}".format(i, bus_names[i]))
        i += 1

    return node_balance


def check_node_balance(Bbus, angles, Pinj, bus_active, bus_names, logger: Logger):
    """

    :param solver:
    :param nbus:
    :param Bbus:
    :param angles:
    :param Pinj:
    :param bus_active:
    :param bus_names:
    :return:
    """
    node_balance = Bbus * angles

    # equal the balance to the generation: eq.13,14 (equality)
    i = 0
    for balance, power in zip(node_balance, Pinj):
        if bus_active[i] and not isinstance(balance, int):  # balance is 0 for isolated buses
            res = balance == power

            if not res:
                logger.add_divergence('Kirchhoff not met (balance == power)', bus_names[i], balance, power)

        i += 1

    return node_balance


def formulate_branches_flow(solver: pywraplp.Solver, nbr, Rates, Sbase,
                            branch_active, branch_names, branch_dc,
                            theta_min, theta_max, control_mode, R, X, F, T, inf,
                            monitor_loading, branch_sensitivity_threshold, monitor_only_sensitive_branches,
                            angles, alpha_abs, logger):
    """

    :param solver:
    :param nbr:
    :param Rates:
    :param Sbase:
    :param branch_active:
    :param branch_names:
    :param branch_dc:
    :param theta_min:
    :param theta_max:
    :param control_mode:
    :param R:
    :param X:
    :param F:
    :param T:
    :param inf:
    :param monitor_loading:
    :param branch_sensitivity_threshold:
    :param monitor_only_sensitive_branches:
    :param angles: node angles array
    :param alpha_abs: absolute branch sensitivities array
    :param logger:
    :param add_slacks:
    :return:
    """

    flow_f = np.zeros(nbr, dtype=object)
    overload1 = np.zeros(nbr, dtype=object)
    overload2 = np.zeros(nbr, dtype=object)
    tau = np.zeros(nbr, dtype=object)
    monitor = np.zeros(nbr, dtype=bool)
    rates = Rates / Sbase

    # formulate flows
    for m in range(nbr):

        if branch_active[m]:

            # determine the monitoring logic
            if monitor_only_sensitive_branches:
                if monitor_loading[m] and alpha_abs[m] > branch_sensitivity_threshold:
                    monitor[m] = True
                else:
                    monitor[m] = False
            else:
                monitor[m] = monitor_loading[m]

            if monitor[m]:

                _f = F[m]
                _t = T[m]

                # declare the flow variable with ample limits
                flow_f[m] = solver.NumVar(-inf, inf, 'pftk_{0}_{1}'.format(m, branch_names[m]))

                # compute the branch susceptance
                if branch_dc[m]:
                    bk = 1.0 / R[m]
                else:
                    bk = 1.0 / X[m]

                if control_mode[m] == TransformerControlType.Pt:  # is a phase shifter
                    # create the phase shift variable
                    tau[m] = solver.NumVar(theta_min[m], theta_max[m],
                                           'phase_shift_{0}_{1}'.format(m, branch_names[m]))
                    # branch power from-to eq.15
                    solver.Add(flow_f[m] == bk * (angles[_f] - angles[_t] + tau[m]),
                               'phase_shifter_power_flow_{0}_{1}'.format(m, branch_names[m]))
                else:
                    # branch power from-to eq.15
                    solver.Add(flow_f[m] == bk * (angles[_f] - angles[_t]),
                               'branch_power_flow_{0}_{1}'.format(m, branch_names[m]))

                if rates[m] <= 0:
                    logger.add_error('Rate = 0', 'Branch:{0}'.format(m) + ';' + branch_names[m], rates[m])

                # rating restriction in the sense from-to: eq.17
                overload1[m] = solver.NumVar(0, inf, 'overload1_{0}_{1}'.format(m, branch_names[m]))
                solver.Add(flow_f[m] <= (rates[m] + overload1[m]), "ft_rating_{0}_{1}".format(m, branch_names[m]))

                # rating restriction in the sense to-from: eq.18
                overload2[m] = solver.NumVar(0, inf, 'overload2_{0}_{1}'.format(m, branch_names[m]))
                solver.Add((-rates[m] - overload2[m]) <= flow_f[m], "tf_rating_{0}_{1}".format(m, branch_names[m]))

    return flow_f, overload1, overload2, tau, monitor


def check_branches_flow(nbr, Rates, Sbase,
                        branch_active, branch_names, branch_dc, control_mode, R, X, F, T,
                        monitor_loading, branch_sensitivity_threshold, monitor_only_sensitive_branches,
                        angles, alpha_abs, logger: Logger, flow_f, tau):
    """

    :param nbr:
    :param Rates:
    :param Sbase:
    :param monitor:
    :param branch_active:
    :param branch_names:
    :param branch_dc:
    :param control_mode:
    :param R:
    :param X:
    :param F:
    :param T:
    :param monitor_loading:
    :param branch_sensitivity_threshold:
    :param monitor_only_sensitive_branches:
    :param angles:
    :param alpha_abs:
    :param logger:
    :param flow_f:
    :param tau:
    :return:
    """

    rates = Rates / Sbase
    monitor = np.zeros(nbr, dtype=bool)

    # formulate flows
    for m in range(nbr):

        if branch_active[m]:

            # determine the monitoring logic
            if monitor_only_sensitive_branches:
                if monitor_loading[m] and alpha_abs[m] > branch_sensitivity_threshold:
                    monitor[m] = True
                else:
                    monitor[m] = False
            else:
                monitor[m] = monitor_loading[m]

            if monitor[m]:

                _f = F[m]
                _t = T[m]

                # compute the branch susceptance
                if branch_dc[m]:
                    bk = 1.0 / R[m]
                else:
                    bk = 1.0 / X[m]

                if control_mode[m] == TransformerControlType.Pt:  # is a phase shifter
                    # branch power from-to eq.15
                    res = flow_f[m] == bk * (angles[_f] - angles[_t] + tau[m])

                    if not res:
                        logger.add_divergence(
                            'Phase shifter flow setting (flow_f[m] == bk * (angles[f] - angles[t] + tau[m]))',
                            branch_names[m], flow_f[m], bk * (angles[_f] - angles[_t] + tau[m]))

                else:
                    # branch power from-to eq.15
                    res = flow_f[m] == bk * (angles[_f] - angles[_t])

                    if not res:
                        logger.add_divergence('Branch flow setting (flow_f[m] == bk * (angles[f] - angles[t]))',
                                              branch_names[m], flow_f[m], bk * (angles[_f] - angles[_t]))

                # rating restriction in the sense from-to: eq.17
                res = flow_f[m] <= rates[m]

                if not res:
                    logger.add_divergence('Positive flow rating violated (flow_f[m] <= rates[m])', branch_names[m], flow_f[m], rates[m])

                # rating restriction in the sense to-from: eq.18
                res = -rates[m] <= flow_f[m]
                if not res:
                    logger.add_divergence('Negative flow rating violated (-rates[m] <= flow_f[m])', branch_names[m], flow_f[m], -rates[m])

    return monitor


def formulate_contingency(solver: pywraplp.Solver, ContingencyRates, Sbase,
                          branch_names, contingency_enabled_indices,
                          LODF, F, T, inf,
                          branch_sensitivity_threshold,
                          flow_f, monitor):
    """

    :param solver:
    :param ContingencyRates:
    :param Sbase:
    :param branch_names:
    :param contingency_enabled_indices:
    :param LODF:
    :param F:
    :param T:
    :param inf:
    :param branch_sensitivity_threshold:
    :param flow_f:
    :param monitor:
    :param add_slacks:
    :return:
    """
    rates = ContingencyRates / Sbase

    # get the indices of the branches marked for contingency
    con_br_idx = contingency_enabled_indices
    mon_br_idx = np.where(monitor == True)[0]

    # formulate contingency flows
    # this is done in a separated loop because all te flow variables must exist beforehand
    flow_n1f = list()
    overloads1 = list()
    overloads2 = list()
    con_idx = list()
    for m in mon_br_idx:  # for every monitored branch
        _f = F[m]
        _t = T[m]

        for c in con_br_idx:  # for every contingency

            if m != c and LODF[m, c] > branch_sensitivity_threshold:
                # compute the N-1 flow
                flow_n1 = flow_f[m] + LODF[m, c] * flow_f[c]

                suffix = "{0}_{1} @ {2}_{3}".format(m, branch_names[m], c, branch_names[c])

                # rating restriction in the sense from-to
                overload1 = solver.NumVar(0, inf, 'n-1_overload1__' + suffix)
                solver.Add(flow_n1 <= (rates[m] + overload1), "n-1_ft_rating_" + suffix)

                # rating restriction in the sense to-from
                overload2 = solver.NumVar(0, inf, 'n-1_overload2_' + suffix)
                solver.Add((-rates[m] - overload2) <= flow_n1, "n-1_tf_rating_" + suffix)

                # store vars
                con_idx.append((m, c))
                flow_n1f.append(flow_n1)
                overloads1.append(overload1)
                overloads2.append(overload2)

    return flow_n1f, overloads1, overloads2, con_idx


def check_contingency(ContingencyRates, Sbase,
                          branch_names, contingency_enabled_indices,
                          LODF, F, T,
                          branch_sensitivity_threshold,
                          flow_f, monitor, logger: Logger):
    """

    :param ContingencyRates:
    :param Sbase:
    :param branch_names:
    :param contingency_enabled_indices:
    :param LODF:
    :param F:
    :param T:
    :param branch_sensitivity_threshold:
    :param flow_f:
    :param monitor:
    :param logger:
    :return:
    """
    rates = ContingencyRates / Sbase

    # get the indices of the branches marked for contingency
    con_br_idx = contingency_enabled_indices
    mon_br_idx = np.where(monitor == True)[0]

    # formulate contingency flows
    # this is done in a separated loop because all te flow variables must exist beforehand
    for m in mon_br_idx:  # for every monitored branch
        _f = F[m]
        _t = T[m]

        for c in con_br_idx:  # for every contingency

            if m != c and LODF[m, c] > branch_sensitivity_threshold:
                # compute the N-1 flow
                flow_n1 = flow_f[m] + LODF[m, c] * flow_f[c]

                res = flow_n1 <= rates[m]

                if not res:
                    logger.add_divergence('Positive contingency flow rating violated (flow_n1 <= rates[m])', branch_names[m] + '@' + branch_names[c], flow_n1, rates[m])

                # rating restriction in the sense to-from
                res = -rates[m] <= flow_n1

                if not res:
                    logger.add_divergence('Negative contingency flow rating violated (-rates[m] <= flow_n1)', branch_names[m] + '@' + branch_names[c], flow_n1, -rates[m])


def formulate_hvdc_flow(solver: pywraplp.Solver, nhvdc, names,
                        rate, angles, active, Pt, r, control_mode, dispatchable,
                        F, T, Pinj, Sbase, inf, logger, t=0):
    """

    :param solver:
    :param nhvdc:
    :param names:
    :param rate:
    :param angles:
    :param active:
    :param Pt:
    :param r:
    :param control_mode:
    :param dispatchable:
    :param F:
    :param T:
    :param Pinj:
    :param Sbase:
    :param inf:
    :param logger:
    :param t:
    :param add_slacks:
    :return:
    """
    rates = rate[:, t] / Sbase

    flow_f = np.zeros(nhvdc, dtype=object)
    overload1 = np.zeros(nhvdc, dtype=object)
    overload2 = np.zeros(nhvdc, dtype=object)
    hvdc_control1 = np.zeros(nhvdc, dtype=object)
    hvdc_control2 = np.zeros(nhvdc, dtype=object)

    for i in range(nhvdc):

        if active[i, t]:

            _f = F[i]
            _t = T[i]

            suffix = "{0}_{1}".format(i, names[i])

            hvdc_control1[i] = solver.NumVar(0, inf, 'hvdc_control1_' + suffix)
            hvdc_control2[i] = solver.NumVar(0, inf, 'hvdc_control2_' + suffix)
            P0 = Pt[i, t] / Sbase

            if control_mode[i] == HvdcControlType.type_0_free:

                if rates[i] <= 0:
                    logger.add_error('Rate = 0', 'HVDC:{0}'.format(i), rates[i])

                flow_f[i] = solver.NumVar(-rates[i], rates[i], 'hvdc_flow_' + suffix)

                # formulate the hvdc flow as an AC line equivalent
                bk = 1.0 / r[i]  # TODO: yes, I know... DC...
                solver.Add(flow_f[i] == P0 + bk * (angles[_f] - angles[_t]) + hvdc_control1[i] - hvdc_control2[i], 'hvdc_power_flow_' + suffix)
                # solver.Add(flow_f[i] == P0 + bk * (angles[_f] - angles[_t]), 'hvdc_power_flow_' + suffix)

                # add the injections matching the flow
                Pinj[_f] -= flow_f[i]
                Pinj[_t] += flow_f[i]

                # rating restriction in the sense from-to: eq.17
                overload1[i] = solver.NumVar(0, inf, 'overload_hvdc1_' + suffix)
                solver.Add(flow_f[i] <= (rates[i] + overload1[i]), "hvdc_ft_rating_" + suffix)

                # rating restriction in the sense to-from: eq.18
                overload2[i] = solver.NumVar(0, inf, 'overload_hvdc2_' + suffix)
                solver.Add((-rates[i] - overload2[i]) <= flow_f[i], "hvdc_tf_rating_" + suffix)

            elif control_mode[i] == HvdcControlType.type_1_Pset and not dispatchable[i]:
                # simple injections model: The power is set by the user
                flow_f[i] = P0 + hvdc_control1[i] - hvdc_control2[i]
                Pinj[_f] -= flow_f[i]
                Pinj[_t] += flow_f[i]

            elif control_mode[i] == HvdcControlType.type_1_Pset and dispatchable[i]:
                # simple injections model, the power is a variable and it is optimized
                P0 = solver.NumVar(-rates[i], rates[i], 'hvdc_pf_' + suffix)
                flow_f[i] = P0 + hvdc_control1[i] - hvdc_control2[i]
                Pinj[_f] -= flow_f[i]
                Pinj[_t] += flow_f[i]

    return flow_f, overload1, overload2, hvdc_control1, hvdc_control2


def check_hvdc_flow(nhvdc, names,
                    rate, angles, active, Pt, r, control_mode, dispatchable,
                    F, T, Sbase, flow_f, logger: Logger, t=0):
    """

    :param solver:
    :param nhvdc:
    :param names:
    :param rate:
    :param angles:
    :param active:
    :param Pt:
    :param r:
    :param control_mode:
    :param dispatchable:
    :param F:
    :param T:
    :param Pinj:
    :param Sbase:
    :param inf:
    :param logger:
    :param t:
    :param add_slacks:
    :return:
    """
    rates = rate[:, t] / Sbase

    for i in range(nhvdc):

        if active[i, t]:

            _f = F[i]
            _t = T[i]

            suffix = "{0}_{1}".format(i, names[i])

            P0 = Pt[i, t] / Sbase

            if control_mode[i] == HvdcControlType.type_0_free:

                # formulate the hvdc flow as an AC line equivalent
                bk = 1.0 / r[i]  # TODO: yes, I know... DC...
                res = flow_f[i] == P0 + bk * (angles[_f] - angles[_t])   # + hvdc_control1[i] - hvdc_control2[i], 'hvdc_power_flow_' + suffix)

                if not res:
                    logger.add_divergence('HVDC free flow violation (flow_f[i] == P0 + bk * (angles[f] - angles[t]))', names[i], flow_f[i], P0 + bk * (angles[_f] - angles[_t]))

                # rating restriction in the sense from-to: eq.17
                res = flow_f[i] <= rates[i]  # , "hvdc_ft_rating_" + suffix)

                if not res:
                    logger.add_divergence('HVDC positive rating violation (flow_f[i] <= rates[i])', names[i], flow_f[i], rates[i])

                # rating restriction in the sense to-from: eq.18
                res = -rates[i] <= flow_f[i]  # , "hvdc_tf_rating_" + suffix)

                if not res:
                    logger.add_divergence('HVDC negative rating violation (-rates[i] <= flow_f[i])', names[i], flow_f[i], -rates[i])

            elif control_mode[i] == HvdcControlType.type_1_Pset and not dispatchable[i]:
                # simple injections model: The power is set by the user
                res = flow_f[i] == P0

                if not res:
                    logger.add_divergence('HVDC Pset, non dispatchable control not met (flow_f[i] == P0)', names[i], flow_f[i], P0)

            elif control_mode[i] == HvdcControlType.type_1_Pset and dispatchable[i]:
                # simple injections model, the power is a variable and it is optimized
                pass


def formulate_objective(solver: pywraplp.Solver,
                        inter_area_branches, flows_f, overload1, overload2, n1overload1, n1overload2,
                        inter_area_hvdc, hvdc_flow_f, hvdc_overload1, hvdc_overload2, hvdc_control1, hvdc_control2,
                        power_shift, dgen1, gen_cost, generation_delta,
                        delta_slack_1, delta_slack_2,
                        weight_power_shift, maximize_exchange_flows, weight_generation_cost,
                        weight_generation_delta, weight_overloads, weight_hvdc_control):
    """

    :param solver:
    :param inter_area_branches:
    :param flows_f:
    :param overload1:
    :param overload2:
    :param n1overload1:
    :param n1overload2:
    :param inter_area_hvdc:
    :param hvdc_flow_f:
    :param hvdc_overload1:
    :param hvdc_overload2:
    :param hvdc_control1:
    :param hvdc_control2:
    :param power_shift:
    :param dgen1:
    :param gen_cost:
    :param generation_delta:
    :param delta_slack_1:
    :param delta_slack_2:
    :param weight_power_shift:
    :param maximize_exchange_flows:
    :param weight_generation_cost:
    :param weight_generation_delta:
    :param weight_overloads:
    :param weight_hvdc_control:
    :return:
    """

    # maximize the power from->to
    flows_ft = np.zeros(len(inter_area_branches), dtype=object)
    for i, (k, sign) in enumerate(inter_area_branches):
        flows_ft[i] = sign * flows_f[k]

    flows_hvdc_ft = np.zeros(len(inter_area_hvdc), dtype=object)
    for i, (k, sign) in enumerate(inter_area_hvdc):
        flows_hvdc_ft[i] = sign * hvdc_flow_f[k]

    flow_from_a1_to_a2 = solver.Sum(flows_ft) + solver.Sum(flows_hvdc_ft)

    # include the cost of generation
    gen_cost_f = solver.Sum(gen_cost * generation_delta)

    branch_overload = solver.Sum(overload1) + solver.Sum(overload2)

    contingency_branch_overload = solver.Sum(n1overload1) + solver.Sum(n1overload2)

    hvdc_overload = solver.Sum(hvdc_overload1) + solver.Sum(hvdc_overload2)

    hvdc_control = solver.Sum(hvdc_control1) + solver.Sum(hvdc_control2)

    delta_slacks = solver.Sum(delta_slack_1) + solver.Sum(delta_slack_2)

    # formulate objective function
    # f = -weight_power_shift * power_shift
    f = -weight_power_shift * flow_from_a1_to_a2

    f += weight_generation_cost * gen_cost_f
    f += weight_generation_delta * delta_slacks
    f += weight_overloads * branch_overload
    f += weight_overloads * contingency_branch_overload
    f += weight_overloads * hvdc_overload
    f += weight_hvdc_control * hvdc_control

    # objective function
    solver.Minimize(f)

    all_slacks_sum = branch_overload + hvdc_overload + hvdc_control + delta_slacks + contingency_branch_overload

    slacks = [overload1, overload2,
              n1overload1, n1overload2,
              hvdc_overload1, hvdc_overload2,
              hvdc_control1, hvdc_control2,
              delta_slack_1, delta_slack_2]

    return all_slacks_sum, slacks


class OpfNTC(Opf):

    def __init__(self, numerical_circuit: SnapshotOpfData,
                 area_from_bus_idx,
                 area_to_bus_idx,
                 alpha,
                 LODF,
                 solver_type: MIPSolvers = MIPSolvers.CBC,
                 generation_formulation: GenerationNtcFormulation = GenerationNtcFormulation.Optimal,
                 monitor_only_sensitive_branches=False,
                 branch_sensitivity_threshold=0.01,
                 skip_generation_limits=False,
                 consider_contingencies=True,
                 maximize_exchange_flows=True,
                 tolerance=1e-2,
                 weight_power_shift=1e0,
                 weight_generation_cost=1e-2,
                 weight_generation_delta=1e0,
                 weight_kirchoff=1e5,
                 weight_overloads=1e5,
                 weight_hvdc_control=1e0,
                 logger: Logger=None):
        """
        DC time series linear optimal power flow
        :param numerical_circuit: NumericalCircuit instance
        :param area_from_bus_idx: indices of the buses of the area 1
        :param area_to_bus_idx: indices of the buses of the area 2
        :param solver_type: type of linear solver
        :param generation_formulation: type of generation formulation
        :param monitor_only_sensitive_branches: Monitor the loading of only the sensitive branches?
        :param branch_sensitivity_threshold: branch sensitivity
        :param skip_generation_limits:
        """

        self.area_from_bus_idx = area_from_bus_idx

        self.area_to_bus_idx = area_to_bus_idx

        self.generation_formulation = generation_formulation

        self.monitor_only_sensitive_branches = monitor_only_sensitive_branches

        self.branch_sensitivity_threshold = branch_sensitivity_threshold

        self.skip_generation_limits = skip_generation_limits

        self.consider_contingencies = consider_contingencies

        self.maximize_exchange_flows = maximize_exchange_flows

        self.tolerance = tolerance

        self.alpha = alpha

        self.LODF = LODF

        self.weight_power_shift = weight_power_shift
        self.weight_generation_cost = weight_generation_cost
        self.weight_generation_delta = weight_generation_delta
        self.weight_kirchoff = weight_kirchoff
        self.weight_overloads = weight_overloads
        self.weight_hvdc_control = weight_hvdc_control

        self.inf = 99999999999999

        # results
        self.all_slacks = None
        self.all_slacks_sum = None
        self.Pg_delta = None
        self.area_balance_slack = None
        self.generation_delta_slacks = None
        self.Pinj = None
        self.hvdc_flow = None
        self.hvdc_slacks = None
        self.phase_shift = None
        self.inter_area_branches = None
        self.inter_area_hvdc = None

        self.logger = logger

        # this builds the formulation right away
        Opf.__init__(self, numerical_circuit=numerical_circuit,
                     solver_type=solver_type,
                     ortools=True)

    def formulate(self, add_slacks=True):
        """
        Formulate the Net Transfer Capacity problem
        :return:
        """

        self.inf = self.solver.infinity()

        # general indices
        n = self.numerical_circuit.nbus
        m = self.numerical_circuit.nbr
        ng = self.numerical_circuit.ngen
        nb = self.numerical_circuit.nbatt
        nl = self.numerical_circuit.nload
        Sbase = self.numerical_circuit.Sbase

        # battery
        Pb_max = self.numerical_circuit.battery_pmax / Sbase
        Pb_min = self.numerical_circuit.battery_pmin / Sbase
        cost_b = self.numerical_circuit.battery_cost
        Cbat = self.numerical_circuit.battery_data.C_bus_batt.tocsc()

        # generator
        Pg_max = self.numerical_circuit.generator_pmax / Sbase
        Pg_min = self.numerical_circuit.generator_pmin / Sbase
        cost_g = self.numerical_circuit.generator_cost
        Pg_fix = self.numerical_circuit.generator_p / Sbase
        enabled_for_dispatch = self.numerical_circuit.generator_dispatchable
        Cgen = self.numerical_circuit.generator_data.C_bus_gen.tocsc()

        if self.skip_generation_limits:
            print('Skipping generation limits')
            Pg_max = self.inf * np.ones(self.numerical_circuit.ngen)
            Pg_min = -self.inf * np.ones(self.numerical_circuit.ngen)

        # load
        Pl = (self.numerical_circuit.load_active * self.numerical_circuit.load_s.real) / Sbase
        cost_l = self.numerical_circuit.load_cost

        # modify Pg_fix until it is identical to Pload
        total_load = Pl.sum()
        total_gen = Pg_fix.sum()
        diff = total_gen - total_load
        Pg_fix -= diff * (Pg_fix / total_gen)

        # branch
        branch_ratings = self.numerical_circuit.branch_rates / Sbase
        Ys = 1 / (self.numerical_circuit.branch_R + 1j * self.numerical_circuit.branch_X)
        Bseries = (self.numerical_circuit.branch_active * Ys).imag
        cost_br = self.numerical_circuit.branch_cost
        alpha_abs = np.abs(self.alpha)

        # --------------------------------------------------------------------------------------------------------------
        # pre-solve to identify base infeasibilities
        # --------------------------------------------------------------------------------------------------------------
        # Cannot solve the power flow problem via optimization
        # solve_power_flow(Bbus=self.numerical_circuit.Bbus,
        #                  Pinj=self.numerical_circuit.Sbus.real,
        #                  bus_active=self.numerical_circuit.bus_data.bus_active,
        #                  vd=self.numerical_circuit.vd,
        #                  bus_names=self.numerical_circuit.bus_data.bus_names,
        #                  angle_min=self.numerical_circuit.bus_data.angle_min,
        #                  angle_max=self.numerical_circuit.bus_data.angle_max,
        #                  logger=self.logger)

        # --------------------------------------------------------------------------------------------------------------
        # Formulate the problem
        # --------------------------------------------------------------------------------------------------------------

        # time index
        t = 0

        # get the inter-area branches and their sign
        inter_area_branches = get_inter_areas_branches(nbr=m,
                                                       F=self.numerical_circuit.branch_data.F,
                                                       T=self.numerical_circuit.branch_data.T,
                                                       buses_areas_1=self.area_from_bus_idx,
                                                       buses_areas_2=self.area_to_bus_idx)

        inter_area_hvdc = get_inter_areas_branches(nbr=self.numerical_circuit.nhvdc,
                                                   F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
                                                   T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
                                                   buses_areas_1=self.area_from_bus_idx,
                                                   buses_areas_2=self.area_to_bus_idx)

        # formulate the generation
        if self.generation_formulation == GenerationNtcFormulation.Optimal:

            generation, generation_delta, gen_a1_idx, gen_a2_idx, \
            power_shift, dgen1, gen_cost, \
            delta_slack_1, delta_slack_2 = formulate_optimal_generation(solver=self.solver,
                                                                        generator_active=self.numerical_circuit.generator_data.generator_active,
                                                                        dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                                                                        generator_cost=self.numerical_circuit.generator_data.generator_cost,
                                                                        generator_names=self.numerical_circuit.generator_data.generator_names,
                                                                        Sbase=self.numerical_circuit.Sbase,
                                                                        logger=self.logger,
                                                                        inf=self.inf,
                                                                        ngen=ng,
                                                                        Cgen=Cgen,
                                                                        Pgen=Pg_fix,
                                                                        Pmax=Pg_max,
                                                                        Pmin=Pg_min,
                                                                        a1=self.area_from_bus_idx,
                                                                        a2=self.area_to_bus_idx,
                                                                        t=t)

        elif self.generation_formulation == GenerationNtcFormulation.Proportional:

            generation, generation_delta, \
            gen_a1_idx, gen_a2_idx, \
            power_shift, dgen1, gen_cost, \
            delta_slack_1, delta_slack_2 = formulate_proportional_generation(solver=self.solver,
                                                                             generator_active=self.numerical_circuit.generator_data.generator_active,
                                                                             generator_dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                                                                             generator_cost=self.numerical_circuit.generator_data.generator_cost,
                                                                             generator_names=self.numerical_circuit.generator_data.generator_names,
                                                                             Sbase=self.numerical_circuit.Sbase,
                                                                             logger=self.logger,
                                                                             inf=self.inf,
                                                                             ngen=ng,
                                                                             Cgen=Cgen,
                                                                             Pgen=Pg_fix,
                                                                             Pmax=Pg_max,
                                                                             Pmin=Pg_min,
                                                                             a1=self.area_from_bus_idx,
                                                                             a2=self.area_to_bus_idx,
                                                                             t=t)
        else:
            raise Exception('Unknown generation mode')

        # add the angles
        theta = formulate_angles(solver=self.solver,
                                 nbus=self.numerical_circuit.nbus,
                                 vd=self.numerical_circuit.vd,
                                 bus_names=self.numerical_circuit.bus_data.bus_names,
                                 angle_min=self.numerical_circuit.bus_data.angle_min,
                                 angle_max=self.numerical_circuit.bus_data.angle_max,
                                 logger=self.logger)

        # formulate the power injections
        Pinj = formulate_power_injections(load_injections_per_bus=self.numerical_circuit.load_data.get_injections_per_bus(),
                                          Cgen=Cgen,
                                          generation=generation,
                                          Sbase=self.numerical_circuit.Sbase,
                                          t=t)

        # formulate the flows
        flow_f, overload1, overload2, tau, monitor = formulate_branches_flow(solver=self.solver,
                                                                             nbr=self.numerical_circuit.nbr,
                                                                             Rates=self.numerical_circuit.Rates,
                                                                             Sbase=self.numerical_circuit.Sbase,
                                                                             branch_active=self.numerical_circuit.branch_active,
                                                                             branch_names=self.numerical_circuit.branch_names,
                                                                             branch_dc=self.numerical_circuit.branch_data.branch_dc,
                                                                             theta_min=self.numerical_circuit.branch_data.theta_min,
                                                                             theta_max=self.numerical_circuit.branch_data.theta_max,
                                                                             control_mode=self.numerical_circuit.branch_data.control_mode,
                                                                             R=self.numerical_circuit.branch_data.R,
                                                                             X=self.numerical_circuit.branch_data.X,
                                                                             F=self.numerical_circuit.F,
                                                                             T=self.numerical_circuit.T,
                                                                             inf=self.inf,
                                                                             monitor_loading=self.numerical_circuit.branch_data.monitor_loading,
                                                                             branch_sensitivity_threshold=self.branch_sensitivity_threshold,
                                                                             monitor_only_sensitive_branches=self.monitor_only_sensitive_branches,
                                                                             angles=theta,
                                                                             alpha_abs=alpha_abs,
                                                                             logger=self.logger)

        # formulate the contingencies
        if self.consider_contingencies:
            n1flow_f, n1overload1, n1overload2, con_br_idx = formulate_contingency(solver=self.solver,
                                                                                   ContingencyRates=self.numerical_circuit.ContingencyRates,
                                                                                   Sbase=self.numerical_circuit.Sbase,
                                                                                   branch_names=self.numerical_circuit.branch_names,
                                                                                   contingency_enabled_indices=self.numerical_circuit.branch_data.get_contingency_enabled_indices(),
                                                                                   LODF=self.LODF,
                                                                                   F=self.numerical_circuit.F,
                                                                                   T=self.numerical_circuit.T,
                                                                                   inf=self.inf,
                                                                                   branch_sensitivity_threshold=self.branch_sensitivity_threshold,
                                                                                   flow_f=flow_f,
                                                                                   monitor=monitor)
        else:
            n1overload1 = list()
            n1overload2 = list()
            con_br_idx = list()
            n1flow_f = list()

        # formulate the HVDC flows
        hvdc_flow_f, hvdc_overload1, hvdc_overload2, \
        hvdc_control1, hvdc_control2 = formulate_hvdc_flow(solver=self.solver,
                                                           nhvdc=self.numerical_circuit.nhvdc,
                                                           names=self.numerical_circuit.hvdc_names,
                                                           rate=self.numerical_circuit.hvdc_data.rate,
                                                           angles=theta,
                                                           active=self.numerical_circuit.hvdc_data.active,
                                                           Pt=self.numerical_circuit.hvdc_data.Pt,
                                                           r=self.numerical_circuit.hvdc_data.r,
                                                           control_mode=self.numerical_circuit.hvdc_data.control_mode,
                                                           dispatchable=self.numerical_circuit.hvdc_data.dispatchable,
                                                           F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
                                                           T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
                                                           Pinj=Pinj,
                                                           Sbase=self.numerical_circuit.Sbase,
                                                           inf=self.inf,
                                                           logger=self.logger,
                                                           t=t)

        # formulate the node power balance
        node_balance = formulate_node_balance(solver=self.solver,
                                              Bbus=self.numerical_circuit.Bbus,
                                              angles=theta,
                                              Pinj=Pinj,
                                              bus_active=self.numerical_circuit.bus_data.bus_active,
                                              bus_names=self.numerical_circuit.bus_data.bus_names)

        # formulate the objective
        self.all_slacks_sum, self.all_slacks = formulate_objective(solver=self.solver,
                                                                   inter_area_branches=inter_area_branches,
                                                                   flows_f=flow_f,
                                                                   overload1=overload1,
                                                                   overload2=overload2,
                                                                   n1overload1=n1overload1,
                                                                   n1overload2=n1overload2,
                                                                   inter_area_hvdc=inter_area_hvdc,
                                                                   hvdc_flow_f=hvdc_flow_f,
                                                                   hvdc_overload1=hvdc_overload1,
                                                                   hvdc_overload2=hvdc_overload2,
                                                                   hvdc_control1=hvdc_control1,
                                                                   hvdc_control2=hvdc_control2,
                                                                   power_shift=power_shift,
                                                                   dgen1=dgen1,
                                                                   gen_cost=gen_cost[gen_a1_idx],
                                                                   generation_delta=generation_delta[gen_a1_idx],
                                                                   delta_slack_1=delta_slack_1,
                                                                   delta_slack_2=delta_slack_2,
                                                                   weight_power_shift=self.weight_power_shift,
                                                                   maximize_exchange_flows=self.maximize_exchange_flows,
                                                                   weight_generation_cost=self.weight_generation_cost,
                                                                   weight_generation_delta=self.weight_generation_delta,
                                                                   weight_overloads=self.weight_overloads,
                                                                   weight_hvdc_control=self.weight_hvdc_control)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta
        self.Pg = generation
        self.Pg_delta = generation_delta
        self.area_balance_slack = power_shift
        self.generation_delta_slacks = delta_slack_1 - delta_slack_2

        # self.Pb = Pb
        self.Pl = Pl
        self.Pinj = Pinj
        # self.load_shedding = load_slack
        self.s_from = flow_f
        self.s_to = - flow_f
        self.n1flow_f = n1flow_f
        self.contingency_br_idx = con_br_idx

        self.hvdc_flow = hvdc_flow_f
        self.hvdc_slacks = hvdc_overload1 - hvdc_overload2

        self.overloads = overload1 - overload2
        self.rating = branch_ratings
        self.phase_shift = tau
        self.nodal_restrictions = node_balance

        self.inter_area_branches = inter_area_branches
        self.inter_area_hvdc = inter_area_hvdc

        # n1flow_f, n1overload1, n1overload2, con_br_idx
        self.contingency_flows_list = n1flow_f
        self.contingency_indices_list = con_br_idx  # [(t, m, c), ...]
        self.contingency_flows_slacks_list = n1overload1

        return self.solver

    def check(self):
        """
        Formulate the Net Transfer Capacity problem
        :return:
        """

        # general indices
        n = self.numerical_circuit.nbus
        m = self.numerical_circuit.nbr
        ng = self.numerical_circuit.ngen
        nb = self.numerical_circuit.nbatt
        nl = self.numerical_circuit.nload
        Sbase = self.numerical_circuit.Sbase

        # battery
        Pb_max = self.numerical_circuit.battery_pmax / Sbase
        Pb_min = self.numerical_circuit.battery_pmin / Sbase
        cost_b = self.numerical_circuit.battery_cost
        Cbat = self.numerical_circuit.battery_data.C_bus_batt.tocsc()

        # generator
        Pg_max = self.numerical_circuit.generator_pmax / Sbase
        Pg_min = self.numerical_circuit.generator_pmin / Sbase
        cost_g = self.numerical_circuit.generator_cost
        Pg_fix = self.numerical_circuit.generator_p / Sbase
        enabled_for_dispatch = self.numerical_circuit.generator_dispatchable
        Cgen = self.numerical_circuit.generator_data.C_bus_gen.tocsc()

        if self.skip_generation_limits:
            print('Skipping generation limits')
            Pg_max = self.inf * np.ones(self.numerical_circuit.ngen)
            Pg_min = -self.inf * np.ones(self.numerical_circuit.ngen)

        # load
        Pl = (self.numerical_circuit.load_active * self.numerical_circuit.load_s.real) / Sbase
        cost_l = self.numerical_circuit.load_cost

        # branch
        branch_ratings = self.numerical_circuit.branch_rates / Sbase
        Ys = 1 / (self.numerical_circuit.branch_R + 1j * self.numerical_circuit.branch_X)
        Bseries = (self.numerical_circuit.branch_active * Ys).imag
        cost_br = self.numerical_circuit.branch_cost
        alpha_abs = np.abs(self.alpha)

        # time index
        t = 0

        # check that the slacks are 0
        if self.all_slacks is not None:
            for var_array in self.all_slacks:
                for var in var_array:
                    if isinstance(var, float) or isinstance(var, int):
                        val = var
                    else:
                        val = var.solution_value()

                    if abs(val) > 0:
                        self.logger.add_divergence('Slack variable is over the tolerance', var.name(), val, 0)

        # check variables
        for var in self.solver.variables():

            if var.solution_value() > var.Ub():
                self.logger.add_divergence('Variable over the upper bound', var.name(), var.solution_value(), var.Ub())
            if var.solution_value() < var.Lb():
                self.logger.add_divergence('Variable under the lower bound', var.name(), var.solution_value(), var.Lb())

        # formulate the generation
        if self.generation_formulation == GenerationNtcFormulation.Optimal:

            check_optimal_generation(generator_active=self.numerical_circuit.generator_data.generator_active,
                                     dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                                     generator_names=self.numerical_circuit.generator_data.generator_names,
                                     Cgen=Cgen,
                                     Pgen=Pg_fix,
                                     a1=self.area_from_bus_idx,
                                     a2=self.area_to_bus_idx,
                                     generation=self.extract(self.Pg),
                                     delta=self.extract(self.Pg_delta),
                                     logger=self.logger)

        elif self.generation_formulation == GenerationNtcFormulation.Proportional:

            check_proportional_generation(generator_active=self.numerical_circuit.generator_data.generator_active,
                                          dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                                          generator_cost=self.numerical_circuit.generator_data.generator_cost,
                                          generator_names=self.numerical_circuit.generator_data.generator_names,
                                          Sbase=self.numerical_circuit.Sbase,
                                          Cgen=Cgen,
                                          Pgen=Pg_fix,
                                          a1=self.area_from_bus_idx,
                                          a2=self.area_to_bus_idx,
                                          t=t,
                                          generation=self.extract(self.Pg),
                                          delta=self.extract(self.Pg_delta),
                                          power_shift=self.area_balance_slack.solution_value(),
                                          logger=self.logger)
        else:
            raise Exception('Unknown generation mode')

        monitor = check_branches_flow(nbr=self.numerical_circuit.nbr,
                                      Rates=self.numerical_circuit.Rates,
                                      Sbase=self.numerical_circuit.Sbase,
                                      branch_active=self.numerical_circuit.branch_active,
                                      branch_names=self.numerical_circuit.branch_names,
                                      branch_dc=self.numerical_circuit.branch_data.branch_dc,
                                      control_mode=self.numerical_circuit.branch_data.control_mode,
                                      R=self.numerical_circuit.branch_data.R,
                                      X=self.numerical_circuit.branch_data.X,
                                      F=self.numerical_circuit.F,
                                      T=self.numerical_circuit.T,
                                      monitor_loading=self.numerical_circuit.branch_data.monitor_loading,
                                      branch_sensitivity_threshold=self.branch_sensitivity_threshold,
                                      monitor_only_sensitive_branches=self.monitor_only_sensitive_branches,
                                      angles=self.extract(self.theta),
                                      alpha_abs=alpha_abs,
                                      logger=self.logger,
                                      flow_f=self.extract(self.s_from),
                                      tau=self.extract(self.phase_shift))

        check_contingency(ContingencyRates=self.numerical_circuit.ContingencyRates,
                          Sbase=self.numerical_circuit.Sbase,
                          branch_names=self.numerical_circuit.branch_names,
                          contingency_enabled_indices=self.numerical_circuit.branch_data.get_contingency_enabled_indices(),
                          LODF=self.LODF,
                          F=self.numerical_circuit.F,
                          T=self.numerical_circuit.T,
                          branch_sensitivity_threshold=self.branch_sensitivity_threshold,
                          flow_f=self.extract(self.s_from),
                          monitor=monitor,
                          logger=self.logger)

        check_hvdc_flow(nhvdc=self.numerical_circuit.nhvdc,
                        names=self.numerical_circuit.hvdc_names,
                        rate=self.numerical_circuit.hvdc_data.rate,
                        angles=self.extract(self.theta),
                        active=self.numerical_circuit.hvdc_data.active,
                        Pt=self.numerical_circuit.hvdc_data.Pt,
                        r=self.numerical_circuit.hvdc_data.r,
                        control_mode=self.numerical_circuit.hvdc_data.control_mode,
                        dispatchable=self.numerical_circuit.hvdc_data.dispatchable,
                        F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
                        T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
                        Sbase=self.numerical_circuit.Sbase,
                        flow_f=self.extract(self.hvdc_flow),
                        logger=self.logger,
                        t=t)

        Pinj = formulate_power_injections(load_injections_per_bus=self.numerical_circuit.load_data.get_injections_per_bus(),
                                          Cgen=Cgen,
                                          generation=self.extract(self.Pg),
                                          Sbase=self.numerical_circuit.Sbase,
                                          t=t)

        check_node_balance(Bbus=self.numerical_circuit.Bbus,
                           angles=self.extract(self.theta),
                           Pinj=Pinj,
                           bus_active=self.numerical_circuit.bus_data.bus_active,
                           bus_names=self.numerical_circuit.bus_data.bus_names,
                           logger=self.logger)

    def save_lp(self, file_name="ntc_opf_problem.lp"):
        """
        Save problem in LP format
        :param file_name: name of the file (.lp or .mps supported)
        """
        save_lp(self.solver, file_name)

    def solve(self):
        """
        Call ORTools to solve the problem
        """
        self.status = self.solver.Solve()

        converged = self.converged()

        self.save_lp('ntc_opf.lp')

        # check the solution
        if not converged:
            self.check()

        return converged

    def error(self):
        """
        Compute total error
        :return: total error
        """
        if self.status == pywraplp.Solver.OPTIMAL:
            return self.all_slacks_sum.solution_value()
        else:
            return 99999

    def converged(self):
        return abs(self.error()) < self.tolerance

    @staticmethod
    def extract(arr, make_abs=False):  # override this method to call ORTools instead of PuLP
        """
        Extract values fro the 1D array of LP variables
        :param arr: 1D array of LP variables
        :param make_abs: substitute the result by its abs value
        :return: 1D numpy array
        """

        if isinstance(arr, list):
            arr = np.array(arr)

        val = np.zeros(arr.shape)
        for i in range(val.shape[0]):
            if isinstance(arr[i], float) or isinstance(arr[i], int):
                val[i] = arr[i]
            else:
                val[i] = arr[i].solution_value()
        if make_abs:
            val = np.abs(val)

        return val

    def get_contingency_flows_list(self):
        """
        Square matrix of contingency flows (n branch, n contingency branch)
        :return:
        """

        x = np.zeros(len(self.contingency_flows_list))

        for i in range(len(self.contingency_flows_list)):
            try:
                x[i] = self.contingency_flows_list[i].solution_value() * self.numerical_circuit.Sbase
            except AttributeError:
                x[i] = float(self.contingency_flows_list[i]) * self.numerical_circuit.Sbase

        return x

    def get_contingency_flows_slacks_list(self):
        """
        Square matrix of contingency flows (n branch, n contingency branch)
        :return:
        """

        x = np.zeros(len(self.n1flow_f))

        for i in range(len(self.n1flow_f)):
            try:
                x[i] = self.contingency_flows_list[i].solution_value() * self.numerical_circuit.Sbase
            except AttributeError:
                x[i] = float(self.contingency_flows_slacks_list[i]) * self.numerical_circuit.Sbase

        return x

    def get_contingency_loading(self):
        """
        Square matrix of contingency flows (n branch, n contingency branch)
        :return:
        """

        x = np.zeros(len(self.n1flow_f))

        for i in range(len(self.n1flow_f)):
            try:
                x[i] = self.n1flow_f[i].solution_value() * self.numerical_circuit.Sbase / (self.rating[i] + 1e-20)
            except AttributeError:
                x[i] = float(self.n1flow_f[i]) * self.numerical_circuit.Sbase / (self.rating[i] + 1e-20)

        return x

    def get_power_injections(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.Pinj, make_abs=False) * self.numerical_circuit.Sbase

    def get_generator_delta(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.Pg_delta, make_abs=False) * self.numerical_circuit.Sbase

    def get_generator_delta_slacks(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.generation_delta_slacks, make_abs=False) * self.numerical_circuit.Sbase

    def get_phase_angles(self):
        """
        Get the phase shift solution
        :return:
        """
        return self.extract(self.phase_shift, make_abs=False)

    def get_hvdc_flow(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.hvdc_flow, make_abs=False) * self.numerical_circuit.Sbase

    def get_hvdc_loading(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.hvdc_flow, make_abs=False) * self.numerical_circuit.Sbase / self.numerical_circuit.hvdc_data.rate[:, 0]

    def get_hvdc_slacks(self):
        """
        return the branch loading (time, device)
        :return: 2D array
        """
        return self.extract(self.hvdc_slacks, make_abs=False) * self.numerical_circuit.Sbase


if __name__ == '__main__':
    from GridCal.Engine.basic_structures import BranchImpedanceMode
    from GridCal.Engine.IO.file_handler import FileOpen
    from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit

    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas_voltages_hvdc_shifter.gridcal'
    fname = r'C:\Users\SPV86\Documents\Git\GitHub\GridCal\Grids_and_profiles\grids\IEEE14 - ntc areas_voltages_hvdc_shifter.gridcal'

    main_circuit = FileOpen(fname).open()

    # compute information about areas ----------------------------------------------------------------------------------

    area_from_idx = 1
    area_to_idx = 0
    areas = main_circuit.get_bus_area_indices()

    numerical_circuit_ = compile_snapshot_opf_circuit(circuit=main_circuit,
                                                      apply_temperature=False,
                                                      branch_tolerance_mode=BranchImpedanceMode.Specified)

    # get the area bus indices
    areas = areas[numerical_circuit_.original_bus_idx]
    a1 = np.where(areas == area_from_idx)[0]
    a2 = np.where(areas == area_to_idx)[0]

    problem = OpfNTC(numerical_circuit=numerical_circuit_, area_from_bus_idx=a1, area_to_bus_idx=a2,
                     generation_formulation=GenerationNtcFormulation.Proportional)

    print('Solving...')
    status = problem.solve()

    print("Status:", status)

    print('Angles\n', np.angle(problem.get_voltage()))
    print('Branch loading\n', problem.get_loading())
    print('Gen power\n', problem.get_generator_power())
    print('Delta power\n', problem.get_generator_delta())
    print('Area slack', problem.area_balance_slack.solution_value())
    print('HVDC flow\n', problem.get_hvdc_flow())
