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

from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp


class VSC(EditableDevice):

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, name='VSC', idtag=None, active=True,
                 r1=0.0001, x1=0.05, m=0.8, theta=0.1, G0=1e-5, Beq=0.001, rate=1e-9,
                 mttf=0, mttr=0):
        """
        Voltage source converter (VSC)
        :param bus_from:
        :param bus_to:
        :param name:
        :param active:
        :param r1:
        :param x1:
        :param m:
        :param theta:
        :param G0:
        :param Beq:
        :param rate:
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=active,
                                device_type=DeviceType.VscDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the branch.'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
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
                                                  'R1': GCProp('p.u.', float, 'Resistive losses.'),
                                                  'X1': GCProp('p.u.', float, 'Magnetic losses.'),
                                                  'Gsw': GCProp('p.u.', float, 'Inverter losses.'),
                                                  'Beq': GCProp('p.u.', float, 'Total shunt susceptance.'),
                                                  'm': GCProp('', float, 'Tap changer module, it a value close to 1.0'),
                                                  'theta': GCProp('rad', float, 'Converter firing angle.'),
                                                  },
                                non_editable_attributes=['bus_from', 'bus_to'],
                                properties_with_profile={'active': 'active_prof',
                                                         'rate': 'rate_prof'})

        # the VSC must only connect from an AC to a DC bus
        assert(bus_from.is_dc != bus_to.is_dc)

        # connectivity:
        # for the later primitives to make sense, the "bus from" must be AC and the "bus to" must be DC
        if bus_to.is_dc:
            self.bus_from = bus_from
            self.bus_to = bus_to
        else:
            self.bus_from = bus_to
            self.bus_to = bus_from
            print('Corrected the connection direction of the VSC device:', self.name)

        # List of measurements
        self.measurements = list()

        # total impedance and admittance in p.u.
        self.R1 = r1
        self.X1 = x1
        self.G0 = G0
        self.Beq = Beq
        self.m = m
        self.theta = theta

        self.mttf = mttf
        self.mttr = mttr

        self.active = active
        self.active_prof = None

        # branch rating in MVA
        self.rate = rate
        self.rate_prof = None

        # branch type: Line, Transformer, etc...
        self.branch_type = BranchType.VSC
