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

from GridCal.Engine.Devices.meta_devices import EditableDevice, DeviceType, GCProp


class StaticGenerator(EditableDevice):
    """
    Arguments:

        **name** (str, "StaticGen"): Name of the static generator

        **P** (float, 0.0): Active power in MW

        **Q** (float, 0.0): Reactive power in MVAr

        **P_prof** (DataFrame, None): Pandas DataFrame with the active power profile in MW

        **Q_prof** (DataFrame, None): Pandas DataFrame with the reactive power profile in MVAr

        **active** (bool, True): Is the static generator active?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

    """

    def __init__(self, name='StaticGen', P=0.0, Q=0.0, P_prof=None, Q_prof=None, active=True, mttf=0.0, mttr=0.0):

        EditableDevice.__init__(self,
                                name=name,
                                active=active,
                                device_type=DeviceType.StaticGeneratorDevice,
                                editable_headers={'name': GCProp('', str, ''),
                                                  'bus': GCProp('', None, ''),
                                                  'active': GCProp('', bool, ''),
                                                  'P': GCProp('MW', float, 'Active power'),
                                                  'Q': GCProp('MVAr', float, 'Reactive power'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery')},
                                non_editable_attributes=list(),
                                properties_with_profile={'P': 'P_prof',
                                                         'Q': 'Q_prof'})

        self.bus = None

        self.mttf = mttf

        self.mttr = mttr

        # Power (MW + jMVAr)
        self.P = P
        self.Q = Q

        # power profile for this load
        self.P_prof = P_prof
        self.Q_prof = Q_prof

    def copy(self):
        """
        Deep copy of this object
        :return:
        """
        return StaticGenerator(name=self.name,
                               P=self.P,
                               Q=self.Q,
                               P_prof=self.P_prof,
                               Q_prof=self.Q_prof,
                               mttf=self.mttf,
                               mttr=self.mttr)

    def get_json_dict(self, id, bus_dict):
        """
        Get json dictionary
        :param id: ID: Id for this object
        :param bus_dict: Dictionary of buses [object] -> ID
        :return:
        """
        return {'id': id,
                'type': 'static_gen',
                'phases': 'ps',
                'name': self.name,
                'bus': bus_dict[self.bus],
                'active': self.active,
                'P': self.P,
                'Q': self.Q}

