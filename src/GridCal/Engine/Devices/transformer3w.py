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
from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp
from GridCal.Engine.Devices.winding import Winding


def delta_to_star(z12, z23, z31):
    """
    Perform the delta->star transformation
    :param z12:
    :param z23:
    :param z31:
    :return:
    """
    zt = z12 + z23 + z31
    if zt > 0:
        z1 = (z12 * z31) / zt
        z2 = (z12 * z23) / zt
        z3 = (z23 * z31) / zt
        return z1, z2, z3
    else:
        return 1e-20, 1e-20, 1e-20


class Transformer3W(EditableDevice):

    def __init__(self, bus1: Bus = None, bus2: Bus = None, bus3: Bus = None,
                 V1=10.0, V2=10.0, V3=10.0,
                 name='Branch', idtag=None, code='', active=True,
                 r12=0.0, r23=0.0, r31=0.0, x12=0.0, x23=0.0, x31=0.0,
                 rate12=0.0, rate23=0.0, rate31=0.0,
                 x=0.0, y=0.0):
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=active,
                                code=code,
                                device_type=DeviceType.Transformer3WDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the branch.'),
                                                  'idtag': GCProp('', str, 'Unique ID', False),
                                                  'code': GCProp('', str, 'Secondary ID'),
                                                  'bus0': GCProp('', DeviceType.BusDevice, 'Middle point connection bus.'),
                                                  'bus1': GCProp('', DeviceType.BusDevice, 'Bus 1.'),
                                                  'bus2': GCProp('', DeviceType.BusDevice, 'Bus 2.'),
                                                  'bus3': GCProp('', DeviceType.BusDevice, 'Bus 3.'),
                                                  'winding1': GCProp('', DeviceType.WindingDevice, 'Winding 1.'),
                                                  'winding2': GCProp('', DeviceType.WindingDevice, 'Winding 2.'),
                                                  'winding3': GCProp('', DeviceType.WindingDevice, 'Winding 3.'),
                                                  'active': GCProp('', bool, 'Is the branch active?'),
                                                  'V1': GCProp('kV', float, 'Side 1 rating'),
                                                  'V2': GCProp('kV', float, 'Side 2 rating'),
                                                  'V3': GCProp('kV', float, 'Side 3 rating'),
                                                  'r12': GCProp('p.u.', float, 'Resistance measured from 1->2'),
                                                  'r23': GCProp('p.u.', float, 'Resistance measured from 2->3'),
                                                  'r31': GCProp('p.u.', float, 'Resistance measured from 3->1'),
                                                  'x12': GCProp('p.u.', float, 'Reactance measured from 1->2'),
                                                  'x23': GCProp('p.u.', float, 'Reactance measured from 2->3'),
                                                  'x31': GCProp('p.u.', float, 'Reactance measured from 3->1'),
                                                  'rate12': GCProp('MVA', float, 'Rating measured from 1->2'),
                                                  'rate23': GCProp('MVA', float, 'Rating measured from 2->3'),
                                                  'rate31': GCProp('MVA', float, 'Rating measured from 3->1'),
                                                  'x': GCProp('px', float, 'x position'),
                                                  'y': GCProp('px', float, 'y position'),
                                                  },
                                non_editable_attributes=['bus0', 'bus1', 'bus2', 'bus3',
                                                         'winding1', 'winding2', 'winding3'],
                                properties_with_profile={'active': 'active_prof'})

        self.bus0 = Bus(name=name + '_bus', vnom=1.0, xpos=x, ypos=y, is_tr_bus=True)

        self._bus1 = bus1
        self._bus2 = bus2
        self._bus3 = bus3

        self._V1 = V1
        self._V2 = V2
        self._V3 = V3

        self._r12 = r12
        self._r23 = r23
        self._r31 = r31

        self._x12 = x12
        self._x23 = x23
        self._x31 = x31

        self._rate12 = rate12
        self._rate23 = rate23
        self._rate31 = rate31

        self.winding1 = Winding(bus_from=self.bus0, bus_to=bus1, HV=V1, LV=1.0, name=name + "_W1")
        self.winding2 = Winding(bus_from=self.bus0, bus_to=bus2, HV=V2, LV=1.0, name=name + "_W2")
        self.winding3 = Winding(bus_from=self.bus0, bus_to=bus3, HV=V3, LV=1.0, name=name + "_W3")

        self.x = x
        self.y = y

    def all_connected(self):
        """
        Check that all three windings are connected to something
        """
        return (self.bus1 is not None) and (self.bus2 is not None) and (self.bus3 is not None)

    @property
    def graphic_obj(self):
        return self._graphic_obj

    @graphic_obj.setter
    def graphic_obj(self, obj):
        self._graphic_obj = obj
        self.bus0.graphic_obj = obj

    @property
    def bus1(self):
        return self._bus1

    @bus1.setter
    def bus1(self, obj: Bus):
        self._bus1 = obj
        self.winding1.bus_to = obj
        self.winding1.set_hv_and_lv(self.winding1.HV, self.winding1.LV)

    @property
    def bus2(self):
        return self._bus2

    @bus2.setter
    def bus2(self, obj: Bus):
        self._bus2 = obj
        self.winding2.bus_to = obj
        self.winding2.set_hv_and_lv(self.winding2.HV, self.winding2.LV)

    @property
    def bus3(self):
        return self._bus3

    @bus3.setter
    def bus3(self, obj: Bus):
        self._bus3 = obj
        self.winding3.bus_to = obj
        self.winding3.set_hv_and_lv(self.winding3.HV, self.winding3.LV)

    @property
    def V1(self):
        return self._V1

    @V1.setter
    def V1(self, val: float):
        self._V1 = val
        self.winding1.HV = val

    @property
    def V2(self):
        return self._V2

    @V2.setter
    def V2(self, val: float):
        self._V2 = val
        self.winding2.HV = val

    @property
    def V3(self):
        return self._V3

    @V3.setter
    def V3(self, val: float):
        self._V3 = val
        self.winding3.HV = val

    def compute_delta_to_star(self):
        """
        Perform the delta -> star transformation
        and apply it to the windings
        """

        r1, r2, r3 = delta_to_star(self.r12, self.r23, self.r31)
        x1, x2, x3 = delta_to_star(self.x12, self.x23, self.x31)
        rate1, rate2, rate3 = delta_to_star(self.rate12, self.rate23, self.rate31)

        self.winding1.R = r1
        self.winding1.X = x1
        self.winding1.rate = rate1

        self.winding2.R = r2
        self.winding2.X = x2
        self.winding2.rate = rate2

        self.winding3.R = r3
        self.winding3.X = x3
        self.winding3.rate = rate3

    @property
    def r12(self):
        return self._r12

    @r12.setter
    def r12(self, val: float):
        self._r12 = val
        self.compute_delta_to_star()

    @property
    def r23(self):
        return self._r23

    @r23.setter
    def r23(self, val: float):
        self._r23 = val
        self.compute_delta_to_star()

    @property
    def r31(self):
        return self._r31

    @r31.setter
    def r31(self, val: float):
        self._r31 = val
        self.compute_delta_to_star()

    @property
    def x12(self):
        return self._x12

    @x12.setter
    def x12(self, val: float):
        self._x12 = val
        self.compute_delta_to_star()

    @property
    def x23(self):
        return self._x23

    @x23.setter
    def x23(self, val: float):
        self._x23 = val
        self.compute_delta_to_star()

    @property
    def x31(self):
        return self._x31

    @x31.setter
    def x31(self, val: float):
        self._x31 = val
        self.compute_delta_to_star()

    @property
    def rate12(self):
        return self._rate12

    @rate12.setter
    def rate12(self, val: float):
        self._rate12 = val
        self.compute_delta_to_star()

    @property
    def rate23(self):
        return self._rate23

    @rate23.setter
    def rate23(self, val: float):
        self._rate23 = val
        self.compute_delta_to_star()

    @property
    def rate31(self):
        return self._rate31

    @rate31.setter
    def rate31(self, val: float):
        self._rate31 = val
        self.compute_delta_to_star()

    def retrieve_graphic_position(self):
        """
        Get the position set by the graphic object into this object's variables
        :return: Nothing
        """
        if self.graphic_obj is not None:
            self.x = int(self.graphic_obj.pos().x())
            self.y = int(self.graphic_obj.pos().y())
