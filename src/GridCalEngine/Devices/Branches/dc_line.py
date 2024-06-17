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

import pandas as pd
from typing import Union
from matplotlib import pyplot as plt
import numpy as np
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Parents.branch_parent import BranchParent
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.enumerations import DeviceType, BuildStatus, SubObjectType
from GridCalEngine.Devices.Branches.line_locations import LineLocations


class DcLine(BranchParent):
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
                 contingency_factor=1.0,
                 protection_rating_factor: float = 1.4,
                 contingency_enabled=True,
                 monitor_loading=True,
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
        :param cost: Cost of overload (e/MW)
        :param mttf: Mean time too failure
        :param mttr: Mean time to repair
        :param r_fault: Fault resistance
        :param fault_pos: Fault position
        :param length: Length (km)
        :param temp_base: base temperature (i.e 25º °C)
        :param temp_oper: Operational temperature (°C)
        :param alpha: Thermal constant of the material (°C)
        :param template: Basic branch template
        :param contingency_factor: Rating factor in case of contingency
        :param contingency_enabled: enabled for contingencies (Legacy)
        :param monitor_loading: monitor the loading (used in OPF)
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
                              cn_from=None,
                              cn_to=None,
                              active=active,
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
                              Cost=cost,
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
        self._temp_oper_prof = Profile(default_value=temp_oper, data_type=float)

        # Conductor thermal constant (1/ºC)
        self.alpha = alpha

        # type template
        self.template = template

        # Line locations
        self._locations: LineLocations = LineLocations()

        self.register(key='R', units='p.u.', tpe=float, definition='Total positive sequence resistance.')
        self.register(key='length', units='km', tpe=float, definition='Length of the line (not used for calculation)')
        self.register(key='r_fault', units='p.u.', tpe=float,
                      definition='Resistance of the mid-line fault.Used in short circuit studies.')
        self.register(key='fault_pos', units='p.u.', tpe=float,
                      definition='Per-unit positioning of the fault:0 would be at the "from" side,1 would '
                                 'be at the "to" side,therefore 0.5 is at the middle.')
        self.register(key='template', units='', tpe=DeviceType.SequenceLineDevice, definition='', editable=False)

        self.register(key='locations', units='', tpe=SubObjectType.LineLocations, definition='', editable=False)

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
    def locations(self) -> LineLocations:
        """
        Cost profile
        :return: Profile
        """
        return self._locations

    @locations.setter
    def locations(self, val: Union[LineLocations, np.ndarray]):
        if isinstance(val, LineLocations):
            self._locations = val
        elif isinstance(val, np.ndarray):
            self._locations.set(data=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a locations')

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
        for name, properties in self.registered_properties.items():
            obj = getattr(self, name)

            if obj is None:
                data.append("")
            else:

                if hasattr(obj, 'idtag'):
                    obj = obj.idtag
                else:
                    if properties.tpe not in [str, float, int, bool]:
                        obj = str(obj)
                    else:
                        obj = str(obj)

                data.append(obj)
        return data

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


