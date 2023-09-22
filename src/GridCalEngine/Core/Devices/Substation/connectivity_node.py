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


from GridCalEngine.Core.Devices.editable_device import EditableDevice, DeviceType


class ConnectivityNode(EditableDevice):

    def __init__(self, name='Substation', idtag=None, code='', x=0.0, y=0.0, dc=False, bus_bar = None):
        """

        :param name:
        :param idtag:
        :param x:
        :param y:
        """
        EditableDevice.__init__(self,
                                name=name,
                                code=code,
                                idtag=idtag,
                                device_type=DeviceType.ConnectivityNodeDevice)

        self.dc = dc

        self.bus_bar = bus_bar

