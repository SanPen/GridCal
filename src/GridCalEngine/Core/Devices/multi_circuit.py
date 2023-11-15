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

import os
import cmath
import warnings

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Union, Any, Callable
from uuid import getnode as get_mac, uuid4
from datetime import timedelta, datetime
import networkx as nx
from matplotlib import pyplot as plt
from scipy.sparse import csc_matrix, lil_matrix

from GridCalEngine.Core import EditableDevice, Switch, UPFC, VSC, Winding, Transformer2W, DcLine, Line
from GridCalEngine.basic_structures import DateVec, IntVec, StrVec, Vec, Mat, CxVec, IntMat, CxMat
from GridCalEngine.data_logger import DataLogger
import GridCalEngine.Core.Devices as dev
import GridCalEngine.basic_structures as bs
import GridCalEngine.Core.topology as tp
from GridCalEngine.enumerations import DeviceType


def get_system_user() -> str:
    """
    Get the system mac + user name
    :return: string with the system mac address and the current user
    """

    # get the proper function to find the user depending on the platform
    if 'USERNAME' in os.environ:
        user = os.environ["USERNAME"]
    elif 'USER' in os.environ:
        user = os.environ["USER"]
    else:
        user = ''

    try:
        mac = get_mac()
    except:
        mac = ''

    return str(mac) + ':' + user


class MultiCircuit:
    """
    The concept of circuit should be easy enough to understand. It represents a set of
    nodes (:ref:`buses<Bus>`) and :ref:`Branches<Branch>` (lines, transformers or other
    impedances).

    The :ref:`MultiCircuit<multicircuit>` class is the main object in **GridCal**. It
    represents a circuit that may contain islands. It is important to understand that a
    circuit split in two or more islands cannot be simulated as is, because the
    admittance matrix would be singular. The solution to this is to split the circuit
    in island-circuits. Therefore :ref:`MultiCircuit<multicircuit>` identifies the
    islands and creates individual **Circuit** objects for each of them.

    **GridCal** uses an object oriented approach for the data management. This allows
    to group the data in a smart way. In **GridCal** there are only two types of object
    directly declared in a **Circuit** or :ref:`MultiCircuit<multicircuit>` object.
    These are the :ref:`Bus<bus>` and the :ref:`Branch<branch>`. The Branches connect
    the buses and the buses contain all the other possible devices like loads,
    generators, batteries, etc. This simplifies enormously the management of element
    when adding, associating and deleting.

    .. code:: ipython3

        from GridCalEngine.Core.multi_circuit import MultiCircuit
        grid = MultiCircuit(name="My grid")

    """

    def __init__(self,
                 name: str = '',
                 Sbase: float = 100,
                 fbase: float = 50.0,
                 idtag: Union[str, None] = None):
        """
        class constructor
        :param name: name of the circuit
        :param Sbase: base power in MVA
        :param fbase: base frequency in Hz
        :param idtag: unique identifier
        """

        self.name: str = name

        if idtag is None:
            self.idtag: str = uuid4().hex
        else:
            self.idtag: str = idtag

        self.comments: str = ''

        # this is a number that serves
        self.model_version: int = 2

        # user mane
        self.user_name: str = get_system_user()

        # Base power (MVA)
        self.Sbase: float = Sbase

        # Base frequency in Hz
        self.fBase: float = fbase

        # Should be able to accept Branches, Lines and Transformers alike
        # self.Branches = list()

        self.lines: List[dev.Line] = list()

        self.dc_lines: List[dev.DcLine] = list()

        self.transformers2w: List[dev.Transformer2W] = list()

        self.hvdc_lines: List[dev.HvdcLine] = list()

        self.vsc_devices: List[dev.VSC] = list()

        self.upfc_devices: List[dev.UPFC] = list()

        self.switch_devices: List[dev.Switch] = list()

        self.transformers3w: List[dev.Transformer3W] = list()

        self.windings: List[dev.Winding] = list()

        # array of branch indices in the master circuit
        self.branch_original_idx: List[int] = list()

        # Should accept buses
        self.buses: List[dev.Bus] = list()

        # array of connectivity nodes
        self.connectivity_nodes: List[dev.ConnectivityNode] = list()

        # array of bus indices in the master circuit
        self.bus_original_idx: List[int] = list()

        # Dictionary relating the bus object to its index. Updated upon compilation
        self.buses_dict: Dict[dev.Bus, int] = dict()

        # List of overhead line objects
        self.overhead_line_types: List[dev.OverheadLineType] = list()

        # list of wire types
        self.wire_types: List[dev.Wire] = list()

        # underground cable lines
        self.underground_cable_types: List[dev.UndergroundLineType] = list()

        # sequence modelled lines
        self.sequence_line_types: List[dev.SequenceLineType] = list()

        # List of transformer types
        self.transformer_types: List[dev.TransformerType] = list()

        # list of substations
        # self.default_substation: dev.Substation = dev.Substation('Default Substation')
        self.substations: List[dev.Substation] = list()  # [self.default_substation]

        # list of areas
        # self.default_area: dev.Area = dev.Area('Default area')
        self.areas: List[dev.Area] = list()  # [self.default_area]

        # list of zones
        # self.default_zone: dev.Zone = dev.Zone('Default zone')
        self.zones: List[dev.Zone] = list()  # [self.default_zone]

        # list of countries
        # self.default_country: dev.Country = dev.Country('Default country')
        self.countries: List[dev.Country] = list()  # [self.default_country]

        # logger of events
        self.logger: bs.Logger = bs.Logger()

        # Bus-Branch graph
        self.graph = None

        # dictionary of bus objects -> bus indices
        self.bus_dictionary: Dict[str, dev.Bus] = dict()

        # master time profile
        self.time_profile: DateVec = None

        # contingencies
        self.contingencies: List[dev.Contingency] = list()

        # contingency group
        self.contingency_groups: List[dev.ContingencyGroup] = list()

        # investments
        self.investments: List[dev.Investment] = list()

        # investments group
        self.investments_groups: List[dev.InvestmentsGroup] = list()

        # technologies
        self.technologies: List[dev.Technology] = list()

        # fuels
        self.fuels: List[dev.Fuel] = list()

        # emission gasses
        self.emission_gases: List[dev.EmissionGas] = list()

        self.generators_technologies: List[dev.GeneratorTechnology] = list()

        self.generators_fuels: List[dev.GeneratorFuel] = list()

        self.generators_emissions: List[dev.GeneratorEmission] = list()

        # fluids
        self.fluid_nodes: List[dev.FluidNode] = list()
        self.fluid_paths: List[dev.FluidPath] = list()
        self.fluid_turbines: List[dev.FluidTurbine] = list()
        self.fluid_pumps: List[dev.FluidPump] = list()

        # objects with profiles
        self.objects_with_profiles = {
            "Substation": [
                dev.Bus(),
                dev.Substation(),
                dev.Zone(),
                dev.Area(),
                dev.Country(),
            ],
            "Injections": [
                dev.Generator(),
                dev.Battery(),
                dev.Load(),
                dev.StaticGenerator(),
                dev.ExternalGrid(),
                dev.Shunt(),
            ],
            "Branches": [
                dev.Line(),
                dev.DcLine(),
                dev.Transformer2W(),
                dev.Winding(),
                dev.Transformer3W(),
                dev.HvdcLine(),
                dev.VSC(),
                dev.UPFC(),
            ],
            "Fluid": [
                dev.FluidNode(),
                dev.FluidPath(),
                dev.FluidTurbine(),
                dev.FluidPump(),
            ],
            "Groups": [
                dev.ContingencyGroup(),
                dev.Contingency(),
                dev.InvestmentsGroup(),
                dev.Investment(),
            ],
            "Tags & Associations": [
                dev.Technology(),
                dev.Fuel(),
                dev.EmissionGas(),
                dev.GeneratorTechnology(),
                dev.GeneratorFuel(),
                dev.GeneratorEmission(),
            ],
            "Catalogue": [
                dev.Wire(),
                dev.OverheadLineType(),
                dev.UndergroundLineType(),
                dev.SequenceLineType(),
                dev.TransformerType()
            ]
        }

        # dictionary of profile magnitudes per object
        self.profile_magnitudes = dict()

        self.device_type_name_dict: Dict[str, DeviceType] = dict()

        '''
        self.type_name = 'Shunt'

        self.properties_with_profile = ['Y']
        '''
        for key, elm_list in self.objects_with_profiles.items():
            for elm in elm_list:
                if elm.properties_with_profile is not None:
                    key = str(elm.device_type.value)
                    profile_attr = list(elm.properties_with_profile.keys())
                    profile_types = [elm.editable_headers[attr].tpe for attr in profile_attr]
                    self.profile_magnitudes[key] = (profile_attr, profile_types)
                    self.device_type_name_dict[key] = elm.device_type

        # list of declared diagrams
        self.diagrams: List[Union[dev.MapDiagram, dev.BusBranchDiagram, dev.NodeBreakerDiagram]] = list()

    def __str__(self):
        return str(self.name)

    @property
    def has_time_series(self) -> bool:
        """
        Area there time series?
        :return: True / False
        """
        # sanity check
        if len(self.buses) > 0:
            if self.buses[0].active_prof is None:

                if self.time_profile is not None:
                    warnings.warn('The grid has a time signature but the objects do not!')
                return False

        return self.time_profile is not None

    def get_objects_with_profiles_list(self) -> List[dev.EditableDevice]:
        """
        get objects_with_profiles in the form of list
        :return: List[dev.EditableDevice]
        """
        lst = list()
        for key, elm_list in self.objects_with_profiles.items():
            for elm in elm_list:
                lst.append(elm)
        return lst

    def get_objects_with_profiles_str_dict(self) -> Dict[str, List[str]]:
        """
        get objects_with_profiles as a strings dictionary
        :return:
        """
        d = dict()
        for key, elm_list in self.objects_with_profiles.items():
            d[key] = [o.device_type.value for o in elm_list]
        return d

    def get_zones(self) -> List[dev.Zone]:
        """
        Get list of zones
        :return: List[dev.Zone]
        """
        return self.zones

    def get_zone_number(self) -> int:
        """
        Get number of areas
        :return: number of areas
        """
        return len(self.zones)

    def get_areas(self) -> List[dev.Area]:
        """
        Get list of areas
        :return: List[dev.Area]
        """
        return self.areas

    def get_area_names(self) -> StrVec:
        """
        Get array of area names
        :return: StrVec
        """
        return np.array([a.name for a in self.areas])

    def get_area_number(self) -> int:
        """
        Get number of areas
        :return: number of areas
        """
        return len(self.areas)

    def get_substations(self) -> List[dev.Substation]:
        """
        Get a list of substations
        :return: List[dev.Substation]
        """
        return self.substations

    def get_substation_number(self) -> int:
        """
        Get number of areas
        :return: number of areas
        """
        return len(self.substations)

    def get_bus_number(self) -> int:
        """
        Return the number of buses
        :return: number
        """
        return len(self.buses)

    def get_bus_default_types(self) -> IntVec:
        """
        Return an array of bus types
        :return: number
        """
        return np.ones(len(self.buses), dtype=int)

    @staticmethod
    def get_branches_types() -> List[DeviceType]:
        """
        Get branches types
        :return list of device types
        """
        return [DeviceType.LineDevice,
                DeviceType.DCLineDevice,
                DeviceType.HVDCLineDevice,
                DeviceType.Transformer2WDevice,
                DeviceType.WindingDevice,
                DeviceType.SwitchDevice,
                DeviceType.VscDevice,
                DeviceType.UpfcDevice]

    def get_branch_lists_wo_hvdc(self) -> List[Union[
        List[dev.Line], List[dev.DcLine], List[dev.Transformer2W], List[dev.Winding], List[dev.VSC], List[dev.UPFC]]]:
        """
        Get list of the branch lists
        :return: List[Union[List[dev.Line], List[dev.DcLine], List[dev.Transformer2W],
                            List[dev.Winding], List[dev.VSC], List[dev.UPFC]]]
        """
        return [
            self.lines,
            self.dc_lines,
            self.transformers2w,
            self.windings,
            self.vsc_devices,
            self.upfc_devices
        ]

    def get_branch_names_wo_hvdc(self) -> StrVec:
        """
        Get all branch names without HVDC devices
        :return: StrVec
        """
        names = list()
        for lst in self.get_branch_lists_wo_hvdc():
            for elm in lst:
                names.append(elm.name)
        return np.array(names)

    def get_branch_lists(self) -> List[Union[List[dev.Line],
    List[dev.DcLine],
    List[dev.Transformer2W],
    List[dev.Winding], List[dev.VSC], List[dev.UPFC],
    List[dev.HvdcLine]]]:
        """
        Get list of the branch lists
        :return: list of lists
        """
        lst = self.get_branch_lists_wo_hvdc()
        lst.append(self.hvdc_lines)
        return lst

    def get_branch_number(self) -> int:
        """
        return the number of Branches (of all types)
        :return: number
        """
        m = 0
        for branch_list in self.get_branch_lists():
            m += len(branch_list)
        return m

    def get_branch_names(self) -> StrVec:
        """
        Get array of all branch names
        :return: StrVec
        """

        names = list()
        for lst in self.get_branch_lists():
            for elm in lst:
                names.append(elm.name)
        return np.array(names)

    def get_branch_number_wo_hvdc(self) -> int:
        """
        return the number of Branches (of all types)
        :return: number
        """
        count = 0
        for branch_list in self.get_branch_lists_wo_hvdc():
            count += len(branch_list)
        return count

    def get_branch_number_wo_hvdc_FT(self) -> Tuple[IntVec, IntVec]:
        """
        get the from and to arrays of indices
        :return: IntVec, IntVec
        """
        devices = self.get_branches_wo_hvdc()
        m = len(devices)
        F = np.zeros(m, dtype=int)
        T = np.zeros(m, dtype=int)
        bus_dict = self.get_bus_index_dict()
        for i, elm in enumerate(devices):
            F[i] = bus_dict[elm.bus_from]
            T[i] = bus_dict[elm.bus_to]
        return F, T

    def get_hvdc_FT(self) -> Tuple[IntVec, IntVec]:
        """
        get the from and to arrays of indices of HVDC lines
        :return: IntVec, IntVec
        """
        m = len(self.hvdc_lines)
        F = np.zeros(m, dtype=int)
        T = np.zeros(m, dtype=int)
        bus_dict = self.get_bus_index_dict()
        for i, elm in enumerate(self.hvdc_lines):
            F[i] = bus_dict[elm.bus_from]
            T[i] = bus_dict[elm.bus_to]
        return F, T

    def get_time_number(self) -> int:
        """
        Return the number of buses
        :return: number
        """
        if self.time_profile is not None:
            return len(self.time_profile)
        else:
            return 0

    def get_all_time_indices(self) -> IntVec:
        """
        Get array with all the time steps
        :return: IntVec
        """
        return np.arange(0, self.get_time_number())

    def get_contingency_number(self) -> int:
        """
        Get number of contingencies
        :return:
        """
        return len(self.contingencies)

    def get_dimensions(self):
        """
        Get the three dimensions of the circuit: number of buses, number of Branches, number of time steps
        :return: (nbus, nbranch, ntime)
        """
        return self.get_bus_number(), self.get_branch_number(), self.get_time_number()

    def get_branch_active_time_array(self) -> IntMat:
        """
        Get branch active matrix
        :return: array with branch active status
        """
        active = np.empty((self.get_time_number(), self.get_branch_number_wo_hvdc()), dtype=int)
        for i, b in enumerate(self.get_branches_wo_hvdc()):
            active[:, i] = b.active_prof
        return active

    def get_topologic_group_dict(self) -> Dict[int, List[int]]:
        """
        Get numerical circuit time groups
        :return: Dictionary with the time: [array of times] represented by the index, for instance
                 {0: [0, 1, 2, 3, 4], 5: [5, 6, 7, 8]}
                 This means that [0, 1, 2, 3, 4] are represented by the topology of 0
                 and that [5, 6, 7, 8] are represented by the topology of 5
        """

        return tp.find_different_states(
            states_array=self.get_branch_active_time_array()
        )

    def get_diagrams(self) -> List[Union[dev.MapDiagram, dev.BusBranchDiagram, dev.NodeBreakerDiagram]]:
        """
        Get list of diagrams
        :return: MapDiagram, BusBranchDiagram, NodeBreakerDiagram device
        """
        return self.diagrams

    def has_diagrams(self) -> bool:
        """
        Check if there are diagrams stored
        :return:
        """
        return len(self.diagrams) > 0

    def add_diagram(self, diagram: Union[dev.MapDiagram, dev.BusBranchDiagram, dev.NodeBreakerDiagram]):
        """
        Add diagram
        :param diagram: MapDiagram, BusBranchDiagram, NodeBreakerDiagram device
        :return:
        """
        self.diagrams.append(diagram)

    def remove_diagram(self, diagram: Union[dev.MapDiagram, dev.BusBranchDiagram, dev.NodeBreakerDiagram]):
        """
        Remove diagrams
        :param diagram: MapDiagram, BusBranchDiagram, NodeBreakerDiagram device
        """
        self.diagrams.remove(diagram)

    def clear(self):
        """
        Clear the multi-circuit (remove the bus and branch objects)
        """
        # Should be able to accept Branches, Lines and Transformers alike
        self.lines = list()
        self.dc_lines = list()
        self.transformers2w = list()
        self.transformers3w = list()
        self.windings = list()
        self.hvdc_lines = list()
        self.vsc_devices = list()
        self.upfc_devices = list()

        self.substations = list()
        self.areas = list()
        self.technologies = list()
        self.contingencies = list()
        self.contingency_groups = list()
        self.investments = list()
        self.investments_groups = list()
        self.fuels = list()
        self.emission_gases = list()

        # array of branch indices in the master circuit
        self.branch_original_idx = list()

        # Should accept buses
        self.buses = list()

        # array of bus indices in the master circuit
        self.bus_original_idx = list()

        # Dictionary relating the bus object to its index. Updated upon compilation
        self.buses_dict = dict()

        # List of overhead line objects
        self.overhead_line_types = list()

        # list of wire types
        self.wire_types = list()

        # underground cable lines
        self.underground_cable_types = list()

        # sequence modelled lines
        self.sequence_line_types = list()

        # List of transformer types
        self.transformer_types = list()

        # Bus-Branch graph
        self.graph = None

        self.bus_dictionary = dict()

        self.time_profile = None

        self.contingencies = list()

    def get_buses(self) -> List[dev.Bus]:
        """
        List of buses
        :return:
        """
        return self.buses

    def get_bus_names(self) -> StrVec:
        """
        List of bus names
        :return:
        """
        return np.array([e.name for e in self.buses])

    def get_branches_wo_hvdc(self) -> list[Union[Switch, UPFC, VSC, Winding, Transformer2W, DcLine, Line]]:
        """
        Return all the branch objects.
        :return: lines + transformers 2w + hvdc
        """
        return self.lines + self.dc_lines + self.transformers2w + self.windings + self.vsc_devices + self.upfc_devices + self.switch_devices

    def get_branches_wo_hvdc_names(self) -> List[str]:
        """
        Get the non HVDC branches' names
        :return: list of names
        """
        return [e.name for e in self.get_branches_wo_hvdc()]

    def get_branches(self) -> List[dev.Branch]:
        """
        Return all the branch objects
        :return: lines + transformers 2w + hvdc
        """
        return self.get_branches_wo_hvdc() + self.hvdc_lines

    def get_contingency_devices(self) -> List[dev.EditableDevice]:
        """
        Get a list of devices susceptible to be included in contingencies
        :return: list of devices
        """
        return self.get_branches() + self.get_generators()

    def get_investment_devices(self) -> List[dev.EditableDevice]:
        """
        Get a list of devices susceptible to be included in investments
        :return: list of devices
        """
        return self.get_branches() + self.get_generators() + self.get_batteries() + self.get_shunts() + self.get_loads() + self.buses

    def get_investmenst_by_groups(self) -> List[Tuple[dev.InvestmentsGroup, List[dev.Investment]]]:
        """
        Get a dictionary of investments goups and their
        :return: list of investment groups and their list of associated investments
        """
        d = {e: list() for e in self.investments_groups}

        for inv in self.investments:
            inv_list = d.get(inv.group, None)

            if inv_list is not None:
                inv_list.append(inv)

        # second pass, sort it
        res = list()
        for inv_group in self.investments_groups:

            inv_list = d.get(inv_group, None)

            if inv_list is not None:
                res.append((inv_group, inv_list))
            else:
                res.append((inv_group, list()))

        return res

    def get_investmenst_by_groups_index_dict(self) -> Dict[int, List[dev.Investment]]:
        """
        Get a dictionary of investments goups and their
        :return: Dict[investment group index] = list of investments
        """
        d = {e: idx for idx, e in enumerate(self.investments_groups)}

        res = dict()
        for inv in self.investments:
            inv_group_idx = d.get(inv.group, None)
            inv_list = res.get(inv_group_idx, None)
            if inv_list is None:
                res[inv_group_idx] = [inv]
            else:
                inv_list.append(inv)

        return res

    def get_investment_groups_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([e.name for e in self.investments_groups])

    def get_lines(self) -> List[dev.Line]:
        """
        get list of ac lines
        :return: list of lines
        """
        return self.lines

    def get_transformers2w(self) -> List[dev.Transformer2W]:
        """
        get list of 2-winding transformers
        :return: list of transformers
        """
        return self.transformers2w

    def get_transformers2w_number(self) -> int:
        """
        get the number of 2-winding transformers
        :return: int
        """
        return len(self.transformers2w)

    def get_transformers2w_names(self) -> List[str]:
        """
        get a list of names of the 2-winding transformers
        :return: list of names
        """
        return [elm.name for elm in self.transformers2w]

    def get_windings(self) -> List[dev.Winding]:
        """

        :return:
        """
        return self.windings

    def get_windings_number(self) -> int:
        """

        :return:
        """
        return len(self.windings)

    def get_windings_names(self) -> List[str]:
        """

        :return:
        """
        return [elm.name for elm in self.windings]

    def get_transformers3w(self) -> List[dev.Transformer3W]:
        """

        :return:
        """
        return self.transformers3w

    def get_transformers3w_number(self) -> int:
        """

        :return:
        """
        return len(self.transformers3w)

    def get_transformers3w_names(self) -> List[str]:
        """

        :return:
        """
        return [elm.name for elm in self.transformers3w]

    def get_vsc(self) -> List[dev.VSC]:
        """

        :return:
        """
        return self.vsc_devices

    def get_dc_lines(self) -> List[dev.DcLine]:
        """

        :return:
        """
        return self.dc_lines

    def get_upfc(self) -> List[dev.UPFC]:
        """

        :return:
        """
        return self.upfc_devices

    def get_switches(self) -> List[dev.Switch]:
        """

        :return:
        """
        return self.switch_devices

    def get_hvdc(self) -> List[dev.HvdcLine]:
        """

        :return:
        """
        return self.hvdc_lines

    def get_hvdc_number(self) -> int:
        """

        :return:
        """
        return len(self.hvdc_lines)

    def get_hvdc_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([elm.name for elm in self.hvdc_lines])

    def get_loads(self) -> List[dev.Load]:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                elm.bus = bus
            lst = lst + bus.loads
        return lst

    def get_loads_number(self) -> int:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        val = 0
        for bus in self.buses:
            val = val + len(bus.loads)
        return val

    def get_load_names(self) -> StrVec:
        """
        Returns a list of :ref:`Load<load>` names.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                lst.append(elm.name)
        return np.array(lst)

    def get_external_grids(self) -> List[dev.ExternalGrid]:
        """
        Returns a list of :ref:`ExternalGrid<external_grid>` objects in the grid.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.external_grids:
                elm.bus = bus
            lst = lst + bus.external_grids
        return lst

    def get_external_grid_names(self) -> StrVec:
        """
        Returns a list of :ref:`ExternalGrid<external_grid>` names.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.external_grids:
                lst.append(elm.name)
        return np.array(lst)

    def get_static_generators(self) -> List[dev.StaticGenerator]:
        """
        Returns a list of :ref:`StaticGenerator<static_generator>` objects in the grid.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.static_generators:
                elm.bus = bus
            lst = lst + bus.static_generators
        return lst

    def get_static_generators_names(self) -> StrVec:
        """
        Returns a list of :ref:`StaticGenerator<static_generator>` names.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.static_generators:
                lst.append(elm.name)
        return np.array(lst)

    def get_calculation_loads(self) -> List[dev.Load]:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                elm.bus = bus
            lst += bus.loads

            for elm in bus.external_grids:
                elm.bus = bus
            lst += bus.external_grids

            for elm in bus.static_generators:
                elm.bus = bus
            lst += bus.static_generators

        return lst

    def get_calculation_loads_number(self) -> int:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        val = 0
        for bus in self.buses:
            val = val + len(bus.loads) + len(bus.external_grids) + len(bus.static_generators)
        return val

    def get_calculation_load_names(self) -> StrVec:
        """
        Returns a list of :ref:`Load<load>` names.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                lst.append(elm.name)

            for elm in bus.external_grids:
                lst.append(elm.name)

            for elm in bus.static_generators:
                lst.append(elm.name)

        return np.array(lst)

    def get_shunts(self) -> List[dev.Shunt]:
        """
        Returns a list of :ref:`Shunt<shunt>` objects in the grid.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.shunts:
                elm.bus = bus
            lst = lst + bus.shunts
        return lst

    def get_shunt_names(self):
        """
        Returns a list of :ref:`Shunt<shunt>` names.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.shunts:
                lst.append(elm.name)
        return np.array(lst)

    def get_generators(self) -> List[dev.Generator]:
        """
        Returns a list of :ref:`Generator<generator>` objects in the grid.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.generators:
                elm.bus = bus
            lst = lst + bus.generators
        return lst

    def get_generators_number(self) -> int:
        """
        Get the number of generators
        :return: int
        """
        val = 0
        for bus in self.buses:
            val = val + len(bus.generators)
        return val

    def get_generator_names(self) -> StrVec:
        """
        Returns a list of :ref:`Generator<generator>` names.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.generators:
                lst.append(elm.name)
        return np.array(lst)

    def get_batteries(self) -> List[dev.Battery]:
        """
        Returns a list of :ref:`Battery<battery>` objects in the grid.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                elm.bus = bus
            lst = lst + bus.batteries
        return lst

    def get_batteries_number(self) -> int:
        """
        Returns a list of :ref:`Battery<battery>` objects in the grid.
        """
        val = 0
        for bus in self.buses:
            val = val + len(bus.batteries)
        return val

    def get_battery_names(self) -> StrVec:
        """
        Returns a list of :ref:`Battery<battery>` names.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                lst.append(elm.name)
        return np.array(lst)

    def get_battery_capacities(self):
        """
        Returns a list of :ref:`Battery<battery>` capacities.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                lst.append(elm.Enom)
        return np.array(lst)

    def get_elements_by_type(self, element_type: DeviceType):
        """
        Get set of elements and their parent nodes
        :param element_type: DeviceTYpe instance
        :return: List of elements, it raises an exception if the elements are unknown
        """

        if element_type == DeviceType.LoadDevice:
            return self.get_loads()

        elif element_type == DeviceType.StaticGeneratorDevice:
            return self.get_static_generators()

        elif element_type == DeviceType.GeneratorDevice:
            return self.get_generators()

        elif element_type == DeviceType.BatteryDevice:
            return self.get_batteries()

        elif element_type == DeviceType.ShuntDevice:
            return self.get_shunts()

        elif element_type == DeviceType.ExternalGridDevice:
            return self.get_external_grids()

        elif element_type == DeviceType.LineDevice:
            return self.lines

        elif element_type == DeviceType.Transformer2WDevice:
            return self.transformers2w

        elif element_type == DeviceType.Transformer3WDevice:
            return self.transformers3w

        elif element_type == DeviceType.WindingDevice:
            return self.windings

        elif element_type == DeviceType.HVDCLineDevice:
            return self.hvdc_lines

        elif element_type == DeviceType.UpfcDevice:
            return self.upfc_devices

        elif element_type == DeviceType.VscDevice:
            return self.vsc_devices

        elif element_type == DeviceType.BusDevice:
            return self.buses

        elif element_type == DeviceType.OverheadLineTypeDevice:
            return self.overhead_line_types

        elif element_type == DeviceType.TransformerTypeDevice:
            return self.transformer_types

        elif element_type == DeviceType.UnderGroundLineDevice:
            return self.underground_cable_types

        elif element_type == DeviceType.SequenceLineDevice:
            return self.sequence_line_types

        elif element_type == DeviceType.WireDevice:
            return self.wire_types

        elif element_type == DeviceType.DCLineDevice:
            return self.dc_lines

        elif element_type == DeviceType.SwitchDevice:
            return self.switch_devices

        elif element_type == DeviceType.SubstationDevice:
            return self.substations

        elif element_type == DeviceType.AreaDevice:
            return self.areas

        elif element_type == DeviceType.ZoneDevice:
            return self.zones

        elif element_type == DeviceType.CountryDevice:
            return self.countries

        elif element_type == DeviceType.ContingencyDevice:
            return self.contingencies

        elif element_type == DeviceType.ContingencyGroupDevice:
            return self.contingency_groups

        elif element_type == DeviceType.Technology:
            return self.technologies

        elif element_type == DeviceType.InvestmentDevice:
            return self.investments

        elif element_type == DeviceType.InvestmentsGroupDevice:
            return self.investments_groups

        elif element_type == DeviceType.FuelDevice:
            return self.fuels

        elif element_type == DeviceType.EmissionGasDevice:
            return self.emission_gases

        elif element_type == DeviceType.GeneratorTechnologyAssociation:
            return self.generators_technologies

        elif element_type == DeviceType.GeneratorFuelAssociation:
            return self.generators_fuels

        elif element_type == DeviceType.GeneratorEmissionAssociation:
            return self.generators_emissions

        elif element_type == DeviceType.ConnectivityNodeDevice:
            return self.connectivity_nodes

        elif element_type == DeviceType.FluidNode:
            return self.fluid_nodes

        elif element_type == DeviceType.FluidPath:
            return self.fluid_paths

        elif element_type == DeviceType.FluidTurbine:
            return self.fluid_turbines

        elif element_type == DeviceType.FluidPump:
            return self.fluid_pumps

        else:
            raise Exception('Element type not understood ' + str(element_type))

    def delete_elements_by_type(self, obj: dev.EditableDevice):
        """
        Get set of elements and their parent nodes
        :param obj: device object to delete
        :return: List of elements, it raises an exception if the elements are unknown
        """

        element_type = obj.device_type

        if element_type == DeviceType.LoadDevice:
            obj.bus.loads.remove(obj)

        elif element_type == DeviceType.StaticGeneratorDevice:
            obj.bus.static_generators.remove(obj)

        elif element_type == DeviceType.GeneratorDevice:
            obj.bus.generators.remove(obj)

        elif element_type == DeviceType.BatteryDevice:
            obj.bus.batteries.remove(obj)

        elif element_type == DeviceType.ShuntDevice:
            obj.bus.shunts.remove(obj)

        elif element_type == DeviceType.ExternalGridDevice:
            obj.bus.external_grids.remove(obj)

        elif element_type == DeviceType.LineDevice:
            return self.delete_line(obj)

        elif element_type == DeviceType.Transformer2WDevice:
            return self.delete_transformer2w(obj)

        elif element_type == DeviceType.Transformer3WDevice:
            return self.delete_transformer3w(obj)

        elif element_type == DeviceType.WindingDevice:
            return self.delete_winding(obj)

        elif element_type == DeviceType.HVDCLineDevice:
            return self.delete_hvdc_line(obj)

        elif element_type == DeviceType.UpfcDevice:
            return self.delete_upfc_converter(obj)

        elif element_type == DeviceType.VscDevice:
            return self.delete_vsc_converter(obj)

        elif element_type == DeviceType.BusDevice:
            return self.delete_bus(obj, False)

        elif element_type == DeviceType.OverheadLineTypeDevice:
            return self.delete_overhead_line(obj)

        elif element_type == DeviceType.TransformerTypeDevice:
            return self.delete_transformer_type(obj)

        elif element_type == DeviceType.UnderGroundLineDevice:
            return self.delete_underground_line(obj)

        elif element_type == DeviceType.SequenceLineDevice:
            return self.delete_sequence_line(obj)

        elif element_type == DeviceType.WireDevice:
            return self.delete_wire(obj)

        elif element_type == DeviceType.DCLineDevice:
            return self.delete_dc_line(obj)

        elif element_type == DeviceType.SubstationDevice:
            return self.delete_substation(obj)

        elif element_type == DeviceType.AreaDevice:
            return self.delete_area(obj)

        elif element_type == DeviceType.ZoneDevice:
            return self.delete_zone(obj)

        elif element_type == DeviceType.CountryDevice:
            return self.delete_country(obj)

        elif element_type == DeviceType.ContingencyDevice:
            return self.delete_contingency(obj)

        elif element_type == DeviceType.ContingencyGroupDevice:
            return self.delete_contingency_group(obj)

        elif element_type == DeviceType.Technology:
            return self.delete_technology(obj)

        elif element_type == DeviceType.InvestmentDevice:
            return self.delete_investment(obj)

        elif element_type == DeviceType.InvestmentsGroupDevice:
            return self.delete_investment_groups(obj)

        elif element_type == DeviceType.FuelDevice:
            return self.delete_fuel(obj)

        elif element_type == DeviceType.EmissionGasDevice:
            return self.delete_emission_gas(obj)

        elif element_type == DeviceType.GeneratorTechnologyAssociation:
            return self.delete_generator_technology(obj)

        elif element_type == DeviceType.GeneratorFuelAssociation:
            return self.delete_generator_fuel(obj)

        elif element_type == DeviceType.GeneratorEmissionAssociation:
            return self.delete_generator_emission(obj)

        elif element_type == DeviceType.FluidNode:
            return self.delete_fluid_node(obj)

        elif element_type == DeviceType.FluidTurbine:
            return self.delete_fluid_turbine(obj)

        elif element_type == DeviceType.FluidPump:
            return self.delete_fluid_pump(obj)

        elif element_type == DeviceType.FluidPath:
            return self.delete_fluid_path(obj)

        else:
            raise Exception('Element type not understood ' + str(element_type))

    def gat_all_elemnts_dict_by_type(self) -> dict[Callable[[], Any], Union[dict[str, EditableDevice], Any]]:
        """
        Get a dictionary of all elements by type
        :return:
        """
        data = dict()
        for tpe in [DeviceType.BusDevice,
                    DeviceType.LoadDevice,
                    DeviceType.StaticGeneratorDevice,
                    DeviceType.GeneratorDevice,
                    DeviceType.BatteryDevice,
                    DeviceType.ShuntDevice,
                    DeviceType.ExternalGridDevice,
                    DeviceType.SubstationDevice,
                    DeviceType.AreaDevice,
                    DeviceType.ZoneDevice,
                    DeviceType.CountryDevice,
                    DeviceType.LineDevice,
                    DeviceType.DCLineDevice,
                    DeviceType.Transformer2WDevice,
                    DeviceType.Transformer3WDevice,
                    DeviceType.UpfcDevice,
                    DeviceType.VscDevice,
                    DeviceType.HVDCLineDevice,
                    DeviceType.SwitchDevice,
                    DeviceType.WindingDevice,

                    DeviceType.FluidNode,
                    DeviceType.FluidPath,
                    DeviceType.FluidTurbine,
                    DeviceType.FluidPump]:
            data[tpe.value] = self.get_elements_dict_by_type(element_type=tpe, use_secondary_key=False)

        return data

    def get_elements_dict_by_type(self, element_type: DeviceType,
                                  use_secondary_key=False) -> Dict[str, dev.EditableDevice]:
        """
        Get dictionary of elements
        :param element_type: element type (Bus, Line, etc...)
        :param use_secondary_key: use the code as dictionary key? otherwise the idtag is used
        :return: Dict[str, dev.EditableDevice]
        """

        if use_secondary_key:
            return {elm.code: elm for elm in self.get_elements_by_type(element_type)}
        else:
            return {elm.idtag: elm for elm in self.get_elements_by_type(element_type)}

    def get_node_elements_by_type2(self, element_type: DeviceType) -> List[dev.EditableDevice]:
        """
        Get set of elements and their parent nodes
        :param element_type: DeviceTYpe instance
        :return: List of elements, it raises an exception if the elements are unknown
        """

        if element_type == DeviceType.LoadDevice:
            return self.get_loads()

        elif element_type == DeviceType.StaticGeneratorDevice:
            return self.get_static_generators()

        elif element_type == DeviceType.GeneratorDevice:
            return self.get_generators()

        elif element_type == DeviceType.BatteryDevice:
            return self.get_batteries()

        elif element_type == DeviceType.ShuntDevice:
            return self.get_shunts()

        elif element_type == DeviceType.ExternalGridDevice:
            return self.get_external_grids()

        elif element_type == DeviceType.SubstationDevice:
            return [x.substation for x in self.buses]

        elif element_type == DeviceType.AreaDevice:
            return [x.area for x in self.buses]

        elif element_type == DeviceType.ZoneDevice:
            return [x.zone for x in self.buses]

        elif element_type == DeviceType.CountryDevice:
            return [x.country for x in self.buses]

        elif element_type == DeviceType.LineDevice:
            return self.get_lines()

        elif element_type == DeviceType.DCLineDevice:
            return self.get_dc_lines()

        elif element_type == DeviceType.Transformer2WDevice:
            return self.get_transformers2w()

        elif element_type == DeviceType.Transformer3WDevice:
            return self.get_transformers3w()

        elif element_type == DeviceType.UpfcDevice:
            return self.get_upfc()

        elif element_type == DeviceType.VscDevice:
            return self.get_vsc()

        elif element_type == DeviceType.HVDCLineDevice:
            return self.get_hvdc()

        elif element_type == DeviceType.SwitchDevice:
            return self.get_switches()

        elif element_type == DeviceType.WindingDevice:
            return self.get_windings()

        else:
            raise Exception('Element type not understood ' + str(element_type))

    def copy(self):
        """
        Returns a deep (true) copy of this circuit.
        """
        # TODO: eliminate usages of this function
        cpy = MultiCircuit()

        cpy.name = self.name

        bus_dict = dict()
        for bus in self.buses:
            cpy.buses.append(bus.copy())

        for branch in self.lines:
            cpy.lines.append(branch.copy())

        for branch in self.transformers2w:
            cpy.transformers2w.append(branch.copy())

        for branch in self.hvdc_lines:
            cpy.hvdc_lines.append(branch.copy())

        for branch in self.vsc_devices:
            cpy.vsc_devices.append(branch.copy())

        cpy.Sbase = self.Sbase

        cpy.branch_original_idx = self.branch_original_idx.copy()

        cpy.bus_original_idx = self.bus_original_idx.copy()

        if self.time_profile is not None:
            cpy.time_profile = self.time_profile.copy()

        return cpy

    def get_catalogue_dict(self, branches_only=False):
        """
        Returns a dictionary with the catalogue types and the associated list of objects.

        Arguments:

            **branches_only** (bool, False): Only branch types
        """
        # 'Wires', 'Overhead lines', 'Underground lines', 'Sequence lines', 'Transformers'

        if branches_only:

            catalogue_dict = {'Overhead lines': self.overhead_line_types,
                              'Transformers': self.transformer_types,
                              'Underground lines': self.underground_cable_types,
                              'Sequence lines': self.sequence_line_types}
        else:
            catalogue_dict = {'Wires': self.wire_types,
                              'Overhead lines': self.overhead_line_types,
                              'Underground lines': self.underground_cable_types,
                              'Sequence lines': self.sequence_line_types,
                              'Transformers': self.transformer_types}

        return catalogue_dict

    def get_catalogue_dict_by_name(self, type_class: str = None):
        """
        Get the catalogue elements by name
        :param type_class:
        :return:
        """
        d = dict()

        # ['Wires', 'Overhead lines', 'Underground lines', 'Sequence lines', 'Transformers']

        if type_class is None:
            tpes = [self.overhead_line_types,
                    self.underground_cable_types,
                    self.wire_types,
                    self.transformer_types,
                    self.sequence_line_types]
            name_prop = ''

        elif type_class == 'Wires':
            tpes = self.wire_types
            name_prop = 'name'

        elif type_class == 'Overhead lines':
            tpes = self.overhead_line_types
            name_prop = 'name'

        elif type_class == 'Underground lines':
            tpes = self.underground_cable_types
            name_prop = 'name'

        elif type_class == 'Sequence lines':
            tpes = self.sequence_line_types
            name_prop = 'name'

        elif type_class == 'Transformers':
            tpes = self.transformer_types
            name_prop = 'name'

        else:
            tpes = list()
            name_prop = 'name'

        # make dictionary
        for tpe in tpes:
            d[getattr(tpe, name_prop)] = tpe

        return d

    def get_properties_dict(self):
        """
        Returns a JSON dictionary of the :ref:`MultiCircuit<multicircuit>` instance
        with the following values: id, type, phases, name, Sbase, comments.

        Arguments:

            **id**: Arbitrary identifier
        """
        d = {'id': self.idtag,
             'phases': 'ps',
             'name': self.name,
             'sbase': self.Sbase,
             'fbase': self.fBase,
             'model_version': self.model_version,
             'user_name': self.user_name,
             'comments': self.comments,
             }

        return d

    def get_units_dict(self):
        """
        Dictionary of units
        used in json export v3
        """
        return {'time': 'Milliseconds since 1/1/1970 (Unix time in ms)'}

    def get_profiles_dict(self):
        """
        Get the profiles dictionary
        mainly used in json export
        """
        if self.time_profile is not None:
            # recommended way to get the unix datetimes
            arr = (self.time_profile - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
            # t = (self.time_profile.array.astype(int) * 1e-9).tolist()  # UNIX time in seconds
            t = arr.tolist()
        else:
            t = list()
        return {'time': t}

    def assign_circuit(self, circ: "MultiCircuit"):
        """
        Assign a circuit object to this object.
        :param circ: Another Circuit instance
        :return:
        """
        self.buses = circ.buses

        self.lines = circ.lines
        self.transformers2w = circ.transformers2w
        self.hvdc_lines = circ.hvdc_lines
        self.vsc_devices = circ.vsc_devices

        self.name = circ.name
        self.Sbase = circ.Sbase
        self.fBase = circ.fBase

        self.sequence_line_types = list(set(self.sequence_line_types + circ.sequence_line_types))
        self.wire_types = list(set(self.wire_types + circ.wire_types))
        self.overhead_line_types = list(set(self.overhead_line_types + circ.overhead_line_types))
        self.underground_cable_types = list(set(self.underground_cable_types + circ.underground_cable_types))
        self.sequence_line_types = list(set(self.sequence_line_types + circ.sequence_line_types))
        self.transformer_types = list(set(self.transformer_types + circ.transformer_types))

    def build_graph(self):
        """
        Returns a networkx DiGraph object of the grid.
        """
        self.graph = nx.DiGraph()

        self.bus_dictionary = dict()

        for i, bus in enumerate(self.buses):
            self.graph.add_node(i)
            self.bus_dictionary[bus.idtag] = i

        tuples = list()
        for branch_list in self.get_branch_lists():
            for branch in branch_list:
                f = self.bus_dictionary[branch.bus_from.idtag]
                t = self.bus_dictionary[branch.bus_to.idtag]
                if branch.device_type in [DeviceType.LineDevice,
                                          DeviceType.DCLineDevice,
                                          DeviceType.HVDCLineDevice]:
                    if hasattr(branch, 'X'):
                        w = branch.X
                    else:
                        w = 1e-3
                else:
                    if hasattr(branch, 'X'):
                        w = branch.X
                    else:
                        w = 1e-6

                # self.graph.add_edge(f, t)
                tuples.append((f, t, w))

        self.graph.add_weighted_edges_from(tuples)

        return self.graph

    def build_graph_real_power_flow(self, current_flow):
        """
        Returns a networkx DiGraph object of the grid.

        Arguments:

            **current_flow** (list): power_flow.results.If object
        """
        graph_real_power_flow = nx.DiGraph()

        current_flow_direction = np.real(current_flow) > 0
        bus_dictionary = self.get_elements_dict_by_type(element_type=DeviceType.BusDevice,
                                                        use_secondary_key=False)

        for branch_list in self.get_branch_lists():
            for direction, branch in zip(current_flow_direction, branch_list):
                f = bus_dictionary[branch.bus_from.idtag]
                t = bus_dictionary[branch.bus_to.idtag]
                if direction:
                    graph_real_power_flow.add_edge(f, t)
                else:
                    graph_real_power_flow.add_edge(t, f)

        return graph_real_power_flow

    def create_profiles(self, steps, step_length, step_unit, time_base: datetime = datetime.now()):
        """
        Set the default profiles in all the objects enabled to have profiles.

        Arguments:

            **steps** (int): Number of time steps

            **step_length** (int): Time length (1, 2, 15, ...)

            **step_unit** (str): Unit of the time step ("h", "m" or "s")

            **time_base** (datetime, datetime.now()): Date to start from
        """

        index = np.empty(steps, dtype=object)
        for i in range(steps):
            if step_unit == 'h':
                index[i] = time_base + timedelta(hours=i * step_length)
            elif step_unit == 'm':
                index[i] = time_base + timedelta(minutes=i * step_length)
            elif step_unit == 's':
                index[i] = time_base + timedelta(seconds=i * step_length)

        index = pd.DatetimeIndex(index)

        self.format_profiles(index)

    def format_profiles(self, index):
        """
        Format the pandas profiles in place using a time index.

        Arguments:

            **index**: Time profile
        """

        self.time_profile = pd.to_datetime(index, dayfirst=True)

        for elm in self.buses:
            elm.create_profiles(index)

        for branch_list in self.get_branch_lists():
            for elm in branch_list:
                elm.create_profiles(index)

    def set_time_profile(self, unix_data: IntVec):
        """
        Set unix array as time array
        :param unix_data: array of seconds since 1970
        """
        # try parse
        try:
            self.time_profile = pd.to_datetime(np.array(unix_data), unit='s', origin='unix')
        except Exception as e:
            # it may come in nanoseconds instead of seconds...
            self.time_profile = pd.to_datetime(np.array(unix_data) / 1e9, unit='s', origin='unix')

        self.ensure_profiles_exist()

        for elm in self.buses:
            elm.create_profiles(self.time_profile)

        for branch_list in self.get_branch_lists():
            for elm in branch_list:
                elm.create_profiles(self.time_profile)

    def ensure_profiles_exist(self):
        """
        Format the pandas profiles in place using a time index.
        """
        if self.time_profile is None:
            raise Exception('Cannot ensure profiles existence without a time index. Try format_profiles instead')

        for elm in self.buses:
            elm.ensure_profiles_exist(self.time_profile)

        for branch_list in self.get_branch_lists():
            for elm in branch_list:
                elm.ensure_profiles_exist(self.time_profile)

    def get_bus_dict(self, by_idtag=False) -> Dict[str, dev.Bus]:
        """
        Return dictionary of buses
        :param by_idtag if true, the key is the idtag else the key is the name
        :return: dictionary of buses {name:object}
        """
        if by_idtag:
            return {b.idtag: b for b in self.buses}
        else:
            return {b.name: b for b in self.buses}

    def get_bus_index_dict(self) -> Dict[dev.Bus, int]:
        """
        Return dictionary of buses
        :return: dictionary of buses {name:object}
        """
        return {b: i for i, b in enumerate(self.buses)}

    def add_bus(self, obj: dev.Bus):
        """
        Add a :ref:`Bus<bus>` object to the grid.

        Arguments:

            **obj** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object
        """
        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)

        # if obj.substation is None:
        #     obj.substation = self.default_substation
        #
        # if obj.zone is None:
        #     obj.zone = self.default_zone
        #
        # if obj.area is None:
        #     obj.area = self.default_area
        #
        # if obj.country is None:
        #     obj.country = self.default_country

        self.buses.append(obj)

    def delete_bus(self, obj: dev.Bus, ask=True):
        """
        Delete a :ref:`Bus<bus>` object from the grid.

        Arguments:

            **obj** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object
        """

        # remove associated Branches in reverse order
        for branch_list in self.get_branch_lists():
            for i in range(len(branch_list) - 1, -1, -1):
                if branch_list[i].bus_from == obj or branch_list[i].bus_to == obj:
                    self.delete_branch(branch_list[i])

        # remove the bus itself
        if obj in self.buses:
            self.buses.remove(obj)

    def add_line(self, obj: dev.Line, logger: Union[bs.Logger, DataLogger] = bs.Logger()):
        """
        Add a line object
        :param obj: Line instance
        :param logger: Logger to record events
        """
        if obj.should_this_be_a_transformer():
            tr = obj.get_equivalent_transformer()
            self.add_transformer2w(tr)
            # print('Converted {} ({}) to a transformer'.format(obj.name, obj.idtag))
            logger.add_warning("Converted line to transformer due to excessive nominal voltage difference",
                               device=obj.idtag)
        else:
            if self.time_profile is not None:
                obj.create_profiles(self.time_profile)
            self.lines.append(obj)

    def add_dc_line(self, obj: dev.DcLine):
        """
        Add a line object
        :param obj: Line instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.dc_lines.append(obj)

    def add_transformer2w(self, obj: dev.Transformer2W):
        """
        Add a transformer object
        :param obj: Transformer2W instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.transformers2w.append(obj)

    def add_winding(self, obj: dev.Winding):
        """
        Add a winding object
        :param obj: Winding instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.windings.append(obj)

    def add_transformer3w(self, obj: dev.Transformer3W):
        """
        Add a transformer object
        :param obj: Transformer3W instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.transformers3w.append(obj)
        self.add_bus(obj.bus0)  # add the middle transformer
        self.add_winding(obj.winding1)
        self.add_winding(obj.winding2)
        self.add_winding(obj.winding3)

    def add_hvdc(self, obj: dev.HvdcLine):
        """
        Add a hvdc line object
        :param obj: HvdcLine instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.hvdc_lines.append(obj)

    def add_vsc(self, obj: dev.VSC):
        """
        Add a hvdc line object
        :param obj: HvdcLine instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.vsc_devices.append(obj)

    def add_upfc(self, obj: dev.UPFC):
        """
        Add a UPFC object
        :param obj: UPFC instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.upfc_devices.append(obj)

    def add_switch(self, obj: dev.Switch):
        """
        Add a Switch object
        :param obj: Switch instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.switch_devices.append(obj)

    def add_branch(self, obj: Union[dev.Line, dev.DcLine, dev.Transformer2W, dev.HvdcLine, dev.VSC,
    dev.UPFC, dev.Winding, dev.Switch, dev.Branch]) -> None:
        """
        Add any branch object (it's type will be infered here)
        :param obj: any class inheriting from ParentBranch
        """

        if obj.device_type == DeviceType.LineDevice:
            self.add_line(obj)

        elif obj.device_type == DeviceType.DCLineDevice:
            self.add_dc_line(obj)

        elif obj.device_type == DeviceType.Transformer2WDevice:
            self.add_transformer2w(obj)

        elif obj.device_type == DeviceType.HVDCLineDevice:
            self.add_hvdc(obj)

        elif obj.device_type == DeviceType.VscDevice:
            self.add_vsc(obj)

        elif obj.device_type == DeviceType.UpfcDevice:
            self.add_upfc(obj)

        elif obj.device_type == DeviceType.WindingDevice:
            self.add_winding(obj)

        elif obj.device_type == DeviceType.SwitchDevice:
            self.add_switch(obj)

        elif obj.device_type == DeviceType.BranchDevice:

            if obj.should_this_be_a_transformer():
                self.add_transformer2w(obj.get_equivalent_transformer())
            else:
                self.add_line(obj.get_equivalent_line())
        else:
            raise Exception('Unrecognized branch type ' + obj.device_type.value)

    def delete_branch(self, obj: Union[dev.Line, dev.DcLine, dev.Transformer2W, dev.HvdcLine, dev.VSC,
    dev.UPFC, dev.Winding, dev.Switch]):
        """
        Delete a :ref:`Branch<branch>` object from the grid.

        Arguments:

            **obj** (:ref:`Branch<branch>`): :ref:`Branch<branch>` object
        """
        for branch_list in self.get_branch_lists():
            try:
                branch_list.remove(obj)
            except:
                pass

    def delete_line(self, obj: dev.Line):
        """
        Delete line
        :param obj: Line instance
        """
        self.lines.remove(obj)

    def delete_dc_line(self, obj: dev.DcLine):
        """
        Delete line
        :param obj: Line instance
        """
        self.dc_lines.remove(obj)

    def delete_transformer2w(self, obj: dev.Transformer2W):
        """
        Delete transformer
        :param obj: Transformer2W instance
        """
        self.transformers2w.remove(obj)

    def delete_switch(self, obj: dev.Switch):
        """
        Delete transformer
        :param obj: Transformer2W instance
        """
        self.switch_devices.remove(obj)

    def delete_winding(self, obj: dev.Winding):
        """
        Delete winding
        :param obj: Winding instance
        """
        for tr3 in self.transformers3w:

            if obj == tr3.winding1:
                tr3.bus1 = None
                # tr3.winding1 = None
                # if tr3.graphic_obj is not None:
                #     tr3.graphic_obj.connection_lines[0] = None

            elif obj == tr3.winding2:
                tr3.bus2 = None
                # tr3.winding2 = None
                # if tr3.graphic_obj is not None:
                #     tr3.graphic_obj.connection_lines[1] = None

            if obj == tr3.winding3:
                tr3.bus3 = None
                # tr3.winding3 = None
                # if tr3.graphic_obj is not None:
                #     tr3.graphic_obj.connection_lines[2] = None

        # self.windings.remove(obj)

    def delete_transformer3w(self, obj: dev.Transformer3W):
        """
        Delete transformer
        :param obj: Transformer2W instance
        """
        self.transformers3w.remove(obj)
        self.delete_winding(obj.winding1)
        self.delete_winding(obj.winding2)
        self.delete_winding(obj.winding3)
        self.delete_bus(obj.bus0)  # also remove the middle bus

    def delete_hvdc_line(self, obj: dev.HvdcLine):
        """
        Delete HVDC line
        :param obj:
        """
        self.hvdc_lines.remove(obj)

    def delete_vsc_converter(self, obj: dev.VSC):
        """
        Delete VSC
        :param obj: VSC Instance
        """
        self.vsc_devices.remove(obj)

    def delete_upfc_converter(self, obj: dev.UPFC):
        """
        Delete VSC
        :param obj: VSC Instance
        """
        self.upfc_devices.remove(obj)

    def add_load(self, bus: dev.Bus, api_obj=None):
        """
        Add a :ref:`Load<load>` object to a :ref:`Bus<bus>`.

        Arguments:

            **bus** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object

            **api_obj** (:ref:`Load<load>`): :ref:`Load<load>` object
        """
        if api_obj is None:
            api_obj = dev.Load()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        if api_obj.name == 'Load':
            api_obj.name += '@' + bus.name

        bus.loads.append(api_obj)

        return api_obj

    def add_generator(self, bus: dev.Bus, api_obj: Union[dev.Generator, None] = None):
        """
        Add a generator
        :param bus: Bus object
        :param api_obj: Generator object
        :return: Generator object (created if api_obj is None)
        """

        if api_obj is None:
            api_obj = dev.Generator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.generators.append(api_obj)

        return api_obj

    def add_static_generator(self, bus: dev.Bus, api_obj: Union[dev.StaticGenerator, None] = None):
        """
        Add a generator
        :param bus: Bus object
        :param api_obj: StaticGenerator object
        :return: StaticGenerator object (created if api_obj is None)
        """

        if api_obj is None:
            api_obj = dev.StaticGenerator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.static_generators.append(api_obj)

        return api_obj

    def add_external_grid(self, bus: dev.Bus, api_obj=None):
        """

        :param bus:
        :param api_obj:
        :return:
        """

        """
        Add a :ref:`Load<load>` object to a :ref:`Bus<bus>`.

        Arguments:

            **bus** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object

            **api_obj** (:ref:`Load<load>`): :ref:`Load<load>` object
        """

        if api_obj is None:
            api_obj = dev.ExternalGrid()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        if api_obj.name == 'External grid':
            api_obj.name += '@' + bus.name

        bus.external_grids.append(api_obj)

        return api_obj

    def add_battery(self, bus: dev.Bus, api_obj=None):
        """
        Add a :ref:`Battery<battery>` object to a :ref:`Bus<bus>`.

        Arguments:

            **bus** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object

            **api_obj** (:ref:`Battery<battery>`): :ref:`Battery<battery>` object
        """
        if api_obj is None:
            api_obj = dev.Battery()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.batteries.append(api_obj)

        return api_obj

    def add_shunt(self, bus: dev.Bus, api_obj=None):
        """
        Add a :ref:`Shunt<shunt>` object to a :ref:`Bus<bus>`.

        Arguments:

            **bus** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object

            **api_obj** (:ref:`Shunt<shunt>`): :ref:`Shunt<shunt>` object
        """
        if api_obj is None:
            api_obj = dev.Shunt()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.shunts.append(api_obj)

        return api_obj

    def add_wire(self, obj: dev.Wire):
        """
        Add Wire to the collection
        :param obj: Wire instance
        """
        if obj is not None:
            if type(obj) == dev.Wire:
                self.wire_types.append(obj)
            else:
                print('The template is not a wire!')

    def delete_wire(self, obj: dev.Wire):
        """
        Delete wire from the collection
        :param obj: Wire object
        """
        for tower in self.overhead_line_types:
            for elm in tower.wires_in_tower:
                if elm.template == obj:
                    elm.template = None

        self.wire_types.remove(obj)

    def add_overhead_line(self, obj: dev.OverheadLineType):
        """
        Add overhead line (tower) template to the collection
        :param obj: Tower instance
        """
        if obj is not None:
            if type(obj) == dev.OverheadLineType:
                self.overhead_line_types.append(obj)
            else:
                print('The template is not an overhead line!')

    def delete_line_template_dependency(self, obj):
        """
        Search a branch template from lines and transformers and delete it
        :param obj:
        :return:
        """
        for elm in self.lines:
            if elm.template == obj:
                elm.template = None

    def delete_transformer_template_dependency(self, obj: dev.TransformerType):
        """
        Search a branch template from lines and transformers and delete it
        :param obj:
        :return:
        """
        for elm in self.transformers2w:
            if elm.template == obj:
                elm.template = None

    def delete_overhead_line(self, obj: dev.OverheadLineType):
        """
        Delete tower from the collection
        :param obj: OverheadLineType
        """

        self.delete_line_template_dependency(obj=obj)
        self.overhead_line_types.remove(obj)

    def add_underground_line(self, obj: dev.UndergroundLineType):
        """
        Add underground line
        :param obj: UndergroundLineType instance
        """
        if obj is not None:
            if type(obj) == dev.UndergroundLineType:
                self.underground_cable_types.append(obj)
            else:
                print('The template is not an underground line!')

    def delete_underground_line(self, obj):
        """
        Delete underground line
        :param obj:
        """
        self.delete_line_template_dependency(obj=obj)
        self.underground_cable_types.remove(obj)

    def add_sequence_line(self, obj: dev.SequenceLineType):
        """
        Add sequence line to the collection
        :param obj: SequenceLineType instance
        """
        if obj is not None:
            if type(obj) == dev.SequenceLineType:
                self.sequence_line_types.append(obj)
            else:
                print('The template is not a sequence line!')

    def delete_sequence_line(self, obj):
        """
        Delete sequence line from the collection
        :param obj:
        """
        self.delete_line_template_dependency(obj=obj)
        self.sequence_line_types.remove(obj)
        return True

    def add_transformer_type(self, obj: dev.TransformerType):
        """
        Add transformer template
        :param obj: TransformerType instance
        """
        if obj is not None:
            if type(obj) == dev.TransformerType:
                self.transformer_types.append(obj)
            else:
                print('The template is not a transformer!')

    def delete_transformer_type(self, obj: dev.TransformerType):
        """
        Delete transformer type from the collection
        :param obj
        """
        self.delete_transformer_template_dependency(obj=obj)
        self.transformer_types.remove(obj)

    def apply_all_branch_types(self) -> bs.Logger:
        """
        Apply all the branch types
        """
        logger = bs.Logger()
        for branch in self.lines:
            if branch.template is not None:
                branch.apply_template(branch.template, self.Sbase, logger=logger)

        for branch in self.transformers2w:
            if branch.template is not None:
                branch.apply_template(branch.template, self.Sbase, logger=logger)

        return logger

    def add_substation(self, obj: dev.Substation):
        """
        Add Substation
        :param obj: Substation object
        """
        self.substations.append(obj)

    def delete_substation(self, obj: dev.Substation):
        """
        Delete Substation
        :param obj: Substation object
        """
        for elm in self.buses:
            if elm.substation == obj:
                elm.substation = None

        self.substations.remove(obj)

    def add_area(self, obj: dev.Area):
        """
        Add area
        :param obj: Area object
        """
        self.areas.append(obj)

    def delete_area(self, obj: dev.Area):
        """
        Delete area
        :param obj: Area
        """
        for elm in self.buses:
            if elm.area == obj:
                elm.area = None

        self.areas.remove(obj)

    def add_zone(self, obj: dev.Zone):
        """
        Add zone
        :param obj: Zone object
        """
        self.zones.append(obj)

    def add_contingency_group(self, obj: dev.ContingencyGroup):
        """
        Add contingency group
        :param obj: ContingencyGroup
        """
        self.contingency_groups.append(obj)

    def delete_contingency_group(self, obj):
        """
        Delete zone
        :param obj: index
        """
        self.contingency_groups.remove(obj)

    def get_contingency_group_names(self):
        """
        Get list of contingency group names
        :return:
        """
        return [e.name for e in self.contingency_groups]

    def get_contingency_group_dict(self) -> Dict[str, List[dev.Contingency]]:
        """
        Get a dictionary of group idtags related to list of contingencies
        :return:
        """
        d = dict()

        for cnt in self.contingencies:
            if cnt.group.idtag not in d:
                d[cnt.group.idtag] = [cnt]
            else:
                d[cnt.group.idtag].append(cnt)

        return d

    def get_branches_wo_hvdc_dict(self) -> Dict[str, List[dev.Branch]]:
        return {e.idtag: ei for ei, e in enumerate(self.get_branches_wo_hvdc())}

    def add_contingency(self, obj: dev.Contingency):
        self.contingencies.append(obj)

    def delete_contingency(self, obj):
        """
        Delete zone
        :param obj: index
        """
        self.contingencies.remove(obj)

    def add_investments_group(self, obj: dev.InvestmentsGroup):
        """
        Add investments group
        :param obj: InvestmentsGroup
        """
        self.investments_groups.append(obj)

    def delete_investment_groups(self, obj):
        """
        Delete zone
        :param obj: index
        """
        self.investments_groups.remove(obj)

    def add_investment(self, obj: dev.Investment):
        """
        Add investment
        :param obj: Investment
        """
        self.investments.append(obj)

    def delete_investment(self, obj):
        """
        Delete zone
        :param obj: index
        """
        self.investments.remove(obj)

    def add_technology(self, obj: dev.Technology):
        """
        Add technology
        :param obj: Technology
        """
        self.technologies.append(obj)

    def delete_technology(self, obj):
        """
        Delete zone
        :param obj: index
        """
        # todo: remove dependencies
        self.technologies.remove(obj)

    def delete_zone(self, obj):
        """
        Delete zone
        :param obj: index
        """
        for elm in self.buses:
            if elm.zone == obj:
                elm.zone = None

        self.zones.remove(obj)

    def add_country(self, obj: dev.Country):
        """
        Add country
        :param obj:  object
        """
        self.countries.append(obj)

    def delete_country(self, obj):
        """
        Delete country
        :param obj: index
        """
        for elm in self.buses:
            if elm.country == obj:
                elm.country = None

        self.countries.remove(obj)

    def add_fuel(self, obj: dev.Fuel):
        """
        Add Fuel
        :param obj: Fuel object
        """
        self.fuels.append(obj)

    def delete_fuel(self, obj):
        """
        Delete Fuel
        :param obj: index
        """
        self.fuels.remove(obj)

    def add_emission_gas(self, obj: dev.EmissionGas):
        """
        Add EmissionGas
        :param obj: EmissionGas object
        """
        self.emission_gases.append(obj)

    def delete_emission_gas(self, obj: dev.EmissionGas):
        """
        Delete Substation
        :param obj: index
        """
        # store the associations
        rels = list()
        for elm in self.generators_emissions:
            if elm.emission == obj:
                rels.append(elm)

        # delete the assciations
        for elm in rels:
            self.delete_generator_emission(elm)

        # delete the gas
        self.emission_gases.remove(obj)

    def add_generator_technology(self, obj: dev.GeneratorTechnology):
        """
        Add GeneratorTechnology
        :param obj: GeneratorTechnology object
        """
        self.generators_technologies.append(obj)

    def delete_generator_technology(self, obj: dev.GeneratorTechnology):
        """
        Delete GeneratorTechnology
        :param obj: GeneratorTechnology
        """
        # store the associations
        rels = list()
        for elm in self.generators_technologies:
            if elm.technology == obj:
                rels.append(elm)

        # delete the assciations
        for elm in rels:
            self.delete_generator_technology(elm)

        # delete the technology
        self.generators_technologies.remove(obj)

    def add_generator_fuel(self, obj: dev.GeneratorFuel):
        """
        Add GeneratorFuel
        :param obj: GeneratorFuel object
        """
        self.generators_fuels.append(obj)

    def delete_generator_fuel(self, obj: dev.GeneratorFuel):
        """
        Delete GeneratorFuel
        :param obj: GeneratorFuel
        """
        # store the associations
        rels = list()
        for elm in self.generators_fuels:
            if elm.fuel == obj:
                rels.append(elm)

        # delete the assciations
        for elm in rels:
            self.delete_generator_fuel(elm)

        # delete the fuel
        self.generators_fuels.remove(obj)

    def add_generator_emission(self, obj: dev.GeneratorEmission):
        """
        Add GeneratorFuel
        :param obj: GeneratorFuel object
        """
        self.generators_emissions.append(obj)

    def delete_generator_emission(self, obj: dev.GeneratorEmission):
        """
        Delete GeneratorFuel
        :param obj: GeneratorFuel
        """
        # todo: delete dependencies
        self.generators_emissions.remove(obj)

    def add_fluid_node(self, obj: dev.FluidNode):
        """
        Add fluid node
        :param obj: FluidNode
        """
        self.fluid_nodes.append(obj)

    def delete_fluid_node(self, obj: dev.FluidNode):
        """
        Delete fluid node
        :param obj: FluidNode
        """
        # delete dependencies
        for elm in reversed(self.fluid_turbines):
            if elm.plant == obj:
                self.delete_fluid_turbine(elm)

        for elm in reversed(self.fluid_pumps):
            if elm.reservoir == obj:
                self.delete_fluid_pump(elm)

        for fluid_path in reversed(self.fluid_paths):
            if fluid_path.source == obj or fluid_path.target == obj:
                self.delete_fluid_path(fluid_path)

        self.fluid_nodes.remove(obj)

    def add_fluid_path(self, obj: dev.FluidPath):
        """
        Add fluid path
        :param obj:FluidPath
        """
        self.fluid_paths.append(obj)

    def delete_fluid_path(self, obj: dev.FluidPath):
        """
        Delete fuid path
        :param obj: FluidPath
        """
        self.fluid_paths.remove(obj)

    def add_fluid_turbine(self, obj: dev.FluidTurbine):
        """
        Add fluid turbine
        :param obj:FluidTurbine
        """
        self.fluid_turbines.append(obj)

    def delete_fluid_turbine(self, obj: dev.FluidTurbine):
        """
        Delete fuid turbine
        :param obj: FluidTurbine
        """
        self.fluid_turbines.remove(obj)

    def add_fluid_pump(self, obj: dev.FluidPump):
        """
        Add fluid pump
        :param obj:FluidPump
        """
        self.fluid_pumps.append(obj)

    def delete_fluid_pump(self, obj: dev.FluidPump):
        """
        Delete fuid pump
        :param obj: FluidPump
        """
        self.fluid_pumps.remove(obj)

    def convert_line_to_hvdc(self, line: dev.Line) -> dev.HvdcLine:
        """
        Convert a line to HVDC, this is the GUI way to create HVDC objects
        :param line: Line instance
        :return: HvdcLine
        """
        hvdc = dev.HvdcLine(bus_from=line.bus_from,
                            bus_to=line.bus_to,
                            name='HVDC Line',
                            active=line.active,
                            rate=line.rate,
                            active_prof=line.active_prof,
                            rate_prof=line.rate_prof)

        # add device to the circuit
        self.add_hvdc(hvdc)

        # delete the line from the circuit
        self.delete_line(line)

        return hvdc

    def convert_line_to_transformer(self, line: dev.Line) -> dev.Transformer2W:
        """
        Convert a line to Transformer
        :param line: Line instance
        :return: Transformer2W
        """
        transformer = dev.Transformer2W(bus_from=line.bus_from,
                                        bus_to=line.bus_to,
                                        name='Transformer',
                                        active=line.active,
                                        rate=line.rate,
                                        r=line.R,
                                        x=line.X,
                                        b=line.B,
                                        active_prof=line.active_prof,
                                        rate_prof=line.rate_prof)

        # add device to the circuit
        self.add_transformer2w(transformer)

        # delete the line from the circuit
        self.delete_line(line)

        return transformer

    def convert_generator_to_battery(self, gen: dev.Generator) -> dev.Battery:
        """
        Convert a generator to battery
        :param gen: Generator instance
        :return: Transformer2W
        """
        batt = dev.Battery(name=gen.name,
                           idtag=gen.idtag,
                           P=gen.P,
                           power_factor=gen.Pf,
                           vset=gen.Vset,
                           is_controlled=gen.is_controlled,
                           Qmin=gen.Qmin, Qmax=gen.Qmax, Snom=gen.Snom,
                           P_prof=gen.P_prof,
                           power_factor_prof=gen.Pf_prof,
                           vset_prof=gen.Vset_prof,
                           active=gen.active,
                           Pmin=gen.Pmin, Pmax=gen.Pmax,
                           Cost=gen.Cost,
                           Sbase=gen.Sbase,
                           enabled_dispatch=gen.enabled_dispatch,
                           mttf=gen.mttf,
                           mttr=gen.mttr,
                           r1=gen.R1, x1=gen.X1,
                           r0=gen.R0, x0=gen.X0,
                           r2=gen.R2, x2=gen.X2,
                           capex=gen.capex,
                           opex=gen.opex,
                           build_status=gen.build_status)

        # add device to the circuit
        self.add_battery(gen.bus, batt)

        # delete the line from the circuit
        gen.bus.generators.remove(gen)

        return batt

    def convert_line_to_vsc(self, line: dev.Line) -> dev.VSC:
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :return: Nothing
        """
        vsc = dev.VSC(bus_from=line.bus_from,
                      bus_to=line.bus_to,
                      name='VSC',
                      active=line.active,
                      rate=line.rate,
                      r=line.R,
                      x=line.X,
                      Beq=line.B,
                      tap_module=1.0,
                      active_prof=line.active_prof,
                      rate_prof=line.rate_prof)

        # add device to the circuit
        self.add_vsc(vsc)

        # delete the line from the circuit
        self.delete_line(line)

        return vsc

    def convert_line_to_upfc(self, line: dev.Line) -> dev.UPFC:
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :return: Nothing
        """
        upfc = dev.UPFC(bus_from=line.bus_from,
                        bus_to=line.bus_to,
                        name='UPFC',
                        active=line.active,
                        rate=line.rate,
                        rs=line.R,
                        xs=line.X,
                        # bl=line.B,
                        active_prof=line.active_prof,
                        rate_prof=line.rate_prof)

        # add device to the circuit
        self.add_upfc(upfc)

        # delete the line from the circuit
        self.delete_line(line)

        return upfc

    def plot_graph(self, ax=None):
        """
        Plot the grid.
        :param ax: Matplotlib axis object
        :return:
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if self.graph is None:
            self.build_graph()

        nx.draw_spring(self.graph, ax=ax)

    def export_pf(self, file_name, power_flow_results):
        """
        Export power flow results to file.

        Arguments:

            **file_name** (str): Excel file name
        """

        if power_flow_results is not None:
            df_bus, df_branch = power_flow_results.export_all()

            df_bus.index = self.get_bus_names()
            df_branch.index = self.get_branch_names_wo_hvdc()

            with pd.ExcelWriter(file_name) as writer:  # pylint: disable=abstract-class-instantiated
                df_bus.to_excel(writer, 'Bus results')
                df_branch.to_excel(writer, 'Branch results')

        else:
            raise Exception('There are no power flow results!')

    def export_profiles(self, file_name):
        """
        Export object profiles to file.

        Arguments:

            **file_name** (str): Excel file name
        """

        if self.time_profile is not None:

            # collect data
            P = list()
            Q = list()
            Ir = list()
            Ii = list()
            G = list()
            B = list()
            P_gen = list()
            V_gen = list()
            E_batt = list()

            load_names = list()
            gen_names = list()
            bat_names = list()

            for bus in self.buses:

                for elm in bus.loads:
                    load_names.append(elm.name)
                    P.append(elm.P_prof)
                    Q.append(elm.Q_prof)

                    Ir.append(elm.Ir_prof)
                    Ii.append(elm.Ii_prof)

                    G.append(elm.G_prof)
                    B.append(elm.B_prof)

                for elm in bus.generators:
                    gen_names.append(elm.name)

                    P_gen.append(elm.P_prof)
                    V_gen.append(elm.Vset_prof)

                for elm in bus.batteries:
                    bat_names.append(elm.name)
                    gen_names.append(elm.name)
                    P_gen.append(elm.P_prof)
                    V_gen.append(elm.Vsetprof)
                    E_batt.append(elm.energy_array)

            # form DataFrames
            P = pd.DataFrame(data=np.array(P).transpose(), index=self.time_profile, columns=load_names)
            Q = pd.DataFrame(data=np.array(Q).transpose(), index=self.time_profile, columns=load_names)
            Ir = pd.DataFrame(data=np.array(Ir).transpose(), index=self.time_profile, columns=load_names)
            Ii = pd.DataFrame(data=np.array(Ii).transpose(), index=self.time_profile, columns=load_names)
            G = pd.DataFrame(data=np.array(G).transpose(), index=self.time_profile, columns=load_names)
            B = pd.DataFrame(data=np.array(B).transpose(), index=self.time_profile, columns=load_names)
            P_gen = pd.DataFrame(data=np.array(P_gen).transpose(), index=self.time_profile, columns=gen_names)
            V_gen = pd.DataFrame(data=np.array(V_gen).transpose(), index=self.time_profile, columns=gen_names)
            E_batt = pd.DataFrame(data=np.array(E_batt).transpose(), index=self.time_profile, columns=bat_names)

            with pd.ExcelWriter(file_name) as writer:  # pylint: disable=abstract-class-instantiated
                P.to_excel(writer, 'P loads')
                Q.to_excel(writer, 'Q loads')

                Ir.to_excel(writer, 'Ir loads')
                Ii.to_excel(writer, 'Ii loads')

                G.to_excel(writer, 'G loads')
                B.to_excel(writer, 'B loads')

                P_gen.to_excel(writer, 'P generators')
                V_gen.to_excel(writer, 'V generators')

                E_batt.to_excel(writer, 'Energy batteries')

        else:
            raise Exception('There are no time series!')

    def set_state(self, t):
        """
        Set the profiles state at the index t as the default values.
        """
        for bus in self.buses:
            bus.set_state(t)

        for branch in self.get_branches():
            branch.set_profile_values(t)

    def get_bus_branch_connectivity_matrix(self) -> Tuple[csc_matrix, csc_matrix, csc_matrix]:
        """
        Get the branch-bus connectivity
        :return: Cf, Ct, C
        """
        n = len(self.buses)
        m = self.get_branch_number()
        Cf = lil_matrix((m, n))
        Ct = lil_matrix((m, n))

        bus_dict = {bus: i for i, bus in enumerate(self.buses)}

        for branch_list in self.get_branch_lists():
            for k, br in enumerate(branch_list):
                i = bus_dict[br.bus_from]  # store the row indices
                j = bus_dict[br.bus_to]  # store the row indices
                Cf[k, i] = 1
                Ct[k, j] = 1

        C = csc_matrix(Cf + Ct)
        Cf = csc_matrix(Cf)
        Ct = csc_matrix(Ct)

        return Cf, Ct, C

    def get_adjacent_matrix(self) -> csc_matrix:
        """
        Get the bus adjacent matrix
        :return: Adjacent matrix
        """
        Cf, Ct, C = self.get_bus_branch_connectivity_matrix()
        A = C.T * C
        return A.tocsc()

    @staticmethod
    def get_adjacent_buses(A: csc_matrix, bus_idx):
        """
        Return array of indices of the buses adjacent to the bus given by it's index
        :param A: Adjacent matrix
        :param bus_idx: bus index
        :return: array of adjacent bus indices
        """
        return A.indices[A.indptr[bus_idx]:A.indptr[bus_idx + 1]]

    def get_center_location(self):
        """
        Get the mean coordinates of the system (lat, lon)
        """
        coord = np.array([b.get_coordinates() for b in self.buses])

        return coord.mean(axis=0).tolist()

    def add_circuit(self, circuit: "MultiCircuit"):
        """
        Add a circuit to this circuit
        :param circuit: Circuit to insert
        :return: Nothing
        """

        # add profiles if required
        if self.time_profile is not None:

            for bus in circuit.buses:
                bus.create_profiles(index=self.time_profile)

            for lst in [circuit.lines, circuit.transformers2w, circuit.hvdc_lines]:
                for branch in lst:
                    branch.create_profiles(index=self.time_profile)

        self.add_devices_list(self.buses, circuit.buses)
        self.add_devices_list(self.lines, circuit.lines)
        self.add_devices_list(self.transformers2w, circuit.transformers2w)
        self.add_devices_list(self.windings, circuit.windings)
        self.add_devices_list(self.transformers3w, circuit.transformers3w)
        self.add_devices_list(self.hvdc_lines, circuit.hvdc_lines)
        self.add_devices_list(self.vsc_devices, circuit.vsc_devices)
        self.add_devices_list(self.upfc_devices, circuit.upfc_devices)
        self.add_devices_list(self.dc_lines, circuit.dc_lines)

        self.add_devices_list(self.switch_devices, circuit.switch_devices)
        self.add_devices_list(self.areas, circuit.areas)
        self.add_devices_list(self.zones, circuit.zones)
        self.add_devices_list(self.substations, circuit.substations)
        self.add_devices_list(self.countries, circuit.countries)

        self.add_devices_list(self.technologies, circuit.technologies)

        self.add_devices_list(self.overhead_line_types, circuit.overhead_line_types)
        self.add_devices_list(self.wire_types, circuit.wire_types)
        self.add_devices_list(self.underground_cable_types, circuit.underground_cable_types)
        self.add_devices_list(self.sequence_line_types, circuit.sequence_line_types)
        self.add_devices_list(self.transformer_types, circuit.transformer_types)

        return circuit.buses

    @staticmethod
    def add_devices_list(original_list, new_list):
        """
        Add a list of devices to another keeping coherence
        :param original_list:
        :param new_list:
        :return:
        """
        existing_uuids = {e.idtag for e in original_list}

        for elm in new_list:
            if elm.idtag in existing_uuids:
                print(elm.name, 'uuid is repeated..generating new one')
                elm.generate_uuid()
            original_list.append(elm)

    def snapshot_balance(self):
        """
        Creates a report DataFrame with the snapshot active power balance
        :return: DataFrame
        """

        data = {'Generators': 0.0,
                'Static generators': 0.0,
                'Batteries': 0.0,
                'Loads': 0.0,
                'Balance': 0.0}

        for bus in self.buses:

            for gen in bus.generators:
                if gen.active:
                    data['Generators'] = data['Generators'] + gen.P

            for gen in bus.static_generators:
                if gen.active:
                    data['Static generators'] = data['Static generators'] + gen.P

            for gen in bus.batteries:
                if gen.active:
                    data['Batteries'] = data['Batteries'] + gen.P

            for load in bus.loads:
                if load.active:
                    data['Loads'] = data['Loads'] + load.P

        generation = data['Generators'] + data['Static generators'] + data['Batteries']
        load = data['Loads']
        data['Generation - Load'] = generation - data['Loads']
        data['Imbalance (%)'] = abs(load - generation) / max(load, generation) * 100.0

        return pd.DataFrame(data, index=['Power (MW)']).transpose()

    def scale_power(self, factor):
        """
        Modify the loads and generators
        :param factor: multiplier
        :return: Nothing
        """
        for elm in self.get_loads():
            elm.P *= factor
            elm.Q *= factor

        for elm in self.get_generators():
            elm.P *= factor

        for elm in self.get_static_generators():
            elm.P *= factor
            elm.Q *= factor

    def get_used_templates(self):
        """
        Get a list of the used templates in the objects
        :return: list
        """
        val = set()

        branches = self.get_branches()

        for branch in branches:
            if hasattr(branch, 'template'):
                obj = getattr(branch, 'template')
                val.add(obj)

                # if it is a tower, add the wire templates too
                if obj.device_type == DeviceType.OverheadLineTypeDevice:
                    for wire in obj.wires_in_tower:
                        val.add(wire)

        return list(val)

    def get_automatic_precision(self):
        """
        Get the precision that simulates correctly the power flow
        :return: tolerance parameter for the power flow options, exponent
        """
        injections = self.get_Pbus()
        P = np.abs(injections) / self.Sbase
        P = P[P > 0]
        if np.sum(P) > 0:
            lg = np.log10(P)
            lg[lg == -np.inf] = 1e20
            exponent = int(np.min(np.abs(lg))) * 3
            tolerance = 1.0 / (10.0 ** exponent)
        else:
            exponent = 3
            tolerance = 1e-3

        return tolerance, exponent

    def fill_xy_from_lat_lon(self,
                             destructive: bool = True,
                             factor: float = 0.01,
                             remove_offset: bool = True) -> bs.Logger:
        """
        fill the x and y value from the latitude and longitude values
        :param destructive: if true, the values are overwritten regardless, otherwise only if x and y are 0
        :param factor: Explosion factor
        :param remove_offset: remove the sometimes huge offset coming from pyproj
        :return Logger object
        """

        n = len(self.buses)
        lon = np.zeros(n)
        lat = np.zeros(n)
        for i, bus in enumerate(self.buses):
            lon[i] = bus.longitude
            lat[i] = bus.latitude

        # perform the coordinate transformation
        logger = bs.Logger()
        try:
            import pyproj
        except ImportError:
            logger.add_error("pyproj is not installed")
            return logger

        transformer = pyproj.Transformer.from_crs(4326, 25830, always_xy=True)

        # the longitude is more reated to x, the latitude is more related to y
        x, y = transformer.transform(xx=lon, yy=lat)
        x *= factor
        y *= factor

        # remove the offset
        if remove_offset:
            x_min = np.min(x)
            y_max = np.max(y)
            x -= x_min + 100  # 100 is a healthy offset
            y -= y_max - 100  # 100 is a healthy offset

        # assign the values
        for i, bus in enumerate(self.buses):
            if destructive or (bus.x == 0.0 and bus.y == 0.0):
                bus.x = x[i]
                bus.y = y[i]

        return logger

    def fill_lat_lon_from_xy(self, destructive=True, factor=1.0, offset_x=0, offset_y=0):
        """
        Convert the coordinates to some random lat lon
        :param destructive:
        :param factor:
        :param offset_x:
        :param offset_y:
        :return:
        """
        n = len(self.buses)
        x = np.zeros(n)
        y = np.zeros(n)
        for i, bus in enumerate(self.buses):
            x[i] = bus.x * factor + offset_x
            y[i] = bus.y * factor + offset_y

        logger = bs.Logger()
        try:
            import pyproj
        except ImportError:
            logger.add_error("pyproj is not installed")
            return logger

        proj_latlon = pyproj.Proj(proj='latlong', datum='WGS84')
        proj_xy = pyproj.Proj(proj="utm", zone=33, datum='WGS84')
        lonlat = pyproj.transform(proj_xy, proj_latlon, x, y)

        lon = lonlat[0]
        lat = lonlat[1]

        # assign the values
        for i, bus in enumerate(self.buses):
            if destructive or (bus.x == 0.0 and bus.y == 0.0):
                bus.latitude = lat[i]
                bus.longitude = lon[i]

        return logger

    def import_bus_lat_lon(self, df: pd.DataFrame, bus_col, lat_col, lon_col) -> bs.Logger:
        """
        Import the buses' latitude and longitude
        :param df: Pandas DataFrame with the information
        :param bus_col: bus column name
        :param lat_col: latitude column name
        :param lon_col: longitude column name
        :return: Logger
        """
        logger = bs.Logger()
        lats = df[lat_col].values
        lons = df[lon_col].values
        names = df[bus_col].values

        d = dict()
        for lat, lon, name in zip(lats, lons, names):
            d[str(name)] = (lat, lon)

        # assign the values
        for i, bus in enumerate(self.buses):
            if bus.name in d.keys():
                lat, lon = d[bus.name]
                bus.latitude = lat
                bus.longitude = lon
            elif bus.code in d.keys():
                lat, lon = d[bus.code]
                bus.latitude = lat
                bus.longitude = lon
            else:
                logger.add_error("No coordinates for bus", bus.name)

        return logger

    def import_plexos_load_profiles(self, df: pd.DataFrame):
        """

        :param df:
        :return: Logger
        """
        logger = bs.Logger()
        nn = df.shape[0]
        if self.get_time_number() != nn:
            self.format_profiles(df.index.values)

        df.columns = [val.split('_')[0] for val in df.columns.values]

        bus_by_code = {bus.code: bus for bus in self.buses}

        for col_name in df.columns.values:
            try:
                bus = bus_by_code[col_name]
                for i, load in enumerate(bus.loads):
                    if i == 0:
                        load.P_prof = df[col_name].values
                        load.Q_prof = load.P_prof * 0.8
                    else:
                        load.P_prof = np.zeros(nn)
                        load.Q_prof = np.zeros(nn)
            except KeyError:
                logger.add_error("Missing in the model", col_name)

        return logger

    def import_plexos_generation_profiles(self, df: pd.DataFrame):
        """

        :param df:
        :return: Logger
        """
        logger = bs.Logger()
        nn = df.shape[0]
        if self.get_time_number() != nn:
            self.format_profiles(df.index.values)

        df.columns = [val.replace('GEN_', '') for val in df.columns.values]

        generators = self.get_generators()
        gen_by_name = {gen.name: gen for gen in generators}

        for col_name in df.columns.values:
            try:
                gen = gen_by_name[col_name]
                gen.P_prof = df[col_name].values
            except KeyError:
                logger.add_error("Missing in the model", col_name)

        return logger

    def import_branch_rates_profiles(self, df: pd.DataFrame):
        """

        :param df:
        :return: Logger
        """
        logger = bs.Logger()
        nn = df.shape[0]
        if self.get_time_number() != nn:
            self.format_profiles(df.index.values)

        # substitute the stupid psse names by their equally stupid short names
        # 11000_AGUAYO_400_12004_ABANTO_400_1_CKT
        cols = list()
        for val in df.columns.values:
            vals = val.split('_')
            if len(vals) < 7:
                logger.add_error("Wrong PSSe name", val)
                cols.append(val)
            else:
                col = vals[0] + '_' + vals[3] + '_' + vals[6]
                cols.append(col)
        df.columns = cols

        branches = self.get_branches()
        elm_by_name = {elm.name: elm for elm in branches}

        for col_name in df.columns.values:
            try:
                elm = elm_by_name[col_name]
                elm.rate_prof = df[col_name].values
            except KeyError:
                # log the error but keep the default rate
                logger.add_error("Missing in the model", col_name)

        return logger

    def get_bus_area_indices(self) -> IntVec:
        """
        Get array of area indices for each bus
        :return:
        """
        areas_dict = {elm: k for k, elm in enumerate(self.get_areas())}

        lst = np.zeros(len(self.buses), dtype=int)
        for k, bus in enumerate(self.buses):
            if bus.area is not None:
                lst[k] = areas_dict.get(bus.area, 0)
            else:
                lst[k] = 0
        return lst

    def get_area_buses(self, area: dev.Area) -> List[Tuple[int, dev.Bus]]:
        """
        Get the selected buses
        :return:
        """
        lst: List[Tuple[int, dev.Bus]] = list()
        for k, bus in enumerate(self.buses):
            if bus.area == area:
                lst.append((k, bus))
        return lst

    def get_areas_buses(self, areas: List[dev.Area]) -> List[Tuple[int, dev.Bus]]:
        """
        Get the selected buses
        :return:
        """
        lst: List[Tuple[int, dev.Bus]] = list()
        for k, bus in enumerate(self.buses):
            if bus.area in areas:
                lst.append((k, bus))
        return lst

    def get_zone_buses(self, zone: dev.Zone) -> List[Tuple[int, dev.Bus]]:
        """
        Get the selected buses
        :return:
        """
        lst: List[Tuple[int, dev.Bus]] = list()
        for k, bus in enumerate(self.buses):
            if bus.zone == zone:
                lst.append((k, bus))
        return lst

    def get_inter_area_branches(self, a1: dev.Area, a2: dev.Area):
        """
        Get the inter-area Branches
        :param a1: Area from
        :param a2: Area to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self.get_branches()):
            if branch.bus_from.area == a1 and branch.bus_to.area == a2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from.area == a2 and branch.bus_to.area == a1:
                lst.append((k, branch, -1.0))
        return lst

    def get_inter_areas_branches(self, a1: List[dev.Area], a2: List[dev.Area]) -> List[Tuple[int, object, float]]:
        """
        Get the inter-area Branches. HVDC Branches are not considered
        :param a1: Area from
        :param a2: Area to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self.get_branches_wo_hvdc()):
            if branch.bus_from.area in a1 and branch.bus_to.area in a2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from.area in a2 and branch.bus_to.area in a1:
                lst.append((k, branch, -1.0))
        return lst

    def get_inter_areas_hvdc_branches(self, a1: List[dev.Area], a2: List[dev.Area]) -> List[Tuple[int, object, float]]:
        """
        Get the inter-area Branches
        :param a1: Area from
        :param a2: Area to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self.hvdc_lines):
            if branch.bus_from.area in a1 and branch.bus_to.area in a2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from.area in a2 and branch.bus_to.area in a1:
                lst.append((k, branch, -1.0))
        return lst

    def get_inter_zone_branches(self, z1: dev.Zone, z2: dev.Zone) -> List[Tuple[int, object, float]]:
        """
        Get the inter-area Branches
        :param z1: Zone from
        :param z2: Zone to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self.get_branches()):
            if branch.bus_from.zone == z1 and branch.bus_to.zone == z2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from.zone == z2 and branch.bus_to.zone == z1:
                lst.append((k, branch, -1.0))
        return lst

    def get_branch_area_connectivity_matrix(self, a1: List[dev.Area], a2: List[dev.Area]) -> csc_matrix:
        """
        Get the inter area connectivity matrix
        :param a1: list of sending areas
        :param a2: list of receiving areas
        :return: Connectivity of the Branches to each sending or receiving area groups (Branches, 2)
        """
        area_dict = {a: i for i, a in enumerate(self.areas)}

        area1_list = [area_dict[a] for a in a1]
        area2_list = [area_dict[a] for a in a2]

        branches = self.get_branches()  # all including HVDC

        conn = lil_matrix((len(branches), 2), dtype=int)

        for k, elm in enumerate(branches):
            i = area_dict[elm.bus_from.area]
            j = area_dict[elm.bus_to.area]
            if i != j:
                if (i in area1_list) and (j in area2_list):
                    # from->to matches the areas
                    conn[k, 0] = 1
                    conn[k, 1] = -1
                elif (i in area2_list) and (j in area1_list):
                    # reverse the sign
                    conn[k, 0] = -1
                    conn[k, 1] = 1

        return conn.tocsc()

    def change_base(self, Sbase_new: float):
        """
        Change the elements base impedance
        :param Sbase_new: new base impedance in MVA
        """
        Sbase_old = self.Sbase

        # get all the Branches with impedance
        elms = self.get_branches_wo_hvdc()

        # change the base at each element
        for elm in elms:
            elm.change_base(Sbase_old, Sbase_new)

        # assign the new base
        self.Sbase = Sbase_new

    def fuse_devices(self):
        """
        Fuse all the different devices in a node to a single device per node
        :return:
        """
        for bus in self.buses:
            bus.fuse_devices()

    def re_index_time(self, year=None, hours_per_step=1.0):
        """
        Generate sequential time steps to correct the time_profile
        :param year: base year, if None, this year is taken
        :param hours_per_step: number of hours per step, by default 1 hour by step
        """
        if year is None:
            t0 = datetime.now()
            year = t0.year

        t0 = datetime(year=year, month=1, day=1)
        self.re_index_time2(t0=t0, step_size=hours_per_step, step_unit='h')

    def re_index_time2(self, t0, step_size, step_unit):
        """
        Generate sequential time steps to correct the time_profile
        :param t0: base time
        :param step_size: number of hours per step, by default 1 hour by step
        :param step_unit: 'h', 'm', 's'
        """
        nt = self.get_time_number()

        if step_unit == 'h':
            tm = [t0 + timedelta(hours=t * step_size) for t in range(nt)]
        elif step_unit == 'm':
            tm = [t0 + timedelta(minutes=t * step_size) for t in range(nt)]
        elif step_unit == 's':
            tm = [t0 + timedelta(seconds=t * step_size) for t in range(nt)]
        else:
            raise Exception("Unsupported time unit")

        self.time_profile = pd.to_datetime(tm)

    def set_generators_active_profile_from_their_active_power(self):
        """
        Modify the generators active profile to match the active power profile
        if P=0, active = False else active=True
        """
        for g in self.get_generators():
            g.active_prof = g.P_prof.astype(bool)

    def set_batteries_active_profile_from_their_active_power(self):
        """
        Modify the batteries active profile to match the active power profile
        if P=0, active = False else active=True
        """
        for g in self.get_batteries():
            g.active_prof = g.P_prof.astype(bool)

    def set_loads_active_profile_from_their_active_power(self):
        """
        Modify the loads active profile to match the active power profile
        if P=0, active = False else active=True
        """
        for ld in self.get_loads():
            ld.active_prof = ld.P_prof.astype(bool)

    def set_contingencies(self, contingencies: List[dev.Contingency]):
        """
        Set contingencies and contingency groups to circuit
        :param contingencies: List of contingencies
        :return:
        """
        devices = self.get_contingency_devices()
        groups = dict()

        devices_code_dict = {d.code: d for d in devices}
        devices_key_dict = {d.idtag: d for d in devices}
        devices_dict = {**devices_code_dict, **devices_key_dict}

        logger = bs.Logger()

        for contingency in contingencies:
            if contingency.code in devices_dict.keys() or contingency.idtag in devices_dict.keys():
                # ensure proper device_idtag and code
                element = devices_dict[contingency.code]
                contingency.device_idtag = element.idtag
                contingency.code = element.code

                self.contingencies.append(contingency)

                if contingency.group.idtag not in groups.keys():
                    groups[contingency.group.idtag] = contingency.group
            else:
                logger.add_info(
                    msg='Contingency element not found in circuit',
                    device=contingency.code,
                )

        for group in groups.values():
            self.contingency_groups.append(group)

        return logger

    def get_voltage_guess(self) -> CxVec:
        """
        Get the buses stored voltage guess
        :return: array of complex voltages per bus
        """
        v = np.zeros(len(self.buses), dtype=complex)

        for i, bus in enumerate(self.buses):
            if bus.active:
                v[i] = cmath.rect(bus.Vm0, bus.Va0)

        return v

    def get_Sbus(self) -> CxVec:
        """
        Get the complex bus power Injections
        :return: (nbus) [MW + j MVAr]
        """
        val = np.zeros(self.get_bus_number(), dtype=complex)

        for i, bus in enumerate(self.buses):
            val[i] = bus.get_Sbus()

        return val

    def get_Sbus_prof(self) -> CxMat:
        """
        Get the complex bus power Injections
        :return: (ntime, nbus) [MW + j MVAr]
        """
        val = np.zeros((self.get_time_number(), self.get_bus_number()), dtype=complex)

        for i, bus in enumerate(self.buses):
            val[:, i] = bus.get_Sbus_prof()

        return val

    def get_Sbus_prof_fixed(self) -> CxMat:
        """
        Get the complex bus power Injections considering those devices that cannot be dispatched
        This is, all devices except generators and batteries with enabled_dispatch=True
        :return: (ntime, nbus) [MW + j MVAr]
        """
        val = np.zeros((self.get_time_number(), self.get_bus_number()), dtype=complex)

        for i, bus in enumerate(self.buses):
            val[:, i] = bus.get_Sbus_prof_fixed()

        return val

    def get_Sbus_prof_dispatchable(self) -> CxMat:
        """
        Get the complex bus power Injections only considering those devices that can be dispatched
        This is, generators and batteries with enabled_dispatch=True
        :return: (ntime, nbus) [MW + j MVAr]
        """
        val = np.zeros((self.get_time_number(), self.get_bus_number()), dtype=complex)

        for i, bus in enumerate(self.buses):
            val[:, i] = bus.get_Sbus_prof_dispatchable()

        return val

    def get_Pbus(self, non_dispatchable_only=False) -> Vec:
        """
        Get snapshot active power array per bus
        :return: Vec
        """
        return self.get_Sbus().real

    def get_Pbus_prof(self, non_dispatchable_only=False) -> Mat:
        """
        Get profiles active power per bus
        :return: Mat
        """
        return self.get_Sbus_prof().real

    def get_branch_rates_prof_wo_hvdc(self) -> Mat:
        """
        Get the complex bus power Injections
        :return: (ntime, nbr) [MVA]
        """
        val = np.zeros((self.get_time_number(), self.get_branch_number_wo_hvdc()))

        for i, branch in enumerate(self.get_branches_wo_hvdc()):
            val[:, i] = branch.rate_prof

        return val

    def get_branch_rates_wo_hvdc(self) -> Vec:
        """
        Get the complex bus power Injections
        :return: (nbr) [MVA]
        """
        val = np.zeros(self.get_branch_number_wo_hvdc())

        for i, branch in enumerate(self.get_branches_wo_hvdc()):
            val[i] = branch.rate

        return val

    def get_branch_contingency_rates_prof_wo_hvdc(self) -> Mat:
        """
        Get the complex bus power Injections
        :return: (ntime, nbr) [MVA]
        """
        val = np.zeros((self.get_time_number(), self.get_branch_number_wo_hvdc()))

        for i, branch in enumerate(self.get_branches_wo_hvdc()):
            val[:, i] = branch.rate_prof * branch.contingency_factor_prof

        return val

    def get_branch_contingency_rates_wo_hvdc(self) -> Vec:
        """
        Get the complex bus power Injections
        :return: (nbr) [MVA]
        """
        val = np.zeros(self.get_branch_number_wo_hvdc())

        for i, branch in enumerate(self.get_branches_wo_hvdc()):
            val[i] = branch.rate_prof * branch.contingency_factor

        return val
