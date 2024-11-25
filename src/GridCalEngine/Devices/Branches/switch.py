# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.Devices.Substation.connectivity_node import ConnectivityNode
from GridCalEngine.enumerations import BuildStatus
from GridCalEngine.Devices.Parents.branch_parent import BranchParent
from GridCalEngine.Devices.Parents.editable_device import DeviceType


class Switch(BranchParent):
    """
    The **Switch** class represents the connections between nodes (i.e.
    :ref:`buses<bus>`) in **GridCal**. A Switch is a devices that cuts or allows the flow.
    """

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None,
                 cn_from: ConnectivityNode = None, cn_to: ConnectivityNode = None,
                 name='Switch', idtag=None, code='', r=1e-20, x=1e-20,
                 rate=1.0,
                 active=True,
                 contingency_factor=1.0, protection_rating_factor: float = 1.4,
                 retained=True,
                 normal_open=False,
                 rated_current=0.0):
        """
        Switch device
        :param bus_from: Bus from
        :param bus_to: Bus to
        :param name: Name of the branch
        :param idtag: UUID code
        :param code: secondary ID
        :param r: resistance in p.u.
        :param x: reactance in p.u.
        :param rate: Branch rating (MW)
        :param active: is it active?
        :param contingency_factor: Rating factor in case of contingency
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
                              contingency_enabled=True,
                              monitor_loading=True,
                              mttf=0.0,
                              mttr=0.0,
                              build_status=BuildStatus.Commissioned,
                              capex=0,
                              opex=0,
                              Cost=0,
                              device_type=DeviceType.SwitchDevice)

        # total impedance and admittance in p.u.
        self.R = float(r)
        self.X = float(x)

        # self.is_open = is_open
        self.retained = bool(retained)

        self.normal_open = bool(normal_open)
        self.rated_current = float(rated_current)

        self.register(key='R', units='pu', tpe=float, definition='Positive-sequence resistance')
        self.register(key='X', units='pu', tpe=float, definition='Positive-sequence reactance')

        # self.register(key='is_open', units="", tpe=bool,
        #               definition='Switch is open', old_names=['open'])
        self.register(key='retained', units="", tpe=bool,
                      definition='Switch is retained')

        self.register(key='normal_open', units="", tpe=bool,
                      definition='Normal position of the switch')
        self.register(key='rated_current', units="kA", tpe=float,
                      definition='Rated current of the switch device.')

    def copy(self, bus_dict=None):
        """
        Returns a copy of the line
        @return: A new  with the same content as this
        """

        if bus_dict is None:
            f = self.bus_from
            t = self.bus_to
        else:
            f = bus_dict[self.bus_from]
            t = bus_dict[self.bus_to]

        b = Switch(bus_from=f,
                   bus_to=t,
                   name=self.name,
                   r=self.R,
                   x=self.X,
                   rate=self.rate,
                   active=self.active)

        return b

    def get_save_data(self):
        """
        Return the data that matches the edit_headers
        :return:
        """
        data = list()
        for name, properties in self.registered_properties.items():
            obj = getattr(self, name)

            if properties.tpe == DeviceType.BusDevice:
                obj = obj.idtag

            elif properties.tpe not in [str, float, int, bool]:
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

        pass
