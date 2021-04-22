# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
from typing import List, Dict, Tuple
from uuid import getnode as get_mac, uuid4
from datetime import timedelta
import networkx as nx
from scipy.sparse import csc_matrix, lil_matrix
from GridCal.Engine.basic_structures import Logger
from GridCal.Gui.GeneralDialogues import *
from GridCal.Engine.Devices import *
from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import Jacobian
from GridCal.Engine.Devices.editable_device import DeviceType


def get_system_user():
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
    nodes (:ref:`buses<Bus>`) and :ref:`branches<Branch>` (lines, transformers or other
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
    These are the :ref:`Bus<bus>` and the :ref:`Branch<branch>`. The branches connect
    the buses and the buses contain all the other possible devices like loads,
    generators, batteries, etc. This simplifies enormously the management of element
    when adding, associating and deleting.

    .. code:: ipython3

        from GridCal.Engine.Core.multi_circuit import MultiCircuit
        grid = MultiCircuit(name="My grid")

    """

    def __init__(self, name='', Sbase=100, fbase=50.0, idtag=None):
        """
        class constructor
        :param name: name of the circuit
        :param Sbase: base power in MVA
        :param fbase: base frequency in Hz
        :param idtag: unique identifier
        """

        self.name = name

        if idtag is None:
            self.idtag = uuid4().hex
        else:
            self.idtag = idtag

        self.comments = ''

        # this is a number that serves
        self.model_version = 2

        # user mane
        self.user_name = get_system_user()

        # Base power (MVA)
        self.Sbase = Sbase

        # Base frequency in Hz
        self.fBase = fbase

        # Should be able to accept Branches, Lines and Transformers alike
        # self.branches = list()

        self.lines = list()  # type: List[Line]

        self.dc_lines = list()  # type: List[DcLine]

        self.transformers2w = list()  # type: List[Transformer2W]

        self.hvdc_lines = list()  # type: List[HvdcLine]

        self.vsc_devices = list()  # type: List[VSC]

        self.upfc_devices = list()  # type List[UPFC]

        self.switch_devices = list()  # type List[Switch]

        # array of branch indices in the master circuit
        self.branch_original_idx = list()

        # Should accept buses
        self.buses = list()  # type: List[Bus]

        # array of bus indices in the master circuit
        self.bus_original_idx = list()

        # Dictionary relating the bus object to its index. Updated upon compilation
        self.buses_dict = dict()  # type: Dict[Bus, int]

        # List of overhead line objects
        self.overhead_line_types = list()  # type: List[Tower]

        # list of wire types
        self.wire_types = list()  # type: List[Wire]

        # underground cable lines
        self.underground_cable_types = list()  # type: List[UndergroundLineType]

        # sequence modelled lines
        self.sequence_line_types = list()  # type: List[SequenceLineType]

        # List of transformer types
        self.transformer_types = list()  # type: List[TransformerType]

        # list of substations
        self.default_substation = Substation('Default substation')
        self.substations = [self.default_substation]  # type: List[Substation]

        # list of areas
        self.default_area = Area('Default area')
        self.areas = [self.default_area]  # type: List[Area]

        # list of zones
        self.default_zone = Zone('Default zone')
        self.zones = [self.default_zone]  # type: List[Zone]

        # list of countries
        self.default_country = Country('Default country')
        self.countries = [self.default_country]  # type: List[Country]

        # logger of events
        self.logger = Logger()

        # Object with the necessary inputs for a power flow study
        self.numerical_circuit = None

        # Bus-Branch graph
        self.graph = None

        # dictionary of bus objects -> bus indices
        self.bus_dictionary = dict()

        # dictionary of branch objects -> branch indices
        self.branch_dictionary = dict()

        # are there time series??
        self.has_time_series = False

        # names of the buses
        self.bus_names = None

        # names of the branches
        self.branch_names = None

        # master time profile
        self.time_profile = None

        # objects with profiles
        self.objects_with_profiles = [Bus(),
                                      Load(),
                                      StaticGenerator(),
                                      Generator(),
                                      Battery(),
                                      Shunt(),
                                      Line(None, None),
                                      DcLine(None, None),
                                      Transformer2W(None, None),
                                      HvdcLine(None, None),
                                      VSC(None, None),
                                      UPFC(None, None),
                                      Substation(),
                                      Zone(),
                                      Area(),
                                      Country()]

        # this dictionary is set by the GUI and it is not meant to be used by the API operations
        self.results_dictionary = dict()

        # dictionary of profile magnitudes per object
        self.profile_magnitudes = dict()

        self.device_type_name_dict = dict()

        '''
        self.type_name = 'Shunt'

        self.properties_with_profile = ['Y']
        '''
        for dev in self.objects_with_profiles:
            if dev.properties_with_profile is not None:
                profile_attr = list(dev.properties_with_profile.keys())
                profile_types = [dev.editable_headers[attr].tpe for attr in profile_attr]
                self.profile_magnitudes[dev.device_type.value] = (profile_attr, profile_types)
                self.device_type_name_dict[dev.device_type.value] = dev.device_type

    def __str__(self):
        return str(self.name)

    def get_bus_number(self):
        """
        Return the number of buses
        :return: number
        """
        return len(self.buses)

    def get_branch_lists(self):
        """
        GEt list of the branch lists
        :return:
        """
        return [self.lines, self.transformers2w, self.hvdc_lines, self.vsc_devices, self.dc_lines, self.upfc_devices]

    def get_branch_number(self):
        """
        return the number of branches (of all types)
        :return: number
        """
        m = 0
        for branch_list in self.get_branch_lists():
            m += len(branch_list)
        return m

    def get_time_number(self):
        """
        Return the number of buses
        :return: number
        """
        if self.time_profile is not None:
            return len(self.time_profile)
        else:
            return 0

    def get_dimensions(self):
        """
        Get the three dimensions of the circuit: number of buses, number of branches, number of time steps
        :return: (nbus, nbranch, ntime)
        """
        return self.get_bus_number(), self.get_branch_number(), self.get_time_number()

    def clear(self):
        """
        Clear the multi-circuit (remove the bus and branch objects)
        """
        # Should be able to accept Branches, Lines and Transformers alike
        self.lines = list()
        self.dc_lines = list()
        self.transformers2w = list()
        self.hvdc_lines = list()
        self.vsc_devices = list()
        self.upfc_devices = list()

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

        # Object with the necessary inputs for a power flow study
        self.numerical_circuit = None

        # Bus-Branch graph
        self.graph = None

        self.bus_dictionary = dict()

        self.branch_dictionary = dict()

        self.has_time_series = False

        self.bus_names = None

        self.branch_names = None

        self.time_profile = None

    def get_buses(self):
        return self.buses

    def get_branches_wo_hvdc(self):
        """
        Return all the branch objects
        :return: lines + transformers 2w + hvdc
        """
        return self.lines + self.transformers2w + self.vsc_devices + self.dc_lines + self.upfc_devices + self.switch_devices

    def get_branches(self):
        """
        Return all the branch objects
        :return: lines + transformers 2w + hvdc
        """
        return self.get_branches_wo_hvdc() + self.hvdc_lines

    def get_loads(self):
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                elm.bus = bus
            lst = lst + bus.loads
        return lst

    def get_load_names(self):
        """
        Returns a list of :ref:`Load<load>` names.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                lst.append(elm.name)
        return np.array(lst)

    def get_static_generators(self):
        """
        Returns a list of :ref:`StaticGenerator<static_generator>` objects in the grid.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.static_generators:
                elm.bus = bus
            lst = lst + bus.static_generators
        return lst

    def get_static_generators_names(self):
        """
        Returns a list of :ref:`StaticGenerator<static_generator>` names.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.static_generators:
                lst.append(elm.name)
        return np.array(lst)

    def get_shunts(self):
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

    def get_generators(self):
        """
        Returns a list of :ref:`Generator<generator>` objects in the grid.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.controlled_generators:
                elm.bus = bus
            lst = lst + bus.controlled_generators
        return lst

    def get_controlled_generator_names(self):
        """
        Returns a list of :ref:`Generator<generator>` names.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.controlled_generators:
                lst.append(elm.name)
        return np.array(lst)

    def get_batteries(self):
        """
        Returns a list of :ref:`Battery<battery>` objects in the grid.
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                elm.bus = bus
            lst = lst + bus.batteries
        return lst

    def get_battery_names(self):
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

        elif element_type == DeviceType.LineDevice:
            return self.lines

        elif element_type == DeviceType.Transformer2WDevice:
            return self.transformers2w

        elif element_type == DeviceType.HVDCLineDevice:
            return self.hvdc_lines

        elif element_type == DeviceType.UpfcDevice:
            return self.upfc_devices

        elif element_type == DeviceType.VscDevice:
            return self.vsc_devices

        elif element_type == DeviceType.BusDevice:
            return self.buses

        elif element_type == DeviceType.TowerDevice:
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

        elif element_type == DeviceType.SubstationDevice:
            return self.substations

        elif element_type == DeviceType.AreaDevice:
            return self.areas

        elif element_type == DeviceType.ZoneDevice:
            return self.zones

        elif element_type == DeviceType.CountryDevice:
            return self.countries

        else:
            raise Exception('Element type not understood ' + str(element_type))

    def get_node_elements_by_type2(self, element_type: DeviceType):
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

        elif element_type == DeviceType.SubstationDevice:
            return [x.substation for x in self.buses]

        elif element_type == DeviceType.AreaDevice:
            return [x.area for x in self.buses]

        elif element_type == DeviceType.ZoneDevice:
            return [x.zone for x in self.buses]

        elif element_type == DeviceType.CountryDevice:
            return [x.country for x in self.buses]

        else:
            raise Exception('Element type not understood ' + str(element_type))

    # def get_Jacobian(self, sparse=False):
    #     """
    #     Returns the grid Jacobian matrix.
    #
    #     Arguments:
    #
    #         **sparse** (bool, False): Return the matrix in CSR sparse format (True) or
    #         as full matrix (False)
    #     """
    #
    #     numerical_circuit = self.compile_snapshot()
    #     islands = numerical_circuit.compute()
    #     i = 0
    #     # Initial magnitudes
    #     pvpq = np.r_[islands[i].pv, islands[i].pq]
    #
    #     J = Jacobian(Ybus=islands[i].Ybus,
    #                  V=islands[i].Vbus,
    #                  Ibus=islands[i].Ibus,
    #                  pq=islands[i].pq,
    #                  pvpq=pvpq)
    #
    #     if sparse:
    #         return J
    #     else:
    #         return J.todense()

    def apply_lp_profiles(self):
        """
        Apply the LP results as device profiles.
        """
        for bus in self.buses:
            bus.apply_lp_profiles(self.Sbase)

    def copy(self):
        """
        Returns a deep (true) copy of this circuit.
        """

        cpy = MultiCircuit()

        cpy.name = self.name

        bus_dict = dict()
        for bus in self.buses:
            bus_cpy = bus.copy()
            bus_dict[bus] = bus_cpy
            cpy.buses.append(bus_cpy)

        for branch in self.lines:
            cpy.lines.append(branch.copy(bus_dict))

        for branch in self.transformers2w:
            cpy.transformers2w.append(branch.copy(bus_dict))

        for branch in self.hvdc_lines:
            cpy.hvdc_lines.append(branch.copy(bus_dict))

        for branch in self.vsc_devices:
            cpy.vsc_devices.append(branch.copy(bus_dict))

        cpy.Sbase = self.Sbase

        cpy.branch_original_idx = self.branch_original_idx.copy()

        cpy.bus_original_idx = self.bus_original_idx.copy()

        cpy.time_profile = self.time_profile.copy()

        # cpy.numerical_circuit = self.numerical_circuit.copy()

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

    def get_catalogue_dict_by_name(self, type_class=None):

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
        """
        return {'time': 'Milliseconds since 1/1/1970 (Unix time in ms)'}

    def get_profiles_dict(self):
        """
        """
        if self.time_profile is not None:
            t = self.time_profile.astype(int).tolist()
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

        self.bus_dictionary = {bus.idtag: i for i, bus in enumerate(self.buses)}

        for branch_list in self.get_branch_lists():
            for i, branch in enumerate(branch_list):
                f = self.bus_dictionary[branch.bus_from.idtag]
                t = self.bus_dictionary[branch.bus_to.idtag]
                self.graph.add_edge(f, t)

        return self.graph

    def create_profiles(self, steps, step_length, step_unit, time_base: datetime = datetime.now()):
        """
        Set the default profiles in all the objects enabled to have profiles.

        Arguments:

            **steps** (int): Number of time steps

            **step_length** (int): Time length (1, 2, 15, ...)

            **step_unit** (str): Unit of the time step ("h", "m" or "s")

            **time_base** (datetime, datetime.now()): Date to start from
        """

        index = [None] * steps
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

    def get_node_elements_by_type(self, element_type: DeviceType):
        """
        Get set of elements and their parent nodes.

        Arguments:

            **element_type** (str): Element type, either "Load", "StaticGenerator",
            "Generator", "Battery" or "Shunt"

        Returns:

            List of elements, list of matching parent buses
        """
        elements = list()
        parent_buses = list()

        if element_type == DeviceType.LoadDevice:
            for bus in self.buses:
                for elm in bus.loads:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == DeviceType.StaticGeneratorDevice:
            for bus in self.buses:
                for elm in bus.static_generators:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == DeviceType.GeneratorDevice:
            for bus in self.buses:
                for elm in bus.controlled_generators:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == DeviceType.BatteryDevice:
            for bus in self.buses:
                for elm in bus.batteries:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == DeviceType.ShuntDevice:
            for bus in self.buses:
                for elm in bus.shunts:
                    elements.append(elm)
                    parent_buses.append(bus)

        else:
            pass

        return elements, parent_buses

    def get_bus_dict(self):
        """
        Return dictionary of buses
        :return: dictionary of buses {name:object}
        """
        return {b.name: b for b in self.buses}

    def get_bus_index_dict(self):
        """
        Return dictionary of buses
        :return: dictionary of buses {name:object}
        """
        return {b: i for i, b in enumerate(self.buses)}

    def add_bus(self, obj: Bus):
        """
        Add a :ref:`Bus<bus>` object to the grid.

        Arguments:

            **obj** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object
        """
        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)

        if obj.substation is None:
            obj.substation = self.default_substation

        if obj.zone is None:
            obj.zone = self.default_zone

        if obj.area is None:
            obj.area = self.default_area

        if obj.country is None:
            obj.country = self.default_country

        self.buses.append(obj)

    def delete_bus(self, obj: Bus):
        """
        Delete a :ref:`Bus<bus>` object from the grid.

        Arguments:

            **obj** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object
        """

        # remove associated branches in reverse order
        for branch_list in self.get_branch_lists():
            for i in range(len(branch_list) - 1, -1, -1):
                if branch_list[i].bus_from == obj or branch_list[i].bus_to == obj:
                    deleted_elm = branch_list.pop(i)
                    if deleted_elm.graphic_obj is not None:
                        deleted_elm.graphic_obj.remove()

        # remove the bus itself
        if obj in self.buses:
            print('Deleted', obj.name)
            self.buses.remove(obj)

    def add_line(self, obj: Line):
        """
        Add a line object
        :param obj: Line instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.lines.append(obj)

    def add_dc_line(self, obj: DcLine):
        """
        Add a line object
        :param obj: Line instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.dc_lines.append(obj)

    def add_transformer2w(self, obj: Transformer2W):
        """
        Add a transformer object
        :param obj: Transformer2W instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.transformers2w.append(obj)

    def add_hvdc(self, obj: HvdcLine):
        """
        Add a hvdc line object
        :param obj: HvdcLine instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.hvdc_lines.append(obj)

    def add_vsc(self, obj: VSC):
        """
        Add a hvdc line object
        :param obj: HvdcLine instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.vsc_devices.append(obj)

    def add_upfc(self, obj: UPFC):
        """
        Add a UPFC object
        :param obj: UPFC instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.upfc_devices.append(obj)

    def add_switch(self, obj: Switch):
        """
        Add a Switch object
        :param obj: Switch instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self.switch_devices.append(obj)

    def add_branch(self, obj):
        """
        Add a :ref:`Branch<branch>` object to the grid.

        Arguments:

            **obj** (:ref:`Branch<branch>`): :ref:`Branch<branch>` object
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

        elif obj.device_type == DeviceType.SwitchDevice:
            self.add_switch(obj)

        elif obj.device_type == DeviceType.BranchDevice:
            # we need to convert it :D
            if obj.branch_type == BranchType.Line or obj.branch_type == BranchType.Transformer:
                obj2 = convert_branch(obj)
                self.add_branch(obj2)  # call this again, but this time it is not a Branch object
            else:
                print('Omitting branch ' + obj.name)
        else:
            raise Exception('Unrecognized branch type ' + obj.device_type.value)

    def delete_branch(self, obj: Branch):
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

    def delete_line(self, obj: Line):
        """
        Delete line
        :param obj: Line instance
        """
        self.lines.remove(obj)

    def delete_dc_line(self, obj: DcLine):
        """
        Delete line
        :param obj: Line instance
        """
        self.dc_lines.remove(obj)

    def delete_transformer2w(self, obj: Transformer2W):
        """
        Delete transformer
        :param obj: Transformer2W instance
        """
        self.transformers2w.remove(obj)

    def delete_hvdc_line(self, obj: HvdcLine):
        """
        Delete HVDC line
        :param obj:
        """
        self.hvdc_lines.remove(obj)

    def delete_vsc_converter(self, obj: VSC):
        """
        Delete VSC
        :param obj: VSC Instance
        """
        self.vsc_devices.remove(obj)

    def delete_upfc_converter(self, obj: UPFC):
        """
        Delete VSC
        :param obj: VSC Instance
        """
        self.upfc_devices.remove(obj)

    def add_load(self, bus: Bus, api_obj=None):
        """
        Add a :ref:`Load<load>` object to a :ref:`Bus<bus>`.

        Arguments:

            **bus** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object

            **api_obj** (:ref:`Load<load>`): :ref:`Load<load>` object
        """
        if api_obj is None:
            api_obj = Load()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        if api_obj.name == 'Load':
            api_obj.name += '@' + bus.name

        bus.loads.append(api_obj)

        return api_obj

    def add_generator(self, bus: Bus, api_obj=None):
        """
        Add a (controlled) :ref:`Generator<generator>` object to a :ref:`Bus<bus>`.

        Arguments:

            **bus** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object

            **api_obj** (:ref:`Generator<generator>`): :ref:`Generator<generator>`
            object
        """
        if api_obj is None:
            api_obj = Generator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.controlled_generators.append(api_obj)

        return api_obj

    def add_static_generator(self, bus: Bus, api_obj=None):
        """
        Add a :ref:`StaticGenerator<static_generator>` object to a :ref:`Bus<bus>`.

        Arguments:

            **bus** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object

            **api_obj** (:ref:`StaticGenerator<static_generator>`):
            :ref:`StaticGenerator<static_generator>` object
        """
        if api_obj is None:
            api_obj = StaticGenerator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.static_generators.append(api_obj)

        return api_obj

    def add_battery(self, bus: Bus, api_obj=None):
        """
        Add a :ref:`Battery<battery>` object to a :ref:`Bus<bus>`.

        Arguments:

            **bus** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object

            **api_obj** (:ref:`Battery<battery>`): :ref:`Battery<battery>` object
        """
        if api_obj is None:
            api_obj = Battery()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.batteries.append(api_obj)

        return api_obj

    def add_shunt(self, bus: Bus, api_obj=None):
        """
        Add a :ref:`Shunt<shunt>` object to a :ref:`Bus<bus>`.

        Arguments:

            **bus** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object

            **api_obj** (:ref:`Shunt<shunt>`): :ref:`Shunt<shunt>` object
        """
        if api_obj is None:
            api_obj = Shunt()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.create_profiles(self.time_profile)

        bus.shunts.append(api_obj)

        return api_obj

    def add_wire(self, obj: Wire):
        """
        Add Wire to the collection
        :param obj: Wire instance
        """
        if obj is not None:
            if type(obj) == Wire:
                self.wire_types.append(obj)
            else:
                print('The template is not a wire!')

    def delete_wire(self, i, catalogue_to_check=None):
        """
        Delete wire from the collection
        :param i: index
        :param catalogue_to_check: list of catalogue types to check this deletion
        """

        if catalogue_to_check is not None:
            if self.wire_types[i] in catalogue_to_check:
                return False  # do not delete

        self.wire_types.pop(i)
        return True

    def add_overhead_line(self, obj: Tower):
        """
        Add overhead line (tower) template to the collection
        :param obj: Tower instance
        """
        if obj is not None:
            if type(obj) == Tower:
                self.overhead_line_types.append(obj)
            else:
                print('The template is not an overhead line!')

    def delete_overhead_line(self, i, catalogue_to_check=None):
        """
        Delete tower from the collection
        :param i: index
        :param catalogue_to_check: list of catalogue types to check this deletion
        """

        if catalogue_to_check is not None:
            if self.overhead_line_types[i] in catalogue_to_check:
                return False  # do not delete

        self.overhead_line_types.pop(i)
        return True

    def add_underground_line(self, obj: UndergroundLineType):
        """
        Add underground line
        :param obj: UndergroundLineType instance
        """
        if obj is not None:
            if type(obj) == UndergroundLineType:
                self.underground_cable_types.append(obj)
            else:
                print('The template is not an underground line!')

    def delete_underground_line(self, i, catalogue_to_check=None):
        """
        Delete underground line
        :param i: index
        :param catalogue_to_check: list of catalogue types to check this deletion
        """
        if catalogue_to_check is not None:
            if self.underground_cable_types[i] in catalogue_to_check:
                return False  # do not delete

        self.underground_cable_types.pop(i)
        return True

    def add_sequence_line(self, obj: SequenceLineType):
        """
        Add sequence line to the collection
        :param obj: SequenceLineType instance
        """
        if obj is not None:
            if type(obj) == SequenceLineType:
                self.sequence_line_types.append(obj)
            else:
                print('The template is not a sequence line!')

    def delete_sequence_line(self, i, catalogue_to_check=None):
        """
        Delete sequence line from the collection
        :param i: index
        :param catalogue_to_check: list of catalogue types to check this deletion
        """
        if catalogue_to_check is not None:
            if self.sequence_line_types[i] in catalogue_to_check:
                return False  # do not delete

        self.sequence_line_types.pop(i)
        return True

    def add_transformer_type(self, obj: TransformerType):
        """
        Add transformer template
        :param obj: TransformerType instance
        """
        if obj is not None:
            if type(obj) == TransformerType:
                self.transformer_types.append(obj)
            else:
                print('The template is not a transformer!')

    def delete_transformer_type(self, i, catalogue_to_check):
        """
        Delete transformer type from the collection
        :param i: index
        :param catalogue_to_check: list of catalogue types to check this deletion
        """
        if catalogue_to_check is not None:
            if self.transformer_types[i] in catalogue_to_check:
                return False  # do not delete

        self.transformer_types.pop(i)
        return True

    def apply_all_branch_types(self):
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

    def add_substation(self, obj: Substation):
        """
        Add substation
        :param obj: Substation object
        """
        self.substations.append(obj)

    def delete_substation(self, i):
        """
        Delete substation
        :param i: index
        """
        self.substations.pop(i)

    def add_area(self, obj: Area):
        """
        Add area
        :param obj: Area object
        """
        self.areas.append(obj)

    def delete_area(self, i):
        """
        Delete area
        :param i: index
        """
        self.areas.pop(i)

    def add_zone(self, obj: Zone):
        """
        Add zone
        :param obj: Zone object
        """
        self.zones.append(obj)

    def delete_zone(self, i):
        """
        Delete zone
        :param i: index
        """
        self.zones.pop(i)

    def add_country(self, obj: Country):
        """
        Add country
        :param obj: Country object
        """
        self.countries.append(obj)

    def delete_country(self, i):
        """
        Delete country
        :param i: index
        """
        self.countries.pop(i)

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

            df_bus.index = self.bus_names
            df_branch.index = self.branch_names

            writer = pd.ExcelWriter(file_name)
            df_bus.to_excel(writer, 'Bus results')
            df_branch.to_excel(writer, 'Branch results')
            writer.save()
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

                for elm in bus.controlled_generators:
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

            writer = pd.ExcelWriter(file_name)
            P.to_excel(writer, 'P loads')
            Q.to_excel(writer, 'Q loads')

            Ir.to_excel(writer, 'Ir loads')
            Ii.to_excel(writer, 'Ii loads')

            G.to_excel(writer, 'G loads')
            B.to_excel(writer, 'B loads')

            P_gen.to_excel(writer, 'P generators')
            V_gen.to_excel(writer, 'V generators')

            E_batt.to_excel(writer, 'Energy batteries')
            writer.save()
        else:
            raise Exception('There are no time series!')

    def set_state(self, t):
        """
        Set the profiles state at the index t as the default values.
        """
        for bus in self.buses:
            bus.set_state(t)

    def get_bus_branch_connectivity_matrix(self):
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
        Cf = csc_matrix(Cf)
        Ct = csc_matrix(Ct)
        C = Cf + Ct
        return Cf, Ct, C

    def get_adjacent_matrix(self):
        """
        Get the bus adjacent matrix
        :return: Adjacent matrix
        """
        Cf, Ct, C = self.get_bus_branch_connectivity_matrix()
        A = C.T * C
        return A

    @staticmethod
    def get_adjacent_buses(A: csc_matrix, bus_idx):
        """
        Return array of indices of the buses adjacent to the bus given by it's index
        :param A: Adjacent matrix
        :param bus_idx: bus index
        :return: array of adjacent bus indices
        """
        return A.indices[A.indptr[bus_idx]:A.indptr[bus_idx + 1]]

    def try_to_fix_buses_location(self, buses_selection):
        """
        Try to fix the location of the null-location buses
        :param buses_selection: list of tuples index, bus object
        :return: indices of the corrected buses
        """
        delta = 1e20

        while delta > 10:

            A = self.get_adjacent_matrix()

            for k, bus in buses_selection:

                idx = list(self.get_adjacent_buses(A, k))

                # remove the elements already in the selection
                for i in range(len(idx) - 1, 0, -1):
                    if k == idx[i]:
                        idx.pop(i)

                x_arr = list()
                y_arr = list()
                for i in idx:
                    x_arr.append(self.buses[i].graphic_obj.x())
                    y_arr.append(self.buses[i].graphic_obj.y())

                x_m = np.mean(x_arr)
                y_m = np.mean(y_arr)

                delta_i = np.sqrt((bus.x - x_m)**2 + (bus.y - y_m)**2)

                if delta_i < delta:
                    delta = delta_i

                bus.x = x_m.copy()
                bus.y = y_m.copy()
                bus.graphic_obj.set_position(x=bus.x, y=bus.y)

        print('Done!')

    def get_center_location(self):
        """
        Get the mean coordinates of the system (lat, lon)
        """
        coord = np.array([b.get_coordinates() for b in self.buses])

        return coord.mean(axis=0).tolist()

    def get_boundaries(self):
        """
        Get the graphic representation boundaries
        :return: min_x, max_x, min_y, max_y
        """
        min_x = sys.maxsize
        min_y = sys.maxsize
        max_x = -sys.maxsize
        max_y = -sys.maxsize

        # shrink selection only
        for bus in self.buses:
            bus.retrieve_graphic_position()
            x = bus.x
            y = bus.y
            max_x = max(max_x, x)
            min_x = min(min_x, x)
            max_y = max(max_y, y)
            min_y = min(min_y, y)

        return min_x, max_x, min_y, max_y

    def average_separation(self):
        """
        Average separation of the buses
        :param branches: list of Branch elements
        :return: average separation
        """
        separation = 0.0
        branches = self.get_branch_lists()
        for branch in branches:
            s = np.sqrt((branch.bus_from.x - branch.bus_to.x)**2 + (branch.bus_from.y - branch.bus_to.y)**2)
            separation += s
        return separation / len(branches)

    def add_circuit(self, circuit: "MultiCircuit", angle):
        """
        Add a circuit to this circuit
        :param circuit: Circuit to insert
        :param angle: angle in degrees
        :return: Nothing
        """

        min_x, max_x, min_y, max_y = self.get_boundaries()

        sep1 = self.average_separation()

        # compute the average point
        xm = (max_x + min_x) / 2
        ym = (max_y + min_y) / 2

        # compute the radius
        r = np.sqrt((max_x-xm)**2 + (max_y-ym)**2)
        a = np.deg2rad(angle)

        # compute the zero point at which to insert the circuit
        x0 = xm + r * np.cos(a)
        y0 = xm + r * np.sin(a)

        # modify the coordinates of the new circuit
        min_x2, max_x2, min_y2, max_y2 = self.get_boundaries(circuit.buses)
        branches2 = circuit.lines + circuit.transformers2w + circuit.hvdc_lines
        sep2 = self.average_separation(branches2)
        factor = sep2 / sep1
        for bus in circuit.buses:
            bus.x = x0 + (bus.x - min_x2) * factor
            bus.y = y0 + (bus.y - min_y2) * factor

        # add profiles if required
        if self.time_profile is not None:

            for bus in circuit.buses:
                bus.create_profiles(index=self.time_profile)

            for lst in [circuit.lines, circuit.transformers2w, circuit.hvdc_lines]:
                for branch in lst:
                    branch.create_profiles(index=self.time_profile)

        self.buses += circuit.buses
        self.lines += circuit.lines
        self.transformers2w += circuit.transformers2w
        self.hvdc_lines += circuit.hvdc_lines
        self.vsc_devices += circuit.vsc_devices
        self.dc_lines += circuit.dc_lines

        return circuit.buses

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

            for gen in bus.controlled_generators:
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
                if obj.device_type == DeviceType.TowerDevice:
                    for wire in obj.wires_in_tower:
                        val.add(wire)

        return list(val)

    def get_automatic_precision(self):
        """
        Get the precision that simulates correctly the power flow
        :return: tolerance parameter for the power flow options, exponent
        """
        injections = list()
        devices = self.get_loads() + self.get_static_generators() + self.get_generators() + self.get_batteries()
        for elm in devices:
            if elm.P != 0.0:
                injections.append(elm.P)

        P = np.abs(injections) / self.Sbase
        P = P[P > 0]
        lg = np.log10(P)
        lg[lg == -np.inf] = 1e20
        exponent = int(np.min(np.abs(lg))) * 3
        tolerance = 1.0 / (10.0 ** exponent)

        return tolerance, exponent

    def fill_xy_from_lat_lon(self, destructive=True, factor=0.01):
        """
        fill the x and y value from the latitude and longitude values
        :param destructive: if true, the values are overwritten regardless, otherwise only if x and y are 0
        :param factor: Explosion factor
        """

        n = len(self.buses)
        lon = np.zeros(n)
        lat = np.zeros(n)
        for i, bus in enumerate(self.buses):
            lon[i] = bus.longitude
            lat[i] = bus.latitude

        # perform the coordinate transformation
        import pyproj
        x, y = pyproj.Transformer.from_crs(4326, 25830, always_xy=True).transform(lon, lat)
        x *= factor
        y *= factor

        # assign the values
        for i, bus in enumerate(self.buses):
            if destructive or (bus.x == 0.0 and bus.y == 0.0):
                bus.x = x[i]
                bus.y = -y[i]

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

        import pyproj
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

    def import_bus_lat_lon(self, df: pd.DataFrame, bus_col, lat_col, lon_col):
        """

        :param df:
        :param bus_col:
        :param lat_col:
        :param lon_col:
        :return:
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

    def import_plexos_load_profiles(self, df: pd.DataFrame):
        """

        :param df:
        :return: Logger
        """
        logger = Logger()
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
        logger = Logger()
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
                # gen.P_prof = np.zeros(nn)
                # gen.Q_prof = np.zeros(nn)

        return logger

    def import_branch_rates_profiles(self, df: pd.DataFrame):
        """

        :param df:
        :return: Logger
        """
        logger = Logger()
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
