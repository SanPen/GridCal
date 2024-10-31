# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


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
