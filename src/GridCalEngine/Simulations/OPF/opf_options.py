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

from typing import List, Union
from GridCalEngine.basic_structures import TimeGrouping, MIPSolvers, ZonalGrouping
from GridCalEngine.basic_structures import SolverType


class OptimalPowerFlowOptions:
    """
    OptimalPowerFlowOptions
    """

    def __init__(self,
                 verbose=False,
                 solver: SolverType = SolverType.DC_OPF,
                 time_grouping: TimeGrouping = TimeGrouping.NoGrouping,
                 zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                 mip_solver=MIPSolvers.CBC,
                 faster_less_accurate=False,
                 power_flow_options=None,
                 bus_types=None,
                 consider_contingencies=False,
                 skip_generation_limits=False,
                 lodf_tolerance=0.001,
                 maximize_flows=False,
                 area_from_bus_idx: List = None,
                 area_to_bus_idx: List = None,
                 areas_from: List = None,
                 areas_to: List = None,
                 unit_commitment=False,
                 export_model_fname: Union[None, str] = None,
                 generate_report=False):
        """
        Optimal power flow options
        :param verbose:
        :param solver:
        :param time_grouping:
        :param zonal_grouping:
        :param mip_solver:
        :param faster_less_accurate:
        :param power_flow_options:
        :param bus_types:
        :param consider_contingencies:
        :param skip_generation_limits:
        :param lodf_tolerance:
        :param maximize_flows:
        :param area_from_bus_idx:
        :param area_to_bus_idx:
        :param areas_from:
        :param areas_to:
        :param unit_commitment:
        :param export_model_fname:
        """
        self.verbose = verbose

        self.solver = solver

        self.grouping = time_grouping

        self.mip_solver = mip_solver

        self.faster_less_accurate = faster_less_accurate

        self.power_flow_options = power_flow_options

        self.bus_types = bus_types

        self.zonal_grouping = zonal_grouping

        self.skip_generation_limits = skip_generation_limits

        self.consider_contingencies = consider_contingencies

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
