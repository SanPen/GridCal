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
from matplotlib import pyplot as plt
from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp


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

    def __init__(self, name='shunt', idtag=None, code='',
                 G=0.0, B=0.0, G_prof=None, B_prof=None, active=True, active_prof=None,
                 controlled=False, Bmin=0.0, Bmax=0.0, vset=1.0, mttf=0.0, mttr=0.0):

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                active=active,
                                device_type=DeviceType.ShuntDevice,
                                editable_headers={'name': GCProp('', str, 'Load name'),
                                                  'idtag': GCProp('', str, 'Unique ID', False),
                                                  'code': GCProp('', str, 'Secondary ID'),
                                                  'bus': GCProp('', DeviceType.BusDevice, 'Connection bus name'),
                                                  'active': GCProp('', bool, 'Is the shunt active?'),
                                                  'is_controlled': GCProp('', bool, 'Is the shunt controllable?'),
                                                  'G': GCProp('MW', float, 'Active power of the impedance component at V=1.0 p.u.'),
                                                  'B': GCProp('MVAr', float, 'Reactive power of the impedance component at V=1.0 p.u.'),
                                                  'Bmin': GCProp('MVAr', float, 'Reactive power min control value at V=1.0 p.u.'),
                                                  'Bmax': GCProp('MVAr', float, 'Reactive power max control value at V=1.0 p.u.'),
                                                  'Vset': GCProp('p.u.', float,
                                                                 'Set voltage. '
                                                                 'This is used for controlled shunts.'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery')},
                                non_editable_attributes=['bus', 'idtag'],
                                properties_with_profile={'active': 'active_prof',
                                                         'G': 'G_prof',
                                                         'B': 'B_prof'})

        # The bus this element is attached to: Not necessary for calculations
        self.bus = None

        self.active_prof = active_prof

        self.is_controlled = controlled

        self.mttf = mttf

        self.mttr = mttr

        # Impedance (MVA)
        self.G = G
        self.B = B
        self.Bmin = Bmin
        self.Bmax = Bmax
        self.Vset = vset

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
                    active_prof=self.active_prof,
                    Bmax=self.Bmax,
                    Bmin=self.Bmin,
                    vset=self.Vset,
                    mttf=self.mttf,
                    mttr=self.mttr)
        return shu

    def get_properties_dict(self):
        """
        Get json dictionary
        :return:
        """

        data = {'id': self.idtag,
                'type': 'shunt',
                'phases': 'ps',
                'name': self.name,
                'name_code': self.code,
                'bus': self.bus.idtag,
                'active': self.active,
                'g': self.G,
                'b': self.B,
                'bmax': self.Bmax,
                'bmin': self.Bmin,
                'id_impedance_table': "",
                'technology': ""
                }
        return data

    def get_profiles_dict(self):
        """

        :return:
        """

        if self.active_prof is not None:
            active_profile = self.active_prof.tolist()
            G_prof = self.G_prof.tolist()
            B_prof = self.B_prof.tolist()
        else:
            active_profile = list()
            G_prof = list()
            B_prof = list()

        return {'id': self.idtag,
                'active': active_profile,
                'g': G_prof,
                'b': B_prof}

    def get_units_dict(self):
        """
        Get units of the values
        """
        return {'g': 'MVAr at V=1 p.u.',
                'b': 'MVAr at V=1 p.u.'}

    def plot_profiles(self, time=None, show_fig=True):
        """
        Plot the time series results of this object
        :param time: array of time values
        :param show_fig: Show the figure?
        """

        if time is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            ax_2 = fig.add_subplot(212, sharex=ax_1)

            # G
            y = self.G_prof
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_1.set_title('Conductance power', fontsize=14)
            ax_1.set_ylabel('MW', fontsize=11)
            df.plot(ax=ax_1)

            # B
            y = self.B_prof
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_2.set_title('Susceptance power', fontsize=14)
            ax_2.set_ylabel('MVAr', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()
