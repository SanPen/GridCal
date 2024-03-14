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
from GridCalEngine.Devices.Parents.editable_device import DeviceType
from GridCalEngine.Devices.Aggregation.area import GenericAreaGroup
from GridCalEngine.Devices.Aggregation.community import Community


class Region(GenericAreaGroup):

    def __init__(self, name='Region', idtag: Union[str, None] = None, code='', latitude=0.0, longitude=0.0,
                 community: Union[Community, None] = None):
        """
        Country
        :param name: name of the area
        :param idtag: UUID code
        :param latitude: latitude (deg)
        :param longitude: longutide (deg)
        """
        GenericAreaGroup.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  device_type=DeviceType.RegionDevice,
                                  latitude=latitude,
                                  longitude=longitude)

        self.community: Union[Community, None] = community

        self.register(key="community", units="", tpe=DeviceType.CommunityDevice,
                      definition="Substation community, altenativelly this can be obtained from the region")
