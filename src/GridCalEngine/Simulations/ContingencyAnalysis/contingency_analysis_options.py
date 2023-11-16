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

import GridCalEngine.basic_structures as bs
from GridCalEngine.basic_structures import Vec
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions, SolverType


class ContingencyAnalysisOptions:
    """
    Contingency analysis options
    """

    def __init__(self,
                 distributed_slack: bool = True,
                 correct_values: bool = True,
                 use_provided_flows: bool = False,
                 Pf: Vec = None,
                 pf_results=None,
                 engine=bs.ContingencyEngine.PowerFlow,
                 pf_options=PowerFlowOptions(SolverType.DC)):
        """

        :param distributed_slack:
        :param correct_values:
        :param use_provided_flows:
        :param Pf:
        :param pf_results:
        :param engine:
        :param pf_options:
        """
        self.distributed_slack = distributed_slack

        self.correct_values = correct_values

        self.use_provided_flows = use_provided_flows

        self.Pf: Vec = Pf

        self.pf_results = pf_results

        self.engine = engine

        self.pf_options = pf_options