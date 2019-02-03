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

import numpy as np


class Graph:

    def __init__(self, adj):
        """
        Graph adapted to work with CSC sparse matrices
        see: http://www.scipy-lectures.org/advanced/scipy_sparse/csc_matrix.html
        :param adj: Adjacency matrix in lil format
        """
        self.node_number = adj.shape[0]
        self.adj = adj

    def find_islands(self):
        """
        Method to get the islands of a graph
        This is the non-recursive version
        :return: islands list where each element is a list of the node indices of the island
        """

        # Mark all the vertices as not visited
        visited = np.zeros(self.node_number, dtype=bool)

        # storage structure for the islands (list of lists)
        islands = list()

        # set the island index
        island_idx = 0

        # go though all the vertices...
        for node in range(self.node_number):

            # if the node has not been visited...
            if not visited[node]:

                # add new island, because the recursive process has already visited all the island connected to v
                # if island_idx >= len(islands):
                islands.append(list())

                # ------------------------------------------------------------------------------------------------------
                # DFS: store in the island all the reachable vertices from current vertex "node"
                #
                # declare a stack with the initial node to visit (node)
                stack = list()
                stack.append(node)

                while len(stack) > 0:

                    # pick the first element of the stack
                    v = stack.pop(0)

                    # if v has not been visited...
                    if not visited[v]:

                        # mark as visited
                        visited[v] = True

                        # add element to the island
                        islands[island_idx].append(v)

                        # Add the neighbours of v to the stack
                        start = self.adj.indptr[v]
                        end = self.adj.indptr[v + 1]
                        for i in range(start, end):
                            k = self.adj.indices[i]  # get the column index in the CSC scheme
                            if not visited[k]:
                                stack.append(k)
                            else:
                                pass
                    else:
                        pass
                #
                # ------------------------------------------------------------------------------------------------------

                # increase the islands index, because all the other connected vertices have been visited
                island_idx += 1

            else:
                pass

        # sort the islands to maintain raccord
        for island in islands:
            island.sort()

        return islands

