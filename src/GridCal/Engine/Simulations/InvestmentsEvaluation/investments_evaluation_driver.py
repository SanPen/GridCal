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
import numpy as np
import pandas as pd
from GridCal.Engine.Simulations.driver_template import DriverTemplate
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.InvestmentsEvaluation.investments_evaluation_results import InvestmentsEvaluationResults
from GridCal.Engine.Core.Devices.multi_circuit import MultiCircuit
from GridCal.Engine.Core.DataStructures.numerical_circuit import compile_numerical_circuit_at


class InvestmentsEvaluationDriver(DriverTemplate):
    name = 'Investments evaluation'
    tpe = SimulationTypes.InvestmestsEvaluation_run

    def __init__(self, grid: MultiCircuit):
        """
        InputsAnalysisDriver class constructor
        :param grid: MultiCircuit instance
        """
        DriverTemplate.__init__(self, grid=grid)

        self.results = InvestmentsEvaluationResults(grid=grid)

    def get_steps(self):
        """

        :return:
        """
        return list()

    def run(self):
        """
        run the QThread
        :return:
        """

        self.tic()

        # compile the snapshot
        nc = compile_numerical_circuit_at(circuit=self.grid, t_idx=None)

        # disable all status
        nc.set_investments_status(investments_list=self.grid.investments, status=0)

        # get investments by investment group
        inv_by_groups_list = self.grid.get_investmenst_by_groups()

        # evaluate the investments
        for k, (inv_group, inv_list) in enumerate(inv_by_groups_list):

            self.progress_text.emit("Evaluating " + inv_group.name + '...')

            # enable the investment
            nc.set_investments_status(investments_list=inv_list, status=1)

            # do something
            pass
            self.results.set_at(i=k,
                                capex=sum([inv.CAPEX for inv in inv_list]),
                                opex=sum([inv.OPEX for inv in inv_list]),
                                losses=0.0,
                                objective_function=0.0)

            # revert to disabled
            nc.set_investments_status(investments_list=inv_list, status=0)

            self.progress_signal.emit((k+1) / len(inv_by_groups_list) * 100.0)

        self.progress_text.emit("Done!")
        self.progress_signal.emit(0.0)
        self.toc()

    def cancel(self):
        self.__cancel__ = True


