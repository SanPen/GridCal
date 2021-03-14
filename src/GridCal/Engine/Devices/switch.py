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


import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Devices.enumerations import BranchType
from GridCal.Engine.Devices.underground_line import UndergroundLineType
from GridCal.Engine.Devices.tower import Tower
from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp


class Switch(EditableDevice):
    """
    The **Switch** class represents the connections between nodes (i.e.
    :ref:`buses<bus>`) in **GridCal**. A Switch is an devices that cuts or allows the flow.

    Arguments:

        **bus_from** (:ref:`Bus`): "From" :ref:`bus<Bus>` object

        **bus_to** (:ref:`Bus`): "To" :ref:`bus<Bus>` object

        **name** (str, "Branch"): Name of the branch

        **r** (float, 1e-20): Branch resistance in per unit

        **x** (float, 1e-20): Branch reactance in per unit

        **rate** (float, 1.0): Branch rate in MVA

        **active** (bool, True): Is the branch active?
    """

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, name='Switch', idtag=None, code='',
                 r=1e-20, x=1e-20, rate=1.0, active=True, active_prof=None):

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=active,
                                device_type=DeviceType.SwitchDevice,
                                code=code,
                                editable_headers={'name': GCProp('', str, 'Name of the line.'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'code': GCProp('', str, 'Secondary ID'),
                                                  'bus_from': GCProp('', DeviceType.BusDevice,
                                                                     'Name of the bus at the "from" side of the line.'),
                                                  'bus_to': GCProp('', DeviceType.BusDevice,
                                                                   'Name of the bus at the "to" side of the line.'),
                                                  'active': GCProp('', bool, 'Is the line active?'),
                                                  'rate': GCProp('MVA', float, 'Thermal rating power of the line.'),
                                                  'R': GCProp('p.u.', float, 'Total resistance.'),
                                                  'X': GCProp('p.u.', float, 'Total reactance.')
                                                  },
                                non_editable_attributes=['bus_from', 'bus_to', 'idtag'],
                                properties_with_profile={'active': 'active_prof'})

        # connectivity
        self.bus_from = bus_from
        self.bus_to = bus_to

        # List of measurements
        self.measurements = list()

        # total impedance and admittance in p.u.
        self.R = r
        self.X = x

        self.active_prof = active_prof

        # line rating in MVA
        self.rate = rate

        # line type: Line, Transformer, etc...
        self.branch_type = BranchType.Switch

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

            if properties.tpe == BranchType:
                obj = self.branch_type.value
            if properties.tpe == DeviceType.BusDevice:
                obj = obj.idtag

            elif properties.tpe not in [str, float, int, bool]:
                obj = str(obj)

            data.append(obj)
        return data

    def get_properties_dict(self):
        """
        Get json dictionary
        :return:
        """

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

        return d

    def get_profiles_dict(self):
        """

        :return:
        """
        if self.active_prof is not None:
            active_prof = self.active_prof.tolist()
        else:
            active_prof = list()

        return {'id': self.idtag,
                'active': active_prof}

    def get_units_dict(self):
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
