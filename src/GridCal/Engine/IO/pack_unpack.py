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

from typing import Dict

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices import *


def get_objects_dictionary():
    """
    creates a dictionary with the types and the circuit objects
    :return: Dictionary instance
    """
    object_types = {'bus': Bus(),

                    'load': Load(),

                    'static_generator': StaticGenerator(),

                    'battery': Battery(),

                    'generator': Generator(),

                    'shunt': Shunt(),

                    'wires': Wire(),

                    'overhead_line_types': Tower(),

                    'underground_cable_types': UndergroundLineType(),

                    'sequence_line_types': SequenceLineType(),

                    'transformer_types': TransformerType(),

                    'branch': Branch(),
                    }

    return object_types


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
    obj.append(['Version', 4])
    obj.append(['Name', str(circuit.name)])
    obj.append(['Comments', str(circuit.comments)])
    obj.append(['program', 'GridCal'])

    dfs['config'] = pd.DataFrame(data=obj, columns=['Property', 'Value'])

    # get the master time profile
    T = circuit.time_profile

    ########################################################################################################
    # retrieve buses information that is necessary
    ########################################################################################################
    names_count = dict()
    if len(circuit.buses) > 0:
        for elm in circuit.buses:

            # check name: if the name is repeated, change it so that it is not
            if elm.name in names_count.keys():
                names_count[elm.name] += 1
                elm.name = elm.name + '_' + str(names_count[elm.name])
            else:
                names_count[elm.name] = 1

            elm.ensure_profiles_exist(T)

            elm.retrieve_graphic_position()

    ########################################################################################################
    # declare objects to iterate  name: [sample object, list of objects, headers]
    ########################################################################################################
    object_types = get_objects_dictionary()

    ########################################################################################################
    # generic object iteration
    ########################################################################################################
    for object_type_name in object_types.keys():

        object_sample = object_types[object_type_name]

        headers = object_sample.editable_headers.keys()

        lists_of_objects = circuit.get_elements_by_type(object_sample.device_type)

        obj = list()
        profiles = dict()
        object_names = list()
        if len(lists_of_objects) > 0:

            for elm in lists_of_objects:

                # get the object normal information
                obj.append(elm.get_save_data())

                object_names.append(elm.name)

                if T is not None:
                    if len(T) > 0:

                        elm.ensure_profiles_exist(T)

                        for profile_property in object_sample.properties_with_profile.values():

                            if profile_property not in profiles.keys():
                                # create the profile
                                profiles[profile_property] = getattr(elm, profile_property)
                            else:
                                # concatenate the new profile
                                profiles[profile_property] = np.c_[profiles[profile_property],
                                                                   getattr(elm, profile_property)]
                    else:
                        pass
                else:
                    pass

            # convert the objects' list to an array
            dta = np.array(obj)
        else:
            # declare an empty array
            dta = np.zeros((0, len(headers)))

        # declare the DataFrames for the normal data
        dfs[object_type_name] = pd.DataFrame(data=dta, columns=headers)

        # create the profiles' DataFrames
        for prop, data in profiles.items():
            dfs[object_type_name + '_' + prop] = pd.DataFrame(data=data, columns=object_names, index=T)

    # towers and wires -------------------------------------------------------------------------------------------------
    # because each tower contains a reference to a number of wires, these relations need to be stored as well
    associations = list()
    for tower in circuit.overhead_line_types:
        for wire in tower.wires_in_tower:
            associations.append([tower.name, wire.name, wire.xpos, wire.ypos, wire.phase])

    dfs['tower_wires'] = pd.DataFrame(data=associations, columns=['tower_name', 'wire_name', 'xpos', 'ypos', 'phase'])

    # Time -------------------------------------------------------------------------------------------------------------

    if circuit.time_profile is not None:
        time_df = pd.DataFrame(data=circuit.time_profile, columns=['Time'])
        dfs['time'] = time_df

    return dfs


def data_frames_to_circuit(data: Dict):
    """
    Interpret data dictionary
    :param data: dictionary of data frames
    :return: MultiCircuit instance
    """
    # create circuit
    circuit = MultiCircuit()

    circuit.name = data['name']

    # set the base magnitudes
    circuit.Sbase = data['baseMVA']

    # Set comments
    circuit.comments = data['Comments'] if 'Comments' in data.keys() else ''

    # dictionary of objects to iterate
    object_types = get_objects_dictionary()

    circuit.logger = Logger()

    # time profile -----------------------------------------------------------------------------------------------------
    if 'time' in data.keys():
        time_df = data['time']
        circuit.time_profile = pd.to_datetime(time_df.values[:, 0])
    else:
        circuit.time_profile = None

    # dictionary of dictionaries by element type
    # elements_dict[DataType][element_name] = actual object
    elements_dict = dict()

    # ------------------------------------------------------------------------------------------------------------------
    # for each element type...
    for key, template_elm in object_types.items():

        if key in data.keys():

            # get the DataFrame
            df = data[key]

            # create the objects ...
            devices = list()
            devices_dict = dict()
            for i in range(df.shape[0]):

                elm = type(template_elm)()
                name = df['name'].values[i]

                # create the buses dictionary, this works because the bus is the first key in "object_types"
                devices_dict[name] = elm

                # add the device to the elements
                devices.append(elm)

            elements_dict[template_elm.device_type] = devices_dict

            # fill in the objects
            if df.shape[0] > 0:

                # for each property ...
                for prop, gc_prop in template_elm.editable_headers.items():

                    # if the object property exists in the data file, set all the object's property
                    if prop in df.columns.values:

                        # get the type converter
                        dtype = gc_prop.tpe

                        # for each object, set the property
                        for i in range(df.shape[0]):

                            # convert and assign the data
                            if dtype is None:
                                val = df[prop].values[i]
                                setattr(devices[i], prop, val)

                            elif dtype == DeviceType.BusDevice:
                                # check if the bus is in the dictionary...
                                if df[prop].values[i] in elements_dict[DeviceType.BusDevice].keys():

                                    parent_bus = elements_dict[DeviceType.BusDevice][df[prop].values[i]]
                                    setattr(devices[i], prop, parent_bus)

                                    # add the device to the bus
                                    if template_elm.device_type != DeviceType.BranchDevice:
                                        parent_bus.add_device(devices[i])

                                else:
                                    circuit.logger.append('Bus not found: ' + str(df[prop].values[i]))

                            else:
                                val = dtype(df[prop].values[i])
                                setattr(devices[i], prop, val)

                        # search the profiles in the data and assign them
                        if prop in template_elm.properties_with_profile.keys():

                            # get the profile property
                            prop_prof = template_elm.properties_with_profile[prop]

                            # build the profile property file-name to get it from the data
                            profile_name = key + '_' + prop_prof

                            if profile_name in data.keys():

                                # get the profile DataFrame
                                dfp = data[profile_name]

                                # for each object, set the profile
                                for i in range(dfp.shape[1]):
                                    profile = dfp.values[:, i]
                                    setattr(devices[i], prop_prof, profile.astype(dtype))

                            else:
                                circuit.logger.append(prop + ' profile was not found in the data')

                    else:
                        circuit.logger.append(prop + ' of object type ' + str(template_elm.device_type) +
                                              ' not found in the input data')
            else:
                # no objects of this type
                pass

            # ensure profiles existence
            if circuit.time_profile is not None:
                for i in range(df.shape[0]):
                    devices[i].ensure_profiles_exist(circuit.time_profile)

            # add the objects to the circuit (buses, branches ot template types)
            if template_elm.device_type == DeviceType.BusDevice:
                circuit.buses = devices

            elif template_elm.device_type == DeviceType.BranchDevice:
                circuit.branches = devices

            elif template_elm.device_type == DeviceType.TowerDevice:
                circuit.overhead_line_types = devices

            elif template_elm.device_type == DeviceType.TransformerTypeDevice:
                circuit.transformer_types = devices

            elif template_elm.device_type == DeviceType.UnderGroundLineDevice:
                circuit.underground_cable_types = devices

            elif template_elm.device_type == DeviceType.SequenceLineDevice:
                circuit.sequence_line_types = devices

            elif template_elm.device_type == DeviceType.WireDevice:
                circuit.wire_types = devices

        else:
            circuit.logger.append('The data does not contain information about the objects of type ' + str(key))

    # fill in wires into towers ----------------------------------------------------------------------------------------
    if 'tower_wires' in data.keys():
        df = data['tower_wires']

        for i in range(df.shape[0]):
            tower_name = df['tower_name'].values[i]
            wire_name = df['wire_name'].values[i]

            if (tower_name in elements_dict[DeviceType.TowerDevice].keys()) and \
                    (wire_name in elements_dict[DeviceType.WireDevice].keys()):

                tower = elements_dict[DeviceType.TowerDevice][tower_name]
                wire = elements_dict[DeviceType.WireDevice][wire_name]
                xpos = df['xpos'].values[i]
                ypos = df['ypos'].values[i]
                phase = df['phase'].values[i]

                w = WireInTower(wire=wire, xpos=xpos, ypos=ypos, phase=phase)
                tower.wires_in_tower.append(w)

    # Other actions ----------------------------------------------------------------------------------------------------
    circuit.logger += circuit.apply_all_branch_types()

    return circuit


if __name__ == '__main__':
    from GridCal.Engine.IO.file_handler import FileOpen, FileSave

    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
    # fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39_1W.gridcal'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Some distribution grid.gridcal'

    main_circuit = FileOpen(fname).open()

    FileSave(main_circuit, 'file.gridcal').save()
