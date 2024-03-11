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

from GridCalEngine.enumerations import ContingencyMethod
from GridCalEngine.basic_structures import Vec
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions, SolverType
from GridCalEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions


class ContingencyAnalysisOptions:
    """
    Contingency analysis options
    """

    def __init__(self,
                 use_provided_flows: bool = False,
                 Pf: Vec = None,
                 pf_options=PowerFlowOptions(SolverType.DC),
                 lin_options=LinearAnalysisOptions(),
                 use_srap: bool = False,
                 srap_max_power: float = 1400.0,
                 srap_top_n: int = 5,
                 srap_deadband: float = 10,
                 srap_rever_to_nominal_rating: bool = False,
                 detailed_massive_report: bool = False,
                 contingency_deadband: float = 0.0,
                 engine=ContingencyMethod.PowerFlow):
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
        :param engine: ContingencyEngine to use (PowerFlow, PTDF, ...)
        """

        self.use_provided_flows = use_provided_flows

        self.Pf: Vec = Pf

        self.contingency_method = engine

        self.pf_options = pf_options

        self.lin_options = lin_options

        self.use_srap: bool = use_srap

        self.srap_max_power: float = srap_max_power

        self.srap_top_n = srap_top_n

        self.srap_deadband: float = srap_deadband

        self.srap_rever_to_nominal_rating: bool = srap_rever_to_nominal_rating

        self.detailed_massive_report = detailed_massive_report

        self.contingency_deadband = contingency_deadband
