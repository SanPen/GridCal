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

from GridCalEngine.enumerations import ContingencyEngine
from GridCalEngine.basic_structures import Vec
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions, SolverType
from GridCalEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions


class ContingencyAnalysisOptions:
    """
    Contingency analysis options
    """

    def __init__(self,
                 distributed_slack: bool = True,
                 use_provided_flows: bool = False,
                 Pf: Vec = None,
                 pf_options=PowerFlowOptions(SolverType.DC),
                 lin_options=LinearAnalysisOptions(),
                 use_srap: bool = False,
                 srap_max_loading: float = 1.4,
                 srap_limit: float = 1400.0,
                 engine=ContingencyEngine.PowerFlow):
        """
        ContingencyAnalysisOptions
        :param distributed_slack: Use distributed slack?
        :param use_provided_flows: Use the provided flows?
        :param Pf: Power flows (at the from bus)
        :param pf_options: PowerFlowOptions
        :param lin_options: LinearAnalysisOptions
        :param use_srap: use the SRAP check?
        :param srap_max_loading: maximum SRAP loading in p.u.
        :param srap_limit: maximum SRAP usage (limit) in MW
        :param engine: ContingencyEngine to use (PowerFlow, PTDF, ...)
        """
        self.distributed_slack = distributed_slack

        self.use_provided_flows = use_provided_flows

        self.Pf: Vec = Pf

        self.engine = engine

        self.pf_options = pf_options

        self.lin_options = lin_options

        self.use_srap: bool = use_srap

        self.srap_max_loading: float = srap_max_loading

        self.srap_limit: float = srap_limit
