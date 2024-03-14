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
from GridCalEngine.Devices.Aggregation.area import GenericAreaGroup, Area
from GridCalEngine.Devices.Aggregation.zone import Zone
from GridCalEngine.Devices.Aggregation.country import Country
from GridCalEngine.Devices.Aggregation.community import Community
from GridCalEngine.Devices.Aggregation.region import Region
from GridCalEngine.Devices.Aggregation.municipality import Municipality


class Substation(GenericAreaGroup):

    def __init__(self, name='Substation', idtag: Union[str, None] = None, code='', latitude=0.0, longitude=0.0,
                 area: Union[Area, None] = None,
                 zone: Union[Zone, None] = None,
                 country: Union[Country, None] = None,
                 community: Union[Community, None] = None,
                 region: Union[Region, None] = None,
                 municipality: Union[Municipality, None] = None,
                 address: str = ""):
        """

        :param name:
        :param idtag:
        :param code:
        :param latitude:
        :param longitude:
        :param area:
        :param zone:
        :param country:
        :param community:
        :param region:
        :param municipality:
        :param address:
        """
        GenericAreaGroup.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  device_type=DeviceType.SubstationDevice,
                                  latitude=latitude,
                                  longitude=longitude)

        self.area: Union[Area, None] = area
        self.zone: Union[Zone, None] = zone
        self.country: Union[Country, None] = country
        self.community: Union[Community, None] = community
        self.region: Union[Region, None] = region
        self.municipality: Union[Municipality, None] = municipality
        self.address: str = address

        self.register(key="area", units="", tpe=DeviceType.AreaDevice,
                      definition="Substation area, altenativelly this can be obtained from the zone")

        self.register(key="zone", units="", tpe=DeviceType.ZoneDevice,
                      definition="Substation area")

        self.register(key="country", units="", tpe=DeviceType.CountryDevice,
                      definition="Substation country, altenativelly this can be obtained from the community")

        self.register(key="community", units="", tpe=DeviceType.CommunityDevice,
                      definition="Substation community, altenativelly this can be obtained from the region")

        self.register(key="region", units="", tpe=DeviceType.RegionDevice,
                      definition="Substation region, altenativelly this can be obtained from the municipality")

        self.register(key="municipality", units="", tpe=DeviceType.MunicipalityDevice,
                      definition="Substation municipality")

        self.register(key="address", units="", tpe=str, definition="Substation address")
