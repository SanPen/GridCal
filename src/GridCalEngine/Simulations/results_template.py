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

from GridCalEngine.Simulations.result_types import ResultTypes
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.basic_structures import IntVec, Vec, CxVec, StrVec, Mat, DateVec, CxMat
from GridCalEngine.enumerations import StudyResultsType
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit


class ResultsProperty:
    """
    ResultsProperty
    """

    def __init__(self, name: str,
                 tpe: Union[Vec, Mat, CxVec, CxMat],
                 old_names: List[str]):
        """
        ResultsProperty
        :param name: name of the property
        :param tpe: type of the property (Vec, Mat, double, ...)
        :param old_names: list of previous names. Use in case of renaming a registered property
        """

        self.name = name

        self.tpe = tpe

        self.old_names = old_names


class ResultsTemplate:
    """
    ResultsTemplate
    """

    def __init__(
            self,
            name: str,
            available_results: Union[Dict[ResultTypes, List[ResultTypes]], List[ResultTypes]],
            time_array: Union[DateVec, None],
            clustering_results: Union["ClusteringResults", None],
            study_results_type: StudyResultsType):
        """
        Results template class
        :param name: Name of the class
        :param available_results: list of stuff to represent the results
        :param clustering_results: ClusteringResults object (optional)
        :param study_results_type: StudyResultsType Instance
        """
        self.name: str = name

        self.study_results_type: StudyResultsType = study_results_type

        self.available_results: Dict[ResultTypes: List[ResultTypes]] = available_results

        self.data_variables: Dict[str, ResultsProperty] = dict()

        self.time_array: Union[DateVec, None] = time_array

        if clustering_results:
            self.clustering_results = clustering_results
            self.using_clusters = True
            self.time_indices: IntVec = clustering_results.time_indices
            self.sampled_probabilities: Vec = clustering_results.sampled_probabilities
            self.original_sample_idx: IntVec = clustering_results.original_sample_idx
        else:
            self.clustering_results = None
            self.using_clusters = False
            self.time_indices = None
            self.sampled_probabilities = None
            self.original_sample_idx = None

        # vars for the inter-area computation
        self.F: IntVec = None
        self.T: IntVec = None
        self.hvdc_F: IntVec = None
        self.hvdc_T: IntVec = None
        self.bus_area_indices: IntVec = None
        self.area_names: StrVec = None

    def register(self, name: str, tpe: Union[Vec, Mat, CxVec, CxMat], old_names: List[str] = list()):
        """
        Register a results variable for disk persistence
        :param name: name of the variable to register (is checked)
        :param tpe: type of the variable
        :param old_names: list of old names for retro compatibility
        """

        assert (hasattr(self, name))  # the property must exist, this avoids bugs when registering

        self.data_variables[name] = ResultsProperty(name=name,
                                                    tpe=tpe,
                                                    old_names=old_names)

    def consolidate_after_loading(self):
        """
        Consolidate
        """
        pass

    def get_results_dict(self):
        """

        :return:
        """
        data = dict()

        return data

    def get_name_to_results_type_dict(self):
        """

        :return:
        """
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
        """

        :return:
        """
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

    def apply_new_rates(self, rates: Vec):
        """

        :param rates:
        """
        pass

    def apply_new_time_series_rates(self, rates: Vec):
        """

        :param rates:
        """
        pass

    def get_inter_area_flows(self,
                             area_names: StrVec,
                             F: IntVec,
                             T: IntVec,
                             Sf: CxVec,
                             hvdc_F: IntVec,
                             hvdc_T: IntVec,
                             hvdc_Pf: Vec,
                             bus_area_indices: IntVec) -> Mat:
        """

        :param area_names:
        :param F:
        :param T:
        :param Sf:
        :param hvdc_F:
        :param hvdc_T:
        :param hvdc_Pf:
        :param bus_area_indices:
        :return:
        """
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

    def get_bus_values_per_area(self, bus_values: Vec, area_names: StrVec, bus_area_indices: IntVec) -> Vec:
        """
        Split array of bus-related values per area
        :param bus_values:
        :param area_names:
        :param bus_area_indices:
        :return:
        """
        na = len(area_names)
        x = np.zeros(na, dtype=bus_values.dtype)

        for a, val in zip(bus_area_indices, bus_values):
            x[a] += val

        return x

    def get_branch_values_per_area(self, branch_values: Vec,
                                   area_names: StrVec,
                                   bus_area_indices: IntVec,
                                   F: IntVec, T: IntVec):
        """
        Split array of branch-related values per area
        :param branch_values:
        :param area_names:
        :param bus_area_indices:
        :param F:
        :param T:
        :return:
        """
        na = len(area_names)
        x = np.zeros((na, na), dtype=branch_values.dtype)

        for f, t, val in zip(F, T, branch_values):
            a1 = bus_area_indices[f]
            a2 = bus_area_indices[t]
            x[a1, a2] += val

        return x

    def get_hvdc_values_per_area(self, hvdc_values: Vec, area_names: StrVec, bus_area_indices: IntVec,
                                 hvdc_F: IntVec, hvdc_T: IntVec):
        """
        Split array of hvdc-related values per area
        :param hvdc_values:
        :param area_names:
        :param bus_area_indices:
        :param hvdc_F:
        :param hvdc_T:
        :return:
        """
        na = len(area_names)
        x = np.zeros((na, na), dtype=hvdc_values.dtype)

        for f, t, val in zip(hvdc_F, hvdc_T, hvdc_values):
            a1 = bus_area_indices[f]
            a2 = bus_area_indices[t]
            x[a1, a2] += val

        return x

    def fill_circuit_info(self, grid: MultiCircuit):
        """

        :param grid:
        :return:
        """
        area_dict = {elm: i for i, elm in enumerate(grid.get_areas())}
        bus_dict = grid.get_bus_index_dict()

        self.area_names = [a.name for a in grid.get_areas()]
        self.bus_area_indices = np.array([area_dict.get(b.area, 0) for b in grid.buses])

        branches = grid.get_branches_wo_hvdc()
        self.F = np.zeros(len(branches), dtype=int)
        self.T = np.zeros(len(branches), dtype=int)
        for k, elm in enumerate(branches):
            self.F[k] = bus_dict[elm.bus_from]
            self.T[k] = bus_dict[elm.bus_to]

        hvdc = grid.get_hvdc()
        self.hvdc_F = np.zeros(len(hvdc), dtype=int)
        self.hvdc_T = np.zeros(len(hvdc), dtype=int)
        for k, elm in enumerate(hvdc):
            self.hvdc_F[k] = bus_dict[elm.bus_from]
            self.hvdc_T[k] = bus_dict[elm.bus_to]

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Get results model (overloaded in the respective implementations)
        :param result_type: ResultTypes
        """
        pass

    def expand_clustered_results(self):
        """
        Expand all arrays to their
        """
        if self.using_clusters:

            self.time_array = self.clustering_results.time_array

            for prop, value in self.__dict__.items():

                if isinstance(value, np.ndarray):
                    if value.ndim == 2:

                        nt = len(self.original_sample_idx)
                        ncol = value.shape[1]
                        # arr = np.zeros((nt, ncol), dtype=value.dtype)  # declare an array of matching size
                        # arr[self.time_indices, :] = value  # copy the values where they match
                        arr = value[self.original_sample_idx, :]  # expand
                        setattr(self, prop, arr)  # ovewrite the array
