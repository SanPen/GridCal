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


from GridCalEngine.Core.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import BuildStatus
from GridCalEngine.Core.Devices.Branches.templates.parent_branch import ParentBranch
from GridCalEngine.Core.Devices.editable_device import DeviceType


class Switch(ParentBranch):
    """
    The **Switch** class represents the connections between nodes (i.e.
    :ref:`buses<bus>`) in **GridCal**. A Switch is an devices that cuts or allows the flow.
    """

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, name='Switch', idtag=None, code='',
                 r=1e-20, x=1e-20, rate=1.0, active=True, active_prof=None, contingency_factor=1.0):
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
        :param active_prof: Active profile
        :param contingency_factor: Rating factor in case of contingency
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
                              rate_prof=None,
                              contingency_factor=contingency_factor,
                              contingency_factor_prof=None,
                              contingency_enabled=True,
                              monitor_loading=True,
                              mttf=0.0,
                              mttr=0.0,
                              build_status=BuildStatus.Commissioned,
                              capex=0,
                              opex=0,
                              Cost=0,
                              Cost_prof=None,
                              device_type=DeviceType.SwitchDevice)

        # List of measurements
        self.measurements = list()

        # total impedance and admittance in p.u.
        self.R = r
        self.X = x

        self.active_prof = active_prof

        self.register(key='R', units='Ohm/km', tpe=float, definition='Positive-sequence resistance')
        self.register(key='X', units='Ohm/km', tpe=float, definition='Positive-sequence reactance')

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

        b.measurements = self.measurements

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
            d = {'id': self.idtag,
                 'type': 'Switch',
                 'phases': 'ps',
                 'name': self.name,
                 'name_code': self.code,
                 'bus_from': self.bus_from.idtag,
                 'bus_to': self.bus_to.idtag,
                 'active': self.active,

                 'rate': self.rate,

                 'r': self.R,
                 'x': self.X
                 }
        elif version == 3:
            d = {'id': self.idtag,
                 'type': 'Switch',
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
                 'x': self.X
                 }
        else:
            d = dict()

        return d

    def get_profiles_dict(self, version=3):
        """

        :return:
        """
        if self.active_prof is not None:
            active_prof = self.active_prof.tolist()
        else:
            active_prof = list()

        return {'id': self.idtag,
                'active': active_prof}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'rate': 'MW',
                'r': 'p.u.',
                'x': 'p.u.'}

    def plot_profiles(self, time_series=None, my_index=0, show_fig=True):
        """
        Plot the time series results of this object
        :param time_series: TimeSeries Instance
        :param my_index: index of this object in the simulation
        :param show_fig: Show the figure?
        """

        pass
