# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from GridCalEngine.Devices.Parents.editable_device import DeviceType
from GridCalEngine.Devices.Aggregation.area import GenericAreaGroup
from GridCalEngine.Devices.Aggregation.country import Country


class Community(GenericAreaGroup):

    def __init__(self, name='Country', idtag: Union[str, None] = None, code='', latitude=0.0, longitude=0.0,
                 country: Union[Country, None] = None):
        """
        Country
        :param name: name of the area
        :param idtag: UUID code
        :param latitude: latitude (deg)
        :param longitude: longutide (deg)
        :param country: (optional)
        """
        GenericAreaGroup.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  device_type=DeviceType.CommunityDevice,
                                  latitude=latitude,
                                  longitude=longitude)

        self.country: Union[Country, None] = country

        self.register(key="country", units="", tpe=DeviceType.CountryDevice,
                      definition="Substation country, altenativelly this can be obtained from the community")
