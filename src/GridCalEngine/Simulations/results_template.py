# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Union, TYPE_CHECKING

from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.basic_structures import (IntVec, IntMat, Vec, CxVec, StrVec, StrMat, Mat, DateVec, CxMat, BoolVec,
                                            Logger)
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, SimulationTypes
from GridCalEngine.Devices.multi_circuit import MultiCircuit

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from GridCalEngine.Simulations.Clustering.clustering_results import ClusteringResults


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
            clustering_results: Union[ClusteringResults, None],
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

        self.available_results: Dict[ResultTypes, List[ResultTypes]] = available_results

        self.data_variables: Dict[str, ResultsProperty] = dict()

        self._time_array: Union[DateVec, None] = time_array

        if clustering_results:
            self.clustering_results = clustering_results
            self.using_clusters = True
            self.time_indices: IntVec | None = clustering_results.time_indices
            self.sampled_probabilities: Vec | None = clustering_results.sampled_probabilities
            self.original_sample_idx: IntVec | None = clustering_results.original_sample_idx
        else:
            self.clustering_results = None
            self.using_clusters = False
            self.time_indices: IntVec | None = None
            self.sampled_probabilities: Vec | None = None
            self.original_sample_idx: IntVec | None = None

        # vars for the inter-area computation
        self.F: IntVec | None = None
        self.T: IntVec | None = None
        self.hvdc_F: IntVec | None = None
        self.hvdc_T: IntVec | None = None
        self.bus_area_indices: IntVec | None = None
        self.area_names: StrVec | None = None

        self.__show_plot = True

    @property
    def time_array(self) -> DateVec:
        """
        Array of time steps
        :return:
        """
        return self._time_array

    @time_array.setter
    def time_array(self, time_array: DateVec):
        self._time_array = time_array

    def plotting_allowed(self) -> bool:
        """

        :return:
        """
        return self.__show_plot

    def activate_plotting(self):
        """

        :return:
        """
        self.__show_plot = True

    def deactivate_plotting(self):
        """

        :return:
        """
        self.__show_plot = False

    def register(self, name: str, tpe: Union[Vec, Mat, CxVec, CxMat], old_names: Union[None, List[str]] = None):
        """
        Register a results variable for disk persistence
        :param name: name of the variable to register (is checked)
        :param tpe: type of the variable
        :param old_names: list of old names for retro compatibility (optional)
        """

        assert (hasattr(self, name))  # the property must exist, this avoids bugs when registering

        self.data_variables[name] = ResultsProperty(name=name,
                                                    tpe=tpe,
                                                    old_names=list() if old_names is None else old_names)

    def consolidate_after_loading(self):
        """
        Consolidate
        """
        pass

    def get_dict(self) -> Dict[str, Any]:
        """
        Get data to pass via json
        :return:
        """
        data = dict()

        # traverse the registered results
        for arr_name, arr_prop in self.data_variables.items():

            # get the array
            arr: np.ndarray = getattr(self, arr_name)

            if arr_prop.tpe in (CxVec, CxMat):
                r = arr.real
                i = arr.imag
                data[arr_name] = {
                    "real": r.tolist(),
                    "imag": i.tolist(),
                }
            elif arr_prop.tpe in (Vec, Mat, IntVec, IntMat, StrVec, StrMat, BoolVec):
                if isinstance(arr, np.ndarray):
                    data[arr_name] = arr.tolist()
                elif isinstance(arr, list):
                    data[arr_name] = arr

            elif arr_prop.tpe == DateVec:
                data[arr_name] = arr.values.astype(float).tolist()  # pass the unix nano-seconds

            else:
                if isinstance(arr, list):
                    data[arr_name] = arr
                elif isinstance(arr, dict):
                    data[arr_name] = arr
                else:
                    data[arr_name] = arr

        return data

    def parse_data(self, data: Dict[str, Any | Dict[str, Any]]):
        """
        The function to parse the data created with get_dict
        :param data:
        :return:
        """

        for arr_name, arr_prop in self.data_variables.items():

            arr_data = data.get(arr_name, None)

            if arr_prop.tpe in (CxVec, CxMat):
                r = np.array(arr_data["real"])
                i = np.array(arr_data["imag"])
                arr = r + 1j * i
                setattr(self, arr_name, arr)

            elif arr_prop.tpe in (Vec, Mat, IntVec, IntMat, StrVec, StrMat, BoolVec):
                arr = np.array(arr_data)
                setattr(self, arr_name, arr)

            elif arr_prop.tpe == DateVec:

                arr = pd.to_datetime(np.array(arr_data), unit='ns')  # pass the unix nano-seconds
                setattr(self, arr_name, arr)

            else:
                data[arr_name] = arr_data

    def get_name_to_results_type_dict(self):
        """

        :return:
        """
        d = dict()
        if isinstance(self.available_results, dict):
            for key, values in self.available_results.items():
                for item in values:
                    d[item.value] = item

        if isinstance(self.available_results, list):
            for item in self.available_results:
                d[item.value] = item

        return d

    def get_name_tree(self):
        """

        :return:
        """
        d = dict()
        if isinstance(self.available_results, dict):
            for key, values in self.available_results.items():
                d[key.value] = [x.value for x in values]
        if isinstance(self.available_results, list):
            d = [x.value for x in self.available_results]

        return d

    def to_json(self, file_name):
        """
        Export as json
        :param file_name: File name
        """

        with open(file_name, "w") as output_file:
            json_str = json.dumps(self.get_dict())
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

        if na > 0:
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

    @staticmethod
    def get_bus_values_per_area(bus_values: Vec, area_names: StrVec, bus_area_indices: IntVec) -> Vec:
        """
        Split array of bus-related values per area
        :param bus_values:
        :param area_names:
        :param bus_area_indices:
        :return:
        """
        na = len(area_names)
        x = np.zeros(na, dtype=bus_values.dtype)

        if na > 0:
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

        if na > 0:
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

        if na > 0:
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
        self.area_names, self.bus_area_indices, self.F, self.T, self.hvdc_F, self.hvdc_T = grid.get_branch_areas_info()

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

                    if value.dtype in [float, complex, bool]:  # only expand float, complex and bool

                        if value.ndim == 1:

                            if len(value) > 0:
                                arr = value[self.original_sample_idx]  # expand
                                setattr(self, prop, arr)  # overwrite the array

                        elif value.ndim == 2:

                            if value.shape[0] > 0:
                                arr = value[self.original_sample_idx, :]  # expand
                                setattr(self, prop, arr)  # overwrite the array
                        else:
                            pass
                            # print(prop, value.ndim, value.dtype)
                    else:
                        pass
                        # print(prop, value.ndim, value.dtype)

    def parse_saved_data(self, grid: MultiCircuit,
                         data_dict: Dict[str, pd.DataFrame],
                         logger: Logger = Logger()) -> None:
        """

        :param grid: MultiCircuit
        :param data_dict: Dictionary with the info loaded from disk
        :param logger: Logger
        :return:
        """
        self.time_array = grid.get_time_array()

        for arr_name, df in data_dict.items():

            is_complex = '__complex__' in arr_name
            arr_name = arr_name.replace('__complex__', '')

            # try to get the property of the saved file
            res_prop: ResultsProperty = self.data_variables.get(arr_name, None)

            if df is not None and res_prop is not None:

                # it may be complex...
                if is_complex:
                    split_pt = int(df.columns.size / 2)
                    r = df.values[:, :split_pt]
                    i = df.values[:, split_pt:]
                    array = r + 1j * i
                else:
                    # keep the 2D shape
                    array = df.values

                if array.shape[1] == 1:
                    # if there is only one column, convert to array directly
                    array = array[:, 0]

                # it may be a single number...
                if res_prop.tpe in [int, float, complex]:
                    if array.size == 1:
                        array = array[0]

                curr_value = getattr(self, res_prop.name)

                if isinstance(curr_value, np.ndarray):
                    if curr_value.shape == array.shape:
                        setattr(self, res_prop.name, array)
                    else:
                        logger.add_error(msg="Wrong array shape",
                                         device_class=self.name,
                                         device_property=res_prop.name,
                                         value=str(array.shape),
                                         expected_value=str(curr_value.shape))
                else:
                    setattr(self, res_prop.name, array)


class DriverToSave:
    """
    Wrapper to save a driver
    """

    def __init__(self,
                 name: str,
                 tpe: SimulationTypes,
                 results: ResultsTemplate,
                 logger: Logger):
        """

        :param name:
        :param tpe:
        :param results:
        :param logger:
        """
        self.name = name
        self.tpe = tpe
        self.results = results
        self.logger = logger
