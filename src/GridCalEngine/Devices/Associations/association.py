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
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Union, List, Iterator
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.basic_structures import Logger

if TYPE_CHECKING:
    from GridCalEngine.Devices.types import ASSOCIATION_TYPES, ALL_DEV_TYPES


class Association:
    """
    GridCal relationship object, this handles the unit of association
    """

    def __init__(self, api_object: Union[None, ASSOCIATION_TYPES] = None, value: float = 1.0):

        self.api_object: ASSOCIATION_TYPES = api_object

        self.value = value

    def to_dict(self) -> Dict[str, Union[str, float]]:
        """

        :return:
        """
        return {
            "elm": self.api_object.idtag,
            "value": self.value
        }

    def parse(self,
              data: Dict[str, Union[str, float]],
              elements_dict: Dict[str, ALL_DEV_TYPES]) -> str:
        """

        :param data:
        :param elements_dict:
        :return:
        """
        idtag = data['elm']
        self.api_object = elements_dict.get(idtag, None)
        self.value = float(data['value'])
        return idtag

    def __eq__(self, other: "Association") -> bool:
        """
        Equal?
        :param other:
        :return:
        """
        if self.api_object.idtag != self.api_object.idtag:
            # Different refference objects
            return False
        if self.value != self.value:
            # different values
            return False

        return True


class Associations:
    """
    GridCal associations object, this handless a set of associations
    """

    def __init__(self, device_type: DeviceType):
        """
        Constructor
        :param device_type: DeviceType
        """
        self._data: Dict[str, Association] = dict()

        self._device_type = device_type

    @property
    def device_type(self) -> DeviceType:
        """
        Device Type
        :return:
        """
        return self._device_type

    def add(self, val: Association):
        """
        Add Association
        :param val:
        :return:
        """
        if val.api_object is not None:
            self._data[val.api_object.idtag] = val

    def add_object(self, api_object: ASSOCIATION_TYPES, val: float) -> Association:
        """
        Add association
        :param api_object:
        :param val:
        :return:
        """
        assoc = Association(api_object=api_object, value=val)
        self.add(assoc)
        return assoc

    def remove(self, val: Association):
        """
        Remove Association
        :param val:
        :return:
        """
        if val.api_object is not None:
            del self._data[val.api_object.idtag]

    def remove_by_key(self, key: str):
        """
        Remove Association by key
        :param key:
        :return:
        """
        if key in self._data.keys():
            del self._data[key]

    def at_key(self, key: str) -> Union[Association, None]:
        """
        Remove Association by key
        :param key:
        :return:
        """
        return self._data.get(key, None)

    def to_dict(self) -> List[Dict[str, Union[str, float]]]:
        """
        Get dictionary representation of Associations
        :return:
        """
        return [val.to_dict() for _, val in self._data.items()]

    def parse(self,
              data: List[Dict[str, Union[str, float]]],
              elements_dict: Dict[str, ALL_DEV_TYPES],
              logger: Logger,
              elm_name: str) -> None:
        """
        Parse the data generated with to_dict()
        :param data: Json data
        :param elements_dict: dictionary of elements of the type self.device_type
        :param logger: Logger
        :param elm_name: base element name for reporting
        """

        for entry in data:

            assoc = Association()
            associated_idtag = assoc.parse(
                data=entry,
                elements_dict=elements_dict
            )

            if assoc.api_object is not None:
                # add the entry
                self.add(assoc)
            else:
                logger.add_error(f'Association api_object not found',
                                 device=elm_name,
                                 value=associated_idtag)

    def append(self, item: Association) -> None:
        """
        Add item
        :param item:
        """
        self.add(item)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[Association]:
        for key, val in self._data.items():
            yield val

    def __repr__(self) -> str:
        return repr(self._data)

    def clear(self) -> None:
        """
        Clear data
        """
        self._data.clear()

    def __eq__(self, other: "Associations") -> bool:
        """
        Equal?
        :param other: Associations
        :return: is equal?
        """
        if not isinstance(other, Associations):
            return False

        if len(self) != len(other):
            # different length
            return False

        for key, val in self._data.items():

            val2 = other._data.get(key, None)

            if val2 is None:
                # a key was not found, these are not equal
                return False
            else:
                if val != val2:
                    # the associations are different
                    return False

        return True





