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

from typing import Tuple, Union
import numpy as np
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Parents.editable_device import EditableDevice, DeviceType
from GridCalEngine.Devices.Branches.winding import Winding
from GridCalEngine.Devices.profile import Profile


def delta_to_star(z12: float, z23: float, z31: float) -> Tuple[float, float, float]:
    """
    Perform the delta->star transformation
    :param z12: 1 to 2 delta value
    :param z23: 2 to 3 delta value
    :param z31: 3 to 1 delta value
    :return: 0->1, 0->2, 0->3 star values
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

    def __init__(self, idtag=None, code='', name='Branch',
                 bus1: Bus = None, bus2: Bus = None, bus3: Bus = None,
                 V1=10.0, V2=10.0, V3=10.0, active=True,
                 r12=0.0, r23=0.0, r31=0.0, x12=0.0, x23=0.0, x31=0.0,
                 rate12=0.0, rate23=0.0, rate31=0.0,
                 x=0.0, y=0.0):
        """
        Constructor
        :param idtag: Unique identifier
        :param code: Secondary identifier
        :param name: name of the transformer
        :param bus1: Bus 1
        :param bus2: Bus 2
        :param bus3: Bus 3
        :param V1: Nominal voltage at 1 (kV)
        :param V2: Nominal voltage at 2 (kV)
        :param V3: Nominal voltage at 3 (kV)
        :param active: Is active?
        :param r12: 1->2 resistance (p.u.)
        :param r23: 2->3 resistance (p.u.)
        :param r31: 3->1 resistance (p.u.)
        :param x12: 1->2 reactance (p.u.)
        :param x23: 2->3 reactance (p.u.)
        :param x31: 3->1 reactance (p.u.)
        :param rate12: 1->2 rating (MVA)
        :param rate23: 2->3 rating (MVA)
        :param rate31: 3->1 rating (MVA)
        :param x: graphical x position (px)
        :param y: graphical y position (px)
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.Transformer3WDevice)

        self.bus0 = Bus(name=name + '_bus', vnom=1.0, xpos=x, ypos=y, is_internal=True)
        self._bus1 = bus1
        self._bus2 = bus2
        self._bus3 = bus3

        self.active = active
        self._active_prof = Profile(default_value=active)

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

        self.register(key='bus0', units='', tpe=DeviceType.BusDevice, definition='Middle point connection bus.',
                      editable=False)
        self.register(key='bus1', units='', tpe=DeviceType.BusDevice, definition='Bus 1.', editable=False)
        self.register(key='bus2', units='', tpe=DeviceType.BusDevice, definition='Bus 2.', editable=False)
        self.register(key='bus3', units='', tpe=DeviceType.BusDevice, definition='Bus 3.', editable=False)

        self.register('active', units="", tpe=bool, definition='Is active?', profile_name="active_prof")

        self.register(key='winding1', units='', tpe=DeviceType.WindingDevice, definition='Winding 1.', editable=False)
        self.register(key='winding2', units='', tpe=DeviceType.WindingDevice, definition='Winding 2.', editable=False)
        self.register(key='winding3', units='', tpe=DeviceType.WindingDevice, definition='Winding 3.', editable=False)

        self.register(key='V1', units='kV', tpe=float, definition='Side 1 rating')
        self.register(key='V2', units='kV', tpe=float, definition='Side 2 rating')
        self.register(key='V3', units='kV', tpe=float, definition='Side 3 rating')
        self.register(key='r12', units='p.u.', tpe=float, definition='Resistance measured from 1->2')
        self.register(key='r23', units='p.u.', tpe=float, definition='Resistance measured from 2->3')
        self.register(key='r31', units='p.u.', tpe=float, definition='Resistance measured from 3->1')
        self.register(key='x12', units='p.u.', tpe=float, definition='Reactance measured from 1->2')
        self.register(key='x23', units='p.u.', tpe=float, definition='Reactance measured from 2->3')
        self.register(key='x31', units='p.u.', tpe=float, definition='Reactance measured from 3->1')
        self.register(key='rate12', units='MVA', tpe=float, definition='Rating measured from 1->2')
        self.register(key='rate23', units='MVA', tpe=float, definition='Rating measured from 2->3')
        self.register(key='rate31', units='MVA', tpe=float, definition='Rating measured from 3->1')
        self.register(key='x', units='px', tpe=float, definition='x position')
        self.register(key='y', units='px', tpe=float, definition='y position')

    @property
    def active_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._active_prof

    @active_prof.setter
    def active_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._active_prof = val
        elif isinstance(val, np.ndarray):
            self._active_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a active_prof')

    def all_connected(self):
        """
        Check that all three windings are connected to something
        """
        return (self.bus1 is not None) and (self.bus2 is not None) and (self.bus3 is not None)

    @property
    def bus1(self) -> Bus:
        """
        Bus 1
        """
        return self._bus1

    @bus1.setter
    def bus1(self, obj: Bus):
        self._bus1 = obj
        self.winding1.bus_to = obj

        if obj is not None:
            self.winding1.set_hv_and_lv(self.winding1.HV, self.winding1.LV)

    @property
    def bus2(self) -> Bus:
        """
        Bus 2
        """
        return self._bus2

    @bus2.setter
    def bus2(self, obj: Bus):
        self._bus2 = obj
        self.winding2.bus_to = obj

        if obj is not None:
            self.winding2.set_hv_and_lv(self.winding2.HV, self.winding2.LV)

    @property
    def bus3(self) -> Bus:
        """
        Bus 3
        """
        return self._bus3

    @bus3.setter
    def bus3(self, obj: Bus):
        self._bus3 = obj
        self.winding3.bus_to = obj

        if obj is not None:
            self.winding3.set_hv_and_lv(self.winding3.HV, self.winding3.LV)

    @property
    def V1(self) -> float:
        """
        Nominal voltage 1 in kV
        """
        return self._V1

    @V1.setter
    def V1(self, val: float):
        self._V1 = val
        self.winding1.HV = val

    @property
    def V2(self):
        """
        Nominal voltage 2 in kV
        """
        return self._V2

    @V2.setter
    def V2(self, val: float):
        self._V2 = val
        self.winding2.HV = val

    @property
    def V3(self):
        """
        Nominal voltage 3 in kV
        """
        return self._V3

    @V3.setter
    def V3(self, val: float):
        self._V3 = val
        self.winding3.HV = val

    def compute_delta_to_star(self) -> None:
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
        """
        1->2 measured resistance in p.u.
        """
        return self._r12

    @r12.setter
    def r12(self, val: float):
        self._r12 = val
        self.compute_delta_to_star()

    @property
    def r23(self):
        """
        2->3 measured resistance in p.u.
        """
        return self._r23

    @r23.setter
    def r23(self, val: float):
        self._r23 = val
        self.compute_delta_to_star()

    @property
    def r31(self):
        """
        3->1 measured resistance in p.u.
        """
        return self._r31

    @r31.setter
    def r31(self, val: float):
        self._r31 = val
        self.compute_delta_to_star()

    @property
    def x12(self):
        """
        1->2 measured reactance in p.u.
        """
        return self._x12

    @x12.setter
    def x12(self, val: float):
        self._x12 = val
        self.compute_delta_to_star()

    @property
    def x23(self):
        """
        2->3 measured reactance in p.u.
        """
        return self._x23

    @x23.setter
    def x23(self, val: float):
        self._x23 = val
        self.compute_delta_to_star()

    @property
    def x31(self):
        """
        3->1 measured reactance in p.u.
        """
        return self._x31

    @x31.setter
    def x31(self, val: float):
        self._x31 = val
        self.compute_delta_to_star()

    @property
    def rate12(self):
        """
        1->2 measured rate in MVA
        """
        return self._rate12

    @rate12.setter
    def rate12(self, val: float):
        self._rate12 = val
        self.compute_delta_to_star()

    @property
    def rate23(self):
        """
        2->3 measured rate in MVA
        """
        return self._rate23

    @rate23.setter
    def rate23(self, val: float):
        self._rate23 = val
        self.compute_delta_to_star()

    @property
    def rate31(self):
        """
        3->1 measured rate in MVA
        """
        return self._rate31

    @rate31.setter
    def rate31(self, val: float):
        self._rate31 = val
        self.compute_delta_to_star()

    def get_winding(self, i: int) -> Winding:
        """
        Get winding from an integer
        :param i: winding index
        :return: Winding at i
        """
        if i == 0:
            return self.winding1
        elif i == 1:
            return self.winding2
        elif i == 2:
            return self.winding3
        else:
            raise Exception("Windings int positions go from 0 to 2")
