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
from typing import Dict


class MapLocation:
    """
    GraphicLocation
    """

    def __init__(self,
                 latitude: float = 0.0,
                 longitude: float = 0.0,
                 altitude: float = 0.0,
                 api_object=None,
                 draw_labels: bool = True):
        """

        :param latitude:
        :param longitude:
        :param altitude:
        :param api_object:
        :param draw_labels:
        """

        self._latitude = latitude if latitude is not None else 0.0
        self._longitude = longitude if longitude is not None else 0.0
        self._altitude = altitude if altitude is not None else 0.0
        self.draw_labels = draw_labels
        self.api_object = api_object

    @property
    def latitude(self):
        """

        :return:
        """
        return self._latitude

    @latitude.setter
    def latitude(self, val: float):
        """

        :param val:
        :return:
        """
        self._latitude = val if val is not None else 0.0

    @property
    def longitude(self):
        """

        :return:
        """
        return self._longitude

    @longitude.setter
    def longitude(self, val: float):
        """

        :param val:
        :return:
        """
        self._longitude = val if val is not None else 0.0

    @property
    def altitude(self):
        """

        :return:
        """
        return self._altitude

    @altitude.setter
    def altitude(self, val: float):
        """

        :param val:
        :return:
        """
        self._altitude = val if val is not None else 0.0

    def get_properties_dict(self) -> Dict[str, float]:
        """
        get as a dictionary point
        :return:
        """
        return {'latitude': self.latitude,
                'longitude': self.longitude,
                'altitude': self.altitude,
                'draw_labels': self.draw_labels}
