# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import random
import uuid
import numpy as np
from GridCalEngine.Devices.profile import Profile
from typing import List, Dict, AnyStr, Any, Union, Type, Tuple
from GridCalEngine.basic_structures import Logger
from GridCalEngine.enumerations import (DeviceType, TimeFrame, BuildStatus, WindingsConnection,
                                        TapModuleControl, TapPhaseControl, SubObjectType, ConverterControlType,
                                        HvdcControlType, ActionType, AvailableTransferMode, ContingencyMethod,
                                        CpfParametrization, CpfStopAt, InvestmentEvaluationMethod, SolverType,
                                        InvestmentsEvaluationObjectives, NodalCapacityMethod, TimeGrouping,
                                        ZonalGrouping, MIPSolvers, AcOpfMode, SubstationTypes, BranchGroupTypes,
                                        BranchImpedanceMode, FaultType, TapChangerTypes, ContingencyOperationTypes,
                                        WindingType, MethodShortCircuit, PhasesShortCircuit, ShuntConnectionType,
                                        BusGraphicType, SwitchGraphicType)

# types that can be assigned to a GridCal property
GCPROP_TYPES = Union[
    Type[int],
    Type[bool],
    Type[float],
    Type[str],
    DeviceType,
    SubObjectType,
    Type[HvdcControlType],
    Type[BuildStatus],
    Type[WindingsConnection],
    Type[TapModuleControl],
    Type[TapPhaseControl],
    Type[ActionType],
    Type[AvailableTransferMode],
    Type[ContingencyMethod],
    Type[CpfParametrization],
    Type[CpfStopAt],
    Type[InvestmentEvaluationMethod],
    Type[InvestmentsEvaluationObjectives],
    Type[NodalCapacityMethod],
    Type[SolverType],
    Type[TimeGrouping],
    Type[ZonalGrouping],
    Type[MIPSolvers],
    Type[AcOpfMode],
    Type[BranchImpedanceMode],
    Type[FaultType],
    Type[TapChangerTypes],
    Type[SubstationTypes],
    Type[ContingencyOperationTypes],
    Type[BranchGroupTypes],
    Type[ConverterControlType],
    Type[WindingType],
    Type[MethodShortCircuit],
    Type[PhasesShortCircuit],
    Type[DeviceType],
    Type[ShuntConnectionType],
    Type[BusGraphicType],
    Type[SwitchGraphicType]
]


def uuid2idtag(val: str):
    """
    Remove the useless characters and format as a proper 32-char UID
    :param val: value that looks like a UUID
    :return: proper UUID
    """
    return val.replace('_', '').replace('-', '')


def parse_idtag(val: Union[str, None]) -> str:
    """
    idtag setter
    :param val: any string or None
    """
    if val is None:
        return uuid.uuid4().hex  # generate a proper UUIDv4 string
    elif isinstance(val, str):
        if len(val) == 32:
            return val  # this is probably a proper UUID
        elif len(val) == 0:
            return uuid.uuid4().hex  # generate a proper UUIDv4 string
        else:
            candidate_val = uuid2idtag(val)
            if len(candidate_val) == 32:
                return candidate_val  # if the string passed can be a UUID, set it
            else:
                return val  # otherwise this is just a plain string, that we hope is valid...
    else:
        return str(val)


def smart_compare(a, b, atol=1.e-10):
    """
    Compares two Python objects with tolerance for numerical values.

    If both inputs are numeric (int, float, complex, or NumPy numbers),
    the function uses `np.isclose()` to compare them. For all other types, it falls back to
    standard equality comparison (`==`).

    a :First object to compare.
    b :Second object to compare.
    :return: bool
    """
    if isinstance(a, float) and isinstance(b, float):
        return np.isclose(a, b, atol=atol)
    return a == b


class GCProp:
    """
    GridCal property
    """

    def __init__(self,
                 prop_name: str,
                 units: str,
                 tpe: GCPROP_TYPES,
                 definition: str,
                 profile_name: str = '',
                 display: bool = True,
                 editable: bool = True,
                 old_names: List[str] = None,
                 is_color: bool = False,
                 is_date: bool = False):
        """
        GridCal property
        :param prop_name:
        :param units: units of the property
        :param tpe: data type [Type[int], Type[bool], Type[float], Type[str], DeviceType, Type[BuildStatus]]
        :param definition: Definition of the property
        :param profile_name: name of the associated profile property
        :param display: Display the property in the GUI
        :param editable: Is this editable?
        :param is_color: Is this a color? i.e. the tpe is str, but it represents a color
        :param is_date: Is this a date? i.e. the tpe is int but represents a date
        """

        self.name = prop_name

        self.units = units

        self.tpe = tpe

        self.definition = definition

        self.profile_name = profile_name

        self.display = display

        self.editable = editable

        self.is_color = is_color

        self.is_date = is_date

        self.old_names = old_names if old_names is not None else list()

        self.selected_to_merge = True  # only applicable if we want to apply the value of this property on merge

    def has_profile(self) -> bool:
        """
        Check if this property has an associated profile
        :return:
        """
        return self.profile_name != ''

    def get_class_name(self) -> str:
        """
        Convert the class name to a string
        :return: str
        """
        tpe_name = str(self.tpe)
        if '.' in tpe_name:
            chunks = tpe_name.split('.')
            return chunks[-1].replace("'", "") \
                .replace("<", "") \
                .replace(">", "").strip()
        else:
            return tpe_name.replace('class', '') \
                .replace("'", "") \
                .replace("<", "") \
                .replace(">", "").strip()

    def get_dict(self) -> Dict[str, str]:
        """
        Get the values of this property as a dictionary
        :return: Dict[name, value]
        """
        return {'name': self.name,
                'class_type': self.get_class_name(),
                'unit': self.units,
                'mandatory': False,
                'max_chars': '',
                "descriptions": self.definition,
                "has_profile": self.has_profile(),
                'comment': ''}

    def __str__(self):
        return self.name

    def __repr__(self):
        return "prop:" + self.name


def get_action_symbol(action: ActionType):
    """

    :param action:
    :return:
    """
    if action == ActionType.NoAction:
        return "."
    elif action == ActionType.Add:
        return "+"
    elif action == ActionType.Delete:
        return "-"
    elif action == ActionType.Modify:
        return "~"
    else:
        return ""


class EditableDevice:
    """
    This is the main device class from which all inherit
    """
    __slots__ = (
        '_idtag',
        '_name',
        '_code',
        '_rdfid',
        'device_type',
        'comment',
        'action',
        'selected_to_merge',
        'property_list',
        'registered_properties',
        'non_editable_properties',
        'properties_with_profile',
        '__auto_update_enabled',
    )

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 device_type: DeviceType,
                 comment: str = "",
                 rdfid: str = ""):
        """
        Class to generalize any editable device
        :param name: Asset's name
        :param idtag: unique ID, if not provided it is generated
        :param code: alternative code to identify this object in other databases (i.e. psse number tec...)
        :param device_type: DeviceType instance
        :param rdfid: RDFID code optional
        """

        self._idtag = parse_idtag(val=idtag)

        self._name: str = name

        self._code: str = code

        self._rdfid = rdfid

        self.device_type: DeviceType = device_type

        self.comment: str = comment

        self.action: ActionType = ActionType.NoAction
        self.selected_to_merge = True

        # list of registered properties. This is supremely useful when accessing via the Table and Tree models
        self.property_list: List[GCProp] = list()

        # dictionary of properties
        self.registered_properties: Dict[str, GCProp] = dict()

        # list of properties that cannot be edited
        self.non_editable_properties: List[str] = list()

        # dictionary with property name -> profile name
        self.properties_with_profile: Dict[str, str] = dict()

        # some devices have an auto update of a property when another property changes
        # (i.e. Line's R, X, B when the length changes) this controls that behaviour and disables it during loading
        self.__auto_update_enabled = False

        self.register(key='idtag', units='', tpe=str, definition='Unique ID', editable=False)
        self.register(key='name', units='', tpe=str, definition='Name of the device.')
        self.register(key='code', units='', tpe=str, definition='Secondary ID')
        self.register(key='rdfid', units='', tpe=str, definition='RDF ID for further compatibility')
        self.register(key='action', units='', tpe=ActionType,
                      definition='Object action to perform.\nOnly used for model merging.',
                      display=False)
        self.register(key='comment', units='', tpe=str, definition='User comment')

    @property
    def auto_update_enabled(self):
        """

        :return:
        """
        return self.__auto_update_enabled

    def enable_auto_updates(self):
        """

        :return:
        """
        self.__auto_update_enabled = True

    def disable_auto_updates(self):
        """

        :return:
        """
        self.__auto_update_enabled = False

    def get_uuid(self) -> str:
        """
        If the idtag property looks like a UUID, it adds the dashes
        :return: UUID with dashes
        """
        if isinstance(self._idtag, str):
            if len(self.idtag) == 32:
                return str(uuid.UUID(self.idtag))
            else:
                raise Exception("The idtag is not a proper UUID")
        else:
            raise Exception("The idtag is not a proper UUID string")

    def __str__(self) -> str:
        """
        Name of the object
        :return: string
        """
        return str(self.name)

    def __repr__(self) -> str:
        return get_action_symbol(self.action) + "::" + self.idtag + '::' + self.name

    def __hash__(self) -> int:
        # alternatively, return hash(repr(self))
        return int(self.idtag, 16)  # hex string to int

    def __lt__(self, other) -> bool:
        return self.__hash__() < other.__hash__()

    def __eq__(self, other) -> bool:
        if hasattr(other, 'idtag'):
            return self.idtag == other.idtag
        else:
            return False

    @property
    def idtag(self) -> str:
        """
        idtag getter
        :return: string, hopefully an UUIDv4
        """
        return self._idtag

    @idtag.setter
    def idtag(self, val: Union[str, None]):
        """
        idtag setter
        :param val: any string or None
        """
        self._idtag = parse_idtag(val)

    @property
    def code(self) -> str:
        """
        code getter
        :return: string, hopefully an UUIDv4
        """
        return self._code

    @code.setter
    def code(self, val: Union[str, None]):
        """
        code setter
        :param val: any string or None
        """
        self._code = val

    @property
    def rdfid(self) -> str:
        return self._rdfid

    @rdfid.setter
    def rdfid(self, val: str):
        self._rdfid = val

    def flatten_idtag(self):
        """
        Remove useless underscore (_) and dash (-)
        :return:
        """
        self._idtag = self._idtag.replace('_', '').replace('-', '')

    @property
    def type_name(self) -> str:
        """
        Name of the device type
        :return: name of the type (str)
        """
        return self.device_type.value

    def get_rdfid(self) -> str:
        """
        Convert the idtag to RDFID
        :return: UUID converted to RDFID
        """
        if len(self._rdfid) == 0:
            lenghts = [8, 4, 4, 4, 12]
            chunks = list()
            s = 0
            for length_ in lenghts:
                a = self.idtag[s:s + length_]
                chunks.append(a)
                s += length_
            return "-".join(chunks)
        else:
            return self.rdfid

    def register(self,
                 key: str,
                 tpe: GCPROP_TYPES,
                 units: str = "",
                 definition: str = "",
                 profile_name: str = '',
                 display: bool = True,
                 editable: bool = True,
                 old_names: List[str] = None,
                 is_color: bool = False,
                 is_date: bool = False):
        """
        Register property
        The property must exist, and if provided, the profile_name property must exist too
        :param key: key (this is the displayed name)
        :param units: string with the declared units
        :param tpe: type of the attribute [Type[int], Type[bool], Type[float], Type[str], DeviceType, Type[BuildStatus]]
        :param definition: Definition of the property
        :param profile_name: name of the profile property (if any)
        :param display: display this property?
        :param editable: is this editable?
        :param old_names: List of old names
        :param is_color: is this a color property?
        :param is_date: Is this a date property?
        """
        assert (hasattr(self, key))  # the property must exist, this avoids bugs when registering

        # create GCProp object
        prop = GCProp(prop_name=key,
                      units=units,
                      tpe=tpe,
                      definition=definition,
                      profile_name=profile_name,
                      display=display,
                      editable=editable,
                      old_names=old_names,
                      is_color=is_color,
                      is_date=is_date)

        if key in self.registered_properties.keys():
            raise Exception(f"Property {key} already registered!")

        self.registered_properties[key] = prop

        self.property_list.append(prop)

        if profile_name != '':
            assert (hasattr(self, profile_name))  # the profile property must exist, this avoids bugs in registering
            assert (isinstance(getattr(self, profile_name), Profile))  # the profile must be of type "Profile"
            self.properties_with_profile[key] = profile_name

        if not editable:
            self.non_editable_properties.append(key)

    def get_property_name_replacements_dict(self) -> Dict[str, str]:
        """
        Get dictionary of old names related to their current name
        This is useful for retro compatibility
        :return: {old_name: new_name} dict
        """
        data = dict()
        for key, prop in self.registered_properties.items():

            for old_name in prop.old_names:
                data[old_name] = prop.name

        return data

    def generate_uuid(self):
        """
        Generate new UUID for the idtag property
        """
        self.idtag = uuid.uuid4().hex

    @property
    def name(self) -> str:
        """
        Name of the object
        """
        return self._name

    @name.setter
    def name(self, val: str):
        self._name = val

    def get_save_data(self) -> List[Union[str, float, int, bool, object]]:
        """
        Return the data that matches the edit_headers
        :return: list with data
        """

        data = list()
        for name, properties in self.registered_properties.items():
            obj = getattr(self, name)

            if obj is not None:
                if properties.tpe in [str, float, int, bool]:
                    data.append(obj)

                else:
                    # if the object is not of a primary type, get the idtag instead
                    if hasattr(obj, 'idtag'):
                        data.append(obj.idtag)
                    else:
                        # some data types might not have the idtag, ten just use the str method
                        data.append(str(obj))
            else:
                data.append(None)

        return data

    def get_headers(self) -> List[AnyStr]:
        """
        Return a list of headers
        """
        return list(self.registered_properties.keys())

    def get_number_of_properties(self) -> int:
        """
        Return the number of registered properties
        :return: int
        """
        return len(self.property_list)

    def get_properties_containing_object(self, obj: "EditableDevice") -> Tuple[List[GCProp], List[int]]:
        """
        Return the list of properties that contain a certain object
        :param obj:
        :return: list of GCProp, list of indices
        """
        props = list()
        indices = list()
        for i, prop in enumerate(self.property_list):
            if getattr(self, prop.name) == obj:
                props.append(prop)
                indices.append(i)

        return props, indices

    def get_association_properties(self) -> Tuple[List[GCProp], List[int]]:
        """
        Return the list of properties that contain associate another type
        :return: list of GCProp, list of indices
        """
        props = list()
        indices = list()
        for i, prop in enumerate(self.property_list):
            if prop.tpe == SubObjectType.Associations:
                props.append(prop)
                indices.append(i)

        return props, indices

    def get_snapshot_value(self, prop: GCProp) -> Any:
        """
        Return the stored object value from the property index
        :param prop: GCProp
        :return: Whatever value is there
        """
        return getattr(self, prop.name)

    def get_snapshot_value_by_name(self, name) -> Any:
        """
        Return the stored object value from the property index
        :param name: snapshot property name
        :return: Whatever value is there
        """
        return getattr(self, name)

    def get_property_value(self, prop: GCProp, t_idx: Union[None, int]) -> Any:
        """
        Return the stored object value from the property index
        :param prop: GCProp
        :param t_idx: Time index, None for Snapshot values
        :return: Whatever value is there
        """

        if t_idx is None:
            # pick the snapshot value whatever it is
            return self.get_snapshot_value(prop=prop)
        else:
            if prop.has_profile():
                # the property has a profile, return the value at t_idx
                return self.get_profile_by_prop(prop=prop)[t_idx]
            else:
                # the property has no profile, just return it
                return self.get_snapshot_value(prop=prop)

    def get_property_by_idx(self, property_idx: int) -> GCProp:
        """
        Return the stored object value from the property index
        :param property_idx: Property index
        :return: GCProp
        """
        return self.property_list[property_idx]

    def get_property_by_name(self, prop_name: str) -> GCProp:
        """

        :param prop_name:
        :return:
        """
        return self.registered_properties[prop_name]

    def get_property_value_by_idx(self, property_idx: int, t_idx: Union[None, int]) -> Any:
        """
        Return the stored object value from the property index
        :param property_idx: Property index
        :param t_idx: Time index, None for Snapshot values
        :return: Whatever value is there
        """
        prop = self.property_list[property_idx]
        return self.get_property_value(prop=prop, t_idx=t_idx)

    def set_profile(self, prop: GCProp, arr: Union[Profile, np.ndarray]) -> None:
        """
        Set the profile from eithr an array or an actual profile object
        :param prop: GCProp instance
        :param arr: Profile object or numpy array object
        """
        if isinstance(arr, np.ndarray):
            profile: Profile = getattr(self, prop.profile_name)
            profile.set(arr)
        elif isinstance(arr, Profile):
            setattr(self, prop.profile_name, arr)
        else:
            raise Exception("profile type not supported")

    def set_profile_array(self, magnitude, arr: Union[Profile, np.ndarray]) -> None:
        """
        Set the profile from eithr an array or an actual profile object
        :param magnitude: snapshot magnitude
        :param arr: Profile object or numpy array object
        """
        if isinstance(arr, np.ndarray):
            prof_name = self.properties_with_profile[magnitude]
            profile: Profile = getattr(self, prof_name)
            profile.set(arr)
        else:
            raise Exception("profile type not supported")

    def set_property_value(self, prop: GCProp, value: Any, t_idx: Union[None, int]):
        """
        Return the stored object value from the property index
        :param prop: GCProp
        :param value: any value is there
        :param t_idx: Time index, None for Snapshot values
        :return: Whatever value is there
        """

        if t_idx is None:
            # set the snapshot value whatever it is
            setattr(self, prop.name, value)
        else:
            if prop.has_profile():
                # the property has a profile, get it and set the t_idx value
                getattr(self, prop.profile_name)[t_idx] = value
            else:
                # the property has no profile, just return it
                setattr(self, prop.name, value)

    def get_value(self, prop: GCProp, t_idx: Union[None, int]) -> Any:
        """
        Return value regardless of the property index
        :param prop: GCProp
        :param t_idx: time index
        :return: Some value
        """
        if t_idx is None:
            # return the normal property
            return getattr(self, prop.name)
        else:
            if prop.has_profile():
                # get the profile value
                return getattr(self, prop.profile_name)[t_idx]
            else:
                # return the normal property
                return getattr(self, prop.name)

    def set_value(self, prop: GCProp, t_idx: Union[None, int], value: Any) -> None:
        """
        Return value regardless of the property index
        :param prop: GCProp
        :param t_idx: time index
        :param value: Some value
        """
        if t_idx is None:
            # return the normal property
            setattr(self, prop.name, value)
        else:
            if prop.has_profile():
                # get the profile value
                prof: Profile = getattr(self, prop.profile_name)
                prof[t_idx] = value  # assign the value
            else:
                # return the normal property
                setattr(self, prop.name, value)

    def set_snapshot_value(self, property_name, value: Any) -> None:
        """
        Set the value of a snapshot property
        :param property_name: name of the property
        :param value: Any
        """
        # set the snapshot value whatever it is
        setattr(self, property_name, value)

    def create_profiles(self, index):
        """
        Create the load object default profiles
        Args:
        :param index: pandas time index
        """
        for magnitude, values in self.properties_with_profile.items():
            self.create_profile(magnitude=magnitude, index=index)

    def resize_profiles(self, index, time_frame: TimeFrame):
        """
        Resize the profiles in this object
        :param index: pandas time index
        :param time_frame: Time frame to use (Short term, Long term)
        """
        n1 = index.shape[0]
        for magnitude, values in self.properties_with_profile.items():
            if values[1] == time_frame:
                # get the current profile
                val = getattr(self, self.properties_with_profile[magnitude]).values[:, 0]
                n2 = val.shape[0]

                if n1 > n2:
                    # extend the values
                    extension = np.ones(n1 - n2, dtype=val.dtype) * getattr(self, magnitude)  # copy the current value
                    val2 = np.r_[val, extension]
                else:
                    # curtail the values
                    val2 = val[:n1]

                # set the profile variable associated with the magnitude
                setattr(self, self.properties_with_profile[magnitude], val2)

    def create_profile(self, magnitude, index):
        """
        Create power profile based on index
        :param magnitude: name of the property
        :param index: pandas time index
        """
        # get the value of the magnitude
        snapshot_value = getattr(self, magnitude)

        prof = self.get_profile(magnitude=magnitude)

        prof.create_sparse(size=len(index), default_value=snapshot_value)

        # set the profile variable associated with the magnitude
        setattr(self, self.properties_with_profile[magnitude], prof)

    def ensure_profiles_exist(self, index):
        """
        It might be that when loading the GridCal Model has properties that the file has not.
        Those properties must be initialized as well
        :param index: Time series index (timestamps)
        """
        if index is not None:
            for magnitude, prof_attr in self.properties_with_profile.items():

                # get the profile
                profile = getattr(self, prof_attr)

                if profile.is_initialized:
                    if profile.size() != len(index):
                        # the length of the profile is different from the length of the master profile
                        # print(self.name, ': created profile for ' + prof_attr)
                        profile.resize(n=len(index))
                    else:
                        # all ok
                        pass
                else:
                    # there is no profile, create a new one with the default values
                    # print(self.name, ': created profile for ' + prof_attr)
                    self.create_profile(magnitude=magnitude, index=index)

        else:
            raise Exception("ensure_profiles_exist: No index provided")

    def delete_profiles(self):
        """
        Delete the object profiles (set all to None)
        """
        for magnitude in self.properties_with_profile.keys():
            self.get_profile(magnitude=magnitude).clear()

    def set_profile_values(self, t):
        """
        Set the profile values at t
        :param t: time index (integer)
        """
        for property_name, profile_name in self.properties_with_profile.items():
            profile: Profile = getattr(self, profile_name)
            setattr(self, property_name, profile[t])

    def get_profile(self, magnitude: str) -> Union[Profile, None]:
        """
        Get the profile of a property name
        :param magnitude: name of the property
        :return: Profile object
        """

        # try to get the profile name
        profile_name = self.properties_with_profile.get(magnitude, None)

        if profile_name is None:
            return None
        else:
            return getattr(self, profile_name)

    def get_profile_by_prop(self, prop: GCProp) -> Union[Profile, None]:
        """
        Get the profile of a property name
        :param prop: GCProp
        :return: Profile object
        """
        return getattr(self, prop.profile_name)

    def copy(self, forced_new_idtag: bool = False):
        """
        Create a deep copy of this object
        """
        tpe = self.__class__

        try:
            new_obj = tpe(name=self.name,
                          idtag=uuid.uuid4().hex if forced_new_idtag else self.idtag,
                          code=self.code,
                          device_type=self.device_type)
        except TypeError:
            new_obj = tpe()

        for prop_name, gc_prop in self.registered_properties.items():
            value = getattr(self, prop_name)
            setattr(new_obj, prop_name, value)

            if gc_prop.has_profile():
                my_prof = getattr(self, gc_prop.profile_name)
                setattr(new_obj, gc_prop.profile_name, my_prof.copy())

        if forced_new_idtag:
            new_obj.idtag = uuid.uuid4().hex

        return new_obj

    @staticmethod
    def rgb2hex(r: int, g: int, b: int) -> str:
        """
        Convert R, G, B to hexadecimal tuple
        :param r: Red amount (0, 255)
        :param g: Green amount (0, 255)
        :param b: Blue amount (0, 255)
        :return: Hexadecimal string
        """
        return "#{:02x}{:02x}{:02x}".format(r, g, b)

    @staticmethod
    def hex2rgb(hexcode: int) -> Tuple[int, ...]:
        """
        Convert hexadecimal string to rgb tuple
        :param hexcode: hexadecimal string
        :return: (R, G, B)
        """
        return tuple(map(ord, hexcode[1:].decode('hex')))

    def rnd_color(self) -> str:
        """
        Generate random colour
        :return: hex string
        """
        r = random.randint(0, 128)
        g = random.randint(0, 128)
        b = random.randint(0, 128)
        return self.rgb2hex(r, g, b)

    def new_idtag(self):
        """
        Generate a new IdTag
        """
        self._idtag = uuid.uuid4().hex  # generate a proper UUIDv4 string

    def replace_objects(self, old_object: Any, new_obj: Any, logger: Logger) -> None:
        """
        Replace object in this objects' properties
        :param old_object: object to replace
        :param new_obj: object used to replace the old one
        :param logger: Logger to record what happened
        """
        for key, prop in self.registered_properties.items():

            obj = getattr(self, prop.name)

            if obj == old_object:
                setattr(self, prop.name, new_obj)
                logger.add_info(msg="Replaced object",
                                device=self.idtag + ":" + self.name,
                                device_property=prop.name,
                                value=str(new_obj))

    def compare(self, other: Any,
                logger: Logger,
                detailed_profile_comparison=False,
                nt=0) -> Tuple[ActionType, List[GCProp]]:
        """
        Compare two objects
        :param other: other device
        :param logger: Logger
        :param detailed_profile_comparison: Compare profiles?
        :param nt: number of time steps (get it from the circuit)
        :return: ActionType
        """
        action = ActionType.NoAction
        properties_changed: List[GCProp] = list()

        # check differences
        for prop_name, prop in self.registered_properties.items():

            # compare the snapshot values
            v1 = self.get_property_value(prop=prop, t_idx=None)
            v2 = other.get_property_value(prop=prop, t_idx=None)

            if not smart_compare(v1, v2):
                logger.add_info(msg="Different snapshot values",
                                device_class=self.device_type.value,
                                device_property=prop.name,
                                value=v2,
                                expected_value=v1)
                action = ActionType.Modify
                properties_changed.append(prop)

            if prop.has_profile():
                p1 = self.get_profile_by_prop(prop=prop)
                p2 = self.get_profile_by_prop(prop=prop)

                if p1 != p2:
                    logger.add_info(msg="Different profile values",
                                    device_class=self.device_type.value,
                                    device_property=prop.name,
                                    object_value=p2,
                                    expected_object_value=p1)
                    action = ActionType.Modify
                    properties_changed.append(prop)

                if detailed_profile_comparison:
                    for t_idx in range(nt):

                        v1 = p1[t_idx]
                        v2 = p2[t_idx]

                        if not smart_compare(v1, v2):
                            logger.add_info(msg="Different time series values",
                                            device_class=self.device_type.value,
                                            device_property=prop.name,
                                            device=str(self),
                                            value=v2,
                                            expected_value=v1)
                            action = ActionType.Modify

                        v1b = self.get_property_value(prop=prop, t_idx=t_idx)
                        v2b = other.get_property_value(prop=prop, t_idx=t_idx)

                        if not smart_compare(v1, v1b):
                            logger.add_info(
                                msg="Profile values differ with different getter methods!",
                                device_class=self.device_type.value,
                                device_property=prop.name,
                                device=str(self),
                                value=v1b,
                                expected_value=v1)
                            action = ActionType.Modify

                        if not smart_compare(v2, v2b):
                            logger.add_info(
                                msg="Profile getting values differ with different getter methods!",
                                device_class=self.device_type.value,
                                device_property=prop.name,
                                device=str(self),
                                value=v1b,
                                expected_value=v1)
                            action = ActionType.Modify

        return action, properties_changed
