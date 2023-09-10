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
from GridCalEngine.IO.base.units import Unit
from GridCalEngine.IO.base.base_property import BaseProperty


class PsseProperty(BaseProperty):
    """
    Psse Property
    """

    def __init__(self,
                 property_name: str,
                 rawx_key: str,
                 class_type: object,
                 unit: Unit,
                 denominator_unit: Unit = None,
                 description: str = '',
                 max_chars=65000,
                 min_value=-1e20,
                 max_value=1e20):

        BaseProperty.__init__(self,
                              property_name=property_name,
                              class_type=class_type,
                              unit=unit,
                              denominator_unit=denominator_unit,
                              description=description,
                              max_chars=max_chars,
                              min_value=min_value,
                              max_value=max_value)

        self.rawx_key = rawx_key
