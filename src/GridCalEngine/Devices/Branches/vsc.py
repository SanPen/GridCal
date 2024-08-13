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
from typing import List, Tuple

from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus, TapModuleControl, TapPhaseControl
from GridCalEngine.Devices.Parents.controllable_branch_parent import ControllableBranchParent
from GridCalEngine.Devices.Parents.editable_device import DeviceType


class VSC(ControllableBranchParent):

    def __init__(self,
                 bus_from: Bus = None,
                 bus_to: Bus = None,
                 cn_from: ConnectivityNode = None,
                 cn_to: ConnectivityNode = None,
                 name='VSC',
                 idtag=None,
                 code='',
                 active=True,
                 r=0.0001,
                 x=0.05,
                 tap_module=1.0,
                 tap_module_max=1.1,
                 tap_module_min=0.8,
                 tap_phase=0.1,
                 tap_phase_max=6.28,
                 tap_phase_min=-6.28,
                 Beq=0.001,
                 Beq_min=-0.1,
                 Beq_max=0.1,
                 G0sw=1e-5,
                 rate=1e-9,
                 kdp=-0.05,
                 k=1.0,
                 alpha1=0.0001,
                 alpha2=0.015,
                 alpha3=0.2,
                 mttf=0.0,
                 mttr=0.0,
                 tap_module_control_mode: TapModuleControl = TapModuleControl.fixed,
                 tap_phase_control_mode: TapPhaseControl = TapPhaseControl.fixed,
                 vset: float = 1.0,
                 Pset: float = 0.0,
                 Qset: float = 0.0,
                 cost=100,
                 contingency_factor=1.0,
                 protection_rating_factor: float = 1.4,
                 contingency_enabled=True,
                 monitor_loading=True,
                 r0=0.0001,
                 x0=0.05,
                 r2=0.0001,
                 x2=0.05,
                 capex=0,
                 opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """
        Voltage source converter (VSC)
        :param bus_from:
        :param bus_to:
        :param name:
        :param idtag:
        :param code:
        :param active:
        :param r:
        :param x:
        :param tap_module:
        :param tap_module_max:
        :param tap_module_min:
        :param tap_phase:
        :param tap_phase_max:
        :param tap_phase_min:
        :param Beq:
        :param Beq_min:
        :param Beq_max:
        :param G0sw:
        :param rate:
        :param kdp:
        :param k:
        :param alpha1:
        :param alpha2:
        :param alpha3:
        :param mttf:
        :param mttr:
        :param cost:
        :param contingency_factor:
        :param contingency_enabled:
        :param monitor_loading:
        :param r0:
        :param x0:
        :param r2:
        :param x2:
        :param capex:
        :param opex:
        :param build_status:
        """

        ControllableBranchParent.__init__(self,
                                          name=name,
                                          idtag=idtag,
                                          code=code,
                                          bus_from=bus_from,
                                          bus_to=bus_to,
                                          cn_from=cn_from,
                                          cn_to=cn_to,
                                          active=active,
                                          rate=rate,
                                          r=r,
                                          x=x,
                                          g=0.0,
                                          b=0.0,
                                          tap_module=tap_module,
                                          tap_module_max=tap_module_max,
                                          tap_module_min=tap_module_min,
                                          tap_phase=tap_phase,
                                          tap_phase_max=tap_phase_max,
                                          tap_phase_min=tap_phase_min,
                                          tolerance=0.0,
                                          Cost=cost,
                                          mttf=mttf,
                                          mttr=mttr,
                                          vset=vset,
                                          Pset=Pset,
                                          Qset=Qset,
                                          regulation_branch=None,
                                          regulation_bus=None,
                                          regulation_cn=None,
                                          temp_base=20.0,
                                          temp_oper=20.0,
                                          alpha=0.00330,
                                          # control_mode=control_mode,
                                          tap_module_control_mode=tap_module_control_mode,
                                          tap_phase_control_mode=tap_phase_control_mode,
                                          contingency_factor=contingency_factor,
                                          protection_rating_factor=protection_rating_factor,
                                          contingency_enabled=contingency_enabled,
                                          monitor_loading=monitor_loading,
                                          r0=r0,
                                          x0=x0,
                                          g0=0.0,
                                          b0=0.0,
                                          r2=r2,
                                          x2=x2,
                                          g2=0.0,
                                          b2=0.0,
                                          capex=capex,
                                          opex=opex,
                                          build_status=build_status,
                                          device_type=DeviceType.VscDevice)

        # the VSC must only connect from an DC to a AC bus
        # this connectivity sense is done to keep track with the articles that set it
        # from -> DC
        # to   -> AC
        # assert(bus_from.is_dc != bus_to.is_dc)
        if bus_to is not None and bus_from is not None:
            # connectivity:
            # for the later primitives to make sense, the "bus from" must be AC and the "bus to" must be DC
            if bus_from.is_dc and not bus_to.is_dc:  # this is the correct sense
                self.bus_from = bus_from
                self.bus_to = bus_to
            elif not bus_from.is_dc and bus_to.is_dc:  # opposite sense, revert
                self.bus_from = bus_to
                self.bus_to = bus_from
                print('Corrected the connection direction of the VSC device:', self.name)
            else:
                raise Exception('Impossible connecting a VSC device here. '
                                'VSC devices must be connected between AC and DC buses')
        else:
            self.bus_from = None
            self.bus_to = None

        self.G0sw = G0sw
        self.Beq = Beq
        self.tap_module = tap_module
        self.tap_module_max = tap_module_max
        self.tap_module_min = tap_module_min

        self.k = k
        self.tap_phase = tap_phase
        self.tap_phase_max = tap_phase_max
        self.tap_phase_min = tap_phase_min
        self.Beq_min = Beq_min
        self.Beq_max = Beq_max

        self.kdp = kdp
        self.alpha1 = alpha1
        self.alpha2 = alpha2
        self.alpha3 = alpha3

        self.register(key='G0sw', units='p.u.', tpe=float, definition='Inverter losses.')
        self.register(key='Beq', units='p.u.', tpe=float, definition='Total shunt susceptance.')
        self.register(key='Beq_max', units='p.u.', tpe=float, definition='Max total shunt susceptance.')
        self.register(key='Beq_min', units='p.u.', tpe=float, definition='Min total shunt susceptance.')

        self.register(key='alpha1', units='', tpe=float,
                      definition='Losses constant parameter (IEC 62751-2 loss Correction).')
        self.register(key='alpha2', units='', tpe=float,
                      definition='Losses linear parameter (IEC 62751-2 loss Correction).')
        self.register(key='alpha3', units='', tpe=float,
                      definition='Losses quadratic parameter (IEC 62751-2 loss Correction).')

        self.register(key='k', units='p.u./p.u.', tpe=float, definition='Converter factor, typically 0.866.')

        self.register(key='kdp', units='p.u./p.u.', tpe=float, definition='Droop Power/Voltage slope.')

    def change_base(self, Sbase_old: float, Sbase_new: float):
        """
        Change the inpedance base
        :param Sbase_old: old base (MVA)
        :param Sbase_new: new base (MVA)
        """
        super().change_base(Sbase_old, Sbase_new)
        b = Sbase_new / Sbase_old
        self.G0sw *= b
        self.Beq *= b

    def get_coordinates(self) -> List[Tuple[float, float]]:
        """
        Get the line defining coordinates
        """
        return [self.bus_from.get_coordinates(), self.bus_to.get_coordinates()]

    def correct_buses_connection(self) -> None:
        """
        Fix the buses connection (from: DC, To: AC)
        """
        # the VSC must only connect from an DC to a AC bus
        # this connectivity sense is done to keep track with the articles that set it
        # from -> DC
        # to   -> AC
        # assert(bus_from.is_dc != bus_to.is_dc)
        if self.bus_to is not None and self.bus_from is not None:
            # connectivity:
            # for the later primitives to make sense, the "bus from" must be AC and the "bus to" must be DC
            if self.bus_from.is_dc and not self.bus_to.is_dc:  # correct sense
                pass
            elif not self.bus_from.is_dc and self.bus_to.is_dc:  # opposite sense, revert
                self.bus_from, self.bus_to = self.bus_to, self.bus_from
                print('Corrected the connection direction of the VSC device:', self.name)
            else:
                raise Exception('Impossible connecting a VSC device here. '
                                'VSC devices must be connected between AC and DC buses')
        else:
            self.bus_from = None
            self.bus_to = None

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


