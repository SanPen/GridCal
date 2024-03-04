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
import math
from typing import Dict, Union, List, Tuple, Any
import pandas as pd
import numpy as np
from enum import EnumMeta as EnumType
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.Parents.editable_device import GCProp
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.sparse_array import SparseArray
from GridCalEngine.enumerations import DiagramType, DeviceType


def get_objects_dictionary() -> Dict[str, dev.EditableDevice]:
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

                    'bus_bar': dev.BusBar(),

                    'connectivity node': dev.ConnectivityNode(),

                    'load': dev.Load(),

                    'static_generator': dev.StaticGenerator(),

                    'battery': dev.Battery(),

                    'generator': dev.Generator(),

                    'shunt': dev.Shunt(),

                    'linear_shunt': dev.ControllableShunt(),

                    'current_injection': dev.CurrentInjection(),

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

                    'fluid_node': dev.FluidNode(),
                    'fluid_path': dev.FluidPath(),
                    'fluid_turbine': dev.FluidTurbine(),
                    'fluid_pump': dev.FluidPump(),
                    'fluid_p2x': dev.FluidP2x(),

                    }

    return object_types


def gather_model_as_data_frames(circuit: MultiCircuit, legacy: bool = False) -> Dict[str, pd.DataFrame]:
    """
    Pack the circuit information into tables (DataFrames)
    :param circuit: MultiCircuit instance
    :param legacy: Generate the legacy object DataFrames
    :return: dictionary of DataFrames
    """
    dfs = dict()

    # configuration ################################################################################################
    obj = list()
    obj.append(['BaseMVA', circuit.Sbase])
    obj.append(['Version', 5])
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
            # elm.ensure_area_objects(circuit)
            elm.ensure_profiles_exist(T)

    ########################################################################################################
    # declare objects to iterate  name: [sample object, list of objects, headers]
    ########################################################################################################
    object_types = get_objects_dictionary()

    # forget abut the Branch object when saving, now we have lines and transformers separated in their own lists
    del object_types['branch']

    ########################################################################################################
    # generic object iteration
    ########################################################################################################
    if legacy:
        for object_type_name, object_sample in object_types.items():

            headers = object_sample.registered_properties.keys()

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

                            for property_name, profile_property in object_sample.properties_with_profile.items():

                                # get the array
                                profile = elm.get_profile(magnitude=property_name)

                                if profile_property not in profiles.keys():
                                    # create the profile
                                    profiles[profile_property] = np.zeros(shape=(nt, len(lists_of_objects)),
                                                                          dtype=profile.dtype)

                                # copy the object profile to the array of profiles
                                profiles[profile_property][:, k] = profile.toarray()

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

        dfs['tower_wires'] = pd.DataFrame(data=associations,
                                          columns=['tower_name', 'wire_name', 'xpos', 'ypos', 'phase'])

        # Time ---------------------------------------------------------------------------------------------------------

        if circuit.time_profile is not None:
            if isinstance(circuit.time_profile, pd.DatetimeIndex):
                time_df = pd.DataFrame(data=circuit.time_profile.values, columns=['Time'])
            else:
                time_df = pd.DataFrame(data=circuit.time_profile, columns=['Time'])
            dfs['time'] = time_df

    return dfs


def profile_todict(profile: Profile) -> Dict[str, str]:
    """
    Get a dictionary representation of the profile
    :return:
    """
    s = profile.size()

    if s > 0:
        if profile.is_sparse:
            return {
                'is_sparse': True,
                'size': s,
                'default': profile.sparse_array.default_value,
                'sparse_data': {
                    'map': profile.sparse_array.get_map()
                }
            }
        else:
            return {
                'is_sparse': False,
                'size': s,
                'default': profile.default_value,
                'dense_data': profile.dense_array.tolist(),
            }
    else:
        return {
                'is_sparse': True,
                'size': s,
                'default': profile.default_value
                if profile.sparse_array is None else profile.sparse_array.default_value,
                'sparse_data': {
                    'map': dict()
                }
            }


def profile_todict_idtag(profile: Profile) -> Dict[str, str]:
    """
    Get a dictionary representation of the profile
    :return:
    """
    default = profile.default_value.idtag if profile.default_value else "None"

    if profile.is_sparse:
        return {
            'is_sparse': profile.is_sparse,
            'size': profile.size(),
            'default': default,
            'sparse_data': {
                'map': {key: val.idtag for key, val in profile.sparse_array.get_map().items()}
                       if profile.sparse_array else dict()
            }
        }
    else:
        return {
            'is_sparse': profile.is_sparse,
            'size': profile.size(),
            'default': default,
            'dense_data': [e.idtag for e in profile.dense_array] if profile.dense_array else list(),
        }


def profile_todict_str(profile: Profile) -> Dict[str, str]:
    """
    Get a dictionary representation of the profile
    :return:
    """
    s = profile.size()

    if s > 0:
        if profile.is_sparse:
            return {
                'is_sparse': True,
                'size': s,
                'default': str(profile.default_value),
                'sparse_data': {
                    'map': {key: str(val) for key, val in profile.sparse_array.get_map().items()}
                }
            }
        else:
            return {
                'is_sparse': False,
                'size': s,
                'default': str(profile.default_value),
                'dense_data': [str(e) for e in profile.dense_array],
            }
    else:
        # empty profile
        return {
            'is_sparse': True,
            'size': s,
            'default': str(profile.default_value),
            'sparse_data': {
                'map': dict()
            }
        }


def get_profile_from_dict(data: Dict[str, Union[str, Union[Any, Dict[str, Any]]]],
                          collection: Union[None, Dict[str, Any]] = None) -> Profile:
    """
    Create a profile from json dict data
    :param data: Json dict data
    :param collection: if the collection is provided, it will be used to convert idtags into objects
    :return: Profile
    """
    default_value = data['default']
    profile = Profile(default_value=default_value, is_sparse=bool(data['is_sparse']))

    if profile.is_sparse:
        sp_data = data['sparse_data']
        profile._sparse_array = SparseArray()
        if collection is None:
            map_data = {int(key): val for key, val in sp_data['map'].items()}

        else:
            default_value = collection.get(data['default'], default_value)
            map_data = {int(key): collection.get(val, default_value) for key, val in sp_data['map'].items()}

        profile.sparse_array.create_from_dict(default_value=default_value, size=data['size'], map=map_data)
    else:

        if collection is None:
            arr = data['dense_data']
        else:
            arr = [collection.get(i, default_value) for i in data['dense_data']]
        profile._dense_array = np.array(arr)
    profile.set_initialized()
    return profile


def gridcal_object_to_json(elm: dev.EditableDevice) -> Dict[str, str]:
    """

    :param elm:
    :return:
    """

    data = dict()
    for name, prop in elm.registered_properties.items():
        obj = elm.get_snapshot_value(prop=prop)

        if prop.tpe in [str, float, int, bool]:
            data[name] = obj

            if prop.has_profile():
                data[name + '_prof'] = profile_todict(elm.get_profile_by_prop(prop=prop))

        elif prop.tpe == DeviceType.GeneratorQCurve:
            data[name] = obj.str()

        else:
            # if the object is not of a primary type, get the idtag instead
            if hasattr(obj, 'idtag'):
                data[name] = obj.idtag

                if prop.has_profile():
                    data[name + '_prof'] = profile_todict_idtag(elm.get_profile_by_prop(prop=prop))

            else:
                # some data types might not have the idtag, ten just use the str method
                data[name] = str(obj)

                if prop.has_profile():
                    data[name + '_prof'] = profile_todict_str(elm.get_profile_by_prop(prop=prop))

    return data


def gather_model_as_jsons(circuit: MultiCircuit) -> Dict[str, Dict[str, str]]:
    """

    :param circuit:
    :return:
    """
    data: Dict[str, Dict[str, str]] = dict()

    # declare objects to iterate  name: [sample object, list of objects, headers]
    object_types = get_objects_dictionary()

    del object_types['branch']

    # generic object iteration
    for object_type_name, object_sample in object_types.items():

        object_json = list()

        lists_of_objects = circuit.get_elements_by_type(object_sample.device_type)

        if len(lists_of_objects) > 0:

            for k, elm in enumerate(lists_of_objects):
                obj_data = gridcal_object_to_json(elm)
                object_json.append(obj_data)

        data[object_type_name] = object_json

    # time
    unix_time = circuit.get_unix_time()
    data['time'] = {'unix': unix_time.tolist(),
                    'prob': list(np.ones(len(unix_time)))}

    return data


def search_property(template_elm: dev.EditableDevice,
                    old_props_dict: Dict[str, str],
                    property_to_search: str,
                    logger: Logger) -> Union[GCProp, None]:
    """
    Search for a property name in the template object registered properties and their old names
    :param template_elm: Device to loo into
    :param old_props_dict: Dictionary matching the old names with their current counterpart
    :param property_to_search: property name to search
    :param logger: Logger
    :return: GCProp or None if not found
    """
    # search the property in the object headers
    gc_prop = template_elm.registered_properties.get(property_to_search, None)

    if gc_prop is None:
        # the property is not in the headers, search in the the old list
        current_prop_name = old_props_dict.get(property_to_search, None)

        if current_prop_name:

            logger.add_info('The file property was updated in the data model',
                            device=str(template_elm.device_type),
                            value=property_to_search)

            gc_prop = template_elm.registered_properties.get(current_prop_name, None)
            return gc_prop
        else:
            # the property does not exists in the registries, this is a bug
            logger.add_error('the property does not exists in the registries',
                             device=str(template_elm.device_type),
                             value=property_to_search)
            return None
    else:
        return gc_prop


def look_for_property(elm: dev.EditableDevice, property_name) -> Union[GCProp, None]:
    """

    :param elm:
    :param property_name:
    :return:
    """
    device_property_definition: GCProp = elm.registered_properties.get(property_name, None)

    if device_property_definition:
        # the property of the file exists directly
        return device_property_definition
    else:
        # the property does not exists directly, look in the older properties
        for name, prop in elm.registered_properties.items():
            if property_name in prop.old_names:
                return prop

        return None  # if we reach here, it wasn't found


def valid_value(val) -> bool:
    """

    :param val:
    :return:
    """
    if isinstance(val, str):
        if val == 'nan':
            return False
        if val == '':
            return False
    if isinstance(val, float):
        if math.isnan(val):
            return False
        if math.isinf(val):
            return False
    return True


def parse_object_type_from_dataframe(main_df: pd.DataFrame,
                                     template_elm: dev.EditableDevice,
                                     elements_dict_by_type: Dict[DeviceType, Dict[str, dev.EditableDevice]],
                                     time_profile: pd.DatetimeIndex,
                                     object_type_key: str,
                                     data: Dict[str, Union[float, str, pd.DataFrame]],
                                     logger: Logger) -> Tuple[List[dev.EditableDevice], Dict[str, dev.EditableDevice]]:
    """
    Convert a DataFrame to a list of GridCal devices
    :param main_df: DataFrame to convert
    :param template_elm: Element to use as template for conversion
    :param elements_dict_by_type: Dictionary of devices grouped by type used to look for referenced objects
                                    elements_dict_by_type[DeviceType][idtag] -> device
    :param time_profile: Master time profile
    :param object_type_key: Object type naming to find the profile
    :param data: Complete data collection to find the profiles
    :param logger: Logger instance
    :return: devices, devices_dict
    """
    # dictionary to be filled with this type of objects
    devices_dict: Dict[str, dev.EditableDevice] = dict()
    devices: List[dev.EditableDevice] = list()

    # parse each object of the dataframe
    for i, row in main_df.iterrows():

        # create device
        idtag = row.get('idtag', None)
        elm = type(template_elm)(idtag=idtag)

        # ensure the profiles existence
        if time_profile is not None:
            elm.ensure_profiles_exist(index=time_profile)

        # parse each property of the row
        for property_name_, property_value in row.items():

            property_name = str(property_name_)

            if property_name != 'idtag':  # idtag was set already
                gc_prop: GCProp = look_for_property(elm=elm, property_name=property_name)
                if gc_prop is not None:

                    if valid_value(property_value):

                        # the property of the file exists, parse it

                        if isinstance(gc_prop.tpe, DeviceType):

                            if gc_prop.tpe == DeviceType.GeneratorQCurve:
                                val = dev.GeneratorQCurve()
                                val.parse(property_value)
                                elm.set_snapshot_value(gc_prop.name, val)

                                if gc_prop.has_profile():
                                    elm.get_profile(magnitude=gc_prop.name).fill(val)

                            else:
                                # we must look for the refference in elements_dict
                                collection = elements_dict_by_type.get(gc_prop.tpe, None)

                                if collection is not None:
                                    ref_idtag = str(property_value)
                                    ref_elm = collection.get(ref_idtag, None)

                                    if ref_elm is not None:
                                        elm.set_snapshot_value(gc_prop.name, ref_elm)

                                        if gc_prop.has_profile():
                                            elm.get_profile(magnitude=gc_prop.name).fill(ref_elm)

                                    else:
                                        logger.add_error("Could not locate refference",
                                                         device=row.get('idtag', 'not provided'),
                                                         device_class=template_elm.device_type.value,
                                                         device_property=gc_prop.name,
                                                         value=ref_idtag)
                                else:
                                    logger.add_error("No device of the refferenced type",
                                                     device=row.get('idtag', 'not provided'),
                                                     device_class=template_elm.device_type.value,
                                                     device_property=gc_prop.name,
                                                     value=property_value)

                        elif gc_prop.tpe == str:
                            # set the value directly
                            elm.set_snapshot_value(gc_prop.name, str(property_value))

                            if gc_prop.has_profile():
                                elm.get_profile(magnitude=gc_prop.name).fill(str(property_value))

                        elif gc_prop.tpe == float:
                            # set the value directly
                            elm.set_snapshot_value(gc_prop.name, float(property_value))

                            if gc_prop.has_profile():
                                elm.get_profile(magnitude=gc_prop.name).fill(float(property_value))

                        elif gc_prop.tpe == int:
                            # set the value directly
                            elm.set_snapshot_value(gc_prop.name, int(property_value))

                            if gc_prop.has_profile():
                                elm.get_profile(magnitude=gc_prop.name).fill(int(property_value))

                        elif gc_prop.tpe == bool:
                            # set the value directly
                            elm.set_snapshot_value(gc_prop.name, bool(property_value))

                            if gc_prop.has_profile():
                                elm.get_profile(magnitude=gc_prop.name).fill(bool(property_value))

                        elif isinstance(gc_prop.tpe, EnumType):

                            try:
                                val = gc_prop.tpe(property_value)
                                elm.set_snapshot_value(gc_prop.name, val)

                                if gc_prop.has_profile():
                                    elm.get_profile(magnitude=gc_prop.name).fill(val)

                            except ValueError:
                                logger.add_error(f'Cannot cast value to {gc_prop.tpe}',
                                                 device=elm.name,
                                                 value=property_value)

                        else:
                            raise Exception(f'Unsupported property type: {gc_prop.tpe}')

                    else:
                        # invalid property value
                        pass

                    # search the profiles in the data and assign them
                    if gc_prop.has_profile() and time_profile is not None:

                        # build the profile property file-name to get it from the data
                        profile_key = object_type_key + '_' + gc_prop.profile_name

                        # get the profile DataFrame
                        dfp = data.get(profile_key, None)

                        if dfp is not None:
                            elm.set_profile(gc_prop, arr=dfp.values[:, i].astype(gc_prop.tpe))

                        else:
                            logger.add_info('No profile for the property', value=gc_prop.name)

                else:
                    # the property does not exists, neither in the old names
                    logger.add_error("File property could not be found",
                                     device=row.get('idtag', 'not provided'),
                                     device_class=template_elm.device_type.value,
                                     device_property=property_name)

        # save the element in the dictionary for later
        devices_dict[elm.idtag] = elm
        devices.append(elm)

    return devices, devices_dict


def searc_property_into_json(json_entry: dict, prop: GCProp):
    """
    Find property in Json entry
    :param json_entry: json of an object
    :param prop: GCProp
    :return: value or None if not found
    """
    
    # search for the main property
    property_value = json_entry.get(prop.name, None)

    if property_value is None:
        
        # if not found, search for an old property
        for p_name in prop.old_names:
            property_value = json_entry.get(p_name, None)
            if property_value is not None:
                return property_value
        
        # we couldn't find the property or the old names...
        return None
            
    else:
        
        # we found the property at first
        return property_value


def search_and_apply_json_profile(json_entry: dict,
                                  gc_prop: GCProp,
                                  elm: dev.EditableDevice,
                                  property_value: Any,
                                  collection: Union[None, Dict[str, Any]] = None) -> None:
    """
    Search fro the property profiles into the json and apply it
    :param json_entry: Json entry of an object
    :param gc_prop: GCProp
    :param elm: THe device to set the profile into
    :param property_value: The snapshot value
    :param collection: if the collection is provided, it will be used to convert idtags into objects
    :return: None
    """
    if gc_prop.has_profile():
        
        # search the profile in the json
        json_profile = json_entry.get(gc_prop.profile_name, None)
        
        if json_profile is None:
            # the profile was not found, so we fill it with the default stuff
            elm.get_profile(magnitude=gc_prop.name).fill(property_value)
        else:
            profile = get_profile_from_dict(data=json_profile, collection=collection)
            elm.set_profile(prop=gc_prop, arr=profile)


def parse_object_type_from_json(template_elm: dev.EditableDevice,
                                data_list: List[Dict[str, Dict[str, str]]],
                                elements_dict_by_type: Dict[DeviceType, Dict[str, dev.EditableDevice]],
                                time_profile: pd.DatetimeIndex,
                                logger: Logger):
    """

    :param template_elm:
    :param data_list:
    :param elements_dict_by_type:
    :param time_profile:
    :param logger:
    :return:
    """
    # dictionary to be filled with this type of objects
    devices_dict: Dict[str, dev.EditableDevice] = dict()
    devices: List[dev.EditableDevice] = list()

    for json_entry in data_list:
        idtag = json_entry['idtag']
        elm = type(template_elm)(idtag=idtag)

        # ensure the profiles existence
        if time_profile is not None:
            elm.ensure_profiles_exist(index=time_profile)

        # for property_name_, property_value in json_entry.items():
        for property_name, gc_prop in template_elm.registered_properties.items():

            # search for the property in the json
            property_value = searc_property_into_json(json_entry, gc_prop)
            
            if property_value is not None:                

                if property_name != 'idtag':  # idtag was set already
                    # gc_prop: GCProp = look_for_property(elm=elm, property_name=property_name)
    
                    if gc_prop is not None:
    
                        if valid_value(property_value):
    
                            if isinstance(gc_prop.tpe, DeviceType):
    
                                if gc_prop.tpe == DeviceType.GeneratorQCurve:
                                    val = dev.GeneratorQCurve()
                                    val.parse(property_value)
                                    elm.set_snapshot_value(gc_prop.name, val)
                                    search_and_apply_json_profile(json_entry=json_entry,
                                                                  gc_prop=gc_prop,
                                                                  elm=elm,
                                                                  property_value=val)
    
                                else:
                                    # we must look for the refference in elements_dict
                                    collection = elements_dict_by_type.get(gc_prop.tpe, None)
    
                                    if collection is not None:
                                        ref_idtag = str(property_value)
                                        ref_elm = collection.get(ref_idtag, None)
    
                                        if ref_elm is not None:
                                            elm.set_snapshot_value(gc_prop.name, ref_elm)
                                            search_and_apply_json_profile(json_entry=json_entry,
                                                                          gc_prop=gc_prop,
                                                                          elm=elm,
                                                                          property_value=ref_elm,
                                                                          collection=collection)
    
                                        else:
                                            logger.add_error("Could not locate refference",
                                                             device=elm.idtag,
                                                             device_class=template_elm.device_type.value,
                                                             device_property=gc_prop.name,
                                                             value=ref_idtag)
                                    else:
                                        logger.add_error("No device of the refferenced type",
                                                         device=elm.idtag,
                                                         device_class=template_elm.device_type.value,
                                                         device_property=gc_prop.name,
                                                         value=property_value)
    
                            elif gc_prop.tpe == str:
                                # set the value directly
                                val = str(property_value)
                                elm.set_snapshot_value(gc_prop.name, val)
                                search_and_apply_json_profile(json_entry=json_entry,
                                                              gc_prop=gc_prop,
                                                              elm=elm,
                                                              property_value=val)

                            elif gc_prop.tpe == float:
                                # set the value directly
                                val = float(property_value)
                                elm.set_snapshot_value(gc_prop.name, val)
                                search_and_apply_json_profile(json_entry=json_entry,
                                                              gc_prop=gc_prop,
                                                              elm=elm,
                                                              property_value=val)
    
                            elif gc_prop.tpe == int:
                                # set the value directly
                                val = int(property_value)
                                elm.set_snapshot_value(gc_prop.name, val)
                                search_and_apply_json_profile(json_entry=json_entry,
                                                              gc_prop=gc_prop,
                                                              elm=elm,
                                                              property_value=val)
    
                            elif gc_prop.tpe == bool:
                                # set the value directly
                                val = bool(property_value)
                                elm.set_snapshot_value(gc_prop.name, val)
                                search_and_apply_json_profile(json_entry=json_entry,
                                                              gc_prop=gc_prop,
                                                              elm=elm,
                                                              property_value=val)
    
                            elif isinstance(gc_prop.tpe, EnumType):
    
                                try:
                                    val = gc_prop.tpe(property_value)
                                    elm.set_snapshot_value(gc_prop.name, val)
                                    search_and_apply_json_profile(json_entry=json_entry,
                                                                  gc_prop=gc_prop,
                                                                  elm=elm,
                                                                  property_value=val)
    
                                except ValueError:
                                    logger.add_error(f'Cannot cast value to {gc_prop.tpe}',
                                                     device=elm.name,
                                                     value=property_value)
    
                            else:
                                raise Exception(f'Unsupported property type: {gc_prop.tpe}')
    
                        else:
                            # invalid property value
                            pass
                    else:
                        # property not found
                        pass
    
                else:
                    # the property is idtag
                    pass
            else:
                # the object property was not found in the json entry
                pass

        # save the element in the dictionary for later
        devices_dict[elm.idtag] = elm
        devices.append(elm)

    return devices, devices_dict


def parse_gridcal_data(data: Dict[str, Union[str, float, Dict, pd.DataFrame, Dict[str, Any]]],
                       logger: Logger = Logger()) -> MultiCircuit:
    """
    Interpret data dictionary
    :param data: dictionary of data frames and other information
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
    data_model_object_types = get_objects_dictionary()

    # time profile -----------------------------------------------------------------------------------------------------
    if 'time' in data.keys():
        time_df = data['time']
        try:
            circuit.time_profile = pd.to_datetime(time_df.values[:, 0], dayfirst=True, format='mixed')
        except ValueError as err:
            circuit.time_profile = pd.to_datetime(time_df.values[:, 0], dayfirst=True)
    else:
        circuit.time_profile = None

    # dictionary of dictionaries by element type
    elements_dict_by_type = dict()

    # ------------------------------------------------------------------------------------------------------------------
    # Legacy DataFrame processing
    # for each element type...
    for object_type_key, template_elm in data_model_object_types.items():

        # try to get the DataFrame
        df = data.get(object_type_key, None)

        if df is not None:

            # fill in the objects
            if df.shape[0] > 0:

                devices, devices_dict = parse_object_type_from_dataframe(main_df=df,
                                                                         template_elm=template_elm,
                                                                         elements_dict_by_type=elements_dict_by_type,
                                                                         time_profile=circuit.time_profile,
                                                                         object_type_key=object_type_key,
                                                                         data=data,
                                                                         logger=logger)

                # set the dictionary per type for later
                elements_dict_by_type[template_elm.device_type] = devices_dict

                # add the devices to the circuit
                circuit.set_elements_by_type(device_type=template_elm.device_type,
                                             devices=devices,
                                             logger=logger)

            else:
                # no objects of this type
                pass
        else:
            # the file does not contain information for the data type (not a problem...)
            pass

    # ------------------------------------------------------------------------------------------------------------------
    # New way of parsing information from .model files.
    # These files are just .json stored in the model_data inside the zip file
    model_data = data.get('model_data', None)
    if model_data is not None:

        if len(model_data) > 0:

            tdata = model_data.get('time', None)
            if tdata is not None:
                circuit.set_unix_time(arr=tdata['unix'])
            else:
                logger.add_error(msg=f'The file must have time data regardless of the profiles existance')
                circuit.time_profile = None

            # for each element type...
            for object_type_key, template_elm in data_model_object_types.items():

                # query the device type into the data set
                data_list = model_data.get(object_type_key, None)

                if data_list is not None:
                    devices, devices_dict = parse_object_type_from_json(template_elm=template_elm,
                                                                        data_list=data_list,
                                                                        elements_dict_by_type=elements_dict_by_type,
                                                                        time_profile=circuit.time_profile,
                                                                        logger=logger)

                    # set the dictionary per type for later
                    elements_dict_by_type[template_elm.device_type] = devices_dict

                    # add the devices to the circuit
                    circuit.set_elements_by_type(device_type=template_elm.device_type,
                                                 devices=devices,
                                                 logger=logger)
                else:
                    logger.add_warning(msg=f'No data for {object_type_key}')

    # fill in wires into towers ----------------------------------------------------------------------------------------
    if 'tower_wires' in data.keys():
        df = data['tower_wires']

        for i in range(df.shape[0]):
            tower_name = df['tower_name'].values[i]
            wire_name = df['wire_name'].values[i]

            if ((tower_name in elements_dict_by_type[DeviceType.OverheadLineTypeDevice].keys()) and
                    (wire_name in elements_dict_by_type[DeviceType.WireDevice].keys())):
                tower: dev.OverheadLineType = elements_dict_by_type[DeviceType.OverheadLineTypeDevice][tower_name]
                wire: dev.Wire = elements_dict_by_type[DeviceType.WireDevice][wire_name]
                xpos = df['xpos'].values[i]
                ypos = df['ypos'].values[i]
                phase = df['phase'].values[i]

                w = dev.WireInTower(wire=wire, xpos=xpos, ypos=ypos, phase=phase)
                tower.add_wire(w)

    # create diagrams --------------------------------------------------------------------------------------------------
    if 'diagrams' in data.keys():

        if len(data['diagrams']):
            obj_dict = circuit.gat_all_elements_dict_by_type()

            for diagram_dict in data['diagrams']:

                if diagram_dict['type'] == DiagramType.BusBranch.value:
                    diagram = dev.BusBranchDiagram()
                    diagram.parse_data(data=diagram_dict, obj_dict=obj_dict, logger=logger)
                    circuit.add_diagram(diagram)

                elif diagram_dict['type'] == DiagramType.NodeBreaker.value:
                    diagram = dev.NodeBreakerDiagram()
                    diagram.parse_data(data=diagram_dict, obj_dict=obj_dict, logger=logger)
                    circuit.add_diagram(diagram)

                elif diagram_dict['type'] == DiagramType.SubstationLineMap.value:
                    diagram = dev.MapDiagram()
                    diagram.parse_data(data=diagram_dict, obj_dict=obj_dict, logger=logger)
                    circuit.add_diagram(diagram)
                else:
                    print('unrecognized diagram', diagram_dict['type'])

    return circuit
