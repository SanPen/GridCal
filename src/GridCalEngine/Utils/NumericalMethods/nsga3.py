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
import math
from typing import Tuple, List
from GridCalEngine.Utils.NumericalMethods.non_dominated_sorting import get_non_dominated_fronts, non_dominated_sorting


# Objective functions
def objective_1(x: np.ndarray) -> float:
    """

    :param x:
    :return:
    """
    return np.sum(x ** 2)


def objective_2(x: np.ndarray) -> float:
    """

    :param x:
    :return:
    """
    return np.sum((x - 2) ** 2)


# Initialize Population
def initialize_population(pop_size: int, bounds: np.ndarray) -> np.ndarray:
    """

    :param pop_size:
    :param bounds:
    :return:
    """
    population = np.empty((pop_size, len(bounds)))
    for i in range(pop_size):
        for j, (low, high) in enumerate(bounds):
            if isinstance(low, int) and isinstance(high, int):
                population[i, j] = np.random.randint(low, high + 1)
            else:
                population[i, j] = np.random.uniform(low, high)
    return population


# Evaluate Population
def evaluate_population(population: np.ndarray) -> np.ndarray:
    """

    :param population:
    :return:
    """
    pop_size = population.shape[0]
    objectives = np.empty((pop_size, 2))
    for i in range(pop_size):
        objectives[i, 0] = objective_1(population[i])
        objectives[i, 1] = objective_2(population[i])
    return objectives


# Tournament Selection
def tournament_selection(population: np.ndarray, objectives: np.ndarray, k: int = 2) -> np.ndarray:
    """

    :param population:
    :param objectives:
    :param k:
    :return:
    """
    pop_size = population.shape[0]
    selected = np.empty_like(population)
    for i in range(pop_size):
        aspirants = np.random.choice(pop_size, k, replace=False)
        aspirant_objectives = objectives[aspirants]
        selected[i] = population[aspirants[np.argmin(aspirant_objectives[:, 0])]]
    return selected


# Crossover
def crossover(parent1: np.ndarray, parent2: np.ndarray, crossover_rate: float = 0.9) -> Tuple[np.ndarray, np.ndarray]:
    """

    :param parent1:
    :param parent2:
    :param crossover_rate:
    :return:
    """
    if np.random.rand() < crossover_rate:
        point = np.random.randint(1, len(parent1))
        child1 = np.concatenate([parent1[:point], parent2[point:]])
        child2 = np.concatenate([parent2[:point], parent1[point:]])
        return child1, child2
    else:
        return parent1, parent2


# Mutation
def mutation(individual: np.ndarray, bounds: np.ndarray, mutation_rate: float = 0.1) -> np.ndarray:
    """

    :param individual:
    :param bounds:
    :param mutation_rate:
    :return:
    """
    for i, (low, high) in enumerate(bounds):
        if np.random.rand() < mutation_rate:
            if isinstance(low, int) and isinstance(high, int):
                individual[i] = np.random.randint(low, high + 1)
            else:
                individual[i] = np.random.uniform(low, high)
    return individual


def generate_recursive(dim: int, left: int, total: int, result: np.ndarray, current: np.ndarray, index: int) -> int:
    """

    :param dim:
    :param left:
    :param total:
    :param result:
    :param current:
    :param index:
    :return:
    """
    if dim == 1:
        current[-1] = left / total
        result[index] = current.copy()
        return index + 1
    else:
        for i in range(left + 1):
            current[-dim] = i / total
            index = generate_recursive(dim - 1, left - i, total, result, current, index)
        return index


# Generate Reference Points
def generate_reference_points(n_obj: int, n_partitions: int) -> np.ndarray:
    """

    :param n_obj:
    :param n_partitions:
    :return:
    """

    num_points = int(math.factorial(n_partitions + n_obj - 1) /
                     (math.factorial(n_partitions) * math.factorial(n_obj - 1)))
    result = np.empty((num_points, n_obj))
    generate_recursive(n_obj, n_partitions, n_partitions, result, np.zeros(n_obj), 0)
    return result


# Associate to Reference Points
def associate_to_reference_points(front: np.ndarray, ref_points: np.ndarray) -> np.ndarray:
    """

    :param front:
    :param ref_points:
    :return:
    """
    distances = np.linalg.norm(ref_points[:, np.newaxis, :] - front[np.newaxis, :, :], axis=2)
    return np.argmin(distances, axis=0)


# Niching Function
def niching(front: np.ndarray, ref_points: np.ndarray, pop_size: int) -> np.ndarray:
    """

    :param front:
    :param ref_points:
    :param pop_size:
    :return:
    """
    associations = associate_to_reference_points(front, ref_points)
    niche_counts = np.zeros(len(ref_points), dtype=int)
    selected_indices = np.zeros(pop_size, dtype=int)

    count = 0
    while count < pop_size:
        niche_indices = np.where(niche_counts == np.min(niche_counts))[0]
        min_indices = np.where(np.isin(associations, niche_indices))[0]

        if len(min_indices) + count <= pop_size:
            selected_indices[count:count + len(min_indices)] = min_indices
            count += len(min_indices)
            niche_counts[associations[min_indices]] += 1
        else:
            remaining = pop_size - count
            selected = np.random.choice(min_indices, remaining, replace=False)
            selected_indices[count:count + remaining] = selected
            count += remaining
            niche_counts[associations[selected]] += 1

    return front[selected_indices]


def nsga3(n_obj: int, pop_size: int, generations: int, n_partitions: int, bounds: np.ndarray):
    """

    :param n_obj:
    :param pop_size:
    :param generations:
    :param n_partitions:
    :param bounds:
    :return:
    """

    population: np.ndarray = initialize_population(pop_size, bounds)
    ref_points: np.ndarray = generate_reference_points(n_obj, n_partitions)

    for generation in range(generations):
        # Evaluate current population
        objectives = evaluate_population(population)

        # Perform tournament selection
        parents = tournament_selection(population, objectives)

        # Generate offspring through crossover and mutation
        offspring = np.empty_like(population)
        for i in range(0, pop_size, 2):
            if i < pop_size - 1:
                parent1 = parents[i, :]
                parent2 = parents[i + 1, :]
                child1, child2 = crossover(parent1, parent2)
                offspring[i] = mutation(child1, bounds)
                offspring[i + 1] = mutation(child2, bounds)
            else:
                parent1 = parents[i]
                offspring[i] = mutation(parent1, bounds)

        # Combine parent and offspring populations
        combined_population = np.vstack((population, offspring))

        # Evaluate combined population
        combined_objectives = evaluate_population(combined_population)

        # Perform non-dominated sorting
        sorted_objectives, sorted_population, _ = non_dominated_sorting(combined_objectives, combined_population)

        # Select new population
        new_population = np.empty((0, combined_population.shape[1]))
        for front in get_non_dominated_fronts(sorted_objectives):
            if len(new_population) + len(front) <= pop_size:
                new_population = np.vstack((new_population, sorted_population[front]))
            else:
                remaining = pop_size - len(new_population)
                new_population = np.vstack((new_population, niching(sorted_population[front], ref_points, remaining)))
                break

        population = new_population

    # Final population
    final_population: np.ndarray = population
    final_objectives: np.ndarray = evaluate_population(final_population)


if __name__ == '__main__':
    # Problem definition and parameters
    int_bounds: np.ndarray = np.array([(1, 5)] * 2)
    cont_bounds: np.ndarray = np.array([(0.0, 1.0)] * 2)
    bounds: np.ndarray = np.vstack((int_bounds, cont_bounds))

    nsga3(n_obj=2,
          pop_size=100,
          generations=10,
          n_partitions=10,
          bounds=bounds)
