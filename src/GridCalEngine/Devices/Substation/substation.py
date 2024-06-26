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

        self._area: Union[Area, None] = area
        self._zone: Union[Zone, None] = zone
        self._country: Union[Country, None] = country
        self._community: Union[Community, None] = community
        self._region: Union[Region, None] = region
        self._municipality: Union[Municipality, None] = municipality
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

    @property
    def area(self) -> Union[Area, None]:
        """
        area getter
        :return: Union[Area, None]
        """
        return self._area

    @area.setter
    def area(self, val: Union[Area, None]):
        """
        area getter
        :param val: value
        """
        if isinstance(val, Union[Area, None]):
            self._area = val
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a area of type Union[Area, None]')

    @property
    def zone(self) -> Union[Zone, None]:
        """
        zone getter
        :return: Union[Zone, None]
        """
        return self._zone

    @zone.setter
    def zone(self, val: Union[Zone, None]):
        """
        zone getter
        :param val: value
        """
        if isinstance(val, Union[Zone, None]):
            self._zone = val

            if val is not None:
                if val.area is not None and self.area is None:
                    self.area = val.area

        else:
            raise Exception(str(type(val)) + 'not supported to be set into a zone of type Union[Zone, None]')

    @property
    def country(self) -> Union[Country, None]:
        """
        country getter
        :return: Union[Country, None]
        """
        return self._country

    @country.setter
    def country(self, val: Union[Country, None]):
        """
        country getter
        :param val: value
        """
        if isinstance(val, Union[Country, None]):
            self._country = val
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a country of type Union[Country, None]')

    @property
    def community(self) -> Union[Community, None]:
        """
        community getter
        :return: Union[Community, None]
        """
        return self._community

    @community.setter
    def community(self, val: Union[Community, None]):
        """
        community getter
        :param val: value
        """
        if isinstance(val, Union[Community, None]):
            self._community = val

            if val is not None:
                if val.country is not None and self.country is None:
                    self.country = val.country
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a community of type Union[Community, None]')

    @property
    def region(self) -> Union[Region, None]:
        """
        region getter
        :return: Union[Region, None]
        """
        return self._region

    @region.setter
    def region(self, val: Union[Region, None]):
        """
        region getter
        :param val: value
        """
        if isinstance(val, Union[Region, None]):
            self._region = val

            if val is not None:
                if val.community is not None and self.community is None:
                    self.community = val.community

        else:
            raise Exception(str(type(val)) + 'not supported to be set into a region of type Union[Region, None]')

    @property
    def municipality(self) -> Union[Municipality, None]:
        """
        municipality getter
        :return: Union[Municipality, None]
        """
        return self._municipality

    @municipality.setter
    def municipality(self, val: Union[Municipality, None]):
        """
        municipality getter
        :param val: value
        """
        if isinstance(val, Union[Municipality, None]):
            self._municipality = val

            if val is not None:
                if val.region is not None and self.region is None:
                    self.region = val.region

        else:
            raise Exception(
                str(type(val)) + 'not supported to be set into a municipality of type Union[Municipality, None]')
