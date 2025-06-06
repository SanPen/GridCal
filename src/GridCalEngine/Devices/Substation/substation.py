# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
import numpy as np
from GridCalEngine.Devices.Parents.editable_device import DeviceType
from GridCalEngine.Devices.Aggregation.area import GenericAreaGroup, Area
from GridCalEngine.Devices.Aggregation.zone import Zone
from GridCalEngine.Devices.Aggregation.country import Country
from GridCalEngine.Devices.Aggregation.community import Community
from GridCalEngine.Devices.Aggregation.region import Region
from GridCalEngine.Devices.Aggregation.municipality import Municipality
from GridCalEngine.Devices.Aggregation.modelling_authority import ModellingAuthority
from GridCalEngine.Devices.profile import Profile


class Substation(GenericAreaGroup):

    def __init__(self,
                 name='Substation',
                 idtag: Union[str, None] = None,
                 code='',
                 latitude=0.0,
                 longitude=0.0,
                 area: Union[Area, None] = None,
                 zone: Union[Zone, None] = None,
                 country: Union[Country, None] = None,
                 community: Union[Community, None] = None,
                 region: Union[Region, None] = None,
                 municipality: Union[Municipality, None] = None,
                 address: str = "",
                 irradiation: float = 0.0,
                 temperature: float = 0.0,
                 wind_speed: float = 0.0,
                 terrain_roughness: float = 0.20,
                 color: Union[str, None] = "#3d7d95"):
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
        :param irradiation:
        :param temperature:
        :param wind_speed:
        :param terrain_roughness:
        :param color: hexadecimal color string (i.e. #AA00FF)
        """
        GenericAreaGroup.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  device_type=DeviceType.SubstationDevice,
                                  latitude=latitude,
                                  longitude=longitude,
                                  color=color,)

        self._area: Union[Area, None] = area
        self._zone: Union[Zone, None] = zone
        self._country: Union[Country, None] = country
        self._community: Union[Community, None] = community
        self._region: Union[Region, None] = region
        self._municipality: Union[Municipality, None] = municipality
        self.address: str = address

        self.irradiation: float = float(irradiation)
        self._irradiation_prof = Profile(default_value=self.irradiation, data_type=float)

        self.temperature: float = float(temperature)
        self._temperature_prof = Profile(default_value=self.temperature, data_type=float)

        self.wind_speed: float = float(wind_speed)
        self._wind_speed_prof = Profile(default_value=self.wind_speed, data_type=float)

        self.terrain_roughness: float = float(terrain_roughness)

        self.modelling_authority: Union[ModellingAuthority, None] = None


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

        self.register(key='modelling_authority', units='', tpe=DeviceType.ModellingAuthority,
                      definition='Modelling authority of this asset')

        self.register(key="address", units="", tpe=str,
                      definition="Substation address")

        self.register(key="irradiation", units="W/m^2", tpe=float,
                      definition="Substation solar irradiation",
                      profile_name="irradiation_prof")

        self.register(key="temperature", units="ºC", tpe=float,
                      definition="Substation temperature",
                      profile_name="temperature_prof")

        self.register(key="wind_speed", units="m/s", tpe=float,
                      definition="Substation wind speed at 80m above the ground",
                      profile_name="wind_speed_prof")

        self.register(key="terrain_roughness", units="", tpe=float,
                      definition="This value is ised for wind speed extrapolation.\n"
                                 "Typical values:\n"
                                 "Not rough (sand, snow, sea): 0~0.02\n"
                                 "Slightly rough (grass, cereal field): 0.02~0.2\n"
                                 "Rough (forest, small houses): 1.0~1.5\n"
                                 "Very rough (Large buildings):1.0~4.0")

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

            if val is not None and self.auto_update_enabled:
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

            if val is not None and self.auto_update_enabled:
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

            if val is not None and self.auto_update_enabled:
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

            if val is not None and self.auto_update_enabled:
                if val.region is not None and self.region is None:
                    self.region = val.region

        else:
            raise Exception(
                str(type(val)) + 'not supported to be set into a municipality of type Union[Municipality, None]')

    @property
    def irradiation_prof(self) -> Profile:
        """
        Irradiation profile
        :return: Profile
        """
        return self._irradiation_prof

    @irradiation_prof.setter
    def irradiation_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._irradiation_prof = val
        elif isinstance(val, np.ndarray):
            self._irradiation_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a irradiation_prof')

    @property
    def temperature_prof(self) -> Profile:
        """
        Temperature profile
        :return: Profile
        """
        return self._temperature_prof

    @temperature_prof.setter
    def temperature_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._temperature_prof = val
        elif isinstance(val, np.ndarray):
            self._temperature_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a temperature_prof')

    @property
    def wind_speed_prof(self) -> Profile:
        """
        wind_speed_prof profile
        :return: Profile
        """
        return self._wind_speed_prof

    @wind_speed_prof.setter
    def wind_speed_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._wind_speed_prof = val
        elif isinstance(val, np.ndarray):
            self._wind_speed_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a wind_speed_prof')
