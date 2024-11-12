# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from typing import Callable, Union
from GridCalEngine.enumerations import InvestmentsEvaluationObjectives, InvestmentEvaluationMethod, DeviceType
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.Simulations.options_template import OptionsTemplate
from typing import Union
from GridCalEngine.enumerations import SolverType



class InvestmentsEvaluationOptions(OptionsTemplate):
    """
    Investments Evaluation Options
    """

    def __init__(self, max_eval: int,
                 pf_options: Union[PowerFlowOptions, None] = None,
                 opf_options: Union[OptimalPowerFlowOptions, None] = None,
                 solver: InvestmentEvaluationMethod = InvestmentEvaluationMethod.NSGA3,
                 obj_tpe: InvestmentsEvaluationObjectives = InvestmentsEvaluationObjectives.PowerFlow,
                 plugin_fcn_ptr: Callable = None,):
        """

        :param max_eval: Maximum number of evaluations
        :param pf_options: Power Flow options
        :param opf_options: Optimal Power Flow options
        :param solver: Black-box solver to use
        :param obj_tpe: Objective function to use
        """
        OptionsTemplate.__init__(self, name='InvestmentsEvaluationOptions')

        self.max_eval = max_eval

        self.pf_options: PowerFlowOptions = pf_options if pf_options else PowerFlowOptions()

        self.opf_options: OptimalPowerFlowOptions = opf_options if opf_options else OptimalPowerFlowOptions(solver=SolverType.NONLINEAR_OPF)

        self.solver = solver

        self.objf_tpe = obj_tpe

        self.plugin_fcn_ptr = plugin_fcn_ptr

        self.register(key="max_eval", tpe=int)
        self.register(key="pf_options", tpe=DeviceType.SimulationOptionsDevice)
        self.register(key="opf_options", tpe=DeviceType.SimulationOptionsDevice)
        self.register(key="solver", tpe=InvestmentEvaluationMethod)
        self.register(key="objf_tpe", tpe=InvestmentsEvaluationObjectives)

