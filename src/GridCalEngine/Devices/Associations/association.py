from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Union, List, Iterator

from GridCalEngine.enumerations import DeviceType
from GridCalEngine.basic_structures import Logger

if TYPE_CHECKING:
    from GridCalEngine.Devices.types import ASSOCIATION_TYPES, ALL_DEV_TYPES


from typing import List, Union, Dict

class ASSOCIATION_TYPES:
    def __init__(self, idtag: str):
        self.idtag = idtag

class Association:
    """
    GridCal relationship object, this handles the unit of association
    """

    def __init__(self, api_objects: List[Union[None, ASSOCIATION_TYPES]] = None, value: float = 1.0):
        """
        Constructor
        :param api_objects: List of ASSOCIATION_TYPES
        :param value: float
        """
        self.api_objects: List[ASSOCIATION_TYPES] = api_objects if api_objects is not None else []
        self.value = value

    def to_dict(self) -> Dict[str, Union[str, float]]:
        """
        Convert the association to a dictionary.
        :return: Dict with the first api_object's idtag and the value.
        """
        if self.api_objects:
            return {
                "elm": self.api_objects[0].idtag,
                "value": self.value
            }
        else:
            return {
                "elm": None,
                "value": self.value
            }

    def to_dict_list(self) -> List[Dict[str, Union[str, float]]]:
        """
        Convert the list of api_objects to a list of dictionaries.
        :return: List of dictionaries with each api_object's idtag and the value.
        """
        return [{"elm": obj.idtag, "value": self.value} for obj in self.api_objects if obj is not None]

    def parse(self,
              data: Dict[str, Union[str, float]],
              elements_dict: Dict[str, ALL_DEV_TYPES]) -> str:
        """
        Parse data to fill the association
        :param data: dictionary data
        :param elements_dict: elements dictionary
        :return: idtag
        """
        idtag = data['elm']
        self.api_object = elements_dict.get(idtag, None)
        self.value = float(data['value'])
        return idtag

    def __eq__(self, other: "Association") -> bool:
        """
        Equal?
        :param other: Association
        :return: is equal?
        """
        if self.api_object.idtag != self.api_object.idtag:
            # Different reference objects
            return False
        if self.value != other.value:
            return False
        return True


class Associations:
    """
    GridCal associations object, this handles a set of associations
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
        :return: DeviceType
        """
        return self._device_type

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
        assoc = Association(api_objects=[api_object], value=val)
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
        :param key: str
        :return: None
        """
        if key in self._data.keys():
            del self._data[key]

    def at_key(self, key: str) -> Union[Association, None]:
        """
        Get Association by key
        :param key: str
        :return: Association or None
        """
        return self._data.get(key, None)

    def to_list(self) -> List[float]:
        """
        Convert associations to a list of values
        :return: list of floats
        """
        return [val.value for val in self._data.values()]

    def to_dict(self) -> List[Dict[str, Union[str, float]]]:
        """
        Get dictionary representation of Associations
        :return: List of dictionaries
        """
        return [val.to_dict() for val in self._data.values()]

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
        :return: None
        """
        for entry in data:
            assoc = Association()
            associated_idtag = assoc.parse(data=entry, elements_dict=elements_dict)
            if assoc.api_object is not None:
                self.add(assoc)
            else:
                logger.add_error(f'Association api_object not found',
                                 device=elm_name,
                                 value=associated_idtag)

    def append(self, item: Association) -> None:
        """
        Add item
        :param item: Association
        :return: None
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
        :return: None
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
            return False
        for key, val in self._data.items():
            val2 = other._data.get(key, None)
            if val2 is None:
                return False
            if val != val2:
                return False
        return True
