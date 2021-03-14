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
import pandas as pd
# from networkx import DiGraph, all_simple_paths, Graph, all_pairs_dijkstra_path_length
import networkx as nx
from scipy.sparse import lil_matrix, csc_matrix
from PySide2.QtCore import QThread, Signal
from typing import List
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import Normalizer

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices.branch import BranchType
from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Simulations.LinearFactors.analytic_ptdf_driver import LinearAnalysisResults

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)


def get_branches_of_bus(B, j):
    """
    Get the indices of the branches connected to the bus j
    :param B: Branch-bus CSC matrix
    :param j: bus index
    :return: list of branches in the bus
    """
    return [B.indices[k] for k in range(B.indptr[j], B.indptr[j + 1])]


def select_branches_to_reduce(circuit: MultiCircuit, rx_criteria=True, rx_threshold=1e-5,
                              selected_types=BranchType.Branch):
    """
    Find branches to remove
    Args:
        circuit: Circuit to modify in-place
        rx_criteria: use the r+x threshold to select branches?
        rx_threshold: r+x threshold
        selected_types: branch types to select
    """

    branches_to_remove_idx = list()
    branches = circuit.get_branches()
    for i in range(len(branches)):

        # is this branch of the selected type?
        if branches[i].branch_type in selected_types:

            # Am I filtering by r+x threshold?
            if rx_criteria:

                # compute the r+x ratio
                rx = branches[i].R + branches[i].X

                # if the r+x criteria is met, add it
                if rx < rx_threshold:
                    print(i, '->', rx, '<', rx_threshold)
                    branches_to_remove_idx.append(i)

            elif branches[i].branch_type == BranchType.Switch:

                # add switches
                branches_to_remove_idx.append(i)

            else:
                # Add the branch because it was selected and there is no further criteria
                branches_to_remove_idx.append(i)

    return branches_to_remove_idx


def reduce_grid_brute(circuit: MultiCircuit, removed_br_idx):
    """
    Remove the first branch found to be removed.
    this function is meant to be called until it returns false
    Args:
        circuit: Circuit to modify in-place
        removed_br_idx: branch index

    Returns: Nothing
    """

    # form C
    m = circuit.get_branch_number()
    n = len(circuit.buses)
    buses_dict = {bus: i for i, bus in enumerate(circuit.buses)}
    C = lil_matrix((m, n), dtype=int)
    graph = nx.DiGraph()

    # TODO: Fix the topology reduction with the GC example, see what is going on
    branches = circuit.get_branches()
    for i, elm in enumerate(branches):
        # get the from and to bus indices
        f = buses_dict[elm.bus_from]
        t = buses_dict[elm.bus_to]
        graph.add_edge(f, t)
        C[i, f] = 1
        C[i, t] = -1

    C = csc_matrix(C)

    # get branch buses
    bus_f = branches[removed_br_idx].bus_from
    bus_t = branches[removed_br_idx].bus_to
    f = buses_dict[bus_f]
    t = buses_dict[bus_t]

    updated_branches = list()

    # get the number of paths
    n_paths = len(list(nx.all_simple_paths(graph, f, t)))

    if n_paths == 1:  # if there is only one path, merge the buses

        # get the branches that are connected to the bus f
        adjacent_br_idx = get_branches_of_bus(C, f)

        for k, modified_branch in enumerate(adjacent_br_idx):  # for each adjacent branch, reassign the removed bus

            # get the indices of the buses
            f2 = buses_dict[modified_branch.bus_from]
            t2 = buses_dict[modified_branch.bus_to]

            # re-assign the right bus
            if f2 == f:
                modified_branch.bus_from = bus_t
            elif t2 == f:
                modified_branch.bus_to = bus_t

            # copy the state of the removed branch
            modified_branch.active = branches[removed_br_idx].active

            # remember the updated branches
            updated_branches.append(modified_branch)

        # merge buses
        bus_t.merge(bus_f)
        updated_bus = bus_t

        # delete bus
        removed_bus = circuit.buses.pop(f)

        # remove the branch and that's it
        removed_branch = branches.pop(removed_br_idx)

    else:
        # remove the branch and that's it
        removed_branch = branches.pop(removed_br_idx)
        removed_bus = None
        updated_bus = None

    # return the removed branch and the possible removed bus
    return removed_branch, removed_bus, updated_bus, updated_branches


def reduce_buses(circuit: MultiCircuit, buses_to_reduce: List[Bus], text_func=None, prog_func=None):
    """
    Reduce the uses in the grid
    This function removes the buses but whenever a bus is removed, the devices connected to it
    are inherited by the bus of higher voltage that is connected.
    If the bus is isolated, those devices are lost.
    :param circuit: MultiCircuit instance
    :param buses_to_reduce: list of Bus objects
    :return: Nothing
    """

    if text_func is not None:
        text_func('Removing and merging buses...')

    # create dictionary of bus relationships
    bus_bus = dict()
    branches = circuit.get_branches()
    for branch in branches:
        f = branch.bus_from
        t = branch.bus_to

        # add that "t" is related to "f"
        if f in bus_bus.keys():
            bus_bus[f].append(t)
        else:
            bus_bus[f] = [t]

        # add that "f" is related to "t"
        if t in bus_bus.keys():
            bus_bus[t].append(f)
        else:
            bus_bus[t] = [f]

    # sort on voltage
    for bus, related in bus_bus.items():
        related.sort(key=lambda x: x.Vnom, reverse=True)

    buses_merged = list()

    # remove
    total = len(buses_to_reduce)
    for k, bus in enumerate(buses_to_reduce):

        if bus in bus_bus.keys():
            related_buses = bus_bus[bus]

            if len(related_buses) > 0:
                selected = related_buses.pop(0)
                while selected not in circuit.buses and len(related_buses) > 0:
                    selected = related_buses.pop(0)

                # merge the bus with the selected one
                print('Assigning', bus.name, 'to', selected.name)
                selected.merge(bus)

                # merge the graphics
                if selected.graphic_obj is not None and bus.graphic_obj is not None:
                    selected.graphic_obj.merge(bus.graphic_obj)

                # remember the buses that keep the devices
                buses_merged.append(selected)

                # delete the bus from the circuit and the dictionary
                circuit.delete_bus(bus)
                bus_bus.__delitem__(bus)
            else:
                # the bus is isolated, so delete it
                circuit.delete_bus(bus)

        else:
            # the bus is isolated, so delete it
            circuit.delete_bus(bus)

        if text_func is not None:
            text_func('Removing ' + bus.name + '...')

        if prog_func is not None:
            prog_func((k+1) / total * 100.0)

    return buses_merged


class TopologyReductionOptions:

    def __init__(self, rx_criteria=False, rx_threshold=1e-5, selected_types=BranchType.Branch):
        """
        Topology reduction options
        :param rx_criteria:
        :param rx_threshold:
        :param selected_types:
        """

        self.rx_criteria = rx_criteria
        self.rx_threshold = rx_threshold
        self.selected_type = selected_types


class TopologyReduction(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, grid: MultiCircuit, branch_indices):
        """
        Topology reduction driver
        :param grid: MultiCircuit instance
        :param options:
        """
        QThread.__init__(self)

        self.grid = grid

        self.br_to_remove = branch_indices

        self.__cancel__ = False

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Detecting which branches to remove...')

        # sort the branches in reverse order
        self.br_to_remove.sort(reverse=True)

        total = len(self.br_to_remove)

        # for every branch in reverse order...
        for i, br_idx in enumerate(self.br_to_remove):

            # delete branch
            removed_branch, removed_bus, updated_bus, updated_branches = reduce_grid_brute(circuit=self.grid,
                                                                                           removed_br_idx=br_idx)

            # display progress
            self.progress_text.emit('Removed branch ' + str(br_idx) + ': ' + removed_branch.name)
            progress = (i+1) / total * 100
            self.progress_signal.emit(progress)

        # display progress
        self.progress_text.emit('Done')
        self.progress_signal.emit(0.0)
        self.done_signal.emit()

    def cancel(self):
        """
        Cancel the simulation
        :return:
        """
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()


class DeleteAndReduce(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, grid: MultiCircuit, objects, sel_idx):
        """

        :param grid:
        :param objects: list of objects to reduce (buses in this cases)
        :param sel_idx: indices
        """
        QThread.__init__(self)

        self.grid = grid

        self.objects = objects

        self.sel_idx = sel_idx

        self.buses_merged = list()

        self.__cancel__ = False

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Detecting which branches to remove...')

        # get the selected buses
        buses = [self.objects[idx.row()] for idx in self.sel_idx]

        # reduce
        self.buses_merged = reduce_buses(circuit=self.grid,
                                         buses_to_reduce=buses,
                                         text_func=self.progress_text.emit,
                                         prog_func=self.progress_signal.emit)

        # display progress
        self.progress_text.emit('Done')
        self.progress_signal.emit(0.0)
        self.done_signal.emit()

    def cancel(self):
        """
        Cancel the simulation
        :return:
        """
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()


class NodeGroupsDriver(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()

    def __init__(self, grid: MultiCircuit, sigmas=0.5, min_group_size=2, ptdf_results: LinearAnalysisResults = None):
        """
        Electric distance clustering
        :param grid: MultiCircuit instance
        :param sigmas: number of standard deviations to consider
        """
        QThread.__init__(self)

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

        bus_dictionary = {bus: i for i, bus in enumerate(self.grid.buses)}

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
        self.progress_signal.emit(0.0)

        n = len(self.grid.buses)

        if self.use_ptdf:
            self.progress_text.emit('Analyzing PTDF...')

            # the PTDF matrix will be scaled to 0, 1 to be able to train
            self.X_train = Normalizer().fit_transform(self.ptdf_results.PTDF.T)

            metric = 'euclidean'
        else:
            self.progress_text.emit('Exploring Dijkstra distances...')
            # explore
            g = self.build_weighted_graph()
            k = 0
            for i, distances_dict in nx.all_pairs_dijkstra_path_length(g):
                for j, d in distances_dict.items():
                    self.X_train[i, j] = d

                self.progress_signal.emit((k+1) / n * 100.0)
                k += 1
            metric = 'precomputed'

        # compute the sample sigma
        self.sigma = np.std(self.X_train)
        # max_distance = self.sigma * self.sigmas
        max_distance = self.sigmas

        # construct groups
        self.progress_text.emit('Building groups with DBSCAN...')

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
        self.progress_text.emit('Done')
        self.progress_signal.emit(0.0)
        self.done_signal.emit()

    def cancel(self):
        """
        Cancel the simulation
        :return:
        """
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled')
        self.done_signal.emit()


if __name__ == '__main__':

    from GridCal.Engine import *
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Illinois 200 Bus.gridcal'
    fname = '/home/santi/Documentos/Private_Grids/Penísula Ibérica 2026.gridcal'
    grid = FileOpen(fname).open()

    driver = NodeGroupsDriver(grid=grid, sigmas=1e-3)
    driver.run()

    print('\nGroups:')
    for group in driver.groups_by_name:
        print(group)

    for group in driver.groups_by_index:
        print(group)
