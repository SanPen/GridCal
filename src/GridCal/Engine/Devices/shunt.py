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


class Shunt(EditableDevice):
    """
    Arguments:

        **name** (str, "shunt"): Name of the shunt

        **G** (float, 0.0): Conductance in MW at 1 p.u. voltage

        **B** (float, 0.0): Susceptance in MW at 1 p.u. voltage

        **G_prof** (DataFrame, None): Pandas DataFrame with the conductance profile in MW at 1 p.u. voltage

        **B_prof** (DataFrame, None): Pandas DataFrame with the susceptance profile in MW at 1 p.u. voltage

        **active** (bool, True): Is the shunt active?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

    """

    def __init__(self, name='shunt', G=0.0, B=0.0, G_prof=None, B_prof=None, active=True, mttf=0.0, mttr=0.0):

        EditableDevice.__init__(self,
                                name=name,
                                active=active,
                                device_type=DeviceType.ShuntDevice,
                                editable_headers={'name': GCProp('', str, 'Load name'),
                                                  'bus': GCProp('', None, 'Connection bus name'),
                                                  'active': GCProp('', bool, 'Is the load active?'),
                                                  'G': GCProp('MW', float,
                                                              'Active power of the impedance component at V=1.0 p.u.'),
                                                  'B': GCProp('MVAr', float,
                                                              'Reactive power of the impedance component at V=1.0 p.u.'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery')},
                                non_editable_attributes=list(),
                                properties_with_profile={'G': 'G_prof',
                                                         'B': 'B_prof'})

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        self.mttf = mttf

        self.mttr = mttr

        # Impedance (MVA)
        self.G = G
        self.B = B

        # admittance profile
        self.G_prof = G_prof
        self.B_prof = B_prof

    def copy(self):
        """
        Copy of this object
        :return: a copy of this object
        """
        shu = Shunt(name=self.name,
                    G=self.G,
                    B=self.B,
                    G_prof=self.G_prof,
                    B_prof=self.B_prof,
                    active=self.active,
                    mttf=self.mttf,
                    mttr=self.mttr)
        return shu

    def get_json_dict(self, id, bus_dict):
        """
        Get json dictionary
        :param id: ID: Id for this object
        :param bus_dict: Dictionary of buses [object] -> ID
        :return:
        """
        return {'id': id,
                'type': 'shunt',
                'phases': 'ps',
                'name': self.name,
                'bus': bus_dict[self.bus],
                'active': self.active,
                'g': self.G,
                'b': self.B}
