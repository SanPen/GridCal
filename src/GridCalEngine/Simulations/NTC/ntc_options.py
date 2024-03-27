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

from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions
from GridCalEngine.basic_structures import IntVec
from GridCalEngine.enumerations import AvailableTransferMode


class OptimalNetTransferCapacityOptions:
    """
    OptimalNetTransferCapacityOptions
    """

    def __init__(self,
                 area_from_bus_idx: IntVec,
                 area_to_bus_idx: IntVec,
                 transfer_method: AvailableTransferMode,
                 loading_threshold_to_report: float,
                 skip_generation_limits: bool,
                 transmission_reliability_margin: float,
                 branch_exchange_sensitivity: float,
                 use_branch_exchange_sensitivity: bool,
                 branch_rating_contribution: float,
                 use_branch_rating_contribution: bool,
                 consider_contingencies: bool,
                 opf_options: OptimalPowerFlowOptions,
                 lin_options: LinearAnalysisOptions):
        """

        :param area_from_bus_idx: array of area "from" bus indices
        :param area_to_bus_idx: array of area "to" bus indices
        :param transfer_method: AvailableTransferMode
        :param loading_threshold_to_report:
        :param skip_generation_limits:
        :param transmission_reliability_margin:
        :param branch_exchange_sensitivity:
        :param use_branch_exchange_sensitivity:
        :param branch_rating_contribution:
        :param use_branch_rating_contribution:
        :param consider_contingencies:
        :param opf_options: OptimalPowerFlowOptions
        :param lin_options: LinearAnalysisOptions
        """

        self.area_from_bus_idx: IntVec = area_from_bus_idx
        self.area_to_bus_idx: IntVec = area_to_bus_idx

        self.transfer_method: AvailableTransferMode = transfer_method
        self.loading_threshold_to_report: float = loading_threshold_to_report
        self.skip_generation_limits: bool = skip_generation_limits
        self.transmission_reliability_margin: float = transmission_reliability_margin
        self.branch_exchange_sensitivity: float = branch_exchange_sensitivity
        self.use_branch_exchange_sensitivity: bool = use_branch_exchange_sensitivity
        self.branch_rating_contribution: float = branch_rating_contribution
        self.use_branch_rating_contribution: bool = use_branch_rating_contribution
        self.consider_contingencies: bool = consider_contingencies

        self.opf_options: OptimalPowerFlowOptions = opf_options

        self.lin_options: LinearAnalysisOptions = lin_options
