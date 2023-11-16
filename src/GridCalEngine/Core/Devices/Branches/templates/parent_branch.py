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
import numpy as np
from typing import Tuple, Union
from matplotlib import pyplot as plt

from GridCalEngine.basic_structures import Logger, Vec, BoolVec
from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.Core.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus
from GridCalEngine.Core.Devices.editable_device import EditableDevice, DeviceType


class ParentBranch(EditableDevice):
    """
    This class serves to represent the basic branch
    All other branches inherit from this one
    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 bus_from: Union[Bus, None],
                 bus_to: Union[Bus, None],
                 cn_from: Union[ConnectivityNode, None],
                 cn_to: Union[ConnectivityNode, None],
                 active: bool,
                 active_prof: BoolVec,
                 rate: float,
                 rate_prof: Vec,
                 contingency_factor: float,
                 contingency_factor_prof: Vec,
                 contingency_enabled: bool,
                 monitor_loading: bool,
                 mttf: float,
                 mttr: float,
                 build_status: BuildStatus,
                 capex: float,
                 opex: float,
                 Cost: float,
                 Cost_prof: Vec,
                 device_type: DeviceType):
        """

        :param name: name of the branch
        :param idtag: UUID code
        :param code: secondary id
        :param bus_from: Name of the bus at the "from" side
        :param bus_to: Name of the bus at the "to" side
        :param cn_from: Name of the connectivity node at the "from" side
        :param cn_to: Name of the connectivity node at the "to" side
        :param active: Is active?
        :param active_prof: Active profile
        :param rate: Branch rating (MVA)
        :param rate_prof: profile of rates
        :param contingency_factor: Factor to multiply the rating in case of contingency
        :param contingency_factor_prof: contingency factor profile
        :param contingency_enabled: Enabled contingency (Legacy, better use contingency objects)
        :param monitor_loading: Monitor loading (Legacy)
        :param mttf: Mean time to failure
        :param mttr: Mean time to repair
        :param build_status: Branch build status. Used in expansion planning.
        :param capex: Cost of investment. (€/MW)
        :param opex: Cost of operation. (€/MWh)
        :param Cost: Cost of overloads. Used in OPF (€/MWh)
        :param Cost_prof: Cost of overload proile
        :param device_type: device_type (passed on)
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type)

        # connectivity
        self.bus_from = bus_from
        self.bus_to = bus_to

        self.cn_from = cn_from
        self.cn_to = cn_to

        self.active = active
        self.active_prof = active_prof

        # List of measurements
        self.measurements = list()

        self.contingency_enabled: bool = contingency_enabled

        self.monitor_loading: bool = monitor_loading

        self.mttf = mttf

        self.mttr = mttr

        self.Cost = Cost

        self.Cost_prof = Cost_prof

        self.capex = capex

        self.opex = opex

        self.build_status = build_status

        # line rating in MVA
        self.rate = rate
        self.rate_prof = rate_prof

        self.contingency_factor = contingency_factor
        self.contingency_factor_prof = contingency_factor_prof

        # List of measurements
        self.measurements = list()

        self.register('bus_from', units="", tpe=DeviceType.BusDevice,
                      definition='Name of the bus at the "from" side', editable=False)

        self.register('bus_to', units="", tpe=DeviceType.BusDevice,
                      definition='Name of the bus at the "to" side', editable=False)

        self.register('cn_from', units="", tpe=DeviceType.ConnectivityNodeDevice,
                      definition='Name of the connectivity node at the "from" side', editable=False)

        self.register('cn_to', units="", tpe=DeviceType.ConnectivityNodeDevice,
                      definition='Name of the connectivity node at the "to" side', editable=False)

        self.register('active', units="", tpe=bool, definition='Is active?', profile_name="active_prof")

        self.register('rate', units="MVA", tpe=float, definition='Thermal rating power', profile_name="rate_prof")
        self.register('contingency_factor', units="p.u.", tpe=float,
                      definition='Rating multiplier for contingencies', profile_name="contingency_factor_prof")

        self.register('monitor_loading', units="", tpe=bool,
                      definition="Monitor this device loading for OPF, NTC or contingency studies.")
        self.register('mttf', units="h", tpe=float, definition="Mean time to failure")
        self.register('mttr', units="h", tpe=float, definition="Mean time to repair")

        self.register('Cost', units="€/MWh", tpe=float,
                      definition="Cost of overloads. Used in OPF", profile_name="Cost_prof")

        self.register('build_status', units="", tpe=BuildStatus,
                      definition="Branch build status. Used in expansion planning.")
        self.register('capex', units="€/MW", tpe=float, definition="Cost of investment. Used in expansion planning.")
        self.register('opex', units="€/MWh", tpe=float, definition="Cost of operation. Used in expansion planning.")

    def get_max_bus_nominal_voltage(self):
        """
        GEt the maximum nominal voltage
        :return:
        """
        return max(self.bus_from.Vnom, self.bus_to.Vnom)

    def get_min_bus_nominal_voltage(self):
        """
        Get the minimum nominal voltage
        :return:
        """
        return min(self.bus_from.Vnom, self.bus_to.Vnom)

    def get_virtual_taps(self) -> Tuple[float, float]:
        """
        Get the branch virtual taps

        The virtual taps generate when a line nominal voltage ate the two connection buses differ

        Returns:

            **tap_f** (float, 1.0): Virtual tap at the *from* side

            **tap_t** (float, 1.0): Virtual tap at the *to* side

        """
        # resolve how the transformer is actually connected and set the virtual taps
        bus_f_v = self.bus_from.Vnom
        bus_t_v = self.bus_to.Vnom

        if bus_f_v == bus_t_v:
            return 1.0, 1.0
        else:
            if bus_f_v > 0.0 and bus_t_v > 0.0:
                return 1.0, bus_f_v / bus_t_v
            else:
                return 1.0, 1.0

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """
        if version == 2:
            return {'id': self.idtag,
                    'type': 'line',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus_from': self.bus_from.idtag,
                    'bus_to': self.bus_to.idtag,
                    'active': self.active,

                    'rate': self.rate,
                    'locations': []
                    }

        elif version == 3:
            return {'id': self.idtag,
                    'type': 'line',
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

                    'overload_cost': self.Cost,
                    'capex': self.capex,
                    'opex': self.opex,
                    'build_status': str(self.build_status.value).lower(),

                    'locations': []
                    }
        else:
            return dict()

    def get_profiles_dict(self, version=3):
        """

        :return:
        """
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
                'x': 'p.u.',
                'b': 'p.u.',
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

    def get_coordinates(self):
        """
        Get the line defining coordinates
        """
        return [self.bus_from.get_coordinates(), self.bus_to.get_coordinates()]

    def convertible_to_vsc(self):
        """
        Is this line convertible to VSC?
        :return:
        """
        if self.bus_to is not None and self.bus_from is not None:
            # connectivity:
            # for the later primitives to make sense, the "bus from" must be AC and the "bus to" must be DC
            if self.bus_from.is_dc and not self.bus_to.is_dc:  # this is the correct sense
                return True
            elif not self.bus_from.is_dc and self.bus_to.is_dc:  # opposite sense, revert
                return True
            else:
                return False
        else:
            return False

    @property
    def Vf(self):
        return self.bus_from.Vnom

    @property
    def Vt(self):
        return self.bus_to.Vnom

    def should_this_be_a_transformer(self, branch_connection_voltage_tolerance: float = 0.1) -> bool:
        """

        :param branch_connection_voltage_tolerance:
        :return:
        """
        V1 = min(self.bus_to.Vnom, self.bus_from.Vnom)
        V2 = max(self.bus_to.Vnom, self.bus_from.Vnom)
        per = V1 / V2
        return per < (1.0 - branch_connection_voltage_tolerance)

    def apply_template(self, obj, Sbase, logger: Logger):
        """
        Virtual function to apply template
        :param obj:
        :param Sbase
        :param logger
        :return:
        """
        pass