# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

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
                              device_type=DeviceType.UpfcDevice)

        # total impedance and admittance in p.u.
        self.R = float(rs)
        self.X = float(xs)
        self.Rsh = float(rp)
        self.Xsh = float(xp)

        self.R0 = float(rs0)
        self.X0 = float(xs0)
        self.Rsh0 = float(rp0)
        self.Xsh0 = float(xp0)

        self.R2 = float(rs2)
        self.X2 = float(xs2)
        self.Rsh2 = float(rp2)
        self.Xsh2 = float(xp2)

        self.Vsh = float(vp)
        self.Pfset = float(Pset)
        self.Qfset = float(Qset)

        self.register(key='R', units='p.u.', tpe=float, definition='Series positive sequence resistance.',
                      old_names=['Rs'])
        self.register(key='X', units='p.u.', tpe=float, definition='Series positive sequence reactance.',
                      old_names=['Xs'])
        self.register(key='Rsh', units='p.u.', tpe=float, definition='Shunt positive sequence resistance.')
        self.register(key='Xsh', units='p.u.', tpe=float, definition='Shunt positive sequence resistance.')
        self.register(key='R0', units='p.u.', tpe=float, definition='Series zero sequence resistance.',
                      old_names=['Rs0'])
        self.register(key='X0', units='p.u.', tpe=float, definition='Series zero sequence reactance.',
                      old_names=['Xs0'])
        self.register(key='Rsh0', units='p.u.', tpe=float, definition='Shunt zero sequence resistance.')
        self.register(key='Xsh0', units='p.u.', tpe=float, definition='Shunt zero sequence resistance.')
        self.register(key='R2', units='p.u.', tpe=float, definition='Series negative sequence resistance.',
                      old_names=['Rs2'])
        self.register(key='X2', units='p.u.', tpe=float, definition='Series negative sequence reactance.',
                      old_names=['Xs2'])
        self.register(key='Rsh2', units='p.u.', tpe=float, definition='Shunt negative sequence resistance.')
        self.register(key='Xsh2', units='p.u.', tpe=float, definition='Shunt negative sequence resistance.')
        self.register(key='Vsh', units='p.u.', tpe=float, definition='Shunt voltage set point.')
        self.register(key='Pfset', units='MW', tpe=float, definition='Active power set point.')
        self.register(key='Qfset', units='MVAr', tpe=float, definition='Active power set point.')

    def get_ysh1(self):
        """

        :return:
        """
        return 1.0 / complex(self.Rsh + 1e-20, self.Xsh)

    def get_ysh0(self):
        """

        :return:
        """
        return 1.0 / complex(self.Rsh0 + 1e-20, self.Xsh0)

    def get_ysh2(self):
        """

        :return:
        """
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

        self.R *= b
        self.X *= b
        self.Rsh *= b
        self.X *= b

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
