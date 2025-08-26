# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from itertools import combinations
import numpy as np
from typing import List, Tuple

from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Devices.Aggregation.contingency import Contingency, ContingencyGroup
from GridCalEngine.Devices.Parents.editable_device import DeviceType
from GridCalEngine.Devices.types import BRANCH_TYPES
from GridCalEngine.enumerations import ContingencyOperationTypes
import GridCalEngine.Devices as dev


def enumerate_states_n_k(m: int, k: int = 1):
    """
    Enumerates the states to produce the so called N-k failures
    :param m: number of Branches
    :param k: failure level
    :return: binary array (number of states, m)
    """

    # num = int(math.factorial(k) / math.factorial(m-k))
    states = list()
    indices = list()
    arr = np.ones(m, dtype=int).tolist()

    idx = list(range(m))
    for k1 in range(k + 1):
        for failed in combinations(idx, k1):
            indices.append(failed)
            arr2 = arr.copy()
            for j in failed:
                arr2[j] = 0
            states.append(arr2)

    return np.array(states), indices


def add_n1_contingencies(branches: List[BRANCH_TYPES],
                         vmin: float,
                         vmax: float,
                         filter_branches_by_voltage: bool,
                         branch_types: List[DeviceType]):
    """
    generate N-1 contingencies on branches
    :param branches:
    :param vmin:
    :param vmax:
    :param filter_branches_by_voltage:
    :param branch_types:
    :return:
    """
    contingencies = list()
    groups = list()

    for i, b in enumerate(branches):

        vi = b.get_max_bus_nominal_voltage()

        filter_ok_i = (vmin <= vi <= vmax) if filter_branches_by_voltage else True

        if filter_ok_i and b.device_type in branch_types:
            group = ContingencyGroup(
                name=b.name,
                category='single',
            )
            contingency = Contingency(
                device=b,
                name=b.name,
                code=b.code,
                prop=ContingencyOperationTypes.Active,
                value=0,
                group=group
            )

            contingencies.append(contingency)
            groups.append(group)

    return contingencies, groups


def add_n2_contingencies(branches, vmin, vmax, filter_branches_by_voltage, branch_types):
    """
    Generate N-2 contingencies for branches
    :param branches:
    :param vmin:
    :param vmax:
    :param filter_branches_by_voltage:
    :param branch_types:
    :return:
    """
    contingencies = list()
    groups = list()

    for i, branch_i in enumerate(branches):

        vi = branch_i.get_max_bus_nominal_voltage()

        filter_ok_i = (vmin <= vi <= vmax) if filter_branches_by_voltage else True

        if filter_ok_i and branch_i.device_type in branch_types:

            for j, branch_j in enumerate(branches):

                if j != i:

                    vj = branch_j.get_max_bus_nominal_voltage()

                    filter_ok_j = (vmin <= vj <= vmax) if filter_branches_by_voltage else True

                    if filter_ok_j and branch_j.device_type in branch_types:
                        group = ContingencyGroup(
                            name=branch_i.name + " " + branch_j.name,
                            category='double',
                        )

                        contingency1 = Contingency(
                            device=branch_i,
                            name=branch_i.name,
                            code=branch_i.code,
                            prop=ContingencyOperationTypes.Active,
                            value=0,
                            group=group
                        )

                        contingency2 = Contingency(
                            device=branch_j,
                            name=branch_j.name,
                            code=branch_j.code,
                            prop=ContingencyOperationTypes.Active,
                            value=0,
                            group=group
                        )

                        contingencies.append(contingency1)
                        contingencies.append(contingency2)
                        groups.append(group)

    return contingencies, groups


def add_generator_contingencies(
        generators: List[dev.Generator],
        pmin: float,
        pmax: float,
        contingency_perc: float,
        filter_injections_by_power: bool):
    """
    Create generator contingencies
    :param generators: Generator list
    :param pmin: Min power to filter
    :param pmax: Max power to filter
    :param contingency_perc: Percentage of power to trigger
    :param filter_injections_by_power: boolean
    :return:
    """
    contingencies = list()
    groups = list()

    for i, gen in enumerate(generators):

        if (pmin <= gen.Snom <= pmax) or not filter_injections_by_power:
            group = ContingencyGroup(
                name=gen.name,
                category='generator',
            )
            contingency = Contingency(
                device=gen,
                name=gen.name,
                code=gen.code,
                prop=ContingencyOperationTypes.PowerPercentage,
                value=contingency_perc,
                group=group
            )

            contingencies.append(contingency)
            groups.append(group)

    return contingencies, groups


def generate_automatic_contingency_plan(
        grid: MultiCircuit,
        k: int,
        consider_branches: bool,
        filter_branches_by_voltage: bool = False,
        vmin: float = 0,
        vmax: float = 1000,
        branch_types: List[DeviceType] | None = None,
        consider_injections: bool = False,
        filter_injections_by_power: bool = False,
        contingency_perc=100.0,
        pmin=0,
        pmax=10000,
        injection_types: List[DeviceType] | None = None
) -> Tuple[List[Contingency], List[ContingencyGroup]]:
    """

    :param grid: MultiCircuit instance
    :param k: index (1 for N-1, 2 for N-2, other values of k will fail)
    :param consider_branches: consider branches?
    :param filter_branches_by_voltage:
    :param vmin:
    :param vmax:
    :param branch_types: List of allowed branch types
    :param consider_injections: Consider injections?
    :param filter_injections_by_power:
    :param contingency_perc:
    :param pmin:
    :param pmax:
    :param injection_types: List of allowed injection types
    :return:
    """

    if branch_types is None:
        branch_types = list()

    if injection_types is None:
        injection_types = list()

    assert (k in [1, 2])
    contingencies = list()
    groups = list()

    # add branch contingencies
    if consider_branches:
        branches = grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)

        if k == 1:
            contingencies1, groups1 = add_n1_contingencies(branches=branches,
                                                           vmin=vmin,
                                                           vmax=vmax,
                                                           filter_branches_by_voltage=filter_branches_by_voltage,
                                                           branch_types=branch_types)

            contingencies += contingencies1
            groups += groups1

        elif k == 2:
            contingencies, groups = add_n1_contingencies(branches=branches,
                                                         vmin=vmin,
                                                         vmax=vmax,
                                                         filter_branches_by_voltage=filter_branches_by_voltage,
                                                         branch_types=branch_types)

            contingencies2, groups2 = add_n2_contingencies(branches=branches,
                                                           vmin=vmin,
                                                           vmax=vmax,
                                                           filter_branches_by_voltage=filter_branches_by_voltage,
                                                           branch_types=branch_types)

            contingencies += contingencies2
            groups += groups2

    # add injection contingencies
    if consider_injections:
        contingencies_gen, groups_gen = add_generator_contingencies(
            generators=grid.get_generators(),
            pmin=pmin,
            pmax=pmax,
            contingency_perc=contingency_perc,
            filter_injections_by_power=filter_injections_by_power,
        )

        contingencies += contingencies_gen
        groups += groups_gen

    return contingencies, groups
