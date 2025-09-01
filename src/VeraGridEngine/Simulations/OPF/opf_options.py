# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import List, Union
from VeraGridEngine.enumerations import (SolverType, MIPSolvers, ZonalGrouping, TimeGrouping, AcOpfMode, DeviceType,
                                         SubObjectType)
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Devices.Aggregation.contingency_group import ContingencyGroup
from VeraGridEngine.Devices.Aggregation.inter_aggregation_info import InterAggregationInfo
from VeraGridEngine.Simulations.options_template import OptionsTemplate
from VeraGridEngine.basic_structures import Vec


class OptimalPowerFlowOptions(OptionsTemplate):
    """
    OptimalPowerFlowOptions
    """

    def __init__(self,
                 verbose: int = 0,
                 solver: SolverType = SolverType.LINEAR_OPF,
                 time_grouping: TimeGrouping = TimeGrouping.NoGrouping,
                 zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                 mip_solver=MIPSolvers.HIGHS,
                 power_flow_options: Union[None, PowerFlowOptions] = None,
                 consider_contingencies=False,
                 contingency_groups_used: List[ContingencyGroup] = (),
                 skip_generation_limits=False,
                 lodf_tolerance=0.001,
                 maximize_flows=False,
                 inter_aggregation_info: InterAggregationInfo | None = None,
                 unit_commitment=False,
                 generation_expansion_planning: bool = False,
                 export_model_fname: Union[None, str] = None,
                 generate_report=False,
                 ips_method: SolverType = SolverType.NR,
                 ips_tolerance: float = 1e-4,
                 ips_iterations: int = 100,
                 ips_trust_radius: float = 1.0,
                 ips_init_with_pf: bool = False,
                 ips_control_q_limits: bool = False,
                 acopf_mode: AcOpfMode = AcOpfMode.ACOPFstd,
                 acopf_v0: Vec | None = None,
                 acopf_S0: Vec | None = None,
                 robust: bool = False,):
        """
        Optimal power flow options
        :param verbose:
        :param solver:
        :param time_grouping:
        :param zonal_grouping:
        :param mip_solver:
        :param power_flow_options:
        :param consider_contingencies:
        :param contingency_groups_used:
        :param skip_generation_limits:
        :param lodf_tolerance:
        :param maximize_flows:
        :param inter_aggregation_info:
        :param unit_commitment:
        :param export_model_fname:
        :param generate_report:
        :param ips_method:
        :param ips_tolerance:
        :param ips_iterations:
        :param ips_trust_radius:
        :param ips_init_with_pf:
        :param ips_control_q_limits:
        :param acopf_mode:
        :param acopf_S0: Sbus initial solution
        :param acopf_v0: Voltage initial solution
        """
        OptionsTemplate.__init__(self, name="Optimal power flow options")

        self.verbose = verbose

        self.solver = solver

        self.time_grouping = time_grouping

        self.zonal_grouping = zonal_grouping

        self.mip_solver = mip_solver

        self.power_flow_options: PowerFlowOptions = power_flow_options if power_flow_options else PowerFlowOptions()

        self.skip_generation_limits = skip_generation_limits

        self.consider_contingencies = consider_contingencies

        self.contingency_groups_used: List[ContingencyGroup] = contingency_groups_used

        self.lodf_tolerance = lodf_tolerance

        self.maximize_flows = maximize_flows

        self.inter_aggregation_info = inter_aggregation_info

        self.unit_commitment = unit_commitment

        self.generation_expansion_planning = generation_expansion_planning

        self.max_va = 6.28

        self.max_vm = 1.0

        self.export_model_fname: Union[None, str] = export_model_fname

        self.generate_report = generate_report

        self.acopf_mode = acopf_mode

        self.robust = robust

        # IPS settings
        self.ips_method: SolverType = ips_method
        self.ips_tolerance = ips_tolerance
        self.ips_iterations = ips_iterations
        self.ips_trust_radius = ips_trust_radius
        self.ips_init_with_pf = ips_init_with_pf
        self.ips_control_q_limits = ips_control_q_limits

        self.acopf_v0 = acopf_v0
        self.acopf_S0 = acopf_S0

        self.register(key="verbose", tpe=int)
        self.register(key="solver", tpe=SolverType)
        self.register(key="time_grouping", tpe=TimeGrouping)
        self.register(key="zonal_grouping", tpe=ZonalGrouping)
        self.register(key="mip_solver", tpe=MIPSolvers)
        self.register(key="power_flow_options", tpe=DeviceType.SimulationOptionsDevice)
        self.register(key="skip_generation_limits", tpe=bool)
        self.register(key="consider_contingencies", tpe=bool)
        self.register(key="contingency_groups_used", tpe=SubObjectType.Array)
        self.register(key="lodf_tolerance", tpe=float)
        self.register(key="maximize_flows", tpe=bool)
        self.register(key="inter_aggregation_info", tpe=DeviceType.InterAggregationInfo)
        self.register(key="unit_commitment", tpe=bool)
        self.register(key="export_model_fname", tpe=str)
        self.register(key="generate_report", tpe=bool)
        self.register(key="acopf_mode", tpe=AcOpfMode)

        self.register(key="ips_method", tpe=SolverType)
        self.register(key="ips_tolerance", tpe=float)
        self.register(key="ips_iterations", tpe=int)
        self.register(key="ips_trust_radius", tpe=float)
        self.register(key="ips_init_with_pf", tpe=bool)
        self.register(key="ips_control_q_limits", tpe=bool)
        self.register(key="robust", tpe=bool)

        self.register(key="acopf_v0", tpe=Vec)
        self.register(key="acopf_S0", tpe=Vec)
