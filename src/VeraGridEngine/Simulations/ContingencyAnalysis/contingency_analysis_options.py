# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import List, Union
from VeraGridEngine.enumerations import ContingencyMethod, SubObjectType, DeviceType
from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions, SolverType
from VeraGridEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions
from VeraGridEngine.Devices.Aggregation.contingency_group import ContingencyGroup
from VeraGridEngine.Simulations.options_template import OptionsTemplate


class ContingencyAnalysisOptions(OptionsTemplate):
    """
    Contingency analysis options
    """

    def __init__(self,
                 use_provided_flows: bool = False,
                 Pf: Vec = None,
                 pf_options=PowerFlowOptions(SolverType.Linear),
                 lin_options=LinearAnalysisOptions(),
                 use_srap: bool = False,
                 srap_max_power: float = 1400.0,
                 srap_top_n: int = 5,
                 srap_deadband: float = 10,
                 srap_rever_to_nominal_rating: bool = False,
                 detailed_massive_report: bool = False,
                 contingency_deadband: float = 0.0,
                 contingency_method=ContingencyMethod.PowerFlow,
                 contingency_groups: Union[List[ContingencyGroup], None] = None):
        """
        ContingencyAnalysisOptions
        :param use_provided_flows: Use the provided flows?
        :param Pf: Power flows (at the from bus)
        :param pf_options: PowerFlowOptions
        :param lin_options: LinearAnalysisOptions
        :param use_srap: use the SRAP check?
        :param srap_max_power: maximum SRAP usage (limit) in MW
        :param srap_top_n: Maximum number of nodes to use with SRAP
        :param srap_deadband: Dead band over the SRAP rating. If greater than zero,
                              the SRAP is investigated for values over the branch
                              protections rating until the specified value. (in %)
        :param srap_rever_to_nominal_rating: If checked the SRAP objective solution is the branch nominal rate.
                                             Otherwise the objective rating is the contingency rating.
        :param detailed_massive_report: If checked, a massive posibly intractable report is generated.
        :param contingency_deadband: Deadband to report contingencies
        :param contingency_method: ContingencyEngine to use (PowerFlow, PTDF, ...)
        :param contingency_groups: List of contingencies to use, if None all will be used
        """
        OptionsTemplate.__init__(self, name="ContingencyAnalysisOptions")

        self.use_provided_flows = use_provided_flows

        self.Pf: Vec = Pf

        self.contingency_method = contingency_method

        self.pf_options = pf_options

        self.lin_options = lin_options

        self.use_srap: bool = use_srap

        self.srap_max_power: float = srap_max_power

        self.srap_top_n = srap_top_n

        self.srap_deadband: float = srap_deadband

        self.srap_rever_to_nominal_rating: bool = srap_rever_to_nominal_rating

        self.detailed_massive_report = detailed_massive_report

        self.contingency_deadband = contingency_deadband

        self.contingency_groups: Union[List[ContingencyGroup], None] = contingency_groups

        self.register(key="use_provided_flows", tpe=bool)
        self.register(key="Pf", tpe=SubObjectType.Array)
        self.register(key="contingency_method", tpe=ContingencyMethod)
        self.register(key="pf_options", tpe=DeviceType.SimulationOptionsDevice)
        self.register(key="lin_options", tpe=DeviceType.SimulationOptionsDevice)
        self.register(key="use_srap", tpe=bool)
        self.register(key="srap_max_power", tpe=float)
        self.register(key="srap_top_n", tpe=int)
        self.register(key="srap_deadband", tpe=float)
        self.register(key="srap_rever_to_nominal_rating", tpe=bool)
        self.register(key="detailed_massive_report", tpe=bool)
        self.register(key="contingency_deadband", tpe=float)
        self.register(key="contingency_groups", tpe=SubObjectType.ObjectsList)
