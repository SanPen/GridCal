# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

from typing import Dict, TypeVar, Union
from GridCalEngine.IO.base.units import Unit


class BaseProperty:
    """
    BaseProperty
    """

    def __init__(self, property_name: str,
                 class_type: TypeVar,
                 unit: Unit,
                 denominator_unit: Unit = None,
                 description: str = '',
                 max_chars=65000,
                 min_value=-1e20,
                 max_value=1e20):
        """

        :param property_name:
        :param class_type:
        :param unit:
        :param denominator_unit:
        :param description:
        :param max_chars:
        :param min_value:
        :param max_value:
        """
        self.property_name = property_name
        self.class_type = class_type
        self.unit = unit
        self.denominator_unit = denominator_unit
        self.description = description
        self.max_chars = max_chars
        self.min_value = min_value
        self.max_value = max_value

    def get_class_name(self):
        """

        :return:
        """
        tpe_name = str(self.class_type)
        if '.' in tpe_name:
            chunks = tpe_name.split('.')
            return (chunks[-1].replace("'", "")
                    .replace("<", "")
                    .replace(">", "").strip())
        else:
            return (tpe_name.replace('class', '')
                    .replace("'", "")
                    .replace("<", "")
                    .replace(">", "").strip())

    def get_unit(self):
        """
        Get units
        :return:
        """
        if self.unit is not None:

            if self.unit.has_unit():
                nom = self.unit.get_unit()

                if self.denominator_unit is not None:

                    if self.denominator_unit.has_unit():
                        den = self.denominator_unit.get_unit()

                        return "{0}/{1}".format(nom, den)
                    else:
                        return nom

                else:
                    return nom
            else:
                return ""
        else:
            if self.denominator_unit is not None:
                den = self.denominator_unit.get_unit()

                return "1/{}".format(den)

            else:
                return ""

    def get_dict(self) -> Dict[str, any]:
        """
        Get dictionary
        :return:
        """
        return {'property_name': self.property_name,
                'class_type': self.get_class_name(),
                'units': self.get_unit(),
                "descriptions": self.description}
