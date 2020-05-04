# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.


import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Devices.types import BranchType
from GridCal.Engine.Devices.transformer import TransformerType
from GridCal.Engine.Devices.sequence_line import SequenceLineType
from GridCal.Engine.Devices.underground_line import UndergroundLineType

from GridCal.Engine.Devices.meta_devices import EditableDevice, DeviceType, GCProp
from GridCal.Engine.Devices.tower import Tower


class DCLine(EditableDevice):

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, name='DC Line', active=True,
                 r1=0.0001, rate=1e-9, mttf=0, mttr=0):
        """
        Voltage source converter (VSC)
        :param bus_from:
        :param bus_to:
        :param name:
        :param active:
        :param r1:
        :param rate:
        """

        EditableDevice.__init__(self,
                                name=name,
                                active=active,
                                device_type=DeviceType.DCBranchDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the branch.'),
                                                  'bus_from': GCProp('', DeviceType.BusDevice,
                                                                     'Name of the bus at the "from" side of the branch.'),
                                                  'bus_to': GCProp('', DeviceType.BusDevice,
                                                                   'Name of the bus at the "to" side of the branch.'),
                                                  'active': GCProp('', bool, 'Is the branch active?'),
                                                  'rate': GCProp('MVA', float, 'Thermal rating power of the branch.'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure, '
                                                                 'used in reliability studies.'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery, '
                                                                 'used in reliability studies.'),
                                                  'Rrd': GCProp('p.u.', float, 'DC Resistance.'),
                                                  },
                                non_editable_attributes=['bus_from', 'bus_to'],
                                properties_with_profile={'active': 'active_prof',
                                                         'rate': 'rate_prof'})

        # connectivity
        self.bus_from = bus_from
        self.bus_to = bus_to

        # List of measurements
        self.measurements = list()

        # total impedance and admittance in p.u.
        self.Rdc = r1

        self.mttf = mttf
        self.mttr = mttr

        self.active = active
        self.active_prof = None

        # branch rating in MVA
        self.rate = rate
        self.rate_prof = None

        # branch type: Line, Transformer, etc...
        self.branch_type = BranchType.DCLine

