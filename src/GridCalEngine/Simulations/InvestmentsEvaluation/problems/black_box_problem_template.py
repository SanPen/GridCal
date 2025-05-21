# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.basic_structures import Vec


class BlackBoxProblemTemplate:

    def __init__(self, grid: MultiCircuit):

        self.grid = grid

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
        raise Exception("You need to implement this in your child class")

    def get_objectives_names(self) -> List[str]:
        """
        Get a list of names for the elements of f
        :return:
        """
        raise Exception("You need to implement this in your child class")

    def get_vars_names(self) -> List[str]:
        """
        Get a list of names for the elements of x
        :return:
        """
        raise Exception("You need to implement this in your child class")

    def objective_function(self, x: Vec) -> Vec:
        """
        Evaluate x and return f(x)
        :param x: array of variable values
        :return: array of objectives
        """
        raise Exception("You need to implement this in your child class")

