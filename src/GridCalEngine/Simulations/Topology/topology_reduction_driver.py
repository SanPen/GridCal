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
import pandas as pd
import networkx as nx
from scipy.sparse import lil_matrix, csc_matrix

from typing import List

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Branches.branch import BranchType
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import SimulationTypes
from GridCalEngine.Simulations.driver_template import DriverTemplate

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)


def get_branches_of_bus(B, j):
    """
    Get the indices of the Branches connected to the bus j
    :param B: Branch-bus CSC matrix
    :param j: bus index
    :return: list of Branches in the bus
    """
    return [B.indices[k] for k in range(B.indptr[j], B.indptr[j + 1])]


def select_branches_to_reduce(circuit: MultiCircuit, rx_criteria=True, rx_threshold=1e-5,
                              selected_types=BranchType.Branch):
    """
    Find Branches to remove
    Args:
        circuit: Circuit to modify in-place
        rx_criteria: use the r+x threshold to select Branches?
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

        # get the Branches that are connected to the bus f
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

            # remember the updated Branches
            updated_branches.append(modified_branch)

        # merge buses
        circuit.merge_buses(bus1=bus_t, bus2=bus_f)
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
    :param text_func:
    :param prog_func:
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
                circuit.merge_buses(bus1=selected, bus2=bus)

                # remember the buses that keep the devices
                buses_merged.append(selected)

                # delete the bus from the circuit and the dictionary
                circuit.delete_bus(bus, delete_associated=True)
                bus_bus.__delitem__(bus)
            else:
                # the bus is isolated, so delete it
                circuit.delete_bus(bus, delete_associated=True)

        else:
            # the bus is isolated, so delete it
            circuit.delete_bus(bus, delete_associated=True)

        if text_func is not None:
            text_func('Removing ' + bus.name + '...')

        if prog_func is not None:
            prog_func((k+1) / total * 100.0)

    return buses_merged


class TopologyReductionOptions:
    """
    TopologyReductionOptions
    """
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


class TopologyReduction(DriverTemplate):
    tpe = SimulationTypes.TopologyReduction_run

    def __init__(self, grid: MultiCircuit, branch_indices):
        """
        Topology reduction driver
        :param grid: MultiCircuit instance
        :param branch_indices: indices of branches to reduce
        """
        DriverTemplate.__init__(self, grid=grid)

        self.br_to_remove = branch_indices

        self.__cancel__ = False

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """
        self.tic()
        self.report_progress(0.0)
        self.report_text('Detecting which Branches to remove...')

        # sort the Branches in reverse order
        self.br_to_remove.sort(reverse=True)

        total = len(self.br_to_remove)

        # for every branch in reverse order...
        for i, br_idx in enumerate(self.br_to_remove):

            # delete branch
            removed_branch, removed_bus, updated_bus, updated_branches = reduce_grid_brute(circuit=self.grid,
                                                                                           removed_br_idx=br_idx)

            # display progress
            self.report_text('Removed branch ' + str(br_idx) + ': ' + removed_branch.name)
            self.report_progress2(i, total)

        self.toc()

    def cancel(self):
        """
        Cancel the simulation
        :return:
        """
        self.__cancel__ = True
        self.report_done("Cancelled!")


class DeleteAndReduce(DriverTemplate):

    def __init__(self, grid: MultiCircuit, objects, sel_idx):
        """

        :param grid:
        :param objects: list of objects to reduce (buses in this cases)
        :param sel_idx: indices
        """
        DriverTemplate.__init__(self, grid=grid)

        self.objects = objects

        self.sel_idx = sel_idx

        self.buses_merged = list()

        self.__cancel__ = False

        self._is_running = True

    def run(self):
        """
        Run the monte carlo simulation
        @return:
        """
        self.tic()
        self._is_running = True
        self.report_progress(0.0)
        self.report_text('Detecting which Branches to remove...')

        # get the selected buses
        buses = [self.objects[idx.row()] for idx in self.sel_idx]

        # reduce
        self.buses_merged = reduce_buses(circuit=self.grid,
                                         buses_to_reduce=buses,
                                         text_func=self.report_text,
                                         prog_func=self.report_progress)

        # display progress
        self.report_done()
        self._is_running = False
        self.toc()

    def cancel(self):
        """
        Cancel the simulation
        :return:
        """
        self.__cancel__ = True
        self.report_done()

    def isRunning(self):
        return self._is_running

    def start(self):
        self.run()

