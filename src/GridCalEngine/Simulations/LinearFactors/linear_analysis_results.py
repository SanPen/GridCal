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
import pandas as pd
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.basic_structures import IntVec, Vec, StrVec, Mat, CxVec
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class LinearAnalysisResults(ResultsTemplate):
    """
    LinearAnalysisResults
    """

    def __init__(self, n_br=0, n_bus=0, br_names=(), bus_names=(), bus_types=()):
        """
        PTDF and LODF results class
        :param n_br: number of Branches
        :param n_bus: number of buses
        :param br_names: branch names
        :param bus_names: bus names
        :param bus_types: bus types array
        """
        ResultsTemplate.__init__(self,
                                 name='Linear Analysis',
                                 available_results=[ResultTypes.PTDF,
                                                    ResultTypes.LODF,
                                                    ResultTypes.BranchActivePowerFrom,
                                                    ResultTypes.BranchLoading],
                                 time_array=None,
                                 clustering_results=None,
                                 study_results_type=StudyResultsType.LinearAnalysis)

        # names of the Branches
        self.branch_names: StrVec = br_names
        self.bus_names: StrVec = bus_names
        self.bus_types: IntVec = bus_types

        self.PTDF: Mat = np.zeros((n_br, n_bus))
        self.LODF: Mat = np.zeros((n_br, n_br))
        self.Sf: Vec = np.zeros(self.n_br)
        self.Sbus: Vec = np.zeros(self.n_bus)
        self.voltage: CxVec = np.ones(self.n_bus, dtype=complex)
        self.loading: Vec = np.zeros(self.n_br)

        self.register(name='branch_names', tpe=StrVec)
        self.register(name='bus_names', tpe=StrVec)
        self.register(name='bus_types', tpe=IntVec)
        self.register(name='PTDF', tpe=Mat)
        self.register(name='LODF', tpe=Mat)
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

