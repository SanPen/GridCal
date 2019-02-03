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

import os
import networkx as nx
import json

from GridCal.Gui.GeneralDialogues import *
from GridCal.Engine.devices import *
from GridCal.Engine.Core.numerical_circuit import NumericalCircuit
from GridCal.Engine.Numerical.jacobian_based_power_flow import Jacobian
from GridCal.Engine.device_types import TransformerType, Tower, BranchTemplate, BranchType, \
                                            UndergroundLineType, SequenceLineType, Wire


class MultiCircuit:
    """
    The concept of circuit should be easy enough to understand. It represents a set of
    nodes (buses) and branches (lines, transformers or other impedances).

    The `MultiCircuit` class is the main object in GridCal. It represents a circuit that
    may contain islands. It is important to understand that a circuit split in two or
    more islands cannot be simulated as is, because the admittance matrix would be
    singular. The solution to this is to split the circuit in island-circuits. Therefore
    `MultiCircuit` identifies the islands and creates individual `Circuit` objects for
    each of them.

    GridCal uses an object oriented approach for the data management. This allows to
    group the data in a smart way. In GridCal there are only two types of object
    directly declared in a `Circuit` or `MultiCircuit` object. These are the `Bus` and
    the `Branch`. The branches connect the buses and the buses contain all the other
    possible devices like loads, generators, batteries, etc. This simplifies enormously
    the management of element when adding, associating and deleting.

    .. code:: ipython3

        from GridCal.Engine.calculation_engine import MultiCircuit
        grid = MultiCircuit(name="My grid")

    """

    def __init__(self, name=''):
        """
        Multi Circuit Constructor
        """

        self.name = name

        self.comments = ''

        # Base power (MVA)
        self.Sbase = 100.0

        # Base frequency in Hz
        self.fBase = 50.0

        # Should be able to accept Branches, Lines and Transformers alike
        self.branches = list()

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
        self.objects_with_profiles = [Load(), StaticGenerator(), Generator(), Battery(), Shunt()]

        # dictionary of profile magnitudes per object
        self.profile_magnitudes = dict()

        '''
        self.type_name = 'Shunt'

        self.properties_with_profile = ['Y']
        '''
        for dev in self.objects_with_profiles:
            if dev.properties_with_profile is not None:
                profile_attr = list(dev.properties_with_profile.keys())
                profile_types = [dev.properties_with_profile[attr][1] for attr in profile_attr]
                self.profile_magnitudes[dev.type_name] = (profile_attr, profile_types)

    def clear(self):

        # Should be able to accept Branches, Lines and Transformers alike
        self.branches = list()

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

        #  containing the power flow results
        self.power_flow_results = None

        # containing the short circuit results
        self.short_circuit_results = None

        # Object with the necessary inputs for th time series simulation
        self.time_series_input = None

        # Object with the time series simulation results
        self.time_series_results = None

        # Monte Carlo input object
        self.monte_carlo_input = None

        # Monte Carlo time series batch
        self.mc_time_series = None

        # Bus-Branch graph
        self.graph = None

        self.bus_dictionary = dict()

        self.branch_dictionary = dict()

        self.has_time_series = False

        self.bus_names = None

        self.branch_names = None

        self.time_profile = None

    def get_loads(self):
        """

        :return:
        """
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                elm.bus = bus
            lst = lst + bus.loads
        return lst

    def get_load_names(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.loads:
                lst.append(elm.name)
        return np.array(lst)

    def get_static_generators(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.static_generators:
                elm.bus = bus
            lst = lst + bus.static_generators
        return lst

    def get_static_generators_names(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.static_generators:
                lst.append(elm.name)
        return np.array(lst)

    def get_shunts(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.shunts:
                elm.bus = bus
            lst = lst + bus.shunts
        return lst

    def get_shunt_names(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.shunts:
                lst.append(elm.name)
        return np.array(lst)

    def get_generators(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.controlled_generators:
                elm.bus = bus
            lst = lst + bus.controlled_generators
        return lst

    def get_controlled_generator_names(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.controlled_generators:
                lst.append(elm.name)
        return np.array(lst)

    def get_batteries(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                elm.bus = bus
            lst = lst + bus.batteries
        return lst

    def get_battery_names(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                lst.append(elm.name)
        return np.array(lst)

    def get_battery_capacities(self):
        lst = list()
        for bus in self.buses:
            for elm in bus.batteries:
                lst.append(elm.Enom)
        return np.array(lst)

    def get_Jacobian(self, sparse=False):
        """
        Returns the Grid Jacobian matrix
        Returns:
            Grid Jacobian Matrix in CSR sparse format or as full matrix
        """

        # Initial magnitudes
        pvpq = np.r_[self.numerical_circuit.pv, self.numerical_circuit.pq]

        J = Jacobian(Ybus=self.numerical_circuit.Ybus,
                     V=self.numerical_circuit.Vbus,
                     Ibus=self.numerical_circuit.Ibus,
                     pq=self.numerical_circuit.pq,
                     pvpq=pvpq)

        if sparse:
            return J
        else:
            return J.todense()

    def get_bus_pf_results_df(self):
        """
        Returns a Pandas DataFrame with the bus results
        :return: DataFrame
        """

        cols = ['|V| (p.u.)', 'angle (rad)', 'P (p.u.)', 'Q (p.u.)', 'Qmin', 'Qmax', 'Q ok?']

        if self.power_flow_results is not None:
            q_l = self.numerical_circuit.Qmin < self.power_flow_results.Sbus.imag
            q_h = self.power_flow_results.Sbus.imag < self.numerical_circuit.Qmax
            q_ok = q_l * q_h
            data = np.c_[np.abs(self.power_flow_results.voltage),
                         np.angle(self.power_flow_results.voltage),
                         self.power_flow_results.Sbus.real,
                         self.power_flow_results.Sbus.imag,
                         self.numerical_circuit.Qmin,
                         self.numerical_circuit.Qmax,
                         q_ok.astype(np.bool)]
        else:
            data = [0, 0, 0, 0, 0, 0]

        return pd.DataFrame(data=data, index=self.numerical_circuit.bus_names, columns=cols)

    def apply_lp_profiles(self):
        """
        Apply the LP results as device profiles
        :return:
        """
        for bus in self.buses:
            bus.apply_lp_profiles(self.Sbase)

    def copy(self):
        """
        Returns a deep (true) copy of this circuit
        @return:
        """

        cpy = MultiCircuit()

        cpy.name = self.name

        bus_dict = dict()
        for bus in self.buses:
            bus_cpy = bus.copy()
            bus_dict[bus] = bus_cpy
            cpy.buses.append(bus_cpy)

        for branch in self.branches:
            cpy.branches.append(branch.copy(bus_dict))

        cpy.Sbase = self.Sbase

        cpy.branch_original_idx = self.branch_original_idx.copy()

        cpy.bus_original_idx = self.bus_original_idx.copy()

        cpy.time_series_input = self.time_series_input.copy()

        cpy.numerical_circuit = self.numerical_circuit.copy()

        return cpy

    def get_catalogue_dict(self, branches_only=False):
        """
        Returns a dictionary with the catalogue types and the associated list of objects
        :param branches_only: only branch types
        :return: dictionary
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

        elif type_class == 'Wires':
            tpes = self.wire_types
            name_prop = 'wire_name'

        elif type_class == 'Overhead lines':
            tpes = self.overhead_line_types
            name_prop = 'tower_name'

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

    def get_json_dict(self, id):
        """
        Get json dictionary
        :return:
        """
        return {'id': id,
                'type': 'circuit',
                'phases': 'ps',
                'name': self.name,
                'Sbase': self.Sbase,
                'comments': self.comments}

    def assign_circuit(self, circ):
        """
        Assign a circuit object to this object
        :param circ: instance of MultiCircuit or Circuit
        """
        self.buses = circ.buses
        self.branches = circ.branches
        self.name = circ.name
        self.Sbase = circ.Sbase
        self.fBase = circ.fBase

        self.sequence_line_types = list(set(self.sequence_line_types + circ.sequence_line_types))
        self.wire_types = list(set(self.wire_types + circ.wire_types))
        self.overhead_line_types = list(set(self.overhead_line_types + circ.overhead_line_types))
        self.underground_cable_types = list(set(self.underground_cable_types + circ.underground_cable_types))
        self.sequence_line_types = list(set(self.sequence_line_types + circ.sequence_line_types))
        self.transformer_types = list(set(self.transformer_types + circ.transformer_types))

    def save_calculation_objects(self, file_path):
        """
        Save all the calculation objects of all the grids
        Args:
            file_path: path to file

        Returns:

        """

        # print('Compiling...', end='')
        numerical_circuit = self.compile()
        calculation_inputs = numerical_circuit.compute()

        writer = pd.ExcelWriter(file_path)

        for c, calc_input in enumerate(calculation_inputs):

            for elm_type in calc_input.available_structures:
                name = elm_type + '_' + str(c)
                df = calc_input.get_structure(elm_type).astype(str)
                df.to_excel(writer, name)

        writer.save()

    def build_graph(self):
        """
        Build graph
        :return: self.graph
        """
        self.graph = nx.DiGraph()

        self.bus_dictionary = {bus: i for i, bus in enumerate(self.buses)}

        for i, branch in enumerate(self.branches):
            f = self.bus_dictionary[branch.bus_from]
            t = self.bus_dictionary[branch.bus_to]
            self.graph.add_edge(f, t)

        return self.graph

    def compile(self, use_opf_vals=False, opf_time_series_results=None, logger=list()):
        """
        Compile the circuit assets into an equivalent circuit that only contains matrices and vectors for calculation
        :param use_opf_vals:
        :param opf_time_series_results:
        :param logger:
        :return:
        """
        n = len(self.buses)
        m = len(self.branches)
        if self.time_profile is not None:
            n_time = len(self.time_profile)
        else:
            n_time = 0

        if use_opf_vals and opf_time_series_results is None:
            raise Exception('You want to use the OPF results but none is passed')

        self.bus_dictionary = dict()

        # Element count
        n_ld = 0
        n_ctrl_gen = 0
        n_sta_gen = 0
        n_batt = 0
        n_sh = 0
        for bus in self.buses:
            n_ld += len(bus.loads)
            n_ctrl_gen += len(bus.controlled_generators)
            n_sta_gen += len(bus.static_generators)
            n_batt += len(bus.batteries)
            n_sh += len(bus.shunts)

        # declare the numerical circuit
        circuit = NumericalCircuit(n_bus=n, n_br=m, n_ld=n_ld, n_gen=n_ctrl_gen,
                                   n_sta_gen=n_sta_gen, n_batt=n_batt, n_sh=n_sh,
                                   n_time=n_time, Sbase=self.Sbase)

        # set hte time array profile
        if n_time > 0:
            circuit.time_array = self.time_profile

        # compile the buses and the shunt devices
        i_ld = 0
        i_gen = 0
        i_sta_gen = 0
        i_batt = 0
        i_sh = 0
        self.bus_names = np.zeros(n, dtype=object)
        for i, bus in enumerate(self.buses):

            # bus parameters
            self.bus_names[i] = bus.name
            circuit.bus_names[i] = bus.name
            circuit.bus_vnom[i] = bus.Vnom  # kV
            circuit.Vmax[i] = bus.Vmax
            circuit.Vmin[i] = bus.Vmin
            circuit.bus_types[i] = bus.determine_bus_type().value[0]

            # Add buses dictionary entry
            self.bus_dictionary[bus] = i

            for elm in bus.loads:
                circuit.load_names[i_ld] = elm.name
                circuit.load_power[i_ld] = complex(elm.P, elm.Q)
                circuit.load_current[i_ld] = complex(elm.Ir, elm.Ii)
                circuit.load_admittance[i_ld] = complex(elm.G, elm.B)
                circuit.load_enabled[i_ld] = elm.active
                circuit.load_mttf[i_ld] = elm.mttf
                circuit.load_mttr[i_ld] = elm.mttr

                if n_time > 0:
                    circuit.load_power_profile[:, i_ld] = elm.P_prof.values[:, 0] + 1j * elm.Q_prof.values[:, 0]
                    circuit.load_current_profile[:, i_ld] = elm.Ir_prof.values[:, 0] + 1j * elm.Ii_prof.values[:, 0]
                    circuit.load_admittance_profile[:, i_ld] = elm.G_prof.values[:, 0] + 1j * elm.B_prof.values[:, 0]

                    if use_opf_vals:
                        # subtract the load shedding from the generation
                        circuit.load_power_profile[:, i_ld] -= opf_time_series_results.load_shedding[:, i_gen]

                circuit.C_load_bus[i_ld, i] = 1
                i_ld += 1

            for elm in bus.static_generators:
                circuit.static_gen_names[i_sta_gen] = elm.name
                circuit.static_gen_power[i_sta_gen] = complex(elm.P, elm.Q)
                circuit.static_gen_enabled[i_sta_gen] = elm.active
                circuit.static_gen_mttf[i_sta_gen] = elm.mttf
                circuit.static_gen_mttr[i_sta_gen] = elm.mttr
                # circuit.static_gen_dispatchable[i_sta_gen] = elm.enabled_dispatch

                if n_time > 0:
                    circuit.static_gen_power_profile[:, i_sta_gen] = elm.P_prof.values[:, 0] + 1j * elm.Q_prof.values[:, 0]

                circuit.C_sta_gen_bus[i_sta_gen, i] = 1
                i_sta_gen += 1

            for elm in bus.controlled_generators:
                circuit.generator_names[i_gen] = elm.name
                circuit.generator_power[i_gen] = elm.P
                circuit.generator_power_factor[i_gen] = elm.Pf
                circuit.generator_voltage[i_gen] = elm.Vset
                circuit.generator_qmin[i_gen] = elm.Qmin
                circuit.generator_qmax[i_gen] = elm.Qmax
                circuit.generator_pmin[i_gen] = elm.Pmin
                circuit.generator_pmax[i_gen] = elm.Pmax
                circuit.generator_enabled[i_gen] = elm.active
                circuit.generator_dispatchable[i_gen] = elm.enabled_dispatch
                circuit.generator_mttf[i_gen] = elm.mttf
                circuit.generator_mttr[i_gen] = elm.mttr

                if n_time > 0:
                    # power profile
                    if use_opf_vals:
                        circuit.generator_power_profile[:, i_gen] = \
                            opf_time_series_results.controlled_generator_power[:, i_gen]
                    else:
                        circuit.generator_power_profile[:, i_gen] = elm.P_prof.values[:, 0]

                    # Power factor profile
                    circuit.generator_power_factor_profile[:, i_gen] = elm.Pf_prof.values[:, 0]

                    # Voltage profile
                    circuit.generator_voltage_profile[:, i_gen] = elm.Vset_prof.values[:, 0]

                circuit.C_gen_bus[i_gen, i] = 1
                circuit.V0[i] *= elm.Vset
                i_gen += 1

            for elm in bus.batteries:
                # 'name', 'bus', 'active', 'P', 'Vset', 'Snom', 'Enom',
                # 'Qmin', 'Qmax', 'Pmin', 'Pmax', 'Cost', 'enabled_dispatch', 'mttf', 'mttr',
                # 'soc_0', 'max_soc', 'min_soc', 'charge_efficiency', 'discharge_efficiency'
                circuit.battery_names[i_batt] = elm.name
                circuit.battery_power[i_batt] = elm.P
                circuit.battery_voltage[i_batt] = elm.Vset
                circuit.battery_qmin[i_batt] = elm.Qmin
                circuit.battery_qmax[i_batt] = elm.Qmax
                circuit.battery_enabled[i_batt] = elm.active
                circuit.battery_dispatchable[i_batt] = elm.enabled_dispatch
                circuit.battery_mttf[i_batt] = elm.mttf
                circuit.battery_mttr[i_batt] = elm.mttr

                circuit.battery_pmin[i_batt] = elm.Pmin
                circuit.battery_pmax[i_batt] = elm.Pmax
                circuit.battery_Enom[i_batt] = elm.Enom
                circuit.battery_soc_0[i_batt] = elm.soc_0
                circuit.battery_discharge_efficiency[i_batt] = elm.discharge_efficiency
                circuit.battery_charge_efficiency[i_batt] = elm.charge_efficiency
                circuit.battery_min_soc[i_batt] = elm.min_soc
                circuit.battery_max_soc[i_batt] = elm.max_soc

                if n_time > 0:
                    # power profile
                    if use_opf_vals:
                        circuit.battery_power_profile[:, i_batt] = \
                            opf_time_series_results.battery_power[:, i_batt]
                    else:
                        circuit.battery_power_profile[:, i_batt] = elm.P_prof.values[:, 0]
                    # Voltage profile
                    circuit.battery_voltage_profile[:, i_batt] = elm.Vset_prof.values[:, 0]

                circuit.C_batt_bus[i_batt, i] = 1
                circuit.V0[i] *= elm.Vset
                i_batt += 1

            for elm in bus.shunts:
                circuit.shunt_names[i_sh] = elm.name
                circuit.shunt_admittance[i_sh] = complex(elm.G, elm.B)
                circuit.shunt_mttf[i_sh] = elm.mttf
                circuit.shunt_mttr[i_sh] = elm.mttr

                if n_time > 0:
                    circuit.shunt_admittance_profile[:, i_sh] = elm.G_prof.values[:, 0] + 1j * elm.B_prof.values[:, 0]

                circuit.C_shunt_bus[i_sh, i] = 1
                i_sh += 1

        # Compile the branches
        self.branch_names = np.zeros(m, dtype=object)
        for i, branch in enumerate(self.branches):

            self.branch_names[i] = branch.name
            f = self.bus_dictionary[branch.bus_from]
            t = self.bus_dictionary[branch.bus_to]

            # connectivity
            circuit.C_branch_bus_f[i, f] = 1
            circuit.C_branch_bus_t[i, t] = 1
            circuit.F[i] = f
            circuit.T[i] = t

            # name and state
            circuit.branch_names[i] = branch.name
            circuit.branch_states[i] = branch.active
            circuit.br_mttf[i] = branch.mttf
            circuit.br_mttr[i] = branch.mttr

            # impedance and tap
            circuit.R[i] = branch.R
            circuit.X[i] = branch.X
            circuit.G[i] = branch.G
            circuit.B[i] = branch.B
            circuit.impedance_tolerance[i] = branch.tolerance
            circuit.br_rates[i] = branch.rate
            circuit.tap_mod[i] = branch.tap_module
            circuit.tap_ang[i] = branch.angle

            # Thermal correction
            circuit.temp_base[i] = branch.temp_base
            circuit.temp_oper[i] = branch.temp_oper
            circuit.alpha[i] = branch.alpha

            # tap changer
            circuit.is_bus_to_regulated[i] = branch.bus_to_regulated
            circuit.tap_position[i] = branch.tap_changer.tap
            circuit.min_tap[i] = branch.tap_changer.min_tap
            circuit.max_tap[i] = branch.tap_changer.max_tap
            circuit.tap_inc_reg_up[i] = branch.tap_changer.inc_reg_up
            circuit.tap_inc_reg_down[i] = branch.tap_changer.inc_reg_down
            circuit.vset[i] = branch.vset

            # switches
            if branch.branch_type == BranchType.Switch:
                circuit.switch_indices.append(i)

            # virtual taps for transformers where the connection voltage is off
            elif branch.branch_type == BranchType.Transformer:
                circuit.tap_f[i], circuit.tap_t[i] = branch.get_virtual_taps()

        # Assign and return
        self.numerical_circuit = circuit
        return self.numerical_circuit

    def create_profiles(self, steps, step_length, step_unit, time_base: datetime = datetime.now()):
        """
        Set the default profiles in all the objects enabled to have profiles
        Args:
            steps: Number of time steps
            step_length: time length (1, 2, 15, ...)
            step_unit: unit of the time step
            time_base: Date to start from
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
        Format the pandas profiles in place using a time index
        Args:
            index: Time profile
        """

        self.time_profile = np.array(index)

        for bus in self.buses:

            for elm in bus.loads:
                elm.create_profiles(index)

            for elm in bus.static_generators:
                elm.create_profiles(index)

            for elm in bus.controlled_generators:
                elm.create_profiles(index)

            for elm in bus.batteries:
                elm.create_profiles(index)

            for elm in bus.shunts:
                elm.create_profiles(index)

    def get_node_elements_by_type(self, element_type):
        """
        Get set of elements and their parent nodes
        Args:
            element_type: String {'Load', 'StaticGenerator', 'Generator', 'Battery', 'Shunt'}

        Returns: List of elements, list of matching parent buses
        """
        elements = list()
        parent_buses = list()

        if element_type == 'Load':
            for bus in self.buses:
                for elm in bus.loads:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'StaticGenerator':
            for bus in self.buses:
                for elm in bus.static_generators:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'Generator':
            for bus in self.buses:
                for elm in bus.controlled_generators:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'Battery':
            for bus in self.buses:
                for elm in bus.batteries:
                    elements.append(elm)
                    parent_buses.append(bus)

        elif element_type == 'Shunt':
            for bus in self.buses:
                for elm in bus.shunts:
                    elements.append(elm)
                    parent_buses.append(bus)

        return elements, parent_buses

    def set_power(self, S):
        """
        Set the power array in the circuits
        @param S: Array of power values in MVA for all the nodes in all the islands
        """
        for circuit_island in self.circuits:
            idx = circuit_island.bus_original_idx  # get the buses original indexing in the island
            circuit_island.power_flow_input.Sbus = S[idx]  # set the values

    def add_bus(self, obj: Bus):
        """
        Add bus keeping track of it as object
        @param obj:
        """
        self.buses.append(obj)

    def delete_bus(self, obj: Bus):
        """
        Remove bus
        @param obj: Bus object
        """

        # remove associated branches in reverse order
        for i in range(len(self.branches) - 1, -1, -1):
            if self.branches[i].bus_from == obj or self.branches[i].bus_to == obj:
                self.branches.pop(i)

        # remove the bus itself
        self.buses.remove(obj)

    def add_branch(self, obj: Branch):
        """
        Add a branch object to the circuit
        @param obj: Branch object
        """
        self.branches.append(obj)

    def delete_branch(self, obj: Branch):
        """
        Delete a branch object from the circuit
        @param obj:
        """
        self.branches.remove(obj)

    def add_load(self, bus: Bus, api_obj=None):
        """
        Add load object to a bus
        Args:
            bus: Bus object
            api_obj: Load object
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
        Add controlled generator to a bus
        Args:
            bus: Bus object
            api_obj: Generator object
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
        Add a static generator object to a bus
        Args:
            bus: Bus object to add it to
            api_obj: StaticGenerator object
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
        Add battery object to a bus.

        Args:
            **bus** (Bus): Bus object to add it to

            **api_obj** (Battery, None): Battery object to add it to
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
        Add shunt object to a bus
        Args:
            bus: Bus object to add it to
            api_obj: Shunt object
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
        Add wire object
        :param obj: Wire object
        """
        self.wire_types.append(obj)

    def delete_wire(self, i):
        """
        Remove wire
        :param i: index
        """
        self.wire_types.pop(i)

    def add_overhead_line(self, obj: Tower):
        """
        Add overhead line
        :param obj: Tower object
        """
        self.overhead_line_types.append(obj)

    def delete_overhead_line(self, i):

        self.overhead_line_types.pop(i)

    def add_underground_line(self, obj: UndergroundLineType):

        self.underground_cable_types.append(obj)

    def delete_underground_line(self, i):

        self.underground_cable_types.pop(i)

    def add_sequence_line(self, obj: SequenceLineType):

        self.sequence_line_types.append(obj)

    def delete_sequence_line(self, i):

        self.sequence_line_types.pop(i)

    def add_transformer_type(self, obj: TransformerType):

        self.transformer_types.append(obj)

    def delete_transformer_type(self, i):

        self.transformer_types.pop(i)

    def apply_all_branch_types(self):
        """
        Apply all the branch types
        """
        logger = list()
        for branch in self.branches:
            branch.apply_template(branch.template, self.Sbase, logger=logger)

        return logger

    def plot_graph(self, ax=None):
        """
        Plot the grid
        @param ax: Matplotlib axis object
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        if self.graph is None:
            self.build_graph()

        nx.draw_spring(self.graph, ax=ax)

    def export_pf(self, file_name, power_flow_results):
        """
        Export power flow results to file
        :param file_name: Excel file name
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
        Export object profiles to file
        :param file_name: Excel file name
        :return: Nothing
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
                    P.append(elm.P_prof.values[:, 0])
                    Q.append(elm.Q_prof.values[:, 0])

                    Ir.append(elm.Ir_prof.values[:, 0])
                    Ii.append(elm.Ii_prof.values[:, 0])

                    G.append(elm.G_prof.values[:, 0])
                    B.append(elm.B_prof.values[:, 0])

                for elm in bus.controlled_generators:
                    gen_names.append(elm.name)

                    P_gen.append(elm.P_prof.values[:, 0])
                    V_gen.append(elm.Vset_prof.values[:, 0])

                for elm in bus.batteries:
                    bat_names.append(elm.name)
                    gen_names.append(elm.name)
                    P_gen.append(elm.P_prof.values[:, 0])
                    V_gen.append(elm.Vsetprof.values[:, 0])
                    E_batt.append(elm.energy_array.values[:, 0])

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

    def copy(self):
        """
        Returns a deep (true) copy of this circuit
        @return:
        """

        cpy = MultiCircuit()

        cpy.name = self.name

        bus_dict = dict()
        for bus in self.buses:
            bus_cpy = bus.copy()
            bus_dict[bus] = bus_cpy
            cpy.add_bus(bus_cpy)

        for branch in self.branches:
            cpy.add_branch(branch.copy(bus_dict))

        cpy.time_profile = self.time_profile

        return cpy

    def dispatch(self):
        """
        Dispatch either load or generation using a simple equalised share rule of the shedding to be done
        @return: Nothing
        """
        if self.numerical_circuit is not None:

            # get the total power balance
            balance = abs(self.numerical_circuit.Sbus.sum())

            if balance > 0:  # more generation than load, dispatch generation
                Gmax = 0
                Lt = 0
                for bus in self.buses:
                    for load in bus.loads:
                        Lt += abs(load.S)
                    for gen in bus.controlled_generators:
                        Gmax += abs(gen.Snom)

                # reassign load
                factor = Lt / Gmax
                print('Decreasing generation by ', factor * 100, '%')
                for bus in self.buses:
                    for gen in bus.controlled_generators:
                        gen.P *= factor

            elif balance < 0:  # more load than generation, dispatch load

                Gmax = 0
                Lt = 0
                for bus in self.buses:
                    for load in bus.loads:
                        Lt += abs(load.S)
                    for gen in bus.controlled_generators:
                        Gmax += abs(gen.P + 1j * gen.Qmax)

                # reassign load
                factor = Gmax / Lt
                print('Decreasing load by ', factor * 100, '%')
                for bus in self.buses:
                    for load in bus.loads:
                        load.S *= factor

            else:  # nothing to do
                pass

        else:
            warn('The grid must be compiled before dispatching it')

    def set_state(self, t):
        """
        Set the profiles state at the index t as the default values
        :param t:
        :return:
        """
        for bus in self.buses:
            bus.set_state(t)



