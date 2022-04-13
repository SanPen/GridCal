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
import json
from typing import List

import numpy as np

from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable


class ResultsTemplate:

    def __init__(self, name='',
                 available_results: List[ResultTypes] = list(),
                 data_variables: List[str] = list()):
        """
        Results template class
        :param name: Name of the class
        :param available_results: list of stuff to represent the results
        :param data_variables: list of class variables to persist to disk
        """
        self.name = name
        self.available_results: List[ResultTypes] = available_results
        self.data_variables: List[str] = data_variables

    def consolidate_after_loading(self):
        pass

    def get_results_dict(self):
        data = dict()

        return data

    def get_arrays(self):
        """
        Get a dictionary with the array name and the actual array of the class (it also works with the derived class)
        :return: {array_name: array}
        """
        property_names = [p for p in dir(self) if isinstance(getattr(self, p), np.ndarray)]
        return {var_name: getattr(self, var_name) for var_name in property_names}

    def to_json(self, file_name):
        """
        Export as json
        :param file_name: File name
        """

        with open(file_name, "w") as output_file:
            json_str = json.dumps(self.get_results_dict())
            output_file.write(json_str)

    def apply_new_rates(self, rates):
        pass

    def apply_new_time_series_rates(self, rates):
        pass

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        pass
