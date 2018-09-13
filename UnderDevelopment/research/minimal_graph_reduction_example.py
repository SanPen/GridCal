# from networkx import DiGraph, all_simple_paths, draw
from matplotlib import pyplot as plt
# Python program to print all paths from a source to destination.

from collections import defaultdict


# This class represents a directed graph
# using adjacency list representation
class Graph:

    def __init__(self, number_of_nodes):

        # default dictionary to store graph
        self.graph = dict()

        # function to add an edge to graph
        self.number_of_nodes = number_of_nodes

        # initialize adjacency graph
        for i in range(number_of_nodes):
            self.graph[i] = list()

    def add_edge(self, u, v):
        """
        Add directed edge between u and v
        :param u: node
        :param v: node
        """
        self.graph[u].append(v)
        # self.graph[v].append(u)

    def all_paths_util(self, u, d, visited, path, paths):
        """
        A recursive function to print all paths from 'u' to 'd'.
        visited[] keeps track of vertices in current path.
        path[] stores actual vertices and path_index is current
        index in path[]
        :param u:
        :param d:
        :param visited:
        :param path:
        :param paths:
        :return:
        """

        # Mark the current node as visited and store in path
        visited[u] = True
        path.append(u)

        # If current vertex is same as destination, then print
        # current path[]
        if u == d:
            paths.append(path)
        else:
            # If current vertex is not destination
            # Recur for all the vertices adjacent to this vertex
            for i in self.graph[u]:
                if visited[i] is False:
                    self.all_paths_util(i, d, visited, path, paths)

        # Remove current vertex from path[] and mark it as unvisited
        path.pop()
        visited[u] = False

    # Prints all paths from 's' to 'd'
    def all_simple_paths(self, s, d):

        # Mark all the vertices as not visited
        visited = [False] * self.number_of_nodes

        # Create an array to store paths
        paths = list()
        path = list()

        # Call the recursive helper function to print all paths
        self.all_paths_util(s, d, visited, path, paths)

        return paths

    def merge_nodes(self, node_to_delete, node_to_keep):
        """
        Merge the information about two nodes
        :param node_to_delete:
        :param node_to_keep:
        :return:
        """
        # self.graph[node_to_keep] += self.graph[node_to_delete]

        lst = self.graph[node_to_delete]

        for x in lst:
            if x != node_to_keep:
                self.graph[x] += node_to_keep

        del self.graph[node_to_delete]

        # for key, values in self.graph.items():
        #     val = values.copy()
        #     for i in range(len(val)):
        #         if val[i] == node_to_delete:
        #             val[i] = node_to_keep
        #             print('\tnode updated', key, ':', node_to_delete, '->', node_to_keep, ' remove(', node_to_delete, ')')
        #     self.graph[key] = val

        pass

    def remove_edge(self, u, v):
        if v in self.graph[u]:
            self.graph[u].remove(v)
            self.graph[v].remove(u)


# data preparation -----------------------------------------------
branches = [(1, 0), (2, 1), (3, 2), (3, 12), (6, 5), (5, 4), (4, 3),
            (7, 6), (8, 7), (8, 9), (9, 10), (10, 11), (11, 0), (12, 8)]

branches_to_remove_idx = [11, 10, 9, 8, 6, 5, 3, 2, 0]
ft_dict = dict()
graph = Graph(13)

for i, br in enumerate(branches):
    graph.add_edge(br[0], br[1])
    ft_dict[i] = (br[0], br[1])

# Processing -----------------------------------------------------
for idx in branches_to_remove_idx:

    # get the nodes that define the edge to remove
    f, t = ft_dict[idx]

    # get the number of paths from 'f' to 't'
    n_paths = len(list(graph.all_simple_paths(f, t)))

    if n_paths == 1:
        # remove branch and merge the nodes 'f' and 't'
        #
        #       This is wat I have no clue how to do
        #
        print('Merge nodes', f, t)
        graph.merge_nodes(f, t)

        pass

    else:
        # remove the branch and that's it
        print('Simple removal of', f, t)
        graph.remove_edge(f, t)


# -----------------------------------------------------------------
