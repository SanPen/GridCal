# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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
import numpy as np
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.Simulations.ContinuationPowerFlow.continuation_power_flow import CpfNumericResults
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.basic_structures import IntVec, Vec, StrVec, CxMat, Mat, BoolVec
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType



class ContinuationPowerFlowResults(ResultsTemplate):

    def __init__(self, nval, nbus, nbr, bus_names, branch_names, bus_types, area_names: StrVec = None):
        """
        ContinuationPowerFlowResults instance
        :param nbus: number of buses
        :param nbr: number of Branches
        :param bus_names: names of the buses
        """
        ResultsTemplate.__init__(self,
                                 name='Continuation Power Flow',
                                 available_results={
                                     ResultTypes.BusResults: [ResultTypes.BusVoltage,
                                                              ResultTypes.BusActivePower,
                                                              ResultTypes.BusReactivePower],
                                     ResultTypes.BranchResults: [ResultTypes.BranchActivePowerFrom,
                                                                 ResultTypes.BranchReactivePowerFrom,
                                                                 ResultTypes.BranchActivePowerTo,
                                                                 ResultTypes.BranchReactivePowerTo,
                                                                 ResultTypes.BranchActiveLosses,
                                                                 ResultTypes.BranchReactiveLosses,
                                                                 ResultTypes.BranchLoading],
                                     ResultTypes.AreaResults: [
                                         ResultTypes.InterAreaExchange,
                                         ResultTypes.ActivePowerFlowPerArea,
                                         ResultTypes.LossesPerArea,
                                         ResultTypes.LossesPercentPerArea,
                                         ResultTypes.LossesPerGenPerArea
                                     ],
                                 },
                                 time_array=None,
                                 clustering_results=None,
                                 study_results_type=StudyResultsType.ContinuationPowerFlow
                                 )

        self.bus_names: StrVec = bus_names
        self.branch_names: StrVec = branch_names
        self.bus_types: IntVec = bus_types

        # vars for the inter-area computation
        self.F: IntVec = None
        self.T: IntVec = None
        self.hvdc_F: IntVec = None
        self.hvdc_T: IntVec = None
        self.bus_area_indices: IntVec = None
        self.area_names: StrVec = area_names

        self.voltages: CxMat = np.zeros((nval, nbus), dtype=complex)

        self.lambdas: Vec = np.zeros(nval)
        self.error: Vec = np.zeros(nval)
        self.converged: BoolVec = np.zeros(nval, dtype=bool)

        self.Sf: CxMat = np.zeros((nval, nbr), dtype=complex)
        self.St: CxMat = np.zeros((nval, nbr), dtype=complex)
        self.loading: Mat = np.zeros((nval, nbr))
        self.losses: CxMat = np.zeros((nval, nbr), dtype=complex)
        self.Sbus: CxMat = np.zeros((nval, nbus), dtype=complex)

        self.register(name='bus_names', tpe=StrVec)
        self.register(name='branch_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)
        self.register(name='voltages', tpe=CxMat)
        self.register(name='lambdas', tpe=Vec)
        self.register(name='error', tpe=Vec)
        self.register(name='converged', tpe=BoolVec)
        self.register(name='Sf', tpe=CxMat)
        self.register(name='St', tpe=CxMat)
        self.register(name='loading', tpe=CxMat)
        self.register(name='losses', tpe=CxMat)
        self.register(name='Sbus', tpe=CxMat)

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'lambda': self.lambdas.tolist(),
                'Vm': np.abs(self.voltages).tolist(),
                'Va': np.angle(self.voltages).tolist(),
                'error': self.error.tolist()}
        return data

    def apply_from_island(self, results: CpfNumericResults, bus_original_idx, branch_original_idx):
        """
        Apply the results of an island to this ContinuationPowerFlowResults instance
        :param results: CpfNumericResults instance of the island
        :param bus_original_idx: indices of the buses in the complete grid
        :param branch_original_idx: indices of the Branches in the complete grid
        """

        nval = np.arange(len(results))

        self.voltages[np.ix_(nval, bus_original_idx)] = results.V
        self.Sbus[np.ix_(nval, bus_original_idx)] = results.Sbus

        self.lambdas[nval] = results.lmbda
        self.error[nval] = results.normF
        self.converged[nval] = results.success

        self.Sf[np.ix_(nval, branch_original_idx)] = results.Sf
        self.St[np.ix_(nval, branch_original_idx)] = results.St

        self.loading[np.ix_(nval, branch_original_idx)] = results.loading
        self.losses[np.ix_(nval, branch_original_idx)] = results.losses

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Plot the results
        :param result_type:
        :return:
        """

        if result_type == ResultTypes.BusVoltage:

            return ResultsTable(data=np.abs(np.array(self.voltages)),
                                index=self.lambdas,
                                idx_device_type=DeviceType.LambdaDevice,
                                columns=self.bus_names,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                xlabel=DeviceType.LambdaDevice.value,
                                units='(p.u.)')

        elif result_type == ResultTypes.BusActivePower:

            return ResultsTable(data=self.Sbus.real,
                                index=self.lambdas,
                                idx_device_type=DeviceType.LambdaDevice,
                                columns=self.bus_names,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                xlabel=DeviceType.LambdaDevice.value,
                                units='(p.u.)')

        elif result_type == ResultTypes.BusReactivePower:

            return ResultsTable(data=self.Sbus.imag,
                                index=self.lambdas,
                                idx_device_type=DeviceType.LambdaDevice,
                                columns=self.bus_names,
                                cols_device_type=DeviceType.BusDevice,
                                title=result_type.value,
                                xlabel=DeviceType.LambdaDevice.value,
                                units='(p.u.)')

        elif result_type == ResultTypes.BranchActivePowerFrom:

            return ResultsTable(data=self.Sf.real,
                                index=self.lambdas,
                                idx_device_type=DeviceType.LambdaDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                xlabel=DeviceType.LambdaDevice.value,
                                units='(MW)')

        elif result_type == ResultTypes.BranchReactivePowerFrom:

            return ResultsTable(data=self.Sf.imag,
                                index=self.lambdas,
                                idx_device_type=DeviceType.LambdaDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                xlabel=DeviceType.LambdaDevice.value,
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActivePowerTo:

            return ResultsTable(data=self.St.real,
                                index=self.lambdas,
                                idx_device_type=DeviceType.LambdaDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                xlabel=DeviceType.LambdaDevice.value,
                                units='(MW)')

        elif result_type == ResultTypes.BranchReactivePowerTo:

            return ResultsTable(data=self.St.imag,
                                index=self.lambdas,
                                idx_device_type=DeviceType.LambdaDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                xlabel=DeviceType.LambdaDevice.value,
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchActiveLosses:

            return ResultsTable(data=self.losses.real,
                                index=self.lambdas,
                                idx_device_type=DeviceType.LambdaDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                xlabel=DeviceType.LambdaDevice.value,
                                units='(MW)')

        elif result_type == ResultTypes.BranchReactiveLosses:

            return ResultsTable(data=self.losses.imag,
                                index=self.lambdas,
                                idx_device_type=DeviceType.LambdaDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                xlabel=DeviceType.LambdaDevice.value,
                                units='(MVAr)')

        elif result_type == ResultTypes.BranchLoading:

            return ResultsTable(data=self.loading * 100.0,
                                index=self.lambdas,
                                idx_device_type=DeviceType.LambdaDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=result_type.value,
                                xlabel=DeviceType.LambdaDevice.value,
                                units='(%)')

        elif result_type == ResultTypes.InterAreaExchange:
            index = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            data = self.get_inter_area_flows(area_names=self.area_names,
                                             F=self.F,
                                             T=self.T,
                                             Sf=self.Sf[-1, :],
                                             hvdc_F=self.hvdc_F,
                                             hvdc_T=self.hvdc_T,
                                             hvdc_Pf=np.zeros(len(self.hvdc_T)),
                                             bus_area_indices=self.bus_area_indices).real

            return ResultsTable(data=data,
                                index=index,
                                idx_device_type=DeviceType.AreaDevice,
                                columns=columns,
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                units='(MW)')

        elif result_type == ResultTypes.LossesPercentPerArea:
            index = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            Pf = self.get_branch_values_per_area(np.abs(self.Sf.real[-1, :]),
                                                 self.area_names, self.bus_area_indices,
                                                 self.F, self.T)

            hvdc_Pf = np.zeros(len(self.hvdc_T))
            Pf += self.get_hvdc_values_per_area(np.abs(hvdc_Pf),
                                                self.area_names, self.bus_area_indices,
                                                self.hvdc_F, self.hvdc_T)

            Pl = self.get_branch_values_per_area(np.abs(self.losses.real[-1, :]),
                                                 self.area_names, self.bus_area_indices,
                                                 self.F, self.T)

            hvdc_losses = np.zeros(len(self.hvdc_T))
            Pl += self.get_hvdc_values_per_area(np.abs(hvdc_losses),
                                                self.area_names, self.bus_area_indices,
                                                self.hvdc_F, self.hvdc_T)

            data = Pl / (Pf + 1e-20) * 100.0

            return ResultsTable(data=data,
                                index=index,
                                idx_device_type=DeviceType.AreaDevice,
                                columns=columns,
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                units='(%)')

        elif result_type == ResultTypes.LossesPerGenPerArea:
            index = [a for a in self.area_names]
            columns = [result_type.value]
            gen_bus = self.Sbus.copy().real
            gen_bus[gen_bus < 0] = 0
            Gf = self.get_bus_values_per_area(gen_bus, self.area_names, self.bus_area_indices)

            Pl = self.get_branch_values_per_area(np.abs(self.losses.real[-1, :]),
                                                 self.area_names, self.bus_area_indices,
                                                 self.F, self.T)

            hvdc_losses = np.zeros(len(self.hvdc_T))
            Pl += self.get_hvdc_values_per_area(np.abs(hvdc_losses),
                                                self.area_names, self.bus_area_indices,
                                                self.hvdc_F, self.hvdc_T)

            data = np.zeros(len(self.area_names))
            for i in range(len(self.area_names)):
                data[i] = Pl[i, i] / (Gf[i] + 1e-20) * 100.0

            return ResultsTable(data=data,
                                index=index,
                                idx_device_type=DeviceType.AreaDevice,
                                columns=columns,
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                units='(%)')

        elif result_type == ResultTypes.LossesPerArea:
            index = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]
            data = self.get_branch_values_per_area(np.abs(self.losses.real[-1, :]),
                                                   self.area_names, self.bus_area_indices,
                                                   self.F, self.T)

            hvdc_losses = np.zeros(len(self.hvdc_T))
            data += self.get_hvdc_values_per_area(np.abs(hvdc_losses),
                                                  self.area_names, self.bus_area_indices,
                                                  self.hvdc_F, self.hvdc_T)

            return ResultsTable(data=data,
                                index=index,
                                idx_device_type=DeviceType.AreaDevice,
                                columns=columns,
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                units='(MW)')

        elif result_type == ResultTypes.ActivePowerFlowPerArea:
            index = [a + '->' for a in self.area_names]
            columns = ['->' + a for a in self.area_names]

            data = self.get_branch_values_per_area(np.abs(self.Sf.real[-1, :]),
                                                   self.area_names, self.bus_area_indices,
                                                   self.F, self.T)

            hvdc_Pf = np.zeros(len(self.hvdc_T))
            data += self.get_hvdc_values_per_area(np.abs(hvdc_Pf),
                                                  self.area_names, self.bus_area_indices,
                                                  self.hvdc_F, self.hvdc_T)

            return ResultsTable(data=data,
                                index=index,
                                idx_device_type=DeviceType.AreaDevice,
                                columns=columns,
                                cols_device_type=DeviceType.AreaDevice,
                                title=result_type.value,
                                units='(MW)')

        else:
            raise Exception('Result type not understood:' + str(result_type))
