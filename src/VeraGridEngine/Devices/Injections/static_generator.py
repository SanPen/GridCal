# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0


from typing import Tuple

from VeraGridEngine.enumerations import (BuildStatus, DeviceType, PrpCat, ParamPowerFlowReferenceType,
                                         StaticGeneratorControlMode)
from VeraGridEngine.Devices.Parents.load_parent import LoadParent
from VeraGridEngine.Devices.Parents.editable_device import GCProp


class StaticGenerator(LoadParent):
    __slots__ = ("_Snom", "_control_mode", "_Vset", "_droop", "_Vset_min", "_Vset_max",
                 "_R0", "_X0", "_R2", "_X2")

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(prop_name='R0', units='p.u.', tpe=float,
               definition='Zero-sequence resistance on the system base; used by grounded sequence injections.',
               cat=[PrpCat.PF3]),
        GCProp(prop_name='X0', units='p.u.', tpe=float,
               definition='Zero-sequence reactance on the system base; used by grounded sequence injections.',
               cat=[PrpCat.PF3]),
        GCProp(prop_name='R2', units='p.u.', tpe=float,
               definition='Negative-sequence resistance on the system base. R2=X2=0 omits the passive response.',
               cat=[PrpCat.PF3]),
        GCProp(prop_name='X2', units='p.u.', tpe=float,
               definition='Negative-sequence reactance on the system base. R2=X2=0 omits the passive response.',
               cat=[PrpCat.PF3]),
        GCProp(
            prop_name='Snom',
            units='MVA',
            tpe=float,
            definition='Nominal power.',
            cat=[PrpCat.OPF, PrpCat.PF, PrpCat.PF3],
            dyn_ref=ParamPowerFlowReferenceType.static_generator_snom_mva,
        ),
        GCProp(prop_name='control_mode', tpe=StaticGeneratorControlMode, units='',
               definition='Fixed P/Q or the VSC Q-V droop law; ABC control uses positive-sequence voltage.',
               cat=[PrpCat.PF, PrpCat.PF3]),
        GCProp(prop_name='Vset', tpe=float, units='p.u.', definition='Droop voltage reference.',
               cat=[PrpCat.PF, PrpCat.PF3]),
        GCProp(prop_name='droop', tpe=float, units='%',
               definition='Voltage droop on Snom; must be positive in Q-V droop mode.', cat=[PrpCat.PF, PrpCat.PF3]),
        GCProp(prop_name='Vset_min', tpe=float, units='p.u.',
               definition='Lower clamp on the voltage used by the droop curve.', cat=[PrpCat.PF, PrpCat.PF3]),
        GCProp(prop_name='Vset_max', tpe=float, units='p.u.',
               definition='Upper clamp on the voltage used by the droop curve.', cat=[PrpCat.PF, PrpCat.PF3]),
    )

    def __init__(self, name: str = 'StaticGen', idtag: str | None = None, code: str = '',
                 P: float = 0.0, Q: float = 0.0, active: bool = True,
                 P1: float = 0.0, P2: float = 0.0, P3: float = 0.0,
                 Q1: float = 0.0, Q2: float = 0.0, Q3: float = 0.0,
                 mttf: float = 0.0, mttr: float = 0.0, Cost: float = 1200.0, Snom: float = 0,
                 capex: float = 0, opex: float = 0, build_status: BuildStatus = BuildStatus.Commissioned,
                 control_mode: StaticGeneratorControlMode = StaticGeneratorControlMode.PQ,
                 vset: float = 1.0, droop: float = 3.0,
                 vset_min: float = 0.9, vset_max: float = 1.1,
                 r0: float = 0.0, x0: float = 0.0, r2: float = 0.0, x2: float = 0.0) -> None:
        """

        :param name:
        :param idtag:
        :param code:
        :param P:
        :param P1:
        :param P2:
        :param P3:
        :param Q:
        :param Q1:
        :param Q2:
        :param Q3:
        :param active:
        :param mttf:
        :param mttr:
        :param Cost:
        :param Snom: Nominal power in MVA, used as the Q-V droop base.
        :param capex:
        :param opex:
        :param build_status:
        :param control_mode: Fixed P/Q by default; optional VSC-equivalent Q-V droop.
        :param vset: Voltage reference in pu, positive sequence in ABC.
        :param droop: Voltage droop in percent on Snom.
        :param vset_min: Lower measured-voltage clamp in pu.
        :param vset_max: Upper measured-voltage clamp in pu.
        :param r0: Zero-sequence resistance on the system base.
        :param x0: Zero-sequence reactance on the system base.
        :param r2: Negative-sequence resistance on the system base.
        :param x2: Negative-sequence reactance on the system base.
        """

        LoadParent.__init__(self,
                            name=name,
                            idtag=idtag,
                            code=code,
                            bus=None,
                            active=active,
                            P=P,
                            P1=P1,
                            P2=P2,
                            P3=P3,
                            Q=Q,
                            Q1=Q1,
                            Q2=Q2,
                            Q3=Q3,
                            Cost=Cost,
                            mttf=mttf,
                            mttr=mttr,
                            capex=capex,
                            opex=opex,
                            build_status=build_status,
                            device_type=DeviceType.StaticGeneratorDevice)

        # Nominal power in MVA (also the machine base)
        self._Snom = float(Snom)
        self._control_mode: StaticGeneratorControlMode = control_mode
        self._Vset: float = float(vset)
        self._droop: float = float(droop)
        self._Vset_min: float = float(vset_min)
        self._Vset_max: float = float(vset_max)
        self._R0: float = float(r0)
        self._X0: float = float(x0)
        self._R2: float = float(r2)
        self._X2: float = float(x2)

    @property
    def R0(self) -> float:
        """Read zero-sequence resistance.

        :return: Resistance on the system base, pu.
        """
        return self._R0

    @R0.setter
    def R0(self, value: float) -> None:
        """Set zero-sequence resistance.

        :param value: Resistance on the system base, pu.
        """
        self._R0 = float(value)

    @property
    def X0(self) -> float:
        """Read zero-sequence reactance.

        :return: Reactance on the system base, pu.
        """
        return self._X0

    @X0.setter
    def X0(self, value: float) -> None:
        """Set zero-sequence reactance.

        :param value: Reactance on the system base, pu.
        """
        self._X0 = float(value)

    @property
    def R2(self) -> float:
        """Read negative-sequence resistance.

        :return: Resistance on the system base, pu.
        """
        return self._R2

    @R2.setter
    def R2(self, value: float) -> None:
        """Set negative-sequence resistance.

        :param value: Resistance on the system base, pu.
        """
        self._R2 = float(value)

    @property
    def X2(self) -> float:
        """Read negative-sequence reactance.

        :return: Reactance on the system base, pu.
        """
        return self._X2

    @X2.setter
    def X2(self, value: float) -> None:
        """Set negative-sequence reactance.

        :param value: Reactance on the system base, pu.
        """
        self._X2 = float(value)

    @property
    def control_mode(self) -> StaticGeneratorControlMode:
        """Read the control objective.

        :return: Reactive-power control mode.
        """
        return self._control_mode

    @control_mode.setter
    def control_mode(self, value: StaticGeneratorControlMode) -> None:
        """Set the control objective.

        :param value: Reactive-power control mode.
        """
        self._control_mode = StaticGeneratorControlMode(value)

    @property
    def Vset(self) -> float:
        """Read the voltage reference.

        :return: Reference in pu.
        """
        return self._Vset

    @Vset.setter
    def Vset(self, value: float) -> None:
        """Set the voltage reference.

        :param value: Reference in pu.
        """
        self._Vset = float(value)

    @property
    def droop(self) -> float:
        """Read the droop on the device rating.

        :return: Droop in percent.
        """
        return self._droop

    @droop.setter
    def droop(self, value: float) -> None:
        """Set the droop on the device rating.

        :param value: Droop in percent.
        """
        self._droop = float(value)

    @property
    def Vset_min(self) -> float:
        """Read the measured-voltage lower clamp.

        :return: Lower clamp in pu.
        """
        return self._Vset_min

    @Vset_min.setter
    def Vset_min(self, value: float) -> None:
        """Set the measured-voltage lower clamp.

        :param value: Lower clamp in pu.
        """
        self._Vset_min = float(value)

    @property
    def Vset_max(self) -> float:
        """Read the measured-voltage upper clamp.

        :return: Upper clamp in pu.
        """
        return self._Vset_max

    @Vset_max.setter
    def Vset_max(self, value: float) -> None:
        """Set the measured-voltage upper clamp.

        :param value: Upper clamp in pu.
        """
        self._Vset_max = float(value)

    @property
    def Snom(self):
        """
        Return the reactive power lower limit
        :return: value
        """
        return self._Snom

    @Snom.setter
    def Snom(self, val):
        """
        Set the generator nominal power
        if the reactive power curve was generated automatically, then it is refreshed
        :param val: float value
        """
        val = float(val)
        self._Snom = val
