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
import random
import uuid
import numpy as np
from typing import List, Dict, AnyStr, Any, Optional, Union, Type, Tuple
from GridCalEngine.Core.Devices.enumerations import DeviceType, TimeFrame, BuildStatus, WindingsConnection, TransformerControlType, ConverterControlType, HvdcControlType, BranchType
from GridCalEngine.basic_structures import ExternalGridMode


class GCProp:
    """
    GridCal property
    """
    def __init__(self,
                 prop_name: str,
                 units: str,
                 tpe: Union[Type[int], Type[bool], Type[float], Type[str], DeviceType, Type[BuildStatus]],
                 definition: str,
                 profile_name: str = '',
                 display: bool = True,
                 editable: bool = True):
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


class EditableDevice:
    """
    This is the main device class from which all inherit
    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 active: bool,
                 device_type: DeviceType):
        """
        Class to generalize any editable device
        :param name: Asset's name
        :param active: is active
        :param device_type: DeviceType instance
        :param idtag: unique ID, if not provided it is generated
        :param code: alternative code to identify this object in other databases (i.e. psse number tec...)
        """

        if idtag is None:
            self.idtag = uuid.uuid4().hex
        else:
            self.idtag = idtag.replace('_', '').replace('-', '')

        self._name = name

        self.code = code

        self.active = active

        self.type_name = device_type.value

        self.device_type: DeviceType = device_type

        # associated graphic object
        self._graphic_obj = None

        self.editable_headers: Dict[str, GCProp] = dict()

        self.non_editable_attributes: List[str] = list()

        self.properties_with_profile: Dict[str, Optional[Any]] = dict()

        self.register(key='name', units='', tpe=str, definition='Name of the branch.')
        self.register(key='idtag', units='', tpe=str, definition='Unique ID', editable=False)
        self.register(key='code', units='', tpe=str, definition='Secondary ID')
        self.register(key='active', units='', tpe=bool, definition='Is active?')  # this one is overriden if active_prof is present

    def get_rdfid(self) -> str:
        """
        Convert the idtag to RDFID
        :return: UUID converted to RDFID
        """
        lenghts = [8, 4, 4, 4, 12]
        chunks = list()
        s = 0
        for l in lenghts:
            a = self.idtag[s:s + l]
            chunks.append(a)
            s += l
        return "-".join(chunks)

    def register(self,
                 key: str,
                 units: str,
                 tpe: Union[Type[int], Type[bool], Type[float], Type[str],
                            DeviceType, Type[BuildStatus], WindingsConnection, TransformerControlType, BranchType],
                 definition: str,
                 profile_name: str = '',
                 display: bool = True,
                 editable: bool = True):
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
        """
        assert (hasattr(self, key))  # the property must exist, this avoids bugs when registering

        self.editable_headers[key] = GCProp(prop_name=key,
                                            units=units,
                                            tpe=tpe,
                                            definition=definition,
                                            profile_name=profile_name,
                                            display=display,
                                            editable=editable)

        if profile_name != '':
            assert (hasattr(self, profile_name))  # the property must exist, this avoids bugs in registering
            self.properties_with_profile[key] = profile_name

        if not editable:
            self.non_editable_attributes.append(key)

    @property
    def graphic_obj(self):
        """
        Get the associated graphical object (if any)
        :return: graphical object
        """
        return self._graphic_obj

    @graphic_obj.setter
    def graphic_obj(self, obj):
        self._graphic_obj = obj

    def generate_uuid(self):
        """
        Generate new UUID for the idtag property
        """
        self.idtag = uuid.uuid4().hex

    def __str__(self) -> AnyStr:
        """
        Name of the object
        :return: string
        """
        return self.name

    def __repr__(self):
        return self.idtag + '::' + self.name

    def __hash__(self):
        # alternatively, return hash(repr(self))
        return int(self.idtag, 16)  # hex string to int

    def __lt__(self, other):
        return self.__hash__() < other.__hash__()

    def __eq__(self, other):
        if hasattr(other, 'idtag'):
            return self.idtag == other.idtag
        else:
            return False

    @property
    def name(self) -> str:
        """
        Name of the object
        """
        return self._name

    @name.setter
    def name(self, val: str):
        self._name = val

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return: list with data
        """

        data = list()
        for name, properties in self.editable_headers.items():
            obj = getattr(self, name)
            if properties.tpe not in [str, float, int, bool]:
                # if the object is not of a primary type, get the idtag instead
                if hasattr(obj, 'idtag'):
                    data.append(obj.idtag)
                else:
                    # some data types might not have the idtag, ten just use the str method
                    data.append(str(obj))
            else:
                data.append(obj)
        return data

    def get_headers(self) -> List[AnyStr]:
        """
        Return a list of headers
        """
        return list(self.editable_headers.keys())

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

    def create_profile(self, magnitude, index, arr=None, arr_in_pu=False):
        """
        Create power profile based on index
        :param magnitude: name of the property
        :param index: pandas time index
        :param arr: array of values to set
        :param arr_in_pu: is the array in per-unit?
        """
        # get the value of the magnitude
        x = getattr(self, magnitude)
        tpe = self.editable_headers[magnitude].tpe
        if arr_in_pu:
            val = arr * x
        else:
            val = np.ones(len(index), dtype=tpe) * x if arr is None else arr

        # set the profile variable associated with the magnitude
        setattr(self, self.properties_with_profile[magnitude], val)

    def ensure_profiles_exist(self, index):
        """
        It might be that when loading the GridCal Model has properties that the file has not.
        Those properties must be initialized as well
        :param index: Time series index (timestamps)
        """
        for magnitude in self.properties_with_profile.keys():

            if index is not None:
                prof_attr = self.properties_with_profile[magnitude]

                profile = getattr(self, prof_attr)

                if profile is None:
                    # there is no profile, create a new one with the default values
                    # print(self.name, ': created profile for ' + prof_attr)
                    self.create_profile(magnitude=magnitude, index=index)
                else:
                    if profile.shape[0] != len(index):
                        # the length of the profile is different from the length of the master profile
                        # print(self.name, ': created profile for ' + prof_attr)
                        self.create_profile(magnitude=magnitude, index=index)
                    else:
                        # all ok
                        pass

            else:
                pass

    def delete_profiles(self):
        """
        Delete the object profiles (set all to None)
        """
        for magnitude in self.properties_with_profile.keys():
            setattr(self, self.properties_with_profile[magnitude], None)

    def set_profile_values(self, t):
        """
        Set the profile values at t
        :param t: time index (integer)
        """
        for magnitude in self.properties_with_profile.keys():
            profile = getattr(self, self.properties_with_profile[magnitude])
            setattr(self, magnitude, profile[t])

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
        return dict()

    def copy(self):
        """
        Create a deep copy of this object
        """
        tpe = type(self)

        new_obj = tpe()

        for prop_name, value in self.__dict__.items():
            setattr(new_obj, prop_name, value)

        return new_obj

    @staticmethod
    def rgb2hex(r: int, g: int, b: int) -> str:
        return "#{:02x}{:02x}{:02x}".format(r, g, b)

    @staticmethod
    def hex2rgb(hexcode: int) -> Tuple[int, ...]:
        return tuple(map(ord, hexcode[1:].decode('hex')))

    def rnd_color(self) -> str:
        r = random.randint(0, 128)
        g = random.randint(0, 128)
        b = random.randint(0, 128)
        return self.rgb2hex(r, g, b)

