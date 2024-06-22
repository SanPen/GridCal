# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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

import numpy as np
from typing import List, Tuple
from GridCalEngine.basic_structures import Vec, Mat, IntVec


def dominates(sol_a: Vec, sol_b: Vec):
    """
    Check if a solution dominates another in the Pareto sense
    :param sol_a: Array representing the solution A (row of the population)
    :param sol_b: Array representing the solution B (row of the population)
    :return: A dominates B?
    """
    # Check if sol_a dominates sol_b
    better_in_any = False
    for a, b in zip(sol_a, sol_b):
        if a > b:  # Assuming a lower value is better; change logic if otherwise
            return False  # sol_a is worse in at least one objective
        elif a < b:
            better_in_any = True
    return better_in_any


def get_non_dominated_fronts(population: Mat) -> List[List[int]]:
    """
    2D non dominated sorting
    :param population: matrix (n points, ndim)
    :return: Fronts ordered by position (front 1, front 2, Front 3, ...)
            Each front is a list of integers representing the positions in the population matrix
    """
    fronts = [[]]  # Initialize the first front
    dom_counts = np.zeros(len(population))  # [0] * len(population)  # Dominance counts
    dom_sets = [set() for _ in range(len(population))]  # Sets of solutions dominated by each individual

    for i, sol_i in enumerate(population):
        for j, sol_j in enumerate(population):
            if i != j:
                if dominates(sol_i, sol_j):
                    dom_sets[i].add(j)
                elif dominates(sol_j, sol_i):
                    dom_counts[i] += 1

        if dom_counts[i] == 0:  # If no one dominates this solution, it's in the first front
            fronts[0].append(i)

    current_front = 0
    while fronts[current_front]:
        next_front = []
        for i in fronts[current_front]:
            for j in dom_sets[i]:
                dom_counts[j] -= 1  # Reduce the domination count
                if dom_counts[j] == 0:  # If it's not dominated by any other, it's in the next front
                    next_front.append(j)
        current_front += 1
        fronts.append(next_front)

    return fronts[:-1]  # Exclude the last empty front


def crowding_distance(front: List[int], population: Mat) -> Vec:
    """

    :param front: list of integers representing the positions in the population matrix
    :param population: Matrix of function evaluations (Npoints, NObjdim)
    :return:
    """

    # Initialize crowding distances
    distances = np.zeros(len(front))

    if len(front) == 0:
        return distances

    # Number of objectives
    num_objectives = population.shape[1]

    for m in range(num_objectives):
        # Sort solutions by this objective
        front.sort(key=lambda x: population[x, m])

        # Boundary points are always selected
        distances[0] = float('inf')
        distances[-1] = float('inf')

        # Objective range
        obj_range = population[front[-1], m] - population[front[0], m]
        if obj_range == 0:
            continue  # Avoid division by zero

        # Update crowding distances
        for i in range(1, len(front) - 1):
            distances[i] += (population[front[i + 1], m] - population[front[i - 1], m]) / obj_range

    return distances


def sort_by_crowding(fronts: List[List[int]], population: Mat) -> Tuple[Mat, IntVec]:
    """

    :param fronts: Fronts ordered by position (front 1, front 2, Front 3, ...)
            Each front is a list of integers representing the positions in the population matrix
    :param population: Matrix of function evaluations (Npoints, NObjdim)
    :return: sorted population, array of sorting indices
    """
    # Assuming 'fronts' is the output from your get_non_dominated_fronts function
    # and 'population' contains all your solutions
    crowding_distances = []
    for front in fronts:
        distances = crowding_distance(front, population)
        crowding_distances.append(distances)

    sorted_fronts = []
    for front, distances in zip(fronts, crowding_distances):
        # Pair each solution with its distance and sort by distance in descending order
        sorted_front = sorted(list(zip(front, distances)), key=lambda s: s[1], reverse=True)
        sorted_fronts.append([item[0] for item in sorted_front])  # Extract the sorted indices

    sorting_indices = []
    remaining_slots = population.shape[0]  # however many individuals you want in the new population

    for sorted_front in sorted_fronts:
        if len(sorted_front) <= remaining_slots:
            # If the entire front fits, add all individuals from this front to the new population
            sorting_indices.extend(sorted_front)
            remaining_slots -= len(sorted_front)
        else:
            # If not all individuals fit, select the ones with the largest crowding distance
            sorting_indices.extend(sorted_front[:remaining_slots])
            break  # The new population is now full

    return population[sorting_indices, :], sorting_indices


def non_dominated_sorting(y_values: Mat, x_values: Mat) -> Tuple[Mat, Mat, IntVec]:
    """
    Use non dominated sorting and crowded sorting to sort the multidimensional objectives
    :param y_values: Matrix of function evaluations (Npoints, NObjdim)
    :param x_values: Matrix of values (Npoints, Ndim)
    :return: Return the pareto y and matching x. The pareto front may have less values than the population
             [Sorted population, Sorted input values (X)]
    """
    # obtain the sorting fronts
    fronts = get_non_dominated_fronts(y_values)

    # use the fronts to sort using the crowded sortig algorithm
    # sorted_population, sorting_indices = sort_by_crowding(fronts=fronts, population=y_values)
    sorted_population, sorting_indices = sort_by_crowding(fronts=[fronts[0]], population=y_values)

    return sorted_population, x_values[sorting_indices, :], sorting_indices
