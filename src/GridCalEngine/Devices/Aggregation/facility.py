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


from typing import Union
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType


class Facility(EditableDevice):
    """
    This is an aggregation of Injection devices
    """

    def __init__(self, name='', code='', idtag: Union[str, None] = None, latitude=0.0, longitude=0.0):
        """
        Constructor
        :param name: Name
        :param code: Secondary code
        :param idtag: IdTag
        :param latitude: latitude (deg)
        :param longitude: longitude (deg)
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.FacilityDevice)

        self.latitude = float(latitude)
        self.longitude = float(longitude)

        self.register(key='longitude', units='deg', tpe=float, definition='longitude.')
        self.register(key='latitude', units='deg', tpe=float, definition='latitude.')
