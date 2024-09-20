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
from typing import Callable
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

