import numpy as np
import pandas as pd

from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.results_table import ResultsTable
from GridCal.Engine.Simulations.results_template import ResultsTemplate

from GridCal.Engine.Devices.enumerations import TransformerControlType, HvdcControlType

class OptimalNetTransferCapacityResults(ResultsTemplate):
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

    def __init__(self, bus_names, branch_names, load_names, generator_names, battery_names,
                 hvdc_names, trm, ntc_load_rule, branch_control_modes, hvdc_control_modes,
                 Sbus=None, voltage=None, battery_power=None, controlled_generation_power=None, Sf=None, loading=None,
                 losses=None, solved=None, bus_types=None, hvdc_flow=None, hvdc_loading=None, hvdc_angle_slack=None,
                 phase_shift=None, generation_delta=None, inter_area_branches=list(), inter_area_hvdc=list(),
                 alpha=None, alpha_n1=None, rates=None, monitor=None, contingency_branch_flows_list=None,
                 contingency_branch_indices_list=None, contingency_generation_flows_list=None,
                 contingency_generation_indices_list=None, contingency_hvdc_flows_list=None,
                 contingency_hvdc_indices_list=None, contingency_rates=None, branch_ntc_load_rule=None,
                 area_from_bus_idx=None, area_to_bus_idx=None, contingency_branch_alpha_list=None,
                 contingency_generation_alpha_list=None, contingency_hvdc_alpha_list=None, structural_ntc=None,
                 sbase=None):

        ResultsTemplate.__init__(
            self,
            name='OPF',
            available_results={
                ResultTypes.BusResults: [
                    ResultTypes.BusVoltageModule,
                    ResultTypes.BusVoltageAngle
                ],
                ResultTypes.BranchResults: [
                    ResultTypes.BranchPower,
                    ResultTypes.BranchLoading,
                    ResultTypes.BranchTapAngle
                ],
                ResultTypes.ReportsResults: [
                    ResultTypes.ContingencyFlowsReport,
                    ResultTypes.ContingencyFlowsBranchReport,
                    ResultTypes.ContingencyFlowsGenerationReport,
                    ResultTypes.ContingencyFlowsHvdcReport
                ],
                ResultTypes.HvdcResults: [
                    ResultTypes.HvdcPowerFrom
                ],
                ResultTypes.DispatchResults: [
                    ResultTypes.BatteryPower,
                    ResultTypes.GeneratorPower,
                    ResultTypes.GenerationDelta
                ],
                ResultTypes.AreaResults: [
                    ResultTypes.AvailableTransferCapacityAlpha,
                    ResultTypes.AvailableTransferCapacityAlphaN1,
                    ResultTypes.InterAreaExchange
                ]
            },
            data_variables=[
                'bus_names',
                'branch_names',
                'load_names',
                'generator_names',
                'battery_names',
                'Sbus',
                'voltage',
                'Sf',
                'bus_types',
                'overloads',
                'loading',
                'battery_power',
                'generator_power',
                'converged'
            ]
        )

        self.bus_names = bus_names
        self.branch_names = branch_names
        self.load_names = load_names
        self.generator_names = generator_names
        self.battery_names = battery_names
        self.hvdc_names = hvdc_names

        self.trm = trm
        self.ntc_load_rule = ntc_load_rule

        self.hvdc_control_modes = hvdc_control_modes
        self.branch_control_modes = branch_control_modes

        self.inter_area_branches = inter_area_branches
        self.inter_area_hvdc = inter_area_hvdc

        self.area_from_bus_idx = area_from_bus_idx
        self.area_to_bus_idx = area_to_bus_idx

        self.generation_delta = generation_delta

        self.Sbus = Sbus

        self.voltage = voltage

        self.Sf = Sf

        self.hvdc_Pf = hvdc_flow
        self.hvdc_loading = hvdc_loading
        self.hvdc_angle_slack = hvdc_angle_slack

        self.phase_shift = phase_shift

        self.bus_types = bus_types

        self.loading = loading

        self.losses = losses

        self.battery_power = battery_power

        self.generator_power = controlled_generation_power

        self.solved = solved

        self.alpha = alpha
        self.alpha_n1 = alpha_n1

        self.monitor = monitor

        self.contingency_branch_flows_list = contingency_branch_flows_list
        self.contingency_branch_indices_list = contingency_branch_indices_list  # [(t, m, c), ...]
        self.contingency_branch_alpha_list = contingency_branch_alpha_list

        self.contingency_generation_flows_list = contingency_generation_flows_list
        self.contingency_generation_indices_list = contingency_generation_indices_list  # [(t, m, c), ...]
        self.contingency_generation_alpha_list = contingency_generation_alpha_list

        self.contingency_hvdc_flows_list = contingency_hvdc_flows_list
        self.contingency_hvdc_indices_list = contingency_hvdc_indices_list  # [(t, m, c), ...]
        self.contingency_hvdc_alpha_list = contingency_hvdc_alpha_list

        self.rates = rates
        self.contingency_rates = contingency_rates

        self.branch_ntc_load_rule = branch_ntc_load_rule

        self.structural_ntc = structural_ntc

        self.sbase = sbase

        self.plot_bars_limit = 100

    def apply_new_rates(self, nc: "SnapshotData"):
        rates = nc.Rates
        self.loading = self.Sf / (rates + 1e-9)

    def initialize(self, n, m):
        """
        Initialize the arrays
        @param n: number of buses
        @param m: number of branches
        @return:
        """
        self.Sbus = np.zeros(n, dtype=complex)

        self.voltage = np.zeros(n, dtype=complex)

        self.Sf = np.zeros(m, dtype=complex)

        self.loading = np.zeros(m, dtype=complex)

        self.losses = np.zeros(m, dtype=complex)

        self.converged = list()

        self.plot_bars_limit = 100

    def get_exchange_power(self):
        y = list()

        for (k, sign) in self.inter_area_branches:
            y.append([self.Sf[k] * sign])

        for (k, sign) in self.inter_area_hvdc:
            y.append([self.hvdc_Pf[k] * sign])

        return np.array(y).sum()

    def get_contingency_report(self, max_report_elements=0):

        l1, c1, y1 = self.get_contingency_branch_report()
        l2, c2, y2 = self.get_contingency_generation_report()
        l3, c3, y3 = self.get_contingency_hvdc_report()

        # group all contingency reports
        labels = l1 + l2 + l3
        columns = c1
        y = np.concatenate((y1, y2, y3), axis=0)

        if len(y.shape) == 2:
            # sort by column value
            sort_idx = columns.index('Contingency flow (%)')
            idx = np.flip(np.argsort(np.abs(y[:, sort_idx].astype(float))))
            y = y[idx, :]
            y = np.array(y, dtype=object)
        else:
            y = np.zeros((0, len(columns)), dtype=object)

        # curtail report
        if max_report_elements > 0:
            y = y[:max_report_elements, :]
            labels = labels[:max_report_elements]

        return labels, columns, y

    def get_base_report(self, max_report_elements=0):

        labels = self.branch_names
        y = list()

        trm = self.trm
        ttc = np.floor(self.get_exchange_power())
        ntc = ttc - trm

        monitor_idx = np.where(self.monitor)[0]
        for m in monitor_idx:
            maczt = ntc * np.abs(self.alpha[m]) / self.rates[m]
            y.append([np.round(ttc, 0),
                      trm,
                      np.round(ntc, 0),
                      np.round(maczt * 100, 2),
                      np.round(self.branch_ntc_load_rule[m], 2),
                      self.branch_names[m],
                      np.round(self.Sf[m].real, 2),
                      np.round(self.Sf[m] / self.rates[m] * 100, 2),
                      self.rates[m],
                      self.alpha[m]])

        y = np.array(y, dtype=object)
        columns = ['TTC',
                   'TRM',
                   'NTC',
                   'MACZT (%)',
                   'NTC Load Rule',
                   'Branch',
                   'Flow (MW)',
                   'Load (%)',
                   'Rate',
                   'Alpha']

        # Add inter area branches, shifter and hvdc data into report
        y, columns = self.add_inter_area_branches_data(y=y, columns=columns)
        y, columns = self.add_hvdc_data(y=y, columns=columns)
        y, columns = self.add_shifter_data(y=y, columns=columns)

        # sort by column value
        sort_idx = columns.index('Load (%)')
        idx = np.flip(np.argsort(np.abs(y[:, sort_idx].astype(float))))
        y = y[idx, :]

        # curtail report
        if max_report_elements > 0:
            y = y[:max_report_elements, :]
            labels = labels[:max_report_elements]

        return labels, columns, y

    def get_controled_shifters_as_pt(self):
        shifter_idx = np.where(self.branch_control_modes == TransformerControlType.Pt)
        shifter_names = self.branch_names[shifter_idx]

        return shifter_names, shifter_idx

    def get_contingency_branch_report(self, max_report_elements=0):
        labels = list()
        y = list()

        ttc = self.get_exchange_power()
        trm = self.trm
        ntc = ttc - trm

        for (m, c), contingency_flow, alpha_n1 in zip(self.contingency_branch_indices_list,
                                                      self.contingency_branch_flows_list,
                                                      self.contingency_branch_alpha_list):
            if contingency_flow != 0.0:
                maczt = ntc * np.abs(alpha_n1) / self.rates[m]
                y.append((np.round(ttc, 0),
                          trm,
                          np.round(ntc, 0),
                          np.round(maczt * 100, 2),
                          np.round(self.branch_ntc_load_rule[m], 2),
                          self.branch_names[m],
                          self.branch_names[c],
                          np.round(contingency_flow, 2),
                          np.round(self.Sf[m], 2),
                          self.contingency_rates[m],
                          self.rates[m],
                          np.round(contingency_flow / self.contingency_rates[m] * 100, 2),
                          np.round(self.Sf[m] / self.rates[m] * 100, 2),
                          self.alpha[m],
                          alpha_n1,
                          self.structural_ntc,
                          'Branch',
                          m, c))
                labels.append(len(y))

        columns = ['TTC',
                   'TRM',
                   'NTC',
                   'MACZT (%)',
                   'NTC Load Rule',
                   'Monitored',
                   'Contingency',
                   'Contingency flow (MW)',
                   'Base flow (MW)',
                   'Contingency rates (MW)',
                   'Base rates (MW)',
                   'Contingency flow (%)',
                   'Base flow (%)',
                   'Alpha N',
                   'Alpha N-1',
                   'Structural NTC',
                   'Contingency type',
                   'Monitored idx',
                   'Contingency idx',
                   ]

        y = np.array(y, dtype=object)

        # Add inter area branches, shifter and hvdc data into report
        y, columns = self.add_inter_area_branches_data(y=y, columns=columns)
        y, columns = self.add_hvdc_data(y=y, columns=columns)
        y, columns = self.add_shifter_data(y=y, columns=columns)

        if len(y.shape) == 2:
            # sort by column value
            sort_idx = columns.index('Contingency flow (%)')
            idx = np.flip(np.argsort(np.abs(y[:, sort_idx].astype(float))))
            y = y[idx, :]
            y = np.array(y, dtype=object)
        else:
            y = np.zeros((0, len(columns)), dtype=object)

        # curtail report
        if max_report_elements > 0:
            y = y[:max_report_elements, :]
            labels = labels[:max_report_elements]

        return labels, columns, y

    def get_contingency_generation_report(self, max_report_elements=0):
        labels = list()
        y = list()

        ttc = self.get_exchange_power()
        trm = self.trm
        ntc = ttc - trm

        for (m, c), contingency_flow, alpha_n1 in zip(self.contingency_generation_indices_list,
                                                      self.contingency_generation_flows_list,
                                                      self.contingency_generation_alpha_list):
            if contingency_flow != 0.0:
                maczt = ntc * np.abs(alpha_n1) / self.rates[m]
                y.append((np.round(ttc, 0),
                          trm,
                          np.round(ntc, 0),
                          np.round(maczt * 100, 2),
                          np.round(self.branch_ntc_load_rule[m], 2),
                          self.branch_names[m],
                          self.generator_names[c],
                          np.round(contingency_flow, 2),
                          np.round(self.Sf[m], 2),
                          self.contingency_rates[m],
                          self.rates[m],
                          np.round(contingency_flow / self.contingency_rates[m] * 100, 2),
                          np.round(self.Sf[m] / self.rates[m] * 100, 2),
                          self.alpha[m],
                          alpha_n1,
                          self.structural_ntc,
                          'Generation',
                          m, c))
                labels.append(len(y))

        columns = ['TTC',
                   'TRM',
                   'NTC',
                   'MACZT (%)',
                   'NTC Load Rule',
                   'Monitored',
                   'Contingency',
                   'Contingency flow (MW)',
                   'Base flow (MW)',
                   'Contingency rates (MW)',
                   'Base rates (MW)',
                   'Contingency flow (%)',
                   'Base flow (%)',
                   'Alpha N',
                   'Alpha N-1',
                   'Structural NTC',
                   'Contingency Type',
                   'Monitored idx',
                   'Contingency idx']

        y = np.array(y, dtype=object)

        # Add inter area branches, shifter and hvdc data into report
        y, columns = self.add_inter_area_branches_data(y=y, columns=columns)
        y, columns = self.add_hvdc_data(y=y, columns=columns)
        y, columns = self.add_shifter_data(y=y, columns=columns)

        if len(y.shape) == 2:
            # sort by column value
            sort_idx = columns.index('Contingency flow (%)')
            idx = np.flip(np.argsort(np.abs(y[:, sort_idx].astype(float))))
            y = y[idx, :]
            y = np.array(y, dtype=object)
        else:
            y = np.zeros((0, len(columns)), dtype=object)

        # curtail report
        if max_report_elements > 0:
            y = y[:max_report_elements, :]
            labels = labels[:max_report_elements]

        return labels, columns, y

    def get_contingency_hvdc_report(self, max_report_elements=0):
        labels = list()
        y = list()

        ttc = self.get_exchange_power()
        trm = self.trm
        ntc = ttc - trm

        for (m, c), contingency_flow, alpha_n1 in zip(self.contingency_hvdc_indices_list,
                                                      self.contingency_hvdc_flows_list,
                                                      self.contingency_hvdc_alpha_list):
            if contingency_flow != 0.0:
                maczt = ntc * np.abs(alpha_n1) / self.rates[m]
                y.append((np.round(ttc, 0),
                          trm,
                          np.round(ntc, 0),
                          np.round(maczt * 100, 2),
                          np.round(self.branch_ntc_load_rule[m], 2),
                          self.branch_names[m],
                          self.hvdc_names[c],
                          np.round(contingency_flow, 2),
                          np.round(self.Sf[m], 2),
                          self.contingency_rates[m],
                          self.rates[m],
                          np.round(contingency_flow / self.contingency_rates[m] * 100, 2),
                          np.round(self.Sf[m] / self.rates[m] * 100, 2),
                          self.alpha[m],
                          alpha_n1,
                          self.structural_ntc,
                          'Hvdc',
                          m, c))
                labels.append(len(y))

        columns = ['TTC',
                   'TRM',
                   'NTC',
                   'MACZT (%)',
                   'NTC Load Rule',
                   'Monitored',
                   'Contingency',
                   'Contingency flow (MW)',
                   'Base flow (MW)',
                   'Contingency rates (MW)',
                   'Base rates (MW)',
                   'Contingency flow (%)',
                   'Base flow (%)',
                   'Alpha N',
                   'Alpha N-1',
                   'Structural NTC',
                   'Contingency Type',
                   'Monitored idx',
                   'Contingency idx']

        y = np.array(y, dtype=object)

        # Add shifter and hvdc data into report
        y, columns = self.add_inter_area_branches_data(y=y, columns=columns)
        y, columns = self.add_hvdc_data(y=y, columns=columns)
        y, columns = self.add_shifter_data(y=y, columns=columns)

        if len(y.shape) == 2:
            # sort by column value
            sort_idx = columns.index('Contingency flow (%)')
            idx = np.flip(np.argsort(np.abs(y[:, sort_idx].astype(float))))
            y = y[idx, :]
            y = np.array(y, dtype=object)
        else:
            y = np.zeros((0, len(columns)), dtype=object)

        # curtail report
        if max_report_elements > 0:
            y = y[:max_report_elements, :]
            labels = labels[:max_report_elements]

        return labels, columns, y

    def add_inter_area_branches_data(self, y, columns):
        """
        Add inter area branches data into y, columns from report
        :param y:
        :param columns:
        :return:
        """
        inter_area_idx = [idx for (idx, name) in self.inter_area_branches]
        inter_area_names = self.branch_names[inter_area_idx]
        inter_area_data = np.array([self.Sf[inter_area_idx]] * y.shape[0])

        if len(y.shape) == 2:
            y = np.concatenate((y, inter_area_data), axis=1)

        columns = columns + [name for name in inter_area_names]

        return y, columns

    def add_shifter_data(self, y, columns):
        """
        Add shifter data into y, columns from report
        :param y:
        :param columns:
        :return:
        """

        shifter_names, shifter_idx = self.get_controled_shifters_as_pt()
        shifter_data = np.array([self.phase_shift[shifter_idx]] * y.shape[0])

        if len(y.shape) == 2:
            y = np.concatenate((y, shifter_data), axis=1)

        columns = columns + [name for name in shifter_names]

        return y, columns

    def add_hvdc_data(self, y, columns):
        """
        Add hvdc data into y, columns from report
        :param y:
        :param columns:
        :return:
        """

        hvdc_data = np.array([self.hvdc_Pf] * y.shape[0])
        hvdc_angles = np.array([self.hvdc_angle_slack] * y.shape[0])

        if len(y.shape) == 2:
            y = np.concatenate((y, hvdc_data, hvdc_angles), axis=1)

        columns = columns + [name for name in self.hvdc_names] + ['Slack angle ' + name for name in self.hvdc_names]

        return y, columns

    def make_report(self, path_out=None):
        """

         :param path_out:
         :return:
         """

        print('NTC is', self.get_exchange_power(), 'MW')

        labels, columns, data = self.get_contingency_report()

        df = pd.DataFrame(data=data, columns=columns, index=labels)

        # print result dataframe
        print('\n\n')
        print(df)

        # Save file
        if path_out:
            df.to_csv(path_out, index=False)

    def mdl(self, result_type) -> "ResultsTable":
        """
        Plot the results
        :param result_type: type of results (string)
        :return: DataFrame of the results (or None if the result was not understood)
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

        elif result_type == ResultTypes.BranchLosses:
            labels = self.branch_names
            y = self.losses.real
            y_label = '(MW)'
            title = 'Branch losses'

        elif result_type == ResultTypes.BranchTapAngle:
            labels = self.branch_names
            y = np.rad2deg(self.phase_shift)
            y_label = '(deg)'
            title = result_type.value[0]

        # elif result_type == ResultTypes.BranchTapAngleRad:
        #    labels = self.branch_names
        #    y = self.phase_shift
        #    y_label = '(rad)'
        #    title = result_type.value[0]

        elif result_type == ResultTypes.GeneratorPower:
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

        # elif result_type == ResultTypes.HvdcPmode3Slack:
        #    labels = self.hvdc_names
        #    y = self.hvdc_angle_slack
        #    y_label = '(rad)'
        #    title = result_type.value[0]

        elif result_type == ResultTypes.AvailableTransferCapacityAlpha:
            labels = self.branch_names
            y = self.alpha
            y_label = '(p.u.)'
            title = result_type.value[0]

        elif result_type == ResultTypes.AvailableTransferCapacityAlphaN1:

            labels = self.branch_names
            columns = labels
            y = self.alpha_n1
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
            title = result_type.value[0]

        elif result_type == ResultTypes.ContingencyFlowsReport:
            labels, columns, y = self.get_contingency_report()
            y_label = ''
            title = result_type.value[0]

        elif result_type == ResultTypes.ContingencyFlowsBranchReport:
            labels, columns, y = self.get_contingency_branch_report()
            y_label = ''
            title = result_type.value[0]

        elif result_type == ResultTypes.ContingencyFlowsGenerationReport:
            labels, columns, y = self.get_contingency_generation_report()
            y_label = ''
            title = result_type.value[0]

        elif result_type == ResultTypes.ContingencyFlowsHvdcReport:
            labels, columns, y = self.get_contingency_hvdc_report()
            y_label = ''
            title = result_type.value[0]

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
