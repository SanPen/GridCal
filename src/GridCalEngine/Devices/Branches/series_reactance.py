# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import Union
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import BuildStatus, DeviceType
from GridCalEngine.Devices.Parents.branch_parent import BranchParent
from GridCalEngine.Devices.profile import Profile


class SeriesReactance(BranchParent):
    __slots__ = (
        'tolerance',
        'r_fault',
        'x_fault',
        'fault_pos',
        'R',
        'X',
        'R0',
        'X0',
        'R2',
        'X2',
        'temp_base',
        'temp_oper',
        '_temp_oper_prof',
        'alpha',
    )

    def __init__(self,
                 bus_from: Bus = None,
                 bus_to: Bus = None,
                 name='SeriesReactance',
                 idtag=None, code='',
                 r=1e-20, x=1e-20, rate=1.0,
                 active=True,
                 tolerance=0,
                 cost=100.0,
                 mttf=0, mttr=0,
                 r_fault=0.0, x_fault=0.0,
                 fault_pos=0.5,
                 temp_base=20, temp_oper=20, alpha=0.00330,
                 contingency_factor=1.0, protection_rating_factor: float = 1.4,
                 contingency_enabled=True, monitor_loading=True,
                 r0=1e-20, x0=1e-20,  r2=1e-20, x2=1e-20,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """
        AC current Line
        :param bus_from: "From" :ref:`bus<Bus>` object
        :param bus_to: "To" :ref:`bus<Bus>` object
        :param name: Name of the branch
        :param idtag: UUID code
        :param code: secondary ID
        :param r: Branch resistance in per unit
        :param x: Branch reactance in per unit
        :param rate: Branch rate in MVA
        :param active: Is the branch active?
        :param tolerance: Tolerance specified for the branch impedance in %
        :param cost: overload cost
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        :param r_fault: Mid-line fault resistance in per unit (SC only)
        :param x_fault: Mid-line fault reactance in per unit (SC only)
        :param fault_pos: Mid-line fault position in per unit (0.0 = `bus_from`, 0.5 = middle, 1.0 = `bus_to`)
        :param temp_base: Base temperature at which `r` is measured in °C
        :param temp_oper: Operating temperature in °C
        :param alpha: Thermal constant of the material in °C
        :param contingency_factor: Rating factor in case of contingency
        :param protection_rating_factor: Rating factor before the protections tripping
        :param contingency_enabled: enabled for contingencies (Legacy)
        :param monitor_loading: monitor the loading (used in OPF)
        :param r0: zero-sequence resistence (p.u.)
        :param x0: zero-sequence reactance (p.u.)
        :param r2: negative-sequence resistence (p.u.)
        :param x2: negative-sequence reactance (p.u.)
        :param capex: Cost of investment (e/MW)
        :param opex: Cost of operation (e/MWh)
        :param build_status: build status (now time)
        """

        BranchParent.__init__(self,
                              name=name,
                              idtag=idtag,
                              code=code,
                              bus_from=bus_from,
                              bus_to=bus_to,
                              active=active,
                              reducible=False,
                              rate=rate,
                              contingency_factor=contingency_factor,
                              protection_rating_factor=protection_rating_factor,
                              contingency_enabled=contingency_enabled,
                              monitor_loading=monitor_loading,
                              mttf=mttf,
                              mttr=mttr,
                              build_status=build_status,
                              capex=capex,
                              opex=opex,
                              cost=cost,
                              device_type=DeviceType.SeriesReactanceDevice)

        # line impedance tolerance
        self.tolerance = tolerance

        # short circuit impedance
        self.r_fault = r_fault
        self.x_fault = x_fault
        self.fault_pos = fault_pos

        # total impedance and admittance in p.u.
        self.R = r
        self.X = x

        self.R0 = r0
        self.X0 = x0

        self.R2 = r2
        self.X2 = x2

        # Conductor base and operating temperatures in ºC
        self.temp_base = temp_base
        self.temp_oper = temp_oper
        self._temp_oper_prof = Profile(default_value=temp_oper, data_type=float)

        # Conductor thermal constant (1/ºC)
        self.alpha = alpha

        self.register(key='R', units='p.u.', tpe=float, definition='Total positive sequence resistance.')
        self.register(key='X', units='p.u.', tpe=float, definition='Total positive sequence reactance.')

        self.register(key='R0', units='p.u.', tpe=float, definition='Total zero sequence resistance.')
        self.register(key='X0', units='p.u.', tpe=float, definition='Total zero sequence reactance.')

        self.register(key='R2', units='p.u.', tpe=float, definition='Total negative sequence resistance.')
        self.register(key='X2', units='p.u.', tpe=float, definition='Total negative sequence reactance.')

        self.register(key='tolerance', units='%', tpe=float,
                      definition='Tolerance expected for the impedance values % is expected '
                                 'for transformers0% for lines.')

        self.register(key='temp_base', units='ºC', tpe=float, definition='Base temperature at which R was measured.')
        self.register(key='temp_oper', units='ºC', tpe=float, definition='Operation temperature to modify R.',
                      profile_name='temp_oper_prof')
        self.register(key='alpha', units='1/ºC', tpe=float,
                      definition='Thermal coefficient to modify R,around a reference temperatureusing a '
                                 'linear approximation.For example:Copper @ 20ºC: 0.004041,Copper @ 75ºC: 0.00323,'
                                 'Annealed copper @ 20ºC: 0.00393,Aluminum @ 20ºC: 0.004308,Aluminum @ 75ºC: 0.00330')
        self.register(key='r_fault', units='p.u.', tpe=float,
                      definition='Resistance of the mid-line fault.Used in short circuit studies.')
        self.register(key='x_fault', units='p.u.', tpe=float,
                      definition='Reactance of the mid-line fault.Used in short circuit studies.')
        self.register(key='fault_pos', units='p.u.', tpe=float,
                      definition='Per-unit positioning of the fault:'
                                 '0 would be at the "from" side,'
                                 '1 would be at the "to" side,'
                                 'therefore 0.5 is at the middle.')

    @property
    def temp_oper_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._temp_oper_prof

    @temp_oper_prof.setter
    def temp_oper_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._temp_oper_prof = val
        elif isinstance(val, np.ndarray):
            self._temp_oper_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a temp_oper_prof')

    @property
    def R_corrected(self):
        """
        Returns a temperature corrected resistance based on a formula provided by:
        NFPA 70-2005, National Electrical Code, Table 8, footnote #2; and
        https://en.wikipedia.org/wiki/Electrical_resistivity_and_conductivity#Linear_approximation
        (version of 2019-01-03 at 15:20 EST).
        """
        return self.R * (1 + self.alpha * (self.temp_oper - self.temp_base))

    def change_base(self, Sbase_old, Sbase_new):
        """
        Change the impedance base
        :param Sbase_old: old base (MVA)
        :param Sbase_new: new base (MVA)
        """
        b = Sbase_new / Sbase_old

        self.R *= b
        self.X *= b

    def get_weight(self) -> float:
        """
        Get a weight of this line for graph purposes
        the weight is the impedance module (sqrt(r^2 + x^2))
        :return: weight value
        """
        return np.sqrt(self.R * self.R + self.X * self.X)

    def fix_inconsistencies(self, logger: Logger):
        """
        Fix the inconsistencies
        :param logger:
        :return:
        """
        errors = False

        if self.R < 0.0:
            logger.add_warning("Corrected transformer R<0", self.name, self.R, -self.R)
            self.R = -self.R
            errors = True

        return errors

    def fill_design_properties(self, r_ohm, x_ohm, length, Imax, Sbase):
        """
        Fill R, X, B from not-in-per-unit parameters
        :param r_ohm: Resistance per km in OHM
        :param x_ohm: Reactance per km in OHM
        :param length: length in kn
        :param Imax: Maximum current in kA
        :param Sbase: Base power in MVA (take always 100 MVA)
        """
        R = r_ohm * length
        X = x_ohm * length
        Vf = self.get_max_bus_nominal_voltage()

        Zbase = (Vf * Vf) / Sbase

        self.R = np.round(R / Zbase, 6)
        self.X = np.round(X / Zbase, 6)
        self.rate = np.round(Imax * Vf * 1.73205080757, 6)  # nominal power in MVA = kA * kV * sqrt(3)

