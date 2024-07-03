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
from GridCalEngine.enumerations import InvestmentsEvaluationObjectives, InvestmentEvaluationMethod, DeviceType
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.options_template import OptionsTemplate


class InvestmentsEvaluationOptions(OptionsTemplate):
    """
    Investments Evaluation Options
    """

    def __init__(self, max_eval: int,
                 pf_options: PowerFlowOptions,
                 solver: InvestmentEvaluationMethod = InvestmentEvaluationMethod.NSGA3,
                 objf_tpe: InvestmentsEvaluationObjectives = InvestmentsEvaluationObjectives.PowerFlow):
        """

        :param max_eval: Maximum number of evaluations
        :param pf_options: Power Flow options
        :param solver: Black-box solver to use
        :param objf_tpe: Objective function to use
        """
        OptionsTemplate.__init__(self, name='InvestmentsEvaluationOptions')

        self.max_eval = max_eval

        self.pf_options = pf_options

        self.solver = solver

        self.objf_tpe = objf_tpe

        self.register(key="max_eval", tpe=int)
        self.register(key="pf_options", tpe=DeviceType.SimulationOptionsDevice)
        self.register(key="solver", tpe=InvestmentEvaluationMethod)
        self.register(key="objf_tpe", tpe=InvestmentsEvaluationObjectives)

