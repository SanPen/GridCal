
import numpy as np
import pandas as pd
from GridCal.Engine.Simulations.driver_template import DriverTemplate
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Core.multi_circuit import MultiCircuit


class InputsAnalysisResults(ResultsTemplate):

    def __init__(self, grid: MultiCircuit):
        """
        Construct the analysis
        :param grid:
        """
        ResultsTemplate.__init__(self,
                                 name='Inputs analysis',
                                 available_results=[ResultTypes.ZoneAnalysis,
                                                    ResultTypes.AreaAnalysis,
                                                    ResultTypes.CountryAnalysis
                                                    ],

                                 data_variables=[])

        self.grid = grid

        self.area_names = list(set([elm.name for elm in grid.areas]))
        self.zone_names = list(set([elm.name for elm in grid.zones]))
        self.country_names = list(set([elm.name for elm in grid.countries]))

        self.gen_data = self.get_generators_df()
        self.battery_data = self.get_batteries_df()
        self.load_data = self.get_loads_df()
        self.static_gen_data = self.get_static_generators_df()

    def get_generators_df(self):
        """

        :return:
        """
        dta = list()
        for elm in self.grid.get_generators():
            dta.append([elm.name,
                            elm.P * elm.active,
                            elm.Pf,
                            elm.Snom,
                            elm.Pmin, elm.Pmax,
                            elm.Qmin, elm.Qmax,
                            elm.Vset,
                            elm.bus.zone.name,
                            elm.bus.area.name,
                            elm.bus.substation.name,
                            elm.bus.country.name])
        cols = ['Name', 'P', 'Pf',
                'Snom', 'Pmin', 'Pmax',
                'Qmin', 'Qmax', 'Vset',
                'Zone', 'Area', 'Substation', 'Country']
        return pd.DataFrame(data=dta, columns=cols)

    def get_batteries_df(self):
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
                            elm.bus.zone.name,
                            elm.bus.area.name,
                            elm.bus.substation.name,
                            elm.bus.country.name])
        cols = ['Name', 'P', 'Pf',
                'Snom', 'Pmin', 'Pmax',
                'Qmin', 'Qmax', 'Vset',
                'Zone', 'Area', 'Substation', 'Country']
        return pd.DataFrame(data=dta, columns=cols)

    def get_loads_df(self):
        """

        :return:
        """
        dta = list()
        for elm in self.grid.get_loads():
            dta.append([elm.name,
                        elm.P * elm.active,
                        elm.Q * elm.active,
                        elm.bus.zone.name,
                        elm.bus.area.name,
                        elm.bus.substation.name,
                        elm.bus.country.name])
        cols = ['Name', 'P', 'Q',
                'Zone', 'Area', 'Substation', 'Country']
        return pd.DataFrame(data=dta, columns=cols)

    def get_static_generators_df(self):
        """

        :return:
        """
        dta = list()
        for elm in self.grid.get_static_generators():
            dta.append([elm.name,
                        elm.P * elm.active,
                        elm.Q * elm.active,
                        elm.bus.zone.name,
                        elm.bus.area.name,
                        elm.bus.substation.name,
                        elm.bus.country.name])
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

    def mdl(self, result_type) -> "ResultsTable":
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results
                (or None if the result was not understood)
        """

        columns = [result_type.value[0]]

        if result_type == ResultTypes.ZoneAnalysis:
            df = self.group_by('Zone')
            columns = df.columns.values
            labels = df.index.values
            y = df.values
            y_label = ''
            title = result_type.value[0]

        elif result_type == ResultTypes.AreaAnalysis:
            df = self.group_by('Area')
            columns = df.columns.values
            labels = df.index.values
            y = df.values
            y_label = ''
            title = result_type.value[0]

        elif result_type == ResultTypes.CountryAnalysis:
            df = self.group_by('Country')
            columns = df.columns.values
            labels = df.index.values
            y = df.values
            y_label = ''
            title = result_type.value[0]

        else:
            labels = []
            y = np.zeros(0)
            y_label = '(MW)'
            title = ''

        mdl = ResultsTable(data=y,
                           index=labels,
                           columns=columns,
                           title=title,
                           ylabel=y_label,
                           xlabel='',
                           units=y_label)
        return mdl


class InputsAnalysisDriver(DriverTemplate):
    name = 'Inputs Analysis'
    tpe = SimulationTypes.InputsAnalysis_run

    def __init__(self, grid: MultiCircuit):
        """
        InputsAnalysisDriver class constructor
        :param grid: MultiCircuit instance
        """
        DriverTemplate.__init__(self, grid=grid)

        self.results = InputsAnalysisResults(grid=grid)

    def get_steps(self):
        """

        :return:
        """
        return list()

    def run(self):
        """
        Pack run_pf for the QThread
        :return:
        """
        pass

    def cancel(self):
        self.__cancel__ = True


if __name__ == '__main__':
    from GridCal.Engine.IO.file_handler import FileOpen

    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14 - ntc areas.gridcal'
    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE 118 Bus - ntc_areas.gridcal'
    fname = r'C:\Users\SPV86\Documents\Git\GitHub\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

    main_circuit = FileOpen(fname).open()

    drv = InputsAnalysisDriver(grid=main_circuit)

    mdl = drv.results.mdl(ResultTypes.AreaAnalysis)

    df = mdl.to_df()

    print(df)

