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
from typing import Dict


class MapLocation:
    """
    GraphicLocation
    """

    def __init__(self, latitude: float = 0.0, longitude: float = 0.0, altitude: float = 0.0, api_object=None):
        """

        :param latitude:
        :param longitude:
        :param altitude:
        """

        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        self.api_object = api_object

    def get_properties_dict(self) -> Dict[str, float]:
        """
        get as a dictionary point
        :return:
        """
        return {'latitude': self.latitude, 'longitude': self.longitude, 'altitude': self.altitude}
