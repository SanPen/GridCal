# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import TYPE_CHECKING, Union, List
import numpy as np
import pandas as pd
from VeraGridEngine.Simulations.driver_template import DriverTemplate
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType, SimulationTypes
from VeraGridEngine.basic_structures import IntVec

if TYPE_CHECKING:  # Only imports the below statements during type checking
    from VeraGridEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults
    from VeraGridEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults


class InputsAnalysisResults(ResultsTemplate):
    tpe = 'Inputs Analysis'

    def __init__(self,
                 grid: MultiCircuit,
                 opf_results: Union[None, OptimalPowerFlowResults] = None,
                 opf_time_series_results: Union[None, OptimalPowerFlowTimeSeriesResults] = None):
        """
        Construct the analysis
        :param grid:
        """
        if grid.get_time_number() > 0:
            available_results = {ResultTypes.SnapshotResults: [ResultTypes.ZoneAnalysis,
                                                               ResultTypes.AreaAnalysis,
                                                               ResultTypes.CountryAnalysis
                                                               ],
                                 ResultTypes.SeriesResults: [ResultTypes.AreaGenerationAnalysis,
                                                             ResultTypes.ZoneGenerationAnalysis,
                                                             ResultTypes.CountryGenerationAnalysis,
                                                             ResultTypes.AreaLoadAnalysis,
                                                             ResultTypes.ZoneLoadAnalysis,
                                                             ResultTypes.CountryLoadAnalysis,
                                                             ResultTypes.AreaBalanceAnalysis,
                                                             ResultTypes.ZoneBalanceAnalysis,
                                                             ResultTypes.CountryBalanceAnalysis
                                                             ]
                                 }
        else:
            available_results = {ResultTypes.SnapshotResults: [ResultTypes.ZoneAnalysis,
                                                               ResultTypes.AreaAnalysis,
                                                               ResultTypes.CountryAnalysis
                                                               ]
                                 }

        ResultsTemplate.__init__(self,
                                 name='Inputs analysis',
                                 available_results=available_results,
                                 time_array=None,
                                 clustering_results=None,
                                 study_results_type=StudyResultsType.InputsAnalysis)

        self.grid = grid
        self.opf_results = opf_results
        self.opf_time_series_results = opf_time_series_results

        self.area_names = list(set([elm.name for elm in grid.areas]))
        self.zone_names = list(set([elm.name for elm in grid.zones]))
        self.country_names = list(set([elm.name for elm in grid.countries]))

        self.gen_data = self.get_generators_df()
        self.battery_data = self.get_batteries_df()
        self.load_data = self.get_loads_df()
        self.static_gen_data = self.get_static_generators_df()

        self.bus_dict = self.grid.get_bus_index_dict()
        self.bus_area_indices = self.get_bus_area_indices()
        self.bus_zone_indices = self.get_bus_zone_indices()
        self.bus_country_indices = self.get_bus_country_indices()

    def get_generators_df(self) -> pd.DataFrame:
        """

        :return:
        """
        dta = list()
        for k, elm in enumerate(self.grid.get_generators()):

            if self.opf_results is None:
                P = elm.P * elm.active
            else:
                P = self.opf_results.generator_power[k] - self.opf_results.generator_shedding[k]

            dta.append([elm.name,
                        P,
                        elm.Pf,
                        elm.Snom,
                        elm.Pmin, elm.Pmax,
                        elm.Qmin, elm.Qmax,
                        elm.Vset,
                        elm.bus.zone.name if elm.bus.zone is not None else "",
                        elm.bus.area.name if elm.bus.area is not None else "",
                        elm.bus.substation.name if elm.bus.substation is not None else "",
                        elm.bus.country.name if elm.bus.country is not None else ""])
        cols = ['Name', 'P', 'Pf',
                'Snom', 'Pmin', 'Pmax',
                'Qmin', 'Qmax', 'Vset',
                'Zone', 'Area', 'Substation', 'Country']
        return pd.DataFrame(data=dta, columns=cols)

    def get_batteries_df(self) -> pd.DataFrame:
        """

        :return:
        """
        dta = list()
        for elm in self.grid.get_batteries():
            dta.append([elm.name,
                        elm.P * elm.active,
                        elm.Pf,
                        elm.Snom,
                        elm.Pmin, elm.Pmax,
                        elm.Qmin, elm.Qmax,
                        elm.Vset,
                        elm.bus.zone.name if elm.bus.zone is not None else "",
                        elm.bus.area.name if elm.bus.area is not None else "",
                        elm.bus.substation.name if elm.bus.substation is not None else "",
                        elm.bus.country.name if elm.bus.country is not None else ""])
        cols = ['Name', 'P', 'Pf',
                'Snom', 'Pmin', 'Pmax',
                'Qmin', 'Qmax', 'Vset',
                'Zone', 'Area', 'Substation', 'Country']
        return pd.DataFrame(data=dta, columns=cols)

    def get_loads_df(self) -> pd.DataFrame:
        """

        :return:
        """
        dta = list()
        for elm in self.grid.get_loads():
            dta.append([elm.name,
                        elm.P * elm.active,
                        elm.Q * elm.active,
                        elm.bus.zone.name if elm.bus.zone is not None else "",
                        elm.bus.area.name if elm.bus.area is not None else "",
                        elm.bus.substation.name if elm.bus.substation is not None else "",
                        elm.bus.country.name if elm.bus.country is not None else ""])
        cols = ['Name', 'P', 'Q',
                'Zone', 'Area', 'Substation', 'Country']
        return pd.DataFrame(data=dta, columns=cols)

    def get_static_generators_df(self) -> pd.DataFrame:
        """

        :return:
        """
        dta = list()
        for elm in self.grid.get_static_generators():
            dta.append([elm.name,
                        elm.P * elm.active,
                        elm.Q * elm.active,
                        elm.bus.zone.name if elm.bus.zone is not None else "",
                        elm.bus.area.name if elm.bus.area is not None else "",
                        elm.bus.substation.name if elm.bus.substation is not None else "",
                        elm.bus.country.name if elm.bus.country is not None else ""])
        cols = ['Name', 'P', 'Q',
                'Zone', 'Area', 'Substation', 'Country']
        return pd.DataFrame(data=dta, columns=cols)

    def group_by(self, group: str):
        """
        Return a DataFrame grouped by Area, Zone or Country
        :param group: "Area", "Zone" or "Country"
        :return: Group DataFrame
        """
        if group == 'Area':
            labels = self.area_names
        elif group == 'Zone':
            labels = self.zone_names
        elif group == 'Country':
            labels = self.country_names
        else:
            raise Exception('Unknown grouping:' + str(group))

        n = len(labels)
        cols_gen = ['P', 'Pmin', 'Pmax', 'Qmin', 'Qmax']
        cols_load = ['P', 'Q']
        cols = ['P', 'Pgen', 'Pload', 'Pbatt', 'Pstagen', 'Pmin', 'Pmax', 'Q', 'Qmin', 'Qmax']
        df = pd.DataFrame(data=np.zeros((n, len(cols))), columns=cols, index=labels)

        if len(self.gen_data):
            df2 = self.gen_data.groupby(group).sum()
            df[cols_gen] += df2[cols_gen]
            df['Pgen'] = df2['P']

        if len(self.battery_data):
            df2 = self.battery_data.groupby(group).sum()
            df[cols_gen] += df2[cols_gen]
            df['Pbatt'] = df2['P']

        if len(self.load_data):
            df2 = self.load_data.groupby(group).sum()
            df[cols_load] -= df2[cols_load]
            df['Pload'] = df2['P']

        if len(self.static_gen_data):
            df2 = self.static_gen_data.groupby(group).sum()
            df[cols_load] += df2[cols_load]
            df['Pstagen'] = df2['P']

        df.fillna(0, inplace=True)

        return df

    def get_bus_zone_indices(self) -> IntVec:
        """

        :return:
        """
        d = {elm: i for i, elm in enumerate(self.grid.zones)}
        return np.array([d.get(bus.zone, "") for bus in self.grid.buses])

    def get_bus_area_indices(self) -> IntVec:
        """

        :return:
        """
        d = {elm: i for i, elm in enumerate(self.grid.areas)}
        return np.array([d.get(bus.area, "") for bus in self.grid.buses])

    def get_bus_country_indices(self) -> IntVec:
        """

        :return:
        """
        d = {elm: i for i, elm in enumerate(self.grid.countries)}
        return np.array([d.get(bus.country, "") for bus in self.grid.buses])

    def get_bus_substation_indices(self) -> IntVec:
        """

        :return:
        """
        d = {elm: i for i, elm in enumerate(self.grid.substations)}
        return np.array([d.get(bus.substation, "") for bus in self.grid.buses])

    def get_collection_attr_series(self, elms, magnitude: str, aggregation="Area"):
        """

        :param elms:
        :param magnitude:snaphot property name
        :param aggregation:
        :return:
        """
        if aggregation == 'Zone':
            d2 = self.get_bus_zone_indices()
            headers = [e.name for e in self.grid.zones]
            ne = len(self.grid.zones)

        elif aggregation == 'Area':
            d2 = self.get_bus_area_indices()
            headers = [e.name for e in self.grid.areas]
            ne = len(self.grid.areas)

        elif aggregation == 'Substation':
            d2 = self.get_bus_substation_indices()
            headers = [e.name for e in self.grid.substations]
            ne = len(self.grid.substations)

        elif aggregation == 'Country':
            d2 = self.get_bus_country_indices()
            headers = [e.name for e in self.grid.countries]
            ne = len(self.grid.countries)

        else:
            raise Exception('Unknown Aggregation. Possible aggregations are Zone, Area, Substation, Country')

        nt = self.grid.get_time_number()
        x = np.zeros((nt, ne))

        for elm in elms:
            i = self.bus_dict[elm.bus]
            i2 = d2[i]
            if i2 != "":
                i3 = int(i2)
                x[:, i3] += elm.get_profile(magnitude=magnitude).toarray()

        return x, headers

    def mdl(self, result_type: ResultTypes) -> "ResultsTable":
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results
                (or None if the result was not understood)
        """

        if result_type == ResultTypes.ZoneAnalysis:
            df = self.group_by('Zone')

            return ResultsTable(data=df.values,
                                index=df.index.values,
                                idx_device_type=DeviceType.ZoneDevice,
                                columns=df.columns.values,
                                cols_device_type=DeviceType.ZoneDevice,
                                title=result_type.value)

        elif result_type == ResultTypes.AreaAnalysis:
            df = self.group_by('Area')
            return ResultsTable(data=df.values,
                                index=df.index.values,
                                idx_device_type=DeviceType.AreaDevice,
                                columns=df.columns.values,
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value)

        elif result_type == ResultTypes.CountryAnalysis:
            df = self.group_by('Country')
            return ResultsTable(data=df.values,
                                index=df.index.values,
                                idx_device_type=DeviceType.CountryDevice,
                                columns=df.columns.values,
                                cols_device_type=DeviceType.CountryDevice,
                                title=result_type.value)

        elif result_type == ResultTypes.AreaGenerationAnalysis:
            generators = self.grid.get_generators() + self.grid.get_batteries() + self.grid.get_static_generators()
            y, columns = self.get_collection_attr_series(generators, 'P', 'Area')

            return ResultsTable(data=y,
                                index=pd.to_datetime(self.grid.time_profile),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=columns,
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                units="(MW)")

        elif result_type == ResultTypes.ZoneGenerationAnalysis:
            generators = self.grid.get_generators() + self.grid.get_batteries() + self.grid.get_static_generators()
            y, columns = self.get_collection_attr_series(generators, 'P', 'Zone')

            return ResultsTable(data=y,
                                index=pd.to_datetime(self.grid.time_profile),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=columns,
                                cols_device_type=DeviceType.ZoneDevice,
                                title=result_type.value,
                                units="(MW)")

        elif result_type == ResultTypes.CountryGenerationAnalysis:
            generators = self.grid.get_generators() + self.grid.get_batteries() + self.grid.get_static_generators()
            y, columns = self.get_collection_attr_series(generators, 'P', 'Country')

            return ResultsTable(data=y,
                                index=pd.to_datetime(self.grid.time_profile),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=columns,
                                cols_device_type=DeviceType.CountryDevice,
                                title=result_type.value,
                                units="(MW)")

        elif result_type == ResultTypes.AreaLoadAnalysis:
            y, columns = self.get_collection_attr_series(self.grid.get_loads(), 'P', 'Area')
            return ResultsTable(data=y,
                                index=pd.to_datetime(self.grid.time_profile),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=columns,
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                units="(MW)")

        elif result_type == ResultTypes.ZoneLoadAnalysis:
            y, columns = self.get_collection_attr_series(self.grid.get_loads(), 'P', 'Zone')
            return ResultsTable(data=y,
                                index=pd.to_datetime(self.grid.time_profile),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=columns,
                                cols_device_type=DeviceType.ZoneDevice,
                                title=result_type.value,
                                units="(MW)")

        elif result_type == ResultTypes.CountryLoadAnalysis:
            y, columns = self.get_collection_attr_series(self.grid.get_loads(), 'P', 'Country')
            return ResultsTable(data=y,
                                index=pd.to_datetime(self.grid.time_profile),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=columns,
                                cols_device_type=DeviceType.CountryDevice,
                                title=result_type.value,
                                units="(MW)")

        elif result_type == ResultTypes.AreaBalanceAnalysis:
            generators = self.grid.get_generators() + self.grid.get_batteries() + self.grid.get_static_generators()
            yg, columns = self.get_collection_attr_series(generators, 'P', 'Area')

            yl, columns = self.get_collection_attr_series(self.grid.get_loads(), 'P', 'Area')

            y = yg - yl

            return ResultsTable(data=y,
                                index=pd.to_datetime(self.grid.time_profile),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=columns,
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                units="(MW)")

        elif result_type == ResultTypes.ZoneBalanceAnalysis:
            generators = self.grid.get_generators() + self.grid.get_batteries() + self.grid.get_static_generators()
            yg, columns = self.get_collection_attr_series(generators, 'P', 'Zone')

            yl, columns = self.get_collection_attr_series(self.grid.get_loads(), 'P', 'Zone')

            y = yg - yl

            return ResultsTable(data=y,
                                index=pd.to_datetime(self.grid.time_profile),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=columns,
                                cols_device_type=DeviceType.ZoneDevice,
                                title=result_type.value,
                                units="(MW)")

        elif result_type == ResultTypes.CountryBalanceAnalysis:
            generators = self.grid.get_generators() + self.grid.get_batteries() + self.grid.get_static_generators()
            yg, columns = self.get_collection_attr_series(generators, 'P', 'Country')

            yl, columns = self.get_collection_attr_series(self.grid.get_loads(), 'P', 'Country')

            y = yg - yl

            return ResultsTable(data=y,
                                index=pd.to_datetime(self.grid.time_profile),
                                idx_device_type=DeviceType.TimeDevice,
                                columns=columns,
                                cols_device_type=DeviceType.CountryDevice,
                                title=result_type.value,
                                units="(MW)")

        else:
            raise Exception('Result type not understood:' + str(result_type))


class InputsAnalysisDriver(DriverTemplate):
    name = 'Inputs Analysis'
    tpe = SimulationTypes.InputsAnalysis_run

    def __init__(self, grid: MultiCircuit):
        """
        InputsAnalysisDriver class constructor
        :param grid: MultiCircuit instance
        """
        DriverTemplate.__init__(self, grid=grid)

        self.tic()
        self.results = InputsAnalysisResults(grid=grid)
        self.toc()

    def get_steps(self) -> List[int]:
        """

        :return:
        """
        return list()

    def run(self) -> None:
        """
        Pack run_pf for the QThread
        :return:
        """
        pass

    def cancel(self):
        self.__cancel__ = True
