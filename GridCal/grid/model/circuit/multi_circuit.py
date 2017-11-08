from datetime import datetime, timedelta

import os
from matplotlib import pyplot as plt
from numpy import delete, argwhere, c_
from warnings import warn

from GridCal.grid.calculate.power_flow.input import PowerFlowInput
from GridCal.grid.model.battery import Battery
from GridCal.grid.model.circuit import Bus, Branch
from GridCal.grid.model.circuit.circuit import Circuit
from GridCal.grid.model.generator.controlled import \
    ControlledGenerator
from GridCal.grid.model.generator.static import StaticGenerator
from GridCal.grid.model.load import Load
from GridCal.grid.model.shunt import Shunt
from GridCal.grid.statistics.statistics import load_from_xls


class MultiCircuit(Circuit):

    def __init__(self):
        """
        Multi Circuit Constructor
        """
        Circuit.__init__(self)

        self.name = 'Grid'

        # List of circuits contained within this circuit
        self.circuits = list()

        # self.power_flow_results = PowerFlowResults()

        self.bus_dictionary = dict()

        self.branch_dictionary = dict()

        self.has_time_series = False

        self.bus_names = None

        self.branch_names = None

        self.objects_with_profiles = [Load(), StaticGenerator(), ControlledGenerator(), Battery(), Shunt()]

        self.time_profile = None

        self.profile_magnitudes = dict()

        '''
        self.type_name = 'Shunt'

        self.properties_with_profile = ['Y']
        '''
        for dev in self.objects_with_profiles:
            if dev.properties_with_profile is not None:
                self.profile_magnitudes[dev.type_name] = dev.properties_with_profile

    def load_file(self, filename):
        """
        Load GridCal compatible file
        @param filename:
        @return:
        """
        if os.path.exists(filename):
            name, file_extension = os.path.splitext(filename)
            print(name, file_extension)
            if file_extension == '.xls' or file_extension == '.xlsx':
                ppc = load_from_xls(filename)

                # Pass the table-like data dictionary to objects in this circuit
                if 'version' not in ppc.keys():
                    from GridCal.grid.ImportParsers.matpower_parser import interpret_data_v1
                    interpret_data_v1(self, ppc)
                    return True
                elif ppc['version'] == 2.0:
                    self.interpret_data_v2(ppc)
                    return True
                else:
                    warn('The file could not be processed')
                    return False

            elif file_extension == '.dgs':
                from GridCal.grid.ImportParsers.DGS_Parser import dgs_to_circuit
                circ = dgs_to_circuit(filename)
                self.buses = circ.buses
                self.branches = circ.branches

            elif file_extension == '.m':
                from GridCal.grid.ImportParsers.matpower_parser import parse_matpower_file
                circ = parse_matpower_file(filename)
                self.buses = circ.buses
                self.branches = circ.branches

            elif file_extension in ['.raw', '.RAW', '.Raw']:
                from GridCal.grid.ImportParsers.PSS_Parser import PSSeParser
                parser = PSSeParser(filename)
                circ = parser.circuit
                self.buses = circ.buses
                self.branches = circ.branches

        else:
            warn('The file does not exist.')
            return False

    def interpret_data_v2(self, data):
        """
        Interpret the new file version
        Args:
            data: Dictionary with the excel file sheet labels and the corresponding DataFrame

        Returns: Nothing, just applies the loaded data to this MultiCircuit instance

        """
        print('Interpreting V2 data...')

        # clear all the data
        self.clear()

        self.name = data['name']

        # set the base magnitudes
        self.Sbase = data['baseMVA']

        self.time_profile = None

        # common function
        def set_object_attributes(obj_, attr_list, values):
            for a, attr in enumerate(attr_list):

                # Hack to change the enabled by active...
                if attr == 'is_enabled':
                    attr = 'active'

                conv = obj.edit_types[attr]  # get the type converter
                if conv is None:
                    setattr(obj_, attr, values[a])
                else:
                    setattr(obj_, attr, conv(values[a]))

        # Add the buses
        lst = data['bus']
        hdr = lst.columns.values
        vals = lst.values
        bus_dict = dict()
        for i in range(len(lst)):
            obj = Bus()
            set_object_attributes(obj, hdr, vals[i, :])
            bus_dict[obj.name] = obj
            self.add_bus(obj)

        # Add the branches
        lst = data['branch']
        bus_from = lst['bus_from'].values
        bus_to = lst['bus_to'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus_from'))
        hdr = delete(hdr, argwhere(hdr == 'bus_to'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = Branch(bus_from=bus_dict[bus_from[i]], bus_to=bus_dict[bus_to[i]])
            set_object_attributes(obj, hdr, vals[i, :])
            self.add_branch(obj)

        # add the loads
        lst = data['load']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = Load()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'load_Sprof' in data.keys():
                val = [complex(v) for v in data['load_Sprof'].values[:, i]]
                idx = data['load_Sprof'].index
                obj.Sprof = pd.DataFrame(data=val, index=idx)

                if self.time_profile is None:
                    self.time_profile = idx

            if 'load_Iprof' in data.keys():
                val = [complex(v) for v in data['load_Iprof'].values[:, i]]
                idx = data['load_Iprof'].index
                obj.Iprof = pd.DataFrame(data=val, index=idx)

                if self.time_profile is None:
                    self.time_profile = idx

            if 'load_Zprof' in data.keys():
                val = [complex(v) for v in data['load_Zprof'].values[:, i]]
                idx = data['load_Zprof'].index
                obj.Zprof = pd.DataFrame(data=val, index=idx)

                if self.time_profile is None:
                    self.time_profile = idx

            bus = bus_dict[bus_from[i]]

            if obj.name == 'Load':
                obj.name += str(len(bus.loads)+1) + '@' + bus.name

            obj.bus = bus
            bus.loads.append(obj)

        # add the controlled generators
        lst = data['controlled_generator']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = ControlledGenerator()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'CtrlGen_P_profiles' in data.keys():
                val = data['CtrlGen_P_profiles'].values[:, i]
                idx = data['CtrlGen_P_profiles'].index
                obj.Pprof = pd.DataFrame(data=val, index=idx)

            if 'CtrlGen_Vset_profiles' in data.keys():
                val = data['CtrlGen_Vset_profiles'].values[:, i]
                idx = data['CtrlGen_Vset_profiles'].index
                obj.Vsetprof = pd.DataFrame(data=val, index=idx)

            bus = bus_dict[bus_from[i]]

            if obj.name == 'gen':
                obj.name += str(len(bus.controlled_generators)+1) + '@' + bus.name

            obj.bus = bus
            bus.controlled_generators.append(obj)

        # add the batteries
        lst = data['battery']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = Battery()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'battery_P_profiles' in data.keys():
                val = data['battery_P_profiles'].values[:, i]
                idx = data['battery_P_profiles'].index
                obj.Pprof = pd.DataFrame(data=val, index=idx)

            if 'battery_Vset_profiles' in data.keys():
                val = data['battery_Vset_profiles'].values[:, i]
                idx = data['battery_Vset_profiles'].index
                obj.Vsetprof = pd.DataFrame(data=val, index=idx)

            bus = bus_dict[bus_from[i]]

            if obj.name == 'batt':
                obj.name += str(len(bus.batteries)+1) + '@' + bus.name

            obj.bus = bus
            bus.batteries.append(obj)

        # add the static generators
        lst = data['static_generator']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = StaticGenerator()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'static_generator_Sprof' in data.keys():
                val = data['static_generator_Sprof'].values[:, i]
                idx = data['static_generator_Sprof'].index
                obj.Sprof = pd.DataFrame(data=val, index=idx)

            bus = bus_dict[bus_from[i]]

            if obj.name == 'StaticGen':
                obj.name += str(len(bus.static_generators)+1) + '@' + bus.name

            obj.bus = bus
            bus.static_generators.append(obj)

        # add the shunts
        lst = data['shunt']
        bus_from = lst['bus'].values
        hdr = lst.columns.values
        hdr = delete(hdr, argwhere(hdr == 'bus'))
        vals = lst[hdr].values
        for i in range(len(lst)):
            obj = Shunt()
            set_object_attributes(obj, hdr, vals[i, :])

            if 'shunt_Y_profiles' in data.keys():
                val = data['shunt_Y_profiles'].values[:, i]
                idx = data['shunt_Y_profiles'].index
                obj.Yprof = pd.DataFrame(data=val, index=idx)

            bus = bus_dict[bus_from[i]]

            if obj.name == 'shunt':
                obj.name += str(len(bus.shunts)+1) + '@' + bus.name

            obj.bus = bus
            bus.shunts.append(obj)

        print('Done!')

        # ['branch', 'load_Zprof', 'version', 'CtrlGen_Vset_profiles', 'CtrlGen_P_profiles', 'basekA',
        #                   'baseMVA', 'load_Iprof', 'battery', 'load', 'bus', 'shunt', 'controlled_generator',
        #                   'load_Sprof', 'static_generator']

    def save_file(self, file_path):
        """
        Save the circuit information
        :param file_path: file path to save
        :return:
        """
        dfs = dict()

        # configuration ################################################################################################
        obj = list()
        obj.append(['BaseMVA', self.Sbase])
        obj.append(['Version', 2])
        obj.append(['Name', self.name])
        dfs['config'] = pd.DataFrame(data=obj, columns=['Property', 'Value'])

        # get the master time profile
        T = self.time_profile

        # buses ########################################################################################################
        obj = list()
        names_count = dict()
        for elm in self.buses:

            # check name: if the name is repeated, change it so that it is not
            if elm.name in names_count.keys():
                names_count[elm.name] += 1
                elm.name = elm.name + '_' + str(names_count[elm.name])
            else:
                names_count[elm.name] = 1

            obj.append(elm.get_save_data())
        dfs['bus'] = pd.DataFrame(data=array(obj).astype('str'), columns=Bus().edit_headers)

        # branches #####################################################################################################
        obj = list()
        for elm in self.branches:
            obj.append(elm.get_save_data())
        dfs['branch'] = pd.DataFrame(data=obj, columns=Branch(None, None).edit_headers)

        # loads ########################################################################################################
        obj = list()
        s_profiles = None
        i_profiles = None
        z_profiles = None
        hdr = list()
        for elm in self.get_loads():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if s_profiles is None and elm.Sprof is not None:
                    s_profiles = elm.Sprof.values
                    i_profiles = elm.Iprof.values
                    z_profiles = elm.Zprof.values
                else:
                    s_profiles = c_[s_profiles, elm.Sprof.values]
                    i_profiles = c_[i_profiles, elm.Iprof.values]
                    z_profiles = c_[z_profiles, elm.Zprof.values]

        dfs['load'] = pd.DataFrame(data=obj, columns=Load().edit_headers)

        if s_profiles is not None:
            dfs['load_Sprof'] = pd.DataFrame(data=s_profiles.astype('str'), columns=hdr, index=T)
            dfs['load_Iprof'] = pd.DataFrame(data=i_profiles.astype('str'), columns=hdr, index=T)
            dfs['load_Zprof'] = pd.DataFrame(data=z_profiles.astype('str'), columns=hdr, index=T)

        # static generators ############################################################################################
        obj = list()
        hdr = list()
        s_profiles = None
        for elm in self.get_static_generators():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if s_profiles is None and elm.Sprof is not None:
                    s_profiles = elm.Sprof.values
                else:
                    s_profiles = c_[s_profiles, elm.Sprof.values]

        dfs['static_generator'] = pd.DataFrame(data=obj, columns=StaticGenerator().edit_headers)

        if s_profiles is not None:
            dfs['static_generator_Sprof'] = pd.DataFrame(data=s_profiles.astype('str'), columns=hdr, index=T)

        # battery ######################################################################################################
        obj = list()
        hdr = list()
        v_set_profiles = None
        p_profiles = None
        for elm in self.get_batteries():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if p_profiles is None and elm.Pprof is not None:
                    p_profiles = elm.Pprof.values
                    v_set_profiles = elm.Vsetprof.values
                else:
                    p_profiles = c_[p_profiles, elm.Pprof.values]
                    v_set_profiles = c_[v_set_profiles, elm.Vsetprof.values]
        dfs['battery'] = pd.DataFrame(data=obj, columns=Battery().edit_headers)

        if p_profiles is not None:
            dfs['battery_Vset_profiles'] = pd.DataFrame(data=v_set_profiles, columns=hdr, index=T)
            dfs['battery_P_profiles'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)

        # controlled generator
        obj = list()
        hdr = list()
        v_set_profiles = None
        p_profiles = None
        for elm in self.get_controlled_generators():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None and elm.Pprof is not None:
                if p_profiles is None:
                    p_profiles = elm.Pprof.values
                    v_set_profiles = elm.Vsetprof.values
                else:
                    p_profiles = c_[p_profiles, elm.Pprof.values]
                    v_set_profiles = c_[v_set_profiles, elm.Vsetprof.values]
        dfs['controlled_generator'] = pd.DataFrame(data=obj, columns=ControlledGenerator().edit_headers)
        if p_profiles is not None:
            dfs['CtrlGen_Vset_profiles'] = pd.DataFrame(data=v_set_profiles, columns=hdr, index=T)
            dfs['CtrlGen_P_profiles'] = pd.DataFrame(data=p_profiles, columns=hdr, index=T)

        # shunt
        obj = list()
        hdr = list()
        y_profiles = None
        for elm in self.get_shunts():
            obj.append(elm.get_save_data())
            hdr.append(elm.name)
            if T is not None:
                if y_profiles is None and elm.Yprof.values is not None:
                    y_profiles = elm.Yprof.values
                else:
                    y_profiles = c_[y_profiles, elm.Yprof.values]

        dfs['shunt'] = pd.DataFrame(data=obj, columns=Shunt().edit_headers)

        if y_profiles is not None:
            dfs['shunt_Y_profiles'] = pd.DataFrame(data=y_profiles, columns=hdr, index=T)

        # flush-save
        writer = pd.ExcelWriter(file_path)
        for key in dfs.keys():
            dfs[key].to_excel(writer, key)

        writer.save()

    def compile(self):
        """
        Divide the grid into the different possible grids
        @return:
        """

        n = len(self.buses)
        m = len(self.branches)
        self.power_flow_input = PowerFlowInput(n, m)

        self.time_series_input = TimeSeriesInput()

        self.graph = nx.Graph()

        self.circuits = list()

        self.has_time_series = True

        self.bus_names = zeros(n, dtype=object)
        self.branch_names = zeros(m, dtype=object)

        # create bus dictionary
        for i in range(n):
            self.bus_dictionary[self.buses[i]] = i
            self.bus_names[i] = self.buses[i].name

        # Compile the branches
        for i in range(m):
            self.branch_names[i] = self.branches[i].name
            if self.branches[i].active:
                if self.branches[i].bus_from.active and self.branches[i].bus_to.active:
                    f = self.bus_dictionary[self.branches[i].bus_from]
                    t = self.bus_dictionary[self.branches[i].bus_to]
                    # Add graph edge (automatically adds the vertices)
                    self.graph.add_edge(f, t, length=self.branches[i].R)
                    self.branch_dictionary[self.branches[i]] = i

        # Split the graph into islands
        islands = [list(isl) for isl in connected_components(self.graph)]

        isl_idx = 0
        for island in islands:

            # Convert island to dictionary
            isl_dict = dict()
            for idx in range(len(island)):
                isl_dict[island[idx]] = idx

            # create circuit of the island
            circuit = Circuit(name='Island ' + str(isl_idx))

            # Set buses of the island
            circuit.buses = [self.buses[b] for b in island]
            circuit.bus_original_idx = island

            # set branches of the island
            for i in range(m):
                f = self.bus_dictionary[self.branches[i].bus_from]
                t = self.bus_dictionary[self.branches[i].bus_to]
                if f in island and t in island:
                    # Copy the branch into a new
                    branch = self.branches[i].copy()
                    # Add the branch to the circuit
                    circuit.branches.append(branch)
                    circuit.branch_original_idx.append(i)

            circuit.compile()
            self.power_flow_input.set_from(circuit.power_flow_input,
                                           circuit.bus_original_idx,
                                           circuit.branch_original_idx)

            self.time_series_input.apply_from_island(circuit.time_series_input,
                                                     circuit.bus_original_idx,
                                                     circuit.branch_original_idx,
                                                     n, m)

            self.circuits.append(circuit)

            self.has_time_series = self.has_time_series and circuit.time_series_input.valid

            isl_idx += 1

        print(islands)

    def create_profiles(self, steps, step_length, step_unit, time_base: datetime=datetime.now()):
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
                index[i] = time_base + timedelta(hours=i*step_length)
            elif step_unit == 'm':
                index[i] = time_base + timedelta(minutes=i*step_length)
            elif step_unit == 's':
                index[i] = time_base + timedelta(seconds=i*step_length)

        self.format_profiles(index)

    def format_profiles(self, index):
        """
        Format the pandas profiles in place using a time index
        Args:
            index: Time profile
        """

        self.time_profile = array(index)

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
            element_type: String {'Load', 'StaticGenerator', 'ControlledGenerator', 'Battery', 'Shunt'}

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

        elif element_type == 'ControlledGenerator':
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

    def add_controlled_generator(self, bus: Bus, api_obj=None):
        """
        Add controlled generator to a bus
        Args:
            bus: Bus object
            api_obj: ControlledGenerator object
        """
        if api_obj is None:
            api_obj = ControlledGenerator()
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
        Add battery object to a bus
        Args:
            bus: Bus object to add it to
            api_obj: Battery object to add it to
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

    def plot_graph(self, ax=None):
        """
        Plot the grid
        @param ax: Matplotlib axis object
        @return: Nothing
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        nx.draw_spring(self.graph, ax=ax)

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

        return cpy

    def dispatch(self):
        """
        Dispatch either load or generation using a simple equalised share rule of the shedding to be done
        @return: Nothing
        """
        if self.power_flow_input is not None:

            # get the total power balance
            balance = abs(self.power_flow_input.Sbus.sum())

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
