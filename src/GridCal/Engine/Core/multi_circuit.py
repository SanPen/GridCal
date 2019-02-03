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


def load_from_xls(filename):
    """
    Loads the excel file content to a dictionary for parsing the data
    """
    data = dict()
    xl = pd.ExcelFile(filename)
    names = xl.sheet_names

    # this dictionary sets the allowed excel sheets and the possible specific converter
    allowed_data_sheets = {'Conf': None,
                           'config': None,
                           'bus': None,
                           'branch': None,
                           'load': None,
                           'load_Sprof': complex,
                           'load_Iprof': complex,
                           'load_Zprof': complex,
                           'load_P_prof': float,
                           'load_Q_prof': float,
                           'load_Ir_prof': float,
                           'load_Ii_prof': float,
                           'load_G_prof': float,
                           'load_B_prof': float,
                           'static_generator': None,
                           'static_generator_Sprof': complex,
                           'static_generator_P_prof': complex,
                           'static_generator_Q_prof': complex,
                           'battery': None,
                           'battery_Vset_profiles': float,
                           'battery_P_profiles': float,
                           'battery_Vset_prof': float,
                           'battery_P_prof': float,
                           'controlled_generator': None,
                           'CtrlGen_Vset_profiles': float,
                           'CtrlGen_P_profiles': float,
                           'generator': None,
                           'generator_Vset_prof': float,
                           'generator_P_prof': float,
                           'generator_Pf_prof': float,
                           'shunt': None,
                           'shunt_Y_profiles': complex,
                           'shunt_G_prof': float,
                           'shunt_B_prof': float,
                           'wires': None,
                           'overhead_line_types': None,
                           'underground_cable_types': None,
                           'sequence_line_types': None,
                           'transformer_types': None}

    # check the validity of this excel file
    for name in names:
        if name not in allowed_data_sheets.keys():
            raise Exception('The file sheet ' + name + ' is not allowed.\n'
                            'Did you create this file manually? Use GridCal instead.')

    # parse the file
    if 'Conf' in names:  # version 1

        data["version"] = 1.0

        for name in names:

            if name.lower() == "conf":
                df = xl.parse(name)
                data["baseMVA"] = np.double(df.values[0, 1])

            elif name.lower() == "bus":
                df = xl.parse(name)
                data["bus"] = np.nan_to_num(df.values)
                if len(df) > 0:
                    if df.index.values.tolist()[0] != 0:
                        data['bus_names'] = df.index.values.tolist()

            elif name.lower() == "gen":
                df = xl.parse(name)
                data["gen"] = np.nan_to_num(df.values)
                if len(df) > 0:
                    if df.index.values.tolist()[0] != 0:
                        data['gen_names'] = df.index.values.tolist()

            elif name.lower() == "branch":
                df = xl.parse(name)
                data["branch"] = np.nan_to_num(df.values)
                if len(df) > 0:
                    if df.index.values.tolist()[0] != 0:
                        data['branch_names'] = df.index.values.tolist()

            elif name.lower() == "storage":
                df = xl.parse(name)
                data["storage"] = np.nan_to_num(df.values)
                if len(df) > 0:
                    if df.index.values.tolist()[0] != 0:
                        data['storage_names'] = df.index.values.tolist()

            elif name.lower() == "lprof":
                df = xl.parse(name, index_col=0)
                data["Lprof"] = np.nan_to_num(df.values)
                data["master_time"] = df.index

            elif name.lower() == "lprofq":
                df = xl.parse(name, index_col=0)
                data["LprofQ"] = np.nan_to_num(df.values)
                # ppc["master_time"] = df.index.values

            elif name.lower() == "gprof":
                df = xl.parse(name, index_col=0)
                data["Gprof"] = np.nan_to_num(df.values)
                data["master_time"] = df.index  # it is the same

    elif 'config' in names:  # version 2

        for name in names:

            if name.lower() == "config":
                df = xl.parse('config', index_col=0)
                idx = df['Property'][df['Property'] == 'BaseMVA'].index
                if len(idx) > 0:
                    data["baseMVA"] = np.double(df.values[idx, 1])
                else:
                    data["baseMVA"] = 100

                idx = df['Property'][df['Property'] == 'Version'].index
                if len(idx) > 0:
                    data["version"] = np.double(df.values[idx, 1])

                idx = df['Property'][df['Property'] == 'Name'].index
                if len(idx) > 0:
                    data["name"] = df.values[idx[0], 1]
                else:
                    data["name"] = 'Grid'

                idx = df['Property'][df['Property'] == 'Comments'].index
                if len(idx) > 0:
                    data["Comments"] = df.values[idx[0], 1]
                else:
                    data["Comments"] = ''

            else:
                # just pick the DataFrame
                df = xl.parse(name, index_col=0)

                if allowed_data_sheets[name] == complex:
                    # pandas does not read complex numbers right,
                    # so when we expect a complex number input, parse directly
                    for c in df.columns.values:
                        df[c] = df[c].apply(lambda x: np.complex(x))

                data[name] = df

    else:
        raise Exception('This excel file is not in GridCal Format')

    return data


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

        # #  containing the power flow results
        # self.power_flow_results = None
        #
        # # containing the short circuit results
        # self.short_circuit_results = None
        #
        # # Object with the necessary inputs for th time series simulation
        # self.time_series_input = None
        #
        # # Object with the time series simulation results
        # self.time_series_results = None
        #
        # # Monte Carlo input object
        # self.monte_carlo_input = None
        #
        # # Monte Carlo time series batch
        # self.mc_time_series = None

        # Bus-Branch graph
        self.graph = None

        # self.power_flow_results = PowerFlowResults()

        self.bus_dictionary = dict()

        self.branch_dictionary = dict()

        self.has_time_series = False

        self.bus_names = None

        self.branch_names = None

        self.time_profile = None

        self.objects_with_profiles = [Load(), StaticGenerator(), Generator(), Battery(), Shunt()]

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

    def load_file(self, filename):
        """
        Load GridCal compatible file
        @param filename:
        @return:
        """
        logger = list()

        if os.path.exists(filename):
            name, file_extension = os.path.splitext(filename)
            # print(name, file_extension)
            if file_extension.lower() in ['.xls', '.xlsx']:

                data_dictionary = load_from_xls(filename)

                # Pass the table-like data dictionary to objects in this circuit
                if 'version' not in data_dictionary.keys():
                    from GridCal.Engine.Importers.matpower_parser import interpret_data_v1
                    interpret_data_v1(self, data_dictionary)
                    return logger
                elif data_dictionary['version'] == 2.0:
                    self.interprete_excel_v2(data_dictionary)
                    return logger
                elif data_dictionary['version'] == 3.0:
                    self.interpret_excel_v3(data_dictionary)
                    return logger
                else:
                    warn('The file could not be processed')
                    return logger

            elif file_extension.lower() == '.dgs':
                from GridCal.Engine.Importers.dgs_parser import dgs_to_circuit
                circ = dgs_to_circuit(filename)
                self.buses = circ.buses
                self.branches = circ.branches
                self.assign_circuit(circ)

            elif file_extension.lower() == '.m':
                from GridCal.Engine.Importers.matpower_parser import parse_matpower_file
                circ = parse_matpower_file(filename)
                self.buses = circ.buses
                self.branches = circ.branches
                self.assign_circuit(circ)

            elif file_extension.lower() == '.dpx':
                from GridCal.Engine.Importers.dpx_parser import load_dpx
                circ, logger = load_dpx(filename)
                self.buses = circ.buses
                self.branches = circ.branches
                self.assign_circuit(circ)

            elif file_extension.lower() == '.json':

                # the json file can be the GridCAl one or the iPA one...
                data = json.load(open(filename))

                if type(data) == dict():
                    if 'Red' in data.keys():
                        from GridCal.Engine.Importers.ipa_parser import load_iPA
                        circ = load_iPA(filename)
                        self.buses = circ.buses
                        self.branches = circ.branches
                        self.assign_circuit(circ)
                    else:
                        logger.append('Unknown json format')

                elif type(data) == list():
                    from GridCal.Engine.Importers.json_parser import parse_json
                    circ = parse_json(filename)
                    self.buses = circ.buses
                    self.branches = circ.branches
                    self.assign_circuit(circ)
                else:
                    logger.append('Unknown json format')

            elif file_extension.lower() == '.raw':
                from GridCal.Engine.Importers.psse_parser import PSSeParser
                parser = PSSeParser(filename)
                circ = parser.circuit
                self.buses = circ.buses
                self.branches = circ.branches
                self.assign_circuit(circ)
                logger = parser.logger

            elif file_extension.lower() == '.xml':
                from GridCal.Engine.Importers.cim_parser import CIMImport
                parser = CIMImport()
                circ = parser.load_cim_file(filename)
                self.assign_circuit(circ)
                logger = parser.logger

        else:
            warn('The file does not exist.')
            logger.append(filename + ' does not exist.')

        return logger

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

    def interprete_excel_v2(self, data):
        """
        Interpret the new file version
        Args:
            data: Dictionary with the excel file sheet labels and the corresponding DataFrame

        Returns: Nothing, just applies the loaded data to this MultiCircuit instance

        """
        # print('Interpreting V2 data...')

        # clear all the data
        self.clear()

        self.name = data['name']

        # set the base magnitudes
        self.Sbase = data['baseMVA']

        # dictionary of branch types [name] -> type object
        branch_types = dict()

        # Set comments
        self.comments = data['Comments'] if 'Comments' in data.keys() else ''

        self.time_profile = None

        self.logger = list()

        # common function
        def set_object_attributes(obj_, attr_list, values):
            for a, attr in enumerate(attr_list):

                # Hack to change the enabled by active...
                if attr == 'is_enabled':
                    attr = 'active'

                if attr == 'type_obj':
                    attr = 'template'

                if hasattr(obj_, attr):
                    conv = obj_.editable_headers[attr][1]  # get the type converter
                    if conv is None:
                        setattr(obj_, attr, values[a])
                    elif conv is BranchType:
                        cbr = BranchTypeConverter(None)
                        setattr(obj_, attr, cbr(values[a]))
                    else:
                        setattr(obj_, attr, conv(values[a]))
                else:

                    if attr in ['Y', 'Z', 'I', 'S', 'seq_resistance', 'seq_admittance', 'Zf']:

                        if attr == 'Z':
                            val = complex(values[a])
                            re = 1 / val.real if val.real != 0.0 else 0
                            im = 1 / val.imag if val.imag != 0.0 else 0
                            setattr(obj_, 'G', re)
                            setattr(obj_, 'B', im)

                        if attr == 'Zf':
                            val = complex(values[a])
                            re = 1 / val.real if val.real != 0.0 else 0
                            im = 1 / val.imag if val.imag != 0.0 else 0
                            setattr(obj_, 'r_fault', re)
                            setattr(obj_, 'x_fault', im)

                        if attr == 'Y':
                            val = complex(values[a])
                            re = val.real
                            im = val.imag
                            setattr(obj_, 'G', re)
                            setattr(obj_, 'B', im)

                        elif attr == 'I':
                            val = complex(values[a])
                            setattr(obj_, 'Ir', val.real)
                            setattr(obj_, 'Ii', val.imag)

                        elif attr == 'S':
                            val = complex(values[a])
                            setattr(obj_, 'P', val.real)
                            setattr(obj_, 'Q', val.imag)

                        elif attr == 'seq_resistance':
                            val = complex(values[a])
                            setattr(obj_, 'R1', val.real)
                            setattr(obj_, 'X1', val.imag)

                        elif attr == 'seq_admittance':
                            val = complex(values[a])
                            setattr(obj_, 'Gsh1', val.real)
                            setattr(obj_, 'Bsh1', val.imag)

                    else:
                        warn(str(obj_) + ' has no ' + attr + ' property.')

        # Add the buses ################################################################################################
        bus_dict = dict()
        if 'bus' in data.keys():
            lst = data['bus']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = Bus()
                set_object_attributes(obj, hdr, vals[i, :])
                bus_dict[obj.name] = obj
                self.add_bus(obj)
        else:
            self.logger.append('No buses in the file!')

        # add the loads ################################################################################################
        if 'load' in data.keys():
            lst = data['load']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = Load()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'load_Sprof' in data.keys():

                    idx = data['load_Sprof'].index

                    # create all the profiles
                    obj.create_profiles(index=idx)

                    # create the power profiles
                    val = np.array([complex(v) for v in data['load_Sprof'].values[:, i]])
                    obj.P_prof = pd.DataFrame(data=val.real, index=idx)
                    obj.Q_prof = pd.DataFrame(data=val.imag, index=idx)
                    if self.time_profile is None:
                        self.time_profile = idx

                if 'load_Iprof' in data.keys():
                    val = np.array([complex(v) for v in data['load_Iprof'].values[:, i]])
                    idx = data['load_Iprof'].index
                    obj.Ir_prof = pd.DataFrame(data=val.real, index=idx)
                    obj.Ii_prof = pd.DataFrame(data=val.imag, index=idx)

                    if self.time_profile is None:
                        self.time_profile = idx

                if 'load_Zprof' in data.keys():
                    val = np.array([complex(v) for v in data['load_Zprof'].values[:, i]])
                    idx = data['load_Zprof'].index
                    obj.Ir_prof = pd.DataFrame(data=val.real, index=idx)
                    obj.Ii_prof = pd.DataFrame(data=val.imag, index=idx)

                    if self.time_profile is None:
                        self.time_profile = idx

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Load bus is not in the buses list.\n' + str(ex))

                if obj.name == 'Load':
                    obj.name += str(len(bus.loads) + 1) + '@' + bus.name

                obj.bus = bus
                bus.loads.append(obj)
                obj.ensure_profiles_exist(self.time_profile)
        else:
            self.logger.append('No loads in the file!')

        # add the controlled generators ################################################################################
        if 'controlled_generator' in data.keys():
            lst = data['controlled_generator']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = Generator()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'CtrlGen_P_profiles' in data.keys():
                    val = data['CtrlGen_P_profiles'].values[:, i]
                    idx = data['CtrlGen_P_profiles'].index
                    obj.create_P_profile(index=idx, arr=val)
                    # also create the Pf array because there might not be values in the file
                    obj.create_Pf_profile(index=idx)

                if 'CtrlGen_Pf_profiles' in data.keys():
                    val = data['CtrlGen_Pf_profiles'].values[:, i]
                    idx = data['CtrlGen_Pf_profiles'].index
                    # obj.Pprof = pd.DataFrame(data=val, index=idx)
                    obj.create_Pf_profile(index=idx, arr=val)

                if 'CtrlGen_Vset_profiles' in data.keys():
                    val = data['CtrlGen_Vset_profiles'].values[:, i]
                    idx = data['CtrlGen_Vset_profiles'].index
                    obj.Vset_prof = pd.DataFrame(data=val, index=idx)

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Controlled generator bus is not in the buses list.\n' + str(ex))

                if obj.name == 'gen':
                    obj.name += str(len(bus.controlled_generators) + 1) + '@' + bus.name

                obj.bus = bus
                bus.controlled_generators.append(obj)
                obj.ensure_profiles_exist(self.time_profile)
        else:
            self.logger.append('No controlled generator in the file!')

        # add the batteries ############################################################################################
        if 'battery' in data.keys():
            lst = data['battery']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = Battery()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'battery_P_profiles' in data.keys():
                    val = data['battery_P_profiles'].values[:, i]
                    idx = data['battery_P_profiles'].index
                    # obj.Pprof = pd.DataFrame(data=val, index=idx)
                    obj.create_P_profile(index=idx, arr=val)

                if 'battery_Vset_profiles' in data.keys():
                    val = data['battery_Vset_profiles'].values[:, i]
                    idx = data['battery_Vset_profiles'].index
                    obj.Vset_prof = pd.DataFrame(data=val, index=idx)

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Battery bus is not in the buses list.\n' + str(ex))

                if obj.name == 'batt':
                    obj.name += str(len(bus.batteries) + 1) + '@' + bus.name

                obj.bus = bus
                bus.batteries.append(obj)
                obj.ensure_profiles_exist(self.time_profile)
        else:
            self.logger.append('No battery in the file!')

        # add the static generators ####################################################################################
        if 'static_generator' in data.keys():
            lst = data['static_generator']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = StaticGenerator()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'static_generator_Sprof' in data.keys():
                    val = data['static_generator_Sprof'].values[:, i]
                    idx = data['static_generator_Sprof'].index
                    # obj.Sprof = pd.DataFrame(data=val, index=idx)
                    obj.P_prof = pd.DataFrame(data=val.real, index=idx)
                    obj.Q_prof = pd.DataFrame(data=val.imag, index=idx)

                if 'static_generator_P_prof' in data.keys():
                    val = data['static_generator_P_prof'].values[:, i]
                    idx = data['static_generator_P_prof'].index
                    obj.P_prof = pd.DataFrame(data=val, index=idx)

                if 'static_generator_Q_prof' in data.keys():
                    val = data['static_generator_Q_prof'].values[:, i]
                    idx = data['static_generator_Q_prof'].index
                    obj.Q_prof = pd.DataFrame(data=val, index=idx)

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Static generator bus is not in the buses list.\n' + str(ex))

                if obj.name == 'StaticGen':
                    obj.name += str(len(bus.static_generators) + 1) + '@' + bus.name

                obj.bus = bus
                bus.static_generators.append(obj)
                obj.ensure_profiles_exist(self.time_profile)
        else:
            self.logger.append('No static generator in the file!')

        # add the shunts ###############################################################################################
        if 'shunt' in data.keys():
            lst = data['shunt']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = Shunt()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'shunt_Y_profiles' in data.keys():
                    val = data['shunt_Y_profiles'].values[:, i]
                    idx = data['shunt_Y_profiles'].index
                    # obj.Yprof = pd.DataFrame(data=val, index=idx)
                    obj.G_prof = pd.DataFrame(data=val.real, index=idx)
                    obj.B_prof = pd.DataFrame(data=val.imag, index=idx)
                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Shunt bus is not in the buses list.\n' + str(ex))

                if obj.name == 'shunt':
                    obj.name += str(len(bus.shunts) + 1) + '@' + bus.name

                obj.bus = bus
                bus.shunts.append(obj)
                obj.ensure_profiles_exist(self.time_profile)
        else:
            self.logger.append('No shunt in the file!')

        # Add the wires ################################################################################################
        if 'wires' in data.keys():
            lst = data['wires']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = Wire()
                set_object_attributes(obj, hdr, vals[i, :])
                self.add_wire(obj)
        else:
            self.logger.append('No wires in the file!')

        # Add the overhead_line_types ##################################################################################
        if 'overhead_line_types' in data.keys():
            lst = data['overhead_line_types']
            if data['overhead_line_types'].values.shape[0] > 0:
                for tower_name in lst['tower_name'].unique():
                    obj = Tower()
                    vals = lst[lst['tower_name'] == tower_name].values

                    # set the tower values
                    set_object_attributes(obj, obj.editable_headers.keys(), vals[0, :])

                    # add the wires
                    for i in range(vals.shape[0]):
                        wire = Wire()
                        set_object_attributes(wire, obj.get_wire_properties(), vals[i, len(obj.editable_headers):])
                        obj.wires.append(wire)

                    self.add_overhead_line(obj)
                    branch_types[str(obj)] = obj
            else:
                pass
        else:
            self.logger.append('No overhead_line_types in the file!')

        # Add the wires ################################################################################################
        if 'underground_cable_types' in data.keys():
            lst = data['underground_cable_types']
            hdr = lst.columns.values
            vals = lst.values
            # for i in range(len(lst)):
            #     obj = UndergroundLineType()
            #     set_object_attributes(obj, hdr, vals[i, :])
            #     self.underground_cable_types.append(obj)
            #     branch_types[str(obj)] = obj
        else:
            self.logger.append('No underground_cable_types in the file!')

        # Add the sequence line types ##################################################################################
        if 'sequence_line_types' in data.keys():
            lst = data['sequence_line_types']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = SequenceLineType()
                set_object_attributes(obj, hdr, vals[i, :])
                self.add_sequence_line(obj)
                branch_types[str(obj)] = obj
        else:
            self.logger.append('No sequence_line_types in the file!')

        # Add the transformer types ####################################################################################
        if 'transformer_types' in data.keys():
            lst = data['transformer_types']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = TransformerType()
                set_object_attributes(obj, hdr, vals[i, :])
                self.add_transformer_type(obj)
                branch_types[str(obj)] = obj
        else:
            self.logger.append('No transformer_types in the file!')

        # Add the branches #############################################################################################
        if 'branch' in data.keys():
            lst = data['branch']

            # fix the old 'is_transformer' property
            if 'is_transformer' in lst.columns.values:
                lst['is_transformer'] = lst['is_transformer'].map({True: 'transformer', False: 'line'})
                lst.rename(columns={'is_transformer': 'branch_type'}, inplace=True)

            bus_from = lst['bus_from'].values
            bus_to = lst['bus_to'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus_from'))
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus_to'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                try:
                    obj = Branch(bus_from=bus_dict[str(bus_from[i])], bus_to=bus_dict[str(bus_to[i])])
                except KeyError as ex:
                    raise Exception(str(i) + ': Branch bus is not in the buses list.\n' + str(ex))

                set_object_attributes(obj, hdr, vals[i, :])

                # correct the branch template object
                template_name = str(obj.template)
                if template_name in branch_types.keys():
                    obj.template = branch_types[template_name]
                    print(template_name, 'updtaed!')

                # set the branch
                self.add_branch(obj)

        else:
            self.logger.append('No branches in the file!')

        # Other actions ################################################################################################
        self.logger += self.apply_all_branch_types()

    def interpret_excel_v3(self, data):
        """
        Interpret the file version 3
        In this file version there are no complex numbers saved
        Args:
            data: Dictionary with the excel file sheet labels and the corresponding DataFrame

        Returns: Nothing, just applies the loaded data to this MultiCircuit instance

        """
        # print('Interpreting V2 data...')

        # clear all the data
        self.clear()

        self.name = data['name']

        # set the base magnitudes
        self.Sbase = data['baseMVA']

        # dictionary of branch types [name] -> type object
        branch_types = dict()

        # Set comments
        self.comments = data['Comments'] if 'Comments' in data.keys() else ''

        self.time_profile = None

        self.logger = list()

        # common function
        def set_object_attributes(obj_, attr_list, values):
            for a, attr in enumerate(attr_list):

                # Hack to change the enabled by active...
                if attr == 'is_enabled':
                    attr = 'active'

                if attr == 'type_obj':
                    attr = 'template'

                if hasattr(obj_, attr):
                    conv = obj_.editable_headers[attr][1]  # get the type converter
                    if conv is None:
                        setattr(obj_, attr, values[a])
                    elif conv is BranchType:
                        cbr = BranchTypeConverter(None)
                        setattr(obj_, attr, cbr(values[a]))
                    else:
                        setattr(obj_, attr, conv(values[a]))
                else:
                    warn(str(obj_) + ' has no ' + attr + ' property.')

        # Add the buses ################################################################################################
        bus_dict = dict()
        if 'bus' in data.keys():
            lst = data['bus']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = Bus()
                set_object_attributes(obj, hdr, vals[i, :])
                bus_dict[obj.name] = obj
                self.add_bus(obj)
        else:
            self.logger.append('No buses in the file!')

        # add the loads ################################################################################################
        if 'load' in data.keys():
            lst = data['load']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values

            profles_attr = {'load_P_prof': 'P_prof',
                            'load_Q_prof': 'Q_prof',
                            'load_Ir_prof': 'Ir_prof',
                            'load_Ii_prof': 'Ii_prof',
                            'load_G_prof': 'G_prof',
                            'load_B_prof': 'B_prof'}

            for i in range(len(lst)):
                obj = Load()
                set_object_attributes(obj, hdr, vals[i, :])

                # parse profiles:
                for sheet_name, load_attr in profles_attr.items():
                    if sheet_name in data.keys():
                        val = data[sheet_name].values[:, i]
                        idx = data[sheet_name].index
                        setattr(obj, load_attr, pd.DataFrame(data=val, index=idx))

                        if self.time_profile is None:
                            self.time_profile = idx

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Load bus is not in the buses list.\n' + str(ex))

                if obj.name == 'Load':
                    obj.name += str(len(bus.loads) + 1) + '@' + bus.name

                obj.bus = bus
                bus.loads.append(obj)
                obj.ensure_profiles_exist(self.time_profile)
        else:
            self.logger.append('No loads in the file!')

        # add the controlled generators ################################################################################
        if 'generator' in data.keys():
            lst = data['generator']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = Generator()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'generator_P_prof' in data.keys():
                    val = data['generator_P_prof'].values[:, i]
                    idx = data['generator_P_prof'].index
                    obj.create_P_profile(index=idx, arr=val)
                    # also create the Pf array because there might not be values in the file
                    obj.create_Pf_profile(index=idx)

                if 'generator_Pf_prof' in data.keys():
                    val = data['generator_Pf_prof'].values[:, i]
                    idx = data['generator_Pf_prof'].index
                    # obj.Pprof = pd.DataFrame(data=val, index=idx)
                    obj.create_Pf_profile(index=idx, arr=val)

                if 'generator_Vset_prof' in data.keys():
                    val = data['generator_Vset_prof'].values[:, i]
                    idx = data['generator_Vset_prof'].index
                    obj.Vset_prof = pd.DataFrame(data=val, index=idx)

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Controlled generator bus is not in the buses list.\n' + str(ex))

                if obj.name == 'gen':
                    obj.name += str(len(bus.controlled_generators) + 1) + '@' + bus.name

                obj.bus = bus
                bus.controlled_generators.append(obj)
                obj.ensure_profiles_exist(self.time_profile)
        else:
            self.logger.append('No controlled generator in the file!')

        # add the batteries ############################################################################################
        if 'battery' in data.keys():
            lst = data['battery']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = Battery()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'battery_P_prof' in data.keys():
                    val = data['battery_P_prof'].values[:, i]
                    idx = data['battery_P_prof'].index
                    # obj.Pprof = pd.DataFrame(data=val, index=idx)
                    obj.create_P_profile(index=idx, arr=val)

                if 'battery_Vset_prof' in data.keys():
                    val = data['battery_Vset_prof'].values[:, i]
                    idx = data['battery_Vset_prof'].index
                    obj.Vset_prof = pd.DataFrame(data=val, index=idx)

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Battery bus is not in the buses list.\n' + str(ex))

                if obj.name == 'batt':
                    obj.name += str(len(bus.batteries) + 1) + '@' + bus.name

                obj.bus = bus
                bus.batteries.append(obj)
                obj.ensure_profiles_exist(self.time_profile)
        else:
            self.logger.append('No battery in the file!')

        # add the static generators ####################################################################################
        if 'static_generator' in data.keys():
            lst = data['static_generator']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = StaticGenerator()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'static_generator_Sprof' in data.keys():
                    val = data['static_generator_Sprof'].values[:, i]
                    idx = data['static_generator_Sprof'].index
                    obj.P_prof = pd.DataFrame(data=val.real, index=idx)
                    obj.Q_prof = pd.DataFrame(data=val.imag, index=idx)

                if 'static_generator_P_prof' in data.keys():
                    val = data['static_generator_P_prof'].values[:, i]
                    idx = data['static_generator_P_prof'].index
                    obj.P_prof = pd.DataFrame(data=val, index=idx)

                if 'static_generator_Q_prof' in data.keys():
                    val = data['static_generator_Q_prof'].values[:, i]
                    idx = data['static_generator_Q_prof'].index
                    obj.P_prof = pd.DataFrame(data=val, index=idx)

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Static generator bus is not in the buses list.\n' + str(ex))

                if obj.name == 'StaticGen':
                    obj.name += str(len(bus.static_generators) + 1) + '@' + bus.name

                obj.bus = bus
                bus.static_generators.append(obj)
                obj.ensure_profiles_exist(self.time_profile)
        else:
            self.logger.append('No static generator in the file!')

        # add the shunts ###############################################################################################
        if 'shunt' in data.keys():
            lst = data['shunt']
            bus_from = lst['bus'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                obj = Shunt()
                set_object_attributes(obj, hdr, vals[i, :])

                if 'shunt_Y_profiles' in data.keys():
                    val = data['shunt_Y_profiles'].values[:, i]
                    idx = data['shunt_Y_profiles'].index
                    obj.G_prof = pd.DataFrame(data=val.real, index=idx)
                    obj.B_prof = pd.DataFrame(data=val.imag, index=idx)

                if 'shunt_G_prof' in data.keys():
                    val = data['shunt_G_prof'].values[:, i]
                    idx = data['shunt_G_prof'].index
                    obj.G_prof = pd.DataFrame(data=val, index=idx)

                if 'shunt_B_prof' in data.keys():
                    val = data['shunt_B_prof'].values[:, i]
                    idx = data['shunt_B_prof'].index
                    obj.B_prof = pd.DataFrame(data=val, index=idx)

                try:
                    bus = bus_dict[str(bus_from[i])]
                except KeyError as ex:
                    raise Exception(str(i) + ': Shunt bus is not in the buses list.\n' + str(ex))

                if obj.name == 'shunt':
                    obj.name += str(len(bus.shunts) + 1) + '@' + bus.name

                obj.bus = bus
                bus.shunts.append(obj)
                obj.ensure_profiles_exist(self.time_profile)
        else:
            self.logger.append('No shunt in the file!')

        # Add the wires ################################################################################################
        if 'wires' in data.keys():
            lst = data['wires']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = Wire()
                set_object_attributes(obj, hdr, vals[i, :])
                self.add_wire(obj)
        else:
            self.logger.append('No wires in the file!')

        # Add the overhead_line_types ##################################################################################
        if 'overhead_line_types' in data.keys():
            lst = data['overhead_line_types']
            if data['overhead_line_types'].values.shape[0] > 0:
                for tower_name in lst['tower_name'].unique():
                    obj = Tower()
                    vals = lst[lst['tower_name'] == tower_name].values

                    # set the tower values
                    set_object_attributes(obj, obj.editable_headers.keys(), vals[0, :])

                    # add the wires
                    for i in range(vals.shape[0]):
                        wire = Wire()
                        set_object_attributes(wire, obj.get_wire_properties(), vals[i, len(obj.editable_headers):])
                        obj.wires.append(wire)

                    self.add_overhead_line(obj)
                    branch_types[str(obj)] = obj
            else:
                pass
        else:
            self.logger.append('No overhead_line_types in the file!')

        # Add the wires ################################################################################################
        if 'underground_cable_types' in data.keys():
            lst = data['underground_cable_types']
            hdr = lst.columns.values
            vals = lst.values
            # for i in range(len(lst)):
            #     obj = UndergroundLineType()
            #     set_object_attributes(obj, hdr, vals[i, :])
            #     self.underground_cable_types.append(obj)
            #     branch_types[str(obj)] = obj
        else:
            self.logger.append('No underground_cable_types in the file!')

        # Add the sequence line types ##################################################################################
        if 'sequence_line_types' in data.keys():
            lst = data['sequence_line_types']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = SequenceLineType()
                set_object_attributes(obj, hdr, vals[i, :])
                self.add_sequence_line(obj)
                branch_types[str(obj)] = obj
        else:
            self.logger.append('No sequence_line_types in the file!')

        # Add the transformer types ####################################################################################
        if 'transformer_types' in data.keys():
            lst = data['transformer_types']
            hdr = lst.columns.values
            vals = lst.values
            for i in range(len(lst)):
                obj = TransformerType()
                set_object_attributes(obj, hdr, vals[i, :])
                self.add_transformer_type(obj)
                branch_types[str(obj)] = obj
        else:
            self.logger.append('No transformer_types in the file!')

        # Add the branches #############################################################################################
        if 'branch' in data.keys():
            lst = data['branch']

            # fix the old 'is_transformer' property
            if 'is_transformer' in lst.columns.values:
                lst['is_transformer'] = lst['is_transformer'].map({True: 'transformer', False: 'line'})
                lst.rename(columns={'is_transformer': 'branch_type'}, inplace=True)

            bus_from = lst['bus_from'].values
            bus_to = lst['bus_to'].values
            hdr = lst.columns.values
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus_from'))
            hdr = np.delete(hdr, np.argwhere(hdr == 'bus_to'))
            vals = lst[hdr].values
            for i in range(len(lst)):
                try:
                    obj = Branch(bus_from=bus_dict[str(bus_from[i])], bus_to=bus_dict[str(bus_to[i])])
                except KeyError as ex:
                    raise Exception(str(i) + ': Branch bus is not in the buses list.\n' + str(ex))

                set_object_attributes(obj, hdr, vals[i, :])

                # correct the branch template object
                template_name = str(obj.template)
                if template_name in branch_types.keys():
                    obj.template = branch_types[template_name]
                    print(template_name, 'updtaed!')

                # set the branch
                self.add_branch(obj)

        else:
            self.logger.append('No branches in the file!')

        # Other actions ################################################################################################
        self.logger += self.apply_all_branch_types()

    def save_file(self, file_path):
        """
        Save File
        :param file_path:
        :return:
        """

        if file_path.endswith('.xlsx'):
            logger = self.save_excel(file_path)
        elif file_path.endswith('.json'):
            logger = self.save_json(file_path)
        elif file_path.endswith('.xml'):
            logger = self.save_cim(file_path)
        else:
            logger = list()
            logger.append('File path extension not understood\n' + file_path)

        return logger

    def save_excel(self, file_path):
        """
        Save the circuit information
        :param file_path: file path to save
        :return:
        """
        logger = list()

        dfs = dict()

        # configuration ################################################################################################
        obj = list()
        obj.append(['BaseMVA', self.Sbase])
        obj.append(['Version', 3])
        obj.append(['Name', self.name])
        obj.append(['Comments', self.comments])
        dfs['config'] = pd.DataFrame(data=obj, columns=['Property', 'Value'])

        # get the master time profile
        T = self.time_profile

        # buses ########################################################################################################
        obj = list()
        names_count = dict()
        headers = Bus().editable_headers.keys()
        if len(self.buses) > 0:
            for elm in self.buses:

                # check name: if the name is repeated, change it so that it is not
                if elm.name in names_count.keys():
                    names_count[elm.name] += 1
                    elm.name = elm.name + '_' + str(names_count[elm.name])
                else:
                    names_count[elm.name] = 1

                elm.retrieve_graphic_position()

                obj.append(elm.get_save_data())

            dta = np.array(obj)
        else:
            dta = np.zeros((0, len(headers)))

        dfs['bus'] = pd.DataFrame(data=dta, columns=headers)

        # branches #####################################################################################################
        headers = Branch(None, None).editable_headers.keys()
        if len(self.branches) > 0:
            obj = list()
            for elm in self.branches:
                obj.append(elm.get_save_data())

            dta = np.array(obj)
        else:
            dta = np.zeros((0, len(headers)))

        dfs['branch'] = pd.DataFrame(data=dta, columns=headers)

        # loads ########################################################################################################
        headers = Load().editable_headers.keys()
        loads = self.get_loads()
        if len(loads) > 0:
            obj = list()
            p_profiles = None
            q_profiles = None
            ir_profiles = None
            ii_profiles = None
            g_profiles = None
            b_profiles = None
            hdr = list()
            for elm in loads:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None:
                    if p_profiles is None and elm.P_prof is not None:
                        p_profiles = elm.P_prof.values
                        q_profiles = elm.Q_prof.values
                        ir_profiles = elm.Ir_prof.values
                        ii_profiles = elm.Ii_prof.values
                        g_profiles = elm.G_prof.values
                        b_profiles = elm.B_prof.values
                    else:
                        p_profiles = np.c_[p_profiles, elm.P_prof.values]
                        q_profiles = np.c_[q_profiles, elm.Q_prof.values]
                        ir_profiles = np.c_[ir_profiles, elm.Ir_prof.values]
                        ii_profiles = np.c_[ii_profiles, elm.Ii_prof.values]
                        g_profiles = np.c_[g_profiles, elm.G_prof.values]
                        b_profiles = np.c_[b_profiles, elm.B_prof.values]

            dfs['load'] = pd.DataFrame(data=obj, columns=headers)

            if p_profiles is not None:
                dfs['load_P_prof'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)
                dfs['load_Q_prof'] = pd.DataFrame(data=q_profiles, columns=hdr, index=T)
                dfs['load_Ir_prof'] = pd.DataFrame(data=ir_profiles, columns=hdr, index=T)
                dfs['load_Ii_prof'] = pd.DataFrame(data=ii_profiles, columns=hdr, index=T)
                dfs['load_G_prof'] = pd.DataFrame(data=g_profiles, columns=hdr, index=T)
                dfs['load_B_prof'] = pd.DataFrame(data=b_profiles, columns=hdr, index=T)
        else:
            dfs['load'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # static generators ############################################################################################
        headers = StaticGenerator().editable_headers.keys()
        st_gen = self.get_static_generators()
        if len(st_gen) > 0:
            obj = list()
            hdr = list()
            p_profiles = None
            q_profiles = None
            for elm in st_gen:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None:
                    if p_profiles is None and elm.Sprof is not None:
                        p_profiles = elm.P_prof.values
                        q_profiles = elm.Q_prof.values
                    else:
                        p_profiles = np.c_[p_profiles, elm.P_prof.values]
                        q_profiles = np.c_[q_profiles, elm.Q_prof.values]

            dfs['static_generator'] = pd.DataFrame(data=obj, columns=headers)

            if p_profiles is not None:
                dfs['static_generator_P_prof'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)
                dfs['static_generator_Q_prof'] = pd.DataFrame(data=q_profiles, columns=hdr, index=T)
        else:
            dfs['static_generator'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # battery ######################################################################################################
        batteries = self.get_batteries()
        headers = Battery().editable_headers.keys()

        if len(batteries) > 0:
            obj = list()
            hdr = list()
            v_set_profiles = None
            p_profiles = None
            for elm in batteries:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None:
                    if p_profiles is None and elm.P_prof is not None:
                        p_profiles = elm.P_prof.values
                        v_set_profiles = elm.Vset_prof.values
                    else:
                        p_profiles = np.c_[p_profiles, elm.P_prof.values]
                        v_set_profiles = np.c_[v_set_profiles, elm.Vset_prof.values]
            dfs['battery'] = pd.DataFrame(data=obj, columns=headers)

            if p_profiles is not None:
                dfs['battery_Vset_prof'] = pd.DataFrame(data=v_set_profiles, columns=hdr, index=T)
                dfs['battery_P_prof'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)
        else:
            dfs['battery'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # controlled generator #########################################################################################
        con_gen = self.get_generators()
        headers = Generator().editable_headers.keys()

        if len(con_gen) > 0:
            obj = list()
            hdr = list()
            v_set_profiles = None
            p_profiles = None
            for elm in con_gen:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None and elm.P_prof is not None:
                    if p_profiles is None:
                        p_profiles = elm.P_prof.values
                        v_set_profiles = elm.Vset_prof.values
                    else:
                        p_profiles = np.c_[p_profiles, elm.P_prof.values]
                        v_set_profiles = np.c_[v_set_profiles, elm.Vset_prof.values]

            dfs['generator'] = pd.DataFrame(data=obj, columns=headers)

            if p_profiles is not None:
                dfs['generator_Vset_prof'] = pd.DataFrame(data=v_set_profiles, columns=hdr, index=T)
                dfs['generator_P_prof'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)
        else:
            dfs['generator'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # shunt ########################################################################################################

        shunts = self.get_shunts()
        headers = Shunt().editable_headers.keys()

        if len(shunts) > 0:
            obj = list()
            hdr = list()
            g_profiles = None
            b_profiles = None
            for elm in shunts:
                obj.append(elm.get_save_data())
                hdr.append(elm.name)
                if T is not None:
                    if g_profiles is None and elm.G_prof.values is not None:
                        g_profiles = elm.G_prof.values
                        b_profiles = elm.B_prof.values
                    else:
                        g_profiles = np.c_[g_profiles, elm.G_prof.values]
                        b_profiles = np.c_[b_profiles, elm.B_prof.values]

            dfs['shunt'] = pd.DataFrame(data=obj, columns=headers)

            if g_profiles is not None:
                dfs['shunt_G_prof'] = pd.DataFrame(data=g_profiles, columns=hdr, index=T)
                dfs['shunt_B_prof'] = pd.DataFrame(data=b_profiles, columns=hdr, index=T)
        else:

            dfs['shunt'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # wires ########################################################################################################

        elements = self.wire_types
        headers = Wire(name='', xpos=0, ypos=0, gmr=0, r=0, x=0, phase=0).editable_headers.keys()

        if len(elements) > 0:
            obj = list()
            for elm in elements:
                obj.append(elm.get_save_data())

            dfs['wires'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['wires'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # overhead cable types ######################################################################################

        elements = self.overhead_line_types
        headers = Tower().get_save_headers()

        if len(elements) > 0:
            obj = list()
            for elm in elements:
                elm.get_save_data(dta_list=obj)

            dfs['overhead_line_types'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['overhead_line_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # underground cable types ######################################################################################

        elements = self.underground_cable_types
        headers = UndergroundLineType().editable_headers.keys()

        if len(elements) > 0:
            obj = list()
            for elm in elements:
                obj.append(elm.get_save_data())

            dfs['underground_cable_types'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['underground_cable_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # sequence line types ##########################################################################################

        elements = self.sequence_line_types
        headers = SequenceLineType().editable_headers.keys()

        if len(elements) > 0:
            obj = list()
            hdr = list()
            for elm in elements:
                obj.append(elm.get_save_data())

            dfs['sequence_line_types'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['sequence_line_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # transformer types ############################################################################################

        elements = self.transformer_types
        headers = TransformerType().editable_headers.keys()

        if len(elements) > 0:
            obj = list()
            hdr = list()
            for elm in elements:
                obj.append(elm.get_save_data())

            dfs['transformer_types'] = pd.DataFrame(data=obj, columns=headers)
        else:
            dfs['transformer_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

        # flush-save ###################################################################################################
        writer = pd.ExcelWriter(file_path)
        for key in dfs.keys():
            dfs[key].to_excel(writer, key)

        writer.save()

        return logger

    def save_json(self, file_path):
        """

        :param file_path:
        :return:
        """

        from GridCal.Engine.Importers.json_parser import save_json_file
        logger = save_json_file(file_path, self)
        return logger

    def save_cim(self, file_path):
        """

        :param file_path:
        :return:
        """

        from GridCal.Engine.Importers.cim_parser import CIMExport

        cim = CIMExport(self)

        cim.save(file_name=file_path)

        return cim.logger

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



