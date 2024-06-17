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
import numpy as np
from matplotlib import pyplot as plt

from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus
from GridCalEngine.Devices.Parents.branch_parent import BranchParent
from GridCalEngine.Devices.Parents.editable_device import DeviceType


class UPFC(BranchParent):

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None,
                 cn_from: ConnectivityNode = None,
                 cn_to: ConnectivityNode = None,
                 name='UPFC', code='', idtag=None, active=True,
                 rs=0.0, xs=0.00001, rp=0.0, xp=0.0, vp=1.0, Pset=0.0, Qset=0.0, rate=9999,
                 mttf=0, mttr=0, cost=100, contingency_factor=1.0, protection_rating_factor: float = 1.4,
                 contingency_enabled=True, monitor_loading=True,
                 rs0=0.0, xs0=0.00001, rp0=0.0, xp0=0.0,
                 rs2=0.0, xs2=0.00001, rp2=0.0, xp2=0.0,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """
        Unified Power Flow Converter (UPFC)
        :param bus_from:
        :param bus_to:
        :param name:
        :param code:
        :param idtag:
        :param active:
        :param rs: series resistance (p.u.)
        :param xs: series reactance (p.u.)
        :param rp: shunt resistance (p.u.)
        :param xp: shunt reactance (p.u.)
        :param vp: shunt voltage set point (p.u.)
        :param Pset: Power set point (MW)
        :param Qset:
        :param rate: Power rating (MVA)
        :param mttf:
        :param mttr:
        :param cost:
        :param contingency_factor:
        :param contingency_enabled:
        :param monitor_loading:
        :param rs0:
        :param xs0:
        :param rp0:
        :param xp0:
        :param rs2:
        :param xs2:
        :param rp2:
        :param xp2:
        :param capex:
        :param opex:
        :param build_status:
        """

        BranchParent.__init__(self,
                              name=name,
                              idtag=idtag,
                              code=code,
                              bus_from=bus_from,
                              bus_to=bus_to,
                              cn_from=cn_from,
                              cn_to=cn_to,
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
                              device_type=DeviceType.UpfcDevice)

        # total impedance and admittance in p.u.
        self.Rs = rs
        self.Xs = xs
        self.Rsh = rp
        self.Xsh = xp

        self.Rs0 = rs0
        self.Xs0 = xs0
        self.Rsh0 = rp0
        self.Xsh0 = xp0

        self.Rs2 = rs2
        self.Xs2 = xs2
        self.Rsh2 = rp2
        self.Xsh2 = xp2

        self.Vsh = vp
        self.Pfset = Pset
        self.Qfset = Qset

        self.register(key='Rs', units='p.u.', tpe=float, definition='Series positive sequence resistance.')
        self.register(key='Xs', units='p.u.', tpe=float, definition='Series positive sequence reactance.')
        self.register(key='Rsh', units='p.u.', tpe=float, definition='Shunt positive sequence resistance.')
        self.register(key='Xsh', units='p.u.', tpe=float, definition='Shunt positive sequence resistance.')
        self.register(key='Rs0', units='p.u.', tpe=float, definition='Series zero sequence resistance.')
        self.register(key='Xs0', units='p.u.', tpe=float, definition='Series zero sequence reactance.')
        self.register(key='Rsh0', units='p.u.', tpe=float, definition='Shunt zero sequence resistance.')
        self.register(key='Xsh0', units='p.u.', tpe=float, definition='Shunt zero sequence resistance.')
        self.register(key='Rs2', units='p.u.', tpe=float, definition='Series negative sequence resistance.')
        self.register(key='Xs2', units='p.u.', tpe=float, definition='Series negative sequence reactance.')
        self.register(key='Rsh2', units='p.u.', tpe=float, definition='Shunt negative sequence resistance.')
        self.register(key='Xsh2', units='p.u.', tpe=float, definition='Shunt negative sequence resistance.')
        self.register(key='Vsh', units='p.u.', tpe=float, definition='Shunt voltage set point.')
        self.register(key='Pfset', units='MW', tpe=float, definition='Active power set point.')
        self.register(key='Qfset', units='MVAr', tpe=float, definition='Active power set point.')

    def get_ysh1(self):
        return 1.0 / complex(self.Rsh + 1e-20, self.Xsh)

    def get_ysh0(self):
        return 1.0 / complex(self.Rsh0 + 1e-20, self.Xsh0)

    def get_ysh2(self):
        return 1.0 / complex(self.Rsh2 + 1e-20, self.Xsh2)

    def get_max_bus_nominal_voltage(self):
        return max(self.bus_from.Vnom, self.bus_to.Vnom)

    def get_min_bus_nominal_voltage(self):
        return min(self.bus_from.Vnom, self.bus_to.Vnom)

    def change_base(self, Sbase_old: float, Sbase_new: float):
        """

        :param Sbase_old:
        :param Sbase_new:
        :return:
        """
        b = Sbase_new / Sbase_old

        self.Rs *= b
        self.Xs *= b
        self.Rsh *= b
        self.Xs *= b

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
            y = time_series.results.loading.real * 100.0
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_1.set_title('Loading', fontsize=14)
            ax_1.set_ylabel('Loading [%]', fontsize=11)
            df.plot(ax=ax_1)

            # losses
            y = np.abs(time_series.results.losses)
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_2.set_title('Losses', fontsize=14)
            ax_2.set_ylabel('Losses [MVA]', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

        if show_fig:
            plt.show()
