# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Dict, Union, List, Tuple, Any, Callable, Set, Optional
import pandas as pd
import numpy as np
from enum import EnumMeta as EnumType
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import (
    ManufacturerNativeBinaryVariant,
    ManufacturerNativeModel,
)
from VeraGridEngine.IO.manufacturer_native.model_info import ManufacturerNativeModelInfo
from VeraGridEngine.IO.manufacturer_native.model_info_codec import decode_manufacturer_native_model_info
from VeraGridEngine.enumerations import IeeeCigreDllPlatform, IeeeCigreDllVerificationStatus
import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.Parents.editable_device import GCProp, EditableDevice
from VeraGridEngine.Devices.Parents.pointer_device_parent import PointerDeviceParent
from VeraGridEngine.Devices.Profiles import AnyProfile
from VeraGridEngine.Utils.Symbolic.symbolic_io import (BlockSaver, BlockParser, Block,
                                                       normalize_persisted_block_uid,
                                                       normalize_persisted_blocks)
from VeraGridEngine.Utils.procedural_logic import ProceduralLogicCodec
from VeraGridEngine.Devices.types import ALL_DEV_TYPES, VERAGRID_FILE_TYPE
from VeraGridEngine.Devices.Diagrams.base_diagram import copy_diagrams
from VeraGridEngine.enumerations import (DiagramType, DeviceType, SubObjectType, TapPhaseControl, TapModuleControl,
                                         ContingencyOperationTypes)

ProfileDictionary = Dict[str, bool | int | str | dict[str, dict[int, Any | None] | dict[Any, Any]] | Any]

ModelDictionary = Dict[str, object]


def get_objects_dictionary() -> Dict[str, ALL_DEV_TYPES]:
    """
    creates a dictionary with the types and the circuit objects
    :return: Dictionary instance
    """

    # this list must be sorted in dependency order so that the
    # loading algorithm is able to find the object substitutions

    return {
        'modelling_authority': dev.ModellingAuthority(),

        'area': dev.Area(),
        'zone': dev.Zone(),

        'country': dev.Country(),
        'community': dev.Community(),
        'region': dev.Region(),
        'municipality': dev.Municipality(),

        'owner': dev.Owner(),

        'substation': dev.Substation(),
        'voltage_level': dev.VoltageLevel(),

        'technology': dev.Technology(),

        'fuel': dev.Fuel(),

        'emission': dev.EmissionGas(),

        'facility': dev.Facility(),

        'market_unit': dev.MarketUnit(),

        'manufacturer_native_model': dev.ManufacturerNativeModel(),
        'rms_model_template': dev.RmsModelTemplate(),
        'emt_model_template': dev.EmtModelTemplate(),
        'fmu_template': dev.FmuTemplate(),

        'bus': dev.Bus(),

        'bus_bar': dev.BusBar(),

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
        'underground_cable_constructions': dev.UndergroundCableType(),
        'underground_cable_types': dev.UndergroundLineType(),
        'sequence_line_types': dev.SequenceLineType(),
        'transformer_types': dev.TransformerType(),

        'branch_group': dev.BranchGroup(),

        'branch': dev.Branch(),
        'transformer2w': dev.Transformer2W(),

        'windings': dev.Winding(),
        'transformer3w': dev.Transformer3W(),
        'transformernw': dev.TransformerNW(),

        'line': dev.Line(),
        'dc_line': dev.DcLine(),

        'hvdc': dev.HvdcLine(),

        'vsc': dev.VSC(),
        'upfc': dev.UPFC(),

        'series_reactance': dev.SeriesReactance(),

        'switch': dev.Switch(),

        'contingency_group': dev.ContingencyGroup(),
        'contingency': dev.Contingency(),
        'short_circuit_definition': dev.ShortCircuitEvent(),

        'remedial_action_group': dev.RemedialActionGroup(),
        'remedial_action': dev.RemedialAction(),

        'investments_group': dev.InvestmentsGroup(),
        'investment': dev.Investment(),

        'rms_event_group': dev.RmsEventsGroup(),
        'rms_event': dev.RmsEvent(),

        'emt_event_group': dev.EmtEventsGroup(),
        'emt_event': dev.EmtEvent(),

        'dynamic_plot': dev.DynamicPlot(),
        'dynamic_plot_entry': dev.DynamicPlotEntry(),

        'fluid_node': dev.FluidNode(),
        'fluid_path': dev.FluidPath(),
        'fluid_turbine': dev.FluidTurbine(),
        'fluid_pump': dev.FluidPump(),
        'fluid_p2x': dev.FluidP2x(),

        'pi_measurement': dev.PiMeasurement(),
        'qi_measurement': dev.QiMeasurement(),
        'pf_measurement': dev.PfMeasurement(),
        'qf_measurement': dev.QfMeasurement(),
        'if_measurement': dev.IfMeasurement(),
        'pt_measurement': dev.PtMeasurement(),
        'qt_measurement': dev.QtMeasurement(),
        'it_measurement': dev.ItMeasurement(),
        'vm_measurement': dev.VmMeasurement(),
        'va_measurement': dev.VaMeasurement(),
        'pg_measurement': dev.PgMeasurement(),
        'qg_measurement': dev.QgMeasurement(),

        'control_pc': dev.ControlPc(),
    }


_FMU_CONFIG_PROPERTY_NAMES: Tuple[str, ...] = (
    "rms_fmu_import_config",
    "emt_fmu_import_config",
    "rms_fmu_me_import_config",
    "emt_fmu_me_import_config",
    "serialized_config",
)


def _to_project_relative_fmu_config(config_text: str, project_directory: Path | None) -> str:
    """
    Rewrite the stored FMU path in one serialized configuration as a project-relative path.

    :param config_text: Serialized FMU configuration payload.
    :param project_directory: Directory containing the VeraGrid project file.
    :return: Serialized configuration with a relative FMU path when possible.
    """

    if project_directory is None:
        return config_text
    else:
        stripped_text: str = config_text.strip()
        if len(stripped_text) == 0:
            return config_text
        else:
            payload: dict[str, Any] = json.loads(stripped_text)
            fmu_path_text = payload.get("fmu_path", None)
            if isinstance(fmu_path_text, str):
                fmu_path = Path(fmu_path_text)
                if fmu_path.is_absolute():
                    try:
                        payload["fmu_path"] = os.path.relpath(str(fmu_path), start=str(project_directory))
                    except ValueError:
                        payload["fmu_path"] = fmu_path_text
                else:
                    pass
            else:
                pass
            return json.dumps(payload, sort_keys=True)


def _resolve_project_fmu_config(config_text: str, project_directory: Path | None) -> str:
    """
    Rewrite the stored FMU path in one serialized configuration as an absolute runtime path.

    :param config_text: Serialized FMU configuration payload.
    :param project_directory: Directory containing the VeraGrid project file.
    :return: Serialized configuration with a resolved absolute FMU path when possible.
    """

    if project_directory is None:
        return config_text
    else:
        stripped_text: str = config_text.strip()
        if len(stripped_text) == 0:
            return config_text
        else:
            payload: dict[str, Any] = json.loads(stripped_text)
            fmu_path_text = payload.get("fmu_path", None)
            if isinstance(fmu_path_text, str):
                fmu_path = Path(fmu_path_text)
                if fmu_path.is_absolute():
                    pass
                else:
                    payload["fmu_path"] = str((project_directory / fmu_path).resolve())
            else:
                pass
            return json.dumps(payload, sort_keys=True)


def _resolve_circuit_fmu_paths(circuit: MultiCircuit, project_directory: Path | None) -> None:
    """
    Resolve stored FMU configuration paths for every element in the circuit.

    :param circuit: Parsed circuit instance.
    :param project_directory: Directory containing the VeraGrid project file.
    :return: None.
    """

    if project_directory is None:
        return
    else:
        elm: ALL_DEV_TYPES
        for elm in circuit.get_all_elements_iter():
            property_name: str
            for property_name in _FMU_CONFIG_PROPERTY_NAMES:
                if property_name in elm.registered_properties:
                    current_value = elm.get_snapshot_value_by_name(property_name)
                    if isinstance(current_value, str):
                        elm.set_snapshot_value(property_name,
                                               _resolve_project_fmu_config(current_value, project_directory))
                    else:
                        pass
                else:
                    pass


def _to_project_relative_path(path_text: str, project_directory: Path | None) -> str:
    """
    Convert one absolute filesystem path into a project-relative path when possible.

    :param path_text: Original path text.
    :param project_directory: Directory containing the VeraGrid project file.
    :return: Relative path when conversion is possible.
    """

    if project_directory is None:
        return path_text
    else:
        normalized_text: str = str(path_text).strip()
        if len(normalized_text) == 0:
            return path_text
        else:
            candidate = Path(normalized_text)
            if candidate.is_absolute():
                try:
                    return os.path.relpath(str(candidate), start=str(project_directory))
                except ValueError:
                    return path_text
            else:
                return path_text


def get_multiverse_node_metadata(metadata: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Extract the per-node metadata dictionary from a multiverse metadata payload.

    Newer files wrap node records under ``nodes`` and may include top-level metadata such as
    ``active_node_id``. Older files store the node records directly at the top level.
    """
    # New-format multiverse metadata is a small envelope:
    # {
    #     "active_node_id": ...,
    #     "nodes": {
    #         <node_id>: {...},
    #         ...
    #     }
    # }
    # In that case, only the nested ``nodes`` mapping contains per-node records.
    nodes = metadata.get("nodes", None)

    # Accept the new wrapped format only if the value really is the node dictionary.
    # This avoids accidentally treating malformed metadata as valid node content.
    if isinstance(nodes, dict):
        return nodes

    # Older files predate the metadata envelope and store the node records directly at
    # the top level. Returning ``metadata`` as-is keeps the loader backward compatible.
    return metadata


def order_multiverse_records(metadata: Dict[str, Dict[str, int | float]] | Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return multiverse metadata records in a parent-before-child order.

    The multiverse payloads must be parsed in dependency order because child delta payloads
    may reference objects inherited from their parent composed scenario.
    """
    node_metadata = get_multiverse_node_metadata(metadata)

    pending_records: Dict[int, Dict[str, Any]] = {
        int(node_id): dict(record) for node_id, record in node_metadata.items()
    }
    ordered_records: List[Dict[str, Any]] = list()

    while pending_records:
        progressed = False

        for pending_node_id in list(pending_records.keys()):
            record = pending_records[pending_node_id]
            parent_id_raw = record["parent_id"]
            parent_id = None if parent_id_raw is None else int(parent_id_raw)

            if parent_id is not None and parent_id in pending_records:
                continue

            ordered_records.append(record)
            del pending_records[pending_node_id]
            progressed = True

        if not progressed:
            unresolved = ", ".join(str(node_id) for node_id in pending_records.keys())
            raise ValueError(f"Could not resolve multiverse metadata dependency order for nodes: {unresolved}")

    return ordered_records


def gather_model_as_data_frames(circuit: MultiCircuit,
                                logger: Logger = Logger(),
                                legacy: bool = False) -> Dict[str, pd.DataFrame]:
    """
    Pack the circuit information into tables (DataFrames)
    :param circuit: MultiCircuit instance
    :param logger: Logger instance
    :param legacy: Generate the legacy object DataFrames
    :return: dictionary of DataFrames
    """
    dfs = dict()

    # get the master time profile
    time_profile = circuit.time_profile
    nt = circuit.get_time_number()

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

        # configuration ################################################################################################
        obj = list()
        obj.append(['BaseMVA', circuit.Sbase])
        obj.append(['Version', 5])
        obj.append(['Name', str(circuit.name)])
        obj.append(['Comments', str(circuit.comments)])
        obj.append(['idtag', str(circuit.idtag)])

        # increase the model version
        circuit.model_version += 1

        obj.append(['ModelVersion', str(circuit.model_version)])
        obj.append(['UserName', str(circuit.user_name)])
        obj.append(['program', 'VeraGrid'])

        dfs['config'] = pd.DataFrame(data=obj, columns=['Property', 'Value'], dtype=str)

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
                                    try:
                                        profiles[profile_property] = np.zeros(shape=(nt, len(lists_of_objects)),
                                                                              dtype=profile.dtype)
                                    except TypeError:
                                        logger.add_warning("Profile packed as object", device_class=str(profile.dtype))
                                        profiles[profile_property] = np.zeros(shape=(nt, len(lists_of_objects)),
                                                                              dtype=object)

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
            for wire in tower.wires_in_tower.data:
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


def profile_todict(profile: AnyProfile) -> ProfileDictionary:
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
            'default': profile.default_value if profile.sparse_array is None else profile.sparse_array.default_value,
            'sparse_data': {
                'map': dict()
            }
        }


def profile_todict_idtag(profile: AnyProfile) -> ProfileDictionary:
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
                'map': {key: val.idtag if hasattr(val, 'idtag') else None
                        for key, val in profile.sparse_array.get_map().items()}
                if profile.sparse_array is not None else dict()
            }
        }
    else:
        return {
            'is_sparse': profile.is_sparse,
            'size': profile.size(),
            'default': default,
            'dense_data': [e.idtag if hasattr(e, 'idtag') else None for e in profile.dense_array]
            if profile.dense_array is not None else list(),
        }


def profile_todict_str(profile: AnyProfile) -> ProfileDictionary:
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


def cast_profile_value(
        profile: AnyProfile,
        value: Any,
        collection: Union[None, Dict[str, Any]] = None,
) -> Any:
    """
    Convert serialized profile payloads into the concrete type required by ``profile``.

    :param profile: Typed profile that will receive the value.
    :param value: Serialized raw value.
    :param collection: Optional idtag-to-object dictionary for device references.
    :return: Converted value.
    """
    if value is None or value == "None":
        return None

    if collection is not None:
        return collection.get(value, None)

    if isinstance(profile.dtype, DeviceType):
        return value

    if isinstance(profile.dtype, EnumType):
        return profile.dtype(value)

    if profile.dtype == bool:
        if isinstance(value, str):
            low = value.strip().lower()
            if low in {"true", "1"}:
                return True
            if low in {"false", "0"}:
                return False
        return bool(value)

    if profile.dtype == int:
        return int(value)

    if profile.dtype == float:
        return float(value)

    if profile.dtype == str:
        return str(value)

    return value


def get_profile_from_dict(profile: AnyProfile,
                          data: Dict[str, Any | Dict[str, Any]],
                          collection: Union[None, Dict[str, Any]] = None):
    """
    Create a profile from JSON declarative data.
    :param profile: Profile object to fill in
    :param data: JSON profile declaration.
    :param collection: if the collection is provided, it will be used to convert idtags into objects
    :return: None
    """
    raw_default_value = data['default']
    is_sparse = bool(data['is_sparse'])

    try:
        default_value: Any = cast_profile_value(profile=profile, value=raw_default_value, collection=collection)
    except (TypeError, ValueError):
        default_value = profile.default_value

    if isinstance(profile.dtype, DeviceType) and default_value == "None":
        default_value = profile.default_value

    if is_sparse:
        sp_data = data['sparse_data']

        if collection is None:
            map_data = {
                int(key): cast_profile_value(profile=profile, value=val, collection=collection)
                for key, val in sp_data['map'].items()
            }
        else:
            map_data = {
                int(key): cast_profile_value(profile=profile, value=val, collection=collection)
                for key, val in sp_data['map'].items()
            }

        profile.create_sparse(default_value=default_value,
                              size=data['size'], map_data=map_data)
    else:

        if collection is None:
            arr = [cast_profile_value(profile=profile, value=i, collection=collection) for i in data['dense_data']]
        else:
            arr = [cast_profile_value(profile=profile, value=i, collection=collection) for i in data['dense_data']]
        profile.set(np.array(arr))

    # mark as initialized
    profile.set_initialized()


def veragrid_object_to_json(elm: ALL_DEV_TYPES,
                            block_saver: BlockSaver,
                            project_directory: Path | None = None) -> Dict[str, str]:
    """

    :param elm:
    :param block_saver:
    :param project_directory: Directory used to store portable FMU paths.
    :return:
    """

    data = dict()
    for name, prop in elm.registered_properties.items():
        obj = elm.get_snapshot_value(prop=prop)

        if prop.tpe in [str, float, int, bool]:
            if name in _FMU_CONFIG_PROPERTY_NAMES and isinstance(obj, str):
                data[name] = _to_project_relative_fmu_config(obj, project_directory)
            else:
                if name == "fmu_relative_path" and isinstance(obj, str):
                    data[name] = _to_project_relative_path(obj, project_directory)
                else:
                    data[name] = obj

            if prop.has_profile():
                data[name + '_prof'] = profile_todict(elm.get_profile_by_prop(prop=prop))

        elif prop.tpe == SubObjectType.ManufacturerNativeModelInfo:
            # Decode before serialization so malformed metadata can never enter
            # a VeraGrid archive through this generic property path.
            decoded_model_info: ManufacturerNativeModelInfo = decode_manufacturer_native_model_info(obj)
            if obj.startswith(b"veragrid-manufacturer-native-model-info-v2\n"):
                canonical_schema_version: int = 2
            else:
                canonical_schema_version = 1
            data[name] = {
                "schema_version": canonical_schema_version,
                "canonical_hex": obj.hex(),
            }
        elif prop.tpe == SubObjectType.MergeInformation:
            data[name] = obj.to_dict()

        elif prop.tpe == SubObjectType.GeneratorQCurve:
            data[name] = obj.to_list()

        elif prop.tpe == SubObjectType.LineLocations:
            data[name] = obj.to_list()

        elif prop.tpe == SubObjectType.ImpedanceTripletList:
            data[name] = obj.to_list()

        elif prop.tpe == SubObjectType.ListOfWires:
            data[name] = obj.to_list()

        elif prop.tpe == SubObjectType.ListOfCables:
            data[name] = obj.to_list()

        elif prop.tpe == SubObjectType.TapChanger:
            data[name] = obj.to_dict()

        elif prop.tpe == SubObjectType.Associations:
            data[name] = obj.to_dict()

        elif prop.tpe == SubObjectType.AdmittanceMatrix:
            data[name] = obj.to_dict()

        elif prop.tpe == SubObjectType.DaeBlockType:
            block_saver.save_block(blk=obj, main=True)
            if isinstance(obj, Block):
                data[name] = obj.uid
            else:
                raise ValueError("must be a block")

        elif prop.tpe == SubObjectType.VarType:
            if obj is not None:
                # Persist the physical variable identity. The mutable UID can
                # be shared by every variable connected to the same signal.
                data[name] = obj.non_mutable_uid
            else:
                # Persistent dynamic plot entries may keep unresolved legacy Var
                # hints as ``None`` while semantic fields remain the canonical
                # binding identity.
                data[name] = None

        elif prop.tpe == SubObjectType.ConstType:
            if obj is not None:
                data[name] = obj.uid
            else:
                data[name] = None

        elif prop.tpe == SubObjectType.Array:
            data[name] = list(obj)

        else:
            # if the object is not of a primary type, get the idtag instead
            if obj is None:
                data[name] = None
            else:
                if isinstance(obj, EditableDevice):
                    data[name] = obj.idtag

                    if prop.has_profile():
                        data[name + '_prof'] = profile_todict_idtag(elm.get_profile_by_prop(prop=prop))
                    else:
                        pass
                else:
                    # some data types might not have the idtag, ten just use the str method
                    data[name] = str(obj)

                    if prop.has_profile():
                        data[name + '_prof'] = profile_todict_str(elm.get_profile_by_prop(prop=prop))
                    else:
                        pass

    if isinstance(elm, ManufacturerNativeModel):
        variant_records: List[Dict[str, object]] = list()
        platform: IeeeCigreDllPlatform
        for platform in (
                IeeeCigreDllPlatform.WINDOWS_X86,
                IeeeCigreDllPlatform.WINDOWS_X64,
                IeeeCigreDllPlatform.LINUX_X64,
        ):
            variant: ManufacturerNativeBinaryVariant | None = elm.get_platform_variant(platform)
            if variant is not None:
                variant_records.append({
                    "platform": variant.platform.value,
                    "extension": variant.extension,
                    "content_sha256": variant.content_sha256,
                    "byte_size": variant.byte_size,
                    "zip_member": variant.zip_member,
                    "verification_status": variant.verification_status.value,
                })
            else:
                pass
        data["binary_variants"] = variant_records
    else:
        pass
    return data


def gather_model_as_jsons(circuit: MultiCircuit,
                          project_directory: Path | None = None) -> ModelDictionary:
    """
    Transform a ``MultiCircuit`` into a collection of JSON records.
    :param circuit:
    :param project_directory:
    :return:
    """

    if circuit.has_time_series:
        circuit.ensure_profiles_exist()

    data: ModelDictionary = dict()

    block_saver = BlockSaver(circuit.var_factory)

    # declare objects to iterate  name: [sample object, list of objects, headers]
    object_types = get_objects_dictionary()

    del object_types['branch']

    # generic object iteration
    for object_type_name, object_sample in object_types.items():

        object_json = list()

        lists_of_objects = circuit.get_elements_by_type(object_sample.device_type)

        if len(lists_of_objects) > 0:

            for k, elm in enumerate(lists_of_objects):
                obj_data = veragrid_object_to_json(elm, block_saver=block_saver, project_directory=project_directory)
                object_json.append(obj_data)

        data[object_type_name] = object_json

    # time
    unix_time = circuit.get_unix_time()
    if len(unix_time) > 1 and np.all(unix_time == unix_time[0]) and abs(int(unix_time[0])) <= 10:
        raise ValueError(
            f"Refusing to save degenerate master time profile: all {len(unix_time)} unix values are "
            f"{int(unix_time[0])}. This usually means circuit.time_profile was overwritten before saving."
        )

    data['time'] = {'unix': unix_time.tolist(),
                    'prob': list(np.ones(len(unix_time))),
                    'snapshot_unix': circuit.get_snapshot_time_unix()}

    # gather the circuit
    circuit.model_version += 1
    data['circuit'] = circuit.to_dict()

    # At this point I already have the symbolic data stored in block_saver

    return {
        "model_data": data,
        "symbolic_data": {
            "vars": block_saver.get_vars_to_save(),
            "consts": block_saver.get_const_to_save(),
            "diff_vars": block_saver.get_diff_vars_to_save(),
            "shared_references": block_saver.get_shared_references_to_save(),
            "connections": block_saver.get_connections_to_save(),
            "blocks": block_saver.get_blocks(),
            "main_block_uids": block_saver.main_block_uids,
        }
    }


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
        # The property is not in the headers, so search the legacy-name list.
        current_prop_name = old_props_dict.get(property_to_search, None)

        if current_prop_name:

            logger.add_info('The file property was updated in the data model',
                            device=str(template_elm.device_type),
                            value=property_to_search)

            gc_prop = template_elm.registered_properties.get(current_prop_name, None)
            return gc_prop
        else:
            # A property absent from both registries identifies invalid input.
            logger.add_error('The property does not exist in the registries',
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
        # A missing direct property may still use a legacy property name.
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

    __slots__ = (
        "legacy_area_dict",
        "legacy_zone_dict",
        "legacy_substation_dict",
        "contingency_groups",
        "contingencies",
        "technologies",
    )

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
        conn = dev.Contingency(device=elm, prop=ContingencyOperationTypes.Active, group=con_group)

        self.contingency_groups.append(con_group)
        self.contingencies.append(conn)

    def create_technology(self, elm: dev.Generator, tech_name: str) -> None:
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


def parse_object_type_from_dataframe(
        main_df: pd.DataFrame,
        template_elm: ALL_DEV_TYPES,
        elements_dict_by_type: Dict[DeviceType, Dict[str, ALL_DEV_TYPES]],
        time_profile: pd.DatetimeIndex,
        object_type_key: str,
        data: Dict[str, Union[float, str, pd.DataFrame]],
        logger: Logger,
        reflexive_references: List[Tuple[ALL_DEV_TYPES, GCProp, str]],
        physical_device_references: List[Tuple[ALL_DEV_TYPES, GCProp, str]]) -> Tuple[
            List[ALL_DEV_TYPES], Dict[str, ALL_DEV_TYPES], CreatedOnTheFly]:
    """
    Convert a DataFrame to a list of VeraGrid devices
    :param main_df: DataFrame to convert
    :param template_elm: Element to use as template for conversion
    :param elements_dict_by_type: Dictionary of devices grouped by type used to look for referenced objects
                                    elements_dict_by_type[DeviceType][idtag] -> device
    :param time_profile: Master time profile
    :param object_type_key: Object type naming to find the profile
    :param data: Complete data collection to find the profiles
    :param logger: Logger instance
    :param reflexive_references: References to resolve after all device types are loaded
    :param physical_device_references: References to resolve against all physical devices
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
        elm.disable_auto_updates()

        # ensure the profiles existence
        if time_profile is None or time_profile is pd.NaT:
            nt = 0
        else:
            nt = len(time_profile)
            if nt > 0:
                elm.ensure_profiles_exist(index=time_profile)

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
                            # we must look for the reference in elements_dict
                            collection = elements_dict_by_type.get(gc_prop.tpe, None)

                            if collection is not None:
                                ref_idtag = str(property_value)
                                ref_elm = collection.get(ref_idtag, None)

                                if ref_elm is not None:
                                    if gc_prop.reflexive:
                                        reflexive_references.append((elm, gc_prop, ref_idtag))
                                    else:
                                        elm.set_snapshot_value(gc_prop.name, ref_elm)

                                        if gc_prop.has_profile():
                                            prof.fill(ref_elm)
                                elif gc_prop.reflexive:
                                    reflexive_references.append((elm, gc_prop, ref_idtag))
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
                                        logger.add_error("Could not locate reference",
                                                         device=row.get('idtag', 'not provided'),
                                                         device_class=template_elm.device_type.value,
                                                         device_property=gc_prop.name,
                                                         value=ref_idtag)
                            elif gc_prop.reflexive:
                                reflexive_references.append((elm, gc_prop, str(property_value)))
                            elif gc_prop.tpe == DeviceType.PhysicalDeviceType:
                                if isinstance(elm, PointerDeviceParent):
                                    # PointerDeviceParent resolves this after parsing its concrete tpe.
                                    pass
                                else:
                                    physical_device_references.append((elm, gc_prop, str(property_value)))
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

                                    logger.add_error("No device of the referenced type",
                                                     device=row.get('idtag', 'not provided'),
                                                     device_class=template_elm.device_type.value,
                                                     device_property=gc_prop.name,
                                                     value=property_value)

                        elif isinstance(gc_prop.tpe, SubObjectType):

                            if gc_prop.tpe == SubObjectType.GeneratorQCurve:
                                q_curve: devices.GeneratorQCurve = elm.get_snapshot_value(gc_prop)

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
                            val, ok = set_enum_snapshot_value(elm=elm,
                                                              gc_prop=gc_prop,
                                                              property_value=property_value,
                                                              logger=logger)
                            if ok and gc_prop.has_profile():
                                prof.fill(val)

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
                            try:
                                elm.set_profile(gc_prop, arr=dfp.values[:, i].astype(gc_prop.tpe))
                            except TypeError:
                                logger.add_error(msg="Cannot set profile value",
                                                 device_property=gc_prop.profile_name,
                                                 device=elm.name)

                        else:
                            skip = False
                            if gc_prop.name == 'bus':
                                skip = True

                            if not skip:
                                logger.add_info(msg='No profile for the property', value=gc_prop.name)

                else:
                    # The property exists under neither its current nor legacy name.
                    skip = False
                    if template_elm.device_type == DeviceType.ShuntDevice:
                        if property_name in ['is_controlled', 'Bmin', 'Bmax', 'Vset']:
                            skip = True

                    if template_elm.device_type == DeviceType.Transformer2WDevice:
                        if property_name == 'control_mode':
                            if "Pf" in property_value:
                                elm.tap_phase_control_mode = TapPhaseControl.Pf
                                skip = True
                            if "Pt" in property_value:
                                elm.tap_phase_control_mode = TapPhaseControl.Pt
                                skip = True
                            if "V" in property_value:
                                elm.tap_module_control_mode = TapModuleControl.Vm
                                elm.regulation_bus = elm.bus_to
                                skip = True
                            if "Qf" in property_value:
                                elm.tap_module_control_mode = TapModuleControl.Qf
                                skip = True
                            if "Qt" in property_value:
                                elm.tap_module_control_mode = TapModuleControl.Qt
                                skip = True
                            if "fixed" in property_value:
                                elm.tap_module_control_mode = TapModuleControl.fixed
                                elm.tap_phase_control_mode = TapPhaseControl.fixed
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


def search_property_into_json(json_entry: dict, prop: GCProp):
    """
    Find a property in one JSON entry.
    :param json_entry: JSON declaration for one object.
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


def set_enum_snapshot_value(elm: ALL_DEV_TYPES,
                            gc_prop: GCProp,
                            property_value: Any,
                            logger: Logger) -> tuple[Any, bool]:
    """
    Set one enum snapshot value, allowing property setters to translate legacy values.
    :return: (typed value, success)
    """
    try:
        val = gc_prop.tpe(property_value)
    except (TypeError, ValueError):
        try:
            elm.set_snapshot_value(gc_prop.name, property_value)
        except (TypeError, ValueError) as e:
            logger.add_error(f'Cannot cast the value to the snapshot',
                             device=elm.name,
                             value=property_value,
                             comment=str(e))
            return property_value, False

        val = elm.get_snapshot_value_by_name(gc_prop.name)
        if not isinstance(val, gc_prop.tpe):
            logger.add_error(f'Cannot cast the value to the snapshot',
                             device=elm.name,
                             value=property_value)
            return property_value, False
    else:
        try:
            elm.set_snapshot_value(gc_prop.name, val)
        except (TypeError, ValueError) as e:
            logger.add_error(f'Cannot set the snapshot',
                             device=elm.name,
                             value=property_value,
                             comment=str(e))
            return property_value, False

    return val, True


def search_and_apply_json_profile(json_entry: Dict[str, Dict[str, Union[str, Union[Any, Dict[str, Any]]]]],
                                  gc_prop: GCProp,
                                  elm: ALL_DEV_TYPES,
                                  property_value: Any,
                                  collection: Union[None, Dict[str, Any]] = None) -> None:
    """
    Find and apply property profiles declared in JSON.
    :param json_entry: JSON entry for one object.
    :param gc_prop: GCProp
    :param elm: THe device to set the profile into
    :param property_value: The snapshot value
    :param collection: if the collection is provided, it will be used to convert idtags into objects
    :return: None
    """
    if gc_prop.has_profile():

        # Resolve the profile from the JSON declaration.
        json_profile = json_entry.get(gc_prop.profile_name, None)

        profile: AnyProfile = elm.get_profile(magnitude=gc_prop.name)

        if json_profile is None:
            # the profile was not found, so we fill it with the default stuff
            profile.fill(property_value)
        else:
            get_profile_from_dict(profile=profile,
                                  data=json_profile,
                                  collection=collection)


def parse_object_type_from_json(template_elm: ALL_DEV_TYPES,
                                data_list: List[Dict[str, Dict[str, str]]],
                                elements_dict_by_type: Dict[DeviceType, Dict[str, ALL_DEV_TYPES]],
                                time_profile: pd.DatetimeIndex,
                                block_parser: BlockParser,
                                logger: Logger,
                                text_func: Union[Callable, None] = None,
                                reflexive_references: List[Tuple[ALL_DEV_TYPES, GCProp, str]] | None = None,
                                physical_device_references: List[Tuple[ALL_DEV_TYPES, GCProp, str]] | None = None):
    """

    :param template_elm:
    :param data_list:
    :param elements_dict_by_type:
    :param time_profile:
    :param block_parser:
    :param logger:
    :param text_func:
    :param reflexive_references:
    :param physical_device_references:
    :return:
    """
    # dictionary to be filled with this type of objects
    devices_dict: Dict[str, ALL_DEV_TYPES] = dict()
    parsed_devices: List[ALL_DEV_TYPES] = list()
    tpe_key = template_elm.device_type.value
    obj_num = len(data_list)
    for obj_i, json_entry in enumerate(data_list):

        if text_func is not None:
            text_func(f"Parsing {tpe_key} model data ({obj_i}/{obj_num})")

        idtag = json_entry['idtag']
        elm: ALL_DEV_TYPES = type(template_elm)(idtag=idtag)
        elm.disable_auto_updates()

        # ensure the profiles existence
        if time_profile is not None:
            elm.ensure_profiles_exist(index=time_profile)

        for property_name, gc_prop in template_elm.registered_properties.items():

            # Resolve the property from the JSON declaration.
            property_value = search_property_into_json(json_entry=json_entry, prop=gc_prop)

            if property_value is not None:

                if property_name != 'idtag':  # idtag was set already
                    # gc_prop: GCProp = look_for_property(elm=elm, property_name=property_name)

                    if gc_prop is not None:

                        if valid_value(property_value):

                            if isinstance(gc_prop.tpe, DeviceType):

                                if gc_prop.tpe == DeviceType.AnyLineTemplateDevice:
                                    # this is an exception, when dealing with line templates we need to look for
                                    # several types, not only one
                                    seq_templates = elements_dict_by_type.get(DeviceType.OverheadLineTypeDevice, dict())
                                    oh_templates = elements_dict_by_type.get(DeviceType.SequenceLineDevice, dict())
                                    ug_templates = elements_dict_by_type.get(DeviceType.UnderGroundLineDevice, dict())
                                    collection = {**seq_templates, **oh_templates, **ug_templates}

                                elif gc_prop.tpe == DeviceType.BusOrBranch:
                                    bus_dic = elements_dict_by_type.get(DeviceType.BusDevice, None)
                                    lines_dict = elements_dict_by_type.get(DeviceType.LineDevice, None)

                                    if bus_dic is not None and lines_dict is not None:
                                        collection = bus_dic | lines_dict
                                    elif bus_dic is not None and lines_dict is None:
                                        collection = bus_dic
                                    elif bus_dic is None and lines_dict is not None:
                                        collection = bus_dic
                                    else:
                                        collection = None
                                else:
                                    # this is a hyperlink to another object
                                    # we must look for the reference in elements_dict
                                    collection = elements_dict_by_type.get(gc_prop.tpe, None)

                                ref_idtag = str(property_value)
                                if gc_prop.reflexive and reflexive_references is not None:
                                    reflexive_references.append((elm, gc_prop, ref_idtag))

                                elif collection is not None:
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
                                elif gc_prop.tpe == DeviceType.PhysicalDeviceType:
                                    if isinstance(elm, PointerDeviceParent):
                                        # PointerDeviceParent resolves this after parsing its concrete tpe.
                                        pass
                                    elif physical_device_references is not None:
                                        physical_device_references.append((elm, gc_prop, ref_idtag))
                                    else:
                                        logger.add_error("No device of the referenced type",
                                                         device=elm.idtag,
                                                         device_class=template_elm.device_type.value,
                                                         device_property=gc_prop.name,
                                                         value=property_value)
                                else:
                                    logger.add_error("No device of the referenced type",
                                                     device=elm.idtag,
                                                     device_class=template_elm.device_type.value,
                                                     device_property=gc_prop.name,
                                                     value=property_value)

                            elif isinstance(gc_prop.tpe, SubObjectType):  # this is a hyperlink to another object

                                if gc_prop.tpe == SubObjectType.ManufacturerNativeModelInfo:
                                    if not isinstance(property_value, dict):
                                        raise TypeError("ModelInfo must use a declarative canonical_hex envelope")
                                    else:
                                        pass
                                    if set(property_value.keys()) != {"schema_version", "canonical_hex"}:
                                        raise ValueError("ModelInfo envelope must contain exactly schema_version and canonical_hex")
                                    else:
                                        pass
                                    schema_version: object = property_value["schema_version"]
                                    if (
                                            not isinstance(schema_version, int)
                                            or isinstance(schema_version, bool)
                                            or schema_version not in (1, 2)
                                    ):
                                        raise ValueError("Unsupported canonical ModelInfo schema version")
                                    else:
                                        pass
                                    canonical_hex: object = property_value["canonical_hex"]
                                    if not isinstance(canonical_hex, str) or len(canonical_hex) % 2 != 0:
                                        raise TypeError("Canonical ModelInfo hexadecimal bytes are invalid")
                                    else:
                                        canonical_bytes: bytes = bytes.fromhex(canonical_hex)
                                    if canonical_bytes.hex() != canonical_hex:
                                        raise ValueError("Canonical ModelInfo hex must be lowercase")
                                    else:
                                        pass
                                    if schema_version == 1:
                                        if not canonical_bytes.startswith(b"veragrid-ieee-cigre-model-info-v1\n"):
                                            raise ValueError("Canonical ModelInfo envelope schema does not match its bytes")
                                        else:
                                            pass
                                    else:
                                        if not canonical_bytes.startswith(
                                                b"veragrid-manufacturer-native-model-info-v2\n"
                                        ):
                                            raise ValueError("Canonical ModelInfo envelope schema does not match its bytes")
                                        else:
                                            pass
                                    decode_manufacturer_native_model_info(canonical_bytes)
                                    elm.set_snapshot_value(gc_prop.name, canonical_bytes)

                                elif gc_prop.tpe == SubObjectType.GeneratorQCurve:

                                    # Fill the curve object from its JSON declaration.
                                    q_curve: dev.GeneratorQCurve = elm.get_snapshot_value(prop=gc_prop)
                                    if isinstance(property_value, str):
                                        q_curve.parse(json.loads(property_value))
                                    else:
                                        q_curve.parse(data=property_value)

                                elif gc_prop.tpe == SubObjectType.LineLocations:

                                    # Fill the line locations from their JSON declaration.
                                    locations_obj: dev.LineLocations = elm.get_snapshot_value(prop=gc_prop)
                                    locations_obj.parse(property_value)

                                elif gc_prop.tpe == SubObjectType.ListOfWires:

                                    # Fill the wire collection from its JSON declaration.
                                    list_of_wires: dev.ListOfWires = elm.get_snapshot_value(prop=gc_prop)
                                    list_of_wires.parse(data=property_value,
                                                        wire_dict=elements_dict_by_type[DeviceType.WireDevice])

                                elif gc_prop.tpe == SubObjectType.ListOfCables:

                                    # Fill cable systems after their physical cable catalogue is available.
                                    list_of_cables: dev.ListOfCables = elm.get_snapshot_value(prop=gc_prop)
                                    list_of_cables.parse(
                                        data=property_value,
                                        cable_dict=elements_dict_by_type[DeviceType.UndergroundCableTypeDevice],
                                    )


                                elif gc_prop.tpe == SubObjectType.ImpedanceTripletList:

                                    # Fill the impedance triplets from their JSON declaration.
                                    impedance_triplet_list: dev.ImpedanceTripletList = elm.get_snapshot_value(
                                        prop=gc_prop)
                                    impedance_triplet_list.parse(data=property_value)

                                elif gc_prop.tpe == SubObjectType.TapChanger:

                                    # Fill the tap changer from its JSON declaration.
                                    tc_obj: dev.TapChanger = elm.get_snapshot_value(prop=gc_prop)
                                    tc_obj.parse(property_value, logger=logger)

                                elif gc_prop.tpe == SubObjectType.Array:

                                    val = np.array(property_value)
                                    elm.set_snapshot_value(gc_prop.name, val)

                                elif gc_prop.tpe == SubObjectType.AdmittanceMatrix:

                                    # Fill the admittance matrix from its JSON declaration.
                                    adm_mat: dev.AdmittanceMatrix = elm.get_snapshot_value(prop=gc_prop)
                                    adm_mat.parse(property_value)

                                elif gc_prop.tpe == SubObjectType.DaeBlockType:

                                    # handle the ModelHost
                                    if isinstance(property_value, dict):

                                        key = property_value.get("model", None)
                                        if key is None:
                                            logger.add_error("Could not locate model", value=property_value)
                                        else:
                                            blk = block_parser.block_dict.get(key, None)
                                            elm.set_snapshot_value(gc_prop.name, blk)
                                    else:
                                        blk = block_parser.block_dict.get(property_value, None)
                                        if blk is None:
                                            logger.add_error("Block not found",
                                                             device=elm.name,
                                                             value=property_value,
                                                             device_class=elm.device_type.value,
                                                             device_property=gc_prop.name
                                                             )
                                        else:
                                            elm.set_snapshot_value(gc_prop.name, blk)


                                elif gc_prop.tpe == SubObjectType.VarType:

                                    # set the value of the property
                                    vl = block_parser.var_factory.get_var(property_value)
                                    elm.set_snapshot_value(gc_prop.name, vl)

                                elif gc_prop.tpe == SubObjectType.ConstType:

                                    # set the value of the property
                                    vl = block_parser.var_factory.get_const(property_value)
                                    elm.set_snapshot_value(gc_prop.name, vl)

                                elif gc_prop.tpe == SubObjectType.Associations:

                                    # get the list of associations
                                    associations = elm.get_snapshot_value(gc_prop)
                                    associations.parse(
                                        data=property_value,
                                        elements_dict=elements_dict_by_type.get(associations.device_type, {}),
                                        logger=logger,
                                        elm_name=elm.name
                                    )

                                elif gc_prop.tpe == SubObjectType.MergeInformation:
                                    # set the value directly
                                    elm.diff_changes.parse(property_value)

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
                                val, ok = set_enum_snapshot_value(elm=elm,
                                                                  gc_prop=gc_prop,
                                                                  property_value=property_value,
                                                                  logger=logger)
                                if ok:
                                    try:
                                        search_and_apply_json_profile(json_entry=json_entry,
                                                                      gc_prop=gc_prop,
                                                                      elm=elm,
                                                                      property_value=val)

                                    except ValueError as e:
                                        logger.add_error(f'Cannot set the profile',
                                                         device=elm.name,
                                                         value=property_value,
                                                         comment=str(e))

                            else:
                                raise Exception(f'Unsupported property type: {gc_prop.tpe} for {gc_prop.name}')

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
                # The object property was not present in the JSON entry.
                pass

        if template_elm.device_type == DeviceType.Transformer3WDevice:
            for property_name in ('r12', 'r23', 'r31', 'x12', 'x23', 'x31', 'rate1', 'rate2', 'rate3'):
                gc_prop = template_elm.registered_properties[property_name]
                property_value = search_property_into_json(json_entry=json_entry, prop=gc_prop)
                if property_value is not None:
                    elm.set_snapshot_value(gc_prop.name, float(property_value))

        if template_elm.device_type == DeviceType.LineDevice:
            gc_prop = template_elm.registered_properties.get('length', None)
            if gc_prop is not None:
                property_value = search_property_into_json(json_entry=json_entry, prop=gc_prop)
                if property_value is not None and float(property_value) == 0.0:
                    elm._length = 0.0

        if isinstance(elm, ManufacturerNativeModel):
            raw_variants: object = json_entry.get("binary_variants", None)
            if not isinstance(raw_variants, list):
                raise TypeError("Manufacturer native provider requires a binary_variants list")
            else:
                pass
            if len(raw_variants) > 3:
                raise ValueError("Manufacturer native provider has too many platform variants")
            else:
                pass
            raw_variant: object
            for raw_variant in raw_variants:
                if not isinstance(raw_variant, dict):
                    raise TypeError("Manufacturer native binary variant must be a record")
                else:
                    pass
                expected_fields: Set[str] = {
                    "platform", "extension", "content_sha256", "byte_size",
                    "zip_member", "verification_status",
                }
                if set(raw_variant.keys()) != expected_fields:
                    raise ValueError("Manufacturer native binary variant has missing or extra fields")
                else:
                    pass
                platform: IeeeCigreDllPlatform = IeeeCigreDllPlatform(raw_variant["platform"])
                if elm.get_platform_variant(platform) is not None:
                    raise ValueError("Manufacturer native platform variant is duplicated")
                else:
                    pass
                byte_size: object = raw_variant["byte_size"]
                if not isinstance(byte_size, int) or isinstance(byte_size, bool):
                    raise TypeError("Manufacturer native binary byte_size must be an integer")
                else:
                    pass
                variant: ManufacturerNativeBinaryVariant = ManufacturerNativeBinaryVariant(
                    platform=platform,
                    extension=str(raw_variant["extension"]),
                    content_sha256=str(raw_variant["content_sha256"]),
                    byte_size=byte_size,
                    zip_member=str(raw_variant["zip_member"]),
                    verification_status=IeeeCigreDllVerificationStatus(raw_variant["verification_status"]),
                )
                elm.set_platform_variant(variant)
            if len(elm.model_info) == 0:
                raise ValueError("Manufacturer native provider is missing canonical ModelInfo")
            else:
                persisted_model_info: ManufacturerNativeModelInfo = (
                    decode_manufacturer_native_model_info(elm.model_info)
                )
            if persisted_model_info.native_interface != elm.native_interface:
                raise ValueError(
                    "Manufacturer native interface does not match canonical ModelInfo"
                )
            else:
                pass
            if elm.model_info.startswith(b"veragrid-manufacturer-native-model-info-v2\n"):
                persisted_schema_version: int = 2
            else:
                persisted_schema_version = 1
            if persisted_schema_version != elm.model_info_schema_version:
                raise ValueError(
                    "Manufacturer native schema version does not match canonical ModelInfo"
                )
            else:
                pass
        # save the element in the dictionary for later
        devices_dict[elm.idtag] = elm
        parsed_devices.append(elm)
    return parsed_devices, devices_dict


def handle_legacy_jsons(model_data: Dict[str, List],
                        elements_dict_by_type: Dict[DeviceType, Dict],
                        logger: Logger) -> None:
    """
    Handle those legacy structures that were deprecated and removed from VeraGrid's structure
    :param model_data:
    :param elements_dict_by_type:
    :param logger:
    :return:
    """
    # The first resistance selector only controlled the core. Recover the
    # former sheath material definition before the shared selector is used.
    cable_types = elements_dict_by_type.get(DeviceType.UndergroundCableTypeDevice, {})
    for entry in model_data.get('underground_cable_constructions', []):
        if ('core_resistance_input' in entry and 'resistance_input' not in entry
                and 'sheath_dc_resistance' not in entry):
            cable = cable_types.get(entry.get('idtag'))
            if cable is not None:
                cable.sheath_dc_resistance = cable.get_sheath_dc_resistance_from_material()
                logger.add_info('Recovered sheath resistance for legacy core-only input selector', device=cable.name)

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
            emission_idtag = entry.get('emission', None)
            rate = entry.get('rate', 1.0)
            generator = elements_dict_by_type[DeviceType.GeneratorDevice].get(gen_idtag, None)
            emission = elements_dict_by_type[DeviceType.EmissionGasDevice].get(emission_idtag, None)
            if generator is not None and emission is not None:
                generator.emissions.add_object(api_object=emission, val=rate)
                logger.add_info("Converted legacy generator emission association",
                                device_class="generator_emission",
                                value=f"{generator.name} -> {emission.name} at {rate}")



def normalize_dynamic_legacy(data: VERAGRID_FILE_TYPE,
                             logger: Logger) -> Dict[str, Any] | None:
    """
    Normalize previous VeraGrid versions which used different mappings in the dynamic symbolism:
    - Some static mapping ParamPowerFlowReferenceType are now named differently.
    - Duplicated mapping of some parameters both in the parent block and the child block.

    :param data: veragrid file data
    :param logger: logger object used
    :return symbolic_data: symbolic dictionary or None, if there's no symbolic data.
    """

    symbolic_data: Dict[str, Any] | None = data.get('symbolic_data', None)

    if symbolic_data is not None:
        if len(symbolic_data) > 0:
            # Every historical symbolic container is first converted to the flat
            # UID-indexed representation consumed by the current BlockParser. The
            # compatibility branches below can then inspect one stable structure
            # instead of repeating the list, dictionary and inline-child cases.
            blocks_data = normalize_persisted_blocks(
                blocks_data=symbolic_data.get("blocks", dict())
            )
            symbolic_data["blocks"] = blocks_data

            # Transformer static mappings written by the first dynamic editor used
            # transformer-specific names. Those enum members were later replaced by
            # the generic branch names. Rename the persisted keys while preserving
            # their symbolic target UID so the current enum can rebuild the mapping.
            legacy_mapping_names: List[Tuple[str, str]] = list()
            legacy_mapping_names.append(("transformer_tap_module", "tap_module"))
            legacy_mapping_names.append(("transformer_tap_phase", "tap_phase"))
            converted_mapping_count: int = 0

            block_uid: int
            block_data: Dict[str, Any]
            for block_uid, block_data in blocks_data.items():
                raw_api_obj_mapping: Any = block_data.get("api_obj_mapping", dict())
                if isinstance(raw_api_obj_mapping, dict):
                    api_obj_mapping: Dict[str, Any] = raw_api_obj_mapping
                    legacy_mapping_name: str
                    current_mapping_name: str
                    for legacy_mapping_name, current_mapping_name in legacy_mapping_names:
                        if legacy_mapping_name in api_obj_mapping:
                            legacy_target_uid: Any = api_obj_mapping[legacy_mapping_name]
                            if current_mapping_name in api_obj_mapping:
                                current_target_uid: Any = api_obj_mapping[current_mapping_name]
                                if current_target_uid != legacy_target_uid:
                                    logger.add_warning(
                                        msg="Conflicting legacy dynamic static mapping",
                                        device=block_data.get("name", ""),
                                        value=legacy_target_uid,
                                        expected_value=current_target_uid,
                                        device_property=legacy_mapping_name,
                                        device_class=f"Block:{block_uid}",
                                    )
                                else:
                                    pass
                            else:
                                api_obj_mapping[current_mapping_name] = legacy_target_uid

                            # The legacy key must not reach ParamPowerFlowReferenceType,
                            # even when both representations were present in the file.
                            del api_obj_mapping[legacy_mapping_name]
                            converted_mapping_count += 1
                        else:
                            pass
                else:
                    logger.add_warning(
                        msg="Invalid dynamic static mapping container",
                        device=block_data.get("name", ""),
                        value=str(type(raw_api_obj_mapping)),
                        expected_value="dictionary",
                        device_property="api_obj_mapping",
                        device_class=f"Block:{block_uid}",
                    )

            if converted_mapping_count > 0:
                logger.add_info(
                    msg="Converted legacy transformer dynamic static mappings",
                    value=converted_mapping_count,
                )
            else:
                pass

            # Dynamic-editor files from the affected releases persisted the line
            # admittance constants both on the device wrapper and on its template
            # child. The wrapper owns the static-device mapping, while the child is
            # the semantic owner of the parameter declaration. Removing only the
            # duplicate wrapper declaration reproduces the current persisted form
            # without losing the authoritative static mapping.
            legacy_static_mapping_names: List[str] = list()
            legacy_static_mapping_names.append("g")
            legacy_static_mapping_names.append("b")
            legacy_static_mapping_names.append("bsh")
            removed_wrapper_parameter_count: int = 0

            for block_uid, block_data in blocks_data.items():
                raw_api_obj_mapping = block_data.get("api_obj_mapping", dict())
                raw_root_parameters: Any = block_data.get("parameters", list())
                if isinstance(raw_api_obj_mapping, dict) and isinstance(raw_root_parameters, list):
                    api_obj_mapping = raw_api_obj_mapping
                    root_parameters: List[Any] = raw_root_parameters

                    # Gather parameter ownership from the complete descendant tree.
                    # This is intentionally iterative because nested functions are
                    # forbidden and historical templates can contain several levels.
                    descendant_parameter_uids: set[int] = set()
                    pending_child_uids: List[int] = list()
                    visited_child_uids: set[int] = set()
                    child_entry: Any
                    for child_entry in block_data.get("children", list()):
                        if isinstance(child_entry, dict):
                            child_uid: int | None = normalize_persisted_block_uid(
                                child_entry.get("uid", None)
                            )
                        else:
                            child_uid = normalize_persisted_block_uid(child_entry)

                        if child_uid is not None:
                            pending_child_uids.append(child_uid)
                        else:
                            pass

                    while len(pending_child_uids) > 0:
                        child_uid = pending_child_uids.pop()
                        if child_uid not in visited_child_uids:
                            visited_child_uids.add(child_uid)
                            child_block_data: Dict[str, Any] | None = blocks_data.get(child_uid, None)
                            if child_block_data is not None:
                                raw_child_parameters: Any = child_block_data.get("parameters", list())
                                if isinstance(raw_child_parameters, list):
                                    child_parameter_entry: Any
                                    for child_parameter_entry in raw_child_parameters:
                                        if isinstance(child_parameter_entry, dict):
                                            child_parameter_uid: int | None = normalize_persisted_block_uid(
                                                child_parameter_entry.get("var", None)
                                            )
                                            if child_parameter_uid is not None:
                                                descendant_parameter_uids.add(child_parameter_uid)
                                            else:
                                                pass
                                        else:
                                            pass
                                else:
                                    pass

                                grandchild_entry: Any
                                for grandchild_entry in child_block_data.get("children", list()):
                                    if isinstance(grandchild_entry, dict):
                                        grandchild_uid: int | None = normalize_persisted_block_uid(
                                            grandchild_entry.get("uid", None)
                                        )
                                    else:
                                        grandchild_uid = normalize_persisted_block_uid(grandchild_entry)

                                    if grandchild_uid is not None:
                                        if grandchild_uid not in visited_child_uids:
                                            pending_child_uids.append(grandchild_uid)
                                        else:
                                            pass
                                    else:
                                        pass
                            else:
                                pass
                        else:
                            pass

                    duplicate_wrapper_parameter_uids: set[int] = set()
                    static_mapping_name: str
                    for static_mapping_name in legacy_static_mapping_names:
                        if static_mapping_name in api_obj_mapping:
                            mapped_parameter_uid: int | None = normalize_persisted_block_uid(
                                api_obj_mapping[static_mapping_name]
                            )
                            if mapped_parameter_uid is not None:
                                if mapped_parameter_uid in descendant_parameter_uids:
                                    duplicate_wrapper_parameter_uids.add(mapped_parameter_uid)
                                else:
                                    pass
                            else:
                                pass
                        else:
                            pass

                    if len(duplicate_wrapper_parameter_uids) > 0:
                        filtered_root_parameters: List[Any] = list()
                        root_parameter_entry: Any
                        for root_parameter_entry in root_parameters:
                            if isinstance(root_parameter_entry, dict):
                                root_parameter_uid: int | None = normalize_persisted_block_uid(
                                    root_parameter_entry.get("var", None)
                                )
                                if root_parameter_uid in duplicate_wrapper_parameter_uids:
                                    removed_wrapper_parameter_count += 1
                                else:
                                    filtered_root_parameters.append(root_parameter_entry)
                            else:
                                filtered_root_parameters.append(root_parameter_entry)

                        block_data["parameters"] = filtered_root_parameters
                    else:
                        pass
                else:
                    pass

            if removed_wrapper_parameter_count > 0:
                logger.add_info(
                    msg="Removed duplicate legacy wrapper static parameters",
                    value=removed_wrapper_parameter_count,
                    device_property="g, b, bsh",
                )
            else:
                pass
        else:
            pass
    else:
        pass

    return symbolic_data


def migrate_dc_cable_types(data: VERAGRID_FILE_TYPE, logger: Logger) -> None:
    """Move legacy DC providers into Cable System before resolving references.

    Preserve identifiers and dynamic associations. The former C field is in
    F/km; Cable System stores microfarad/km. A 50 Hz representation preserves
    the original frequency-neutral L/C exactly up to floating-point rounding.
    Both native JSON and legacy DataFrame tables are accepted.
    """
    omega = 2.0 * np.pi * 50.0

    def convert(record: dict) -> dict:
        result = dict(record)
        result['freq'] = 50.0
        result['X'] = float(result.pop('L', 0.0)) * omega
        result['C'] = float(result.get('C', 0.0)) * 1.0e6
        result['B'] = result['C'] * omega
        return result

    model_data = data.get('model_data')
    if model_data is not None and 'dc_cable_types' in model_data:
        legacy = model_data.pop('dc_cable_types')
        existing = model_data.setdefault('underground_cable_types', [])
        existing_ids = {item.get('idtag') for item in existing}
        for record in legacy:
            if record.get('idtag') in existing_ids:
                logger.add_warning('Duplicate legacy DC cable identifier; keeping Cable System',
                                   device=record.get('idtag'))
            else:
                existing.append(convert(record))
                existing_ids.add(record.get('idtag'))
        if legacy:
            logger.add_info('Migrated DC cable types to Cable System', value=len(legacy))

    legacy_df = data.pop('dc_cable_types', None)
    if legacy_df is not None and not legacy_df.empty:
        converted = pd.DataFrame([convert(row) for row in legacy_df.to_dict('records')])
        existing_df = data.get('underground_cable_types')
        if existing_df is not None and not existing_df.empty:
            converted = pd.concat([existing_df, converted], ignore_index=True)
        data['underground_cable_types'] = converted
        logger.add_info('Migrated DC cable table to Cable System', value=len(legacy_df))


def resolve_reflexive_references(device_type: DeviceType,
                                elements_dict_by_type: Dict[DeviceType, Dict[str, ALL_DEV_TYPES]],
                                reflexive_references: List[Tuple[ALL_DEV_TYPES, GCProp, str]],
                                logger: Logger) -> None:
    """Resolve deferred references once their target device type is fully loaded.

    :param device_type: Type whose objects have just been registered.
    :param elements_dict_by_type: Loaded objects indexed by type and idtag.
    :param reflexive_references: Deferred source-property-idtag triples; resolved entries are removed.
    :param logger: Logger for missing targets or rejected assignments.
    :return: None.
    """
    collection = elements_dict_by_type.get(device_type, None)
    remaining_references: List[Tuple[ALL_DEV_TYPES, GCProp, str]] = list()

    for source_elm, gc_prop, ref_idtag in reflexive_references:
        if gc_prop.tpe == device_type:
            if collection is not None:
                ref_elm = collection.get(ref_idtag, None)
                if ref_elm is not None:
                    try:
                        source_elm.set_snapshot_value(gc_prop.name, ref_elm)
                    except (TypeError, ValueError) as error:
                        logger.add_error("Could not set reference",
                                         device=source_elm.idtag,
                                         device_class=source_elm.device_type.value,
                                         device_property=gc_prop.name,
                                         value=ref_idtag,
                                         comment=str(error))
                else:
                    logger.add_error("Could not locate reference",
                                     device=source_elm.idtag,
                                     device_class=source_elm.device_type.value,
                                     device_property=gc_prop.name,
                                     value=ref_idtag)
            else:
                logger.add_error("No device of the referenced type",
                                 device=source_elm.idtag,
                                 device_class=source_elm.device_type.value,
                                 device_property=gc_prop.name,
                                 value=ref_idtag)
        else:
            remaining_references.append((source_elm, gc_prop, ref_idtag))

    reflexive_references[:] = remaining_references


def parse_veragrid_data(data: VERAGRID_FILE_TYPE,
                        previous_circuit: Union[MultiCircuit, None] = None,
                        project_directory: str | Path | None = None,
                        refine_pointers: bool = True,
                        text_func: Union[Callable, None] = None,
                        progress_func: Union[Callable, None] = None,
                        logger: Logger = Logger()) -> MultiCircuit:
    """
    Interpret data
    :param project_directory: file project directory
    :param refine_pointers: Refine (and possibly delete) the pointer objects such as investments and contingencies?
    :param data: dictionary of data frames and other information
    :param previous_circuit: Optional previous VeraGrid circuit. This is relevant in case of loading grid increments
    :param text_func: text callback function
    :param progress_func: progress callback function
    :param logger: Logger to register events
    :return: MultiCircuit instance
    """
    migrate_dc_cable_types(data=data, logger=logger)

    # create circuit
    circuit = MultiCircuit()

    # Legacy circuit information parsing -------------------------------------------------------------------------------
    if 'name' in data.keys():
        circuit.name = str(data['name'])
        if circuit.name == 'nan':
            circuit.name = ''

    if 'idtag' in data.keys():
        val = str(data['idtag'])
        if val != '':
            circuit.idtag = val
        else:
            logger.add_warning("Had to create a new idtag", value=circuit.idtag)

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
    template_object_types = get_objects_dictionary()

    # time profile -----------------------------------------------------------------------------------------------------
    if 'time' in data.keys():
        time_df = data['time']
        try:
            circuit.time_profile = pd.to_datetime(time_df.values[:, 0], dayfirst=True, format='mixed')
        except ValueError:
            circuit.time_profile = pd.to_datetime(time_df.values[:, 0], dayfirst=True)
    else:
        circuit.time_profile = None

    # dictionary of dictionaries by element type
    if previous_circuit is None:
        elements_dict_by_type = dict()
    else:
        elements_dict_by_type = previous_circuit.get_all_elements_dict_by_type(add_locations=True, string_keys=False)

    # Reflexive references need all objects registered before resolving their IDs.
    reflexive_references: List[Tuple[ALL_DEV_TYPES, GCProp, str]] = list()
    physical_device_references: List[Tuple[ALL_DEV_TYPES, GCProp, str]] = list()

    # ------------------------------------------------------------------------------------------------------------------
    # Legacy DataFrame processing
    # for each element type...
    item_count = 0
    n_data_types = len(template_object_types)
    for object_type_key, template_elm in template_object_types.items():

        if text_func is not None:
            text_func(f"Parsing {object_type_key} table data...")

        # try to get the DataFrame
        # Todo: here we should get the data from template_object_types dict, not from data dict
        df = data.get(object_type_key, None)

        if df is not None:

            # fill in the objects
            if df.shape[0] > 0:

                parsed_devices, devices_dict, on_the_fly = parse_object_type_from_dataframe(
                    main_df=df,
                    template_elm=template_elm,
                    elements_dict_by_type=elements_dict_by_type,
                    time_profile=circuit.time_profile,
                    object_type_key=object_type_key,
                    data=data,
                    logger=logger,
                    reflexive_references=reflexive_references,
                    physical_device_references=physical_device_references
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

                # set/augment the dictionary per type for later
                prev_dict = elements_dict_by_type.get(template_elm.device_type, dict())
                elements_dict_by_type[template_elm.device_type] = dict(prev_dict, **devices_dict)

                resolve_reflexive_references(device_type=template_elm.device_type,
                                             elements_dict_by_type=elements_dict_by_type,
                                             reflexive_references=reflexive_references,
                                             logger=logger)

                # add the devices to the circuit
                circuit.set_elements_list_by_type(device_type=template_elm.device_type,
                                                  devices=parsed_devices,
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
    # Parse the declarative information stored in JSON ``.model`` files.
    # These files are just .json stored in the model_data inside the zip file

    model_data: Dict[str, Any] | None = data.get('model_data', None)

    # Allow compatibility with old VeraGrid versions
    symbolic_data = normalize_dynamic_legacy(data=data, logger=logger)

    if symbolic_data is not None:
        blocks_data = symbolic_data.get("blocks", dict())
    else:
        blocks_data = dict()

    block_parser = BlockParser(
        var_factory=circuit.var_factory,
        logger=logger,
        procedural_logic_codec=ProceduralLogicCodec(),
    )
    if symbolic_data is not None:
        if len(symbolic_data) > 0:
            if "shared_references" in symbolic_data:
                block_parser.parse_references(symbolic_data["shared_references"])
            else:
                pass
            block_parser.parse_consts(symbolic_data["consts"])
            block_parser.parse_vars(symbolic_data["vars"])
            block_parser.parse_diff_vars(symbolic_data["diff_vars"])

            if "connections" in symbolic_data:
                block_parser.parse_connections(symbolic_data["connections"])
            else:
                pass
            # BlockParser owns compatibility with all historical dynamics
            # containers, including list-based tables, inline children and
            # archives created before main_block_uids existed.
            block_parser.parse_blocks(blocks_data=blocks_data,
                                      main_block_uids=symbolic_data.get("main_block_uids", None))
        else:
            pass  # the symbolic data is empty
    else:
        pass  # there is no symbolic data records

    if model_data is not None:

        if len(model_data) > 0:

            # parse circuit own data
            circuit_data: Dict[str, str | int | float] | None = model_data.get('circuit', None)
            if circuit_data is not None:
                circuit.parse(data=circuit_data)

            # parse time
            tdata = model_data.get('time', None)
            if tdata is not None:
                circuit.set_unix_time(arr=tdata['unix'])

                snapshot_unix_time = tdata.get('snapshot_unix', None)
                if snapshot_unix_time is not None:
                    circuit.set_snapshot_time_unix(val=snapshot_unix_time)

            else:
                logger.add_error(msg=f'The file must have time data regardless of the profiles existence')
                circuit.time_profile = None

            # for each element type...
            item_count = 0
            n_data_types = len(template_object_types)
            for object_type_key, template_elm in template_object_types.items():

                if text_func is not None:
                    text_func(f"Parsing {object_type_key} model data...")

                # query the device type into the data set
                data_list = model_data.get(object_type_key, None)

                if data_list is not None:
                    parsed_devices, devices_dict = parse_object_type_from_json(
                        template_elm=template_elm,
                        data_list=data_list,
                        elements_dict_by_type=elements_dict_by_type,
                        time_profile=circuit.time_profile,
                        block_parser=block_parser,
                        logger=logger,
                        text_func=text_func,
                        reflexive_references=reflexive_references,
                        physical_device_references=physical_device_references
                    )

                    # set/augment the dictionary per type for later
                    prev_dict = elements_dict_by_type.get(template_elm.device_type, dict())
                    prev_dict.update(devices_dict)  # augment prev_dict with devices_dict
                    elements_dict_by_type[template_elm.device_type] = prev_dict

                    resolve_reflexive_references(device_type=template_elm.device_type,
                                                 elements_dict_by_type=elements_dict_by_type,
                                                 reflexive_references=reflexive_references,
                                                 logger=logger)

                    # add the devices to the circuit
                    circuit.set_elements_list_by_type(device_type=template_elm.device_type,
                                                      devices=parsed_devices,
                                                      logger=logger)
                else:
                    # Legacy and optional sections should not generate warnings when absent.
                    if object_type_key not in {'branch', 'fmu_template'}:
                        logger.add_warning(msg=f'No data for {object_type_key}')

                if progress_func is not None:
                    progress_func(float(item_count + 1) / float(n_data_types) * 100)

                item_count += 1

            # Handle the legacy objects that may be present in the data bus not declared in the program
            # i.e. generator_technology
            handle_legacy_jsons(model_data=model_data,
                                elements_dict_by_type=elements_dict_by_type,
                                logger=logger)

    all_elements_dict: Dict[str, ALL_DEV_TYPES] = dict()
    if len(physical_device_references) > 0:
        all_elements_dict, _ = circuit.get_all_elements_dict()
        for source_elm, gc_prop, ref_idtag in physical_device_references:
            ref_elm = all_elements_dict.get(ref_idtag, None)
            if ref_elm is not None:
                try:
                    source_elm.set_snapshot_value(gc_prop.name, ref_elm)
                except (TypeError, ValueError) as error:
                    logger.add_error("Could not set reference",
                                     device=source_elm.idtag,
                                     device_class=source_elm.device_type.value,
                                     device_property=gc_prop.name,
                                     value=ref_idtag,
                                     comment=str(error))
            else:
                logger.add_error("Could not locate reference",
                                 device=source_elm.idtag,
                                 device_class=source_elm.device_type.value,
                                 device_property=gc_prop.name,
                                 value=ref_idtag)
    else:
        pass

    # fill in device into pointer devices ------------------------------------------------------------------------------

    to_delete: List[ALL_DEV_TYPES] = list()
    for dtype in [
        DeviceType.PiMeasurementDevice,
        DeviceType.QiMeasurementDevice,
        DeviceType.PfMeasurementDevice,
        DeviceType.QfMeasurementDevice,
        DeviceType.PtMeasurementDevice,
        DeviceType.QtMeasurementDevice,
        DeviceType.PgMeasurementDevice,
        DeviceType.QgMeasurementDevice,
        DeviceType.IfMeasurementDevice,
        DeviceType.ItMeasurementDevice,
        DeviceType.VaMeasurementDevice,
        DeviceType.VmMeasurementDevice,
        DeviceType.ContingencyDevice,
        DeviceType.InvestmentDevice,
        DeviceType.RemedialActionDevice,
        DeviceType.RmsEventDevice,
        DeviceType.EmtEventDevice,
        DeviceType.ShortCircuitEvent
    ]:
        elms = circuit.get_elements_by_type(device_type=dtype)

        for elm in elms:

            if elm.tpe != DeviceType.NoDevice:
                # search in the per-device type dictionary (already created and faster)
                referenced_dict = elements_dict_by_type[elm.tpe]
                referenced_elm = referenced_dict.get(elm.device_idtag, None)
            else:
                # lazy-creation of the all elements dict, takes time to initialize
                if len(all_elements_dict) == 0:
                    all_elements_dict, _ = circuit.get_all_elements_dict()
                referenced_elm = all_elements_dict.get(elm.device_idtag, None)

            if referenced_elm is None:
                to_delete.append(elm)
            else:
                elm.set_device(elm=referenced_elm)

    # Delete pointer elements that refer to missing objects.
    for elm in to_delete:
        circuit.delete_element(elm)
        logger.add_error(msg="Invalid pointer element deleted",
                         device_class=elm.device_type.value,
                         device=elm.name)

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
                tower.add_wire_relationship(wire=wire, xpos=xpos, ypos=ypos, phase=phase)
    else:
        pass

    # create diagrams --------------------------------------------------------------------------------------------------
    if text_func is not None:
        text_func("Parsing diagrams...")

    # try to get the list of diagrams
    list_of_diagrams: List[Dict[str, Any]] = data.get('diagrams', None)

    if list_of_diagrams is not None:

        if len(list_of_diagrams):
            obj_dict = circuit.get_all_elements_dict_by_type(add_locations=True)
            diagrams_by_id: Dict[str, dev.BaseDiagram] = dict()

            for diagram_dict in list_of_diagrams:

                if diagram_dict['type'] in [DiagramType.Schematic.value, "bus-branch"]:
                    diagram = dev.SchematicDiagram()
                    diagram.parse_data(data=diagram_dict, obj_dict=obj_dict, logger=logger)
                    circuit.add_diagram(diagram)
                    diagrams_by_id[diagram.idtag] = diagram

                elif diagram_dict['type'] == DiagramType.SubstationLineMap.value:
                    diagram = dev.MapDiagram()
                    diagram.parse_data(data=diagram_dict, obj_dict=obj_dict, logger=logger)
                    circuit.add_diagram(diagram)
                    diagrams_by_id[diagram.idtag] = diagram
                else:
                    print('unrecognized diagram', diagram_dict['type'])

            diagram_tree_data = data.get('diagram_tree', None)
            if diagram_tree_data is not None and hasattr(circuit.diagrams, 'parse_data'):
                circuit.diagrams.parse_data(diagram_tree_data, diagrams_by_id)

    if text_func is not None:
        text_func("Done!")

    # search contingencies, investments and remedial actions pointed devices
    # and remove those that point nowhere
    if refine_pointers:
        circuit.refine_pointer_objects(logger=logger)

    if circuit.has_time_series:
        circuit.ensure_profiles_exist()

    resolved_project_directory: Path | None
    if project_directory is None:
        resolved_project_directory = None
    else:
        resolved_project_directory = Path(project_directory)
    _resolve_circuit_fmu_paths(circuit, resolved_project_directory)

    # Enable auto updates internally only after everything has been filled
    for elm in circuit.get_all_elements_iter():
        elm.enable_auto_updates()

    return circuit


def parse_multiverse_data(data: Dict[str, VERAGRID_FILE_TYPE],
                          metadata: Dict[str, Dict[str, int | float] | int | None],
                          text_func: Union[Callable, None] = None,
                          progress_func: Union[Callable, None] = None,
                          logger: Logger = Logger()) -> dev.MultiVerse:
    """

    :param data:
    :param metadata:
    :param text_func:
    :param progress_func:
    :param logger:
    :return:
    """
    mv = dev.MultiVerse(current_model=None)

    diffs_dict: Dict[str, MultiCircuit] = dict()
    diagrams_dict: Dict[str, List[Dict[str, Any]]] = dict()
    diagram_tree_dict: Dict[str, Optional[Dict[str, Any]]] = dict()
    composed_by_node_id: Dict[int, MultiCircuit] = dict()

    # IMPORTANT:
    # Multiverse node payloads are not all full circuits.
    #
    # - Root nodes store a full authoritative MultiCircuit.
    # - Non-root nodes store only the electrical delta against their parent.
    #
    # This has two non-obvious effects on loading:
    #
    # 1. Electrical references in child payloads may legitimately point to objects that are
    #    not present in the child's delta payload, because those objects live in the parent /
    #    ancestor composed circuit. Example: a child adds a new line whose bus_to points to a
    #    bus inherited from the parent scenario. If the child payload were parsed in isolation,
    #    that reference would fail with "Could not locate reference".
    #
    # 2. Node-owned diagrams are full scenario diagrams, not diagram deltas. A child diagram may
    #    therefore reference both child-owned and inherited parent-owned API objects. Parsing such
    #    diagrams against the raw child delta payload would also fail.
    #
    # Because of that, multiverse loading must happen in two phases:
    # - First parse the electrical payloads in parent-before-child order, passing the fully composed
    #   parent circuit as previous_circuit so child references to inherited objects can be resolved.
    # - Then, after the tree exists, parse each node's diagrams against that node's full composed
    #   scenario, never against the raw delta payload.
    node_metadata = get_multiverse_node_metadata(metadata)
    ordered_records = order_multiverse_records(metadata)
    all_elements_dict: Dict[str, ALL_DEV_TYPES] = dict()

    for record in ordered_records:
        node_id = int(record["node_id"])
        circuit_idtag = str(record["circuit_idtag"])
        parent_id_raw = record["parent_id"]
        parent_id = None if parent_id_raw is None else int(parent_id_raw)

        multiverse_data = data.get("multiverse", None)
        if multiverse_data is not None:
            model_data = multiverse_data.get(circuit_idtag, None)

            if model_data is not None:
                diagrams_dict[circuit_idtag] = model_data.get("diagrams", list())
                diagram_tree_dict[circuit_idtag] = model_data.get("diagram_tree", None)

                model_without_diagrams = dict(model_data)
                model_without_diagrams["diagrams"] = list()
                model_without_diagrams.pop("diagram_tree", None)

                previous_circuit = None if parent_id is None else composed_by_node_id[parent_id]

                grid = parse_veragrid_data(data=model_without_diagrams,
                                           previous_circuit=previous_circuit,
                                           refine_pointers=False,
                                           text_func=text_func,
                                           progress_func=progress_func,
                                           logger=logger)

                # we create a dictionary of all the elements in all the scenarios such that finding pointers doesn't fail later
                d, ok = grid.get_all_elements_dict(logger=logger)
                all_elements_dict.update(d)

                grid.idtag = circuit_idtag
                diffs_dict[circuit_idtag] = grid

                if parent_id is None:
                    composed_by_node_id[node_id] = grid.copy()
                else:
                    composed = composed_by_node_id[parent_id].copy()
                    composed.merge_circuit(grid)
                    composed.name = grid.name
                    composed_by_node_id[node_id] = composed
            else:
                # model_data is None
                pass
        else:
            # multiverse is None
            pass

    # Refine pointer in all grids
    for idtag, grid in diffs_dict.items():
        grid.refine_pointer_objects(logger=logger, all_elements_dict=all_elements_dict)

    # Parse the multiverse data
    try:
        mv.parse_json(diffs_dict=diffs_dict, metadata=metadata)
    except ValueError as e:
        logger.add_error(str(e))

    # Parse diagrams only after the multiverse tree exists, so each node can resolve them
    # against its full composed scenario instead of its raw delta payload.
    for record in node_metadata.values():
        node_id = int(record["node_id"])
        circuit_idtag = str(record["circuit_idtag"])
        if mv.check_node(node_id):
            node = mv.get_node(node_id)
            full_circuit = mv.checkout(node)
            obj_dict = full_circuit.get_all_elements_dict_by_type(add_locations=True)
            parsed_diagrams: dev.DiagramTree = dev.DiagramTree()
            diagrams_by_id: Dict[str, dev.BaseDiagram] = dict()

            for diagram_dict in diagrams_dict.get(circuit_idtag, list()):
                if diagram_dict['type'] in [DiagramType.Schematic.value, "bus-branch"]:
                    diagram = dev.SchematicDiagram()
                    diagram.parse_data(data=diagram_dict, obj_dict=obj_dict, logger=logger)
                    parsed_diagrams.append(diagram)
                    diagrams_by_id[diagram.idtag] = diagram

                elif diagram_dict['type'] == DiagramType.SubstationLineMap.value:
                    diagram = dev.MapDiagram()
                    diagram.parse_data(data=diagram_dict, obj_dict=obj_dict, logger=logger)
                    parsed_diagrams.append(diagram)
                    diagrams_by_id[diagram.idtag] = diagram

            node_tree_data = diagram_tree_dict.get(circuit_idtag, None)
            if node_tree_data is not None and hasattr(parsed_diagrams, 'parse_data'):
                parsed_diagrams.parse_data(node_tree_data, diagrams_by_id)

            node.diagrams = parsed_diagrams
            if node.circuit is not None:
                node.circuit.diagrams = parsed_diagrams
        else:
            logger.add_error("Node ID not found", value=str(node_id))

    if isinstance(metadata, dict):
        active_node_id_raw: int = metadata.get("active_node_id", -1)
        if mv.current_node is not None and mv.current_model is not None:
            obj_dict = mv.current_model.get_all_elements_dict_by_type(add_locations=True)
            mv.current_model.diagrams = copy_diagrams(diagrams=mv.current_node.diagrams, obj_dict=obj_dict)

        if (active_node_id_raw > -1
                and (mv.current_node is None or mv.current_node.node_id != int(active_node_id_raw))):
            if mv.check_node(active_node_id_raw):
                mv.activate_scenario(int(active_node_id_raw))

    return mv
