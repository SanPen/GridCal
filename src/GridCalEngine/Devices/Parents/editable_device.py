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
import random
import uuid
import numpy as np
from GridCalEngine.enumerations import (DeviceType, TimeFrame, BuildStatus, WindingsConnection, TransformerControlType,
                                        ConverterControlType, TapModuleControl, TapAngleControl, SubObjectType,
                                        HvdcControlType)
from GridCalEngine.Devices.profile import Profile
from typing import List, Dict, AnyStr, Any, Optional, Union, Type, Tuple

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
    Type[TransformerControlType],
    Type[ConverterControlType],
    Type[TapModuleControl],
    Type[TapAngleControl],
]


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
            candidate_val = val.replace('_', '').replace('-', '')
            if len(candidate_val) == 32:
                return candidate_val  # if the string passed can be a UUID, set it
            else:
                return val  # otherwise this is just a plain string, that we hope is valid...
    else:
        return str(val)


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
                 old_names: List[str] = None):
        """
        GridCal property
        :param prop_name:
        :param units: units of the property
        :param tpe: data type [Type[int], Type[bool], Type[float], Type[str], DeviceType, Type[BuildStatus]]
        :param definition: Definition of the property
        :param profile_name: name of the associated profile property
        :param display: Display the property in the GUI
        :param editable: Is this editable?
        """

        self.name = prop_name

        self.units = units

        self.tpe = tpe

        self.definition = definition

        self.profile_name = profile_name

        self.display = display

        self.editable = editable

        self.old_names = old_names if old_names is not None else list()

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
                'comment': ''}

    def __str__(self):
        return self.name

    def __repr__(self):
        return "prop:" + self.name


class EditableDevice:
    """
    This is the main device class from which all inherit
    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 device_type: DeviceType):
        """
        Class to generalize any editable device
        :param name: Asset's name
        :param device_type: DeviceType instance
        :param idtag: unique ID, if not provided it is generated
        :param code: alternative code to identify this object in other databases (i.e. psse number tec...)
        """

        self._idtag = parse_idtag(val=idtag)

        self._name: str = name

        self.code: str = code

        self.device_type: DeviceType = device_type

        # list of registered properties. This is supremelly useful when accessing via the Table and Tree models
        self.property_list: List[GCProp] = list()

        self.registered_properties: Dict[str, GCProp] = dict()

        self.non_editable_properties: List[str] = list()

        self.properties_with_profile: Dict[str, Optional[Any]] = dict()

        self.register(key='idtag', units='', tpe=str, definition='Unique ID', editable=False)
        self.register(key='name', units='', tpe=str, definition='Name of the branch.')
        self.register(key='code', units='', tpe=str, definition='Secondary ID')

    def __str__(self) -> str:
        """
        Name of the object
        :return: string
        """
        return self.name

    def __repr__(self) -> str:
        return self.idtag + '::' + self.name

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

    def flatten_idtag(self):
        """
        Remove useless undercore and
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
        lenghts = [8, 4, 4, 4, 12]
        chunks = list()
        s = 0
        for length_ in lenghts:
            a = self.idtag[s:s + length_]
            chunks.append(a)
            s += length_
        return "-".join(chunks)

    def register(self,
                 key: str,
                 units: str,
                 tpe: GCPROP_TYPES,
                 definition: str,
                 profile_name: str = '',
                 display: bool = True,
                 editable: bool = True,
                 old_names: List[str] = None):
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
        """
        assert (hasattr(self, key))  # the property must exist, this avoids bugs when registering

        prop = GCProp(prop_name=key,
                      units=units,
                      tpe=tpe,
                      definition=definition,
                      profile_name=profile_name,
                      display=display,
                      editable=editable,
                      old_names=old_names)

        if key in self.registered_properties.keys():
            raise Exception(f"Property {key} already registered!")

        self.registered_properties[key] = prop

        self.property_list.append(prop)

        if profile_name != '':
            assert (hasattr(self, profile_name))  # the profile property must exist, this avoids bugs in registering
            assert (isinstance(getattr(self, profile_name), Profile))
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
            if properties.tpe in [str, float, int, bool]:
                data.append(obj)
            elif properties.tpe == DeviceType.GeneratorQCurve:
                data.append(obj.str())
            else:
                # if the object is not of a primary type, get the idtag instead
                if hasattr(obj, 'idtag'):
                    data.append(obj.idtag)
                else:
                    # some data types might not have the idtag, ten just use the str method
                    data.append(str(obj))
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

    def set_vaule(self, prop: GCProp, t_idx: Union[None, int], value: Any) -> None:
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
        val = Profile(default_value=snapshot_value)
        val.create_sparse(size=len(index), default_value=snapshot_value)

        # set the profile variable associated with the magnitude
        setattr(self, self.properties_with_profile[magnitude], val)

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
            self.get_profile(magnitude=magnitude).resize(0)

    def set_profile_values(self, t):
        """
        Set the profile values at t
        :param t: time index (integer)
        """
        for magnitude in self.properties_with_profile.keys():
            profile: Profile = getattr(self, self.properties_with_profile[magnitude])
            setattr(self, magnitude, profile[t])

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

    def get_properties_dict(self, version=3):
        """

        :param version:
        :return:
        """
        return dict()

    def get_units_dict(self, version=3):
        """

        :param version:
        :return:
        """
        return dict()

    def get_profiles_dict(self, version=3):
        """

        :param version:
        :return:
        """

        """
        {'id': self.idtag,
        'active': active_prof,
        'rate': rate_prof}
        """
        data = {'id': self.idtag}
        for property_name, profile_name in self.properties_with_profile.items():
            data[property_name] = profile_name

        return data

    def copy(self):
        """
        Create a deep copy of this object
        """
        tpe = type(self)

        try:
            new_obj = tpe(name=self.name,
                          idtag=self.idtag,
                          code=self.code,
                          device_type=self.device_type)
        except TypeError:
            new_obj = tpe(name=self.name,
                          idtag=self.idtag,
                          code=self.code)

        for prop_name, value in self.__dict__.items():
            setattr(new_obj, prop_name, value)

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
