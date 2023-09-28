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

from typing import Union
from GridCalEngine.Core.Devices.editable_device import EditableDevice
from GridCalEngine.enumerations import BuildStatus, DeviceType
from GridCalEngine.basic_structures import Vec


class InjectionTemplate(EditableDevice):
    """
    The load object implements the so-called ZIP model, in which the load can be
    represented by a combination of power (P), current(I), and impedance (Z).

    The sign convention is: Positive to act as a load, negative to act as a generator.

    Arguments:

        **name** (str, "Load"): Name of the load

        **G** (float, 0.0): Conductance in equivalent MW

        **B** (float, 0.0): Susceptance in equivalent MVAr

        **Ir** (float, 0.0): Real current in equivalent MW

        **Ii** (float, 0.0): Imaginary current in equivalent MVAr

        **P** (float, 0.0): Active power in MW

        **Q** (float, 0.0): Reactive power in MVAr

        **G_prof** (DataFrame, None): Pandas DataFrame with the conductance profile in equivalent MW

        **B_prof** (DataFrame, None): Pandas DataFrame with the susceptance profile in equivalent MVAr

        **Ir_prof** (DataFrame, None): Pandas DataFrame with the real current profile in equivalent MW

        **Ii_prof** (DataFrame, None): Pandas DataFrame with the imaginary current profile in equivalent MVAr

        **P_prof** (DataFrame, None): Pandas DataFrame with the active power profile in equivalent MW

        **Q_prof** (DataFrame, None): Pandas DataFrame with the reactive power profile in equivalent MVAr

        **active** (bool, True): Is the load active?

        **mttf** (float, 0.0): Mean time to failure in hours

        **mttr** (float, 0.0): Mean time to recovery in hours

    """

    def __init__(self,
                 name: str,
                 idtag: Union[str, None],
                 code: str,
                 bus: Union["Bus", None],
                 cn: Union["ConnectivityNode", None],
                 active: bool,
                 active_prof: Union[Vec, None],
                 Cost: float,
                 Cost_prof: Union[Vec, None],
                 mttf: float,
                 mttr: float,
                 capex: float,
                 opex: float,
                 build_status: BuildStatus,
                 device_type: DeviceType):
        """

        :param name:
        :param idtag:
        :param code:
        :param bus:
        :param cn:
        :param active:
        :param active_prof:
        :param Cost:
        :param Cost_prof:
        :param mttf:
        :param mttr:
        :param capex:
        :param opex:
        :param build_status:
        :param device_type:
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type)

        self.bus = bus

        self.cn = cn

        self.active = active
        self.active_prof = active_prof

        self.mttf = mttf

        self.mttr = mttr

        self.Cost = Cost

        self.Cost_prof = Cost_prof

        self.capex = capex

        self.opex = opex

        self.build_status = build_status

        self.register(key='bus', units='', tpe=DeviceType.BusDevice, definition='Connection bus', editable=False)
        self.register(key='cn', units='', tpe=DeviceType.ConnectivityNodeDevice,
                      definition='Connection connectivity node', editable=False)

        self.register(key='active', units='', tpe=bool, definition='Is the load active?', profile_name='active_prof')

        self.register(key='mttf', units='h', tpe=float, definition='Mean time to failure')
        self.register(key='mttr', units='h', tpe=float, definition='Mean time to recovery')

        self.register(key='capex', units='e/MW', tpe=float,
                      definition='Cost of investment. Used in expansion planning.')
        self.register(key='opex', units='e/MWh', tpe=float, definition='Cost of operation. Used in expansion planning.')

        self.register(key='build_status', units='', tpe=BuildStatus,
                      definition='Branch build status. Used in expansion planning.')

        self.register(key='Cost', units='e/MWh', tpe=float, definition='Cost of not served energy. Used in OPF.',
                      profile_name='Cost_prof')

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """
        if version in [2, 3]:
            return {'id': self.idtag,
                    'type': 'load',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus': self.bus.idtag,
                    'active': bool(self.active),
                    'p': self.P,
                    'q': self.Q,
                    'shedding_cost': self.Cost
                    }
        else:
            return dict()

    def get_profiles_dict(self, version=3):
        """

        :return:
        """

        if self.active_prof is not None:
            active_profile = self.active_prof.tolist()
            P_prof = self.P_prof.tolist()
            Q_prof = self.Q_prof.tolist()

        else:
            active_profile = list()
            P_prof = list()
            Q_prof = list()

        return {'id': self.idtag,
                'active': active_profile,
                'p': P_prof,
                'q': Q_prof}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'g': 'MVAr at V=1 p.u.',
                'b': 'MVAr at V=1 p.u.',
                'ir': 'MVAr at V=1 p.u.',
                'ii': 'MVAr at V=1 p.u.',
                'p': 'MW',
                'q': 'MVAr'}

