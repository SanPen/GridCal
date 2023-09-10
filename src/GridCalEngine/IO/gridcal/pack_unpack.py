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

from typing import Dict
import pandas as pd
import numpy as np
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Core.Devices as dev
from GridCalEngine.Core.Devices import DeviceType
from GridCalEngine.Core.Devices.enumerations import DiagramType


def get_objects_dictionary():
    """
    creates a dictionary with the types and the circuit objects
    :return: Dictionary instance
    """

    # this list must be sorted in dependency order so that the
    # loading algorithm is able to find the object substitutions
    object_types = {'area': dev.Area(),

                    'zone': dev.Zone(),

                    'substation': dev.Substation(),

                    'country': dev.Country(),

                    'technology': dev.Technology(),

                    'fuel': dev.Fuel(),

                    'emission': dev.EmissionGas(),

                    'bus': dev.Bus(),

                    'load': dev.Load(),

                    'static_generator': dev.StaticGenerator(),

                    'battery': dev.Battery(),

                    'generator': dev.Generator(),

                    'shunt': dev.Shunt(),

                    'wires': dev.Wire(),

                    'overhead_line_types': dev.OverheadLineType(),

                    'underground_cable_types': dev.UndergroundLineType(),

                    'sequence_line_types': dev.SequenceLineType(),

                    'transformer_types': dev.TransformerType(),

                    'branch': dev.Branch(),

                    'transformer2w': dev.Transformer2W(),

                    'windings': dev.Winding(),

                    'transformer3w': dev.Transformer3W(),

                    'line': dev.Line(),

                    'dc_line': dev.DcLine(None, None),

                    'hvdc': dev.HvdcLine(),

                    'vsc': dev.VSC(None, None),

                    'upfc': dev.UPFC(None, None),

                    'contingency_group': dev.ContingencyGroup(),

                    'contingency': dev.Contingency(),

                    'investments_group': dev.InvestmentsGroup(),

                    'investment': dev.Investment(),

                    'generator_technology': dev.GeneratorTechnology(),

                    'generator_fuel': dev.GeneratorFuel(),

                    'generator_emission': dev.GeneratorEmission(),

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

    # increase the model version
    circuit.model_version += 1

    obj.append(['ModelVersion', str(circuit.model_version)])
    obj.append(['UserName', str(circuit.user_name)])
    obj.append(['program', 'GridCal'])

    dfs['config'] = pd.DataFrame(data=obj, columns=['Property', 'Value'], dtype=str)

    # get the master time profile
    T = circuit.time_profile

    ########################################################################################################
    # retrieve buses information that is necessary
    ########################################################################################################
    # names_count = dict()
    if len(circuit.buses) > 0:
        for elm in circuit.buses:
            elm.ensure_area_objects(circuit)
            elm.ensure_profiles_exist(T)
            elm.retrieve_graphic_position()

    ########################################################################################################
    # declare objects to iterate  name: [sample object, list of objects, headers]
    ########################################################################################################
    object_types = get_objects_dictionary()

    # forget abut the Branch object when saving, now we have lines and transformers separated in their own lists
    del object_types['branch']

    ########################################################################################################
    # generic object iteration
    ########################################################################################################
    for object_type_name, object_sample in object_types.items():

        headers = object_sample.editable_headers.keys()

        lists_of_objects = circuit.get_elements_by_type(object_sample.device_type)

        obj = list()
        profiles = dict()
        object_idtags = list()
        if len(lists_of_objects) > 0:

            for k, elm in enumerate(lists_of_objects):

                # get the object normal information
                obj.append(elm.get_save_data())
                object_idtags.append(elm.idtag)

                if T is not None:
                    nt = len(T)
                    if nt > 0:

                        elm.ensure_profiles_exist(T)

                        for profile_property in object_sample.properties_with_profile.values():

                            # get the array
                            arr = getattr(elm, profile_property)

                            if profile_property not in profiles.keys():
                                # create the profile
                                profiles[profile_property] = np.zeros((nt, len(lists_of_objects)), dtype=arr.dtype)

                            # copy the object profile to the array of profiles
                            profiles[profile_property][:, k] = arr

            # convert the objects' list to an array
            dta = np.array(obj)
        else:
            # declare an empty array
            dta = np.zeros((0, len(headers)))

        # declare the DataFrames for the normal data
        dfs[object_type_name] = pd.DataFrame(data=dta, columns=list(headers))

        # create the profiles' DataFrames
        for prop, data in profiles.items():
            dfs[object_type_name + '_' + prop] = pd.DataFrame(data=data, columns=object_idtags, index=T)

    # towers and wires -------------------------------------------------------------------------------------------------
    # because each tower contains a reference to a number of wires, these relations need to be stored as well
    associations = list()
    for tower in circuit.overhead_line_types:
        for wire in tower.wires_in_tower:
            associations.append([tower.name, wire.name, wire.xpos, wire.ypos, wire.phase])

    dfs['tower_wires'] = pd.DataFrame(data=associations, columns=['tower_name', 'wire_name', 'xpos', 'ypos', 'phase'])

    # Time -------------------------------------------------------------------------------------------------------------

    if circuit.time_profile is not None:
        if isinstance(circuit.time_profile, pd.DatetimeIndex):
            time_df = pd.DataFrame(data=circuit.time_profile.values, columns=['Time'])
        else:
            time_df = pd.DataFrame(data=circuit.time_profile, columns=['Time'])
        dfs['time'] = time_df

    return dfs


def data_frames_to_circuit(data: Dict, logger: Logger = Logger()):
    """
    Interpret data dictionary
    :param data: dictionary of data frames
    :param logger: Logger to register events
    :return: MultiCircuit instance
    """
    # create circuit
    circuit = MultiCircuit()

    if 'name' in data.keys():
        circuit.name = str(data['name'])
        if circuit.name == 'nan':
            circuit.name = ''

    # set the base magnitudes
    if 'baseMVA' in data.keys():
        circuit.Sbase = data['baseMVA']

    # Set comments
    if 'Comments' in data.keys():
        circuit.comments = str(data['Comments'])
        if circuit.comments == 'nan':
            circuit.comments = ''

    if 'ModelVersion' in data.keys():
        circuit.model_version = int(data['ModelVersion'])

    if 'UserName' in data.keys():
        circuit.user_name = data['UserName']

    # dictionary of objects to iterate
    object_types = get_objects_dictionary()

    circuit.logger = Logger()

    # time profile -----------------------------------------------------------------------------------------------------
    if 'time' in data.keys():
        time_df = data['time']
        circuit.time_profile = pd.to_datetime(time_df.values[:, 0], dayfirst=True, format='mixed')
    else:
        circuit.time_profile = None

    # dictionary of dictionaries by element type
    # elements_dict[DataType][element_name] = actual object
    elements_dict = dict()
    elements_dict_by_name = dict()

    # ------------------------------------------------------------------------------------------------------------------
    # for each element type...
    for key, template_elm in object_types.items():

        if key in data.keys():

            # get the DataFrame
            df = data[key]

            # create the objects ...
            devices = list()
            devices_dict = dict()
            if 'idtag' in df.columns.values:
                for i in range(df.shape[0]):

                    elm = type(template_elm)()
                    idtag = df['idtag'].values[i]

                    # create the buses dictionary, this works because the bus is the first key in "object_types"
                    devices_dict[idtag] = elm

                    # add the device to the elements
                    devices.append(elm)
            else:
                for i in range(df.shape[0]):

                    elm = type(template_elm)()
                    idtag = df['name'].values[i]

                    # create the buses dictionary, this works because the bus is the first key in "object_types"
                    devices_dict[idtag] = elm

                    # add the device to the elements
                    devices.append(elm)

            elements_dict[template_elm.device_type] = devices_dict

            # fill in the objects
            if df.shape[0] > 0:

                # for each property ...
                for object_property_name, gc_prop in template_elm.editable_headers.items():

                    # if the object property exists in the data file, set all the object's property
                    if object_property_name in df.columns.values:

                        # get the type converter
                        dtype = gc_prop.tpe

                        # for each object, set the property
                        for i in range(df.shape[0]):

                            # convert and assign the data
                            if dtype is None:
                                val = df[object_property_name].values[i]
                                setattr(devices[i], object_property_name, val)

                            elif dtype in [DeviceType.SubstationDevice,
                                           DeviceType.AreaDevice,
                                           DeviceType.ZoneDevice,
                                           DeviceType.CountryDevice,
                                           DeviceType.Technology,
                                           DeviceType.ContingencyGroupDevice,
                                           DeviceType.InvestmentsGroupDevice,
                                           DeviceType.FuelDevice,
                                           DeviceType.EmissionGasDevice,
                                           DeviceType.GeneratorDevice,
                                           ]:

                                """
                                This piece is to assign the objects matching the Area, Substation, Zone and Country
                                The cases may be:
                                a) there is a matching id tag -> ok, assign it
                                b) the value is a string -> create the relevant object, 
                                                            make sure it is not repeated by name
                                                            inset the object in its matching object dictionary
                                """

                                # search for the Substation, Area, Zone or Country matching object and assign the object
                                # this is the stored string (either idtag or name...)
                                val = str(df[object_property_name].values[i])

                                if dtype not in elements_dict.keys():
                                    elements_dict[dtype] = dict()

                                if dtype not in elements_dict_by_name.keys():
                                    elements_dict_by_name[dtype] = dict()

                                if val in elements_dict[dtype].keys():
                                    # the grouping exists as object, use it
                                    grouping = elements_dict[dtype][val]
                                else:
                                    # create the grouping

                                    if val in elements_dict_by_name[dtype].keys():
                                        grouping = elements_dict_by_name[dtype][val]

                                    else:
                                        grouping = type(object_types[dtype.value.lower()])(name=val)
                                        elements_dict[dtype][grouping.idtag] = grouping

                                        # store also by name
                                        elements_dict_by_name[dtype][grouping.name] = grouping

                                # set the object
                                setattr(devices[i], object_property_name, grouping)

                            elif dtype == DeviceType.BusDevice:

                                # check if the bus is in the dictionary...
                                if df[object_property_name].values[i] in elements_dict[DeviceType.BusDevice].keys():

                                    parent_bus: dev.Bus = elements_dict[DeviceType.BusDevice][df[object_property_name].values[i]]
                                    setattr(devices[i], object_property_name, parent_bus)

                                    # add the device to the bus
                                    if template_elm.device_type in [DeviceType.LoadDevice,
                                                                    DeviceType.GeneratorDevice,
                                                                    DeviceType.BatteryDevice,
                                                                    DeviceType.StaticGeneratorDevice,
                                                                    DeviceType.ShuntDevice,
                                                                    DeviceType.ExternalGridDevice]:

                                        parent_bus.add_device(devices[i])

                                else:
                                    circuit.logger.add_error('Bus not found', str(df[object_property_name].values[i]))

                            elif dtype in [DeviceType.TransformerTypeDevice,  # template types mostly
                                           DeviceType.SequenceLineDevice,
                                           DeviceType.OverheadLineTypeDevice,
                                           DeviceType.WindingDevice]:

                                if df[object_property_name].values[i] in elements_dict[dtype].keys():

                                    # get the actual template and set it
                                    val = elements_dict[dtype][df[object_property_name].values[i]]
                                    setattr(devices[i], object_property_name, val)

                                else:
                                    circuit.logger.add_error(dtype.value + ' type not found',
                                                             str(df[object_property_name].values[i]))

                            elif dtype == bool:
                                # regular types (int, str, float, etc...)
                                val = df[object_property_name].values[i]
                                if val == 'False':
                                    setattr(devices[i], object_property_name, False)
                                elif val == 'True':
                                    setattr(devices[i], object_property_name, True)
                                else:
                                    setattr(devices[i], object_property_name, bool(val))

                            elif dtype == str:
                                val = dtype(df[object_property_name].values[i]).replace('nan', '')
                                setattr(devices[i], object_property_name, val)

                            else:
                                # regular types (int, str, float, etc...)
                                try:
                                    val = dtype(df[object_property_name].values[i])
                                    setattr(devices[i], object_property_name, val)
                                except ValueError:
                                    circuit.logger.add_error('type error', devices[i].name, df[object_property_name].values[i])

                        # search the profiles in the data and assign them
                        if object_property_name in template_elm.properties_with_profile.keys():

                            # get the profile property
                            prop_prof = template_elm.properties_with_profile[object_property_name]

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
                                circuit.logger.add_error('Profile was not found in the data', object_property_name)

                    else:
                        circuit.logger.add_error(object_property_name + ' of object type ' + str(template_elm.device_type) +
                                                 ' not found in the input data')
            else:
                # no objects of this type
                pass

            # ensure profiles existence
            if circuit.time_profile is not None:
                for i in range(df.shape[0]):
                    devices[i].ensure_profiles_exist(circuit.time_profile)

            # add the objects to the circuit (buses, Branches ot template types)
            if template_elm.device_type == DeviceType.BusDevice:
                circuit.buses = devices

            # elif template_elm.device_type == DeviceType.SubstationDevice:
            #     circuit.substations = devices
            #
            # elif template_elm.device_type == DeviceType.AreaDevice:
            #     circuit.areas = devices
            #
            # elif template_elm.device_type == DeviceType.ZoneDevice:
            #     circuit.zones = devices
            #
            # elif template_elm.device_type == DeviceType.CountryDevice:
            #     circuit.countries = devices

            elif template_elm.device_type == DeviceType.BranchDevice:
                for d in devices:
                    circuit.add_branch(d)  # each branch needs to be converted accordingly

            elif template_elm.device_type == DeviceType.LineDevice:
                for d in devices:
                    circuit.add_line(d, logger=logger)  # this is done to detect those lines that should be transformers
                # circuit.lines = devices

            elif template_elm.device_type == DeviceType.DCLineDevice:
                circuit.dc_lines = devices

            elif template_elm.device_type == DeviceType.Transformer2WDevice:
                circuit.transformers2w = devices

            elif template_elm.device_type == DeviceType.WindingDevice:
                circuit.windings = devices

            elif template_elm.device_type == DeviceType.Transformer3WDevice:
                circuit.transformers3w = devices

            elif template_elm.device_type == DeviceType.HVDCLineDevice:
                circuit.hvdc_lines = devices

            elif template_elm.device_type == DeviceType.UpfcDevice:
                circuit.upfc_devices = devices

            elif template_elm.device_type == DeviceType.VscDevice:
                for elm in devices:
                    elm.correct_buses_connection()
                circuit.vsc_devices = devices

            elif template_elm.device_type == DeviceType.OverheadLineTypeDevice:
                circuit.overhead_line_types = devices

            elif template_elm.device_type == DeviceType.TransformerTypeDevice:
                circuit.transformer_types = devices

            elif template_elm.device_type == DeviceType.UnderGroundLineDevice:
                circuit.underground_cable_types = devices

            elif template_elm.device_type == DeviceType.SequenceLineDevice:
                circuit.sequence_line_types = devices

            elif template_elm.device_type == DeviceType.WireDevice:
                circuit.wire_types = devices

            elif template_elm.device_type == DeviceType.Technology:
                circuit.technologies = devices

            elif template_elm.device_type == DeviceType.ContingencyGroupDevice:
                circuit.contingency_groups = devices

            elif template_elm.device_type == DeviceType.ContingencyDevice:
                circuit.contingencies = devices

            elif template_elm.device_type == DeviceType.InvestmentsGroupDevice:
                circuit.investments_groups = devices

            elif template_elm.device_type == DeviceType.InvestmentDevice:
                circuit.investments = devices

            elif template_elm.device_type == DeviceType.FuelDevice:
                circuit.fuels = devices

            elif template_elm.device_type == DeviceType.EmissionGasDevice:
                circuit.emission_gases = devices

            elif template_elm.device_type == DeviceType.GeneratorTechnologyAssociation:
                circuit.generators_technologies = devices

            elif template_elm.device_type == DeviceType.GeneratorFuelAssociation:
                circuit.generators_fuels = devices

            elif template_elm.device_type == DeviceType.GeneratorEmissionAssociation:
                circuit.generators_emissions = devices

        else:
            circuit.logger.add_error('The data does not contain information about the type', str(key))

    # fill in wires into towers ----------------------------------------------------------------------------------------
    if 'tower_wires' in data.keys():
        df = data['tower_wires']

        for i in range(df.shape[0]):
            tower_name = df['tower_name'].values[i]
            wire_name = df['wire_name'].values[i]

            if (tower_name in elements_dict[DeviceType.OverheadLineTypeDevice].keys()) and \
                    (wire_name in elements_dict[DeviceType.WireDevice].keys()):

                tower = elements_dict[DeviceType.OverheadLineTypeDevice][tower_name]
                wire = elements_dict[DeviceType.WireDevice][wire_name]
                xpos = df['xpos'].values[i]
                ypos = df['ypos'].values[i]
                phase = df['phase'].values[i]

                w = dev.WireInTower(wire=wire, xpos=xpos, ypos=ypos, phase=phase)
                tower.add_wire(w)

    # create diagrams --------------------------------------------------------------------------------------------------
    if 'diagrams' in data.keys():

        if len(data['diagrams']):
            obj_dict = circuit.gat_all_elemnts_dict_by_type()

            for diagram_dict in data['diagrams']:

                if diagram_dict['type'] == DiagramType.BusBranch.value:
                    diagram = dev.BusBranchDiagram()
                    diagram.parse_data(data=diagram_dict, obj_dict=obj_dict)
                    circuit.add_diagram(diagram)

                elif diagram_dict['type'] == DiagramType.NodeBreaker.value:
                    diagram = dev.NodeBreakerDiagram()
                    diagram.parse_data(data=diagram_dict, obj_dict=obj_dict)
                    circuit.add_diagram(diagram)

                elif diagram_dict['type'] == DiagramType.SubstationLineMap.value:
                    diagram = dev.MapDiagram()
                    diagram.parse_data(data=diagram_dict, obj_dict=obj_dict)
                    circuit.add_diagram(diagram)
                else:
                    print('unrecognized diagram', diagram_dict['type'])

    # Other actions ----------------------------------------------------------------------------------------------------
    circuit.logger += circuit.apply_all_branch_types()

    # Add the groups ---------------------------------------------------------------------------------------------------
    if DeviceType.SubstationDevice in elements_dict.keys():
        circuit.substations = list(elements_dict[DeviceType.SubstationDevice].values())

    if DeviceType.AreaDevice in elements_dict.keys():
        circuit.areas = list(elements_dict[DeviceType.AreaDevice].values())

    if DeviceType.ZoneDevice in elements_dict.keys():
        circuit.zones = list(elements_dict[DeviceType.ZoneDevice].values())

    if DeviceType.CountryDevice in elements_dict.keys():
        circuit.countries = list(elements_dict[DeviceType.CountryDevice].values())

    # if DeviceType.Technology in elements_dict.keys():
    #     circuit.technologies = list(elements_dict[DeviceType.Technology].values())
    #
    # if DeviceType.ContingencyGroupDevice in elements_dict.keys():
    #     circuit.contingency_groups = list(elements_dict[DeviceType.ContingencyGroupDevice].values())
    #
    # if DeviceType.ContingencyDevice in elements_dict.keys():
    #     circuit.contingencies = list(elements_dict[DeviceType.ContingencyDevice].values())

    return circuit

