# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.basic_structures import IntVec, Vec, StrVec, Mat, CxVec
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class LinearAnalysisResults(ResultsTemplate):
    """
    LinearAnalysisResults
    """

    def __init__(self,
                 br_names=(), bus_names=(), hvdc_names=(), vsc_names=(),
                 bus_types=()):
        """
        PTDF and LODF results class
        :param br_names: branch names
        :param bus_names: bus names
        :param hvdc_names: HVDC names
        :param vsc_names: VSC names
        :param bus_types: bus types array
        """
        ResultsTemplate.__init__(self,
                                 name='Linear Analysis',
                                 available_results=[ResultTypes.PTDF,
                                                    ResultTypes.LODF,
                                                    ResultTypes.HvdcPTDF,
                                                    ResultTypes.HvdcODF,
                                                    ResultTypes.VscPTDF,
                                                    ResultTypes.VscODF,
                                                    ResultTypes.BranchActivePowerFrom,
                                                    ResultTypes.BranchLoading],
                                 time_array=None,
                                 clustering_results=None,
                                 study_results_type=StudyResultsType.LinearAnalysis)

        n_br = len(bus_names)
        n_bus = len(br_names)
        n_hvdc = len(hvdc_names)
        n_vsc = len(vsc_names)

        # names of the Branches
        self.branch_names: StrVec = br_names
        self.bus_names: StrVec = bus_names
        self.hvdc_names: StrVec = hvdc_names
        self.vsc_names: StrVec = vsc_names
        self.bus_types: IntVec = bus_types

        self.PTDF: Mat = np.zeros((n_br, n_bus))
        self.LODF: Mat = np.zeros((n_br, n_br))

        self.HvdcDF: Mat = np.zeros((n_hvdc, n_bus))
        self.HvdcODF: Mat = np.zeros((n_br, n_hvdc))

        self.VscDF: Mat = np.zeros((n_vsc, n_bus))
        self.VscODF: Mat = np.zeros((n_br, n_vsc))

        self.Sf: Vec = np.zeros(self.n_br)
        self.Sbus: Vec = np.zeros(self.n_bus)
        self.voltage: CxVec = np.ones(self.n_bus, dtype=complex)
        self.loading: Vec = np.zeros(self.n_br)

        self.register(name='branch_names', tpe=StrVec)
        self.register(name='bus_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)
        self.register(name='PTDF', tpe=Mat)
        self.register(name='LODF', tpe=Mat)

        self.register(name='HvdcDF', tpe=Mat)
        self.register(name='HvdcODF', tpe=Mat)

        self.register(name='VscDF', tpe=Mat)
        self.register(name='VscODF', tpe=Mat)

        self.register(name='Sf', tpe=Vec)
        self.register(name='Sbus', tpe=Vec)
        self.register(name='voltage', tpe=CxVec)
        self.register(name='loading', tpe=Vec)

    @property
    def n_br(self):
        """
        Branch number
        :return:
        """
        return self.PTDF.shape[0]

    @property
    def n_bus(self):
        """
        Bus number
        :return:
        """
        return self.PTDF.shape[1]

    def get_bus_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the buses results
        :return: DataFrame
        """
        return pd.DataFrame(data={'Vm': np.abs(self.voltage),
                                  'Va': np.angle(self.voltage, deg=True),
                                  'P': self.Sbus.real,
                                  'Q': self.Sbus.imag},
                            index=self.bus_names)

    def get_branch_df(self) -> pd.DataFrame:
        """
        Get a DataFrame with the branches results
        :return: DataFrame
        """
        return pd.DataFrame(data={'Pf': self.Sf.real,
                                  'loading': self.loading.real * 100.0},
                            index=self.branch_names)

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Plot the results.

        Arguments:

            **result_type**: ResultTypes

        Returns: ResultsModel
        """

        if result_type == ResultTypes.PTDF:
            title = 'Branches sensitivity'

            return ResultsTable(data=self.PTDF,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=self.bus_names,
                                cols_device_type=DeviceType.BusDevice,
                                title=title,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.LODF:
            title = 'Branch failure sensitivity'

            return ResultsTable(data=self.LODF,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=self.branch_names,
                                cols_device_type=DeviceType.BranchDevice,
                                title=title,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.HvdcPTDF:

            return ResultsTable(data=self.HvdcDF,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=self.hvdc_names,
                                cols_device_type=DeviceType.HVDCLineDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.HvdcODF:

            return ResultsTable(data=self.HvdcODF,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=self.hvdc_names,
                                cols_device_type=DeviceType.HVDCLineDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.VscPTDF:

            return ResultsTable(data=self.VscDF,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=self.vsc_names,
                                cols_device_type=DeviceType.VscDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')

        elif result_type == ResultTypes.VscODF:

            return ResultsTable(data=self.VscODF,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=self.vsc_names,
                                cols_device_type=DeviceType.VscDevice,
                                title=result_type.value,
                                ylabel='(p.u.)',
                                units='(p.u.)')


        elif result_type == ResultTypes.BranchActivePowerFrom:

            return ResultsTable(data=self.Sf,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(MW)',
                                units='(MW)')

        elif result_type == ResultTypes.BranchLoading:

            return ResultsTable(data=self.loading * 100.0,
                                index=self.branch_names,
                                idx_device_type=DeviceType.BranchDevice,
                                columns=[result_type.value],
                                cols_device_type=DeviceType.NoDevice,
                                title=result_type.value,
                                ylabel='(%)',
                                units='(%)')

        else:
            raise Exception('Result type not understood:' + str(result_type))

