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


from GridCal.Engine.Core.Devices.editable_device import DeviceType, GCProp
from GridCal.Engine.Core.Devices.Aggregation.area import GenericAreaGroup


class Substation(GenericAreaGroup):

    def __init__(self, name='Substation', idtag=None, code='', latitude=0.0, longitude=0.0):
        """

        :param name:
        :param idtag:
        :param latitude:
        :param longitude:
        """
        GenericAreaGroup.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  device_type=DeviceType.SubstationDevice,
                                  latitude=latitude,
                                  longitude=longitude)
