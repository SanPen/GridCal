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
import uuid
from typing import List
from GridCal.Engine.Core.multi_circuit import MultiCircuit, DeviceType


class Contingency:

    def __init__(self):

        self.id = uuid.uuid4().hex

        self.name = ''

        self.tpe = ''

        # list of branch indices to fail
        self.branch_indices: List[int] = list()

        # list of HVDC line indices to fail
        self.hvdc_indices: List[int] = list()

        # list of generator indices to fail (reducing power)
        self.generator_indices: List[int] = list()

        # list of generator per unit amount to reduce
        self.generator_power_amount_to_reduce: List[float] = list()

    def add_branch(self, i: int):
        """
        Add a branch
        """
        self.branch_indices.append(i)

    def add_hvdc(self, i: int):
        """
        Add a branch
        """
        self.hvdc_indices.append(i)

    def add_generator(self, i: int, perc: float):
        """
        Add a generator
        """
        self.generator_indices.append(i)
        self.generator_power_amount_to_reduce.append(perc)

    def get_dict(self):
        """
        Get this contingency as dictionary
        :return:
        """
        return {'id': self.id,
                'name': self.name,
                'type': self.tpe,
                'branch_indices': self.branch_indices,
                'hvdc_indices': self.hvdc_indices,
                'generator_indices': self.generator_indices,
                'generator_power_amount_to_reduce': self.generator_power_amount_to_reduce}

    def parse_dict(self, data: dict):
        """
        parse the dictionary
        :param data:
        :return:
        """
        self.id = data['id'] if 'id' in data else uuid.uuid4().hex
        self.name = data['name'] if 'name' in data else ""
        self.tpe = data['type'] if 'type' in data else ""
        self.branch_indices = data['branch_indices'] if 'branch_indices' in data else list()
        self.hvdc_indices = data['hvdc_indices'] if 'hvdc_indices' in data else list()
        self.generator_indices = data['generator_indices'] if 'generator_indices' in data else list()
        self.generator_power_amount_to_reduce = data['generator_power_amount_to_reduce'] if 'generator_power_amount_to_reduce' in data else list()


class ContingencyPlan:

    def __init__(self):
        self.contingencies: List[Contingency] = list()

    def add_contingency(self, c: Contingency):
        self.contingencies.append(c)

    def delete_contingency(self, idx):
        self.contingencies.pop(idx)

    def get_dict(self):
        return [e.get_dict() for e in self.contingencies]

    def parse_data(self, data: list):

        for elm in data:
            c = Contingency()
            c.parse_dict(elm)
            self.add_contingency(c)


def get_branch_max_voltage(branch):
    """

    :param branch:
    :return:
    """
    v1 = branch.bus_from.Vnom
    v2 = branch.bus_to.Vnom

    return max(v1, v2)


def add_n1_contingencies(plan: ContingencyPlan, branches, vmin, vmax, filter_branches_by_voltage, branch_types):
    """

    :param plan:
    :param branches:
    :param vmin:
    :param vmax:
    :param filter_branches_by_voltage:
    :param branch_types:
    :return:
    """
    for i, branch_i in enumerate(branches):

        vi = get_branch_max_voltage(branch_i)

        filter_ok_i = (vmin <= vi <= vmax) if filter_branches_by_voltage else True

        if filter_ok_i and branch_i.device_type in branch_types:
            ci = Contingency()
            ci.add_branch(i)
            plan.add_contingency(ci)
            ci.name = branch_i.name
            ci.tpe = 'N-1'


def add_n2_contingencies(plan: ContingencyPlan, branches, vmin, vmax, filter_branches_by_voltage, branch_types):
    """

    :param plan:
    :param branches:
    :param vmin:
    :param vmax:
    :param filter_branches_by_voltage:
    :param branch_types:
    :return:
    """
    for i, branch_i in enumerate(branches):

        vi = get_branch_max_voltage(branch_i)

        filter_ok_i = (vmin <= vi <= vmax) if filter_branches_by_voltage else True

        if filter_ok_i and branch_i.device_type in branch_types:

            for j, branch_j in enumerate(branches):

                if j != i:

                    vj = get_branch_max_voltage(branch_j)

                    filter_ok_j = (vmin <= vj <= vmax) if filter_branches_by_voltage else True

                    if filter_ok_j and branch_j.device_type in branch_types:
                        ci = Contingency()
                        ci.tpe = 'N-2'
                        ci.add_branch(i)
                        ci.add_branch(j)
                        ci.name = branch_i.name + ':' + branch_j.name

                        # add the N-2 contingency
                        plan.add_contingency(ci)


def generate_automatic_contingency_plan(grid: MultiCircuit, k: int,
                                        filter_branches_by_voltage: bool = False, vmin=0, vmax=1000,
                                        branch_types: List[DeviceType] = list(),
                                        filter_injections_by_power: bool = False, contingency_perc=100.0, pmin=0, pmax=10000,
                                        injection_types: List[DeviceType] = list()) -> ContingencyPlan:
    """

    :param grid: MultiCircuit instance
    :param k: index (1 for N-1, 2 for N-2, other values of k will fail)
    :param filter_branches_by_voltage:
    :param vmin:
    :param vmax:
    :param branch_types: List of allowed branch types
    :param filter_injections_by_power:
    :param contingency_perc:
    :param pmin:
    :param pmax:
    :param injection_types: List of allowed injection types
    :return:
    """

    assert (k in [1, 2])

    plan = ContingencyPlan()

    branches = grid.get_branches_wo_hvdc()

    if k == 1:
        add_n1_contingencies(plan, branches, vmin, vmax, filter_branches_by_voltage, branch_types)

    elif k == 2:
        add_n1_contingencies(plan, branches, vmin, vmax, filter_branches_by_voltage, branch_types)
        add_n2_contingencies(plan, branches, vmin, vmax, filter_branches_by_voltage, branch_types)

    return plan
