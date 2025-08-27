# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List, Dict

import numpy as np

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Aggregation.investment import Investment
from VeraGridEngine.basic_structures import Vec, IntVec, StrVec, Logger


class BlackBoxProblemTemplate:

    def __init__(self, grid: MultiCircuit, x_dim: int, plot_x_idx: int, plot_y_idx: int):

        self.grid = grid

        self.logger = Logger()

        self.plot_x_idx = plot_x_idx
        self.plot_y_idx = plot_y_idx

        self.x_dim = x_dim
        self.x_min = np.zeros(self.x_dim)
        self.x_max = np.ones(self.x_dim)

        # dictionary of investment groups
        self.investments_by_group: Dict[int, List[Investment]] = self.grid.get_investment_by_groups_index_dict()

    def get_investments_for_combination(self, x: IntVec) -> List[Investment]:
        """
        Get the list of the investments that belong to a certain combination
        :param x: array of 0/1
        :return: list of investments objects
        """
        # add all the investments of the investment groups reflected in the combination
        inv_list: List[Investment] = list()

        for i, active in enumerate(x):
            if active == 1:
                inv_list += self.investments_by_group[i]
            if active == 0:
                pass
            else:
                # raise Exception('Value different from 0 and 1!')
                # print('Value different from 0 and 1!', active)
                pass
        return inv_list

    def n_objectives(self) -> int:
        """
        Number of objectives (size of f)
        :return:
        """
        raise Exception("You need to implement this in your child class")

    def n_vars(self) -> int:
        """
        Number of variables (size of x)
        :return:
        """
        return self.x_dim

    def get_objectives_names(self) -> StrVec:
        """
        Get a list of names for the elements of f
        :return:
        """
        raise Exception("You need to implement this in your child class")

    def get_vars_names(self) -> StrVec:
        """
        Get a list of names for the elements of x
        :return:
        """
        raise Exception("You need to implement this in your child class")

    def objective_function(self, x: Vec | IntVec) -> Vec:
        """
        Evaluate x and return f(x)
        :param x: array of variable values
        :return: array of objectives
        """
        raise Exception("You need to implement this in your child class")

