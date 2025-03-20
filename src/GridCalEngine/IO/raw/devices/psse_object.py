# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import hashlib
import uuid as uuidlib
from typing import List, Dict, TypeVar, Any
from GridCalEngine.IO.base.units import Unit
from GridCalEngine.IO.raw.devices.psse_property import PsseProperty


def uuid_from_seed(seed: str):
    """

    :param seed:
    :return:
    """
    m = hashlib.md5()
    m.update(seed.encode('utf-8'))
    return uuidlib.UUID(m.hexdigest()).hex


def format_raw_float(value: float) -> str:
    """
    Format a float in engineering notation with 5 decimals.
    Ensure the formatted string doesn't exceed 8 characters when possible.
    """
    # Attempt engineering format with 5 decimals
    formatted = f"{value:.5E}"

    # Split into mantissa and exponent
    mantissa, exponent = formatted.split("E")
    exponent = int(exponent)

    # Adjust the exponent to a multiple of 3
    eng_exponent = 3 * (exponent // 3)
    eng_mantissa = float(mantissa) * (10 ** (exponent - eng_exponent))

    # Format the result
    result = f"{eng_mantissa:.5f}E{eng_exponent:+03}"

    # Ensure it fits within 8 characters
    if len(result) <= 11:
        return result
    else:
        # Fall back to a shorter general format if too long
        return f"{value:.5g}"


class RawObject:
    """
    PSSeObject
    """

    def __init__(self, class_name):

        self.class_name = class_name

        self.version = 33

        self.idtag = uuidlib.uuid4().hex  # always initialize with random  uuid

        self.__registered_properties: Dict[str, PsseProperty] = dict()

        self.register_property(property_name="idtag",
                               rawx_key="uuid:string",
                               class_type=str,
                               description="Element UUID")

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

    def get_properties(self) -> List[PsseProperty]:
        """
        Get list of properties
        :return: List[PsseProperty]
        """
        return list(self.__registered_properties.values())

    def get_prop_value(self, prop: PsseProperty):
        """
        Get property value
        :param prop:
        :return:
        """
        return getattr(self, prop.property_name)

    def get_rawx_dict(self) -> Dict[str, PsseProperty]:
        """
        Get the RAWX property dictionary
        :return: Dict[str, PsseProperty]
        """

        return {value.rawx_key: value
                for key, value in self.__registered_properties.items()}

    def register_property(self,
                          property_name: str,
                          rawx_key: str,
                          class_type: TypeVar | object,
                          unit: Unit = Unit(),
                          denominator_unit: Unit = Unit(),
                          description: str = '',
                          max_chars=None,
                          min_value=-1e20,
                          max_value=1e20,
                          format_rule=None):
        """
        Register property of this object
        :param property_name:
        :param rawx_key:
        :param class_type:
        :param unit:
        :param denominator_unit:
        :param description:
        :param max_chars:
        :param min_value:
        :param max_value:
        :param format_rule: some formatting rule
        """
        if hasattr(self, property_name):
            self.__registered_properties[property_name] = PsseProperty(property_name=property_name,
                                                                       rawx_key=rawx_key,
                                                                       class_type=class_type,
                                                                       unit=unit,
                                                                       denominator_unit=denominator_unit,
                                                                       description=description,
                                                                       max_chars=max_chars,
                                                                       min_value=min_value,
                                                                       max_value=max_value,
                                                                       format_rule=format_rule)
        else:
            raise Exception('Property not found when trying to declare it :(')

    def format_raw_line_prop(self, props: List[str]):
        """
        Format a list of property names
        :param props: list of property names
        :return:
        """
        lst = list()
        for p in props:
            if p in self.__registered_properties:
                prop = self.__registered_properties[p]
                val = getattr(self, p)
                if prop.class_type == str:
                    lst.append("'" + val + "'")
                else:
                    lst.append(str(val))
        return ", ".join(lst)

    @staticmethod
    def extend_or_curtail(data: List[Any], n: int) -> List[Any]:
        """
        Extends of curtails the input so that it marches what's expected
        :param data: list of values
        :param n: expected number of items
        :return: extended or curtailed data
        """
        if len(data) == n:
            return data
        elif len(data) < n:
            diff = n - len(data)
            extra = [0 for _ in range(diff)]
            return data + extra
        elif len(data) > n:
            return [data[i] for i in range(n)]

    def format_raw_line(self, props: List[str]) -> str:
        """
        Format a list of values
        :param props: list of property names
        :return:
        """
        lst = list()
        for p_name in props:

            prop = self.__registered_properties.get(p_name, None)

            if prop is None:
                raise Exception(f'Raw property {p_name} not found when trying to format it :(')
            else:
                val = getattr(self, p_name)

                if prop.class_type == str:
                    str_val = str(val)
                    if prop.max_chars is not None:
                        lst.append(f"'{str_val.ljust(prop.max_chars)}'")
                    else:
                        lst.append(f"'{str_val}'")
                elif prop.class_type == float:
                    if prop.format_rule is None:
                        str_val = format_raw_float(value=val)
                    else:
                        str_val = f"{val:{prop.format_rule}}"
                    if prop.max_chars is not None:
                        lst.append(f"{str_val.rjust(prop.max_chars)}")
                    else:
                        lst.append(f"{str_val.rjust(8)}")

                elif prop.class_type == int:
                    str_val = str(val)
                    if prop.max_chars is not None:
                        lst.append(f"{str_val.rjust(prop.max_chars)}")
                    else:
                        lst.append(f"{str_val.rjust(6)}")

                else:
                    lst.append(str(val))

        return ", ".join(lst)

    def get_raw_line(self, version: int) -> str:
        """
        Get raw line
        :param version: PSSe version
        :return: Raw string representing this object
        """
        return ""

    def get_id(self) -> str:
        """
        Get a PSSe ID
        Each device will implement its own way of generating this
        :return: id
        """
        return ""

    def __str__(self):
        return self.get_id()

    def get_seed(self) -> str:
        """
        Get seed ID
        :return: seed ID
        """
        return self.get_id()

    def get_uuid5(self):
        """
        Generate UUID with the seed given by get_id()
        :return: UUID based on the PSSe seed
        """
        return uuid_from_seed(seed=self.get_seed())
