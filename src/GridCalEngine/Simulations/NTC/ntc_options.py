# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from GridCalEngine.Simulations.options_template import OptionsTemplate
from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from GridCalEngine.Simulations.LinearFactors.linear_analysis_options import LinearAnalysisOptions
from GridCalEngine.basic_structures import IntVec
from GridCalEngine.enumerations import AvailableTransferMode, SubObjectType, DeviceType


class OptimalNetTransferCapacityOptions(OptionsTemplate):
    """
    OptimalNetTransferCapacityOptions
    """

    def __init__(self,
                 sending_bus_idx: IntVec,
                 receiving_bus_idx: IntVec,
                 transfer_method: AvailableTransferMode = AvailableTransferMode.InstalledPower,
                 loading_threshold_to_report: float = 98.0,
                 skip_generation_limits: bool = True,
                 transmission_reliability_margin: float = 400.0,
                 branch_exchange_sensitivity: float = 5.0 / 100.0,
                 use_branch_exchange_sensitivity: bool = True,
                 branch_rating_contribution: float = 70 / 100.0,
                 use_branch_rating_contribution: bool = False,
                 consider_contingencies: bool = False,
                 opf_options: OptimalPowerFlowOptions | None = None,
                 lin_options: LinearAnalysisOptions | None = None, ):
        """

        :param sending_bus_idx: array of area "from" bus indices
        :param receiving_bus_idx: array of area "to" bus indices
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
        OptionsTemplate.__init__(self, name="OptimalNetTransferCapacityOptions")

        self.sending_bus_idx: IntVec = sending_bus_idx
        self.receiving_bus_idx: IntVec = receiving_bus_idx

        self.transfer_method: AvailableTransferMode = transfer_method
        self.loading_threshold_to_report: float = loading_threshold_to_report
        self.skip_generation_limits: bool = skip_generation_limits
        self.transmission_reliability_margin: float = transmission_reliability_margin
        self.branch_exchange_sensitivity: float = branch_exchange_sensitivity
        self.use_branch_exchange_sensitivity: bool = use_branch_exchange_sensitivity
        self.branch_rating_contribution: float = branch_rating_contribution
        self.use_branch_rating_contribution: bool = use_branch_rating_contribution
        self.consider_contingencies: bool = consider_contingencies

        if opf_options is None:
            self.opf_options = OptimalPowerFlowOptions()
        else:
            self.opf_options: OptimalPowerFlowOptions = opf_options

        if lin_options is None:
            self.lin_options = LinearAnalysisOptions()
        else:
            self.lin_options: LinearAnalysisOptions = lin_options

        self.register(key="sending_bus_idx", tpe=SubObjectType.Array)
        self.register(key="receiving_bus_idx", tpe=SubObjectType.Array)
        self.register(key="transfer_method", tpe=AvailableTransferMode)
        self.register(key="loading_threshold_to_report", tpe=float)
        self.register(key="skip_generation_limits", tpe=bool)
        self.register(key="transmission_reliability_margin", tpe=float)
        self.register(key="branch_exchange_sensitivity", tpe=float)
        self.register(key="use_branch_exchange_sensitivity", tpe=bool)
        self.register(key="branch_rating_contribution", tpe=float)
        self.register(key="use_branch_rating_contribution", tpe=bool)
        self.register(key="consider_contingencies", tpe=bool)
        self.register(key="opf_options", tpe=DeviceType.SimulationOptionsDevice)
        self.register(key="lin_options", tpe=DeviceType.SimulationOptionsDevice)
