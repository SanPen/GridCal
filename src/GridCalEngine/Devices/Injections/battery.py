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


from GridCalEngine.Devices.Parents.editable_device import DeviceType
from GridCalEngine.Devices.Injections.generator import Generator, BuildStatus


class Battery(Generator):
    """
    :ref:`Battery<battery>` (voltage controlled and dispatchable).

    Arguments:

        **name** (str, "batt"): Name of the battery

        **active_power** (float, 0.0): Active power in MW

        **power_factor** (float, 0.8): Power factor

        **voltage_module** (float, 1.0): Voltage setpoint in per unit

        **is_controlled** (bool, True): Is the unit voltage controlled (if so, the
        connection bus becomes a PV bus)

        **Qmin** (float, -9999): Minimum reactive power in MVAr

        **Qmax** (float, 9999): Maximum reactive power in MVAr

        **Snom** (float, 9999): Nominal apparent power in MVA

        **Enom** (float, 9999): Nominal energy capacity in MWh

        **p_min** (float, -9999): Minimum dispatchable power in MW

        **p_max** (float, 9999): Maximum dispatchable power in MW

        **op_cost** (float, 1.0): Operational cost in Eur (or other e) per MW

        **power_prof** (DataFrame, None): Pandas DataFrame with the active power
        profile in MW

        **power_factor_prof** (DataFrame, None): Pandas DataFrame with the power factor profile

        **vset_prof** (DataFrame, None): Pandas DataFrame with the voltage setpoint
        profile in per unit

        **active** (bool, True): Is the battery active?

        **Sbase** (float, 100): Base apparent power in MVA

        **enabled_dispatch** (bool, True): Is the battery enabled for OPF?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

        **charge_efficiency** (float, 0.9): Efficiency when charging

        **discharge_efficiency** (float, 0.9): Efficiency when discharging

        **max_soc** (float, 0.99): Maximum state of charge

        **min_soc** (float, 0.3): Minimum state of charge

        **soc** (float, 0.8): Current state of charge

        **charge_per_cycle** (float, 0.1): Per unit of power to take per cycle when charging

        **discharge_per_cycle** (float, 0.1): Per unit of power to deliver per cycle
        when discharging

    """

    def __init__(self, name='batt', idtag=None, P=0.0, power_factor=0.8, vset=1.0,
                 is_controlled=True, Qmin=-9999, Qmax=9999, Snom=9999, Enom=9999, Pmin=-9999, Pmax=9999,
                 Cost=1.0, active=True, Sbase=100,
                 enabled_dispatch=True, mttf=0.0, mttr=0.0, charge_efficiency=0.9, discharge_efficiency=0.9,
                 max_soc=0.99, min_soc=0.3, soc=0.8, charge_per_cycle=0.1, discharge_per_cycle=0.1,
                 r1=1e-20, x1=1e-20, r0=1e-20, x0=1e-20, r2=1e-20, x2=1e-20,
                 capex=0, opex=0,
                 srap_enabled: bool = True,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """

        :param name:
        :param idtag:
        :param P:
        :param power_factor:
        :param vset:
        :param is_controlled:
        :param Qmin:
        :param Qmax:
        :param Snom:
        :param Enom:
        :param Pmin:
        :param Pmax:
        :param Cost:
        :param active:
        :param Sbase:
        :param enabled_dispatch:
        :param mttf:
        :param mttr:
        :param charge_efficiency:
        :param discharge_efficiency:
        :param max_soc:
        :param min_soc:
        :param soc:
        :param charge_per_cycle:
        :param discharge_per_cycle:
        :param r1:
        :param x1:
        :param r0:
        :param x0:
        :param r2:
        :param x2:
        :param capex:
        :param opex:
        :param build_status:
        """
        Generator.__init__(self, name=name,
                           idtag=idtag,
                           P=P,
                           power_factor=power_factor,
                           vset=vset,
                           is_controlled=is_controlled,
                           Qmin=Qmin, Qmax=Qmax, Snom=Snom,
                           active=active,
                           Pmin=Pmin, Pmax=Pmax,
                           Cost=Cost,
                           Sbase=Sbase,
                           enabled_dispatch=enabled_dispatch,
                           mttf=mttf,
                           mttr=mttr,
                           r1=r1, x1=x1,
                           r0=r0, x0=x0,
                           r2=r2, x2=x2,
                           capex=capex,
                           opex=opex,
                           srap_enabled=srap_enabled,
                           build_status=build_status)

        # type of this device
        self.device_type = DeviceType.BatteryDevice

        self.charge_efficiency = charge_efficiency

        self.discharge_efficiency = discharge_efficiency

        self.max_soc = max_soc

        self.min_soc = min_soc

        self.min_soc_charge = (self.max_soc + self.min_soc) / 2  # SoC state to force the battery charge

        self.charge_per_cycle = charge_per_cycle  # charge 10% per cycle

        self.discharge_per_cycle = discharge_per_cycle

        self.min_energy = Enom * self.min_soc

        self.Enom = Enom

        self.soc_0 = soc

        self.soc = soc

        self.energy = self.Enom * self.soc

        self.energy_array = None

        self.power_array = None

        self.register(key='Enom', units='MWh', tpe=float, definition='Nominal energy capacity.')
        self.register(key='max_soc', units='p.u.', tpe=float, definition='Minimum state of charge.')
        self.register(key='min_soc', units='p.u.', tpe=float, definition='Maximum state of charge.')
        self.register(key='soc_0', units='p.u.', tpe=float, definition='Initial state of charge.')
        self.register(key='charge_efficiency', units='p.u.', tpe=float, definition='Charging efficiency.')
        self.register(key='discharge_efficiency', units='p.u.', tpe=float, definition='Discharge efficiency.')
        self.register(key='discharge_per_cycle', units='p.u.', tpe=float, definition='')
