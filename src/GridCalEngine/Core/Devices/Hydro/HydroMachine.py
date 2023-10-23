# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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


from warnings import warn
import pandas as pd
import numpy as np
from GridCalEngine.Core.Devices.editable_device import DeviceType, GCProp
from GridCalEngine.Core.Devices.Injections.generator import Generator, BuildStatus


class HydroMachine(Generator):


    def __init__(self, name='batt', idtag=None, P=0.0, power_factor=0.8, vset=1.0,
                 is_controlled=True, Qmin=-9999, Qmax=9999, Snom=9999, Enom=9999, Pmin=-9999, Pmax=9999,
                 Cost=1.0, P_prof=None, power_factor_prof=None, vset_prof=None, active=True, Sbase=100,
                 enabled_dispatch=True, mttf=0.0, mttr=0.0, charge_efficiency=0.9, discharge_efficiency=0.9,
                 max_soc=0.99, min_soc=0.3, soc=0.8, charge_per_cycle=0.1, discharge_per_cycle=0.1,
                 r1=1e-20, x1=1e-20, r0=1e-20, x0=1e-20, r2=1e-20, x2=1e-20,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):

        Generator.__init__(self, name=name,
                           idtag=idtag,
                           P=P,
                           power_factor=power_factor,
                           vset=vset,
                           is_controlled=is_controlled,
                           Qmin=Qmin, Qmax=Qmax, Snom=Snom,
                           P_prof=P_prof,
                           power_factor_prof=power_factor_prof,
                           vset_prof=vset_prof,
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
                           build_status=build_status)

        # type of this device
        self.device_type = DeviceType.HydroMachine

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

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return: json-compatible dictionary
        """
        if version == 2:
            return {'id': self.idtag,
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
        elif version == 3:
            return {'id': self.idtag,
                    'type': 'battery',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus': self.bus.idtag,
                    'active': self.active,
                    'is_controlled': self.is_controlled,
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

                    'cost2': self.Cost2,
                    'cost1': self.Cost,
                    'cost0': self.Cost0,

                    'startup_cost': self.StartupCost,
                    'shutdown_cost': self.ShutdownCost,
                    'min_time_up': self.MinTimeUp,
                    'min_time_down': self.MinTimeDown,
                    'ramp_up': self.RampUp,
                    'ramp_down': self.RampDown,

                    'capex': self.capex,
                    'opex': self.opex,
                    'build_status': str(self.build_status.value).lower(),
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
        else:
            return dict()

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


