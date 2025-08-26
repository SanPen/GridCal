# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
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
    __slots__ = ('api_object', 'value')

    def __init__(self, api_object: Union[None, ASSOCIATION_TYPES] = None, value: float = 1.0):
        """

        :param api_object:
        :param value:
        """
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
    GridCal associations object, this handles a set of associations
    """
    __slots__ = ('_data', '_device_type')

    def __init__(self, device_type: DeviceType):
        """
        Constructor
        :param device_type: DeviceType
        """
        self._data: Dict[str, Association] = dict()
        self._device_type = device_type

    @property
    def data(self) -> Dict[str, Association]:
        """

        :return:
        """
        return self._data

    @property
    def device_type(self) -> DeviceType:
        """
        Device Type
        :return: DeviceType
        """
        return self._device_type

    @device_type.setter
    def device_type(self, value: DeviceType):
        """
        Set the device type of the association, as needed in empty investments
        :param value: DeviceType
        """
        if isinstance(value, DeviceType):
            self._device_type = value
        else:
            raise ValueError("value must be an instance of DeviceType")

    def add(self, val: Association):
        """
        Add Association
        :param val: Association
        :return: None
        """

        if val.api_object is not None:
            self._data[val.api_object.idtag] = val

    def add_object(self, api_object: ASSOCIATION_TYPES, val: float) -> Association:
        """
        Add association
        :param api_object: ASSOCIATION_TYPES
        :param val: float
        :return: Association
        """
        assoc = Association(api_object=api_object, value=val)
        self.add(assoc)
        return assoc

    def remove(self, val: Association):
        """
        Remove Association
        :param val: Association
        :return: None
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

    def to_list(self) -> List[ALL_DEV_TYPES]:
        """
        Get a list of the associated api objects
        :return:
        """
        return [val.api_object for _, val in self._data.items()]

    def parse(self,
              data: List[Dict[str, Union[str, float]]],
              elements_dict: Dict[str, ALL_DEV_TYPES],
              logger: Logger,
              elm_name: str,
              updatable_device_type: bool = False) -> None:
        """
        Parse the data generated with to_dict()
        :param data: Json data
        :param elements_dict: dictionary of elements of the type self.device_type
        :param logger: Logger
        :param elm_name: base element name for reporting
        :param updatable_device_type: if the device type has to be updated in case of empty investments
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
