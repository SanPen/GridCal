# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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
from enum import Enum
from typing import List, Dict, Tuple, Any
import numpy as np
import time

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.basic_structures import TimeGrouping, MIPSolvers, ZonalGrouping
from GridCal.Engine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.OPF.ac_opf import OpfAc
from GridCal.Engine.Simulations.OPF.dc_opf import OpfDc
from GridCal.Engine.Simulations.OPF.simple_dispatch import OpfSimple
from GridCal.Engine.basic_structures import SolverType
from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from GridCal.Engine.Core.snapshot_opf_data import compile_snapshot_opf_circuit
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import DriverTemplate

########################################################################################################################
# Optimal Power flow classes
########################################################################################################################


class OptimalPowerFlowOptions:

    def __init__(self, verbose=False,
                 solver: SolverType = SolverType.DC_OPF,
                 time_grouping: TimeGrouping = TimeGrouping.NoGrouping,
                 zonal_grouping: ZonalGrouping = ZonalGrouping.NoGrouping,
                 mip_solver=MIPSolvers.CBC,
                 faster_less_accurate=False,
                 power_flow_options=None,
                 bus_types=None,
                 consider_contingencies=False,
                 skip_generation_limits=False,
                 tolerance=1.0,
                 LODF=None,
                 lodf_tolerance=0.001,
                 maximize_flows=False,
                 area_from_bus_idx: List = None,
                 area_to_bus_idx: List = None):
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
        :param tolerance:
        :param LODF:
        :param lodf_tolerance:
        :param maximize_flows:
        :param area_from_bus_idx:
        :param area_to_bus_idx:
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

        self.LODF = LODF

        self.tolerance = tolerance

        self.lodf_tolerance = lodf_tolerance

        self.maximize_flows = maximize_flows

        self.area_from_bus_idx = area_from_bus_idx

        self.area_to_bus_idx = area_to_bus_idx
