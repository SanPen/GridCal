# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.enumerations import InvestmentsEvaluationObjectives, InvestmentEvaluationMethod
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions


class InvestmentsEvaluationOptions:
    """
    InvestmentsEvaluationOptions
    """

    def __init__(self, max_eval: int,
                 pf_options: PowerFlowOptions,
                 solver: InvestmentEvaluationMethod = InvestmentEvaluationMethod.MVRSM,
                 w_overload: float = 1.0,
                 w_voltage_module: float = 1.0,
                 w_voltage_angle: float = 1.0,
                 w_losses: float = 1.0,
                 w_capex: float = 1.0,
                 w_opex: float = 1.0,
                 objf_tpe: InvestmentsEvaluationObjectives = InvestmentsEvaluationObjectives.PowerFlow):
        """

        :param max_eval:
        :param pf_options:
        :param solver:
        :param w_overload:
        :param w_voltage_module:
        :param w_voltage_angle:
        :param w_losses:
        :param w_capex:
        :param w_opex:
        :param objf_tpe:
        """
        self.max_eval = max_eval

        self.pf_options = pf_options

        self.solver = solver

        self.w_overload = w_overload

        self.w_voltage_module = w_voltage_module

        self.w_voltage_angle = w_voltage_angle

        self.w_losses = w_losses

        self.w_capex = w_capex

        self.w_opex = w_opex

        self.objf_tpe = objf_tpe
