# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from VeraGridEngine.Devices.Parents.editable_device import DeviceType
from VeraGridEngine.Devices.Aggregation.area import GenericAreaGroup
from VeraGridEngine.Devices.Aggregation.region import Region


class Municipality(GenericAreaGroup):
    __slots__ = ('region',)

    def __init__(self, name='Municipality', idtag: Union[str, None] = None, code='', latitude=0.0, longitude=0.0,
                 region: Union[Region, None] = None):
        """
        Country
        :param name: name of the area
        :param idtag: UUID code
        :param latitude: latitude (deg)
        :param longitude: longutide (deg)
        :param region: (optional)
        """
        GenericAreaGroup.__init__(self,
                                  name=name,
                                  idtag=idtag,
                                  code=code,
                                  device_type=DeviceType.MunicipalityDevice,
                                  latitude=latitude,
                                  longitude=longitude)

        self.region: Union[Region, None] = region

        self.register(key="region", units="", tpe=DeviceType.RegionDevice,
                      definition="Substation region, alternatively this can be obtained from the municipality")
