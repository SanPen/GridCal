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

import os
from numpy import sqrt
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Devices.enumerations import BranchType, TransformerControlType

from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp


class Transformer3W(EditableDevice):

    def __init__(self, bus1: Bus = None, bus2: Bus = None, bus3: Bus = None, V1=10, V2=10, V3=10,
                 name='Branch', idtag=None, code='', active=True):
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=active,
                                code=code,
                                device_type=DeviceType.Transformer3WDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the branch.'),
                                                  'idtag': GCProp('', str, 'Unique ID', False),
                                                  'code': GCProp('', str, 'Secondary ID'),
                                                  'bus1': GCProp('', DeviceType.BusDevice, 'Bus 1.'),
                                                  'bus2': GCProp('', DeviceType.BusDevice, 'Bus 2.'),
                                                  'bus3': GCProp('', DeviceType.BusDevice, 'Bus 3.'),
                                                  'active': GCProp('', bool, 'Is the branch active?'),
                                                  'V1': GCProp('kV', float, 'Side 1 rating'),
                                                  'V2': GCProp('kV', float, 'Side 2 rating'),
                                                  'V3': GCProp('kV', float, 'Side 3 rating'),
                                                  },
                                non_editable_attributes=['bus1', 'bus2', 'bus3'],
                                properties_with_profile={'active': 'active_prof'})

        self.bus1 = bus1
        self.bus2 = bus2
        self.bus3 = bus3

        self.V1 = V1
        self.V2 = V2
        self.V3 = V3

        self.x = 0
        self.y = 0
        self.h = 0
        self.w = 0

    def retrieve_graphic_position(self):
        """
        Get the position set by the graphic object into this object's variables
        :return: Nothing
        """
        if self.graphic_obj is not None:
            self.x = int(self.graphic_obj.pos().x())
            self.y = int(self.graphic_obj.pos().y())
