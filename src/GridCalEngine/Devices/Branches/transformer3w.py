# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Tuple, Union
import numpy as np
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.Devices.Parents.physical_device import PhysicalDevice
from GridCalEngine.Devices.Branches.winding import Winding
from GridCalEngine.Devices.Branches.transformer_type import get_impedances
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.enumerations import DeviceType


def delta_to_star(z12: float, z23: float, z31: float) -> Tuple[float, float, float]:
    """
    Perform the delta->star transformation
    See: https://www.electronics-tutorials.ws/dccircuits/dcp_10.html
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


def star_to_delta(z1: float, z2: float, z3: float) -> Tuple[float, float, float]:
    """
    Perform the star->delta transformation
    See: https://www.electronics-tutorials.ws/dccircuits/dcp_10.html
    :param z1: 0->1 impedance
    :param z2: 0->2 impedance
    :param z3: 0->3 impedance
    :return: z12, z23, z31 impedances
    """
    zt = z1 * z2 + z2 * z3 + z3 * z1
    z12 = zt / z3
    z23 = zt / z1
    z31 = zt / z2

    return z12, z23, z31


class Transformer3W(PhysicalDevice):

    def __init__(self, idtag: Union[str, None] = None,
                 code: str = '',
                 name: str = 'Branch',
                 bus0: Union[None, Bus] = None,
                 bus1: Bus = None, bus2: Bus = None, bus3: Bus = None,
                 cn0: Union[None, ConnectivityNode] = None,
                 cn1: ConnectivityNode = None,
                 cn2: ConnectivityNode = None,
                 cn3: ConnectivityNode = None,
                 w1_idtag: Union[str, None] = None,
                 w2_idtag: Union[str, None] = None,
                 w3_idtag: Union[str, None] = None,
                 V1=10.0, V2=10.0, V3=10.0, active=True,
                 r12=0.0, r23=0.0, r31=0.0, x12=0.0, x23=0.0, x31=0.0,
                 rate12=0.0, rate23=0.0, rate31=0.0,
                 x=0.0, y=0.0):
        """
        Constructor
        :param idtag: Unique identifier
        :param code: Secondary identifier
        :param name: name of the transformer
        :param bus1: Bus 0, middle bus
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
        PhysicalDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.Transformer3WDevice)

        if bus0 is None:
            self.bus0 = Bus(name=name + '_bus', Vnom=1.0, xpos=x, ypos=y, is_internal=True)
        else:
            bus0.internal = True
            bus0.Vnom = 1.0
            self.bus0 = bus0

        if cn0 is None:
            self.cn0 = ConnectivityNode(name=name + '_cn',
                                        Vnom=1.0,
                                        internal=True,
                                        default_bus=self.bus0)
        else:
            cn0.is_internal = True
            cn0.Vnom = 1.0
            self.cn0 = cn0
            self.cn0.bus = self.bus0

        self._bus1 = bus1
        self._bus2 = bus2
        self._bus3 = bus3

        self._cn1 = cn1
        self._cn2 = cn2
        self._cn3 = cn3

        self.active = bool(active)
        self._active_prof = Profile(default_value=self.active, data_type=bool)

        self._V1 = float(V1)
        self._V2 = float(V2)
        self._V3 = float(V3)

        self._r12 = float(r12)
        self._r23 = float(r23)
        self._r31 = float(r31)

        self._x12 = float(x12)
        self._x23 = float(x23)
        self._x31 = float(x31)

        self._rate1 = float(rate12)
        self._rate2 = float(rate23)
        self._rate3 = float(rate31)

        # remember design values also
        self._Pcu12: float = 0.0
        self._Pcu23: float = 0.0
        self._Pcu31: float = 0.0

        self._Vsc12: float = 0.0
        self._Vsc23: float = 0.0
        self._Vsc31: float = 0.0

        self._Pfe: float = 0.0
        self._I0: float = 0.0

        self._winding1 = Winding(bus_from=self.bus0, idtag=w1_idtag,
                                 bus_to=bus1,
                                 cn_from=self.cn0,
                                 cn_to=self.cn1,
                                 HV=V1, LV=1.0, name=name + "_W1")
        self._winding2 = Winding(bus_from=self.bus0, idtag=w2_idtag,
                                 bus_to=bus2,
                                 cn_from=self.cn0,
                                 cn_to=self.cn2,
                                 HV=V2, LV=1.0, name=name + "_W2")
        self._winding3 = Winding(bus_from=self.bus0, idtag=w3_idtag,
                                 bus_to=bus3,
                                 cn_from=self.cn0,
                                 cn_to=self.cn3,
                                 HV=V3, LV=1.0, name=name + "_W3")

        self.x = float(x)
        self.y = float(y)

        self.register(key='bus0', units='', tpe=DeviceType.BusDevice, definition='Middle point connection bus.',
                      editable=False)
        self.register(key='bus1', units='', tpe=DeviceType.BusDevice, definition='Bus 1.', editable=False)
        self.register(key='bus2', units='', tpe=DeviceType.BusDevice, definition='Bus 2.', editable=False)
        self.register(key='bus3', units='', tpe=DeviceType.BusDevice, definition='Bus 3.', editable=False)

        self.register(key='cn0', units='', tpe=DeviceType.ConnectivityNodeDevice,
                      definition='Middle point connection cn.',
                      editable=False)
        self.register(key='cn1', units='', tpe=DeviceType.ConnectivityNodeDevice, definition='ConnectivityNode 1.',
                      editable=False)
        self.register(key='cn2', units='', tpe=DeviceType.ConnectivityNodeDevice, definition='ConnectivityNode 2.',
                      editable=False)
        self.register(key='cn3', units='', tpe=DeviceType.ConnectivityNodeDevice, definition='ConnectivityNode 3.',
                      editable=False)

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

        self.register(key='rate1', units='MVA', tpe=float, definition='Rating 1', old_names=['rate12'])
        self.register(key='rate2', units='MVA', tpe=float, definition='Rating 2', old_names=['rate23'])
        self.register(key='rate3', units='MVA', tpe=float, definition='Rating 3', old_names=['rate31'])

        self.register(key='Pcu12', units='KW', tpe=float, definition='Copper loss between 1->2')
        self.register(key='Pcu23', units='KW', tpe=float, definition='Copper loss between 2->3')
        self.register(key='Pcu31', units='KW', tpe=float, definition='Copper loss between 3->1')

        self.register(key='Vsc12', units='%', tpe=float, definition='Short-circuit voltage between 1->2')
        self.register(key='Vsc23', units='%', tpe=float, definition='Short-circuit voltage between 2->3')
        self.register(key='Vsc31', units='%', tpe=float, definition='Short-circuit voltage between 3->1')

        self.register(key='Pfe', units='KW', tpe=float, definition='Iron loss')
        self.register(key='I0', units='%', tpe=float, definition='No-load current')

        self.register(key='x', units='px', tpe=float, definition='x position')
        self.register(key='y', units='px', tpe=float, definition='y position')

    @property
    def winding1(self) -> Winding:
        """
        Winding 1 getter
        :return: Winding
        """
        return self._winding1

    @property
    def winding2(self) -> Winding:
        """
        Winding 2 getter
        :return: Winding
        """
        return self._winding2

    @property
    def winding3(self) -> Winding:
        """
        Winding 3 getter
        :return: Winding
        """
        return self._winding3

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
    def cn1(self) -> ConnectivityNode:
        """
        ConnectivityNode 1
        """
        return self._cn1

    @cn1.setter
    def cn1(self, obj: ConnectivityNode):
        self._cn1 = obj
        self.winding1.cn_to = obj

    @property
    def cn2(self) -> ConnectivityNode:
        """
        ConnectivityNode 2
        """
        return self._cn2

    @cn2.setter
    def cn2(self, obj: ConnectivityNode):
        self._cn2 = obj
        self.winding2.cn_to = obj

    @property
    def cn3(self) -> ConnectivityNode:
        """
        ConnectivityNode 3
        """
        return self._cn3

    @cn3.setter
    def cn3(self, obj: ConnectivityNode):
        self._cn3 = obj
        self.winding3.cn_to = obj

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

        self.winding1.R = r1
        self.winding1.X = x1
        self.winding1.rate = self.rate1

        self.winding2.R = r2
        self.winding2.X = x2
        self.winding2.rate = self.rate2

        self.winding3.R = r3
        self.winding3.X = x3
        self.winding3.rate = self.rate3

    def fill_from_star(self, r1: float, r2: float, r3: float, x1: float, x2: float, x3: float) -> None:
        """
        Fill from Star values
        :param r1: resistance of the branch 1 (p.u.)
        :param r2: resistance of the branch 2 (p.u.)
        :param r3: resistance of the branch 3 (p.u.)
        :param x1: reactance of the branch 1 (p.u.)
        :param x2: reactance of the branch 2 (p.u.)
        :param x3: reactance of the branch 3 (p.u.)
        """
        self._r12, self._r23, self._r31 = star_to_delta(z1=r1, z2=r2, z3=r3)
        self._x12, self._x23, self._x31 = star_to_delta(z1=x1, z2=x2, z3=x3)

        self.winding1.R = r1
        self.winding1.X = x1

        self.winding2.R = r2
        self.winding2.X = x2

        self.winding3.R = r3
        self.winding3.X = x3

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
    def rate1(self):
        """
        1 measured rate in MVA
        """
        return self._rate1

    @rate1.setter
    def rate1(self, val: float):
        self._rate1 = val
        self.compute_delta_to_star()

    @property
    def rate2(self):
        """
        2 measured rate in MVA
        """
        return self._rate2

    @rate2.setter
    def rate2(self, val: float):
        self._rate2 = val
        self.compute_delta_to_star()

    @property
    def rate3(self):
        """
        3->1 measured rate in MVA
        """
        return self._rate3

    @rate3.setter
    def rate3(self, val: float):
        self._rate3 = val
        self.compute_delta_to_star()

    @property
    def Pcu12(self) -> float:
        """

        :return:
        """
        return self._Pcu12

    @Pcu12.setter
    def Pcu12(self, value: float) -> None:
        self._Pcu12 = value
        self._recalc_from_definition(Sbase=100)

    # Property for _Pcu23
    @property
    def Pcu23(self) -> float:
        """

        :return:
        """
        return self._Pcu23

    @Pcu23.setter
    def Pcu23(self, value: float) -> None:
        self._Pcu23 = value
        self._recalc_from_definition(Sbase=100)

    # Property for _Pcu31
    @property
    def Pcu31(self) -> float:
        """

        :return:
        """
        return self._Pcu31

    @Pcu31.setter
    def Pcu31(self, value: float) -> None:
        self._Pcu31 = value
        self._recalc_from_definition(Sbase=100)

    # Property for _Vsc12
    @property
    def Vsc12(self) -> float:
        """

        :return:
        """
        return self._Vsc12

    @Vsc12.setter
    def Vsc12(self, value: float) -> None:
        self._Vsc12 = value
        self._recalc_from_definition(Sbase=100)

    # Property for _Vsc23
    @property
    def Vsc23(self) -> float:
        """

        :return:
        """
        return self._Vsc23

    @Vsc23.setter
    def Vsc23(self, value: float) -> None:
        self._Vsc23 = value
        self._recalc_from_definition(Sbase=100)

    # Property for _Vsc31
    @property
    def Vsc31(self) -> float:
        """

        :return:
        """
        return self._Vsc31

    @Vsc31.setter
    def Vsc31(self, value: float) -> None:
        self._Vsc31 = value
        self._recalc_from_definition(Sbase=100)

    # Property for _Pfe
    @property
    def Pfe(self) -> float:
        """

        :return:
        """
        return self._Pfe

    @Pfe.setter
    def Pfe(self, value: float) -> None:
        self._Pfe = value
        self._recalc_from_definition(Sbase=100)

    # Property for _I0
    @property
    def I0(self) -> float:
        """

        :return:
        """
        return self._I0

    @I0.setter
    def I0(self, value: float) -> None:
        self._I0 = value
        self._recalc_from_definition(Sbase=100)

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

    def _recalc_from_definition(self, Sbase: float):
        """
        Recompute from the definition stored data
        :param Sbase:
        :return:
        """
        z_series12, y_shunt12 = get_impedances(VH_bus=max(self.bus1.Vnom, self.bus2.Vnom),
                                               VL_bus=max(self.bus1.Vnom, self.bus2.Vnom),
                                               Sn=self.rate1,
                                               HV=max(self.V1, self.V2),
                                               LV=min(self.V1, self.V2),
                                               Pcu=self.Pcu12,
                                               Pfe=self.Pfe,
                                               I0=self.I0,
                                               Vsc=self.Vsc12,
                                               Sbase=Sbase,
                                               GR_hv1=0.5)

        z_series23, y_shunt23 = get_impedances(VH_bus=max(self.bus2.Vnom, self.bus3.Vnom),
                                               VL_bus=max(self.bus2.Vnom, self.bus3.Vnom),
                                               Sn=self.rate2,
                                               HV=max(self.V2, self.V3),
                                               LV=min(self.V2, self.V3),
                                               Pcu=self.Pcu23,
                                               Pfe=self.Pfe,
                                               I0=self.I0,
                                               Vsc=self.Vsc23,
                                               Sbase=Sbase,
                                               GR_hv1=0.5)

        z_series31, y_shunt31 = get_impedances(VH_bus=max(self.bus3.Vnom, self.bus1.Vnom),
                                               VL_bus=max(self.bus3.Vnom, self.bus1.Vnom),
                                               Sn=self.rate3,
                                               HV=max(self.V3, self.V1),
                                               LV=min(self.V3, self.V1),
                                               Pcu=self.Pcu31,
                                               Pfe=self.Pfe,
                                               I0=self.I0,
                                               Vsc=self.Vsc31,
                                               Sbase=Sbase,
                                               GR_hv1=0.5)

        self._r12 = np.round(z_series12.real, 6)
        self._r23 = np.round(z_series23.real, 6)
        self._r31 = np.round(z_series31.real, 6)

        self._x12 = np.round(z_series12.imag, 6)
        self._x23 = np.round(z_series23.imag, 6)
        self._x31 = np.round(z_series31.imag, 6)

        self.compute_delta_to_star()

    def fill_from_design_values(self, V1: float, V2: float, V3: float,
                                Sn1: float, Sn2: float, Sn3: float,
                                Pcu12: float, Pcu23: float, Pcu31: float,
                                Vsc12: float, Vsc23: float, Vsc31: float,
                                Pfe: float, I0: float, Sbase: float, ):
        """
        Fill winding per unit impedances from the short circuit study values
        :param V1: Primary voltage (KV)
        :param V2: Secondary voltage (KV)
        :param V3: Tertiary Voltage (KV)
        :param Sn1: Primary power (MVA)
        :param Sn2: Secondary power (MVA)
        :param Sn3: Tertiary power (MVA)
        :param Pcu12: Pcu 1-2(kW)
        :param Pcu23: Pcu 2-3(kW)
        :param Pcu31: Pcu 3-1(kW)
        :param Vsc12: Vsc 1-2(%)
        :param Vsc23: Vsc 2-3(%)
        :param Vsc31: Vsc 3-1(%)
        :param Pfe: Pfe(kW)
        :param I0: I0(%)
        :param Sbase: base power
        :return:
        """

        self._V1 = float(V1)
        self._V2 = float(V2)
        self._V3 = float(V3)

        self._Pcu12: float = Pcu12
        self._Pcu23: float = Pcu23
        self._Pcu31: float = Pcu31

        self._Vsc12: float = Vsc12
        self._Vsc23: float = Vsc23
        self._Vsc31: float = Vsc31

        self._Pfe: float = Pfe
        self._I0: float = I0

        self._rate1 = Sn1
        self._rate2 = Sn2
        self._rate3 = Sn3

        self._recalc_from_definition(Sbase)
