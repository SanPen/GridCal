# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
from typing import List, Dict, Union

import numpy as np

from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable


class ResultsTemplate:

    def __init__(
            self,
            name: str = '',
            available_results: Union[
                Dict[ResultTypes, List[ResultTypes]],
                List[ResultTypes]
            ] = dict(),
            data_variables: List[str] = list()):
        """
        Results template class
        :param name: Name of the class
        :param available_results: list of stuff to represent the results
        :param data_variables: list of class variables to persist to disk
        """
        self.name: str = name
        self.available_results: Dict[ResultTypes: List[ResultTypes]] = available_results
        self.data_variables: List[str] = data_variables

    def consolidate_after_loading(self):
        pass

    def get_results_dict(self):
        data = dict()

        return data

    def get_name_to_results_type_dict(self):

        d = dict()
        if isinstance(self.available_results, dict):
            for key, values in self.available_results.items():
                for item in values:
                    d[item.value[0]] = item

        if isinstance(self.available_results, list):
            for item in self.available_results:
                d[item.value[0]] = item

        return d

    def get_name_tree(self):

        d = dict()
        if isinstance(self.available_results, dict):
            for key, values in self.available_results.items():
                d[key.value[0]] = [x.value[0] for x in values]
        if isinstance(self.available_results, list):
            d = [x.value[0] for x in self.available_results]

        return d

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

    def get_inter_area_flows(self, area_names, F, T, Sf, hvdc_F, hvdc_T, hvdc_Pf, bus_area_indices):

        na = len(area_names)
        x = np.zeros((na, na), dtype=complex)

        for f, t, flow in zip(F, T, Sf):
            a1 = bus_area_indices[f]
            a2 = bus_area_indices[t]
            if a1 != a2:
                x[a1, a2] += flow
                x[a2, a1] -= flow

        for f, t, flow in zip(hvdc_F, hvdc_T, hvdc_Pf):
            a1 = bus_area_indices[f]
            a2 = bus_area_indices[t]
            if a1 != a2:
                x[a1, a2] += flow
                x[a2, a1] -= flow

        return x

    def get_bus_values_per_area(self, bus_values: np.ndarray, area_names, bus_area_indices):

        na = len(area_names)
        x = np.zeros(na, dtype=bus_values.dtype)

        for a, val in zip(bus_area_indices, bus_values):
            x[a] += val

        return x

    def get_branch_values_per_area(self, branch_values: np.ndarray, area_names, bus_area_indices, F, T):

        na = len(area_names)
        x = np.zeros((na, na), dtype=branch_values.dtype)

        for f, t, val in zip(F, T, branch_values):
            a1 = bus_area_indices[f]
            a2 = bus_area_indices[t]
            x[a1, a2] += val

        return x

    def get_hvdc_values_per_area(self, hvdc_values: np.ndarray, area_names, bus_area_indices, hvdc_F, hvdc_T):

        na = len(area_names)
        x = np.zeros((na, na), dtype=hvdc_values.dtype)

        for f, t, val in zip(hvdc_F, hvdc_T, hvdc_values):
            a1 = bus_area_indices[f]
            a2 = bus_area_indices[t]
            x[a1, a2] += val

        return x

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        pass
