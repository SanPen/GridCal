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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from GridCalEngine.Devices.types import ASSOCIATION_TYPE


class GCAssociation:
    """
    GridCal relationship object
    """

    def __init__(self, api_object: ASSOCIATION_TYPE, value: float = 1.0):
        self.api_object: ASSOCIATION_TYPE = api_object

        self.value = value

    def to_dict(self):
        """

        :return:
        """
        return {
            "elm": self.api_object.idtag,
            "value": self.value
        }
