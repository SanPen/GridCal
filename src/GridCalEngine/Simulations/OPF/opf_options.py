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

from typing import List, Union
from GridCalEngine.enumerations import (SolverType, MIPSolvers, ZonalGrouping, TimeGrouping, AcOpfMode, DeviceType,
                                        SubObjectType)
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Devices.Aggregation.contingency_group import ContingencyGroup
from GridCalEngine.Devices.Aggregation.area import Area
from GridCalEngine.Simulations.options_template import OptionsTemplate
from GridCalEngine.basic_structures import IntVec


class OptimalPowerFlowOptions(OptionsTemplate):
    """
    OptimalPowerFlowOptions
    """

    def __init__(self,
                 verbose: int = 0,
                 solver: SolverType = SolverType.LINEAR_OPF,
                 time_grouping: TimeGrouping = TimeGrouping.NoGrouping,
                 zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                 mip_solver=MIPSolvers.CBC,
                 power_flow_options: Union[None, PowerFlowOptions] = None,
                 consider_contingencies=False,
                 contingency_groups_used: List[ContingencyGroup] = (),
                 skip_generation_limits=False,
                 lodf_tolerance=0.001,
                 maximize_flows=False,
                 area_from_bus_idx: IntVec = None,
                 area_to_bus_idx: IntVec = None,
                 areas_from: List[Area] = None,
                 areas_to: List[Area] = None,
                 unit_commitment=False,
                 export_model_fname: Union[None, str] = None,
                 generate_report=False,
                 ips_method: SolverType = SolverType.NR,
                 ips_tolerance: float = 1e-4,
                 ips_iterations: int = 100,
                 ips_trust_radius: float = 1.0,
                 ips_init_with_pf: bool = False,
                 acopf_mode: AcOpfMode = AcOpfMode.ACOPFstd):
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
        :param area_from_bus_idx:
        :param area_to_bus_idx:
        :param areas_from:
        :param areas_to:
        :param unit_commitment:
        :param export_model_fname:
        :param generate_report:
        :param ips_method:
        :param ips_tolerance:
        :param ips_iterations:
        :param ips_trust_radius:
        :param ips_init_with_pf:
        :param acopf_mode:
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

        self.area_from_bus_idx = area_from_bus_idx

        self.area_to_bus_idx = area_to_bus_idx

        self.areas_from = areas_from

        self.areas_to = areas_to

        self.unit_commitment = unit_commitment

        self.max_va = 6.28

        self.max_vm = 1.0

        self.export_model_fname: Union[None, str] = export_model_fname

        self.generate_report = generate_report

        self.acopf_mode = acopf_mode

        # IPS settings
        self.ips_method: SolverType = ips_method
        self.ips_tolerance = ips_tolerance
        self.ips_iterations = ips_iterations
        self.ips_trust_radius = ips_trust_radius
        self.ips_init_with_pf = ips_init_with_pf

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
        self.register(key="area_from_bus_idx", tpe=SubObjectType.Array)
        self.register(key="area_to_bus_idx", tpe=SubObjectType.Array)
        self.register(key="areas_from", tpe=SubObjectType.Array)
        self.register(key="areas_to", tpe=SubObjectType.Array)
        self.register(key="unit_commitment", tpe=bool)
        self.register(key="export_model_fname", tpe=str)
        self.register(key="generate_report", tpe=bool)
        self.register(key="acopf_mode", tpe=AcOpfMode)

        self.register(key="ips_method", tpe=SolverType)
        self.register(key="ips_tolerance", tpe=float)
        self.register(key="ips_iterations", tpe=int)
        self.register(key="ips_trust_radius", tpe=float)
        self.register(key="ips_init_with_pf", tpe=bool)

