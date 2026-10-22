# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Union, TYPE_CHECKING, Tuple

from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.basic_structures import (IntVec, IntMat, Vec, CxVec, StrVec, StrMat, Mat, DateVec, CxMat, BoolVec,
                                             Logger)
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, SimulationTypes
from VeraGridEngine.Devices.multi_circuit import MultiCircuit

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGridEngine.Simulations.Clustering.clustering_results import ClusteringResults


class ResultsProperty:
    """
    ResultsProperty
    """
    __slots__ = (
        "name",
        "tpe",
        "old_names",
        "expandable"
    )

    def __init__(self, name: str,
                 tpe: Any,
                 old_names: Union[List[str], Tuple[str, ...]],
                 expandable: bool) -> None:
        """
        ResultsProperty
        :param name: name of the property
        :param tpe: type of the property (Vec, Mat, double, ...)
        :param old_names: list of previous names. Use in case of renaming a registered property
        """

        self.name: str = name

        self.tpe: Any = tpe

        self.old_names: Tuple[str, ...] = tuple(old_names)

        self.expandable = expandable


class ResultsTemplateMeta(type):
    """
    Metaclass that pre-builds inherited results schema declarations.
    """

    def __new__(mcs: type, name: str, bases: Tuple[type, ...], namespace: Dict[str, Any]) -> type:
        """
        Build a new class and aggregate result declarations from base to child.
        :param name: Class name
        :param bases: Base classes
        :param namespace: Class namespace
        :return: New class
        """
        cls: type = super().__new__(mcs, name, bases, namespace)

        aggregated_declarations: List[ResultsProperty] = list()
        for base in bases:
            base_declarations: Tuple[ResultsProperty, ...] = vars(base).get(
                "CLASS_RESULTS_DECLARATIONS",
                tuple(),
            )
            for declaration in base_declarations:
                aggregated_declarations.append(declaration)

        local_declarations: Tuple[ResultsProperty, ...] = namespace.get("LOCAL_RESULTS_DECLARATIONS", tuple())
        for declaration in local_declarations:
            aggregated_declarations.append(declaration)

        cls.CLASS_RESULTS_DECLARATIONS = tuple(aggregated_declarations)

        class_data_variables: Dict[str, ResultsProperty] = dict()
        for declaration in cls.CLASS_RESULTS_DECLARATIONS:
            prop: ResultsProperty = declaration
            class_data_variables[prop.name] = prop

        cls.CLASS_DATA_VARIABLES = class_data_variables

        return cls


class ResultsTemplate(metaclass=ResultsTemplateMeta):
    """
    ResultsTemplate
    """
    __slots__ = (
        "name",
        "report_text",
        "study_results_type",
        "available_results",
        "_data_variables",
        "_time_array",
        "_is_3ph",
        "clustering_results",
        "using_clusters",
        "time_indices",
        "sampled_probabilities",
        "original_sample_idx",
        "F",
        "T",
        "hvdc_F",
        "hvdc_T",
        "bus_area_indices",
        "area_names",
        "_ResultsTemplate__show_plot",
    )

    def __init__(
            self,
            name: str,
            available_results: Union[Dict[ResultTypes, List[ResultTypes]], List[ResultTypes]],
            # available_results: Union[Dict[ResultTypes, List[ResultTypes]], List[ResultTypes], Dict[ResultTypes, Dict[ResultTypes, List[ResultTypes]]], List[ResultTypes, Dict[ResultTypes, Dict[ResultTypes, List[ResultTypes]]]]],
            time_array: Union[DateVec, None],
            clustering_results: Union[ClusteringResults, None],
            study_results_type: StudyResultsType,
            is_3ph: bool = False):
        """
        Results template class
        :param name: Name of the class
        :param available_results: list of stuff to represent the results
        :param clustering_results: ClusteringResults object (optional)
        :param study_results_type: StudyResultsType Instance
        :param is_3ph: is this a 3-phase result?
        """
        self.name: str = name

        self.report_text: str = ""

        self.study_results_type: StudyResultsType = study_results_type

        self.available_results: Dict[ResultTypes, List[ResultTypes]] = available_results

        self._data_variables: Dict[str, ResultsProperty] = type(self).CLASS_DATA_VARIABLES

        self._time_array: Union[DateVec, None] = time_array

        self._is_3ph = is_3ph

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
    def data_variables(self) -> Dict[str, ResultsProperty]:
        """

        :return:
        """
        return type(self).CLASS_DATA_VARIABLES

    @property
    def time_array(self) -> DateVec | None:
        """
        Array of time steps
        :return:
        """
        return self._time_array

    @time_array.setter
    def time_array(self, time_array: DateVec):
        self._time_array = time_array

    @property
    def is_3ph(self):
        return self._is_3ph

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

    def register(self, name: str, tpe: Union[Vec, Mat, CxVec, CxMat], old_names: Union[None, List[str]] = None) -> None:
        """
        Runtime registration is intentionally disabled.
        :param name: name of the variable to register (is checked)
        :param tpe: type of the variable
        :param old_names: list of old names for retro compatibility (optional)
        :return: None
        """
        raise RuntimeError(
            "Runtime results registration is disabled. "
            "Declare results in LOCAL_RESULTS_DECLARATIONS."
        )

    def consolidate_after_loading(self):
        """
        Consolidate
        """
        pass

    def prepare_for_saving(self) -> None:
        """
        Refresh any derived payload that must be serialized with the results.

        :return: None.
        """
        pass

    def get_dict(self) -> Dict[str, Any]:
        """
        Get data to pass via json
        :return:
        """
        data = dict()

        # traverse the registered results
        for arr_name, arr_prop in self._data_variables.items():

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

        for arr_name, arr_prop in self._data_variables.items():

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

    def get_results_type_dict(self) -> Dict[ResultTypes, ResultTypes]:
        """
        Get result types keyed by their enum identity.

        :return: Dictionary mapping each result type to itself.
        """
        d: Dict[ResultTypes, ResultTypes] = dict()
        if isinstance(self.available_results, dict):
            for key, values in self.available_results.items():
                for item in values:
                    d[item] = item

        if isinstance(self.available_results, list):
            for item in self.available_results:
                d[item] = item

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

    def get_results_type_tree(self) -> Union[Dict[ResultTypes, List[ResultTypes]], List[ResultTypes]]:
        """
        Get the result tree using enum values as runtime payloads.

        :return: Result type tree.
        """
        d: Union[Dict[ResultTypes, List[ResultTypes]], List[ResultTypes]] = dict()
        if isinstance(self.available_results, dict):
            for key, values in self.available_results.items():
                d[key] = list(values)
        if isinstance(self.available_results, list):
            d = list(self.available_results)

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

    def fill_simulation_info(self, grid: MultiCircuit):
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
        Expand all arrays using the clustering info
        """

        if self.using_clusters:

            if self.clustering_results is not None:

                # Replace the reduced time array by the expanded time array
                self.time_array = self.clustering_results.time_array

                # NOTE: You might be tempted to change this loop to use the registered properties.
                #       Don't do it, there may be unregistered properties that will fail if this doesn't
                #       traverse all the actual properties of the class... this may be a future topic
                for prop in self.CLASS_RESULTS_DECLARATIONS:
                    if prop.expandable:

                        value: np.ndarray = getattr(self, prop.name)

                        if value.ndim == 1:

                            if len(value) > 0:
                                try:
                                    arr = value[self.original_sample_idx]  # expand
                                    setattr(self, prop.name, arr)  # overwrite the array
                                except IndexError as e:
                                    print(f"Index error in expand_clustered_results (1D) for {prop}")

                        elif value.ndim == 2:

                            if value.shape[0] > 0:
                                try:
                                    arr = value[self.original_sample_idx, :]  # expand
                                    setattr(self, prop.name, arr)  # overwrite the array
                                except IndexError as e:
                                    print(f"Index error in expand_clustered_results (2D) for {prop}")
                        else:
                            pass
            else:
                print("No clusters!")

    def parse_saved_data(self, grid: MultiCircuit,
                         data_dict: Dict[str, pd.DataFrame | np.ndarray],
                         logger: Logger = Logger()) -> None:
        """

        :param grid: MultiCircuit
        :param data_dict: Dictionary with the info loaded from disk
        :param logger: Logger
        :return:
        """
        self.time_array = grid.get_time_array()

        for arr_name, stored_data in data_dict.items():

            is_complex = '__complex__' in arr_name
            arr_name = arr_name.replace('__complex__', '')

            # try to get the property of the saved file
            res_prop: ResultsProperty = self._data_variables.get(arr_name, None)

            if stored_data is not None and res_prop is not None:

                # it may be complex...
                if is_complex:
                    values_2d: np.ndarray
                    if isinstance(stored_data, pd.DataFrame):
                        values_2d = stored_data.values
                    else:
                        values_2d = np.asarray(stored_data)

                    split_pt = int(values_2d.shape[1] / 2)
                    r = values_2d[:, :split_pt]
                    i = values_2d[:, split_pt:]
                    array = r + 1j * i
                else:
                    if isinstance(stored_data, pd.DataFrame):
                        # Keep the 2-D shape for the historical parquet path.
                        array = stored_data.values
                    else:
                        # NumPy payloads are already restored with their native shape.
                        array = np.asarray(stored_data)

                vector_like_types = (Vec, IntVec, StrVec, BoolVec, CxVec)

                if (
                        isinstance(array, np.ndarray)
                        and array.ndim == 2
                        and array.shape[1] == 1
                        and res_prop.tpe in vector_like_types
                ):
                    # if there is only one column, convert to array directly
                    array = array[:, 0]

                # it may be a single number...
                if res_prop.tpe in [int, float, complex]:
                    if array.size == 1:
                        # Parquet stores scalars as 1x1 tables; restore a Python scalar.
                        array = array.item()
                    else:
                        pass
                else:
                    pass

                if res_prop.tpe == DateVec:
                    array = pd.to_datetime(np.asarray(array).reshape(-1))
                else:
                    pass

                curr_value = getattr(self, res_prop.name)

                if isinstance(curr_value, (np.ndarray, pd.Index)):

                    # if results arrays are exactly 0, don't check
                    curr_shape = np.shape(curr_value)
                    dont_check = len(curr_shape) > 0 and sum(curr_shape) == 0
                    both_empty = (
                        isinstance(array, np.ndarray)
                        and isinstance(curr_value, np.ndarray)
                        and array.size == 0
                        and curr_value.size == 0
                    )

                    if np.shape(curr_value) == np.shape(array) or dont_check:
                        setattr(self, res_prop.name, array)
                    elif both_empty:
                        pass
                    else:
                        logger.add_error(msg="Wrong array shape",
                                         device_class=self.name,
                                         device_property=res_prop.name,
                                         value=str(np.shape(array)),
                                         expected_value=str(np.shape(curr_value)))
                else:
                    setattr(self, res_prop.name, array)
