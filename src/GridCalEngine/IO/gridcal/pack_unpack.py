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
import json
import math
from typing import Dict, Union, List, Tuple, Any, Callable
import pandas as pd
import numpy as np
from enum import EnumMeta as EnumType
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.Parents.editable_device import GCProp
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.enumerations import (DiagramType, DeviceType, SubObjectType, TransformerControlType)


def get_objects_dictionary() -> Dict[str, ALL_DEV_TYPES]:
    """
    creates a dictionary with the types and the circuit objects
    :return: Dictionary instance
    """

    # this list must be sorted in dependency order so that the
    # loading algorithm is able to find the object substitutions

    object_types = {
        'modelling_authority': dev.ModellingAuthority(),

        'area': dev.Area(),
        'zone': dev.Zone(),

        'country': dev.Country(),
        'community': dev.Community(),
        'region': dev.Region(),
        'municipality': dev.Municipality(),

        'substation': dev.Substation(),
        'voltage_level': dev.VoltageLevel(),

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

        'external_grid': dev.ExternalGrid(),

        'current_injection': dev.CurrentInjection(),

        'wires': dev.Wire(),
        'overhead_line_types': dev.OverheadLineType(),
        'underground_cable_types': dev.UndergroundLineType(),
        'sequence_line_types': dev.SequenceLineType(),
        'transformer_types': dev.TransformerType(),

        'branch_group': dev.BranchGroup(),

        'branch': dev.Branch(),
        'transformer2w': dev.Transformer2W(),

        'windings': dev.Winding(),
        'transformer3w': dev.Transformer3W(),

        'line': dev.Line(),
        'dc_line': dev.DcLine(None, None),

        'hvdc': dev.HvdcLine(),

        'vsc': dev.VSC(None, None),
        'upfc': dev.UPFC(None, None),

        'series_reactance': dev.SeriesReactance(),

        'switch': dev.Switch(),

        'contingency_group': dev.ContingencyGroup(),
        'contingency': dev.Contingency(),

        'investments_group': dev.InvestmentsGroup(),
        'investment': dev.Investment(),

        # TODO: Handle these legacy types
        # 'generator_technology': dev.GeneratorTechnology(),
        # 'generator_fuel': dev.GeneratorFuel(),
        # 'generator_emission': dev.GeneratorEmission(),

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
    time_profile = circuit.time_profile
    nt = len(time_profile) if time_profile is not None else 0

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

            lists_of_objects: List[ALL_DEV_TYPES] = circuit.get_elements_by_type(object_sample.device_type)

            obj = list()
            profiles = dict()
            object_idtags = list()
            if len(lists_of_objects) > 0:

                for k, elm in enumerate(lists_of_objects):

                    # get the object normal information
                    obj.append(elm.get_save_data())
                    object_idtags.append(elm.idtag)

                    if time_profile is not None:

                        if nt > 0:

                            elm.ensure_profiles_exist(time_profile)

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
                dfs[object_type_name + '_' + prop] = pd.DataFrame(data=data, columns=object_idtags, index=time_profile)

        # towers and wires ---------------------------------------------------------------------------------------------
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
    default = profile.default_value.idtag if hasattr(profile.default_value, 'idtag') else "None"

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


def get_profile_from_dict(profile: Profile,
                          data: Dict[str, Union[str, Union[Any, Dict[str, Any]]]],
                          collection: Union[None, Dict[str, Any]] = None):
    """
    Create a profile from json dict data
    :param profile: Profile object to fill in
    :param data: Json dict data
    :param collection: if the collection is provided, it will be used to convert idtags into objects
    :return: None
    """
    default_value = data['default']
    is_sparse = bool(data['is_sparse'])
    # profile = Profile(default_value=default_value, is_sparse=bool(data['is_sparse']))

    if is_sparse:
        sp_data = data['sparse_data']

        if collection is None:
            map_data = {int(key): val for key, val in sp_data['map'].items()}

        else:
            default_value = collection.get(data['default'], default_value)
            map_data = {int(key): collection.get(val, default_value) for key, val in sp_data['map'].items()}

        if profile.dtype == DeviceType.BusDevice:  # manual correction for buses profile incorrect value
            if default_value == "None":
                default_value = profile.default_value

        profile.create_sparse(default_value=default_value, size=data['size'], map_data=map_data)
    else:

        if collection is None:
            arr = data['dense_data']
        else:
            arr = [collection.get(i, default_value) for i in data['dense_data']]
        profile.set(np.array(arr))
    profile.set_initialized()


def gridcal_object_to_json(elm: ALL_DEV_TYPES) -> Dict[str, str]:
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

        elif prop.tpe == SubObjectType.GeneratorQCurve:
            data[name] = obj.to_list()

        elif prop.tpe == SubObjectType.LineLocations:
            data[name] = obj.to_list()

        elif prop.tpe == SubObjectType.TapChanger:
            data[name] = obj.to_dict()

        elif prop.tpe == SubObjectType.Associations:
            data[name] = obj.to_dict()

        elif prop.tpe == SubObjectType.Array:
            data[name] = list(obj)

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
    Transform a MultiCircuit into a collection of Json files
    :param circuit:
    :return:
    """
    data: Dict[str, Union[Dict[str, str], List[Dict[str, str]]]] = dict()

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
                    'prob': list(np.ones(len(unix_time))),
                    'snapshot_unix': circuit.get_snapshot_time_unix()}

    return data


def search_property(template_elm: ALL_DEV_TYPES,
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


def look_for_property(elm: ALL_DEV_TYPES, property_name) -> Union[GCProp, None]:
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
        if val == 'None':
            return False
    if isinstance(val, float):
        if math.isnan(val):
            return False
        if math.isinf(val):
            return False
    return True


def look_in_collection_by_name(key: str, collection: Dict[str, ALL_DEV_TYPES]) -> Union[ALL_DEV_TYPES, None]:
    """
    Look in a collection for an element by its name instead of by Idtag
    :param key: name of the element
    :param collection: Collection to look into
    :return: Device or None if not found
    """
    for idtag, elm in collection.items():
        if elm.name == key:
            return elm
    return None


class CreatedOnTheFly:
    """
    This class is to pack all those devices that are created "on the fly" to support legacy formats
    """

    def __init__(self) -> None:
        """
        Constructor
        """
        # legacy operations: this is from when area, zone and substation were strings,
        # now we create those objects on the fly
        self.legacy_area_dict: Dict[str, dev.Area] = dict()
        self.legacy_zone_dict: Dict[str, dev.Zone] = dict()
        self.legacy_substation_dict: Dict[str, dev.Substation] = dict()

        self.contingency_groups: List[dev.ContingencyGroup] = list()
        self.contingencies: List[dev.Contingency] = list()

        self.technologies: Dict[str, dev.Technology] = dict()

    def get_create_area(self, property_value):
        """

        :param property_value:
        :return:
        """
        area = self.legacy_area_dict.get(property_value, None)
        if area is None:
            area = dev.Area(name=str(property_value))
            self.legacy_area_dict[property_value] = area
        return area

    def get_create_zone(self, property_value):
        """

        :param property_value:
        :return:
        """
        zone = self.legacy_zone_dict.get(property_value, None)
        if zone is None:
            zone = dev.Zone(name=str(property_value))
            self.legacy_zone_dict[property_value] = zone
        return zone

    def get_create_substation(self, property_value):
        """

        :param property_value:
        :return:
        """
        substation = self.legacy_substation_dict.get(property_value, None)
        if substation is None:
            substation = dev.Substation(name=str(property_value))
            self.legacy_substation_dict[property_value] = substation
        return substation

    def create_contingency(self, elm: ALL_DEV_TYPES):
        """

        :param elm:
        :return:
        """
        con_group = dev.ContingencyGroup(name=elm.name)
        conn = dev.Contingency(device_idtag=elm.idtag, prop='active', group=con_group)

        self.contingency_groups.append(con_group)
        self.contingencies.append(conn)

    def create_technology(self, elm: dev.Generator, tech_name: str):
        """

        :param elm:
        :param tech_name:
        :return:
        """

        tech = self.technologies.get(tech_name, None)

        if tech is None:
            tech = dev.Technology(name=tech_name)
            self.technologies[tech_name] = tech

        elm.technologies.add_object(api_object=tech, val=1.0)


def parse_object_type_from_dataframe(main_df: pd.DataFrame,
                                     template_elm: ALL_DEV_TYPES,
                                     elements_dict_by_type: Dict[DeviceType, Dict[str, ALL_DEV_TYPES]],
                                     time_profile: pd.DatetimeIndex,
                                     object_type_key: str,
                                     data: Dict[str, Union[float, str, pd.DataFrame]],
                                     logger: Logger) -> Tuple[
    List[ALL_DEV_TYPES], Dict[str, ALL_DEV_TYPES], CreatedOnTheFly]:
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
    devices_dict: Dict[str, ALL_DEV_TYPES] = dict()
    devices: List[ALL_DEV_TYPES] = list()

    # legacy operations: this is from when area, zone and substation were strings,
    # now we create those objects on the fly
    on_the_fly = CreatedOnTheFly()

    # parse each object of the dataframe
    for i, row in main_df.iterrows():

        # create device
        idtag = row.get('idtag', None)
        elm = type(template_elm)(idtag=idtag)

        # ensure the profiles existence
        if time_profile is not None:
            nt = len(time_profile)
            if nt > 0:
                elm.ensure_profiles_exist(index=time_profile)
        else:
            nt = 0

        # parse each property of the row
        for property_name_, property_value in row.items():

            property_name = str(property_name_)

            if property_name != 'idtag':  # idtag was set already
                gc_prop: GCProp = look_for_property(elm=elm, property_name=property_name)
                if gc_prop is not None:

                    if valid_value(property_value):

                        if gc_prop.has_profile():
                            prof = elm.get_profile(magnitude=gc_prop.name)
                            if 0 < nt != prof.size():
                                prof.resize(nt)
                        else:
                            prof = None

                        # the property of the file exists, parse it
                        if isinstance(gc_prop.tpe, DeviceType):

                            # we must look for the refference in elements_dict
                            collection = elements_dict_by_type.get(gc_prop.tpe, None)

                            if collection is not None:
                                ref_idtag = str(property_value)
                                ref_elm = collection.get(ref_idtag, None)

                                if ref_elm is not None:
                                    elm.set_snapshot_value(gc_prop.name, ref_elm)

                                    if gc_prop.has_profile():
                                        prof.fill(ref_elm)

                                else:

                                    # legacy operations: this is from when grids referenced buses by name
                                    if gc_prop.name in ['bus_from', 'bus_to', 'bus']:
                                        ref_elm = look_in_collection_by_name(key=ref_idtag, collection=collection)
                                        if ref_elm is None:
                                            could_not_fix_it = True
                                        else:
                                            could_not_fix_it = False

                                            elm.set_snapshot_value(gc_prop.name, ref_elm)

                                            if gc_prop.has_profile():
                                                prof.fill(ref_elm)
                                    else:
                                        could_not_fix_it = True

                                    if could_not_fix_it:
                                        logger.add_error("Could not locate refference",
                                                         device=row.get('idtag', 'not provided'),
                                                         device_class=template_elm.device_type.value,
                                                         device_property=gc_prop.name,
                                                         value=ref_idtag)
                            else:

                                # legacy operations: this is from when area, zone and substation were strings
                                if gc_prop.name == 'area':

                                    if str(property_value).strip() != '':
                                        area = on_the_fly.get_create_area(property_value=str(property_value))
                                        elm.set_snapshot_value(gc_prop.name, area)

                                elif gc_prop.name == 'zone':

                                    if str(property_value).strip() != '':
                                        zone = on_the_fly.get_create_zone(property_value=str(property_value))
                                        elm.set_snapshot_value(gc_prop.name, zone)

                                elif gc_prop.name == 'substation':

                                    if str(property_value).strip() != '':
                                        substation = on_the_fly.get_create_substation(
                                            property_value=str(property_value))
                                        elm.set_snapshot_value(gc_prop.name, substation)
                                elif gc_prop.name == 'template' and property_value == 'BranchTemplate':
                                    # skip this
                                    pass
                                else:

                                    logger.add_error("No device of the refferenced type",
                                                     device=row.get('idtag', 'not provided'),
                                                     device_class=template_elm.device_type.value,
                                                     device_property=gc_prop.name,
                                                     value=property_value)

                        elif isinstance(gc_prop.tpe, SubObjectType):

                            if gc_prop.tpe == SubObjectType.GeneratorQCurve:
                                q_curve: dev.GeneratorQCurve = elm.get_snapshot_value(gc_prop)

                                if isinstance(property_value, str):
                                    q_curve.parse(json.loads(property_value))
                                else:
                                    q_curve.parse(property_value)

                        elif gc_prop.tpe == str:
                            # set the value directly
                            elm.set_snapshot_value(gc_prop.name, str(property_value))

                            if gc_prop.has_profile():
                                prof.fill(str(property_value))

                        elif gc_prop.tpe == float:
                            # set the value directly
                            elm.set_snapshot_value(gc_prop.name, float(property_value))

                            if gc_prop.has_profile():
                                prof.fill(float(property_value))

                        elif gc_prop.tpe == int:
                            # set the value directly
                            elm.set_snapshot_value(gc_prop.name, int(property_value))

                            if gc_prop.has_profile():
                                prof.fill(int(property_value))

                        elif gc_prop.tpe == bool:
                            # set the value directly
                            elm.set_snapshot_value(gc_prop.name, bool(property_value))

                            if gc_prop.has_profile():
                                prof.fill(bool(property_value))

                        elif isinstance(gc_prop.tpe, EnumType):

                            try:
                                val = gc_prop.tpe(property_value)
                                elm.set_snapshot_value(gc_prop.name, val)

                                if gc_prop.has_profile():
                                    prof.fill(val)

                            except ValueError:
                                skip = False
                                if property_name == 'control_mode':
                                    if property_value == "1:Pt":
                                        elm.set_snapshot_value(gc_prop.name, TransformerControlType.Pf)
                                        skip = True

                                if not skip:
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
                            skip = False
                            if gc_prop.name == 'bus':
                                skip = True

                            if not skip:
                                logger.add_info(msg='No profile for the property', value=gc_prop.name)

                else:
                    # the property does not exists, neither in the old names
                    skip = False
                    if template_elm.device_type == DeviceType.ShuntDevice:
                        if property_name in ['is_controlled', 'Bmin', 'Bmax', 'Vset']:
                            skip = True

                    if property_name == 'contingency_enabled':
                        # this is a branch with the legacy property "contingency_enabled", hence, create a contingency
                        on_the_fly.create_contingency(elm=elm)
                        skip = True
                    elif property_name == 'technology':
                        on_the_fly.create_technology(elm=elm, tech_name=property_value)
                        skip = True

                    if not skip:
                        logger.add_warning("Property in the file is not found in the model",
                                           device=row.get('idtag', 'not provided'),
                                           device_class=template_elm.device_type.value,
                                           device_property=property_name)

        # save the element in the dictionary for later
        devices_dict[elm.idtag] = elm
        devices.append(elm)

    return devices, devices_dict, on_the_fly


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


def search_and_apply_json_profile(json_entry: Dict[str, Dict[str, Union[str, Union[Any, Dict[str, Any]]]]],
                                  gc_prop: GCProp,
                                  elm: ALL_DEV_TYPES,
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

        profile: Profile = elm.get_profile(magnitude=gc_prop.name)

        if json_profile is None:
            # the profile was not found, so we fill it with the default stuff
            profile.fill(property_value)
        else:
            get_profile_from_dict(profile=profile, data=json_profile, collection=collection)


def parse_object_type_from_json(template_elm: ALL_DEV_TYPES,
                                data_list: List[Dict[str, Dict[str, str]]],
                                elements_dict_by_type: Dict[DeviceType, Dict[str, ALL_DEV_TYPES]],
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
    devices_dict: Dict[str, ALL_DEV_TYPES] = dict()
    devices: List[ALL_DEV_TYPES] = list()

    for json_entry in data_list:
        idtag = json_entry['idtag']
        elm = type(template_elm)(idtag=idtag)

        # ensure the profiles existence
        if time_profile is not None:
            elm.ensure_profiles_exist(index=time_profile)

        # for property_name_, property_value in json_entry.items():
        for property_name, gc_prop in template_elm.registered_properties.items():

            # search for the property in the json
            property_value = searc_property_into_json(json_entry=json_entry, prop=gc_prop)

            if property_value is not None:

                if property_name != 'idtag':  # idtag was set already
                    # gc_prop: GCProp = look_for_property(elm=elm, property_name=property_name)

                    if gc_prop is not None:

                        if valid_value(property_value):

                            if isinstance(gc_prop.tpe, DeviceType):

                                # this is a hyperlink to another object
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
                                        logger.add_error("Could not locate reference",
                                                         device=elm.idtag,
                                                         device_class=template_elm.device_type.value,
                                                         device_property=gc_prop.name,
                                                         value=ref_idtag)
                                else:
                                    logger.add_error("No device of the referenced type",
                                                     device=elm.idtag,
                                                     device_class=template_elm.device_type.value,
                                                     device_property=gc_prop.name,
                                                     value=property_value)

                            elif isinstance(gc_prop.tpe, SubObjectType):  # this is a hyperlink to another object

                                if gc_prop.tpe == SubObjectType.GeneratorQCurve:

                                    # get the curve object and fill it with the json data
                                    q_curve: dev.GeneratorQCurve = elm.get_snapshot_value(prop=gc_prop)
                                    if isinstance(property_value, str):
                                        q_curve.parse(json.loads(property_value))
                                    else:
                                        q_curve.parse(property_value)

                                elif gc_prop.tpe == SubObjectType.LineLocations:

                                    # get the line locations object and fill it with the json data
                                    locations_obj: dev.LineLocations = elm.get_snapshot_value(prop=gc_prop)
                                    locations_obj.parse(property_value)

                                elif gc_prop.tpe == SubObjectType.TapChanger:

                                    # get the line locations object and fill it with the json data
                                    locations_obj: dev.TapChanger = elm.get_snapshot_value(prop=gc_prop)
                                    locations_obj.parse(property_value)

                                elif gc_prop.tpe == SubObjectType.Array:

                                    val = np.array(property_value)
                                    elm.set_snapshot_value(gc_prop.name, val)

                                elif gc_prop.tpe == SubObjectType.Associations:

                                    # get the list of associations
                                    associations = elm.get_snapshot_value(gc_prop)
                                    associations.parse(
                                        data=property_value,
                                        elements_dict=elements_dict_by_type.get(associations.device_type, {}),
                                        logger=logger,
                                        elm_name=elm.name
                                    )

                                else:
                                    raise Exception(f"SubObjectType {gc_prop.tpe} not implemented")

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


def handle_legacy_jsons(model_data: Dict[str, List],
                        elements_dict_by_type: Dict[DeviceType, Dict],
                        logger: Logger) -> None:
    """
    Handle those legacy structures that were deprecated and removed from GridCal's structure
    :param model_data:
    :param elements_dict_by_type:
    :param logger:
    :return:
    """
    gt_data_list = model_data.get("generator_technology", None)
    if gt_data_list is not None:
        for entry in gt_data_list:
            gen_idtag = entry.get('generator', None)
            tech_idtag = entry.get('technology', None)
            proportion = entry.get('proportion', 1.0)
            generator = elements_dict_by_type[DeviceType.GeneratorDevice].get(gen_idtag, None)
            tech = elements_dict_by_type[DeviceType.Technology].get(tech_idtag, None)
            if generator is not None and tech is not None:
                generator.technologies.add_object(api_object=tech, val=proportion)
                logger.add_info("Converted legacy generator technology association",
                                device_class="Generator_technology",
                                value=f"{generator.name} -> {tech.name} at {proportion}")

    gf_data_list = model_data.get("generator_fuel", None)
    if gf_data_list is not None:
        for entry in gf_data_list:
            gen_idtag = entry.get('generator', None)
            fuel_idtag = entry.get('fuel', None)
            rate = entry.get('rate', 1.0)
            generator = elements_dict_by_type[DeviceType.GeneratorDevice].get(gen_idtag, None)
            fuel = elements_dict_by_type[DeviceType.FuelDevice].get(fuel_idtag, None)
            if generator is not None and fuel is not None:
                generator.fuels.add_object(api_object=fuel, val=rate)
                logger.add_info("Converted legacy generator fuel association",
                                device_class="generator_fuel",
                                value=f"{generator.name} -> {fuel.name} at {rate}")

    ge_data_list = model_data.get("generator_emission", None)
    if ge_data_list is not None:
        for entry in ge_data_list:
            gen_idtag = entry.get('generator', None)
            emision_idtag = entry.get('emission', None)
            rate = entry.get('rate', 1.0)
            generator = elements_dict_by_type[DeviceType.GeneratorDevice].get(gen_idtag, None)
            emission = elements_dict_by_type[DeviceType.EmissionGasDevice].get(emision_idtag, None)
            if generator is not None and emission is not None:
                generator.emissions.add_object(api_object=emission, val=rate)
                logger.add_info("Converted legacy generator emission association",
                                device_class="generator_emission",
                                value=f"{generator.name} -> {emission.name} at {rate}")


def parse_gridcal_data(data: Dict[str, Union[str, float, pd.DataFrame, Dict[str, Any], List[Dict[str, Any]]]],
                       text_func: Union[Callable, None] = None,
                       progress_func: Union[Callable, None] = None,
                       logger: Logger = Logger()) -> MultiCircuit:
    """
    Interpret data dictionary
    :param data: dictionary of data frames and other information
    :param text_func: text callback function
    :param progress_func: progress callback function
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
    item_count = 0
    n_data_types = len(data_model_object_types)
    for object_type_key, template_elm in data_model_object_types.items():

        if text_func is not None:
            text_func(f"Parsing {object_type_key} table data...")

        # try to get the DataFrame
        df = data.get(object_type_key, None)

        if df is not None:

            # fill in the objects
            if df.shape[0] > 0:

                devices, devices_dict, on_the_fly = parse_object_type_from_dataframe(
                    main_df=df,
                    template_elm=template_elm,
                    elements_dict_by_type=elements_dict_by_type,
                    time_profile=circuit.time_profile,
                    object_type_key=object_type_key,
                    data=data,
                    logger=logger
                )

                # add the elements that were created on the fly...
                for name, on_the_fly_elm in on_the_fly.legacy_area_dict.items():
                    circuit.add_area(obj=on_the_fly_elm)
                for name, on_the_fly_elm in on_the_fly.legacy_zone_dict.items():
                    circuit.add_zone(obj=on_the_fly_elm)
                for name, on_the_fly_elm in on_the_fly.legacy_substation_dict.items():
                    circuit.add_substation(obj=on_the_fly_elm)
                for conn_group in on_the_fly.contingency_groups:
                    circuit.add_contingency_group(obj=conn_group)
                for cont in on_the_fly.contingencies:
                    circuit.add_contingency(obj=cont)
                for tech_name, technology in on_the_fly.technologies.items():
                    circuit.add_technology(obj=technology)

                # set the dictionary per type for later
                elements_dict_by_type[template_elm.device_type] = devices_dict

                # add the devices to the circuit
                circuit.set_elements_list_by_type(device_type=template_elm.device_type,
                                                  devices=devices,
                                                  logger=logger)

            else:
                # no objects of this type
                pass
        else:
            # the file does not contain information for the data type (not a problem...)
            pass

        if progress_func is not None:
            progress_func(float(item_count + 1) / float(n_data_types) * 100)

        item_count += 1

    # ------------------------------------------------------------------------------------------------------------------
    # New way of parsing information from .model files.
    # These files are just .json stored in the model_data inside the zip file
    model_data = data.get('model_data', None)
    if model_data is not None:

        if len(model_data) > 0:

            tdata = model_data.get('time', None)
            if tdata is not None:
                circuit.set_unix_time(arr=tdata['unix'])

                snapshot_unix_time = tdata.get('snapshot_unix', None)
                if snapshot_unix_time is not None:
                    circuit.set_snapshot_time_unix(val=snapshot_unix_time)

            else:
                logger.add_error(msg=f'The file must have time data regardless of the profiles existance')
                circuit.time_profile = None

            # for each element type...
            item_count = 0
            n_data_types = len(data_model_object_types)
            for object_type_key, template_elm in data_model_object_types.items():

                if text_func is not None:
                    text_func(f"Parsing {object_type_key} model data...")

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
                    circuit.set_elements_list_by_type(device_type=template_elm.device_type,
                                                      devices=devices,
                                                      logger=logger)
                else:
                    # branch is a legacy structure, so we can avoid reporting its absence
                    if object_type_key != 'branch':
                        logger.add_warning(msg=f'No data for {object_type_key}')

                if progress_func is not None:
                    progress_func(float(item_count + 1) / float(n_data_types) * 100)

                item_count += 1

            # Handle the legacy objects that may be present in the data bus not declared in the program
            # i.e. generator_technology
            handle_legacy_jsons(model_data=model_data,
                                elements_dict_by_type=elements_dict_by_type,
                                logger=logger)

    # fill in wires into towers ----------------------------------------------------------------------------------------
    if text_func is not None:
        text_func("Tower wires...")
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
    if text_func is not None:
        text_func("Parsing diagrams...")

    # try to get the get the list of diagrams
    list_of_diagrams: List[Dict[str, Any]] = data.get('diagrams', None)

    if list_of_diagrams is not None:

        if len(list_of_diagrams):
            obj_dict = circuit.get_all_elements_dict_by_type(add_locations=True)

            for diagram_dict in list_of_diagrams:

                if diagram_dict['type'] in [DiagramType.Schematic.value, "bus-branch"]:
                    diagram = dev.SchematicDiagram()
                    diagram.parse_data(data=diagram_dict, obj_dict=obj_dict, logger=logger)
                    circuit.add_diagram(diagram)

                elif diagram_dict['type'] == DiagramType.SubstationLineMap.value:
                    diagram = dev.MapDiagram()
                    diagram.parse_data(data=diagram_dict, obj_dict=obj_dict, logger=logger)
                    circuit.add_diagram(diagram)
                else:
                    print('unrecognized diagram', diagram_dict['type'])

    if text_func is not None:
        text_func("Done!")

    return circuit
