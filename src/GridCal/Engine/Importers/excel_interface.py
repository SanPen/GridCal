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
import pandas as pd
import numpy as np

from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.devices import *
from GridCal.Engine.device_types import *

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


def check_names(names):
    for name in names:
        if name not in allowed_data_sheets.keys():
            raise Exception('The file sheet ' + name + ' is not allowed.\n'
                            'Did you create this file manually? Use GridCal instead.')


def load_from_xls(filename):
    """
    Loads the excel file content to a dictionary for parsing the data
    """
    data = dict()
    xl = pd.ExcelFile(filename)
    names = xl.sheet_names

    # check the validity of this excel file
    check_names(names=names)

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


def interprete_excel_v2(circuit: MultiCircuit, data):
    """
    Interpret the new file version
    Args:
        data: Dictionary with the excel file sheet labels and the corresponding DataFrame

    Returns: Nothing, just applies the loaded data to this MultiCircuit instance

    """
    # print('Interpreting V2 data...')

    # clear all the data
    circuit.clear()

    circuit.name = data['name']

    # set the base magnitudes
    circuit.Sbase = data['baseMVA']

    # dictionary of branch types [name] -> type object
    branch_types = dict()

    # Set comments
    circuit.comments = data['Comments'] if 'Comments' in data.keys() else ''

    circuit.time_profile = None

    circuit.logger = list()

    # common function
    def set_object_attributes(obj_, attr_list, values):
        for a, attr in enumerate(attr_list):

            # Hack to change the enabled by active...
            if attr == 'is_enabled':
                attr = 'active'

            if attr == 'type_obj':
                attr = 'template'

            if hasattr(obj_, attr):
                conv = obj_.editable_headers[attr].tpe  # get the type converter
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
            circuit.add_bus(obj)
    else:
        circuit.logger.append('No buses in the file!')

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
                obj.create_profile(magnitude='P', index=idx, arr=val.real)
                obj.create_profile(magnitude='Q', index=idx, arr=val.imag)

                if circuit.time_profile is None or len(circuit.time_profile) < len(idx):
                    circuit.time_profile = idx

            if 'load_Iprof' in data.keys():
                val = np.array([complex(v) for v in data['load_Iprof'].values[:, i]])
                idx = data['load_Iprof'].index
                obj.create_profile(magnitude='Ir', index=idx, arr=val.real)
                obj.create_profile(magnitude='Ii', index=idx, arr=val.imag)

                if circuit.time_profile is None or len(circuit.time_profile) < len(idx):
                    circuit.time_profile = idx

            if 'load_Zprof' in data.keys():
                val = np.array([complex(v) for v in data['load_Zprof'].values[:, i]])
                idx = data['load_Zprof'].index
                obj.create_profile(magnitude='G', index=idx, arr=val.real)
                obj.create_profile(magnitude='B', index=idx, arr=val.imag)

                if circuit.time_profile is None or len(circuit.time_profile) < len(idx):
                    circuit.time_profile = idx

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Load bus is not in the buses list.\n' + str(ex))

            if obj.name == 'Load':
                obj.name += str(len(bus.loads) + 1) + '@' + bus.name

            obj.bus = bus
            bus.loads.append(obj)
            obj.ensure_profiles_exist(circuit.time_profile)
    else:
        circuit.logger.append('No loads in the file!')

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
                obj.create_profile(magnitude='P', index=idx, arr=val)
                # also create the Pf array because there might not be values in the file
                obj.create_profile(magnitude='Pf', index=idx)

            if 'CtrlGen_Pf_profiles' in data.keys():
                val = data['CtrlGen_Pf_profiles'].values[:, i]
                idx = data['CtrlGen_Pf_profiles'].index
                obj.create_profile(magnitude='Pf', index=idx, arr=val)

            if 'CtrlGen_Vset_profiles' in data.keys():
                val = data['CtrlGen_Vset_profiles'].values[:, i]
                idx = data['CtrlGen_Vset_profiles'].index
                obj.create_profile(magnitude='Vset', index=idx, arr=val)

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Controlled generator bus is not in the buses list.\n' + str(ex))

            if obj.name == 'gen':
                obj.name += str(len(bus.controlled_generators) + 1) + '@' + bus.name

            obj.bus = bus
            bus.controlled_generators.append(obj)
            obj.ensure_profiles_exist(circuit.time_profile)
    else:
        circuit.logger.append('No controlled generator in the file!')

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
                obj.create_profile(magnitude='P', index=idx, arr=val)
                obj.create_profile(magnitude='Pf', index=idx)

            if 'battery_Pf_profiles' in data.keys():
                val = data['battery_Pf_profiles'].values[:, i]
                idx = data['battery_Pf_profiles'].index
                obj.create_profile(magnitude='Pf', index=idx, arr=val)

            if 'battery_Vset_profiles' in data.keys():
                val = data['battery_Vset_profiles'].values[:, i]
                idx = data['battery_Vset_profiles'].index
                obj.create_profile(magnitude='Vset', index=idx, arr=val)

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Battery bus is not in the buses list.\n' + str(ex))

            if obj.name == 'batt':
                obj.name += str(len(bus.batteries) + 1) + '@' + bus.name

            obj.bus = bus
            bus.batteries.append(obj)
            obj.ensure_profiles_exist(circuit.time_profile)
    else:
        circuit.logger.append('No battery in the file!')

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
                obj.create_profile(magnitude='P', index=idx, arr=val.real)
                obj.create_profile(magnitude='Q', index=idx, arr=val.imag)

            if 'static_generator_P_prof' in data.keys():
                val = data['static_generator_P_prof'].values[:, i]
                idx = data['static_generator_P_prof'].index
                obj.create_profile(magnitude='P', index=idx, arr=val)

            if 'static_generator_Q_prof' in data.keys():
                val = data['static_generator_Q_prof'].values[:, i]
                idx = data['static_generator_Q_prof'].index
                obj.create_profile(magnitude='Q', index=idx, arr=val)

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Static generator bus is not in the buses list.\n' + str(ex))

            if obj.name == 'StaticGen':
                obj.name += str(len(bus.static_generators) + 1) + '@' + bus.name

            obj.bus = bus
            bus.static_generators.append(obj)
            obj.ensure_profiles_exist(circuit.time_profile)
    else:
        circuit.logger.append('No static generator in the file!')

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
                obj.create_profile(magnitude='G', index=idx, arr=val.real)
                obj.create_profile(magnitude='B', index=idx, arr=val.imag)
            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Shunt bus is not in the buses list.\n' + str(ex))

            if obj.name == 'shunt':
                obj.name += str(len(bus.shunts) + 1) + '@' + bus.name

            obj.bus = bus
            bus.shunts.append(obj)
            obj.ensure_profiles_exist(circuit.time_profile)
    else:
        circuit.logger.append('No shunt in the file!')

    # Add the wires ################################################################################################
    if 'wires' in data.keys():
        lst = data['wires']
        hdr = lst.columns.values
        vals = lst.values
        for i in range(len(lst)):
            obj = Wire()
            set_object_attributes(obj, hdr, vals[i, :])
            circuit.add_wire(obj)
    else:
        circuit.logger.append('No wires in the file!')

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

                circuit.add_overhead_line(obj)
                branch_types[str(obj)] = obj
        else:
            pass
    else:
        circuit.logger.append('No overhead_line_types in the file!')

    # Add the wires ################################################################################################
    if 'underground_cable_types' in data.keys():
        lst = data['underground_cable_types']
        hdr = lst.columns.values
        vals = lst.values
        # for i in range(len(lst)):
        #     obj = UndergroundLineType()
        #     set_object_attributes(obj, hdr, vals[i, :])
        #     circuit.underground_cable_types.append(obj)
        #     branch_types[str(obj)] = obj
    else:
        circuit.logger.append('No underground_cable_types in the file!')

    # Add the sequence line types ##################################################################################
    if 'sequence_line_types' in data.keys():
        lst = data['sequence_line_types']
        hdr = lst.columns.values
        vals = lst.values
        for i in range(len(lst)):
            obj = SequenceLineType()
            set_object_attributes(obj, hdr, vals[i, :])
            circuit.add_sequence_line(obj)
            branch_types[str(obj)] = obj
    else:
        circuit.logger.append('No sequence_line_types in the file!')

    # Add the transformer types ####################################################################################
    if 'transformer_types' in data.keys():
        lst = data['transformer_types']
        hdr = lst.columns.values
        vals = lst.values
        for i in range(len(lst)):
            obj = TransformerType()
            set_object_attributes(obj, hdr, vals[i, :])
            circuit.add_transformer_type(obj)
            branch_types[str(obj)] = obj
    else:
        circuit.logger.append('No transformer_types in the file!')

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
            circuit.add_branch(obj)

    else:
        circuit.logger.append('No branches in the file!')

    # Other actions ################################################################################################
    circuit.logger += circuit.apply_all_branch_types()


def interpret_excel_v3(circuit: MultiCircuit, data):
    """
    Interpret the file version 3
    In this file version there are no complex numbers saved
    Args:
        data: Dictionary with the excel file sheet labels and the corresponding DataFrame

    Returns: Nothing, just applies the loaded data to this MultiCircuit instance

    """
    # print('Interpreting V2 data...')

    # clear all the data
    circuit.clear()

    circuit.name = data['name']

    # set the base magnitudes
    circuit.Sbase = data['baseMVA']

    # dictionary of branch types [name] -> type object
    branch_types = dict()

    # Set comments
    circuit.comments = data['Comments'] if 'Comments' in data.keys() else ''

    circuit.time_profile = None

    circuit.logger = list()

    # common function
    def set_object_attributes(obj_, attr_list, values):
        for a, attr in enumerate(attr_list):

            # Hack to change the enabled by active...
            if attr == 'is_enabled':
                attr = 'active'

            if attr == 'type_obj':
                attr = 'template'

            if hasattr(obj_, attr):
                conv = obj_.editable_headers[attr].tpe  # get the type converter
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
            circuit.add_bus(obj)
    else:
        circuit.logger.append('No buses in the file!')

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

                    if circuit.time_profile is None or len(circuit.time_profile) < len(idx):
                        circuit.time_profile = idx

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Load bus is not in the buses list.\n' + str(ex))

            if obj.name == 'Load':
                obj.name += str(len(bus.loads) + 1) + '@' + bus.name

            obj.bus = bus
            bus.loads.append(obj)
            obj.ensure_profiles_exist(circuit.time_profile)
    else:
        circuit.logger.append('No loads in the file!')

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
                obj.create_profile(magnitude='P', index=idx, arr=val)
                # also create the Pf array because there might not be values in the file
                obj.create_profile(magnitude='Pf', index=idx, arr=None)

                if circuit.time_profile is None or len(circuit.time_profile) < len(idx):
                    circuit.time_profile = idx

            if 'generator_Pf_prof' in data.keys():
                val = data['generator_Pf_prof'].values[:, i]
                idx = data['generator_Pf_prof'].index
                obj.create_profile(magnitude='Pf', index=idx, arr=val)

            if 'generator_Vset_prof' in data.keys():
                val = data['generator_Vset_prof'].values[:, i]
                idx = data['generator_Vset_prof'].index
                obj.create_profile(magnitude='Vset', index=idx, arr=val)

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Controlled generator bus is not in the buses list.\n' + str(ex))

            if obj.name == 'gen':
                obj.name += str(len(bus.controlled_generators) + 1) + '@' + bus.name

            obj.bus = bus
            bus.controlled_generators.append(obj)
            obj.ensure_profiles_exist(circuit.time_profile)
    else:
        circuit.logger.append('No controlled generator in the file!')

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
                obj.create_profile(magnitude='P', index=idx, arr=val)
                # also create the Pf array because there might not be values in the file
                obj.create_profile(magnitude='Pf', index=idx, arr=None)

            if 'battery_Vset_prof' in data.keys():
                val = data['battery_Vset_prof'].values[:, i]
                idx = data['battery_Vset_prof'].index
                obj.create_profile(magnitude='Vset', index=idx, arr=val)

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Battery bus is not in the buses list.\n' + str(ex))

            if obj.name == 'batt':
                obj.name += str(len(bus.batteries) + 1) + '@' + bus.name

            obj.bus = bus
            bus.batteries.append(obj)
            obj.ensure_profiles_exist(circuit.time_profile)
    else:
        circuit.logger.append('No battery in the file!')

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
                obj.create_profile(magnitude='P', index=idx, arr=val.real)
                obj.create_profile(magnitude='Q', index=idx, arr=val.imag)

            if 'static_generator_P_prof' in data.keys():
                val = data['static_generator_P_prof'].values[:, i]
                idx = data['static_generator_P_prof'].index
                obj.create_profile(magnitude='P', index=idx, arr=val)

            if 'static_generator_Q_prof' in data.keys():
                val = data['static_generator_Q_prof'].values[:, i]
                idx = data['static_generator_Q_prof'].index
                obj.create_profile(magnitude='Q', index=idx, arr=val)

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Static generator bus is not in the buses list.\n' + str(ex))

            if obj.name == 'StaticGen':
                obj.name += str(len(bus.static_generators) + 1) + '@' + bus.name

            obj.bus = bus
            bus.static_generators.append(obj)
            obj.ensure_profiles_exist(circuit.time_profile)
    else:
        circuit.logger.append('No static generator in the file!')

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
                obj.create_profile(magnitude='G', index=idx, arr=val.real)
                obj.create_profile(magnitude='B', index=idx, arr=val.imag)

            if 'shunt_G_prof' in data.keys():
                val = data['shunt_G_prof'].values[:, i]
                idx = data['shunt_G_prof'].index
                obj.create_profile(magnitude='G', index=idx, arr=val)

            if 'shunt_B_prof' in data.keys():
                val = data['shunt_B_prof'].values[:, i]
                idx = data['shunt_B_prof'].index
                obj.create_profile(magnitude='B', index=idx, arr=val)

            try:
                bus = bus_dict[str(bus_from[i])]
            except KeyError as ex:
                raise Exception(str(i) + ': Shunt bus is not in the buses list.\n' + str(ex))

            if obj.name == 'shunt':
                obj.name += str(len(bus.shunts) + 1) + '@' + bus.name

            obj.bus = bus
            bus.shunts.append(obj)
            obj.ensure_profiles_exist(circuit.time_profile)
    else:
        circuit.logger.append('No shunt in the file!')

    # Add the wires ################################################################################################
    if 'wires' in data.keys():
        lst = data['wires']
        hdr = lst.columns.values
        vals = lst.values
        for i in range(len(lst)):
            obj = Wire()
            set_object_attributes(obj, hdr, vals[i, :])
            circuit.add_wire(obj)
    else:
        circuit.logger.append('No wires in the file!')

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

                circuit.add_overhead_line(obj)
                branch_types[str(obj)] = obj
        else:
            pass
    else:
        circuit.logger.append('No overhead_line_types in the file!')

    # Add the wires ################################################################################################
    if 'underground_cable_types' in data.keys():
        lst = data['underground_cable_types']
        hdr = lst.columns.values
        vals = lst.values
        # for i in range(len(lst)):
        #     obj = UndergroundLineType()
        #     set_object_attributes(obj, hdr, vals[i, :])
        #     circuit.underground_cable_types.append(obj)
        #     branch_types[str(obj)] = obj
    else:
        circuit.logger.append('No underground_cable_types in the file!')

    # Add the sequence line types ##################################################################################
    if 'sequence_line_types' in data.keys():
        lst = data['sequence_line_types']
        hdr = lst.columns.values
        vals = lst.values
        for i in range(len(lst)):
            obj = SequenceLineType()
            set_object_attributes(obj, hdr, vals[i, :])
            circuit.add_sequence_line(obj)
            branch_types[str(obj)] = obj
    else:
        circuit.logger.append('No sequence_line_types in the file!')

    # Add the transformer types ####################################################################################
    if 'transformer_types' in data.keys():
        lst = data['transformer_types']
        hdr = lst.columns.values
        vals = lst.values
        for i in range(len(lst)):
            obj = TransformerType()
            set_object_attributes(obj, hdr, vals[i, :])
            circuit.add_transformer_type(obj)
            branch_types[str(obj)] = obj
    else:
        circuit.logger.append('No transformer_types in the file!')

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
            circuit.add_branch(obj)

    else:
        circuit.logger.append('No branches in the file!')

    # Other actions ################################################################################################
    circuit.logger += circuit.apply_all_branch_types()


def create_data_frames(circuit: MultiCircuit):
    """
    Pack the circuit information into tables (DataFrames)
    :param circuit: MultiCircuit instance
    :return: dictionary of DataFrames
    """
    dfs = dict()

    # configuration ################################################################################################
    obj = list()
    obj.append(['BaseMVA', circuit.Sbase])
    obj.append(['Version', 3])
    obj.append(['Name', circuit.name])
    obj.append(['Comments', circuit.comments])
    obj.append(['program', 'GridCal'])

    dfs['config'] = pd.DataFrame(data=obj, columns=['Property', 'Value'])

    # get the master time profile
    T = circuit.time_profile

    # buses ########################################################################################################
    obj = list()
    names_count = dict()
    headers = Bus().editable_headers.keys()
    if len(circuit.buses) > 0:
        for elm in circuit.buses:

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
    if len(circuit.branches) > 0:
        obj = list()
        for elm in circuit.branches:
            obj.append(elm.get_save_data())

        dta = np.array(obj)
    else:
        dta = np.zeros((0, len(headers)))

    dfs['branch'] = pd.DataFrame(data=dta, columns=headers)

    # loads ########################################################################################################
    headers = Load().editable_headers.keys()
    loads = circuit.get_loads()
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
    st_gen = circuit.get_static_generators()
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
    batteries = circuit.get_batteries()
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
    con_gen = circuit.get_generators()
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

    shunts = circuit.get_shunts()
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

    elements = circuit.wire_types
    headers = Wire(name='', xpos=0, ypos=0, gmr=0, r=0, x=0, phase=0).editable_headers.keys()

    if len(elements) > 0:
        obj = list()
        for elm in elements:
            obj.append(elm.get_save_data())

        dfs['wires'] = pd.DataFrame(data=obj, columns=headers)
    else:
        dfs['wires'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

    # overhead cable types ######################################################################################

    elements = circuit.overhead_line_types
    headers = Tower().get_save_headers()

    if len(elements) > 0:
        obj = list()
        for elm in elements:
            elm.get_save_data(dta_list=obj)

        dfs['overhead_line_types'] = pd.DataFrame(data=obj, columns=headers)
    else:
        dfs['overhead_line_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

    # underground cable types ######################################################################################

    elements = circuit.underground_cable_types
    headers = UndergroundLineType().editable_headers.keys()

    if len(elements) > 0:
        obj = list()
        for elm in elements:
            obj.append(elm.get_save_data())

        dfs['underground_cable_types'] = pd.DataFrame(data=obj, columns=headers)
    else:
        dfs['underground_cable_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

    # sequence line types ##########################################################################################

    elements = circuit.sequence_line_types
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

    elements = circuit.transformer_types
    headers = TransformerType().editable_headers.keys()

    if len(elements) > 0:
        obj = list()
        hdr = list()
        for elm in elements:
            obj.append(elm.get_save_data())

        dfs['transformer_types'] = pd.DataFrame(data=obj, columns=headers)
    else:
        dfs['transformer_types'] = pd.DataFrame(data=np.zeros((0, len(headers))), columns=headers)

    return dfs


def save_excel(circuit: MultiCircuit, file_path):
    """
    Save the circuit information in excel format
    :param circuit: MultiCircuit instance
    :param file_path: path to the excel file
    :return: logger with information
    """
    logger = list()

    dfs = create_data_frames(circuit=circuit)

    # flush-save ###################################################################################################
    writer = pd.ExcelWriter(file_path)
    for key in dfs.keys():
        dfs[key].to_excel(writer, key)

    writer.save()

    return logger
