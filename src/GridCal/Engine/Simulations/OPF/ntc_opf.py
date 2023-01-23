# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""
This file implements a DC-OPF for time series
That means that solves the OPF problem for a complete time series at once
"""
from enum import Enum
from typing import List, Dict, Tuple
import numpy as np
from GridCal.Engine.Core.snapshot_opf_data import SnapshotOpfData
from GridCal.Engine.Simulations.OPF.opf_templates import Opf, MIPSolvers
from GridCal.Engine.Devices.enumerations import TransformerControlType, HvdcControlType, \
    GenerationNtcFormulation
from GridCal.Engine.basic_structures import Logger
import os

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


def save_lp(solver: pywraplp.Solver, file_name="ntc_opf_problem.lp"):
    """
    Save problem in LP format
    :param solver: Solver instance
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
    Get the branches that join two areas
    :param nbr: Number of branches
    :param F: Array of From node indices
    :param T: Array of To node indices
    :param buses_areas_1: Area from
    :param buses_areas_2: Area to
    :return: List of (branch index, flow sense w.r.t the area exchange)
    """

    lst: List[Tuple[int, float]] = list()
    for k in range(nbr):
        if F[k] in buses_areas_1 and T[k] in buses_areas_2:
            lst.append((k, 1.0))
        elif F[k] in buses_areas_2 and T[k] in buses_areas_1:
            lst.append((k, -1.0))
    return lst


def get_structural_ntc(inter_area_branches, inter_area_hvdc, branch_ratings, hvdc_ratings):
    '''

    :param inter_area_branches:
    :param inter_area_hvdc:
    :param branch_ratings:
    :param hvdc_ratings:
    :return:
    '''
    if len(inter_area_branches):
        idx_branch, b = list(zip(*inter_area_branches))
        idx_branch = list(idx_branch)
    else:
        idx_branch = list()

    if len(inter_area_hvdc):
        idx_hvdc, b = list(zip(*inter_area_hvdc))
        idx_hvdc = list(idx_hvdc)
    else:
        idx_hvdc = list()

    return sum(branch_ratings[idx_branch]) + sum(hvdc_ratings[idx_hvdc])


def get_generators_per_areas(Cgen, buses_in_a1, buses_in_a2):
    """
    Get the generators that belong to the Area 1, Area 2 and the rest of areas
    :param Cgen: CSC connectivity matrix of generators and buses [ngen, nbus]
    :param buses_in_a1: List of bus indices of the area 1
    :param buses_in_a2: List of bus indices of the area 2
    :return: Tree lists: (gens_in_a1, gens_in_a2, gens_out) each of the lists contains (bus index, generator index) tuples
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


def validate_generator_limits(gen_idx, Pgen, Pmax, Pmin, logger):
    """

    :param gen_idx: generator index to check
    :param Pgen: Array of generator active power values in p.u.
    :param Pmax: Array of generator maximum active power values in p.u.
    :param Pmin: Array of generator minimum active power values in p.u.
    :return:
    """

    if Pmin[gen_idx] >= Pmax[gen_idx]:
        logger.add_error('Pmin >= Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

    if Pgen[gen_idx] > Pmax[gen_idx]:
        logger.add_error('Pgen > Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

    if Pgen[gen_idx] < Pmin[gen_idx]:
        logger.add_error('Pgen < Pmin', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])


def validate_generator_to_increase(gen_idx, generator_active, generator_dispatchable, Pgen, Pmax, Pmin):
    """

    :param gen_idx: generator index to check
    :param generator_active: Array of generation active values (True / False)
    :param generator_dispatchable: Array of Generator dispatchable variables (True / False)
    :param Pgen: Array of generator active power values in p.u.
    :param Pmax: Array of generator maximum active power values in p.u.
    :param Pmin: Array of generator minimum active power values in p.u.
    :return:
    """

    c1 = generator_active[gen_idx]
    c2 = generator_dispatchable[gen_idx]
    c3 = Pgen[gen_idx] < Pmax[gen_idx]
    # c4 = Pgen[gen_idx] > 0

    return c1 and c2 and c3  # and c4


def validate_generator_to_decrease(gen_idx, generator_active, generator_dispatchable, Pgen, Pmax, Pmin):
    """

    :param gen_idx:
    :param generator_active: Array of generation active values (True / False)
    :param generator_dispatchable: Array of Generator dispatchable variables (True / False)
    :param Pgen: Array of generator active power values in p.u.
    :param Pmax: Array of generator maximum active power values in p.u.
    :param Pmin: Array of generator minimum active power values in p.u.
    :return:
    """

    c1 = generator_active[gen_idx]
    c2 = generator_dispatchable[gen_idx]
    c3 = Pgen[gen_idx] > Pmin[gen_idx]
    # c4 = Pgen[gen_idx] > 0

    return c1 and c2 and c3  # and c4


def formulate_optimal_generation(solver: pywraplp.Solver, generator_active, dispatchable, generator_cost,
                                 generator_names, Sbase, inf, ngen, Cgen, Pgen, Pmax, Pmin, a1, a2,
                                 logger: Logger, dispatch_all_areas=False):
    """
    Formulate the Generation in an optimal fashion. This means that the generator increments
    attend to the generation cost and not to a proportional dispatch rule
    :param solver: Solver instance to which add the equations
    :param generator_active: Array of generation active values (True / False)
    :param dispatchable: Array of Generator dispatchable variables (True / False)
    :param generator_cost: Array of generator costs
    :param generator_names: Array of Generator names
    :param Sbase: Base power (i.e. 100 MVA)
    :param inf: Value representing the infinite value (i.e. 1e20)
    :param ngen: Number of generators
    :param Cgen: CSC connectivity matrix of generators and buses [ngen, nbus]
    :param Pgen: Array of generator active power values in p.u.
    :param Pmax: Array of generator maximum active power values in p.u.
    :param Pmin: Array of generator minimum active power values in p.u.
    :param a1: array of bus indices of the area 1
    :param a2: array of bus indices of the area 2
    :param logger: Logger instance
    :param dispatch_all_areas: boolean to force all areas dispatch
    :return: Many arrays of variables:
        - generation: Array of generation LP variables
        - delta: Array of generation delta LP variables
        - gen_a1_idx: Indices of the generators in the area 1
        - gen_a2_idx: Indices of the generators in the area 2
        - power_shift: Power shift LP variable
        - dgen1: List of generation delta LP variables in the area 1
        - gen_cost: used generation cost
        - delta_slack_1: Array of generation delta LP Slack variables up
        - delta_slack_2: Array of generation delta LP Slack variables down
    """

    #TODO: check this method

    gens1, gens2, gens_out = get_generators_per_areas(Cgen, a1, a2)
    gen_cost = generator_cost * Sbase  # pass from $/MWh to $/p.u.h
    generation = np.zeros(ngen, dtype=object)
    delta = np.zeros(ngen, dtype=object)

    dgen1 = list()
    dgen2 = list()

    generation1 = list()
    generation2 = list()

    Pgen1 = list()
    Pgen2 = list()

    gen_a1_idx = list()
    gen_a2_idx = list()

    # generators in the sending area
    for bus_idx, gen_idx in gens1:

        if generator_active[gen_idx] and dispatchable[gen_idx]:
            name = 'gen_up_{0}_bus{1}'.format(generator_names[gen_idx], bus_idx)

            if Pmin[gen_idx] >= Pmax[gen_idx]:
                logger.add_error('Pmin >= Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

            generation[gen_idx] = solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
            delta[gen_idx] = generation[gen_idx] - Pgen[gen_idx]

            dgen1.append(delta[gen_idx])

        else:
            generation[gen_idx] = Pgen[gen_idx]
            delta[gen_idx] = 0

        # generation1.append(generation[gen_idx])
        Pgen1.append(Pgen[gen_idx])
        gen_a1_idx.append(gen_idx)

    # Generators in the receiving area
    for bus_idx, gen_idx in gens2:

        if generator_active[gen_idx] and dispatchable[gen_idx]:
            name = 'gen_down_{0}_bus{1}'.format( generator_names[gen_idx], bus_idx)

            if Pmin[gen_idx] >= Pmax[gen_idx]:
                logger.add_error('Pmin >= Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

            generation[gen_idx] = solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
            delta[gen_idx] = Pgen[gen_idx] - generation[gen_idx]

            dgen2.append(delta[gen_idx])

        else:
            generation[gen_idx] = Pgen[gen_idx]
            delta[gen_idx] = 0

        # generation2.append(generation[gen_idx])
        Pgen2.append(Pgen[gen_idx])
        gen_a2_idx.append(gen_idx)

    # fix the generation at the rest of generators
    for bus_idx, gen_idx in gens_out:

        if dispatch_all_areas:

            if generator_active[gen_idx] and dispatchable[gen_idx]:
                name = 'gen_down_{0}@bus{1}'.format(generator_names[gen_idx], bus_idx)

                if Pmin[gen_idx] >= Pmax[gen_idx]:
                    logger.add_error('Pmin >= Pmax', 'Generator index {0}'.format(gen_idx), Pmin[gen_idx])

                generation[gen_idx] = solver.NumVar(Pmin[gen_idx], Pmax[gen_idx], name)
                delta[gen_idx] = Pgen[gen_idx] - generation[gen_idx]

            else:
                generation[gen_idx] = Pgen[gen_idx]
                delta[gen_idx] = 0
        else:
            generation[gen_idx] = Pgen[gen_idx]
            delta[gen_idx] = 0

    # enforce area equality
    solver.Add(solver.Sum(dgen1) == solver.Sum(dgen2), 'Area equality assignment')

    power_shift = solver.Sum(generation1)

    return generation, delta, gen_a1_idx, gen_a2_idx, power_shift, dgen1, gen_cost


def check_optimal_generation(generator_active, generator_names, dispatchable, Cgen, Pgen, a1, a2, generation, delta,
                             logger: Logger):
    """
    Check the results of the optimal generation increments
    :param generator_active: Array of generation active values (True / False)
    :param generator_names: Array of Generator names
    :param dispatchable: Array of Generator dispatchable variables (True / False)
    :param Cgen: CSC connectivity matrix of generators and buses [ngen, nbus]
    :param Pgen: Array of generator active power values in p.u.
    :param a1: array of bus indices of the area 1
    :param a2: array of bus indices of the area 2
    :param generation: Array of generation values (resulting of the LP solution)
    :param delta: Array of generation delta values (resulting of the LP solution)
    :param logger: Logger instance
    :return: Nothing
    """
    gens1, gens2, gens_out = get_generators_per_areas(Cgen, a1, a2)

    dgen1 = list()
    dgen2 = list()

    for bus_idx, gen_idx in gens1:
        if generator_active[gen_idx] and dispatchable[gen_idx]:
            res = generation[gen_idx] == Pgen[gen_idx] + delta[gen_idx]
            dgen1.append(delta[gen_idx])

            if not res:
                logger.add_divergence('Delta up condition not met '
                                      '(generation[gen_idx] == Pgen[gen_idx] + delta[gen_idx])',
                                      generator_names[gen_idx], generation[gen_idx], Pgen[gen_idx] + delta[gen_idx])

    for bus_idx, gen_idx in gens2:
        if generator_active[gen_idx] and dispatchable[gen_idx]:
            res = generation[gen_idx] == Pgen[gen_idx] - delta[gen_idx]
            dgen2.append(delta[gen_idx])

            if not res:
                logger.add_divergence('Delta down condition not met '
                                      '(generation[gen_idx] == Pgen[gen_idx] - delta[gen_idx])',
                                      generator_names[gen_idx], generation[gen_idx], Pgen[gen_idx] - delta[gen_idx])

    # check area equality
    sum_a1 = sum(dgen1)
    sum_a2 = sum(dgen2)
    res = sum_a1 == sum_a2

    if not res:
        logger.add_divergence('Area equality not met', 'grid', sum_a1, sum_a2)

def formulate_proportional_generation(solver: pywraplp.Solver, generator_active, generator_dispatchable,
                                      generator_cost, generator_names, inf, ngen, Cgen, Pgen, Pmax,
                                      Pmin, a1, a2, logger: Logger):
    """
    Formulate the generation increments in a proportional fashion
    :param solver: Solver instance to which add the equations
    :param generator_active: Array of generation active values (True / False)
    :param generator_dispatchable: Array of Generator dispatchable variables (True / False)
    :param generator_cost: Array of generator costs
    :param generator_names: Array of Generator names
    :param inf: Value representing the infinite value (i.e. 1e20)
    :param ngen: Number of generators
    :param Cgen: CSC connectivity matrix of generators and buses [ngen, nbus]
    :param Pgen: Array of generator active power values in p.u.
    :param Pmax: Array of generator maximum active power values in p.u.
    :param Pmin: Array of generator minimum active power values in p.u.
    :param a1: array of bus indices of the area 1
    :param a2: array of bus indices of the area 2
    :param logger: Logger instance
        :return: Many arrays of variables:
        - generation: Array of generation LP variables
        - delta: Array of generation delta LP variables
        - gen_a1_idx: Indices of the generators in the area 1
        - gen_a2_idx: Indices of the generators in the area 2
        - power_shift: Power shift LP variable
        - gen_cost: Array of generation costs
    """
    gens_a1, gens_a2, gens_out = get_generators_per_areas(Cgen, a1, a2)
    gen_cost = np.ones(ngen)
    generation = np.zeros(ngen, dtype=object)
    delta = np.zeros(ngen, dtype=object)

    # # Only for debug purpose
    # Pgen = np.array([-102, 500, 1800, 1500, -300, 100])
    # gens_a1 = [(0, 0), (1, 1), (2, 2)]
    # gens_a2 = [(3, 3), (4, 4), (5, 5)]
    # gens_out = [(6, 6)]
    # Pmax = np.array([1500, 1500, 1500, 1500, 1500, 1500])
    # Pmin = np.array([-1500, -1500, -1500, -1500, -100, -1500])
    # generator_active = np.array([True, True, True, True, True, True])
    # generator_dispatchable = np.array([True, True, True, True, True, True])

    # get generator idx for each areas. A1 increase. A2 decrease
    a1_gen_idx = [gen_idx for bus_idx, gen_idx in gens_a1]
    a2_gen_idx = [gen_idx for bus_idx, gen_idx in gens_a2]
    out_gen_idx = [gen_idx for bus_idx, gen_idx in gens_out]

    # generator area mask
    is_gen_in_a1 = np.isin(range(len(Pgen)), a1_gen_idx, assume_unique=True)
    is_gen_in_a2 = np.isin(range(len(Pgen)), a2_gen_idx, assume_unique=True)

    # mask for valid generators
    Pgen_a1 = Pgen * is_gen_in_a1 * generator_active * generator_dispatchable * (Pgen < Pmax)
    Pgen_a2 = Pgen * is_gen_in_a2 * generator_active * generator_dispatchable * (Pgen > Pmin)

    # Filter positive and negative generators. Same vectors lenght, set not matched values to zero.
    gen_pos_a1 = np.where(Pgen_a1 < 0, 0, Pgen_a1)
    gen_neg_a1 = np.where(Pgen_a1 > 0, 0, Pgen_a1)
    gen_pos_a2 = np.where(Pgen_a2 < 0, 0, Pgen_a2)
    gen_neg_a2 = np.where(Pgen_a2 > 0, 0, Pgen_a2)

    # get proportions of contribution by sense (gen or pump) and area
    # the idea is both techs contributes to achieve the power shift goal in the same proportion
    # that in base situation
    prop_up_a1 = np.sum(gen_pos_a1) / np.sum(np.abs(Pgen_a1))
    prop_dw_a1 = np.sum(gen_neg_a1) / np.sum(np.abs(Pgen_a1))
    prop_up_a2 = np.sum(gen_pos_a2) / np.sum(np.abs(Pgen_a2))
    prop_dw_a2 = np.sum(gen_neg_a2) / np.sum(np.abs(Pgen_a2))

    # get proportion by production (ammount of power contributed by generator to his sensed area).
    prop_up_gen_a1 = gen_pos_a1 / np.sum(np.abs(gen_pos_a1)) if np.sum(np.abs(gen_pos_a1)) != 0 else np.zeros_like(gen_pos_a1)
    prop_dw_gen_a1 = gen_neg_a1 / np.sum(np.abs(gen_neg_a1)) if np.sum(np.abs(gen_neg_a1)) != 0 else np.zeros_like(gen_neg_a1)
    prop_up_gen_a2 = gen_pos_a2 / np.sum(np.abs(gen_pos_a2)) if np.sum(np.abs(gen_pos_a2)) != 0 else np.zeros_like(gen_pos_a2)
    prop_dw_gen_a2 = gen_neg_a2 / np.sum(np.abs(gen_neg_a2)) if np.sum(np.abs(gen_neg_a2)) != 0 else np.zeros_like(gen_neg_a2)

    # delta proportion by generator (considering both proportions: sense and production)
    prop_gen_delta_up_a1 = prop_up_gen_a1 * prop_up_a1
    prop_gen_delta_dw_a1 = prop_dw_gen_a1 * prop_dw_a1
    prop_gen_delta_up_a2 = prop_up_gen_a2 * prop_up_a2
    prop_gen_delta_dw_a2 = prop_dw_gen_a2 * prop_dw_a2

    # Join generator proportions into one vector
    # Notice they will not added: just joining like 'or' logical operation
    proportions_a1 = prop_gen_delta_up_a1 + prop_gen_delta_dw_a1
    proportions_a2 = prop_gen_delta_up_a2 + prop_gen_delta_dw_a2
    proportions = proportions_a1 + proportions_a2

    # some checks
    if not np.isclose(np.sum(proportions_a1), 1, rtol=1e-6):
        logger.add_warning('Issue computing proportions to scale delta generation in area 1.')

    if not np.isclose(np.sum(proportions_a2), 1, rtol=1e-6):
        logger.add_warning('Issue computing proportions to scale delta generation in area 2')

    # apply power shift sense based on area (increase a1, decrease a2)
    sense = (1 * is_gen_in_a1) + (-1 * is_gen_in_a2)

    # # only for debug purpose
    # debug_power_shift = 1000
    # debug_deltas = debug_power_shift * proportions * sense
    # debug_generation = Pgen + debug_deltas

    # --------------------------------------------
    # Formulate Solver valiables
    # --------------------------------------------

    power_shift = solver.NumVar(-inf, inf, 'power_shift')

    for gen_idx, P in enumerate(Pgen):
        if gen_idx not in out_gen_idx:

            # store solver variables
            generation[gen_idx] = solver.NumVar(
                Pmin[gen_idx], Pmax[gen_idx],
                'gen_{0}'.format(generator_names[gen_idx]))

            delta[gen_idx] = solver.NumVar(
                -inf, inf,
                'gen_{0}_delta'.format(generator_names[gen_idx]))

            # solver variables formulation
            solver.Add(
                delta[gen_idx] == power_shift * proportions[gen_idx] * sense[gen_idx],
                'gen_{0}_assignment'.format(generator_names[gen_idx]))

            solver.Add(
                generation[gen_idx] == Pgen[gen_idx] + delta[gen_idx],
                'gen_{0}_delta_assignment'.format(generator_names[gen_idx]))

        else:
            generation[gen_idx] = Pgen[gen_idx]


    return generation, delta, a1_gen_idx, a2_gen_idx, power_shift, gen_cost


def check_proportional_generation(generator_active, generator_dispatchable, generator_cost, generator_names,
                                  Sbase, Cgen, Pgen, Pmax, Pmin, a1, a2, generation, delta,
                                  power_shift, logger: Logger):
    """

    :param generator_active: Array of generation active values (True / False)
    :param generator_dispatchable: Array of Generator dispatchable variables (True / False)
    :param generator_cost: Array of generator costs
    :param generator_names: Array of Generator names
    :param Sbase: Base power (i.e. 100 MVA)
    :param Cgen: CSC connectivity matrix of generators and buses [ngen, nbus]
    :param Pgen: Array of generator active power values in p.u.
    :param Pmax: Array of generator maximum active power values in p.u.
    :param Pmin: Array of generator minimum active power values in p.u.
    :param a1: array of bus indices of the area 1
    :param a2: array of bus indices of the area 2
    :param t: Time index (i.e 0)
    :param generation: Array of generation values (resulting of the LP solution)
    :param delta: Array of generation delta values (resulting of the LP solution)
    :param power_shift: power shift LP variable
    :param logger: Logger instance
    :return: Nothing
    """
    gens1, gens2, gens_out = get_generators_per_areas(Cgen, a1, a2)
    gen_cost = generator_cost * Sbase  # pass from $/MWh to $/p.u.h

    dgen1 = list()
    dgen2 = list()

    nU1 = 0
    nD1 = 0

    sum_gen_1 = 0
    for bus_idx, gen_idx in gens1:
        if Pgen[gen_idx] > 0:
            nU1 += Pgen[gen_idx]

        if Pgen[gen_idx] < 0:
            nD1 -= Pgen[gen_idx]

        if validate_generator_to_increase(gen_idx, generator_active, generator_dispatchable, Pgen, Pmax, Pmin):
            sum_gen_1 += Pgen[gen_idx]


    nU2 = 0
    nD2 = 0
    sum_gen_2 = 0
    for bus_idx, gen_idx in gens2:
        if validate_generator_to_decrease(gen_idx, generator_active, generator_dispatchable, Pgen, Pmax, Pmin):
            sum_gen_2 += Pgen[gen_idx]

    # check area 1
    for bus_idx, gen_idx in gens1:

        if validate_generator_to_increase(gen_idx, generator_active, generator_dispatchable, Pgen, Pmax, Pmin):

            prop = abs(Pgen[gen_idx] / sum_gen_1)
            res = delta[gen_idx] == prop * power_shift
            if not res:
                logger.add_divergence(
                    "Delta up equal to it's share of the power shift  (delta[i] == prop * power_shift)",
                    generator_names[gen_idx],
                    delta[gen_idx],
                    prop * power_shift
                )

            res = generation[gen_idx] == Pgen[gen_idx] + delta[gen_idx]
            if not res:
                logger.add_divergence(
                    'Delta up condition not met (generation[i] == Pgen[i] + delta[i])',
                    generator_names[gen_idx],
                    generation[gen_idx],
                    Pgen[gen_idx] + delta[gen_idx]
                )

            dgen1.append(delta[gen_idx])

    # check area 2
    for bus_idx, gen_idx in gens2:

        if validate_generator_to_decrease(gen_idx, generator_active, generator_dispatchable, Pgen, Pmax, Pmin):

            prop = abs(Pgen[gen_idx] / sum_gen_2)
            res = delta[gen_idx] == prop * power_shift
            if not res:
                logger.add_divergence(
                    "Delta down equal to it's share of the power shift (delta[i] == prop * power_shift)",
                    generator_names[gen_idx],
                    delta[gen_idx],
                    prop * power_shift)

            res = generation[gen_idx] == Pgen[gen_idx] - delta[gen_idx]

            if not res:
                logger.add_divergence(
                    'Delta down condition not met (generation[i] == Pgen[i] - delta[i])',
                    generator_names[gen_idx],
                    generation[gen_idx],
                    Pgen[gen_idx] - delta[gen_idx])

            dgen2.append(delta[gen_idx])

    # check area equality
    sum_a1 = sum(dgen1)
    sum_a2 = sum(dgen2)
    res = sum_a1 == sum_a2

    if not res:
        logger.add_divergence('Area equality not met', 'grid', sum_a1, sum_a2)


def formulate_angles(solver: pywraplp.Solver, nbus, vd, bus_names, angle_min, angle_max,
                     logger: Logger, set_ref_to_zero=True):
    """
    Formulate the angles
    :param solver: Solver instance to which add the equations
    :param nbus: number of buses
    :param vd: array of slack nodes
    :param bus_names: Array of bus names
    :param angle_min: Array of bus minimum angles
    :param angle_max: Array of bus maximum angles
    :param logger: Logger instance
    :param set_ref_to_zero: Set reference bus angle to zero?
    :return: Array of bus angles LP variables
    """
    theta = np.zeros(nbus, dtype=object)

    for i in range(nbus):

        if angle_min[i] > angle_max[i]:
            logger.add_error('Theta min > Theta max', 'Bus {0}'.format(i), angle_min[i])

        theta[i] = solver.NumVar(
            angle_min[i], angle_max[i],
            'theta_{0}:{1}'.format(bus_names[i], i))

    if set_ref_to_zero:
        for i in vd:
            solver.Add(theta[i] == 0, "reference_bus_angle_zero_assignment_{0}:{1}".format(bus_names[i], i))

    return theta


def formulate_angles_shifters(solver: pywraplp.Solver, nbr, branch_active, branch_names, branch_theta,
                              branch_theta_min, branch_theta_max, control_mode, logger):
    """

    :param solver: Solver instance to which add the equations
    :param nbr: number of branches
    :param nbr: number of buses
    :param branch_active: array of branch active states
    :param branch_names: array of branch names
    :param branch_theta: Array of branch shift angles
    :param branch_theta_min: Array of branch minimum angles
    :param branch_theta_max: Array of branch maximum angles
    :param control_mode: Array of branch control modes
    :param logger: logger instance
    :return:
        - theta_shift: array of bus voltage shift angles (LP variables)
        - tau: Array branch phase shift angles (mix of values and LP variables)
    """

    tau = np.zeros(nbr, dtype=object)

    for m in range(nbr):

        if branch_active[m]:

            if control_mode[m] == TransformerControlType.Pt:  # is a phase shifter
                # create the phase shift variable
                tau[m] = solver.NumVar(
                    branch_theta_min[m], branch_theta_max[m],
                    'branch_phase_shift_{0}:{1}'.format(branch_names[m], m))

            else:
                tau[m] = branch_theta[m]

    return tau


def formulate_power_injections(solver: pywraplp.Solver, Cgen, generation, Cload, load_power,
                               logger: Logger):
    """
    Formulate the power injections
    :param solver: Solver instance to which add the equations
    :param Cgen: CSC connectivity matrix of generators and buses [ngen, nbus]
    :param generation: Array of generation LP variables
    :param Cload: CSC connectivity matrix of load and buses [nload, nbus]
    :param load_active: Array of load active state
    :param load_power: Array of load power
    :param Sbase: Base power (i.e. 100 MVA)
    :param logger: logger instance
    :return:
        - power injections array
    """
    gen_injections_per_bus = lpExpand(Cgen, generation)
    load_fixed_injections = Cload * load_power

    return gen_injections_per_bus - load_fixed_injections


def check_power_injections(load_power, Cgen, generation, Cload):
    """
    Check the power injections formulas once solved the problem
    :param Cgen: CSC connectivity matrix of generators and buses [ngen, nbus]
    :param generation: Array of generation values (resulting of the LP solution)
    :param Cload: CSC connectivity matrix of load and buses [nload, nbus]
    :return: Array of bus power injections
    """
    gen_injections = Cgen * generation
    load_fixed_injections = Cload * load_power
    return gen_injections - load_fixed_injections


def formulate_node_balance(solver: pywraplp.Solver, Bbus, angles, Pinj, bus_active, bus_names,
                           logger: Logger):
    """
    Formulate the nodal power balance
    :param solver: Solver instance to which add the equations
    :param Bbus: Susceptance matrix in CSC format
    :param angles: Array of voltage angles LP variables
    :param Pinj: Array of power injections per bus (mix of values and LP variables)
    :param bus_active: Array of bus active status
    :param bus_names: Array of bus names.
    :param logger: logger instance
    :return: Array of calculated power (mix of values and LP variables)
    """

    calculated_power = lpDot(Bbus, angles)

    # equal the balance to the generation: eq.13,14 (equality)
    i = 0
    for p_calc, p_set in zip(calculated_power, Pinj):
        if bus_active[i] and not isinstance(p_calc, int):  # balance is 0 for isolated buses
            solver.Add(p_calc == p_set, "node_power_balance_assignment_{0}:{1}".format(bus_names[i], i))
        i += 1

    return calculated_power


def check_node_balance(Bbus, angles, Pinj, bus_active, bus_names, logger: Logger):
    """
    Formulate the power balance
    :param Bbus: Susceptance matrix in CSC format
    :param angles: Array of voltage angles LP variables
    :param Pinj: Power injections array
    :param bus_active: Array of bus active status
    :param bus_names: Array of bus names.
    :param logger: logger instance
    :return: Array of computed powers per bus (only values)
    """
    calculated_power = Bbus * angles

    # equal the balance to the generation: eq.13,14 (equality)
    i = 0
    for p_calc, p_set in zip(calculated_power, Pinj):
        if bus_active[i] and not isinstance(p_calc, int):  # balance is 0 for isolated buses
            res = p_calc == p_set

            if not res:
                logger.add_divergence('Kirchhoff not met (balance == power)', bus_names[i], p_calc, p_set)

        i += 1

    return calculated_power


def formulate_branches_flow(solver: pywraplp.Solver, nbr, nbus, Rates, Sbase,
                            branch_active, branch_names, branch_dc, R, X, F, T, inf, monitor_loading,
                            branch_sensitivity_threshold, monitor_only_sensitive_branches, angles, tau,
                            alpha_abs, alpha_n1_abs, monitor_only_ntc_load_rule_branches, cep_rule,
                            structural_ntc, logger):
    """

    :param solver: Solver instance to which add the equations
    :param nbr: number of branches
    :param nbus: number of branches
    :param Rates: array of branch rates
    :param branch_active: array of branch active states
    :param branch_names: array of branch names
    :param branch_dc: array of branch DC status (True/False)
    :param R: Array of branch resistance values
    :param X: Array of branch reactance values
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param inf: Value representing the infinite (i.e. 1e20)
    :param monitor_loading: Array of branch monitor loading status (True/False)
    :param branch_sensitivity_threshold: minimum branch sensitivity to the exchange (used to filter branches out)
    :param monitor_only_sensitive_branches: Flag to monitor only sensitive branches
    :param angles: array of bus voltage angles (LP variables)
    :param tau: Array branch phase shift angles (mix of values and LP variables)
    :param alpha_abs: Array of absolute branch sensitivity to the exchange
    :param alpha_n1_abs: Array of absolute branch sensitivity to the exchange in n-1 condition
    :param structural_ntc: Maximun NTC available by thermal interconexion rates.
    :param cep_rule: percentage of loading reserved to exchange flow (Clean Energy Package rule by ACER).
    :param logger: logger instance
    :return:
        - flow_f: Array of formulated branch flows (LP variblaes)
        - tau: Array branch phase shift angles (mix of values and LP variables)
        - theta_shift: Array bus shift angle (mix of values and LP variables)
        - monitor: Array of final monitor status per branch after applying the logic
    """

    flow_f = np.zeros(nbr, dtype=object)
    monitor = np.zeros(nbr, dtype=bool)
    branch_ntc_load_rule = np.zeros(nbr, dtype=float)
    Pinj_tau = np.zeros(nbus, dtype=object)
    rates = Rates / Sbase

    # formulate flows
    for m in range(nbr):

        if branch_active[m]:

            max_alpha = max(alpha_abs[m], max(alpha_n1_abs[m]))

            if rates[m] <= 0:
                logger.add_error('Rate = 0', 'Branch:{0}'.format(m) + ';' + branch_names[m], rates[m])

            # determine the monitoring logic
            monitor[m] = monitor_loading[m]

            if monitor_only_sensitive_branches:
                monitor[m] = monitor[m] and max_alpha > branch_sensitivity_threshold

            if monitor_only_ntc_load_rule_branches:
                monitor[m] = monitor[m] and branch_ntc_load_rule[m] <= structural_ntc

            # determine branch rate according monitor logic
            if monitor[m]:
                # declare the flow variable with rate limits
                flow_f[m] = solver.NumVar(
                    -rates[m], rates[m], 'branch_flow_{0}:{1}'.format(branch_names[m], m))
            else:
                # declare the flow variable with ample limits
                flow_f[m] = solver.NumVar(
                    -inf, inf, 'branch_flow_{0}:{1}'.format(branch_names[m], m))

            # NTC min for considering as limiting element by CEP rule
            branch_ntc_load_rule[m] = cep_rule * rates[m] / (max_alpha + 1e-20)

            # compute the flow
            _f = F[m]
            _t = T[m]

            # compute the branch susceptance
            if branch_dc[m]:
                bk = 1.0 / R[m]
            else:
                bk = 1.0 / X[m]

            # branch power from-to eq.15
            solver.Add(
                flow_f[m] == bk * (angles[_f] - angles[_t] - tau[m]),
                'branch_power_flow_assignment_{0}:{1}'.format(branch_names[m], m))

            # add the shifter injections matching the flow
            Ptau = bk * tau[m]

            Pinj_tau[_f] = -Ptau
            Pinj_tau[_t] = Ptau

    return flow_f, monitor, Pinj_tau, branch_ntc_load_rule


def check_branches_flow(nbr, Rates, Sbase, branch_active, branch_names, branch_dc, control_mode, R, X, F, T,
                        monitor_loading, branch_sensitivity_threshold, monitor_only_sensitive_branches,
                        angles, alpha_abs, alpha_n1_abs, flow_f, tau, logger: Logger,):
    """

    :param nbr: number of branches
    :param Rates: array of branch rates
    :param Sbase: Base power (i.e. 100 MVA)
    :param branch_active: array of branch active states
    :param branch_names: array of branch names
    :param branch_dc: array of branch DC status (True/False)
    :param control_mode: Array of branch control modes
    :param R: Array of branch resistance values
    :param X: Array of branch reactance values
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param monitor_loading: Array of branch monitor loading status (True/False)
    :param branch_sensitivity_threshold: minimum branch sensitivity to the exchange (used to filter branches out)
    :param monitor_only_sensitive_branches: Flag to monitor only sensitive branches
    :param angles: array of bus voltage angles (LP variables)
    :param alpha_abs: Array of absolute branch sensitivity to the exchange
    :param alpha_n1_abs: Array of absolute branch sensitivity to the exchange on n-1 condition
    :param flow_f: Array of branch flow solutions
    :param tau: Array branch phase shift angle solutions
    :param logger: logger instance
    :return: Array of final monitor status per branch after applying the logic
    """

    rates = Rates / Sbase
    monitor = np.zeros(nbr, dtype=bool)

    # formulate flows
    for m in range(nbr):

        if branch_active[m]:

            # determine the monitoring logic
            if monitor_only_sensitive_branches:
                monitor[m] = monitor_loading[m] and max(alpha_abs[m], alpha_n1_abs[m]) > branch_sensitivity_threshold
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
                            branch_names[m], flow_f[m], bk * (angles[_f] - angles[_t] + tau[m])
                        )

                else:
                    # branch power from-to eq.15
                    res = flow_f[m] == bk * (angles[_f] - angles[_t])

                    if not res:
                        logger.add_divergence(
                            'Branch flow setting (flow_f[m] == bk * (angles[f] - angles[t]))',
                            branch_names[m], flow_f[m], bk * (angles[_f] - angles[_t])
                        )

                # rating restriction in the sense from-to: eq.17
                res = flow_f[m] <= rates[m]

                if not res:
                    logger.add_divergence(
                        'Positive flow rating violated (flow_f[m] <= rates[m])',
                        branch_names[m], flow_f[m], rates[m]
                    )

                # rating restriction in the sense to-from: eq.18
                res = -rates[m] <= flow_f[m]
                if not res:
                    logger.add_divergence(
                        'Negative flow rating violated (-rates[m] <= flow_f[m])',
                        branch_names[m], flow_f[m], -rates[m]
                    )

    return monitor


def formulate_contingency(solver: pywraplp.Solver, ContingencyRates, Sbase, branch_names,
                          contingency_enabled_indices, LODF, F, T,  branch_sensitivity_threshold,
                          flow_f, monitor, alpha_n1, logger: Logger,  lodf_replacement_value=0):
    """
    Formulate the contingency flows
    :param solver: Solver instance to which add the equations
    :param ContingencyRates: array of branch contingency rates
    :param Sbase: Base power (i.e. 100 MVA)
    :param branch_names: array of branch names
    :param contingency_enabled_indices: array of branch indices enables for contingency
    :param LODF: LODF matrix
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param branch_sensitivity_threshold: minimum branch sensitivity to the exchange (used to filter branches out)
    :param flow_f: Array of formulated branch flows (LP variables)
    :param alpha_n1: Power transfer sensibility matrix
    :param monitor: Array of final monitor status per branch after applying the logic
    :return:
        - flow_n1f: List of contingency flows LP variables
        - con_idx: list of accepted contingency monitored and failed indices [(monitored, failed), ...]
    """
    rates = ContingencyRates / Sbase

    # get the indices of the branches marked for contingency
    con_br_idx = contingency_enabled_indices
    mon_br_idx = np.where(monitor == True)[0]

    # formulate contingency flows
    # this is done in a separated loop because all te flow variables must exist beforehand
    flow_n1f = list()
    con_idx = list()
    con_alpha = list()

    for m in mon_br_idx:  # for every monitored branch
        _f = F[m]
        _t = T[m]

        for c in con_br_idx:  # for every contingency

            c1 = m != c
            c2 = LODF[m, c] > branch_sensitivity_threshold
            c3 = np.abs(alpha_n1[m, c]) > branch_sensitivity_threshold

            if c1 and c2 and c3:

                lodf = LODF[m, c]

                if lodf > 1.1:
                    logger.add_warning("LODF correction", device=branch_names[m] + "@" + branch_names[c],
                                       value=lodf, expected_value=1.1)
                    lodf = lodf_replacement_value

                elif lodf < -1.1:
                    logger.add_warning("LODF correction", device=branch_names[m] + "@" + branch_names[c],
                                       value=lodf, expected_value=-1.1)
                    lodf = -lodf_replacement_value

                suffix = "{0}@{1}_{2}@{3}".format(branch_names[m], branch_names[c], m, c)

                flow_n1 = solver.NumVar(
                    -rates[m], rates[m], 'branch_flow_n-1_' + suffix)

                solver.Add(flow_n1 == flow_f[m] + lodf * flow_f[c],
                           "branch_flow_n-1_assignment_" + suffix)

                # store vars
                con_idx.append((m, c))
                flow_n1f.append(flow_n1)
                con_alpha.append(alpha_n1[m, c])

    return flow_n1f, con_alpha, con_idx


def check_contingency(ContingencyRates, Sbase, branch_names, contingency_enabled_indices, LODF, F, T,
                      branch_sensitivity_threshold, flow_f, monitor, logger: Logger):
    """
    Check the resulting contingency flows
    :param ContingencyRates: array of branch contingency rates
    :param Sbase: Base power (i.e. 100 MVA)
    :param branch_names: array of branch names
    :param contingency_enabled_indices: array of branch indices enables for contingency
    :param LODF: LODF matrix
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param branch_sensitivity_threshold: minimum branch sensitivity to the exchange (used to filter branches out)
    :param flow_f: Array of formulated branch flows (LP variblaes)
    :param monitor: Array of final monitor status per branch after applying the logic
    :param logger: logger instance
    :return: Nothing
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
                    logger.add_divergence('Positive contingency flow rating violated (flow_n1 <= rates[m])',
                                          branch_names[m] + '@' + branch_names[c], flow_n1, rates[m])

                # rating restriction in the sense to-from
                res = -rates[m] <= flow_n1

                if not res:
                    logger.add_divergence('Negative contingency flow rating violated (-rates[m] <= flow_n1)',
                                          branch_names[m] + '@' + branch_names[c], flow_n1, -rates[m])


def formulate_hvdc_flow(solver: pywraplp.Solver, nhvdc, names, rate, angles, hvdc_active, Pt, angle_droop, control_mode,
                        dispatchable, F, T, Pinj, Sbase, inf, inter_area_hvdc,
                        logger: Logger, force_exchange_sense=False):
    """
    Formulate the HVDC flow
    :param solver: Solver instance to which add the equations
    :param nhvdc: number of HVDC devices
    :param names: Array of HVDC names
    :param rate: Array of HVDC rates
    :param angles: Array of bus voltage angles (LP Variables)
    :param hvdc_active: Array of HVDC active status (True / False)
    :param Pt: Array of HVDC sending power
    :param angle_droop: Array of HVDC resistance values (this is used as the HVDC power/angle droop)
    :param control_mode: Array of HVDC control modes
    :param dispatchable: Array of HVDC dispatchable status (True/False)
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Pinj: Array of power injections (Mix of values and LP variables)
    :param Sbase: Base power (i.e. 100 MVA)
    :param inf: Value representing the infinite (i.e. 1e20)
    :param logger: logger instance
    :param force_exchange_sense: Boolean to force the hvdc flow in the same sense than exchange
    :return:
        - flow_f: Array of formulated HVDC flows (mix of values and variables)
    """
    rates = rate / Sbase

    flow_f = np.zeros(nhvdc, dtype=object)
    flow_sensed = np.zeros(nhvdc, dtype=object)
    hvdc_angle_slack_pos = np.zeros(nhvdc, dtype=object)
    hvdc_angle_slack_neg = np.zeros(nhvdc, dtype=object)

    for i in range(nhvdc):

        if hvdc_active[i]:

            _f = F[i]
            _t = T[i]

            suffix = "{0}_{1}".format(names[i], i)

            P0 = Pt[i] / Sbase

            if control_mode[i] == HvdcControlType.type_0_free:

                if rates[i] <= 0:
                    logger.add_error('Rate = 0', 'HVDC:{0}'.format(i), rates[i])

                flow_f[i] = solver.NumVar(-rates[i], rates[i], 'hvdc_flow_' + suffix)

                # formulate the hvdc flow as an AC line equivalent
                # to pass from MW/deg to p.u./rad -> * 180 / pi / (sbase=100)
                angle_droop_rad = angle_droop[i] * 57.295779513 / Sbase

                hvdc_angle_slack_pos[i] = solver.NumVar(0, inf, 'hvdc_angle_slack_pos_' + suffix)
                hvdc_angle_slack_neg[i] = solver.NumVar(0, inf, 'hvdc_angle_slack_neg_' + suffix)

                solver.Add(
                    flow_f[i] == P0 + angle_droop_rad * (angles[_f] - angles[_t] + hvdc_angle_slack_pos[i] - hvdc_angle_slack_neg[i]),
                    'hvdc_flow_assignment_' + suffix)

            elif control_mode[i] == HvdcControlType.type_1_Pset and not dispatchable[i]:
                # simple injections model: The power is set by the user
                flow_f[i] = P0

            elif control_mode[i] == HvdcControlType.type_1_Pset and dispatchable[i]:
                # simple injections model, the power is a variable and it is optimized
                P0 = solver.NumVar(-rates[i], rates[i], 'hvdc_pset_' + suffix)
                flow_f[i] = P0

            # add the injections matching the flow
            Pinj[_f] -= flow_f[i]
            Pinj[_t] += flow_f[i]


    if force_exchange_sense:

        # hvdc flow must be in the same exchange sense
        for i, sense in inter_area_hvdc:

            if control_mode[i] == HvdcControlType.type_1_Pset and dispatchable[i]:

                suffix = "{0}:{1}".format(names[i], i)

                flow_sensed[i] = solver.NumVar(0, inf, 'hvdc_sense_flow_' + suffix)

                solver.Add(
                    flow_sensed[i] == flow_f[i] * sense,
                    'hvdc_sense_restriction_assignment_' + suffix)



    #todo: ver cómo devolver el peso para el slack de hvdc que sea la diferencia entre el rate-flow (¿puede ser una variable?)

    return flow_f, hvdc_angle_slack_pos, hvdc_angle_slack_neg


def check_hvdc_flow(nhvdc, names, rate, angles, hvdc_active, Pt, angle_droop, control_mode, dispatchable,
                    F, T, Sbase, flow_f, logger: Logger):
    """
    Check the HVDC flows
    :param nhvdc: number of HVDC devices
    :param names: Array of HVDC names
    :param rate: Array of HVDC rates
    :param angles: Array of bus voltage angles (values from the problem)
    :param hvdc_active: Array of HVDC active status (True / False)
    :param Pt: Array of HVDC sending power
    :param r: Array of HVDC resistance values (this is used as the HVDC power/angle droop)
    :param control_mode: Array of HVDC control modes
    :param dispatchable: Array of HVDC dispatchable status (True/False)
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param Sbase: Base power (i.e. 100 MVA)
    :param flow_f: Array of formulated HVDC flows (values from the problem)
    :param logger: logger instance
    :return: None
    """
    rates = rate / Sbase

    for i in range(nhvdc):

        if hvdc_active[i]:

            _f = F[i]
            _t = T[i]

            suffix = "{0}:{1}".format(names[i], i)

            P0 = Pt[i] / Sbase

            if control_mode[i] == HvdcControlType.type_0_free:

                # formulate the hvdc flow as an AC line equivalent
                angle_droop_rad = angle_droop[i] * 57.295779513 / Sbase
                res = flow_f[i] == P0 + angle_droop_rad * (angles[_f] - angles[_t])

                if not res:
                    logger.add_divergence(
                        'HVDC free flow violation (flow_f[i] == P0 + bk * (angles[f] - angles[t]))',
                        names[i], flow_f[i], P0 + angle_droop_rad * (angles[_f] - angles[_t])
                    )

                # rating restriction in the sense from-to: eq.17
                res = flow_f[i] <= rates[i]

                if not res:
                    logger.add_divergence(
                        'HVDC positive rating violation (flow_f[i] <= rates[i])',
                        names[i], flow_f[i], rates[i]
                    )

                # rating restriction in the sense to-from: eq.18
                res = -rates[i] <= flow_f[i]

                if not res:
                    logger.add_divergence(
                        'HVDC negative rating violation (-rates[i] <= flow_f[i])',
                        names[i], flow_f[i], -rates[i]
                    )

            elif control_mode[i] == HvdcControlType.type_1_Pset and not dispatchable[i]:
                # simple injections model: The power is set by the user
                res = flow_f[i] == P0

                if not res:
                    logger.add_divergence(
                        'HVDC Pset, non dispatchable control not met (flow_f[i] == P0)',
                        names[i], flow_f[i], P0
                    )

            elif control_mode[i] == HvdcControlType.type_1_Pset and dispatchable[i]:
                # simple injections model, the power is a variable and it is optimized
                pass



def formulate_hvdc_contingency(solver: pywraplp.Solver, ContingencyRates, Sbase,
                               hvdc_flow_f, hvdc_active, PTDF, F, T, F_hvdc, T_hvdc, flow_f, monitor, alpha,
                               logger: Logger):
    """
    Formulate the contingency flows
    :param solver: Solver instance to which add the equations
    :param ContingencyRates: array of branch contingency rates
    :param PTDF: PTDF matrix
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param F_hvdc: Array of hvdc "from" bus indices
    :param T_hvdc: Array of hvdc "to" bus indices
    :param flow_f: Array of formulated branch flows (LP variblaes)
    :param hvdc_active: Array of hvdc active status
    :param monitor: Array of final monitor status per branch after applying the logic
    :param logger: logger instance
    :return:
        - flow_n1f: List of contingency flows LP variables
        - con_idx: list of accepted contingency monitored and failed indices [(monitored, failed), ...]
    """

    rates = ContingencyRates / Sbase
    mon_br_idx = np.where(monitor == True)[0]

    flow_hvdc_n1f = list()
    con_hvdc_idx = list()
    con_alpha = list()

    for i, hvdc_f in enumerate(hvdc_flow_f):
        _f_hvdc = F_hvdc[i]
        _t_hvdc = T_hvdc[i]

        if hvdc_active[i]:
            for m in mon_br_idx:  # for every monitored branch
                _f = F[m]
                _t = T[m]
                suffix = "Branch_{0}@Hvdc_{1}".format(m, i)

                flow_n1 = solver.NumVar(-rates[m], rates[m], 'hvdc_n-1_flow_' + suffix)
                solver.Add(flow_n1 == flow_f[m] + (PTDF[m, _f_hvdc] - PTDF[m, _t_hvdc]) * hvdc_f,
                           "hvdc_n-1_flow_assignment_" + suffix)

                # store vars
                con_hvdc_idx.append((m, i))
                flow_hvdc_n1f.append(flow_n1)
                con_alpha.append(PTDF[m, _f_hvdc] - PTDF[m, _t_hvdc] - alpha[m])

    return flow_hvdc_n1f, con_alpha, con_hvdc_idx


def formulate_generator_contingency(solver: pywraplp.Solver, ContingencyRates, Sbase, branch_names, generator_names,
                                    Cgen, Pgen, generation_contingency_threshold, PTDF, F, T, flow_f, monitor, alpha,
                                    logger: Logger):
    """
    Formulate the contingency flows
    :param solver: Solver instance to which add the equations
    :param ContingencyRates: array of branch contingency rates
    :param branch_names: array of branch names
    :param generator_names: Array of Generator names
    :param Cgen: CSC connectivity matrix of generators and buses [ngen, nbus]
    :param Pgen: Array of generator active power values in p.u.
    :param generation_contingency_threshold: Generation power threshold to consider as contingency (in MW)
    :param PTDF: PTDF matrix
    :param F: Array of branch "from" bus indices
    :param T: Array of branch "to" bus indices
    :param flow_f: Array of formulated branch flows (LP variblaes)
    :param monitor: Array of final monitor status per branch after applying the logic
    :param logger: logger instance
    :return:
        - flow_n1f: List of contingency flows LP variables
        - con_idx: list of accepted contingency monitored and failed indices [(monitored, failed), ...]
    """

    rates = ContingencyRates / Sbase
    mon_br_idx = np.where(monitor == True)[0]

    flow_gen_n1f = list()
    con_gen_idx = list()
    alpha_n1_list = list()

    generation_contingency_threshold_pu = generation_contingency_threshold / Sbase

    for j in range(Cgen.shape[1]):  # for each generator
        for ii in range(Cgen.indptr[j], Cgen.indptr[j + 1]):
            i = Cgen.indices[ii]  # bus index

            if Pgen[j] >= generation_contingency_threshold_pu:

                for m in mon_br_idx:  # for every monitored branch
                    _f = F[m]
                    _t = T[m]
                    suffix = "{0}@{1}_{2}@{3}".format(branch_names[m], generator_names[j], m, j)

                    flow_n1 = solver.NumVar(-rates[m], rates[m], 'gen_n-1_flow_' + suffix)

                    solver.Add(flow_n1 == flow_f[m] - PTDF[m, i] * generation_contingency_threshold_pu,
                               "gen_n-1_flow_assignment_" + suffix)

                    # store vars
                    con_gen_idx.append((m, j))
                    flow_gen_n1f.append(flow_n1)
                    alpha_n1_list.append(PTDF[m, i] - alpha[m])

    return flow_gen_n1f, alpha_n1_list, con_gen_idx

def formulate_objective(solver: pywraplp.Solver,
                        power_shift, gen_cost, generation_delta,
                        weight_power_shift, weight_generation_cost,
                        hvdc_angle_slack_pos, hvdc_angle_slack_neg,
                        logger: Logger):
    """

    :param solver: Solver instance to which add the equations
    :param power_shift: Array of branch phase shift angles (mix of values and LP variables)
    :param gen_cost: Array of generation costs
    :param generation_delta:  Array of generation delta LP variables
    :param weight_power_shift: Power shift maximization weight
    :param weight_generation_cost: Generation cost minimization weight
    :param logger: logger instance
    """

    # include the cost of generation
    gen_cost_f = solver.Sum(gen_cost * generation_delta)

    # formulate objective function
    f = -weight_power_shift * power_shift
    f += weight_generation_cost * gen_cost_f
    f += solver.Sum(hvdc_angle_slack_pos)
    f += solver.Sum(hvdc_angle_slack_neg)


    solver.Minimize(f)




class OpfNTC(Opf):

    def __init__(self, numerical_circuit: SnapshotOpfData,
                 area_from_bus_idx,
                 area_to_bus_idx,
                 alpha,
                 alpha_n1,
                 LODF,
                 PTDF,
                 solver_type: MIPSolvers = MIPSolvers.CBC,
                 generation_formulation: GenerationNtcFormulation = GenerationNtcFormulation.Proportional,
                 monitor_only_sensitive_branches=False,
                 monitor_only_ntc_load_rule_branches=False,
                 branch_sensitivity_threshold=0.05,
                 ntc_load_rule=0,
                 skip_generation_limits=True,
                 maximize_exchange_flows=True,
                 dispatch_all_areas=False,
                 tolerance=1e-2,
                 weight_power_shift=1e5,
                 weight_generation_cost=1e5,
                 consider_contingencies=True,
                 consider_hvdc_contingencies=True,
                 consider_gen_contingencies=True,
                 generation_contingency_threshold=1000,
                 match_gen_load=False,
                 force_exchange_sense=False,
                 logger: Logger = None):
        """
        DC time series linear optimal power flow
        :param numerical_circuit:  NumericalCircuit instance
        :param area_from_bus_idx:  indices of the buses of the area 1
        :param area_to_bus_idx: indices of the buses of the area 2
        :param alpha: Array of branch sensitivities to the exchange
        :param alpha_n1: Array of branch sensitivities to the exchange on n-1 condition
        :param LODF: LODF matrix
        :param solver_type: type of linear solver
        :param generation_formulation: type of generation formulation
        :param monitor_only_sensitive_branches: Monitor the loading of the sensitive branches
        :param monitor_only_sensitive_branches: Monitor the loading of branches over ntc load rule
        :param branch_sensitivity_threshold: branch sensitivity used to filter out the branches whose sensitivity is under the threshold
        :param ntc load rule
        :param skip_generation_limits: Skip the generation limits?
        :param consider_contingencies: Consider contingencies?
        :param maximize_exchange_flows: Maximize the exchange flow?
        :param tolerance: Solution tolerance
        :param weight_power_shift: Power shift maximization weight
        :param weight_generation_cost: Generation cost minimization weight
        :param match_gen_load: Boolean to match generation and load power
        :param logger: logger instance
        """

        self.area_from_bus_idx = area_from_bus_idx

        self.area_to_bus_idx = area_to_bus_idx

        self.generation_formulation = generation_formulation

        self.monitor_only_sensitive_branches = monitor_only_sensitive_branches

        self.monitor_only_ntc_load_rule_branches = monitor_only_ntc_load_rule_branches

        self.branch_sensitivity_threshold = branch_sensitivity_threshold

        self.skip_generation_limits = skip_generation_limits

        self.maximize_exchange_flows = maximize_exchange_flows

        self.dispatch_all_areas = dispatch_all_areas

        self.tolerance = tolerance

        self.alpha = alpha
        self.alpha_n1 = alpha_n1
        self.ntc_load_rule = ntc_load_rule

        self.LODF = LODF

        self.PTDF = PTDF

        self.consider_contingencies = consider_contingencies
        self.consider_hvdc_contingencies = consider_hvdc_contingencies
        self.consider_gen_contingencies = consider_gen_contingencies
        self.generation_contingency_threshold = generation_contingency_threshold

        self.weight_power_shift = weight_power_shift
        self.weight_generation_cost = weight_generation_cost

        self.match_gen_load = match_gen_load
        self.force_exchange_sense = force_exchange_sense

        self.inf = 99999999999999

        # results
        self.gen_a1_idx = None
        self.gen_a2_idx = None
        self.Pg_delta = None
        self.Pinj = None
        self.hvdc_flow = None
        self.phase_shift = None
        self.inter_area_branches = None
        self.inter_area_hvdc = None
        self.hvdc_angle_slack_pos = None
        self.hvdc_angle_slack_neg = None
        self.monitor = None

        self.contingency_gen_flows_list = list()
        self.contingency_gen_indices_list = list()  # [(m, c), ...]
        self.contingency_hvdc_flows_list = list()
        self.contingency_hvdc_indices_list = list()  # [(m, c), ...]

        self.structural_ntc = 0

        self.logger = logger

        # this builds the formulation right away
        Opf.__init__(self, numerical_circuit=numerical_circuit,
                     solver_type=solver_type,
                     ortools=True)

    def scale_to_reference(self, reference, scalable):

        delta = np.sum(reference) - np.sum(scalable)

        positive = scalable * (scalable > 0)
        negative = scalable * (scalable < 0)

        # proportion of delta to increase and to decrease
        prop_up = np.sum(positive) / np.sum(np.abs(scalable))
        prop_dw = np.sum(negative) / np.sum(np.abs(scalable))

        delta_up = delta * prop_up
        delta_dw = delta * prop_dw

        # proportion of value to increase and to
        sum_pos = np.sum(positive)
        sum_neg = np.sum(negative)
        prop_up = delta_up / sum_pos if sum_pos != 0 else 0
        prop_dw = delta_dw / sum_neg if sum_neg != 0 else 0

        # scale
        positive *= (1 + prop_up)
        negative *= (1 - prop_dw)

        # join
        scalable = positive + negative

        return scalable

    def formulate(self):
        """
        Formulate the Net Transfer Capacity problem
        :return:
        """

        self.inf = self.solver.infinity()

        # time index
        t = 0

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
        Pgen_orig = self.numerical_circuit.generator_data.get_effective_generation()[:, t] / Sbase
        Cgen = self.numerical_circuit.generator_data.C_bus_gen.tocsc()

        if self.skip_generation_limits:
            Pg_max = self.inf * np.ones(self.numerical_circuit.ngen)
            Pg_min = -self.inf * np.ones(self.numerical_circuit.ngen)

        # load
        Pload = self.numerical_circuit.load_data.get_effective_load().real[:, t] / Sbase

        if self.match_gen_load:
            Pgen = self.scale_to_reference(reference=Pload, scalable=Pgen_orig)
        else:
            Pgen = Pgen_orig

        # branch
        branch_ratings = self.numerical_circuit.branch_rates / Sbase
        hvdc_ratings = self.numerical_circuit.hvdc_data.rate / Sbase

        alpha_abs = np.abs(self.alpha)
        alpha_n1_abs = np.abs(self.alpha_n1)

        # --------------------------------------------------------------------------------------------------------------
        # Formulate the problem
        # --------------------------------------------------------------------------------------------------------------

        load_cost = self.numerical_circuit.load_data.load_cost[:, t]

        # get the inter-area branches and their sign
        inter_area_branches = get_inter_areas_branches(
            nbr=m,
            F=self.numerical_circuit.branch_data.F,
            T=self.numerical_circuit.branch_data.T,
            buses_areas_1=self.area_from_bus_idx,
            buses_areas_2=self.area_to_bus_idx)

        inter_area_hvdc = get_inter_areas_branches(
            nbr=self.numerical_circuit.nhvdc,
            F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
            T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
            buses_areas_1=self.area_from_bus_idx,
            buses_areas_2=self.area_to_bus_idx)

        structural_ntc = get_structural_ntc(inter_area_branches, inter_area_hvdc, branch_ratings, hvdc_ratings)

        # formulate the generation
        if self.generation_formulation == GenerationNtcFormulation.Optimal:

            generation, generation_delta, gen_a1_idx, gen_a2_idx, power_shift, dgen1, \
            gen_cost = formulate_optimal_generation(
                solver=self.solver,
                generator_active=self.numerical_circuit.generator_data.active[:, t],
                dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                generator_cost=self.numerical_circuit.generator_data.generator_cost[:, t],
                generator_names=self.numerical_circuit.generator_data.names,
                Sbase=self.numerical_circuit.Sbase,
                inf=self.inf,
                ngen=ng,
                Cgen=Cgen,
                Pgen=Pgen,
                Pmax=Pg_max,
                Pmin=Pg_min,
                a1=self.area_from_bus_idx,
                a2=self.area_to_bus_idx,
                dispatch_all_areas=self.dispatch_all_areas,
                logger=self.logger)

        elif self.generation_formulation == GenerationNtcFormulation.Proportional:

            generation, generation_delta, gen_a1_idx, gen_a2_idx, power_shift, \
            gen_cost = formulate_proportional_generation(
                solver=self.solver,
                generator_active=self.numerical_circuit.generator_data.active[:, t],
                generator_dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                generator_cost=self.numerical_circuit.generator_data.generator_cost[:, t],
                generator_names=self.numerical_circuit.generator_data.names,
                inf=self.inf,
                ngen=ng,
                Cgen=Cgen,
                Pgen=Pgen,
                Pmax=Pg_max,
                Pmin=Pg_min,
                a1=self.area_from_bus_idx,
                a2=self.area_to_bus_idx,
                logger=self.logger)

            load_cost = np.ones(self.numerical_circuit.nload)

        else:
            raise Exception('Unknown generation mode')


        # formulate the power injections
        Pinj = formulate_power_injections(
            solver=self.solver,
            Cgen=Cgen,
            generation=generation,
            Cload=self.numerical_circuit.load_data.C_bus_load,
            load_power=Pload,
            logger=self.logger)

        # add the angles
        theta = formulate_angles(
            solver=self.solver,
            nbus=self.numerical_circuit.nbus,
            vd=self.numerical_circuit.vd,
            bus_names=self.numerical_circuit.bus_data.names,
            angle_min=self.numerical_circuit.bus_data.angle_min,
            angle_max=self.numerical_circuit.bus_data.angle_max,
            logger=self.logger)

        # add shifter angles
        tau = formulate_angles_shifters(
            solver=self.solver,
            nbr=self.numerical_circuit.nbr,
            branch_active=self.numerical_circuit.branch_active,
            branch_names=self.numerical_circuit.branch_names,
            branch_theta=self.numerical_circuit.branch_data.theta[:, t],
            branch_theta_min=self.numerical_circuit.branch_data.theta_min,
            branch_theta_max=self.numerical_circuit.branch_data.theta_max,
            control_mode=self.numerical_circuit.branch_data.control_mode,
            logger=self.logger)

        # formulate the flows
        flow_f, monitor, Pinj_tau, branch_ntc_load_rule = formulate_branches_flow(
            solver=self.solver,
            nbr=self.numerical_circuit.nbr,
            nbus=self.numerical_circuit.nbus,
            Rates=self.numerical_circuit.Rates,
            Sbase=self.numerical_circuit.Sbase,
            branch_active=self.numerical_circuit.branch_active,
            branch_names=self.numerical_circuit.branch_names,
            branch_dc=self.numerical_circuit.branch_data.dc,
            R=self.numerical_circuit.branch_data.R,
            X=self.numerical_circuit.branch_data.X,
            F=self.numerical_circuit.F,
            T=self.numerical_circuit.T,
            angles=theta,
            tau=tau,
            inf=self.inf,
            monitor_loading=self.numerical_circuit.branch_data.monitor_loading,
            branch_sensitivity_threshold=self.branch_sensitivity_threshold,
            monitor_only_sensitive_branches=self.monitor_only_sensitive_branches,
            alpha_abs=alpha_abs,
            alpha_n1_abs=alpha_n1_abs,
            monitor_only_ntc_load_rule_branches=self.monitor_only_ntc_load_rule_branches,
            cep_rule=self.ntc_load_rule,
            structural_ntc=structural_ntc,
            logger=self.logger)

        # formulate the HVDC flows
        hvdc_flow_f, hvdc_angle_slack_pos, hvdc_angle_slack_neg = formulate_hvdc_flow(
            solver=self.solver,
            nhvdc=self.numerical_circuit.nhvdc,
            names=self.numerical_circuit.hvdc_names,
            rate=self.numerical_circuit.hvdc_data.rate[:, t],
            angles=theta,
            hvdc_active=self.numerical_circuit.hvdc_data.active[:, t],
            Pt=self.numerical_circuit.hvdc_data.Pset[:, t],
            angle_droop=self.numerical_circuit.hvdc_data.get_angle_droop_in_pu_rad(Sbase)[:, t],
            control_mode=self.numerical_circuit.hvdc_data.control_mode,
            dispatchable=self.numerical_circuit.hvdc_data.dispatchable,
            F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
            T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
            Pinj=Pinj,
            Sbase=self.numerical_circuit.Sbase,
            inf=self.inf,
            inter_area_hvdc=inter_area_hvdc,
            force_exchange_sense=self.force_exchange_sense,
            logger=self.logger)

        # formulate the node power balance
        node_balance = formulate_node_balance(
            solver=self.solver,
            Bbus=self.numerical_circuit.Bbus,
            angles=theta,
            Pinj=Pinj - Pinj_tau,
            bus_active=self.numerical_circuit.bus_data.active[:, t],
            bus_names=self.numerical_circuit.bus_data.names,
            logger=self.logger)

        if self.consider_contingencies:
            # formulate the contingencies
            n1flow_f, con_br_alpha, con_br_idx = formulate_contingency(
                solver=self.solver,
                ContingencyRates=self.numerical_circuit.ContingencyRates,
                Sbase=self.numerical_circuit.Sbase,
                branch_names=self.numerical_circuit.branch_names,
                contingency_enabled_indices=self.numerical_circuit.branch_data.get_contingency_enabled_indices(),
                LODF=self.LODF,
                F=self.numerical_circuit.F,
                T=self.numerical_circuit.T,
                branch_sensitivity_threshold=self.branch_sensitivity_threshold,
                flow_f=flow_f,
                monitor=monitor,
                alpha_n1=self.alpha_n1,
                lodf_replacement_value=0,
                logger=self.logger)

        else:
            con_br_idx = list()
            n1flow_f = list()
            con_br_alpha = list()

        if self.consider_gen_contingencies and self.generation_contingency_threshold != 0:
            # formulate the generator contingencies
            n1flow_gen_f, con_gen_alpha, con_gen_idx = formulate_generator_contingency(
                solver=self.solver,
                ContingencyRates=self.numerical_circuit.ContingencyRates,
                Sbase=self.numerical_circuit.Sbase,
                branch_names=self.numerical_circuit.branch_names,
                generator_names=self.numerical_circuit.generator_data.names,
                Cgen=Cgen,
                Pgen=Pgen,
                generation_contingency_threshold=self.generation_contingency_threshold,
                PTDF=self.PTDF,
                F=self.numerical_circuit.F,
                T=self.numerical_circuit.T,
                flow_f=flow_f,
                monitor=monitor,
                alpha=self.alpha,
                logger=self.logger)
        else:
            n1flow_gen_f = list()
            con_gen_idx = list()
            con_gen_alpha = list()

        if self.consider_hvdc_contingencies:
            # formulate the hvdc contingencies
            n1flow_hvdc_f, con_hvdc_alpha, con_hvdc_idx = formulate_hvdc_contingency(
                solver=self.solver,
                ContingencyRates=self.numerical_circuit.ContingencyRates,
                Sbase=self.numerical_circuit.Sbase,
                hvdc_flow_f=hvdc_flow_f,
                hvdc_active=self.numerical_circuit.hvdc_data.active[:, t],
                PTDF=self.PTDF,
                F=self.numerical_circuit.F,
                T=self.numerical_circuit.T,
                F_hvdc=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
                T_hvdc=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
                flow_f=flow_f,
                monitor=monitor,
                alpha=self.alpha,
                logger=self.logger)
        else:
            n1flow_hvdc_f = list()
            con_hvdc_idx = list()
            con_hvdc_alpha = list()

        # formulate the objective
        formulate_objective(
            solver=self.solver,
            power_shift=power_shift,
            gen_cost=gen_cost[gen_a1_idx],
            generation_delta=generation_delta[gen_a1_idx],
            weight_power_shift=self.weight_power_shift,
            weight_generation_cost=self.weight_generation_cost,
            hvdc_angle_slack_pos=hvdc_angle_slack_pos,
            hvdc_angle_slack_neg=hvdc_angle_slack_neg,
            logger=self.logger)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta
        self.Pg = generation
        self.Pg_delta = generation_delta
        self.power_shift = power_shift

        self.gen_a1_idx = gen_a1_idx
        self.gen_a2_idx = gen_a2_idx

        self.monitor = monitor

        # self.Pb = Pb
        self.Pl = Pload
        self.Pinj = Pinj

        self.s_from = flow_f
        self.s_to = - flow_f
        self.n1flow_f = n1flow_f
        self.contingency_br_idx = con_br_idx

        self.hvdc_flow = hvdc_flow_f

        self.n1flow_gen_f = n1flow_gen_f
        self.con_gen_idx = con_gen_idx
        self.n1flow_hvdc_f = n1flow_hvdc_f
        self.con_hvdc_idx = con_hvdc_idx

        self.rating = branch_ratings
        self.phase_shift = tau
        self.nodal_restrictions = node_balance

        self.inter_area_branches = inter_area_branches
        self.inter_area_hvdc = inter_area_hvdc

        self.hvdc_angle_slack_pos = hvdc_angle_slack_pos
        self.hvdc_angle_slack_neg = hvdc_angle_slack_neg

        self.branch_ntc_load_rule = branch_ntc_load_rule

        # n1flow_f, con_br_idx
        self.contingency_flows_list = n1flow_f
        self.contingency_indices_list = con_br_idx  # [(t, m, c), ...]
        self.contingency_gen_flows_list = n1flow_gen_f
        self.contingency_gen_indices_list = con_gen_idx  # [(m, c), ...]
        self.contingency_hvdc_flows_list = n1flow_hvdc_f
        self.contingency_hvdc_indices_list = con_hvdc_idx  # [(m, c), ...]

        self.contingency_branch_alpha_list = con_br_alpha
        self.contingency_hvdc_alpha_list = con_hvdc_alpha
        self.contingency_generation_alpha_list = con_gen_alpha

        self.structural_ntc = structural_ntc

        return self.solver

    def formulate_ts(self, t=0):
        """
        Formulate the Net Transfer Capacity problem
        :param t: time index
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
        cost_b = self.numerical_circuit.battery_cost[:, t]
        Cbat = self.numerical_circuit.battery_data.C_bus_batt.tocsc()

        # generator
        Pg_max = self.numerical_circuit.generator_pmax / Sbase
        Pg_min = self.numerical_circuit.generator_pmin / Sbase
        Pgen_orig = self.numerical_circuit.generator_data.get_effective_generation()[:, t] / Sbase
        Cgen = self.numerical_circuit.generator_data.C_bus_gen.tocsc()

        if self.skip_generation_limits:
            Pg_max = self.inf * np.ones(self.numerical_circuit.ngen)
            Pg_min = -self.inf * np.ones(self.numerical_circuit.ngen)

        # load
        Pload = self.numerical_circuit.load_data.get_effective_load().real[:, t] / Sbase

        if self.match_gen_load:
            Pgen = self.scale_to_reference(reference=Pload, scalable=Pgen_orig)
        else:
            Pgen = Pgen_orig

        # branch
        branch_ratings = self.numerical_circuit.branch_rates[:, t] / Sbase
        hvdc_ratings = self.numerical_circuit.hvdc_data.rate[:, t] / Sbase
        alpha_abs = np.abs(self.alpha)
        alpha_n1_abs = np.abs(self.alpha_n1)

        # --------------------------------------------------------------------------------------------------------------
        # Formulate the problem
        # --------------------------------------------------------------------------------------------------------------

        load_cost = self.numerical_circuit.load_data.load_cost[:, t]

        # get the inter-area branches and their sign
        inter_area_branches = get_inter_areas_branches(
            nbr=m,
            F=self.numerical_circuit.branch_data.F,
            T=self.numerical_circuit.branch_data.T,
            buses_areas_1=self.area_from_bus_idx,
            buses_areas_2=self.area_to_bus_idx)

        inter_area_hvdc = get_inter_areas_branches(
            nbr=self.numerical_circuit.nhvdc,
            F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
            T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
            buses_areas_1=self.area_from_bus_idx,
            buses_areas_2=self.area_to_bus_idx)

        structural_ntc = get_structural_ntc(
            inter_area_branches=inter_area_branches,
            inter_area_hvdc=inter_area_hvdc,
            branch_ratings=branch_ratings,
            hvdc_ratings=hvdc_ratings)

        # formulate the generation
        if self.generation_formulation == GenerationNtcFormulation.Optimal:

            generation, generation_delta, gen_a1_idx, gen_a2_idx, power_shift, dgen1, \
            gen_cost = formulate_optimal_generation(
                solver=self.solver,
                generator_active=self.numerical_circuit.generator_data.active[:, t],
                dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                generator_cost=self.numerical_circuit.generator_data.generator_cost[:, t],
                generator_names=self.numerical_circuit.generator_data.names,
                Sbase=self.numerical_circuit.Sbase,
                inf=self.inf,
                ngen=ng,
                Cgen=Cgen,
                Pgen=Pgen,
                Pmax=Pg_max,
                Pmin=Pg_min,
                a1=self.area_from_bus_idx,
                a2=self.area_to_bus_idx,
                dispatch_all_areas=self.dispatch_all_areas,
                logger=self.logger)

        elif self.generation_formulation == GenerationNtcFormulation.Proportional:

            generation, generation_delta, gen_a1_idx, gen_a2_idx, power_shift, \
            gen_cost = formulate_proportional_generation(
                solver=self.solver,
                generator_active=self.numerical_circuit.generator_data.active[:, t],
                generator_dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                generator_cost=self.numerical_circuit.generator_data.generator_cost[:, t],
                generator_names=self.numerical_circuit.generator_data.names,
                inf=self.inf,
                ngen=ng,
                Cgen=Cgen,
                Pgen=Pgen,
                Pmax=Pg_max,
                Pmin=Pg_min,
                a1=self.area_from_bus_idx,
                a2=self.area_to_bus_idx,
                logger=self.logger)

            load_cost = np.ones(self.numerical_circuit.nload)

        else:
            raise Exception('Unknown generation mode')

        # formulate the power injections
        Pinj = formulate_power_injections(
            solver=self.solver,
            Cgen=Cgen,
            generation=generation,
            Cload=self.numerical_circuit.load_data.C_bus_load,
            load_power=Pload,
            logger=self.logger)


        # add the angles
        theta = formulate_angles(
            solver=self.solver,
            nbus=self.numerical_circuit.nbus,
            vd=self.numerical_circuit.vd,
            bus_names=self.numerical_circuit.bus_data.names,
            angle_min=self.numerical_circuit.bus_data.angle_min,
            angle_max=self.numerical_circuit.bus_data.angle_max,
            logger=self.logger)

        # update angles with the shifter effect
        tau = formulate_angles_shifters(
            solver=self.solver,
            nbr=self.numerical_circuit.nbr,
            branch_active=self.numerical_circuit.branch_active[:, t],
            branch_names=self.numerical_circuit.branch_names,
            branch_theta=self.numerical_circuit.branch_data.theta[:, t],
            branch_theta_min=self.numerical_circuit.branch_data.theta_min,
            branch_theta_max=self.numerical_circuit.branch_data.theta_max,
            control_mode=self.numerical_circuit.branch_data.control_mode,
            logger=self.logger)

        # formulate the flows
        flow_f, monitor, Pinj_tau, branch_ntc_load_rule = formulate_branches_flow(
            solver=self.solver,
            nbr=self.numerical_circuit.nbr,
            nbus=self.numerical_circuit.nbus,
            Rates=self.numerical_circuit.Rates[:, t],
            Sbase=self.numerical_circuit.Sbase,
            branch_active=self.numerical_circuit.branch_active[:, t],
            branch_names=self.numerical_circuit.branch_names,
            branch_dc=self.numerical_circuit.branch_data.dc,
            R=self.numerical_circuit.branch_data.R,
            X=self.numerical_circuit.branch_data.X,
            F=self.numerical_circuit.F,
            T=self.numerical_circuit.T,
            angles=theta,
            tau=tau,
            inf=self.inf,
            monitor_loading=self.numerical_circuit.branch_data.monitor_loading,
            branch_sensitivity_threshold=self.branch_sensitivity_threshold,
            monitor_only_sensitive_branches=self.monitor_only_sensitive_branches,
            alpha_abs=alpha_abs,
            alpha_n1_abs=alpha_n1_abs,
            monitor_only_ntc_load_rule_branches=self.monitor_only_ntc_load_rule_branches,
            cep_rule=self.ntc_load_rule,
            structural_ntc=structural_ntc,
            logger=self.logger)


        # formulate the HVDC flows
        hvdc_flow_f, hvdc_angle_slack_pos, hvdc_angle_slack_neg = formulate_hvdc_flow(
            solver=self.solver,
            nhvdc=self.numerical_circuit.nhvdc,
            names=self.numerical_circuit.hvdc_names,
            rate=self.numerical_circuit.hvdc_data.rate[:, t],
            angles=theta,
            hvdc_active=self.numerical_circuit.hvdc_data.active[:, t],
            Pt=self.numerical_circuit.hvdc_data.Pset[:, t],
            angle_droop=self.numerical_circuit.hvdc_data.get_angle_droop_in_pu_rad(Sbase)[:, t],
            control_mode=self.numerical_circuit.hvdc_data.control_mode,
            dispatchable=self.numerical_circuit.hvdc_data.dispatchable,
            F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
            T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
            Pinj=Pinj,
            Sbase=self.numerical_circuit.Sbase,
            inf=self.inf,
            inter_area_hvdc=inter_area_hvdc,
            force_exchange_sense=self.force_exchange_sense,
            logger=self.logger)


        # formulate the node power balance
        node_balance = formulate_node_balance(
            solver=self.solver,
            Bbus=self.numerical_circuit.Bbus,
            angles=theta,
            Pinj=Pinj - Pinj_tau,
            bus_active=self.numerical_circuit.bus_data.active[:, t],
            bus_names=self.numerical_circuit.bus_data.names,
            logger=self.logger)


        if self.consider_contingencies:
            # formulate the contingencies
            n1flow_f, con_brn_alpha, con_br_idx = formulate_contingency(
                solver=self.solver,
                ContingencyRates=self.numerical_circuit.ContingencyRates[:, t],
                Sbase=self.numerical_circuit.Sbase,
                branch_names=self.numerical_circuit.branch_names,
                contingency_enabled_indices=self.numerical_circuit.branch_data.get_contingency_enabled_indices(),
                LODF=self.LODF,
                F=self.numerical_circuit.F,
                T=self.numerical_circuit.T,
                branch_sensitivity_threshold=self.branch_sensitivity_threshold,
                flow_f=flow_f,
                monitor=monitor,
                lodf_replacement_value=0,
                alpha_n1=self.alpha_n1,
                logger=self.logger)

        else:
            con_br_idx = list()
            n1flow_f = list()
            alpha_n1_list = list()

        if self.consider_gen_contingencies and self.generation_contingency_threshold != 0:
            # formulate the generator contingencies
            n1flow_gen_f, con_gen_alpha, con_gen_idx = formulate_generator_contingency(
                solver=self.solver,
                ContingencyRates=self.numerical_circuit.ContingencyRates[:, t],
                Sbase=self.numerical_circuit.Sbase,
                branch_names=self.numerical_circuit.branch_names,
                generator_names=self.numerical_circuit.generator_data.names,
                Cgen=Cgen,
                Pgen=Pgen,
                generation_contingency_threshold=self.generation_contingency_threshold,
                PTDF=self.PTDF,
                F=self.numerical_circuit.F,
                T=self.numerical_circuit.T,
                flow_f=flow_f,
                monitor=monitor,
                alpha=self.alpha,
                logger=self.logger)
        else:
            n1flow_gen_f = list()
            con_gen_idx = list()

        if self.consider_hvdc_contingencies:
            # formulate the hvdc contingencies
            n1flow_hvdc_f, con_hvdc_alpha, con_hvdc_idx = formulate_hvdc_contingency(
                solver=self.solver,
                ContingencyRates=self.numerical_circuit.ContingencyRates[:, t],
                Sbase=self.numerical_circuit.Sbase,
                hvdc_flow_f=hvdc_flow_f,
                hvdc_active=self.numerical_circuit.hvdc_data.active[:, t],
                PTDF=self.PTDF,
                F=self.numerical_circuit.F,
                T=self.numerical_circuit.T,
                F_hvdc=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
                T_hvdc=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
                flow_f=flow_f,
                monitor=monitor,
                alpha=self.alpha,
                logger=self.logger)
        else:
            n1flow_hvdc_f = list()
            con_hvdc_idx = list()

        # formulate the objective
        formulate_objective(
            solver=self.solver,
            power_shift=power_shift,
            gen_cost=gen_cost[gen_a1_idx],
            generation_delta=generation_delta[gen_a1_idx],
            weight_power_shift=self.weight_power_shift,
            weight_generation_cost=self.weight_generation_cost,
            hvdc_angle_slack_pos=hvdc_angle_slack_pos,
            hvdc_angle_slack_neg=hvdc_angle_slack_neg,
            logger=self.logger)

        # Assign variables to keep
        # transpose them to be in the format of GridCal: time, device
        self.theta = theta
        self.Pg = generation
        self.Pg_delta = generation_delta
        self.power_shift = power_shift

        self.gen_a1_idx = gen_a1_idx
        self.gen_a2_idx = gen_a2_idx

        self.monitor = monitor

        # self.Pb = Pb
        self.Pl = Pload
        self.Pinj = Pinj

        self.s_from = flow_f
        self.s_to = - flow_f
        self.n1flow_f = n1flow_f
        self.contingency_br_idx = con_br_idx

        self.hvdc_flow = hvdc_flow_f

        self.n1flow_gen_f = n1flow_gen_f
        self.con_gen_idx = con_gen_idx
        self.n1flow_hvdc_f = n1flow_hvdc_f
        self.con_hvdc_idx = con_hvdc_idx

        self.rating = branch_ratings
        self.phase_shift = tau
        self.nodal_restrictions = node_balance

        self.inter_area_branches = inter_area_branches
        self.inter_area_hvdc = inter_area_hvdc

        self.hvdc_angle_slack_pos = hvdc_angle_slack_pos
        self.hvdc_angle_slack_neg = hvdc_angle_slack_neg

        self.branch_ntc_load_rule = branch_ntc_load_rule

        # n1flow_f, con_br_idx
        self.contingency_flows_list = n1flow_f
        self.contingency_indices_list = con_br_idx  # [(t, m, c), ...]
        self.contingency_gen_flows_list = n1flow_gen_f
        self.contingency_gen_indices_list = con_gen_idx  # [(t, m, c), ...]
        self.contingency_hvdc_flows_list = n1flow_hvdc_f
        self.contingency_hvdc_indices_list = con_hvdc_idx  # [(t, m, c), ...]

        self.contingency_branch_alpha_list = con_brn_alpha
        self.contingency_generation_alpha_list = con_gen_alpha
        self.contingency_hvdc_alpha_list = con_hvdc_alpha

        return self.solver

    def check(self):
        """
        Formulate the Net Transfer Capacity problem
        :return:
        """
        # time index
        t = 0

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
        Pg_fix = self.numerical_circuit.generator_data.get_effective_generation()[:, t] / Sbase
        Pg_max = self.numerical_circuit.generator_pmax / Sbase
        Cgen = self.numerical_circuit.generator_data.C_bus_gen.tocsc()

        if self.skip_generation_limits:
            Pg_max = self.inf * np.ones(self.numerical_circuit.ngen)
            Pg_min = -self.inf * np.ones(self.numerical_circuit.ngen)

        # load
        Pl_fix = self.numerical_circuit.load_data.get_effective_load().real[:, t] / Sbase

        # branch
        alpha_abs = np.abs(self.alpha)

        # check variables
        for var in self.solver.variables():

            if var.solution_value() > var.Ub():
                self.logger.add_divergence(
                    'Variable over the upper bound', var.name(), var.solution_value(), var.Ub())
            if var.solution_value() < var.Lb():
                self.logger.add_divergence(
                    'Variable under the lower bound', var.name(), var.solution_value(), var.Lb())

        # formulate the generation
        if self.generation_formulation == GenerationNtcFormulation.Optimal:

            check_optimal_generation(
                generator_active=self.numerical_circuit.generator_data.active[:, t],
                dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                generator_names=self.numerical_circuit.generator_data.names,
                Cgen=Cgen,
                Pgen=Pg_fix,
                a1=self.area_from_bus_idx,
                a2=self.area_to_bus_idx,
                generation=self.extract(self.Pg),
                delta=self.extract(self.Pg_delta),
                logger=self.logger)

        elif self.generation_formulation == GenerationNtcFormulation.Proportional:

            check_proportional_generation(
                generator_active=self.numerical_circuit.generator_data.active[:, t],
                generator_dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                generator_cost=self.numerical_circuit.generator_data.generator_cost[:, t],
                generator_names=self.numerical_circuit.generator_data.names,
                Sbase=self.numerical_circuit.Sbase,
                Cgen=Cgen,
                Pgen=Pg_fix,
                Pmax=Pg_max,
                Pmin=Pg_min,
                a1=self.area_from_bus_idx,
                a2=self.area_to_bus_idx,
                generation=self.extract(self.Pg),
                delta=self.extract(self.Pg_delta),
                power_shift=self.power_shift.solution_value(),
                logger=self.logger
            )
        else:
            raise Exception('Unknown generation mode')

        monitor = check_branches_flow(
            nbr=self.numerical_circuit.nbr,
            Rates=self.numerical_circuit.Rates,
            Sbase=self.numerical_circuit.Sbase,
            branch_active=self.numerical_circuit.branch_active,
            branch_names=self.numerical_circuit.branch_names,
            branch_dc=self.numerical_circuit.branch_data.dc,
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

        check_contingency(
            ContingencyRates=self.numerical_circuit.ContingencyRates,
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

        check_hvdc_flow(
            nhvdc=self.numerical_circuit.nhvdc,
            names=self.numerical_circuit.hvdc_names,
            rate=self.numerical_circuit.hvdc_data.rate[:, t],
            angles=self.extract(self.theta),
            hvdc_active=self.numerical_circuit.hvdc_data.active[:, t],
            Pt=self.numerical_circuit.hvdc_data.Pset[:, t],
            angle_droop=self.numerical_circuit.hvdc_data.get_angle_droop_in_pu_rad(Sbase)[:, t],
            control_mode=self.numerical_circuit.hvdc_data.control_mode,
            dispatchable=self.numerical_circuit.hvdc_data.dispatchable,
            F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
            T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
            Sbase=self.numerical_circuit.Sbase,
            flow_f=self.extract(self.hvdc_flow),
            logger=self.logger)

        Pinj = check_power_injections(
            load_power=Pl_fix,
            Cgen=Cgen,
            generation=self.extract(self.Pg),
            Cload=self.numerical_circuit.load_data.C_bus_load)

        check_node_balance(
            Bbus=self.numerical_circuit.Bbus,
            angles=self.extract(self.theta),
            Pinj=Pinj,
            bus_active=self.numerical_circuit.bus_data.active[:, t],
            bus_names=self.numerical_circuit.bus_data.names,
            logger=self.logger)

    def check_ts(self, t=0):
        """
        Formulate the Net Transfer Capacity problem
        param t: time index
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
        Pg_fix = self.numerical_circuit.generator_data.get_effective_generation()[:, t] / Sbase
        Pg_max = self.numerical_circuit.generator_pmax / Sbase
        Cgen = self.numerical_circuit.generator_data.C_bus_gen.tocsc()

        if self.skip_generation_limits:
            Pg_max = self.inf * np.ones(self.numerical_circuit.ngen)
            Pg_min = -self.inf * np.ones(self.numerical_circuit.ngen)

        # load
        Pl_fix = self.numerical_circuit.load_data.get_effective_load().real[:, t] / Sbase

        # branch
        alpha_abs = np.abs(self.alpha)

        # check that the slacks are 0
        if self.all_slacks is not None:
            for var_array in self.all_slacks:
                for var in var_array:
                    if isinstance(var, float) or isinstance(var, int):
                        val = var
                    else:
                        val = var.solution_value()

                    if abs(val) > 0:
                        self.logger.add_divergence(
                            'Slack variable is over the tolerance', var.name(), val, 0)

        # check variables
        for var in self.solver.variables():

            if var.solution_value() > var.Ub():
                self.logger.add_divergence(
                    'Variable over the upper bound', var.name(), var.solution_value(), var.Ub())
            if var.solution_value() < var.Lb():
                self.logger.add_divergence(
                    'Variable under the lower bound', var.name(), var.solution_value(), var.Lb())

        # formulate the generation
        if self.generation_formulation == GenerationNtcFormulation.Optimal:

            check_optimal_generation(
                generator_active=self.numerical_circuit.generator_data.active[:, t],
                dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                generator_names=self.numerical_circuit.generator_data.names,
                Cgen=Cgen,
                Pgen=Pg_fix,
                a1=self.area_from_bus_idx,
                a2=self.area_to_bus_idx,
                generation=self.extract(self.Pg),
                delta=self.extract(self.Pg_delta),
                logger=self.logger)

        elif self.generation_formulation == GenerationNtcFormulation.Proportional:

            check_proportional_generation(
                generator_active=self.numerical_circuit.generator_data.active[:, t],
                generator_dispatchable=self.numerical_circuit.generator_data.generator_dispatchable,
                generator_cost=self.numerical_circuit.generator_data.generator_cost[:, t],
                generator_names=self.numerical_circuit.generator_data.names,
                Sbase=self.numerical_circuit.Sbase,
                Cgen=Cgen,
                Pgen=Pg_fix,
                Pmax=Pg_max,
                Pmin=Pg_min,
                a1=self.area_from_bus_idx,
                a2=self.area_to_bus_idx,
                generation=self.extract(self.Pg),
                delta=self.extract(self.Pg_delta),
                power_shift=self.power_shift.solution_value(),
                logger=self.logger
            )
        else:
            raise Exception('Unknown generation mode')

        monitor = check_branches_flow(
            nbr=self.numerical_circuit.nbr,
            Rates=self.numerical_circuit.Rates[:, t],
            Sbase=self.numerical_circuit.Sbase,
            branch_active=self.numerical_circuit.branch_active[:, t],
            branch_names=self.numerical_circuit.branch_names,
            branch_dc=self.numerical_circuit.branch_data.dc,
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

        check_contingency(
            ContingencyRates=self.numerical_circuit.ContingencyRates[:, t],
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

        check_hvdc_flow(
            nhvdc=self.numerical_circuit.nhvdc,
            names=self.numerical_circuit.hvdc_names,
            rate=self.numerical_circuit.hvdc_data.rate[:, t],
            angles=self.extract(self.theta),
            hvdc_active=self.numerical_circuit.hvdc_data.active[:, t],
            Pt=self.numerical_circuit.hvdc_data.Pset[:, t],
            angle_droop=self.numerical_circuit.hvdc_data.get_angle_droop_in_pu_rad(Sbase)[:, t],
            control_mode=self.numerical_circuit.hvdc_data.control_mode,
            dispatchable=self.numerical_circuit.hvdc_data.dispatchable,
            F=self.numerical_circuit.hvdc_data.get_bus_indices_f(),
            T=self.numerical_circuit.hvdc_data.get_bus_indices_t(),
            Sbase=self.numerical_circuit.Sbase,
            flow_f=self.extract(self.hvdc_flow),
            logger=self.logger)

        Pinj = check_power_injections(
            load_power=Pl_fix,
            Cgen=Cgen,
            generation=self.extract(self.Pg),
            Cload=self.numerical_circuit.load_data.C_bus_load)

        check_node_balance(
            Bbus=self.numerical_circuit.Bbus,
            angles=self.extract(self.theta),
            Pinj=Pinj,
            bus_active=self.numerical_circuit.bus_data.active[:, t],
            bus_names=self.numerical_circuit.bus_data.names,
            logger=self.logger)

    def save_lp(self, file_name="ntc_opf_problem.lp"):
        """
        Save problem in LP format
        :param file_name: name of the file (.lp or .mps supported)
        """
        save_lp(self.solver, file_name)

    def solve(self, with_solution_checks=True, time_limit_ms=0):
        """
        Call ORTools to solve the problem
        """
        if time_limit_ms != 0:
            self.solver.set_time_limit(int(time_limit_ms))

        self.status = self.solver.Solve()

        solved = self.solved()

        # check the solution
        self.save_lp('snp_ntc_opf.lp')
        if not solved and with_solution_checks:
            self.check()

        return solved

    def solve_ts(self, t, with_check=True, time_limit_ms=0):
        """
        Call ORTools to solve the problem
        """
        if time_limit_ms != 0:
            self.solver.set_time_limit(int(time_limit_ms))

        self.status = self.solver.Solve()

        solved = self.solved()


        # check the solution
        if not solved and with_check:
            self.save_lp('h{0}_ntc_opf_ts.lp'.format(t))
            self.check_ts()

        return solved

    def error(self):
        """
        Compute total error
        :return: total error
        """
        if self.status == pywraplp.Solver.OPTIMAL:
            return 0
            # return self.all_slacks_sum.solution_value()
        else:
            return 99999


    def solved(self):
        return self.status == pywraplp.Solver.OPTIMAL
        # return abs(self.error()) < self.tolerance

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

    def get_alpha_n1_list(self):

        x = np.zeros(len(self.contingency_indices_list))
        for i in range(len(self.contingency_indices_list)):
            m, c = self.contingency_indices_list[i]
            x[i] = self.alpha_n1[m, c]
        return x


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

    def get_contingency_gen_flows_list(self):
        """
        Square matrix of contingency flows (n branch, n contingency branch)
        :return:
        """

        x = np.zeros(len(self.contingency_gen_flows_list))

        for i in range(len(self.contingency_gen_flows_list)):
            try:
                x[i] = self.contingency_gen_flows_list[i].solution_value() * self.numerical_circuit.Sbase
            except AttributeError:
                x[i] = float(self.contingency_gen_flows_list[i]) * self.numerical_circuit.Sbase

        return x

    def get_contingency_hvdc_flows_list(self):
        """
        Square matrix of contingency flows (n branch, n contingency branch)
        :return:
        """

        x = np.zeros(len(self.contingency_hvdc_flows_list))

        for i in range(len(self.contingency_hvdc_flows_list)):
            try:
                x[i] = self.contingency_hvdc_flows_list[i].solution_value() * self.numerical_circuit.Sbase
            except AttributeError:
                x[i] = float(self.contingency_hvdc_flows_list[i]) * self.numerical_circuit.Sbase

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
        x = self.extract(self.Pg_delta, make_abs=False) * self.numerical_circuit.Sbase
        x[self.gen_a2_idx] *= -1  # this is so that the deltas in the receiving area appear negative in the final vector
        return x

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
        return the hvdc loading (time, device)
        :return: 2D array
        """
        return self.extract(
            self.hvdc_flow, make_abs=False
        ) * self.numerical_circuit.Sbase / self.numerical_circuit.hvdc_data.rate[:, 0]

    def get_hvdc_angle_slacks(self):
        """
        return the hvdc angle slacks (time, device)
        :return: 2D array
        """
        return self.extract(self.hvdc_angle_slack_neg + self.hvdc_angle_slack_pos, make_abs=False)

    def get_branch_ntc_load_rule(self):
        """
        return the branch min ntc load by ntc rule
        :return:
        """
        return self.extract(self.branch_ntc_load_rule, make_abs=False) * self.numerical_circuit.Sbase

if __name__ == '__main__':
    from GridCal.Engine.basic_structures import BranchImpedanceMode
    from GridCal.Engine.IO.file_handler import FileOpen
    from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit

    folder = r'\\mornt4\DESRED\DPE-Planificacion\Plan 2021_2026\_0_TRABAJO\5_Plexos_PSSE\Peninsula\_2026_TRABAJO\Vesiones con alegaciones\Anexo II\TYNDP 2022 V2\5GW\Con N-x\merged\GridCal'
    fname = os.path.join(folder, 'ES-PTv2--FR v4_fused - ts corta 5k.gridcal')

    main_circuit = FileOpen(fname).open()

    # compute information about areas ----------------------------------------------------------------------------------
    area_from_idx = 0
    area_to_idx = 1
    areas = main_circuit.get_bus_area_indices()

    numerical_circuit_ = compile_snapshot_opf_circuit(
        circuit=main_circuit,
        apply_temperature=False,
        branch_tolerance_mode=BranchImpedanceMode.Specified)

    # get the area bus indices
    areas = areas[numerical_circuit_.original_bus_idx]
    a1 = np.where(areas == area_from_idx)[0]
    a2 = np.where(areas == area_to_idx)[0]

    problem = OpfNTC(
        numerical_circuit=numerical_circuit_,
        area_from_bus_idx=a1,
        area_to_bus_idx=a2,
        generation_formulation=GenerationNtcFormulation.Proportional)

    print('Solving...')
    status = problem.solve()

    print("Status:", status)

    print('Angles\n', np.angle(problem.get_voltage()))
    print('Branch loading\n', problem.get_loading())
    print('Gen power\n', problem.get_generator_power())
    print('Delta power\n', problem.get_generator_delta())
    print('Area slack', problem.power_shift.solution_value())
    print('HVDC flow\n', problem.get_hvdc_flow())
