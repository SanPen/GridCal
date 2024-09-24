__author__ = "Paul Schultz"
__date__ = "Jul 11, 2015"
__version__ = "v2.1"

# This file is based on the network creation algorithm published in:
#
# A Random Growth Model for Power Grids and Other Spatially Embedded Infrastructure Networks
# Paul Schultz, Jobst Heitzig, and Juergen Kurths
# Eur. Phys. J. Special Topics on "Resilient power grids and extreme events" (2014)
# DOI: 10.1140/epjst/e2014-02279-6
#

import numpy as np
import networkx as nx
import itertools
from scipy.sparse import dok_matrix


class RpgAlgorithm(object):
    def __init__(self):

        # parameters for the algorithm
        self.n = 20
        self.n0 = 10
        self.p = 0.2
        self.q = 0.3
        self.r = 1. / 3.
        self.s = 0.1

        # node coordinates
        self.lon = []
        self.lat = []
        self.distance = {}
        self.added_nodes = 0
        self.added_edges = 0

        # CHANGE WITH CAUTION!
        self.distance_measure = "euclidean"
        self.sampling = "uniform"
        self.low_memory = True
        self.debug = False

        self.init_edges = set()

    def __str__(self):
        print("----------")
        for attr in vars(self):
            if attr in ["identifier", "added_nodes", "n", "n0", "p", "q", "r", "s"]:
                print("{} : {}".format(attr, str(getattr(self, attr))))
        return "----------"

    ###############################################################################
    # ##                       PUBLIC FUNCTIONS                                ## #
    ###############################################################################

    def set_params(self, **kwargs):
        for key in kwargs:
            if not hasattr(self, key):
                print("ERROR: There is no parameter called: {}".format(key))
                print("Possible choices: n,n0,p,q,r,s")
                continue
            else:
                if self._validation(key, kwargs[key]):
                    setattr(self, key, kwargs[key])
                else:
                    print("ERROR: invalid parameter value for {}".format(key))

    def initialise(self):
        assert self.n >= self.n0

        # keep track of added nodes
        self.added_nodes = 0

        # step I1: draw random locations from rho and add nodes
        #######################################################
        self._add_random_locations(self.n0)
        self.added_nodes += self.n0

        # step I2: construct minimum spanning tree
        ##########################################
        self._initial_mst()

        edge_mask = set([self._s(key) for key in self.adjacency.keys()])
        # edge_mask = set(edge_mask)
        if self.debug:
            print("I2", edge_mask)

        # step I3: add redundant links
        ##############################
        m = min(int(np.floor(self.n0 * (1 - self.s) * (self.p + self.q))), self.n0 * (self.n0 - 1) / 2 - (self.n0 - 1))

        candidates = dict()
        for (u, v) in self.distance.keys():
            if not (u, v) in set(edge_mask):
                candidates[(u, v)] = self.distance[(u, v)]

        if self.r > 0:
            dGmatrix = self._get_graph_distances()
            onesquare = np.ones([self.n0, self.n0])

        for k in range(m):
            if self.r > 0:
                for (u, v) in candidates.keys():
                    candidates[(u, v)] = self.distance[(u, v)] / (1. + dGmatrix[u, v])**self.r

            a, b = min(candidates, key=candidates.get)
            self.adjacency[a, b] = self.adjacency[b, a] = 1
            # make sure i,j is not selected again:
            candidates.pop((a, b), None)

            if self.r > 0:
                dGmatrix = np.minimum(np.minimum(dGmatrix, dGmatrix[:, [a]] + onesquare + dGmatrix[[b], :]),
                                      dGmatrix[:, [b]] + onesquare + dGmatrix[[a], :])

            if self.debug:
                print("I3", (a, b))

        self.added_edges += m

        assert self.added_edges == (len(self.adjacency.keys()) / 2)

        # label initial edges
        self.init_edges = sorted(set([self._s(key) for key in self.adjacency.keys()]))

        if self.debug and self.r > 0:
            assert ((dGmatrix - self._get_graph_distances())**2).sum() == 0 # check that update went well

    def grow(self):
        self._add_random_locations(self.n - self.n0)
        self.adjacency._shape = (self.n, self.n)

        if self.r > 0:
            self.dGmatrix = self._get_graph_distances()
            self.dGmatrix = np.concatenate([np.concatenate([self.dGmatrix, np.zeros((self.n - self.n0, self.n0))],axis=0),
                                            np.zeros((self.n, self.n - self.n0))],axis=1)
        # connect new vertices
        for i in range(self.n0, self.n):
            self.added_nodes += 1
            self._growth_step(i)

        # TODO: this is probably redundant
        assert self.added_nodes == self.n

        if self.debug and self.r > 0:
            assert ((self.dGmatrix - self._get_graph_distances())**2).sum() == 0 # check that update went well

        if self.r > 0:
            delattr(self, "dGmatrix")

    @property
    def edges(self):
        return list(set([self._s(key) for key in self.adjacency.keys()]))

    ###############################################################################
    # ##                       PRIVATE FUNCTIONS                               ## #
    ###############################################################################

    def _get_coords(self):
        if self.sampling == "uniform":
            return self._uniformunitsquare()
        else:
            raise NotImplementedError()

    def _get_distance(self, u, v):
        if self.distance_measure == "euclidean":
            return self._euclidean(int(u), int(v))
        else:
            raise NotImplementedError()

    def _update_distance(self):
        N = len(self.lat)
        for v in range(N):
            for u in range(v):
                self.distance[(u, v)] = self._get_distance(u, v)

    @staticmethod
    def _uniformunitsquare():
        """
        return point drawn uniformly at random
        from unit square -> 2D coordinates
        """
        return np.random.uniform(size=2)

    def _euclidean(self, u, v):
        """
        return euclidean distance between x and y
        """
        x = np.array([self.lat[u], self.lon[u]])
        y = np.array([self.lat[v], self.lon[v]])
        return np.sqrt(sum((x-y)**2))

    def _growth_step(self, node):
        if self.debug:
            print("---------")
            print("adding node {}".format(node))




        # step G5: split random link at midpoint
        ########################################
        if (np.random.random() < self.s) and len(self.adjacency) > 1:
            # choose link at random:
            elist = sorted(set([self._s(key) for key in self.adjacency.keys()]))

            ei = np.random.randint(len(elist))
            e = elist[ei]
            a, b = e[0], e[1]


            # add node at midpoint and calc distances:
            self.lat[node] = (self.lat[a] + self.lat[b]) / 2.
            self.lon[node] = (self.lon[a] + self.lon[b]) / 2.
            if not self.low_memory:
                self._update_distance()

            self.adjacency[a, b] = self.adjacency[b, a] = 0
            self.adjacency[a, node] = self.adjacency[node, a] = 1
            self.adjacency[b, node] = self.adjacency[node, b] = 1

            if self.r > 0:
                self.dGmatrix[:(node + 1), :(node + 1)] = self._get_graph_distances()

            self.added_edges += 1

            if self.debug:
                print("G5", (int(a), int(b)))

            #TODO: make shure (a, node) and (b, node) are not selected again?
        else:
            # step G2: link to nearest
            ##########################
            if node == 1:
                target = 0
            else:
                target = self._get_closest_connected_node(node, node - 1)
            self.adjacency[node, target] = self.adjacency[target, node] = 1


            if self.r > 0:
                # adjust network distances:
                #self.dGmatrix[:(node + 1), :(node + 1)] = self._get_graph_distances()
                self.dGmatrix[node, :self.added_nodes] = self.dGmatrix[target, :self.added_nodes] + 1
                self.dGmatrix[:self.added_nodes, node] = self.dGmatrix[:self.added_nodes, target] + 1
                self.dGmatrix[node, node] = 0

            self.added_edges += 1

            if self.debug:
                print("G2", (node, target))

            # step G3: add optimal redundant link to node
            #############################################
            if np.random.random() < self.p:
                candidates = {}
                for v in range(node - 1):
                    if self.adjacency[v, node] == 0:
                        candidates[(v, node)] = self._get_distance(v, node) if self.low_memory else self.distance[(v, node)]

                # there might be no candidates if n0 = 1
                if len(candidates) > 0:
                    if self.r > 0:
                        #dGmatrix = self._get_graph_distances()

                        for (u, v) in candidates.keys():
                            candidates[(u, v)] /=  ( 1. + self.dGmatrix[u, v])**self.r

                    a, b = min(candidates, key=candidates.get)

                    self.adjacency[a, b] = self.adjacency[b, a] = 1

                    if self.r > 0:
                        if a == node:
                            target = b
                        else:
                            target = a
                        # adjust network distances:
                        self.dGmatrix = np.minimum(
                            np.minimum(self.dGmatrix,
                                       self.dGmatrix[:, [node]] +
                                       np.ones([self.n, self.n]) +
                                       self.dGmatrix[[target],:]
                            ),
                            self.dGmatrix[:,[target]] +
                            np.ones([self.n, self.n]) +
                            self.dGmatrix[[node], :]
                        )

                    self.added_edges += 1

                    if self.debug:
                        print("G3", (a, b))


            # step G4: add another optimal redundant link to random node
            ############################################################
            if np.random.random() < self.q:
                i2 = np.random.randint(node)

                candidates = {}
                for v in range(node):
                    if v == i2:
                        continue
                    if self.adjacency[v, i2] == 0:
                        candidates[self._s((v, i2))] = self._get_distance(v, i2) if self.low_memory else self.distance[self._s((v, i2))]


                # there might be no candidates if n0 = 1
                if len(candidates) > 0:
                    if self.r > 0:
                        #dGmatrix = self._get_graph_distances()

                        for (u, v) in candidates.keys():
                            candidates[(u, v)] /= ( 1. + self.dGmatrix[u, v])**self.r

                    a, b = min(candidates, key=candidates.get)
                    self.adjacency[a, b] = self.adjacency[b, a] = 1


                    if self.r > 0:
                        if a == i2:
                            target = b
                        else:
                            target = a
                        # adjust network distances:
                        self.dGmatrix = np.minimum(
                            np.minimum(self.dGmatrix,
                                       self.dGmatrix[:, [i2]] +
                                       np.ones([self.n, self.n]) +
                                       self.dGmatrix[[target], :]
                            ),
                            self.dGmatrix[:, [target]] +
                            np.ones([self.n, self.n]) +
                            self.dGmatrix[[i2], :]
                        )

                    self.added_edges += 1

                    if self.debug:
                        print("G4", i2, (a, b))

        if self.debug and self.r > 0:
            # check that update went well
            assert ((self.dGmatrix[:(node + 1), :(node + 1)] - self._get_graph_distances())**2).sum() == 0

    @staticmethod
    def _validation(attr, value):
        """

        :param attr:
        :param value:
        :return:
        """
        if attr == "n0" or attr == "n":
            if value < 1:
                return False
            else:
                return True
        elif attr == "r":
            if value < 0:
                return False
            else:
                return True
        else:
            if value < 0 or value > 1:
                return False
            else:
                return True

    def _initial_mst(self):
        adjacency = np.zeros([self.n0, self.n0])
        np.fill_diagonal(adjacency, 0)

        self.mst_edges = self._get_mst()
        for edge in self.mst_edges:
            adjacency[edge[0], edge[1]] = adjacency[edge[1], edge[0]] = 1
            self.added_edges += 1

        self.adjacency = dok_matrix(adjacency)

    def _get_mst(self):

        # full_graph = Graph.Full(self.n0)
        # factor = 1e5  # since small weights lead to MST problem
        # weights = [factor * self.distance[self._s((edge.source,edge.target))] for edge in full_graph.es]
        # G = full_graph.spanning_tree(weights).as_undirected()
        # return G.get_edgelist()

        g = nx.complete_graph(self.n0)
        factor = 1e5
        for u, v in g.edges():
            g[u][v]['weight'] = factor * self.distance[self._s((u, v))]
        nx.minimum_spanning_edges(g)
        return list(nx.minimum_spanning_edges(g))

    def _get_graph_distances(self):
        elist = sorted(set([self._s(key) for key in self.adjacency.keys()]))

        # old code
        # G = Graph(self.added_nodes)
        # G.add_edges(elist)
        # return np.array(G.shortest_paths())

        g = nx.Graph(elist)
        p = dict(nx.shortest_path_length(g))
        n = len(p)
        pairs = np.empty((n, n), dtype=int)
        for i, j in itertools.product(range(n), range(n)):
            pairs[i, j] = p[i][j]

        return pairs

    def _add_random_locations(self, _m):
        m = int(_m)
        if m < 1:
            raise ValueError("You have to add a positive integer number of nodes.")
        else:
            for i in range(m):
                pos = self._get_coords()
                self.lat.append(pos[0])
                self.lon.append(pos[1])
            self._update_distance()

    def _get_closest_connected_node(self, source, connected):
        # vertices need to be properly ordered for this to work, i.e. nodes in the connected component
        # should be labeled from 0 to connected-1
        min_ = np.inf
        target = source
        for node in range(connected):
            if source == node:
                # should actually not happen
                continue
            elif self.adjacency[source, node] == 0:
                d = self._get_distance(node, source) if self.low_memory else self.distance[(node, source)]
                if d < min_:
                    min_ = d
                    target = node
        return target

    @staticmethod
    def _s(tuple_: tuple) -> tuple:
        """

        :param tuple_:
        :return:
        """
        if tuple_[0] < tuple_[1]:
            return tuple_
        else:
            return tuple_[1], tuple_[0]


#######################################################################################################################
#######################################################################################################################
#######################################################################################################################


def main():
    from matplotlib import pyplot as plt

    # initialise algorithm
    g = RpgAlgorithm()

    # for detailed output set 
    g.debug = False

    # set desired parameters and perform algorithm
    g.set_params(n=100, n0=10, r=1./3.)
    g.initialise()
    g.grow()

    print(g)

    G = nx.Graph(g.edges)
    pos = {i: (g.lat[i], g.lon[i]) for i in range(g.added_nodes)}
    nx.draw(G, pos=pos, with_labels=True, node_color='lightblue')
    plt.show()
    

if __name__ == "__main__":
    main()






