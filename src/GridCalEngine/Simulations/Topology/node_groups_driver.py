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
import networkx as nx
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import Normalizer

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Simulations.LinearFactors.linear_analysis_driver import LinearAnalysisResults
from GridCalEngine.enumerations import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate


class NodeGroupsDriver(DriverTemplate):
    """
    NodeGroupsDriver
    """

    name = 'Node groups'
    tpe = SimulationTypes.NodeGrouping_run

    def __init__(self, grid: MultiCircuit, sigmas, min_group_size, ptdf_results: LinearAnalysisResults):
        """
        Electric distance clustering
        :param grid: MultiCircuit instance
        :param sigmas: number of standard deviations to consider
        :param min_group_size: minimum number of elemnts in a group
        :param ptdf_results: LinearAnalysisResults (if None, they are resimulated)
        """
        DriverTemplate.__init__(self, grid=grid)

        self.grid = grid

        self.sigmas = sigmas

        self.min_group_size = min_group_size

        n = len(grid.buses)

        self.use_ptdf = True

        self.ptdf_results = ptdf_results

        # results
        self.X_train = np.zeros((n, n))
        self.sigma = 1.0
        self.groups_by_name = list()
        self.groups_by_index = list()

        self.__cancel__ = False

    def build_weighted_graph(self):
        """

        :return:
        """
        graph = nx.Graph()

        bus_dictionary = {bus: i for i, bus in enumerate(self.grid.get_buses())}

        for branch_list in self.grid.get_branch_lists():
            for i, branch in enumerate(branch_list):
                # if branch.active:
                f = bus_dictionary[branch.bus_from]
                t = bus_dictionary[branch.bus_to]
                w = branch.get_weight()
                graph.add_edge(f, t, weight=w)

        return graph

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """
        self.tic()
        self.report_progress(0.0)

        n = self.grid.get_bus_number()

        if self.use_ptdf:
            self.report_text('Analyzing PTDF...')

            # the PTDF matrix will be scaled to 0, 1 to be able to train
            self.X_train = Normalizer().fit_transform(self.ptdf_results.PTDF.T)

            metric = 'euclidean'
        else:
            self.report_text('Exploring Dijkstra distances...')
            # explore
            g = self.build_weighted_graph()
            k = 0
            for i, distances_dict in nx.all_pairs_dijkstra_path_length(g):
                for j, d in distances_dict.items():
                    self.X_train[i, j] = d

                self.report_progress2(k, n)
                k += 1
            metric = 'precomputed'

        # compute the sample sigma
        self.sigma = np.std(self.X_train)
        # max_distance = self.sigma * self.sigmas
        max_distance = self.sigmas

        # construct groups
        self.report_text('Building groups with DBSCAN...')

        # Compute DBSCAN
        model = DBSCAN(eps=max_distance,
                       min_samples=self.min_group_size,
                       metric=metric)

        db = model.fit(self.X_train)

        # get the labels that are greater than -1
        labels = list({i for i in db.labels_ if i > -1})
        self.groups_by_name = [list() for k in labels]
        self.groups_by_index = [list() for k in labels]

        # fill in the groups
        for i, (bus, group_idx) in enumerate(zip(self.grid.buses, db.labels_)):
            if group_idx > -1:
                self.groups_by_name[group_idx].append(bus.name)
                self.groups_by_index[group_idx].append(i)

        # display progress
        self.report_done()
        self.toc()

    def cancel(self):
        """
        Cancel the simulation
        :return:
        """
        self.__cancel__ = True
        self.report_done("Cancelled!")

