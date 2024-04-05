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

import os
import cmath
import warnings
import copy
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Union, Any, Callable, Set
from uuid import getnode as get_mac, uuid4
from datetime import timedelta, datetime
import networkx as nx
from matplotlib import pyplot as plt
from scipy.sparse import csc_matrix, lil_matrix

from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.basic_structures import IntVec, StrVec, Vec, Mat, CxVec, IntMat, CxMat
from GridCalEngine.data_logger import DataLogger
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.types import ALL_DEV_TYPES, BRANCH_TYPES, INJECTION_DEVICE_TYPES, FLUID_TYPES
from GridCalEngine.basic_structures import Logger
import GridCalEngine.Topology.topology as tp
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


def get_fused_device_lst(elm_list: List[INJECTION_DEVICE_TYPES], property_names: list):
    """
    Fuse all the devices of a list by adding their selected properties
    :param elm_list: list of devices
    :param property_names: properties to fuse
    :return: list of one element
    """
    if len(elm_list) > 1:
        # more than a single element, fuse the list

        elm1 = elm_list[0]  # select the main device
        deletable_elms = [elm_list[i] for i in range(1, len(elm_list))]
        act_final = elm1.active
        act_prof_final = elm1.active_prof.toarray()

        # set the final active value
        for i in range(1, len(elm_list)):  # for each of the other generators
            elm2 = elm_list[i]

            # modify the final status
            act_final = bool(act_final + elm2.active)  # equivalent to OR

            if act_prof_final is not None:
                act_prof_final = (act_prof_final.toarray() + elm2.active_prof.toarray()).astype(bool)

        for prop in property_names:  # sum the properties

            # initialize the value with whatever it is inside elm1
            if 'prof' not in prop:
                # is a regular property
                val = getattr(elm1, prop) * elm1.active
            else:
                if act_prof_final is not None:
                    # it is a profile property
                    val = getattr(elm1, prop).toarray() * elm1.active_prof.toarray()
                else:
                    val = None

            for i in range(1, len(elm_list)):  # for each of the other generators
                elm2 = elm_list[i]

                if 'prof' not in prop:
                    # is a regular property
                    val += getattr(elm2, prop) * elm2.active
                else:
                    if act_prof_final is not None:
                        # it is a profile property
                        val += elm2.get_profile(prop).toarray() * elm2.active_prof.toarray()

            # set the final property value
            if 'prof' not in prop:
                elm1.set_snapshot_value(prop, val)
            else:
                elm1.set_profile(prop, val)

        # set the final active status
        elm1.active = act_final
        elm1.active_prof.set(act_prof_final)

        return [elm1], deletable_elms

    elif len(elm_list) == 1:
        # single element list, return it as it comes
        return elm_list, list()

    else:
        # the list is empty
        return list(), list()


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

        from GridCalEngine.multi_circuit import MultiCircuit
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

        self.series_reactances: List[dev.SeriesReactance] = list()

        # Should accept buses
        self.buses: List[dev.Bus] = list()

        # array of connectivity nodes
        self.connectivity_nodes: List[dev.ConnectivityNode] = list()

        # array of busbars
        self.bus_bars: List[dev.BusBar] = list()

        # array of voltage levels
        self.voltage_levels: List[dev.VoltageLevel] = list()

        # List of loads
        self.loads: List[dev.Load] = list()

        # List of generators
        self.generators: List[dev.Generator] = list()

        # List of External Grids
        self.external_grids: List[dev.ExternalGrid] = list()

        # List of shunts
        self.shunts: List[dev.Shunt] = list()

        # List of batteries
        self.batteries: List[dev.Battery] = list()

        # List of static generators
        self.static_generators: List[dev.StaticGenerator] = list()

        # List of current injections devices
        self.current_injections: List[dev.CurrentInjection] = list()

        # List of linear shunt devices
        self.controllable_shunts: List[dev.ControllableShunt] = list()

        # Lists of measurements
        self.pi_measurements: List[dev.PiMeasurement] = list()
        self.qi_measurements: List[dev.QiMeasurement] = list()
        self.vm_measurements: List[dev.VmMeasurement] = list()
        self.pf_measurements: List[dev.PfMeasurement] = list()
        self.qf_measurements: List[dev.QfMeasurement] = list()
        self.if_measurements: List[dev.IfMeasurement] = list()

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

        # list of branch groups
        self.branch_groups: List[dev.BranchGroup] = list()

        # list of substations
        self.substations: List[dev.Substation] = list()  # [self.default_substation]

        # list of areas
        self.areas: List[dev.Area] = list()  # [self.default_area]

        # list of zones
        self.zones: List[dev.Zone] = list()  # [self.default_zone]

        # list of countries
        self.countries: List[dev.Country] = list()  # [self.default_country]

        self.communities: List[dev.Community] = list()

        self.regions: List[dev.Region] = list()

        self.municipalities: List[dev.Municipality] = list()

        # logger of events
        self.logger: Logger = Logger()

        # master time profile
        self.time_profile: Union[pd.DatetimeIndex, None] = None

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

        # Modelling authority
        self.modelling_authorities: List[dev.ModellingAuthority] = list()

        # fuels
        self.fuels: List[dev.Fuel] = list()

        # emission gasses
        self.emission_gases: List[dev.EmissionGas] = list()

        self.generators_technologies: List[dev.GeneratorTechnology] = list()

        self.generators_fuels: List[dev.GeneratorFuel] = list()

        self.generators_emissions: List[dev.GeneratorEmission] = list()

        # fluids
        self.fluid_nodes: List[dev.FluidNode] = list()

        # fluid paths
        self.fluid_paths: List[dev.FluidPath] = list()

        # list of turbines
        self.turbines: List[dev.FluidTurbine] = list()

        # list of pumps
        self.pumps: List[dev.FluidPump] = list()

        # list of power to gas devices
        self.p2xs: List[dev.FluidP2x] = list()

        # objects with profiles
        self.objects_with_profiles = {
            "Regions": [
                dev.Country(),
                dev.Community(),
                dev.Region(),
                dev.Municipality(),
                dev.Area(),
                dev.Zone(),
            ],
            "Substation": [
                dev.Substation(),
                dev.VoltageLevel(),
                dev.BusBar(),
                dev.ConnectivityNode(),
                dev.Bus(),
            ],
            "Injections": [
                dev.Generator(),
                dev.Battery(),
                dev.Load(),
                dev.StaticGenerator(),
                dev.ExternalGrid(),
                dev.Shunt(),
                dev.ControllableShunt(),
                dev.CurrentInjection()
            ],
            "Branches": [
                dev.Line(),
                dev.DcLine(),
                dev.Transformer2W(),
                dev.Winding(),
                dev.Transformer3W(),
                dev.SeriesReactance(),
                dev.HvdcLine(),
                dev.VSC(),
                dev.UPFC(),
            ],
            "Fluid": [
                dev.FluidNode(),
                dev.FluidPath(),
                dev.FluidTurbine(),
                dev.FluidPump(),
                dev.FluidP2x(),
            ],
            "Groups": [
                dev.ContingencyGroup(),
                dev.Contingency(),
                dev.InvestmentsGroup(),
                dev.Investment(),
                dev.BranchGroup(),
                dev.ModellingAuthority()
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
                    profile_types = [elm.registered_properties[attr].tpe for attr in profile_attr]
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
            if self.time_profile is not None:
                if self.buses[0].active_prof.size() != self.get_time_number():
                    warnings.warn('The grid has a time signature but the objects do not!')

        return self.time_profile is not None

    def get_unix_time(self) -> IntVec:
        """
        Get the unix time representation of the time
        :return:
        """
        if self.has_time_series:
            return self.time_profile.values.astype(np.int64) // 10 ** 9
        else:
            return np.zeros(0, dtype=np.int64)

    def set_unix_time(self, arr: IntVec):
        """
        Set the time with a unix time
        :param arr: UNIX time iterable
        """
        self.time_profile = pd.to_datetime(arr, unit='s')

    def get_objects_with_profiles_list(self) -> List[ALL_DEV_TYPES]:
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

    def get_branch_lists_wo_hvdc(self) -> List[List[BRANCH_TYPES]]:
        """
        Get list of the branch lists
        :return: List[List[BRANCH_TYPES]]
        """
        return [
            self.lines,
            self.dc_lines,
            self.transformers2w,
            self.windings,
            self.vsc_devices,
            self.upfc_devices,
            self.series_reactances
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

    def get_branch_lists(self) -> List[List[BRANCH_TYPES]]:
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

    def get_time_array(self) -> pd.DatetimeIndex:
        """
        Get the time array
        :return: pd.DatetimeIndex
        """
        return self.time_profile

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
            active[:, i] = b.active_prof.toarray()
        return active

    def get_topologic_group_dict(self) -> Dict[int, List[int]]:
        """
        Get numerical circuit time groups
        :return: Dictionary with the time: [array of times] represented by the index, for instance
                 {0: [0, 1, 2, 3, 4], 5: [5, 6, 7, 8]}
                 This means that [0, 1, 2, 3, 4] are represented by the topology of 0
                 and that [5, 6, 7, 8] are represented by the topology of 5
        """

        return tp.find_different_states(states_array=self.get_branch_active_time_array())

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

    def get_buses(self) -> List[dev.Bus]:
        """
        List of buses
        :return:
        """
        return self.buses

    def get_bus_at(self, i: int) -> dev.Bus:
        """
        List of buses
        :param i: index
        :return:
        """
        return self.buses[i]

    def get_bus_names(self) -> StrVec:
        """
        List of bus names
        :return:
        """
        return np.array([e.name for e in self.buses])

    def get_branches_wo_hvdc(self) -> list[BRANCH_TYPES]:
        """
        Return all the branch objects.
        :return: lines + transformers 2w + hvdc
        """
        lst = list()
        for dev_list in self.get_branch_lists_wo_hvdc():
            lst += dev_list
        return lst

    def get_branches_wo_hvdc_names(self) -> List[str]:
        """
        Get the non HVDC branches' names
        :return: list of names
        """
        return [e.name for e in self.get_branches_wo_hvdc()]

    def get_branches(self) -> List[BRANCH_TYPES]:
        """
        Return all the branch objects
        :return: lines + transformers 2w + hvdc
        """
        return self.get_branches_wo_hvdc() + self.hvdc_lines

    def get_branches_wo_hvdc_index_dict(self) -> Dict[BRANCH_TYPES, int]:
        """
        Get the branch to index dictionary
        :return:
        """
        return {b: i for i, b in enumerate(self.get_branches_wo_hvdc())}

    def get_injection_devices_lists(self) -> List[List[INJECTION_DEVICE_TYPES]]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        return [self.get_generators(),
                self.get_batteries(),
                self.get_loads(),
                self.get_external_grids(),
                self.get_static_generators(),
                self.get_shunts(),
                self.get_controllable_shunts(),
                self.get_current_injections()]

    def get_injection_devices(self) -> List[INJECTION_DEVICE_TYPES]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """

        elms = list()
        for lst in self.get_injection_devices_lists():
            elms += lst
        return elms

    def get_load_like_devices_lists(self) -> List[List[INJECTION_DEVICE_TYPES]]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        return [self.get_loads(),
                self.get_external_grids(),
                self.get_static_generators(),
                self.get_controllable_shunts(),
                self.get_current_injections()]

    def get_load_like_devices(self) -> List[INJECTION_DEVICE_TYPES]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        elms = list()
        for lst in self.get_load_like_devices_lists():
            elms += lst
        return elms

    def get_load_like_device_number(self) -> int:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        n = 0
        for lst in self.get_load_like_devices_lists():
            n += len(lst)

        return n

    def get_generation_like_devices(self) -> List[INJECTION_DEVICE_TYPES]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        return (self.get_generators()
                + self.get_batteries())

    def get_fluid_devices(self) -> List[FLUID_TYPES]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        return (self.get_fluid_nodes()
                + self.get_fluid_paths()
                + self.get_fluid_pumps()
                + self.get_fluid_turbines()
                + self.get_fluid_p2xs())

    def get_fluid_lists(self) -> List[List[FLUID_TYPES]]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        return [self.get_fluid_nodes(),
                self.get_fluid_paths(),
                self.get_fluid_pumps(),
                self.get_fluid_turbines(),
                self.get_fluid_p2xs()]

    def get_contingency_devices(self) -> List[ALL_DEV_TYPES]:
        """
        Get a list of devices susceptible to be included in contingencies
        :return: list of devices
        """
        return self.get_branches() + self.get_generators()

    def get_investment_devices(self) -> List[ALL_DEV_TYPES]:
        """
        Get a list of devices susceptible to be included in investments
        :return: list of devices
        """
        return (self.get_branches() + self.get_generators() + self.get_batteries() +
                self.get_shunts() + self.get_loads() + self.buses)

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

    def get_fuels(self) -> List[dev.Fuel]:
        """

        :return:
        """
        return self.fuels

    def get_fuel_number(self) -> int:
        """

        :return:
        """
        return len(self.fuels)

    def get_fuel_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([elm.name for elm in self.fuels])

    def get_emissions(self) -> List[dev.EmissionGas]:
        """

        :return:
        """
        return self.emission_gases

    def get_emission_number(self) -> int:
        """

        :return:
        """
        return len(self.emission_gases)

    def get_emission_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([elm.name for elm in self.emission_gases])

    def get_loads(self) -> List[dev.Load]:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        return self.loads

    def get_loads_number(self) -> int:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        return len(self.loads)

    def get_load_names(self) -> StrVec:
        """
        Returns a list of :ref:`Load<load>` names.
        """
        return np.array([elm.name for elm in self.loads])

    def get_external_grids(self) -> List[dev.ExternalGrid]:
        """
        Returns a list of :ref:`ExternalGrid<external_grid>` objects in the grid.
        """
        return self.external_grids

    def get_external_grids_number(self) -> int:
        """
        Returns a list of :ref:`ExternalGrid<external_grid>` objects in the grid.
        """
        return len(self.external_grids)

    def get_external_grid_names(self) -> StrVec:
        """
        Returns a list of :ref:`ExternalGrid<external_grid>` names.
        """
        return np.array([elm.name for elm in self.external_grids])

    def get_static_generators(self) -> List[dev.StaticGenerator]:
        """
        Returns a list of :ref:`StaticGenerator<static_generator>` objects in the grid.
        """
        return self.static_generators

    def get_static_generators_number(self) -> int:
        """
        Return number of static generators
        :return:
        """
        return len(self.static_generators)

    def get_static_generators_names(self) -> StrVec:
        """
        Returns a list of :ref:`StaticGenerator<static_generator>` names.
        """
        return np.array([elm.name for elm in self.static_generators])

    def get_shunts(self) -> List[dev.Shunt]:
        """
        Returns a list of :ref:`Shunt<shunt>` objects in the grid.
        """
        return self.shunts

    def get_shunts_number(self) -> int:
        """
        Get the number of shunts
        """
        return len(self.shunts)

    def get_shunt_names(self):
        """
        Returns a list of :ref:`Shunt<shunt>` names.
        """
        return np.array([elm.name for elm in self.shunts])

    def get_generators(self) -> List[dev.Generator]:
        """
        Returns a list of :ref:`Generator<generator>` objects in the grid.
        """
        return self.generators

    def get_generators_number(self) -> int:
        """
        Get the number of generators
        :return: int
        """
        return len(self.generators)

    def get_generator_names(self) -> StrVec:
        """
        Returns a list of :ref:`Generator<generator>` names.
        """
        return np.array([elm.name for elm in self.generators])

    def get_batteries(self) -> List[dev.Battery]:
        """
        Returns a list of :ref:`Battery<battery>` objects in the grid.
        """
        return self.batteries

    def get_batteries_number(self) -> int:
        """
        Returns a list of :ref:`Battery<battery>` objects in the grid.
        """
        return len(self.batteries)

    def get_battery_names(self) -> StrVec:
        """
        Returns a list of :ref:`Battery<battery>` names.
        """
        return np.array([elm.name for elm in self.batteries])

    def get_battery_capacities(self):
        """
        Returns a list of :ref:`Battery<battery>` capacities.
        """
        return np.array([elm.Enom for elm in self.batteries])

    # ----------------------------------------------------------------------------------------------------------------------
    # current_injections
    # ----------------------------------------------------------------------------------------------------------------------

    def get_current_injections(self) -> List[dev.CurrentInjection]:
        """
        List of current_injections
        :return: List[dev.CurrentInjection]
        """
        return self.current_injections

    def get_current_injections_number(self) -> int:
        """
        Size of the list of current_injections
        :return: size of current_injections
        """
        return len(self.current_injections)

    def get_current_injection_at(self, i: int) -> dev.CurrentInjection:
        """
        Get current_injection at i
        :param i: index
        :return: CurrentInjection
        """
        return self.current_injections[i]

    def get_current_injection_names(self) -> StrVec:
        """
        Array of current_injection names
        :return: StrVec
        """
        return np.array([e.name for e in self.current_injections])

    def add_current_injection(self,
                              bus: dev.Bus,
                              api_obj: Union[None, dev.CurrentInjection] = None) -> dev.CurrentInjection:
        """
        Add a CurrentInjection object
        :param bus: Bus
        :param api_obj: CurrentInjection instance
        """

        if api_obj is None:
            api_obj = dev.CurrentInjection()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        if api_obj.name == 'CInj':
            api_obj.name += '@' + bus.name

        self.current_injections.append(api_obj)

        return api_obj

    def delete_current_injection(self, obj: dev.CurrentInjection) -> None:
        """
        Add a CurrentInjection object
        :param obj: CurrentInjection instance
        """

        self.current_injections.remove(obj)

    # ----------------------------------------------------------------------------------------------------------------------
    # controllable_shunts
    # ----------------------------------------------------------------------------------------------------------------------

    def get_controllable_shunts(self) -> List[dev.ControllableShunt]:
        """
        List of controllable_shunts
        :return: List[dev.LinearShunt]
        """
        return self.controllable_shunts

    def get_controllable_shunts_number(self) -> int:
        """
        Size of the list of controllable_shunts
        :return: size of controllable_shunts
        """
        return len(self.controllable_shunts)

    def get_controllable_shunt_at(self, i: int) -> dev.ControllableShunt:
        """
        Get linear_shunt at i
        :param i: index
        :return: LinearShunt
        """
        return self.controllable_shunts[i]

    def get_controllable_shunt_names(self) -> StrVec:
        """
        Array of linear_shunt names
        :return: StrVec
        """
        return np.array([e.name for e in self.controllable_shunts])

    def add_controllable_shunt(self,
                               bus: dev.Bus,
                               api_obj: Union[None, dev.ControllableShunt] = None) -> dev.ControllableShunt:
        """
        Add a ControllableShunt object
        :param bus: Bus
        :param api_obj: ControllableShunt instance
        """

        if api_obj is None:
            api_obj = dev.ControllableShunt()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        if api_obj.name == 'CShutn':
            api_obj.name += '@' + bus.name

        self.controllable_shunts.append(api_obj)

        return api_obj

    def delete_controllable_shunt(self, obj: dev.ControllableShunt) -> None:
        """
        Add a LinearShunt object
        :param obj: LinearShunt instance
        """

        self.controllable_shunts.remove(obj)

    # ----------------------------------------------------------------------------------------------------------------------
    # voltage_levels
    # ----------------------------------------------------------------------------------------------------------------------

    def get_voltage_levels(self) -> List[dev.VoltageLevel]:
        """
        List of voltage_levels
        :return: List[dev.VoltageLevel]
        """
        return self.voltage_levels

    def get_voltage_levels_number(self) -> int:
        """
        Size of the list of voltage_levels
        :return: size of voltage_levels
        """
        return len(self.voltage_levels)

    def get_voltage_level_at(self, i: int) -> dev.VoltageLevel:
        """
        Get voltage_level at i
        :param i: index
        :return: VoltageLevel
        """
        return self.voltage_levels[i]

    def get_voltage_level_names(self) -> StrVec:
        """
        Array of voltage_level names
        :return: StrVec
        """
        return np.array([e.name for e in self.voltage_levels])

    def add_voltage_level(self, obj: dev.VoltageLevel):
        """
        Add a VoltageLevel object
        :param obj: VoltageLevel instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.voltage_levels.append(obj)

    def delete_voltage_level(self, obj: dev.VoltageLevel) -> None:
        """
        Add a VoltageLevel object
        :param obj: VoltageLevel instance
        """

        self.voltage_levels.remove(obj)

    # ----------------------------------------------------------------------------------------------------------------------
    # pi_measurements
    # ----------------------------------------------------------------------------------------------------------------------

    def get_pi_measurements(self) -> List[dev.PiMeasurement]:
        """
        List of pi_measurements
        :return: List[dev.PiMeasurement]
        """
        return self.pi_measurements

    def get_pi_measurements_number(self) -> int:
        """
        Size of the list of pi_measurements
        :return: size of pi_measurements
        """
        return len(self.pi_measurements)

    def get_pi_measurement_at(self, i: int) -> dev.PiMeasurement:
        """
        Get pi_measurement at i
        :param i: index
        :return: PiMeasurement
        """
        return self.pi_measurements[i]

    def get_pi_measurement_names(self) -> StrVec:
        """
        Array of pi_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self.pi_measurements])

    def add_pi_measurement(self, obj: dev.PiMeasurement):
        """
        Add a PiMeasurement object
        :param obj: PiMeasurement instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.pi_measurements.append(obj)

    def delete_pi_measurement(self, obj: dev.PiMeasurement) -> None:
        """
        Add a PiMeasurement object
        :param obj: PiMeasurement instance
        """

        self.pi_measurements.remove(obj)

    # ----------------------------------------------------------------------------------------------------------------------
    # qi_measurements
    # ----------------------------------------------------------------------------------------------------------------------

    def get_qi_measurements(self) -> List[dev.QiMeasurement]:
        """
        List of qi_measurements
        :return: List[dev.QiMeasurement]
        """
        return self.qi_measurements

    def get_qi_measurements_number(self) -> int:
        """
        Size of the list of qi_measurements
        :return: size of qi_measurements
        """
        return len(self.qi_measurements)

    def get_qi_measurement_at(self, i: int) -> dev.QiMeasurement:
        """
        Get qi_measurement at i
        :param i: index
        :return: QiMeasurement
        """
        return self.qi_measurements[i]

    def get_qi_measurement_names(self) -> StrVec:
        """
        Array of qi_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self.qi_measurements])

    def add_qi_measurement(self, obj: dev.QiMeasurement):
        """
        Add a QiMeasurement object
        :param obj: QiMeasurement instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.qi_measurements.append(obj)

    def delete_qi_measurement(self, obj: dev.QiMeasurement) -> None:
        """
        Add a QiMeasurement object
        :param obj: QiMeasurement instance
        """

        self.qi_measurements.remove(obj)

    # ----------------------------------------------------------------------------------------------------------------------
    # vm_measurements
    # ----------------------------------------------------------------------------------------------------------------------

    def get_vm_measurements(self) -> List[dev.VmMeasurement]:
        """
        List of vm_measurements
        :return: List[dev.VmMeasurement]
        """
        return self.vm_measurements

    def get_vm_measurements_number(self) -> int:
        """
        Size of the list of vm_measurements
        :return: size of vm_measurements
        """
        return len(self.vm_measurements)

    def get_vm_measurement_at(self, i: int) -> dev.VmMeasurement:
        """
        Get vm_measurement at i
        :param i: index
        :return: VmMeasurement
        """
        return self.vm_measurements[i]

    def get_vm_measurement_names(self) -> StrVec:
        """
        Array of vm_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self.vm_measurements])

    def add_vm_measurement(self, obj: dev.VmMeasurement):
        """
        Add a VmMeasurement object
        :param obj: VmMeasurement instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.vm_measurements.append(obj)

    def delete_vm_measurement(self, obj: dev.VmMeasurement) -> None:
        """
        Add a VmMeasurement object
        :param obj: VmMeasurement instance
        """

        self.vm_measurements.remove(obj)

    # ----------------------------------------------------------------------------------------------------------------------
    # pf_measurements
    # ----------------------------------------------------------------------------------------------------------------------

    def get_pf_measurements(self) -> List[dev.PfMeasurement]:
        """
        List of pf_measurements
        :return: List[dev.PfMeasurement]
        """
        return self.pf_measurements

    def get_pf_measurements_number(self) -> int:
        """
        Size of the list of pf_measurements
        :return: size of pf_measurements
        """
        return len(self.pf_measurements)

    def get_pf_measurement_at(self, i: int) -> dev.PfMeasurement:
        """
        Get pf_measurement at i
        :param i: index
        :return: PfMeasurement
        """
        return self.pf_measurements[i]

    def get_pf_measurement_names(self) -> StrVec:
        """
        Array of pf_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self.pf_measurements])

    def add_pf_measurement(self, obj: dev.PfMeasurement):
        """
        Add a PfMeasurement object
        :param obj: PfMeasurement instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.pf_measurements.append(obj)

    def delete_pf_measurement(self, obj: dev.PfMeasurement) -> None:
        """
        Add a PfMeasurement object
        :param obj: PfMeasurement instance
        """

        self.pf_measurements.remove(obj)

    # ----------------------------------------------------------------------------------------------------------------------
    # qf_measurements
    # ----------------------------------------------------------------------------------------------------------------------

    def get_qf_measurements(self) -> List[dev.QfMeasurement]:
        """
        List of qf_measurements
        :return: List[dev.QfMeasurement]
        """
        return self.qf_measurements

    def get_qf_measurements_number(self) -> int:
        """
        Size of the list of qf_measurements
        :return: size of qf_measurements
        """
        return len(self.qf_measurements)

    def get_qf_measurement_at(self, i: int) -> dev.QfMeasurement:
        """
        Get qf_measurement at i
        :param i: index
        :return: QfMeasurement
        """
        return self.qf_measurements[i]

    def get_qf_measurement_names(self) -> StrVec:
        """
        Array of qf_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self.qf_measurements])

    def add_qf_measurement(self, obj: dev.QfMeasurement):
        """
        Add a QfMeasurement object
        :param obj: QfMeasurement instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.qf_measurements.append(obj)

    def delete_qf_measurement(self, obj: dev.QfMeasurement) -> None:
        """
        Add a QfMeasurement object
        :param obj: QfMeasurement instance
        """

        self.qf_measurements.remove(obj)

    # ----------------------------------------------------------------------------------------------------------------------
    # if_measurements
    # ----------------------------------------------------------------------------------------------------------------------

    def get_if_measurements(self) -> List[dev.IfMeasurement]:
        """
        List of if_measurements
        :return: List[dev.IfMeasurement]
        """
        return self.if_measurements

    def get_if_measurements_number(self) -> int:
        """
        Size of the list of if_measurements
        :return: size of if_measurements
        """
        return len(self.if_measurements)

    def get_if_measurement_at(self, i: int) -> dev.IfMeasurement:
        """
        Get if_measurement at i
        :param i: index
        :return: IfMeasurement
        """
        return self.if_measurements[i]

    def get_if_measurement_names(self) -> StrVec:
        """
        Array of if_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self.if_measurements])

    def add_if_measurement(self, obj: dev.IfMeasurement):
        """
        Add a IfMeasurement object
        :param obj: IfMeasurement instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.if_measurements.append(obj)

    def delete_if_measurement(self, obj: dev.IfMeasurement) -> None:
        """
        Add a IfMeasurement object
        :param obj: IfMeasurement instance
        """

        self.if_measurements.remove(obj)

    # ----------------------------------------------------------------------------------------------------------------------
    # branch_groups
    # ----------------------------------------------------------------------------------------------------------------------

    def get_branch_groups(self) -> List[dev.BranchGroup]:
        """
        List of branch_groups
        :return: List[dev.BranchGroup]
        """
        return self.branch_groups

    def get_branch_groups_number(self) -> int:
        """
        Size of the list of branch_groups
        :return: size of branch_groups
        """
        return len(self.branch_groups)

    def get_branch_group_at(self, i: int) -> dev.BranchGroup:
        """
        Get branch_group at i
        :param i: index
        :return: BranchGroup
        """
        return self.branch_groups[i]

    def get_branch_group_names(self) -> StrVec:
        """
        Array of branch_group names
        :return: StrVec
        """
        return np.array([e.name for e in self.branch_groups])

    def add_branch_group(self, obj: dev.BranchGroup):
        """
        Add a BranchGroup object
        :param obj: BranchGroup instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.branch_groups.append(obj)

    def delete_branch_group(self, obj: dev.BranchGroup) -> None:
        """
        Add a BranchGroup object
        :param obj: BranchGroup instance
        """

        self.branch_groups.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # modelling_authority
    # ------------------------------------------------------------------------------------------------------------------

    def get_modelling_authorities(self) -> List[dev.ModellingAuthority]:
        """
        List of modelling_authorities
        :return: List[dev.ModellingAuthority]
        """
        return self.modelling_authorities

    def get_modelling_authorities_number(self) -> int:
        """
        Size of the list of modelling_authorities
        :return: size of modelling_authorities
        """
        return len(self.modelling_authorities)

    def get_modelling_authority_at(self, i: int) -> dev.ModellingAuthority:
        """
        Get modelling_authority at i
        :param i: index
        :return: ModellingAuthority
        """
        return self.modelling_authorities[i]

    def get_modelling_authority_names(self) -> StrVec:
        """
        Array of modelling_authority names
        :return: StrVec
        """
        return np.array([e.name for e in self.modelling_authorities])

    def add_modelling_authority(self, obj: dev.ModellingAuthority):
        """
        Add a ModellingAuthority object
        :param obj: ModellingAuthority instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.modelling_authorities.append(obj)

    def delete_modelling_authority(self, obj: dev.ModellingAuthority) -> None:
        """
        Add a ModellingAuthority object
        :param obj: ModellingAuthority instance
        """

        self.modelling_authorities.remove(obj)

    def get_elements_by_type(self, device_type: DeviceType) -> List[ALL_DEV_TYPES]:
        """
        Get set of elements and their parent nodes
        :param device_type: DeviceTYpe instance
        :return: List of elements, it raises an exception if the elements are unknown
        """

        if device_type == DeviceType.LoadDevice:
            return self.get_loads()

        elif device_type == DeviceType.StaticGeneratorDevice:
            return self.get_static_generators()

        elif device_type == DeviceType.GeneratorDevice:
            return self.get_generators()

        elif device_type == DeviceType.BatteryDevice:
            return self.get_batteries()

        elif device_type == DeviceType.ShuntDevice:
            return self.get_shunts()

        elif device_type == DeviceType.ExternalGridDevice:
            return self.get_external_grids()

        elif device_type == DeviceType.CurrentInjectionDevice:
            return self.get_current_injections()

        elif device_type == DeviceType.ControllableShuntDevice:
            return self.get_controllable_shunts()

        elif device_type == DeviceType.LineDevice:
            return self.lines

        elif device_type == DeviceType.Transformer2WDevice:
            return self.transformers2w

        elif device_type == DeviceType.Transformer3WDevice:
            return self.transformers3w

        elif device_type == DeviceType.WindingDevice:
            return self.windings

        elif device_type == DeviceType.SeriesReactanceDevice:
            return self.series_reactances

        elif device_type == DeviceType.HVDCLineDevice:
            return self.hvdc_lines

        elif device_type == DeviceType.UpfcDevice:
            return self.upfc_devices

        elif device_type == DeviceType.VscDevice:
            return self.vsc_devices

        elif device_type == DeviceType.BranchGroupDevice:
            return self.branch_groups

        elif device_type == DeviceType.BusDevice:
            return self.buses

        elif device_type == DeviceType.OverheadLineTypeDevice:
            return self.overhead_line_types

        elif device_type == DeviceType.TransformerTypeDevice:
            return self.transformer_types

        elif device_type == DeviceType.UnderGroundLineDevice:
            return self.underground_cable_types

        elif device_type == DeviceType.SequenceLineDevice:
            return self.sequence_line_types

        elif device_type == DeviceType.WireDevice:
            return self.wire_types

        elif device_type == DeviceType.DCLineDevice:
            return self.dc_lines

        elif device_type == DeviceType.SwitchDevice:
            return self.switch_devices

        elif device_type == DeviceType.SubstationDevice:
            return self.substations

        elif device_type == DeviceType.VoltageLevelDevice:
            return self.voltage_levels

        elif device_type == DeviceType.ConnectivityNodeDevice:
            return self.connectivity_nodes

        elif device_type == DeviceType.BusBarDevice:
            return self.bus_bars

        elif device_type == DeviceType.AreaDevice:
            return self.areas

        elif device_type == DeviceType.ZoneDevice:
            return self.zones

        elif device_type == DeviceType.CountryDevice:
            return self.countries

        elif device_type == DeviceType.CommunityDevice:
            return self.communities

        elif device_type == DeviceType.RegionDevice:
            return self.regions

        elif device_type == DeviceType.MunicipalityDevice:
            return self.municipalities

        elif device_type == DeviceType.ContingencyDevice:
            return self.contingencies

        elif device_type == DeviceType.ContingencyGroupDevice:
            return self.contingency_groups

        elif device_type == DeviceType.Technology:
            return self.technologies

        elif device_type == DeviceType.InvestmentDevice:
            return self.investments

        elif device_type == DeviceType.InvestmentsGroupDevice:
            return self.investments_groups

        elif device_type == DeviceType.FuelDevice:
            return self.fuels

        elif device_type == DeviceType.EmissionGasDevice:
            return self.emission_gases

        elif device_type == DeviceType.GeneratorTechnologyAssociation:
            return self.generators_technologies

        elif device_type == DeviceType.GeneratorFuelAssociation:
            return self.generators_fuels

        elif device_type == DeviceType.GeneratorEmissionAssociation:
            return self.generators_emissions

        elif device_type == DeviceType.ConnectivityNodeDevice:
            return self.connectivity_nodes

        elif device_type == DeviceType.FluidNodeDevice:
            return self.fluid_nodes

        elif device_type == DeviceType.FluidPathDevice:
            return self.get_fluid_paths()

        elif device_type == DeviceType.FluidTurbineDevice:
            return self.get_fluid_turbines()

        elif device_type == DeviceType.FluidPumpDevice:
            return self.get_fluid_pumps()

        elif device_type == DeviceType.FluidP2XDevice:
            return self.get_fluid_p2xs()

        elif device_type == DeviceType.PiMeasurementDevice:
            return self.get_pi_measurements()

        elif device_type == DeviceType.QiMeasurementDevice:
            return self.get_qi_measurements()

        elif device_type == DeviceType.PfMeasurementDevice:
            return self.get_pf_measurements()

        elif device_type == DeviceType.QfMeasurementDevice:
            return self.get_qf_measurements()

        elif device_type == DeviceType.VmMeasurementDevice:
            return self.get_vm_measurements()

        elif device_type == DeviceType.IfMeasurementDevice:
            return self.get_if_measurements()

        elif device_type == DeviceType.LoadLikeDevice:
            return self.get_load_like_devices()

        elif device_type == DeviceType.BranchDevice:
            return self.get_branches_wo_hvdc()

        elif device_type == DeviceType.NoDevice:
            return list()

        elif device_type == DeviceType.TimeDevice:
            return self.get_time_array()

        elif device_type == DeviceType.ModellingAuthority:
            return self.get_modelling_authorities()

        else:
            raise Exception('Element type not understood ' + str(device_type))

    def set_elements_by_type(self, device_type: DeviceType,
                             devices: List[ALL_DEV_TYPES],
                             logger: Logger = Logger()):
        """
        Set a list of elements all at once
        :param device_type: DeviceType
        :param devices: list of devices
        :param logger: Logger
        """
        if device_type == DeviceType.LoadDevice:
            self.loads = devices

        elif device_type == DeviceType.StaticGeneratorDevice:
            self.static_generators = devices

        elif device_type == DeviceType.GeneratorDevice:
            self.generators = devices

        elif device_type == DeviceType.BatteryDevice:
            self.batteries = devices

        elif device_type == DeviceType.ShuntDevice:
            self.shunts = devices

        elif device_type == DeviceType.ExternalGridDevice:
            self.external_grids = devices

        elif device_type == DeviceType.CurrentInjectionDevice:
            self.current_injections = devices

        elif device_type == DeviceType.ControllableShuntDevice:
            self.controllable_shunts = devices

        elif device_type == DeviceType.LineDevice:
            for d in devices:
                # this is done to detect those lines that should be transformers
                self.add_line(d, logger=logger)

        elif device_type == DeviceType.Transformer2WDevice:
            self.transformers2w = devices

        elif device_type == DeviceType.Transformer3WDevice:
            self.transformers3w = devices

        elif device_type == DeviceType.WindingDevice:
            self.windings = devices

        elif device_type == DeviceType.SeriesReactanceDevice:
            self.series_reactances = devices

        elif device_type == DeviceType.HVDCLineDevice:
            self.hvdc_lines = devices

        elif device_type == DeviceType.UpfcDevice:
            self.upfc_devices = devices

        elif device_type == DeviceType.VscDevice:
            for elm in devices:
                elm.correct_buses_connection()
            self.vsc_devices = devices

        elif device_type == DeviceType.BranchGroupDevice:
            self.branch_groups = devices

        elif device_type == DeviceType.BusDevice:
            self.buses = devices

        elif device_type == DeviceType.OverheadLineTypeDevice:
            self.overhead_line_types = devices

        elif device_type == DeviceType.TransformerTypeDevice:
            self.transformer_types = devices

        elif device_type == DeviceType.UnderGroundLineDevice:
            self.underground_cable_types = devices

        elif device_type == DeviceType.SequenceLineDevice:
            self.sequence_line_types = devices

        elif device_type == DeviceType.WireDevice:
            self.wire_types = devices

        elif device_type == DeviceType.DCLineDevice:
            self.dc_lines = devices

        elif device_type == DeviceType.SwitchDevice:
            self.switch_devices = devices

        elif device_type == DeviceType.SubstationDevice:
            self.substations = devices

        elif device_type == DeviceType.VoltageLevelDevice:
            self.voltage_levels = devices

        elif device_type == DeviceType.ConnectivityNodeDevice:
            self.connectivity_nodes = devices

        elif device_type == DeviceType.BusBarDevice:
            self.bus_bars = devices

        elif device_type == DeviceType.AreaDevice:
            self.areas = devices

        elif device_type == DeviceType.ZoneDevice:
            self.zones = devices

        elif device_type == DeviceType.CountryDevice:
            self.countries = devices

        elif device_type == DeviceType.CommunityDevice:
            self.communities = devices

        elif device_type == DeviceType.RegionDevice:
            self.regions = devices

        elif device_type == DeviceType.MunicipalityDevice:
            self.municipalities = devices

        elif device_type == DeviceType.ContingencyDevice:
            self.contingencies = devices

        elif device_type == DeviceType.ContingencyGroupDevice:
            self.contingency_groups = devices

        elif device_type == DeviceType.Technology:
            self.technologies = devices

        elif device_type == DeviceType.InvestmentDevice:
            self.investments = devices

        elif device_type == DeviceType.InvestmentsGroupDevice:
            self.investments_groups = devices

        elif device_type == DeviceType.FuelDevice:
            self.fuels = devices

        elif device_type == DeviceType.EmissionGasDevice:
            self.emission_gases = devices

        elif device_type == DeviceType.GeneratorTechnologyAssociation:
            self.generators_technologies = devices

        elif device_type == DeviceType.GeneratorFuelAssociation:
            self.generators_fuels = devices

        elif device_type == DeviceType.GeneratorEmissionAssociation:
            self.generators_emissions = devices

        elif device_type == DeviceType.ConnectivityNodeDevice:
            self.connectivity_nodes = devices

        elif device_type == DeviceType.FluidNodeDevice:
            self.fluid_nodes = devices

        elif device_type == DeviceType.FluidPathDevice:
            self.fluid_paths = devices

        elif device_type == DeviceType.FluidTurbineDevice:
            self.turbines = devices

        elif device_type == DeviceType.FluidPumpDevice:
            self.pumps = devices

        elif device_type == DeviceType.FluidP2XDevice:
            self.p2xs = devices

        elif device_type == DeviceType.BranchDevice:
            for d in devices:
                self.add_branch(d)  # each branch needs to be converted accordingly

        elif device_type == DeviceType.PiMeasurementDevice:
            self.pi_measurements = devices

        elif device_type == DeviceType.QiMeasurementDevice:
            self.qi_measurements = devices

        elif device_type == DeviceType.PfMeasurementDevice:
            self.pf_measurements = devices

        elif device_type == DeviceType.QfMeasurementDevice:
            self.qf_measurements = devices

        elif device_type == DeviceType.VmMeasurementDevice:
            self.vm_measurements = devices

        elif device_type == DeviceType.IfMeasurementDevice:
            self.if_measurements = devices

        elif device_type == DeviceType.ModellingAuthority:
            self.modelling_authorities = devices

        else:
            raise Exception('Element type not understood ' + str(device_type))

    def delete_elements_by_type(self, obj: ALL_DEV_TYPES):
        """
        Get set of elements and their parent nodes
        :param obj: device object to delete
        :return: List of elements, it raises an exception if the elements are unknown
        """

        element_type = obj.device_type

        if element_type == DeviceType.LoadDevice:
            self.loads.remove(obj)

        elif element_type == DeviceType.StaticGeneratorDevice:
            self.static_generators.remove(obj)

        elif element_type == DeviceType.GeneratorDevice:
            self.generators.remove(obj)

        elif element_type == DeviceType.BatteryDevice:
            self.batteries.remove(obj)

        elif element_type == DeviceType.ShuntDevice:
            self.shunts.remove(obj)

        elif element_type == DeviceType.ExternalGridDevice:
            self.external_grids.remove(obj)

        elif element_type == DeviceType.CurrentInjectionDevice:
            self.current_injections.remove(obj)

        elif element_type == DeviceType.ControllableShuntDevice:
            self.controllable_shunts.remove(obj)

        elif element_type == DeviceType.LineDevice:
            return self.delete_line(obj)

        elif element_type == DeviceType.Transformer2WDevice:
            return self.delete_transformer2w(obj)

        elif element_type == DeviceType.Transformer3WDevice:
            return self.delete_transformer3w(obj)

        elif element_type == DeviceType.WindingDevice:
            return self.delete_winding(obj)

        elif element_type == DeviceType.SeriesReactanceDevice:
            return self.delete_series_reactance(obj)

        elif element_type == DeviceType.HVDCLineDevice:
            return self.delete_hvdc_line(obj)

        elif element_type == DeviceType.UpfcDevice:
            return self.delete_upfc_converter(obj)

        elif element_type == DeviceType.VscDevice:
            return self.delete_vsc_converter(obj)

        elif element_type == DeviceType.BusDevice:
            return self.delete_bus(obj, delete_associated=True)

        elif element_type == DeviceType.ConnectivityNodeDevice:
            return self.delete_connectivity_node(obj)

        elif element_type == DeviceType.BranchGroupDevice:
            return self.delete_branch_group(obj)

        elif element_type == DeviceType.BusBarDevice:
            return self.delete_bus_bar(obj)

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

        elif element_type == DeviceType.VoltageLevelDevice:
            return self.delete_voltage_level(obj)

        elif element_type == DeviceType.AreaDevice:
            return self.delete_area(obj)

        elif element_type == DeviceType.ZoneDevice:
            return self.delete_zone(obj)

        elif element_type == DeviceType.CountryDevice:
            return self.delete_country(obj)

        elif element_type == DeviceType.CommunityDevice:
            return self.delete_community(obj)

        elif element_type == DeviceType.RegionDevice:
            return self.delete_region(obj)

        elif element_type == DeviceType.MunicipalityDevice:
            return self.delete_municipality(obj)

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

        elif element_type == DeviceType.FluidNodeDevice:
            return self.delete_fluid_node(obj)

        elif element_type == DeviceType.FluidTurbineDevice:
            return self.delete_fluid_turbine(obj)

        elif element_type == DeviceType.FluidP2XDevice:
            return self.delete_fluid_p2x(obj)

        elif element_type == DeviceType.FluidPumpDevice:
            return self.delete_fluid_pump(obj)

        elif element_type == DeviceType.FluidPathDevice:
            return self.delete_fluid_path(obj)

        elif element_type == DeviceType.PiMeasurementDevice:
            return self.delete_pi_measurement(obj)

        elif element_type == DeviceType.QiMeasurementDevice:
            return self.delete_qi_measurement(obj)

        elif element_type == DeviceType.PfMeasurementDevice:
            return self.delete_pf_measurement(obj)

        elif element_type == DeviceType.QfMeasurementDevice:
            return self.delete_qf_measurement(obj)

        elif element_type == DeviceType.VmMeasurementDevice:
            return self.delete_vm_measurement(obj)

        elif element_type == DeviceType.IfMeasurementDevice:
            return self.delete_if_measurement(obj)

        elif element_type == DeviceType.ModellingAuthority:
            return self.delete_modelling_authority(obj)

        else:
            raise Exception('Element type not understood ' + str(element_type))

    def get_all_elements_dict(self) -> dict[str, ALL_DEV_TYPES]:
        """
        Get a dictionary of all elements
        :return: Dict[idtag] -> object
        """
        data = dict()
        for key, tpe in self.device_type_name_dict.items():
            elements = self.get_elements_by_type(device_type=tpe)

            for elm in elements:
                data[elm.idtag] = elm

        return data

    def gat_all_elements_dict_by_type(self) -> dict[Callable[[], Any], Union[dict[str, ALL_DEV_TYPES], Any]]:
        """
        Get a dictionary of all elements by type
        :return:
        """

        data = dict()
        for key, tpe in self.device_type_name_dict.items():
            data[tpe.value] = self.get_elements_dict_by_type(element_type=tpe, use_secondary_key=False)

        return data

    def get_elements_dict_by_type(self, element_type: DeviceType,
                                  use_secondary_key=False) -> Dict[str, ALL_DEV_TYPES]:
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

    def copy(self) -> "MultiCircuit":
        """
        Returns a deep (true) copy of this circuit.
        """
        cpy = MultiCircuit(name=self.name, Sbase=self.Sbase, fbase=self.fBase, idtag=self.idtag)

        ppts = ['branch_groups',
                'lines',
                'dc_lines',
                'transformers2w',
                'hvdc_lines',
                'vsc_devices',
                'upfc_devices',
                'switch_devices',
                'transformers3w',
                'windings',
                'series_reactances',
                'buses',

                'loads',
                'generators',
                'external_grids',
                'shunts',
                'batteries',
                'static_generators',
                'current_injections',
                'controllable_shunts',

                'connectivity_nodes',
                'bus_bars',
                'overhead_line_types',
                'wire_types',
                'underground_cable_types',
                'sequence_line_types',
                'transformer_types',
                'substations',
                'voltage_levels',
                'areas',
                'zones',
                'countries',
                'communities',
                'regions',
                'municipalities',
                'time_profile',
                'contingencies',
                'contingency_groups',
                'investments',
                'investments_groups',
                'technologies',
                'fuels',
                'emission_gases',
                'generators_technologies',
                'generators_fuels',
                'generators_emissions',
                'fluid_nodes',
                'fluid_paths',
                'pi_measurements',
                'qi_measurements',
                'vm_measurements',
                'pf_measurements',
                'qf_measurements',
                'if_measurements',
                'modelling_authorities'
                ]

        for pr in ppts:
            setattr(cpy, pr, copy.deepcopy(getattr(self, pr)))

        return cpy

    def clear(self) -> None:
        """
        Clear the multi-circuit (remove the bus and branch objects)
        """

        for key, elm_list in self.objects_with_profiles.items():
            for elm in elm_list:
                self.get_elements_by_type(device_type=elm.device_type).clear()

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

    def get_time_profile_as_list(self):
        """
        Get the profiles dictionary
        mainly used in json export
        """
        if self.time_profile is not None:
            # recommended way to get the unix datetimes
            arr = (self.time_profile - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
            # t = (self.time_profile.array.astype(int) * 1e-9).tolist()  # UNIX time in seconds
            return arr.tolist()
        else:
            return list()

    def build_graph(self):
        """
        Returns a networkx DiGraph object of the grid.
        """
        graph = nx.DiGraph()

        bus_dictionary = dict()

        for i, bus in enumerate(self.buses):
            graph.add_node(i)
            bus_dictionary[bus.idtag] = i

        tuples = list()
        for branch_list in self.get_branch_lists():
            for branch in branch_list:
                f = bus_dictionary[branch.bus_from.idtag]
                t = bus_dictionary[branch.bus_to.idtag]
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

        graph.add_weighted_edges_from(tuples)

        return graph

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
        :param steps: Number of time steps
        :param step_length: Time length (1, 2, 15, ...)
        :param step_unit: Unit of the time step ("h", "m" or "s")
        :param time_base: Date to start from
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

    def format_profiles(self, index: pd.DatetimeIndex):
        """
        Format the pandas profiles in place using a time index.
        :param index: Time profile
        """

        self.time_profile = pd.to_datetime(index, dayfirst=True)

        for elm in self.buses:
            elm.create_profiles(index)

        for devs_list in self.get_injection_devices_lists():
            for elm in devs_list:
                elm.create_profiles(index)

        for devs_list in self.get_branch_lists():
            for elm in devs_list:
                elm.create_profiles(index)

        for devs_list in self.get_fluid_lists():
            for elm in devs_list:
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
            print("Error", e)
            # it may come in nanoseconds instead of seconds...
            self.time_profile = pd.to_datetime(np.array(unix_data) / 1e9, unit='s', origin='unix')

        self.ensure_profiles_exist()

        for elm in self.buses:
            elm.create_profiles(self.time_profile)

        for lst in self.get_branch_lists():
            for elm in lst:
                elm.create_profiles(self.time_profile)

        for lst in self.get_injection_devices_lists():
            for elm in lst:
                elm.create_profiles(self.time_profile)

    def ensure_profiles_exist(self) -> None:
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

        for lst in self.get_injection_devices_lists():
            for elm in lst:
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

    def add_bus(self, obj: Union[None, dev.Bus] = None) -> dev.Bus:
        """
        Add a :ref:`Bus<bus>` object to the grid.

        Arguments:

            **obj** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object
        """
        if obj is None:
            obj = dev.Bus()

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)

        self.buses.append(obj)

        return obj

    def delete_bus(self, obj: dev.Bus, delete_associated=False):
        """
        Delete a :ref:`Bus<bus>` object from the grid.
        :param obj: :ref:`Bus<bus>` object
        :param delete_associated:
        """

        # remove associated Branches in reverse order
        for branch_list in self.get_branch_lists():
            for i in range(len(branch_list) - 1, -1, -1):
                if branch_list[i].bus_from == obj:
                    if delete_associated:
                        self.delete_branch(branch_list[i])
                    else:
                        branch_list[i].bus_from = None
                elif branch_list[i].bus_to == obj:
                    if delete_associated:
                        self.delete_branch(branch_list[i])
                    else:
                        branch_list[i].bus_to = None

        # remove the associated injection devices
        for inj_list in self.get_injection_devices_lists():
            for i in range(len(inj_list) - 1, -1, -1):
                if inj_list[i].bus == obj:
                    if delete_associated:
                        self.delete_injection_device(inj_list[i])
                    else:
                        inj_list[i].bus = None

        # remove associations in bus_bars
        for cn in self.connectivity_nodes:
            if cn.default_bus == obj:
                cn.default_bus = None  # remove the association

        # remove the bus itself
        if obj in self.buses:
            self.buses.remove(obj)

    def add_line(self, obj: dev.Line, logger: Union[Logger, DataLogger] = Logger()):
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

    def add_branch(self, obj: Union[BRANCH_TYPES, dev.Branch]) -> None:
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
            raise Exception(f'Unrecognized branch type {obj.device_type.value}')

    def delete_branch(self, obj: BRANCH_TYPES):
        """
        Delete a :ref:`Branch<branch>` object from the grid.

        Arguments:

            **obj** (:ref:`Branch<branch>`): :ref:`Branch<branch>` object
        """
        for branch_list in self.get_branch_lists():
            try:
                branch_list.remove(obj)
            except ValueError:  # element not found ...
                pass

    def delete_injection_device(self, obj: INJECTION_DEVICE_TYPES):
        """
        Delete a :ref:`Branch<branch>` object from the grid.

        Arguments:

            **obj** (:ref:`Branch<branch>`): :ref:`Branch<branch>` object
        """
        for inj_list in self.get_injection_devices_lists():
            try:
                inj_list.remove(obj)
            except ValueError:  # element not found ...
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
        self.delete_bus(obj.bus0, delete_associated=True)  # also remove the middle bus

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

        self.loads.append(api_obj)

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

        self.generators.append(api_obj)

        return api_obj

    def delete_generator(self, obj: dev.Generator):
        """
        Delete a generator
        :param obj:
        :return:
        """
        self.generators.remove(obj)

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

        self.static_generators.append(api_obj)

        return api_obj

    def add_external_grid(self, bus: dev.Bus, api_obj: Union[None, dev.ExternalGrid] = None):
        """
        Add an external grid
        :param bus: Bus object
        :param api_obj: api_obj, if None, create a new one
        :return:
        """

        if api_obj is None:
            api_obj = dev.ExternalGrid()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        if api_obj.name == 'External grid':
            api_obj.name += '@' + bus.name

        self.external_grids.append(api_obj)

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

        self.batteries.append(api_obj)

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

        self.shunts.append(api_obj)

        return api_obj

    def add_wire(self, obj: dev.Wire):
        """
        Add Wire to the collection
        :param obj: Wire instance
        """
        if obj is not None:
            if isinstance(obj, dev.Wire):
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
            if isinstance(obj, dev.OverheadLineType):
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
            if isinstance(obj, dev.UndergroundLineType):
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
            if isinstance(obj, dev.SequenceLineType):
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
            if isinstance(obj, dev.TransformerType):
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

    def apply_all_branch_types(self) -> Logger:
        """
        Apply all the branch types
        """
        logger = Logger()
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

    def get_bus_bars(self) -> List[dev.BusBar]:
        """
        Get all bus bars
        """
        return self.bus_bars

    def get_bus_bars_number(self) -> int:
        """
        Get all bus-bars number
        :return:
        """
        return len(self.bus_bars)

    def add_bus_bar(self, obj: dev.BusBar):
        """
        Add Substation
        :param obj: BusBar object
        """
        self.bus_bars.append(obj)

        # add the internal connectivity node
        self.add_connectivity_node(obj.cn)

    def delete_bus_bar(self, obj: dev.BusBar):
        """
        Delete Substation
        :param obj: Substation object
        """
        for elm in self.connectivity_nodes:
            if elm.bus_bar == obj:
                elm.bus_bar = None

        self.bus_bars.remove(obj)

    def get_connectivity_nodes(self) -> List[dev.ConnectivityNode]:
        """
        Get all connectivity nodes
        """
        return self.connectivity_nodes

    def add_connectivity_node(self, obj: dev.ConnectivityNode):
        """
        Add Substation
        :param obj: BusBar object
        """
        self.connectivity_nodes.append(obj)

    def delete_connectivity_node(self, obj: dev.ConnectivityNode):
        """
        Delete Substation
        :param obj: Substation object
        """
        for elm in self.bus_bars:
            elm.connectivity_node = None

        self.connectivity_nodes.remove(obj)

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

    def get_contingency_group_names(self) -> List[str]:
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

    def get_branches_wo_hvdc_dict(self) -> Dict[str, int]:
        """
        Get dictionary of branches (excluding HVDC)
        the key is the idtag, the value is the branch position
        :return: Dict[str, int]
        """
        return {e.idtag: ei for ei, e in enumerate(self.get_branches_wo_hvdc())}

    def add_contingency(self, obj: dev.Contingency):
        """
        Add a contingency
        :param obj: Contingency
        """
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

    def get_countries(self) -> List[dev.Country]:
        """
        Get all countries
        """
        return self.countries

    def get_country_number(self) -> int:
        """
        Get country number
        :return:
        """
        return len(self.countries)

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

    # ----------------------------------------------------------------------------------------------------------------------
    # series_reactances
    # ----------------------------------------------------------------------------------------------------------------------

    def get_series_reactances(self) -> List[dev.SeriesReactance]:
        """
        List of series_reactances
        :return: List[dev.SeriesReactance]
        """
        return self.series_reactances

    def get_series_reactances_number(self) -> int:
        """
        Size of the list of series_reactances
        :return: size of series_reactances
        """
        return len(self.series_reactances)

    def get_series_reactance_at(self, i: int) -> dev.SeriesReactance:
        """
        Get series_reactance at i
        :param i: index
        :return: SeriesReactance
        """
        return self.series_reactances[i]

    def get_series_reactance_names(self) -> StrVec:
        """
        Array of series_reactance names
        :return: StrVec
        """
        return np.array([e.name for e in self.series_reactances])

    def add_series_reactance(self, obj: dev.SeriesReactance):
        """
        Add a SeriesReactance object
        :param obj: SeriesReactance instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.series_reactances.append(obj)

    def delete_series_reactance(self, obj: dev.SeriesReactance) -> None:
        """
        Add a SeriesReactance object
        :param obj: SeriesReactance instance
        """

        self.series_reactances.remove(obj)

    # ----------------------------------------------------------------------------------------------------------------------
    # communities
    # ----------------------------------------------------------------------------------------------------------------------

    def get_communities(self) -> List[dev.Community]:
        """
        List of communities
        :return: List[dev.Community]
        """
        return self.communities

    def get_communities_number(self) -> int:
        """
        Size of the list of communities
        :return: size of communities
        """
        return len(self.communities)

    def get_community_at(self, i: int) -> dev.Community:
        """
        Get community at i
        :param i: index
        :return: Community
        """
        return self.communities[i]

    def get_community_names(self) -> StrVec:
        """
        Array of community names
        :return: StrVec
        """
        return np.array([e.name for e in self.communities])

    def add_community(self, obj: dev.Community):
        """
        Add a Community object
        :param obj: Community instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.communities.append(obj)

    def delete_community(self, obj: dev.Community) -> None:
        """
        Add a Community object
        :param obj: Community instance
        """

        self.communities.remove(obj)

    # ----------------------------------------------------------------------------------------------------------------------
    # regions
    # ----------------------------------------------------------------------------------------------------------------------

    def get_regions(self) -> List[dev.Region]:
        """
        List of regions
        :return: List[dev.Region]
        """
        return self.regions

    def get_regions_number(self) -> int:
        """
        Size of the list of regions
        :return: size of regions
        """
        return len(self.regions)

    def get_region_at(self, i: int) -> dev.Region:
        """
        Get region at i
        :param i: index
        :return: Region
        """
        return self.regions[i]

    def get_region_names(self) -> StrVec:
        """
        Array of region names
        :return: StrVec
        """
        return np.array([e.name for e in self.regions])

    def add_region(self, obj: dev.Region):
        """
        Add a Region object
        :param obj: Region instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.regions.append(obj)

    def delete_region(self, obj: dev.Region) -> None:
        """
        Add a Region object
        :param obj: Region instance
        """

        self.regions.remove(obj)

    # ----------------------------------------------------------------------------------------------------------------------
    # municipalities
    # ----------------------------------------------------------------------------------------------------------------------

    def get_municipalities(self) -> List[dev.Municipality]:
        """
        List of municipalities
        :return: List[dev.Municipality]
        """
        return self.municipalities

    def get_municipalities_number(self) -> int:
        """
        Size of the list of municipalities
        :return: size of municipalities
        """
        return len(self.municipalities)

    def get_municipality_at(self, i: int) -> dev.Municipality:
        """
        Get municipality at i
        :param i: index
        :return: Municipality
        """
        return self.municipalities[i]

    def get_municipality_names(self) -> StrVec:
        """
        Array of municipality names
        :return: StrVec
        """
        return np.array([e.name for e in self.municipalities])

    def add_municipality(self, obj: dev.Municipality):
        """
        Add a Municipality object
        :param obj: Municipality instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.municipalities.append(obj)

    def delete_municipality(self, obj: dev.Municipality) -> None:
        """
        Add a Municipality object
        :param obj: Municipality instance
        """

        self.municipalities.remove(obj)

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

        # delete the associations
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

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)

    def delete_fluid_node(self, obj: dev.FluidNode):
        """
        Delete fluid node
        :param obj: FluidNode
        """
        # delete dependencies
        for fluid_path in reversed(self.fluid_paths):
            if fluid_path.source == obj or fluid_path.target == obj:
                self.delete_fluid_path(fluid_path)

        self.fluid_nodes.remove(obj)

    def get_fluid_nodes(self) -> List[dev.FluidNode]:
        """

        :return:
        """
        return self.fluid_nodes

    def get_fluid_nodes_number(self) -> int:
        """

        :return:
        """
        return len(self.fluid_nodes)

    def get_fluid_node_names(self) -> StrVec:
        """
        List of fluid node names
        :return:
        """
        return np.array([e.name for e in self.fluid_nodes])

    def add_fluid_path(self, obj: dev.FluidPath):
        """
        Add fluid path
        :param obj:FluidPath
        """
        self.fluid_paths.append(obj)

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)

    def delete_fluid_path(self, obj: dev.FluidPath):
        """
        Delete fuid path
        :param obj: FluidPath
        """
        self.fluid_paths.remove(obj)

    def get_fluid_paths(self) -> List[dev.FluidPath]:
        """

        :return:
        """
        return self.fluid_paths

    def get_fluid_path_names(self) -> StrVec:
        """
        List of fluid paths names
        :return:
        """
        return np.array([e.name for e in self.fluid_paths])

    def get_fluid_paths_number(self) -> int:
        """

        :return:
        """
        return len(self.fluid_paths)

    def add_fluid_turbine(self, node: dev.FluidNode, api_obj: Union[dev.FluidTurbine, None]) -> dev.FluidTurbine:
        """
        Add fluid turbine
        :param node: Fluid node to add to
        :param api_obj: FluidTurbine
        """

        if api_obj is None:
            api_obj = dev.FluidTurbine()
        api_obj.plant = node

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        self.turbines.append(api_obj)

        return api_obj

    def delete_fluid_turbine(self, obj: dev.FluidTurbine):
        """
        Delete fuid turbine
        :param obj: FluidTurbine
        """
        self.turbines.remove(obj)

    def get_fluid_turbines(self) -> List[dev.FluidTurbine]:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        return self.turbines.copy()

    def get_fluid_turbines_number(self) -> int:
        """
        :return: number of total turbines in the network
        """
        return len(self.turbines)

    def get_fluid_turbines_names(self) -> StrVec:
        """
        Returns a list of :ref:`Turbine<turbine>` names.
        """
        return np.array([elm.name for elm in self.turbines])

    def add_fluid_pump(self, node: dev.FluidNode, api_obj: Union[dev.FluidPump, None]) -> dev.FluidPump:
        """
        Add fluid pump
        :param node: Fluid node to add to
        :param api_obj:FluidPump
        """
        if api_obj is None:
            api_obj = dev.FluidTurbine()
        api_obj.plant = node

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        self.pumps.append(api_obj)

        return api_obj

    def delete_fluid_pump(self, obj: dev.FluidPump):
        """
        Delete fuid pump
        :param obj: FluidPump
        """
        self.pumps.remove(obj)

    def get_fluid_pumps(self) -> List[dev.FluidPump]:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        return self.pumps

    def get_fluid_pumps_number(self) -> int:
        """
        :return: number of total pumps in the network
        """
        return len(self.pumps)

    def get_fluid_pumps_names(self) -> StrVec:
        """
        Returns a list of :ref:`Pump<pump>` names.
        """
        return np.array([elm.name for elm in self.pumps])

    def add_fluid_p2x(self, node: dev.FluidNode,
                      api_obj: Union[dev.FluidP2x, None]) -> dev.FluidP2x:
        """
        Add power to x
        :param node: Fluid node to add to
        :param api_obj:FluidP2x
        """
        if api_obj is None:
            api_obj = dev.FluidTurbine()
        api_obj.plant = node

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        self.p2xs.append(api_obj)

        return api_obj

    def delete_fluid_p2x(self, obj: dev.FluidP2x):
        """
        Delete fuid pump
        :param obj: FluidP2x
        """
        self.p2xs.remove(obj)

    def get_fluid_p2xs(self) -> List[dev.FluidP2x]:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        return self.p2xs

    def get_fluid_p2xs_number(self) -> int:
        """
        :return: number of total pumps in the network
        """
        return len(self.p2xs)

    def get_fluid_p2xs_names(self) -> StrVec:
        """
        Returns a list of :ref:`P2X<P2X>` names.
        """
        return np.array([elm.name for elm in self.p2xs])

    def get_fluid_injection_number(self) -> int:
        """
        Get number of fluid injections
        :return: int
        """
        return self.get_fluid_turbines_number() + self.get_fluid_pumps_number() + self.get_fluid_p2xs_number()

    def get_fluid_injection_names(self) -> StrVec:
        """
        Returns a list of :ref:`Injection<Injection>` names.
        Sort by order: turbines, pumps, p2xs
        """
        names = list()
        for elm in self.turbines:
            names.append(elm.name)

        for elm in self.pumps:
            names.append(elm.name)

        for elm in self.p2xs:
            names.append(elm.name)

        return np.array(names)

    def get_fluid_injections(self) -> List[FLUID_TYPES]:
        """
        Returns a list of :ref:`Injection<Injection>` names.
        Sort by order: turbines, pumps, p2xs
        """
        return self.turbines + self.pumps + self.p2xs

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
                            )

        hvdc.active_prof = line.active_prof
        hvdc.rate_prof = line.rate_prof

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
                                        )

        transformer.active_prof = line.active_prof
        transformer.rate_prof = line.rate_prof

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
                           Qmin=gen.Qmin,
                           Qmax=gen.Qmax,
                           Snom=gen.Snom,
                           active=gen.active,
                           Pmin=gen.Pmin,
                           Pmax=gen.Pmax,
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

        batt.active_prof = gen.active_prof
        batt.P_prof = gen.P_prof
        batt.power_factor_prof = gen.Pf_prof
        batt.vset_prof = gen.Vset_prof

        # add device to the circuit
        self.add_battery(gen.bus, batt)

        # delete the line from the circuit
        self.delete_injection_device(gen)

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
                      )

        vsc.active_prof = line.active_prof
        vsc.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_vsc(vsc)

        # delete the line from the circuit
        self.delete_line(line)

        return vsc

    def convert_line_to_upfc(self, line: dev.Line) -> dev.UPFC:
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :return: UPFC
        """
        upfc = dev.UPFC(bus_from=line.bus_from,
                        bus_to=line.bus_to,
                        name='UPFC',
                        active=line.active,
                        rate=line.rate,
                        rs=line.R,
                        xs=line.X)

        upfc.active_prof = line.active_prof
        upfc.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_upfc(upfc)

        # delete the line from the circuit
        self.delete_line(line)

        return upfc

    def convert_line_to_series_reactance(self, line: dev.Line) -> dev.SeriesReactance:
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :return: SeriesReactance
        """
        series_reactance = dev.SeriesReactance(bus_from=line.bus_from,
                                               bus_to=line.bus_to,
                                               name='Series reactance',
                                               active=line.active,
                                               rate=line.rate,
                                               r=line.R,
                                               x=line.X,
                                               )

        series_reactance.active_prof = line.active_prof
        series_reactance.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_series_reactance(series_reactance)

        # delete the line from the circuit
        self.delete_line(line)

        return series_reactance

    def convert_fluid_path_to_line(self, fluid_path: dev.FluidPath) -> dev.Line:
        """
        Convert a line to voltage source converter
        :param fluid_path: FluidPath
        :return: Line
        """
        line = dev.Line(bus_from=fluid_path.source.bus,
                        bus_to=fluid_path.target.bus,
                        name='line',
                        active=True,
                        rate=9999,
                        r=0.001,
                        x=0.01)

        # add device to the circuit
        self.add_line(line)

        # delete the line from the circuit
        self.delete_fluid_path(fluid_path)

        return line

    def plot_graph(self, ax=None):
        """
        Plot the grid.
        :param ax: Matplotlib axis object
        :return:
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        graph = self.build_graph()
        nx.draw_spring(graph, ax=ax)

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

            for elm in self.loads:
                load_names.append(elm.name)
                P.append(elm.P_prof)
                Q.append(elm.Q_prof)

                Ir.append(elm.Ir_prof)
                Ii.append(elm.Ii_prof)

                G.append(elm.G_prof)
                B.append(elm.B_prof)

            for elm in self.generators:
                gen_names.append(elm.name)

                P_gen.append(elm.P_prof)
                V_gen.append(elm.Vset_prof)

            for elm in self.batteries:
                bat_names.append(elm.name)
                gen_names.append(elm.name)
                P_gen.append(elm.P_prof)
                V_gen.append(elm.Vset_prof)
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
            bus.set_profile_values(t)

        for elm in self.get_injection_devices():
            elm.set_profile_values(t)

        for elm in self.get_fluid_devices():
            elm.set_profile_values(t)

        for branch in self.get_branches():
            branch.set_profile_values(t)

    def get_bus_branch_connectivity_matrix(self) -> Tuple[csc_matrix, csc_matrix, csc_matrix]:
        """
        Get the branch-bus connectivity
        :return: Cf, Ct, C
        """
        n = self.get_bus_number()
        m = self.get_branch_number()
        Cf = lil_matrix((m, n))
        Ct = lil_matrix((m, n))

        bus_dict = {bus: i for i, bus in enumerate(self.buses)}

        k = 0
        for branch_list in self.get_branch_lists():
            for br in branch_list:
                i = bus_dict[br.bus_from]  # store the row indices
                j = bus_dict[br.bus_to]  # store the row indices
                Cf[k, i] = 1
                Ct[k, j] = 1
                k += 1

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

        for gen in self.generators:
            if gen.active:
                data['Generators'] = data['Generators'] + gen.P

        for gen in self.static_generators:
            if gen.active:
                data['Static generators'] = data['Static generators'] + gen.P

        for gen in self.batteries:
            if gen.active:
                data['Batteries'] = data['Batteries'] + gen.P

        for load in self.loads:
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
        injections = np.array([g.P for g in self.get_generators()])
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
                             remove_offset: bool = True) -> Logger:
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
        logger = Logger()
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

        logger = Logger()
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

    def import_bus_lat_lon(self, df: pd.DataFrame, bus_col, lat_col, lon_col) -> Logger:
        """
        Import the buses' latitude and longitude
        :param df: Pandas DataFrame with the information
        :param bus_col: bus column name
        :param lat_col: latitude column name
        :param lon_col: longitude column name
        :return: Logger
        """
        logger = Logger()
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

    def get_branch_areas_info(self) -> Tuple[List[str], IntVec, IntVec, IntVec, IntVec, IntVec]:
        """
        Get the area-branches information
        :return: area_names, bus_area_indices, F, T, hvdc_F, hvdc_T
        """
        area_dict = {elm: i for i, elm in enumerate(self.get_areas())}
        bus_dict = self.get_bus_index_dict()

        area_names = [a.name for a in self.get_areas()]
        bus_area_indices = np.array([area_dict.get(b.area, 0) for b in self.get_buses()])

        branches = self.get_branches_wo_hvdc()
        F = np.zeros(len(branches), dtype=int)
        T = np.zeros(len(branches), dtype=int)
        for k, elm in enumerate(branches):
            F[k] = bus_dict[elm.bus_from]
            T[k] = bus_dict[elm.bus_to]

        hvdc = self.get_hvdc()
        hvdc_F = np.zeros(len(hvdc), dtype=int)
        hvdc_T = np.zeros(len(hvdc), dtype=int)
        for k, elm in enumerate(hvdc):
            hvdc_F[k] = bus_dict[elm.bus_from]
            hvdc_T[k] = bus_dict[elm.bus_to]

        return area_names, bus_area_indices, F, T, hvdc_F, hvdc_T

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

    def get_injection_devices_grouped_by_bus(self) -> Dict[dev.Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]]:
        """
        Get the injection devices grouped by bus and by device type
        :return: Dict[bus, Dict[DeviceType, List[Injection devs]]
        """
        groups: Dict[dev.Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]] = dict()

        for lst in self.get_injection_devices_lists():

            for elm in lst:

                devices_by_type = groups.get(elm.bus, None)

                if devices_by_type is None:
                    groups[elm.bus] = {elm.device_type: [elm]}
                else:
                    lst = devices_by_type.get(elm.device_type, None)
                    if lst is None:
                        devices_by_type[elm.device_type] = [elm]
                    else:
                        devices_by_type[elm.device_type].append(elm)

        return groups

    def get_injection_devices_grouped_by_fluid_node(self) -> Dict[dev.FluidNode, Dict[DeviceType, List[FLUID_TYPES]]]:
        """
        Get the injection devices grouped by bus and by device type
        :return: Dict[bus, Dict[DeviceType, List[Injection devs]]
        """
        groups: Dict[dev.FluidNode, Dict[DeviceType, List[FLUID_TYPES]]] = dict()

        for elm in self.get_fluid_injections():

            devices_by_type = groups.get(elm.plant, None)

            if devices_by_type is None:
                groups[elm.plant] = {elm.device_type: [elm]}
            else:
                lst = devices_by_type.get(elm.device_type, None)
                if lst is None:
                    devices_by_type[elm.device_type] = [elm]
                else:
                    devices_by_type[elm.device_type].append(elm)

        return groups

    def get_injection_devices_grouped_by_group_type(
            self,
            group_type: DeviceType) -> List[Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]]:
        """
        Get the injection devices grouped by bus and by device type
        :return: Dict[bus, Dict[DeviceType, List[Injection devs]]
        """
        result: List[Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]] = list()

        group_devices = self.get_elements_by_type(device_type=group_type)

        for group_device in group_devices:

            devices_by_type = dict()

            for lst in self.get_injection_devices_lists():

                for elm in lst:

                    if group_type == DeviceType.AreaDevice:
                        matches = elm.bus.area == group_device

                    elif group_type == DeviceType.ZoneDevice:
                        matches = elm.bus.zone == group_device

                    elif group_type == DeviceType.SubstationDevice:
                        matches = elm.bus.substation == group_device

                    elif group_type == DeviceType.CountryDevice:
                        matches = ((elm.bus.country == group_device) or
                                   (elm.bus.substation.country == group_device))

                    elif group_type == DeviceType.CommunityDevice:
                        matches = (elm.bus.substation.community == group_device)

                    elif group_type == DeviceType.RegionDevice:
                        matches = elm.bus.substation.region == group_device

                    elif group_type == DeviceType.MunicipalityDevice:
                        matches = elm.bus.substation.municipality == group_device

                    else:
                        matches = False

                    if matches:
                        lst = devices_by_type.get(elm.device_type, None)
                        if lst is None:
                            devices_by_type[elm.device_type] = [elm]
                        else:
                            devices_by_type[elm.device_type].append(elm)

            result.append(devices_by_type)

        return result

    def get_batteries_by_bus(self) -> Dict[dev.Bus, List[dev.Battery]]:
        """
        Get the injection devices grouped by bus and by device type
        :return: Dict[bus, Dict[DeviceType, List[Injection devs]]
        """
        groups: Dict[dev.Bus, List[dev.Battery]] = dict()

        for elm in self.get_batteries():

            lst = groups.get(elm.bus, None)
            if lst is None:
                groups[elm.bus] = [elm]
            else:
                lst.append(elm)

        return groups

    def fuse_devices(self) -> List[INJECTION_DEVICE_TYPES]:
        """
        Fuse all the different devices in a node to a single device per node
        :return:
        """
        list_of_deleted = list()
        for bus, devices_by_type in self.get_injection_devices_grouped_by_bus().items():

            for dev_tpe, injection_devs_list in devices_by_type.items():

                if len(injection_devs_list) > 1:
                    # there are more than one device of this type in the bus
                    # we keep the first, we delete the others
                    if dev_tpe == DeviceType.GeneratorDevice:
                        _, to_delete = get_fused_device_lst(injection_devs_list,
                                                            ['P', 'Pmin', 'Pmax',
                                                             'Qmin', 'Qmax', 'Snom', 'P_prof'])
                    elif dev_tpe == DeviceType.BatteryDevice:
                        _, to_delete = get_fused_device_lst(injection_devs_list,
                                                            ['P', 'Pmin', 'Pmax',
                                                             'Qmin', 'Qmax', 'Snom', 'Enom', 'P_prof'])
                    elif dev_tpe == DeviceType.LoadDevice:
                        _, to_delete = get_fused_device_lst(injection_devs_list,
                                                            ['P', 'Q', 'Ir', 'Ii', 'G', 'B',
                                                             'P_prof', 'Q_prof'])
                    elif dev_tpe == DeviceType.StaticGeneratorDevice:
                        _, to_delete = get_fused_device_lst(injection_devs_list, ['P', 'Q', 'P_prof', 'Q_prof'])

                    elif dev_tpe == DeviceType.ShuntDevice:
                        _, to_delete = get_fused_device_lst(injection_devs_list, ['G', 'B', 'G_prof', 'B_prof'])

                    else:
                        to_delete = list()

                    # delete elements
                    for elm in to_delete:
                        self.delete_injection_device(obj=elm)
                        list_of_deleted.append(elm)

        return list_of_deleted

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
            g.active_prof.set(g.P_prof.toarray().astype(bool))

    def set_batteries_active_profile_from_their_active_power(self):
        """
        Modify the batteries active profile to match the active power profile
        if P=0, active = False else active=True
        """
        for g in self.get_batteries():
            g.active_prof.set(g.P_prof.toarray().astype(bool))

    def set_loads_active_profile_from_their_active_power(self):
        """
        Modify the loads active profile to match the active power profile
        if P=0, active = False else active=True
        """
        for ld in self.get_loads():
            ld.active_prof.set(ld.P_prof.toarray().astype(bool))

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

        logger = Logger()

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
        bus_dict = self.get_bus_index_dict()

        for elm in self.get_injection_devices():
            k = bus_dict[elm.bus]
            val[k] = elm.get_S()

        return val

    def get_Sbus_prof(self) -> CxMat:
        """
        Get the complex bus power Injections
        :return: (ntime, nbus) [MW + j MVAr]
        """
        val = np.zeros((self.get_time_number(), self.get_bus_number()), dtype=complex)

        bus_dict = self.get_bus_index_dict()

        for elm in self.get_injection_devices():
            k = bus_dict[elm.bus]
            val[:, k] = elm.get_Sprof()

        return val

    def get_Sbus_prof_fixed(self) -> CxMat:
        """
        Get the complex bus power Injections considering those devices that cannot be dispatched
        This is, all devices except generators and batteries with enabled_dispatch=True
        :return: (ntime, nbus) [MW + j MVAr]
        """
        val = np.zeros((self.get_time_number(), self.get_bus_number()), dtype=complex)
        bus_dict = self.get_bus_index_dict()

        for elm in self.get_load_like_devices():
            k = bus_dict[elm.bus]
            val[:, k] = elm.get_Sprof()

        for elm in self.get_generation_like_devices():
            if not elm.enabled_dispatch:
                k = bus_dict[elm.bus]
                val[:, k] = elm.get_Sprof()

        return val

    def get_Sbus_prof_dispatchable(self) -> CxMat:
        """
        Get the complex bus power Injections only considering those devices that can be dispatched
        This is, generators and batteries with enabled_dispatch=True
        :return: (ntime, nbus) [MW + j MVAr]
        """
        val = np.zeros((self.get_time_number(), self.get_bus_number()), dtype=complex)
        bus_dict = self.get_bus_index_dict()

        for elm in self.get_generation_like_devices():
            if elm.enabled_dispatch:
                k = bus_dict[elm.bus]
                val[:, k] = elm.get_Sprof()

        return val

    def get_Pbus(self) -> Vec:
        """
        Get snapshot active power array per bus
        :return: Vec
        """
        return self.get_Sbus().real

    def get_Pbus_prof(self) -> Mat:
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
            val[:, i] = branch.rate_prof.toarray()

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
            val[:, i] = branch.rate_prof.toarray() * branch.contingency_factor_prof.toarray()

        return val

    def get_branch_contingency_rates_wo_hvdc(self) -> Vec:
        """
        Get the complex bus power Injections
        :return: (nbr) [MVA]
        """
        val = np.zeros(self.get_branch_number_wo_hvdc())

        for i, branch in enumerate(self.get_branches_wo_hvdc()):
            val[i] = branch.rate_prof.toarray() * branch.contingency_factor.toarray()

        return val

    def get_generator_indexing_dict(self) -> Dict[str, int]:
        """
        Get a dictionary that relates the generator uuid's with their index
        :return: Dict[str, int]
        """
        gen_index_dict: Dict[str, int] = dict()
        for k, elm in enumerate(self.get_generators()):
            gen_index_dict[elm.idtag] = k  # associate the idtag to the index
        return gen_index_dict

    def get_fuel_indexing_dict(self) -> Dict[str, int]:
        """
        Get a dictionary that relates the fuel uuid's with their index
        :return: Dict[str, int]
        """
        index_dict: Dict[str, int] = dict()
        for k, elm in enumerate(self.get_fuels()):
            index_dict[elm.idtag] = k  # associate the idtag to the index
        return index_dict

    def get_emissions_indexing_dict(self) -> Dict[str, int]:
        """
        Get a dictionary that relates the fuel uuid's with their index
        :return: Dict[str, int]
        """
        index_dict: Dict[str, int] = dict()
        for k, elm in enumerate(self.get_emissions()):
            index_dict[elm.idtag] = k  # associate the idtag to the index
        return index_dict

    def get_technology_indexing_dict(self) -> Dict[str, int]:
        """
        Get a dictionary that relates the fuel uuid's with their index
        :return: Dict[str, int]
        """
        index_dict: Dict[str, int] = dict()
        for k, elm in enumerate(self.technologies):
            index_dict[elm.idtag] = k  # associate the idtag to the index
        return index_dict

    def get_fuel_rates_sparse_matrix(self) -> csc_matrix:
        """
        Get the fuel rates matrix with relation to the generators
        should be used to get the fuel amounts by: Rates_mat x Pgen
        :return: CSC sparse matrix (n_fuel, n_gen)
        """
        nfuel = len(self.fuels)
        gen_index_dict = self.get_generator_indexing_dict()
        fuel_index_dict = self.get_fuel_indexing_dict()
        nelm = len(gen_index_dict)

        gen_fuel_rates_matrix: lil_matrix = lil_matrix((nfuel, nelm), dtype=float)

        # create associations between generators and fuels
        for entry in self.generators_fuels:
            gen_idx = gen_index_dict[entry.generator.idtag]
            fuel_idx = fuel_index_dict[entry.fuel.idtag]
            gen_fuel_rates_matrix[fuel_idx, gen_idx] = entry.rate

        return gen_fuel_rates_matrix.tocsc()

    def get_emission_rates_sparse_matrix(self) -> csc_matrix:
        """
        Get the emission rates matrix with relation to the generators
        should be used to get the fuel amounts by: Rates_mat x Pgen
        :return: CSC sparse matrix (n_emissions, n_gen)
        """
        nemissions = len(self.emission_gases)
        gen_index_dict = self.get_generator_indexing_dict()
        em_index_dict = self.get_emissions_indexing_dict()
        nelm = len(gen_index_dict)

        gen_emissions_rates_matrix: lil_matrix = lil_matrix((nemissions, nelm), dtype=float)

        # create associations between generators and emissions
        for entry in self.generators_emissions:
            gen_idx = gen_index_dict[entry.generator.idtag]
            em_idx = em_index_dict[entry.emission.idtag]
            gen_emissions_rates_matrix[em_idx, gen_idx] = entry.rate

        return gen_emissions_rates_matrix.tocsc()

    def get_technology_connectivity_matrix(self) -> csc_matrix:
        """
        Get the technology connectivity matrix with relation to the generators
        should be used to get the generatio per technology by: Tech_mat x Pgen
        :return: CSC sparse matrix (n_tech, n_gen)
        """
        ntech = len(self.technologies)
        gen_index_dict = self.get_generator_indexing_dict()
        tech_index_dict = self.get_technology_indexing_dict()
        nelm = len(gen_index_dict)

        gen_tech_proportions_matrix: lil_matrix = lil_matrix((ntech, nelm), dtype=int)

        # create associations between generators and technologies
        for i, entry in enumerate(self.generators_technologies):
            gen_idx = gen_index_dict[entry.generator.idtag]
            tech_idx = tech_index_dict[entry.technology.idtag]
            gen_tech_proportions_matrix[tech_idx, gen_idx] = entry.proportion

        return gen_tech_proportions_matrix.tocsc()

    def set_investments_status(self, investments_list: List[dev.Investment], status: bool,
                               all_elemnts_dict: Union[None, dict[str, EditableDevice]] = None) -> None:
        """
        Set the active (and active profile) status of a list of investmensts' objects
        :param investments_list: list of investments
        :param status: status to set in the internal strctures
        :param all_elemnts_dict: Dictionary of all elemets (idtag -> object), if None if is computed
        """

        if all_elemnts_dict is None:
            all_elemnts_dict = self.get_all_elements_dict()

        for inv in investments_list:
            device_idtag = inv.device_idtag
            device = all_elemnts_dict[device_idtag]

            if hasattr(device, 'active'):
                device.active = status
                profile = device.get_profile('active')
                if profile is not None:
                    profile.fill(status)

    def merge_buses(self, bus1: dev.Bus, bus2: dev.Bus):
        """
        Transfer the injection elements' associations from bus2 to bus 1
        :param bus1: Bus that will receive the devices
        :param bus2: Bus that "donates" the devices
        """
        for elm in self.get_injection_devices():

            if elm.bus == bus2:
                elm.bus = bus1

    def compare_circuits(self, grid2: "MultiCircuit", detailed_profile_comparison: bool = True) -> Tuple[bool, Logger]:
        """
        Compare this circuit with another circuits for equality
        :param grid2: MultiCircuit
        :param detailed_profile_comparison: if true, profiles are compared element-wise with the getters
        :return: equal?, Logger with the comparison information
        """
        logger = Logger()

        if self.get_time_number() != grid2.get_time_number():
            nt = 0
            logger.add_error(msg="Different number of time steps",
                             device_class="time",
                             value=grid2.get_time_number(),
                             expected_value=self.get_time_number())
        else:
            nt = self.get_time_number()

        # for each category
        for key, template_elms_list in self.objects_with_profiles.items():

            # for each object type
            for template_elm in template_elms_list:

                # get all objects of the type
                elms1 = self.get_elements_by_type(device_type=template_elm.device_type)
                elms2 = grid2.get_elements_by_type(device_type=template_elm.device_type)

                if len(elms1) != len(elms2):
                    logger.add_error(msg="Different number of elements",
                                     device_class=template_elm.device_type.value)

                # for every property
                for prop_name, prop in template_elm.registered_properties.items():

                    # for every pair of elements:
                    for elm1, elm2 in zip(elms1, elms2):

                        # compare the snapshot values
                        v1 = elm1.get_property_value(prop=prop, t_idx=None)
                        v2 = elm2.get_property_value(prop=prop, t_idx=None)

                        if v1 != v2:
                            logger.add_error(msg="Different snapshot values",
                                             device_class=template_elm.device_type.value,
                                             device_property=prop.name,
                                             value=v2,
                                             expected_value=v1)

                        if prop.has_profile():
                            p1 = elm1.get_profile_by_prop(prop=prop)
                            p2 = elm1.get_profile_by_prop(prop=prop)

                            if p1 != p2:
                                logger.add_error(msg="Different profile values",
                                                 device_class=template_elm.device_type.value,
                                                 device_property=prop.name,
                                                 object_value=p2,
                                                 expected_object_value=p1)

                            if detailed_profile_comparison:
                                for t_idx in range(nt):

                                    v1 = p1[t_idx]
                                    v2 = p2[t_idx]

                                    if v1 != v2:
                                        logger.add_error(msg="Different time series values",
                                                         device_class=template_elm.device_type.value,
                                                         device_property=prop.name,
                                                         device=str(elm1),
                                                         value=v2,
                                                         expected_value=v1)

                                    v1b = elm1.get_property_value(prop=prop, t_idx=t_idx)
                                    v2b = elm2.get_property_value(prop=prop, t_idx=t_idx)

                                    if v1 != v1b:
                                        logger.add_error(
                                            msg="Profile getting values differ with different getter methods!",
                                            device_class=template_elm.device_type.value,
                                            device_property=prop.name,
                                            device=str(elm1),
                                            value=v1b,
                                            expected_value=v1)

                                    if v2 != v2b:
                                        logger.add_error(
                                            msg="Profile getting values differ with different getter methods!",
                                            device_class=template_elm.device_type.value,
                                            device_property=prop.name,
                                            device=str(elm1),
                                            value=v1b,
                                            expected_value=v1)

        # if any error in the logger, bad
        return logger.error_count() == 0, logger

    def convert_to_node_breaker(self) -> None:
        """
        Convert this MultiCircuit from bus/branch to node/breaker network model
        """

        bbcn = dict()
        for bus in self.buses:
            bus_bar = dev.BusBar(name='Artificial_BusBar_{}'.format(bus.name))
            self.add_bus_bar(bus_bar)
            bbcn[bus.idtag] = bus_bar.cn
            bus_bar.cn.code = bus.code  # for soft checking later
            # bus_bar.cn.default_bus = bus

        # branches
        for elm in self.get_branches():
            # Create two new connectivity nodes
            cnfrom = dev.ConnectivityNode(name='Artificial_CN_from_L{}'.format(elm.name))
            cnto = dev.ConnectivityNode(name='Artificial_CN_to_L{}'.format(elm.name))
            self.add_connectivity_node(cnfrom)
            self.add_connectivity_node(cnto)
            elm.cn_to = cnto
            elm.cn_from = cnfrom
            # Create two new switches
            sw1 = dev.Switch(name='Artificial_SW_from_L{}'.format(elm.name),
                             cn_from=bbcn[elm.bus_from.idtag],
                             cn_to=cnfrom,
                             active=True)
            sw2 = dev.Switch(name='Artificial_SW_to_L{}'.format(elm.name),
                             cn_from=cnto,
                             cn_to=bbcn[elm.bus_to.idtag],
                             active=True)
            self.add_switch(sw1)
            self.add_switch(sw2)

        # injections
        for elm in self.get_injection_devices():
            # TODO: Add the posibbility to add a switch here too
            elm.cn = bbcn[elm.bus.idtag]

        # Removing original buses
        # if not keep_buses:
        bidx = [b for b in self.get_buses()]
        for b in bidx:
            self.delete_bus(b)

    def clean_branches(self,
                       nt: int,
                       bus_set: Set[dev.Bus],
                       cn_set: Set[dev.ConnectivityNode],
                       logger: Logger) -> None:
        """
        Clean the branch refferences
        :param nt: number of time steps
        :param bus_set: Set of Buses
        :param cn_set: Set of connectivity nodes
        :param logger: Logger
        """
        elements_to_delete = list()
        for lst in self.get_branch_lists():
            for elm in lst:
                if elm.bus_from is not None:
                    if elm.bus_from not in bus_set:
                        elm.bus_from = None
                        logger.add_info("Bus from set to None",
                                        device=elm.idtag,
                                        device_class=elm.device_type.value,
                                        device_property="bus_from")

                if elm.bus_to is not None:
                    if elm.bus_to not in bus_set:
                        elm.bus_to = None
                        logger.add_info("Bus to set to None",
                                        device=elm.idtag,
                                        device_class=elm.device_type.value,
                                        device_property="bus_to")

                if elm.cn_from is not None:
                    if elm.cn_from not in cn_set:
                        elm.cn_from = None
                        logger.add_info("Cn from set to None",
                                        device=elm.idtag,
                                        device_class=elm.device_type.value,
                                        device_property="cn_from")

                if elm.cn_to is not None:
                    if elm.cn_to not in cn_set:
                        elm.cn_to = None
                        logger.add_info("Cn to set to None",
                                        device=elm.idtag,
                                        device_class=elm.device_type.value,
                                        device_property="cn_to")

                all_bus_from_prof_none = True
                all_bus_to_prof_none = True
                for t_idx in range(nt):
                    if elm.bus_from_prof[t_idx] is not None:
                        if elm.bus_from_prof[t_idx] not in bus_set:
                            elm.bus_from_prof[t_idx] = None
                        else:
                            all_bus_from_prof_none = False

                    if elm.bus_to_prof[t_idx] is not None:
                        if elm.bus_to_prof[t_idx] not in bus_set:
                            elm.bus_to_prof[t_idx] = None
                        else:
                            all_bus_to_prof_none = False

                # if the element is topologically isolated, delete it
                if (all_bus_from_prof_none and all_bus_to_prof_none
                        and elm.bus_from is None and elm.bus_to is None
                        and elm.cn_from is None and elm.cn_to is None):
                    elements_to_delete.append(elm)

        for elm in elements_to_delete:
            self.delete_elements_by_type(obj=elm)
            logger.add_info("Deleted isolated branch",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

    def clean_injections(self,
                         nt: int,
                         bus_set: Set[dev.Bus],
                         cn_set: Set[dev.ConnectivityNode],
                         logger: Logger) -> None:
        """
        Clean the branch refferences
        :param nt: number of time steps
        :param bus_set: Set of Buses
        :param cn_set: Set of connectivity nodes
        :param logger: Logger
        """
        elements_to_delete = list()
        for lst in self.get_injection_devices_lists():
            for elm in lst:
                if elm.bus is not None:
                    if elm.bus not in bus_set:
                        elm.bus = None
                        logger.add_info("Bus set to None",
                                        device=elm.idtag,
                                        device_class=elm.device_type.value,
                                        device_property="bus")

                if elm.cn is not None:
                    if elm.cn not in cn_set:
                        elm.cn = None
                        logger.add_info("Cn set to None",
                                        device=elm.idtag,
                                        device_class=elm.device_type.value,
                                        device_property="cn")

                all_bus_prof_none = True
                for t_idx in range(nt):
                    if elm.bus_prof[t_idx] is not None:
                        if elm.bus_prof[t_idx] not in bus_set:
                            elm.bus_prof[t_idx] = None
                        else:
                            all_bus_prof_none = False

                # if the element is topologically isolated, delete it
                if all_bus_prof_none and elm.bus is None and elm.cn is None:
                    elements_to_delete.append(elm)

        for elm in elements_to_delete:
            self.delete_elements_by_type(obj=elm)
            logger.add_info("Deleted isolated injection",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

    def clean_contingencies(self, all_dev: Dict[str, ALL_DEV_TYPES], logger: Logger) -> None:
        """
        Clean the contingencies and contingency groups
        :param all_dev:
        :param logger: Logger
        """
        contingencies_to_delete = list()

        # pass 1: detect the "null" contingencies
        for elm in self.contingencies:
            if elm.device_idtag not in all_dev.keys():
                contingencies_to_delete.append(elm)

        # pass 2: delete the "null" contingencies
        for elm in contingencies_to_delete:
            self.delete_contingency(obj=elm)
            logger.add_info("Deleted isolated contingency",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

        # pass 3: count how many times a group is refferenced
        group_counter = np.zeros(len(self.contingency_groups), dtype=int)
        group_dict = {elm: i for i, elm in enumerate(self.contingency_groups)}
        for elm in self.contingencies:
            group_idx = group_dict[elm.group]
            group_counter[group_idx] += 1

        # pass 4: delete unrefferenced groups
        groups_to_delete = [elm for i, elm in enumerate(self.contingency_groups) if group_counter[i] == 0]
        for elm in groups_to_delete:
            self.delete_contingency_group(obj=elm)
            logger.add_info("Deleted isolated contingency group",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

    def clean_investments(self, all_dev: Dict[str, ALL_DEV_TYPES], logger: Logger) -> None:
        """
        Clean the investments and investment groups
        :param all_dev:
        :param logger: Logger
        """
        contingencies_to_delete = list()

        # pass 1: detect the "null" contingencies
        for elm in self.investments:
            if elm.device_idtag not in all_dev.keys():
                contingencies_to_delete.append(elm)

        # pass 2: delete the "null" contingencies
        for elm in contingencies_to_delete:
            self.delete_investment(obj=elm)
            logger.add_info("Deleted isolated investment",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

        # pass 3: count how many times a group is refferenced
        group_counter = np.zeros(len(self.investments_groups), dtype=int)
        group_dict = {elm: i for i, elm in enumerate(self.investments_groups)}
        for elm in self.investments:
            group_idx = group_dict[elm.group]
            group_counter[group_idx] += 1

        # pass 4: delete unrefferenced groups
        groups_to_delete = [elm for i, elm in enumerate(self.investments_groups) if group_counter[i] == 0]
        for elm in groups_to_delete:
            self.delete_investment_groups(obj=elm)
            logger.add_info("Deleted isolated investment group",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

    def clean(self) -> Logger:
        """
        Clean dead references
        """
        logger = Logger()
        bus_set = set(self.buses)
        cn_set = set(self.connectivity_nodes)
        all_dev = self.get_all_elements_dict()
        nt = self.get_time_number()

        self.clean_branches(nt=nt, bus_set=bus_set, cn_set=cn_set, logger=logger)
        self.clean_injections(nt=nt, bus_set=bus_set, cn_set=cn_set, logger=logger)
        self.clean_contingencies(all_dev=all_dev, logger=logger)
        self.clean_investments(all_dev=all_dev, logger=logger)

        return logger

    # def split_line(self, line: dev.Line, position: float) -> Tuple["Line", "Line", Bus]:
    #     """
    #     Split a branch by a given distance
    #     :param position: per unit distance measured from the "from" bus (0 ~ 1)
    #     :return: the two new Branches and the mid short circuited bus
    #     """
    #
    #     assert (0.0 < position < 1.0)
    #
    #     # Each of the Branches will have the proportional impedance
    #     # Bus_from           Middle_bus            Bus_To
    #     # o----------------------o--------------------o
    #     #   >-------- x -------->|
    #     #   (x: distance measured in per unit (0~1)
    #
    #     middle_bus = line.bus_from.copy()
    #     middle_bus.name += ' split'
    #
    #     # C(x, y) = (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    #     middle_bus.X = line.bus_from.x + (line.bus_to.x - line.bus_from.x) * position
    #     middle_bus.y = line.bus_from.y + (line.bus_to.y - line.bus_from.y) * position
    #
    #     props_to_scale = ['R', 'R0', 'X', 'X0', 'B', 'B0', 'length']  # list of properties to scale
    #
    #     br1 = line.copy()
    #     br1.bus_from = line.bus_from
    #     br1.bus_to = middle_bus
    #     for p in props_to_scale:
    #         setattr(br1, p, getattr(line, p) * position)
    #
    #     br2 = line.copy()
    #     br2.bus_from = middle_bus
    #     br2.bus_to = line.bus_to
    #     for p in props_to_scale:
    #         setattr(br2, p, getattr(line, p) * (1.0 - position))
    #
    #     return br1, br2, middle_bus
