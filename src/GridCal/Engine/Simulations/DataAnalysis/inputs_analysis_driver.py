
import numpy as np
import pandas as pd
from GridCal.Engine.Simulations.driver_template import DriverTemplate
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.results_template import ResultsTemplate
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Core.multi_circuit import MultiCircuit


class DataAnalysisResults(ResultsTemplate):
    """
    OPF results.

    Arguments:

        **Sbus**: bus power injections

        **voltage**: bus voltages

        **load_shedding**: load shedding values

        **Sf**: branch power values

        **overloads**: branch overloading values

        **loading**: branch loading values

        **losses**: branch losses

        **converged**: converged?
    """

    def __init__(self, grid: MultiCircuit):

        ResultsTemplate.__init__(self,
                                 name='Data analysis',
                                 available_results=[ResultTypes.BusVoltageModule,
                                                    ResultTypes.BusVoltageAngle,
                                                    ResultTypes.BranchPower,
                                                    ResultTypes.BranchLoading,
                                                    ResultTypes.BranchOverloads,
                                                    ResultTypes.ContingencyFlows,
                                                    ResultTypes.ContingencyLoading,
                                                    ResultTypes.BranchTapAngle,
                                                    ResultTypes.HvdcPowerFrom,
                                                    ResultTypes.HvdcOverloads,
                                                    ResultTypes.NodeSlacks,
                                                    ResultTypes.BatteryPower,
                                                    ResultTypes.ControlledGeneratorPower,
                                                    ResultTypes.GenerationDelta,
                                                    ResultTypes.GenerationDeltaSlacks,
                                                    ResultTypes.AvailableTransferCapacityAlpha,
                                                    ResultTypes.InterAreaExchange
                                                    ],

                                 data_variables=[])

        gen_dta = list()
        for elm in grid.get_generators():
            gen_dta.append([elm.name,
                            elm.P,
                            elm.Pf,
                            elm.Snom,
                            elm.Pmax, elm.Pmin,
                            elm.Qmax, elm.Qmin,
                            elm.Vset,
                            elm.bus.zone.name,
                            elm.bus.area.name,
                            elm.bus.substation.name,
                            elm.bus.country.name])
        for elm in grid.get_batteries():
            gen_dta.append([elm.name,
                            elm.P,
                            elm.Pf,
                            elm.Snom,
                            elm.Pmax, elm.Pmin,
                            elm.Qmax, elm.Qmin,
                            elm.Vset,
                            elm.bus.zone.name,
                            elm.bus.area.name,
                            elm.bus.substation.name,
                            elm.bus.country.name])
        cols = ['Name', 'P', 'Pf',
                'Snom', 'Pmin', 'Pmax',
                'Qmin', 'Qmax', 'Vset',
                'Zone', 'Area', 'Substation', 'Country']
        self.gen_data = pd.DataFrame(data=gen_dta, columns=cols)

        ld_dta = list()
        for elm in grid.get_loads():
            ld_dta.append([elm.name,
                           -elm.P,
                           -elm.Q,
                           elm.bus.zone.name,
                           elm.bus.area.name,
                           elm.bus.substation.name,
                           elm.bus.country.name])
        for elm in grid.get_static_generators():
            ld_dta.append([elm.name,
                           elm.P,
                           elm.Q,
                           elm.bus.zone.name,
                           elm.bus.area.name,
                           elm.bus.substation.name,
                           elm.bus.country.name])
        cols = ['Name', 'P', 'Q',
                'Zone', 'Area', 'Substation', 'Country']
        self.load_data = pd.DataFrame(data=ld_dta, columns=cols)

    def mdl(self, result_type) -> "ResultsTable":
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results
                (or None if the result was not understood)
        """

        columns = [result_type.value[0]]

        if result_type == ResultTypes.BusVoltageModule:
            labels = self.bus_names
            y = np.abs(self.voltage)
            y_label = '(p.u.)'
            title = 'Bus voltage module'

        elif result_type == ResultTypes.BusVoltageAngle:
            labels = self.bus_names
            y = np.angle(self.voltage)
            y_label = '(Radians)'
            title = 'Bus voltage angle'

        elif result_type == ResultTypes.BranchPower:
            labels = self.branch_names
            y = self.Sf.real
            y_label = '(MW)'
            title = 'Branch power'

        elif result_type == ResultTypes.BusPower:
            labels = self.bus_names
            y = self.Sbus.real
            y_label = '(MW)'
            title = 'Bus power'

        elif result_type == ResultTypes.BranchLoading:
            labels = self.branch_names
            y = self.loading * 100.0
            y_label = '(%)'
            title = 'Branch loading'

        elif result_type == ResultTypes.BranchOverloads:
            labels = self.branch_names
            y = np.abs(self.overloads)
            y_label = '(MW)'
            title = 'Branch overloads'

        elif result_type == ResultTypes.ContingencyFlows:
            labels = self.branch_names
            columns = labels
            y = np.abs(self.contingency_flows)
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.ContingencyLoading:
            labels = self.branch_names
            columns = labels
            y = np.abs(self.contingency_loading)
            y_label = '(%)'
            title = result_type.value[0]

        elif result_type == ResultTypes.BranchLosses:
            labels = self.branch_names
            y = self.losses.real
            y_label = '(MW)'
            title = 'Branch losses'

        elif result_type == ResultTypes.NodeSlacks:
            labels = self.bus_names
            y = self.node_slacks
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.GenerationDeltaSlacks:
            labels = self.generator_names
            y = self.generation_delta_slacks
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.ControlledGeneratorPower:
            labels = self.generator_names
            y = self.generator_power
            y_label = '(MW)'
            title = 'Controlled generators power'

        elif result_type == ResultTypes.BatteryPower:
            labels = self.battery_names
            y = self.battery_power
            y_label = '(MW)'
            title = 'Battery power'

        elif result_type == ResultTypes.HvdcPowerFrom:
            labels = self.hvdc_names
            y = self.hvdc_Pf
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.HvdcOverloads:
            labels = self.hvdc_names
            y = self.hvdc_slacks
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.AvailableTransferCapacityAlpha:
            labels = self.branch_names
            y = self.alpha
            y_label = '(p.u.)'
            title = result_type.value[0]

        elif result_type == ResultTypes.GenerationDelta:
            labels = self.generator_names
            y = self.generation_delta
            y_label = '(MW)'
            title = result_type.value[0]

        elif result_type == ResultTypes.InterAreaExchange:
            labels = list()
            y = list()

            for (k, sign) in self.inter_area_branches:
                labels.append(self.branch_names[k])
                y.append([self.Sf[k] * sign])

            for (k, sign) in self.inter_area_hvdc:
                labels.append(self.hvdc_names[k])
                y.append([self.hvdc_Pf[k] * sign])

            y.append([np.array(y).sum()])
            y = np.array(y)
            labels = np.array(labels + ['Total'])
            y_label = '(MW)'
            title = result_type.value

        else:
            labels = []
            y = np.zeros(0)
            y_label = '(MW)'
            title = 'Battery power'

        mdl = ResultsTable(data=y,
                           index=labels,
                           columns=columns,
                           title=title,
                           ylabel=y_label,
                           xlabel='',
                           units=y_label)
        return mdl


class DataAnalysisDriver(DriverTemplate):
    name = 'Data Analysis'
    tpe = SimulationTypes.SigmaAnalysis_run

    def __init__(self, grid: MultiCircuit):
        """
        PowerFlowDriver class constructor
        :param grid: MultiCircuit instance
        """
        DriverTemplate.__init__(self, grid=grid)

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

