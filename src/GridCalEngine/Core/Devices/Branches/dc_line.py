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


import pandas as pd
from typing import Union
from matplotlib import pyplot as plt

from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.Core.Devices.Branches.line import LineTemplate
from GridCalEngine.Core.Devices.Branches.templates.parent_branch import ParentBranch
from GridCalEngine.enumerations import DeviceType, BuildStatus


class DcLine(ParentBranch):
    def __init__(self,
                 bus_from: Union[Bus, None] = None,
                 bus_to: Union[Bus, None] = None,
                 name: str = 'Dc Line',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 r=1e-20,
                 rate=1.0,
                 active=True,
                 tolerance=0,
                 cost=0.0,
                 mttf=0,
                 mttr=0,
                 r_fault=0.0,
                 fault_pos=0.5,
                 length=1,
                 temp_base=20,
                 temp_oper=20,
                 alpha=0.00330,
                 template=None,
                 rate_prof=None,
                 Cost_prof=None,
                 active_prof=None,
                 temp_oper_prof=None,
                 contingency_factor=1.0,
                 contingency_enabled=True,
                 monitor_loading=True,
                 contingency_factor_prof=None,
                 capex=0,
                 opex=0,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """
        DC current line
        :param bus_from: Bus from
        :param bus_to: Bus to
        :param name: Name of the branch
        :param idtag: UUID code
        :param code: secondary ID
        :param r: resistance in p.u.
        :param rate: Branch rating (MW)
        :param active: is it active?
        :param tolerance: Tolerance specified for the branch impedance in %
        :param cost: Cost of overload (€/MW)
        :param mttf: Mean time too failure
        :param mttr: Mean time to repair
        :param r_fault: Fault resistance
        :param fault_pos: Fault position
        :param length: Length (km)
        :param temp_base: base temperature (i.e 25º °C)
        :param temp_oper: Operational temperature (°C)
        :param alpha: Thermal constant of the material (°C)
        :param template: Basic branch template
        :param rate_prof: Rating profile
        :param Cost_prof: Overload cost profile
        :param active_prof: Active profile
        :param temp_oper_prof: Operational temperature profile
        :param contingency_factor: Rating factor in case of contingency
        :param contingency_enabled: enabled for contingencies (Legacy)
        :param monitor_loading: monitor the loading (used in OPF)
        :param contingency_factor_prof: profile of contingency ratings
        :param capex: Cost of investment (€/MW)
        :param opex: Cost of operation (€/MWh)
        :param build_status: build status (now time)
        """

        ParentBranch.__init__(self,
                              name=name,
                              idtag=idtag,
                              code=code,
                              bus_from=bus_from,
                              bus_to=bus_to,
                              cn_from=None,
                              cn_to=None,
                              active=active,
                              active_prof=active_prof,
                              rate=rate,
                              rate_prof=rate_prof,
                              contingency_factor=contingency_factor,
                              contingency_factor_prof=contingency_factor_prof,
                              contingency_enabled=contingency_enabled,
                              monitor_loading=monitor_loading,
                              mttf=mttf,
                              mttr=mttr,
                              build_status=build_status,
                              capex=capex,
                              opex=opex,
                              Cost=cost,
                              Cost_prof=Cost_prof,
                              device_type=DeviceType.DCLineDevice)

        # List of measurements
        self.measurements = list()

        # line length in km
        self.length = length

        # line impedance tolerance
        self.tolerance = tolerance

        # short circuit impedance
        self.r_fault = r_fault
        self.fault_pos = fault_pos

        # total impedance and admittance in p.u.
        self.R = r

        # Conductor base and operating temperatures in ºC
        self.temp_base = temp_base
        self.temp_oper = temp_oper

        self.temp_oper_prof = temp_oper_prof

        # Conductor thermal constant (1/ºC)
        self.alpha = alpha

        # type template
        self.template = template

        self.register(key='R', units='p.u.', tpe=float, definition='Total positive sequence resistance.')
        self.register(key='length', units='km', tpe=float, definition='Length of the line (not used for calculation)')
        self.register(key='r_fault', units='p.u.', tpe=float,
                      definition='Resistance of the mid-line fault.Used in short circuit studies.')
        self.register(key='fault_pos', units='p.u.', tpe=float,
                      definition='Per-unit positioning of the fault:0 would be at the "from" side,1 would '
                                 'be at the "to" side,therefore 0.5 is at the middle.')
        self.register(key='template', units='', tpe=DeviceType.SequenceLineDevice, definition='', editable=False)

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

        b = Sbase_new / Sbase_old

        self.R *= b

    def get_weight(self):
        return self.R

    def copy(self, bus_dict=None):
        """
        Returns a copy of the dc line
        @return: A new  with the same content as this
        """

        if bus_dict is None:
            f = self.bus_from
            t = self.bus_to
        else:
            f = bus_dict[self.bus_from]
            t = bus_dict[self.bus_to]

        b = DcLine(bus_from=f,
                   bus_to=t,
                   name=self.name,
                   r=self.R,
                   rate=self.rate,
                   active=self.active,
                   mttf=self.mttf,
                   mttr=self.mttr,
                   temp_base=self.temp_base,
                   temp_oper=self.temp_oper,
                   alpha=self.alpha,
                   template=self.template)

        b.measurements = self.measurements

        b.active_prof = self.active_prof
        b.rate_prof = self.rate_prof

        return b

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        data = list()
        for name, properties in self.editable_headers.items():
            obj = getattr(self, name)

            if properties.tpe == DeviceType.BusDevice:
                obj = obj.idtag

            elif properties.tpe == LineTemplate:
                if obj is None:
                    obj = ''
                else:
                    obj = str(obj)

            elif properties.tpe not in [str, float, int, bool]:
                obj = str(obj)

            data.append(obj)
        return data

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """
        if version == 2:
            return {'id': self.idtag,
                    'type': 'dc_line',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus_from': self.bus_from.idtag,
                    'bus_to': self.bus_to.idtag,
                    'active': self.active,
                    'rate': self.rate,
                    'r': self.R,
                    'length': self.length,
                    'base_temperature': self.temp_base,
                    'operational_temperature': self.temp_oper,
                    'alpha': self.alpha,
                    'locations': []}
        elif version == 3:
            return {'id': self.idtag,
                    'type': 'dc_line',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus_from': self.bus_from.idtag,
                    'bus_to': self.bus_to.idtag,
                    'active': self.active,
                    'rate': self.rate,
                    'contingency_factor1': self.contingency_factor,
                    'contingency_factor2': self.contingency_factor,
                    'contingency_factor3': self.contingency_factor,
                    'r': self.R,
                    'length': self.length,
                    'base_temperature': self.temp_base,
                    'operational_temperature': self.temp_oper,
                    'alpha': self.alpha,

                    'overload_cost': self.Cost,
                    'capex': self.capex,
                    'opex': self.opex,
                    'build_status': str(self.build_status.value).lower(),
                    'locations': []}
        else:
            return dict()

    def get_profiles_dict(self, version=3):

        if self.active_prof is not None:
            active_prof = self.active_prof.tolist()
            rate_prof = self.rate_prof.tolist()
        else:
            active_prof = list()
            rate_prof = list()

        return {'id': self.idtag,
                'active': active_prof,
                'rate': rate_prof}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'rate': 'MW',
                'r': 'p.u.',
                'length': 'km',
                'base_temperature': 'ºC',
                'operational_temperature': 'ºC',
                'alpha': '1/ºC'}

    def plot_profiles(self, time_series=None, my_index=0, show_fig=True):
        """
        Plot the time series results of this object
        :param time_series: TimeSeries Instance
        :param my_index: index of this object in the simulation
        :param show_fig: Show the figure?
        """

        if time_series is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            ax_2 = fig.add_subplot(212, sharex=ax_1)

            x = time_series.results.time_array

            # loading
            y = time_series.results.loading * 100.0
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_1.set_title('Loading', fontsize=14)
            ax_1.set_ylabel('Loading [%]', fontsize=11)
            df.plot(ax=ax_1)

            # losses
            y = time_series.results.losses
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_2.set_title('Losses', fontsize=14)
            ax_2.set_ylabel('Losses [MVA]', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

        if show_fig:
            plt.show()

    def get_coordinates(self):
        """
        Get the branch defining coordinates
        """
        return [self.bus_from.get_coordinates(), self.bus_to.get_coordinates()]


