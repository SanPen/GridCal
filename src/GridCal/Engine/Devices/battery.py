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


from warnings import warn
import pandas as pd
import numpy as np
from GridCal.Engine.Devices.editable_device import DeviceType, GCProp
from GridCal.Engine.Devices.generator import Generator


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

        **op_cost** (float, 1.0): Operational cost in Eur (or other currency) per MW

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

    def __init__(self, name='batt', idtag=None, active_power=0.0, power_factor=0.8, voltage_module=1.0,
                 is_controlled=True, Qmin=-9999, Qmax=9999, Snom=9999, Enom=9999, p_min=-9999, p_max=9999,
                 op_cost=1.0, power_prof=None, power_factor_prof=None, vset_prof=None, active=True, Sbase=100,
                 enabled_dispatch=True, mttf=0.0, mttr=0.0, charge_efficiency=0.9, discharge_efficiency=0.9,
                 max_soc=0.99, min_soc=0.3, soc=0.8, charge_per_cycle=0.1, discharge_per_cycle=0.1):

        Generator.__init__(self, name=name,
                           idtag=idtag,
                           active_power=active_power,
                           power_factor=power_factor,
                           voltage_module=voltage_module,
                           is_controlled=is_controlled,
                           Qmin=Qmin, Qmax=Qmax, Snom=Snom,
                           power_prof=power_prof,
                           power_factor_prof=power_factor_prof,
                           vset_prof=vset_prof,
                           active=active,
                           p_min=p_min, p_max=p_max,
                           op_cost=op_cost,
                           Sbase=Sbase,
                           enabled_dispatch=enabled_dispatch,
                           mttf=mttf,
                           mttr=mttr)

        # type of this device
        self.device_type = DeviceType.BatteryDevice

        # manually modify the editable headers
        self.editable_headers = {'name': GCProp('', str, 'Name of the battery'),
                                 'idtag': GCProp('', str, 'Unique ID'),
                                 'bus': GCProp('', DeviceType.BusDevice, 'Connection bus name'),
                                 'active': GCProp('', bool, 'Is the battery active?'),
                                 'is_controlled': GCProp('', bool, 'Is this battery voltage-controlled?'),
                                 'P': GCProp('MW', float, 'Active power'),
                                 'Pf': GCProp('', float,
                                              'Power factor (cos(fi)). This is used for non-controlled batteries.'),
                                 'Vset': GCProp('p.u.', float, 'Set voltage. This is used for controlled batteries.'),
                                 'Snom': GCProp('MVA', float, 'Nomnial power.'),
                                 'Enom': GCProp('MWh', float, 'Nominal energy capacity.'),
                                 'max_soc': GCProp('p.u.', float, 'Minimum state of charge.'),
                                 'min_soc': GCProp('p.u.', float, 'Maximum state of charge.'),
                                 'soc_0': GCProp('p.u.', float, 'Initial state of charge.'),
                                 'charge_efficiency': GCProp('p.u.', float, 'Charging efficiency.'),
                                 'discharge_efficiency': GCProp('p.u.', float, 'Discharge efficiency.'),
                                 'discharge_per_cycle': GCProp('p.u.', float, ''),
                                 'Qmin': GCProp('MVAr', float, 'Minimum reactive power.'),
                                 'Qmax': GCProp('MVAr', float, 'Maximum reactive power.'),
                                 'Pmin': GCProp('MW', float, 'Minimum active power. Used in OPF.'),
                                 'Pmax': GCProp('MW', float, 'Maximum active power. Used in OPF.'),
                                 'Cost': GCProp('e/MWh', float, 'Generation unitary cost. Used in OPF.'),
                                 'enabled_dispatch': GCProp('', bool, 'Enabled for dispatch? Used in OPF.'),
                                 'mttf': GCProp('h', float, 'Mean time to failure'),
                                 'mttr': GCProp('h', float, 'Mean time to recovery')}

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

    def copy(self):
        """
        Make a copy of this object
        Returns: :ref:`Battery<battery>` instance
        """

        # create a new instance of the battery
        batt = Battery()

        batt.name = self.name

        # Power (MVA)
        # MVA = kV * kA
        batt.P = self.P

        batt.Pmax = self.Pmax

        batt.Pmin = self.Pmin

        # power profile for this load
        batt.P_prof = self.P_prof

        # Voltage module set point (p.u.)
        batt.Vset = self.Vset

        # voltage set profile for this load
        batt.Vset_prof = self.Vset_prof

        # minimum reactive power in per unit
        batt.Qmin = self.Qmin

        # Maximum reactive power in per unit
        batt.Qmax = self.Qmax

        # Nominal power MVA
        batt.Snom = self.Snom

        # Nominal energy MWh
        batt.Enom = self.Enom

        # Enable for active power dispatch?
        batt.enabled_dispatch = self.enabled_dispatch

        batt.mttf = self.mttf

        batt.mttr = self.mttr

        batt.charge_efficiency = self.charge_efficiency

        batt.discharge_efficiency = self.discharge_efficiency

        batt.max_soc = self.max_soc

        batt.min_soc = self.min_soc

        batt.min_soc_charge = self.min_soc_charge  # SoC state to force the battery charge

        batt.charge_per_cycle = self.charge_per_cycle  # charge 10% per cycle

        batt.discharge_per_cycle = self.discharge_per_cycle

        batt.min_energy = self.min_energy

        batt.soc_0 = self.soc

        batt.soc = self.soc

        batt.energy = self.energy

        batt.energy_array = self.energy_array

        batt.power_array = self.power_array

        return batt

    def get_properties_dict(self):
        """
        Get json dictionary
        :return: json-compatible dictionary
        """

        data = {'id': self.idtag,
                'type': 'battery',
                'phases': 'ps',
                'name': self.name,
                'name_code': self.code,
                'bus': self.bus.idtag,
                'active': self.active,

                'p': self.P,
                'vset': self.Vset,
                'pf': self.Pf,
                'snom': self.Snom,
                'enom': self.Enom,
                'qmin': self.Qmin,
                'qmax': self.Qmax,
                'pmin': self.Pmin,
                'pmax': self.Pmax,
                'cost': self.Cost,
                'charge_efficiency': self.charge_efficiency,
                'discharge_efficiency': self.discharge_efficiency,
                'min_soc': self.min_soc,
                'max_soc': self.max_soc,
                'soc_0': self.soc_0,
                'min_soc_charge': self.min_soc_charge,
                'charge_per_cycle': self.charge_per_cycle,
                'discharge_per_cycle': self.discharge_per_cycle,
                'technology': ""
                }

        return data

    def get_profiles_dict(self):
        """

        :return:
        """

        if self.active_prof is None:
            active_prof = list()
        else:
            active_prof = self.active_prof.tolist()

        if self.P_prof is None:
            P_prof = list()
        else:
            P_prof = self.P_prof.tolist()

        if self.Pf_prof is None:
            Pf_prof = list()
        else:
            Pf_prof = self.Pf_prof.tolist()

        if self.Vset_prof is None:
            Vset_prof = list()
        else:
            Vset_prof = self.Vset_prof.tolist()

        return {'id': self.idtag,
                'active': active_prof,
                'p': P_prof,
                'v': Vset_prof,
                'pf': Pf_prof
                }

    def get_units_dict(self):
        """
        Get units of the values
        """
        return {'p': 'MW',
                'vset': 'p.u.',
                'pf': 'p.u.',
                'snom': 'MVA',
                'enom': 'MWh',
                'qmin': 'MVAr',
                'qmax': 'MVAr',
                'pmin': 'MW',
                'pmax': 'MW',
                'cost': '€/MWh',
                'charge_efficiency': 'p.u.',
                'discharge_efficiency': 'p.u.',
                'min_soc': 'p.u.',
                'max_soc': 'p.u.',
                'soc_0': 'p.u.',
                'min_soc_charge': 'p.u.',
                'charge_per_cycle': 'p.u.',
                'discharge_per_cycle': 'p.u.'}

    def initialize_arrays(self, index, arr=None, arr_in_pu=False):
        """
        Create power profile based on index
        :param index: time index associated
        :param arr: array of values
        :param arr_in_pu: is the array in per unit?
        """
        if arr_in_pu:
            dta = arr * self.P
        else:
            dta = np.ones(len(index)) * self.P if arr is None else arr
        self.power_array = pd.DataFrame(data=dta.copy(), index=index, columns=[self.name])
        self.energy_array = pd.DataFrame(data=dta.copy(), index=index, columns=[self.name])

    def reset(self):
        """
        Set the battery to its initial state
        """
        self.soc = self.soc_0
        self.energy = self.Enom * self.soc
        self.power_array = self.P_prof.copy()
        self.energy_array = self.P_prof.copy()

    def process(self, P, dt, charge_if_needed=False):
        """
        process a cycle in the battery
        :param P: proposed power in MW
        :param dt: time increment in hours
        :param charge_if_needed: True / False
        :return: Amount of power actually processed in MW
        """

        # if self.Enom is None:
        #     raise Exception('You need to set the battery nominal power!')

        if np.isnan(P):
            warn('NaN found!!!!!!')

        # pick the right efficiency value
        if P >= 0.0:
            eff = self.discharge_efficiency
            # energy_per_cycle = self.nominal_energy * self.discharge_per_cycle
        else:
            eff = self.charge_efficiency

        # amount of energy that the battery can take in a cycle of 1 hour
        energy_per_cycle = self.Enom * self.charge_per_cycle

        # compute the proposed energy. Later we check how much is actually possible
        proposed_energy = self.energy - P * dt * eff

        # charge the battery from the grid if the SoC is too low and we are allowing this behaviour
        if charge_if_needed and self.soc < self.min_soc_charge:
            proposed_energy -= energy_per_cycle / dt  # negative is for charging

        # Check the proposed energy
        if proposed_energy > self.Enom * self.max_soc:  # Truncated, too high

            energy_new = self.Enom * self.max_soc
            power_new = (self.energy - energy_new) / (dt * eff)

        elif proposed_energy < self.Enom * self.min_soc:  # Truncated, too low

            energy_new = self.Enom * self.min_soc
            power_new = (self.energy - energy_new) / (dt * eff)

        else:  # everything is within boundaries

            energy_new = proposed_energy
            power_new = P

        # Update the state of charge and the energy state
        self.soc = energy_new / self.Enom
        self.energy = energy_new

        return power_new, self.energy

    def get_processed_at(self, t, dt, store_values=True):
        """
        Get the processed power at the time index t
        :param t: time index
        :param dt: time step in hours
        :param store_values: store the values?
        :return: active power processed by the battery control in MW
        """
        power_value = self.P_prof[t]

        processed_power, processed_energy = self.process(power_value, dt)

        if store_values:
            self.energy_array[t] = processed_energy
            self.power_array[t] = processed_power

        return processed_power

