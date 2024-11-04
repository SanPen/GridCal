# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from typing import Callable
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
                 objf_tpe: InvestmentsEvaluationObjectives = InvestmentsEvaluationObjectives.PowerFlow,
                 plugin_fcn_ptr: Callable = None,):
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

        self.plugin_fcn_ptr = plugin_fcn_ptr

        self.register(key="max_eval", tpe=int)
        self.register(key="pf_options", tpe=DeviceType.SimulationOptionsDevice)
        self.register(key="solver", tpe=InvestmentEvaluationMethod)
        self.register(key="objf_tpe", tpe=InvestmentsEvaluationObjectives)

