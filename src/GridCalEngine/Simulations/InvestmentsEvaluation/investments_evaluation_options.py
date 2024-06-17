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
from GridCalEngine.enumerations import InvestmentsEvaluationObjectives, InvestmentEvaluationMethod
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions


class InvestmentsEvaluationOptions:
    """
    InvestmentsEvaluationOptions
    """

    def __init__(self, max_eval: int,
                 pf_options: PowerFlowOptions,
                 solver: InvestmentEvaluationMethod = InvestmentEvaluationMethod.NSGA3,
                 # w_overload: float = 1.0,
                 # w_voltage_module: float = 1.0,
                 # w_voltage_angle: float = 1.0,
                 # w_losses: float = 1.0,
                 # w_capex: float = 1.0,
                 # w_opex: float = 1.0,
                 w_electrical: float = 1.0,
                 w_financial: float = 1.0,
                 objf_tpe: InvestmentsEvaluationObjectives = InvestmentsEvaluationObjectives.PowerFlow):
        """

        :param max_eval:
        :param pf_options:
        :param solver:
        :param w_electrical:
        :param w_financial:
        :param objf_tpe:
        """
        self.max_eval = max_eval

        self.pf_options = pf_options

        self.solver = solver

        # self.w_overload = w_overload
        #
        # self.w_voltage_module = w_voltage_module
        #
        # self.w_voltage_angle = w_voltage_angle
        #
        # self.w_losses = w_losses
        #
        # self.w_capex = w_capex
        #
        # self.w_opex = w_opex

        self.w_electrical = w_electrical

        self.w_financial = w_financial

        self.objf_tpe = objf_tpe
