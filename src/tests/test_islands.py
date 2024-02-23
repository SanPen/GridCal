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
import os
import pandas as pd
import numpy as np

from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import ReactivePowerControlMode, SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from GridCalEngine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at
from GridCalEngine.api import FileOpen, find_islands


def test_ieee14_islands():
    """
    checks that the computed islands are correct
    This test checks 2 things:
    - PSS/e import fidelity
    - PSS/e vs GridCal results
    :return: Nothing if ok, fails if not
    """

    fname = os.path.join('data', 'grids', 'IEEE14 - multi-island hvdc.gridcal')
    main_circuit = FileOpen(fname).open()

    numerical_circuit = compile_numerical_circuit_at(main_circuit, t_idx=None)

    computed_islands = find_islands(adj=numerical_circuit.compute_adjacency_matrix(),
                                    active=numerical_circuit.bus_data.active)

    expected_islands = [
        np.array([0, 1, 2, 3, 4, 6, 7, 14, 15]),
        np.array([[5, 8, 9, 10, 11, 12, 13]])
    ]

    assert len(computed_islands) == len(expected_islands)

    for computed_indices, expected_indices in zip(computed_islands, expected_islands):
        assert (computed_indices == expected_indices).all()


def test_islands():
    """
    tests several grids islands calculation against tested function written in python
    """

    def find_islands_tested(node_number, indptr, indices, active: np.ndarray):
        """
        Method to get the islands of a graph
        This is the non-recursive version
        :return: list of islands, where each element is a list of the node indices of the island
        """

        # Mark all the vertices as not visited
        visited = np.zeros(node_number, dtype=int)

        # storage structure for the islands (list of lists)
        islands = list()  # type: List[List[int]]
        # islands = nb.typeof([[0]])

        # set the island index
        island_idx = 0

        # go though all the vertices...
        for node in range(node_number):

            # if the node has not been visited...
            if not visited[node] and active[node]:

                # add new island, because the recursive process has already visited all the island connected to v
                # if island_idx >= len(islands):
                islands.append(list())

                # ------------------------------------------------------------------------------------------------------
                # DFS: store in the island all the reachable vertices from current vertex "node"
                #
                # declare a stack with the initial node to visit (node)
                stack = list()  # type: List[int]
                stack.append(node)

                while len(stack) > 0:

                    # pick the first element of the stack
                    v = stack.pop(0)

                    # if v has not been visited...
                    if not visited[v]:

                        # mark as visited
                        visited[v] = 1

                        # add element to the island
                        islands[island_idx].append(v)

                        # Add the neighbours of v to the stack
                        start = indptr[v]
                        end = indptr[v + 1]
                        for i in range(start, end):
                            k = indices[i]  # get the row index in the CSC scheme
                            if not visited[k] and active[k]:
                                stack.append(k)
                # ------------------------------------------------------------------------------------------------------

                # increase the islands index, because all the other connected vertices have been visited
                island_idx += 1

        # sort each of the islands to maintain raccord
        for island in islands:
            island.sort()  # the sorting is done in-place

        return [np.array(isl) for isl in islands]

    fnames = [os.path.join('data', 'grids', 'IEEE14 - multi-island hvdc.gridcal'),
              os.path.join('data', 'grids', '8_nodes_2_islands.gridcal'),
              os.path.join('data', 'grids', 'IEEE 39 (2 islands).gridcal')]

    for fname in fnames:
        main_circuit = FileOpen(fname).open()

        numerical_circuit = compile_numerical_circuit_at(main_circuit, t_idx=None)

        A = numerical_circuit.compute_adjacency_matrix()

        computed_islands = find_islands(adj=A,
                                        active=numerical_circuit.bus_data.active)

        expected_islands = find_islands_tested(node_number=A.shape[0],
                                               indptr=A.indptr,
                                               indices=A.indices,
                                               active=numerical_circuit.bus_data.active)

        assert len(computed_islands) == len(expected_islands)

        for computed_indices, expected_indices in zip(computed_islands, expected_islands):
            assert (computed_indices == expected_indices).all()


if __name__ == '__main__':
    test_ieee14_islands()
