# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Union
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from VeraGridEngine.enumerations import DeviceType, BuildStatus
from VeraGridEngine.Devices.Parents.load_parent import LoadParent
from VeraGridEngine.Devices.profile import Profile
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, DynamicVarType


class Load(LoadParent):
    """
    Load
    """
    __slots__ = (
        'G',
        'B',
        'Ir',
        'Ii',
        '_G_prof',
        '_B_prof',
        '_Ir_prof',
        '_Ii_prof',

        'G1',
        'B1',
        'Ir1',
        'Ii1',
        '_G1_prof',
        '_B1_prof',
        '_Ir1_prof',
        '_Ii1_prof',

        'G2',
        'B2',
        'Ir2',
        'Ii2',
        '_G2_prof',
        '_B2_prof',
        '_Ir2_prof',
        '_Ii2_prof',

        'G3',
        'B3',
        'Ir3',
        'Ii3',
        '_G3_prof',
        '_B3_prof',
        '_Ir3_prof',
        '_Ii3_prof',

        '_n_customers',
        '_n_customers_prof',

        'Pl0',
        'Ql0',
        'init_params'
    )

    def __init__(self, name='Load', idtag=None, code='',
                 G=0.0, B=0.0, Ir=0.0, Ii=0.0, P=0.0, Q=0.0, Cost=1200.0,
                 P1=0.0, P2=0.0, P3=0.0, Q1=0.0, Q2=0.0, Q3=0.0,
                 G1=0.0, G2=0.0, G3=0.0, B1=0.0, B2=0.0, B3=0.0,
                 Ir1=0.0, Ir2=0.0, Ir3=0.0, Ii1=0.0, Ii2=0.0, Ii3=0.0, Pl0=1.0, Ql0=1.0,
                 active=True, mttf=0.0, mttr=0.0, capex=0, opex=0,
                 init_params: dict[str, float] = {},
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """
        The load object implements the so-called ZIP model, in which the load can be
        represented by a combination of power (P), current(I), and impedance (Z).
        The sign convention is: Positive to act as a load, negative to act as a generator.
        :param name: Name of the load
        :param idtag: UUID code
        :param code: secondary ID code
        :param G: Conductance in equivalent MW
        :param G1: Conductance in equivalent MW
        :param G2: Conductance in equivalent MW
        :param G3: Conductance in equivalent MW
        :param B: Susceptance in equivalent MVAr
        :param B1: Susceptance in equivalent MVAr
        :param B2: Susceptance in equivalent MVAr
        :param B3: Susceptance in equivalent MVAr
        :param Ir: Real current in equivalent MW
        :param Ir1: Real current in equivalent MW
        :param Ir2: Real current in equivalent MW
        :param Ir3: Real current in equivalent MW
        :param Ii: Imaginary current in equivalent MVAr
        :param Ii1: Imaginary current in equivalent MVAr
        :param Ii2: Imaginary current in equivalent MVAr
        :param Ii3: Imaginary current in equivalent MVAr
        :param P: Active power in MW
        :param P1: Active power in MW
        :param P2: Active power in MW
        :param P3: Active power in MW
        :param Q: Reactive power in MVAr
        :param Q1: Reactive power in MVAr
        :param Q2: Reactive power in MVAr
        :param Q3: Reactive power in MVAr
        :param Cost: Cost of load shedding
        :param active: Is the load active?
        :param mttf: Mean time to failure in hours
        :param mttr: Mean time to recovery in hours
        """
        LoadParent.__init__(self,
                            name=name,
                            idtag=idtag,
                            code=code,
                            bus=None,
                            active=active,
                            P=P,
                            P1=P1,
                            P2=P2,
                            P3=P3,
                            Q=Q,
                            Q1=Q1,
                            Q2=Q2,
                            Q3=Q3,
                            Cost=Cost,
                            mttf=mttf,
                            mttr=mttr,
                            capex=capex,
                            opex=opex,
                            build_status=build_status,
                            device_type=DeviceType.LoadDevice)

        self.G = float(G)
        self.G1 = float(G1)
        self.G2 = float(G2)
        self.G3 = float(G3)
        self.B = float(B)
        self.B1 = float(B1)
        self.B2 = float(B2)
        self.B3 = float(B3)
        self.Ir = float(Ir)
        self.Ir1 = float(Ir1)
        self.Ir2 = float(Ir2)
        self.Ir3 = float(Ir3)
        self.Ii = float(Ii)
        self.Ii1 = float(Ii1)
        self.Ii2 = float(Ii2)
        self.Ii3 = float(Ii3)

        self._G_prof = Profile(default_value=self.G, data_type=float)
        self._G1_prof = Profile(default_value=self.G1, data_type=float)
        self._G2_prof = Profile(default_value=self.G2, data_type=float)
        self._G3_prof = Profile(default_value=self.G3, data_type=float)
        self._B_prof = Profile(default_value=self.B, data_type=float)
        self._B1_prof = Profile(default_value=self.B1, data_type=float)
        self._B2_prof = Profile(default_value=self.B2, data_type=float)
        self._B3_prof = Profile(default_value=self.B3, data_type=float)
        self._Ir_prof = Profile(default_value=self.Ir, data_type=float)
        self._Ir1_prof = Profile(default_value=self.Ir1, data_type=float)
        self._Ir2_prof = Profile(default_value=self.Ir2, data_type=float)
        self._Ir3_prof = Profile(default_value=self.Ir3, data_type=float)
        self._Ii_prof = Profile(default_value=self.Ii, data_type=float)
        self._Ii1_prof = Profile(default_value=self.Ii1, data_type=float)
        self._Ii2_prof = Profile(default_value=self.Ii2, data_type=float)
        self._Ii3_prof = Profile(default_value=self.Ii3, data_type=float)

        self._n_customers: int = 1
        self._n_customers_prof = Profile(default_value=self._n_customers, data_type=int)

        self.Pl0 = Pl0
        self.Ql0 = Ql0

        self.init_params = init_params

        self.register(key='Ir', units='MW', tpe=float,
                      definition='Active power of the current component at V=1.0 p.u.', profile_name='Ir_prof')
        self.register(key='Ir1', units='MW', tpe=float,
                      definition='Active power of the phase 1 current component at V=1.0 p.u.', profile_name='Ir1_prof')
        self.register(key='Ir2', units='MW', tpe=float,
                      definition='Active power of the phase 2 current component at V=1.0 p.u.', profile_name='Ir2_prof')
        self.register(key='Ir3', units='MW', tpe=float,
                      definition='Active power of the phase 3 current component at V=1.0 p.u.', profile_name='Ir3_prof')
        self.register(key='Ii', units='MVAr', tpe=float,
                      definition='Reactive power of the current component at V=1.0 p.u.', profile_name='Ii_prof')
        self.register(key='Ii1', units='MVAr', tpe=float,
                      definition='Reactive power of the phase 1 current component at V=1.0 p.u.',
                      profile_name='Ii1_prof')
        self.register(key='Ii2', units='MVAr', tpe=float,
                      definition='Reactive power of the phase 2 current component at V=1.0 p.u.',
                      profile_name='Ii2_prof')
        self.register(key='Ii3', units='MVAr', tpe=float,
                      definition='Reactive power of the phase 3 current component at V=1.0 p.u.',
                      profile_name='Ii3_prof')
        self.register(key='G', units='MW', tpe=float,
                      definition='Active power of the impedance component at V=1.0 p.u.', profile_name='G_prof')
        self.register(key='G1', units='MW', tpe=float,
                      definition='Active power of the phase 1 impedance component at V=1.0 p.u.',
                      profile_name='G1_prof')
        self.register(key='G2', units='MW', tpe=float,
                      definition='Active power of the phase 2 impedance component at V=1.0 p.u.',
                      profile_name='G2_prof')
        self.register(key='G3', units='MW', tpe=float,
                      definition='Active power of the phase 3 impedance component at V=1.0 p.u.',
                      profile_name='G3_prof')
        self.register(key='B', units='MVAr', tpe=float,
                      definition='Reactive power of the impedance component at V=1.0 p.u.', profile_name='B_prof')
        self.register(key='B1', units='MVAr', tpe=float,
                      definition='Reactive power of the phase 1 impedance component at V=1.0 p.u.',
                      profile_name='B1_prof')
        self.register(key='B2', units='MVAr', tpe=float,
                      definition='Reactive power of the phase 2 impedance component at V=1.0 p.u.',
                      profile_name='B2_prof')
        self.register(key='B3', units='MVAr', tpe=float,
                      definition='Reactive power of the phase 3 impedance component at V=1.0 p.u.',
                      profile_name='B3_prof')
        self.register(key='n_customers', units='unit', tpe=int,
                      definition='Number of customers represented by this load', profile_name='n_customers_prof')

    @property
    def Ir_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ir_prof

    @Ir_prof.setter
    def Ir_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ir_prof = val
        elif isinstance(val, np.ndarray):
            self._Ir_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ir_prof')

    @property
    def Ir1_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ir1_prof

    @Ir1_prof.setter
    def Ir1_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ir1_prof = val
        elif isinstance(val, np.ndarray):
            self._Ir1_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ir1_prof')

    @property
    def Ir2_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ir2_prof

    @Ir2_prof.setter
    def Ir2_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ir2_prof = val
        elif isinstance(val, np.ndarray):
            self._Ir2_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ir2_prof')

    @property
    def Ir3_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ir3_prof

    @Ir3_prof.setter
    def Ir3_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ir3_prof = val
        elif isinstance(val, np.ndarray):
            self._Ir3_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ir3_prof')

    @property
    def Ii_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ii_prof

    @Ii_prof.setter
    def Ii_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ii_prof = val
        elif isinstance(val, np.ndarray):
            self._Ii_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ii_prof')

    @property
    def Ii1_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ii1_prof

    @Ii1_prof.setter
    def Ii1_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ii1_prof = val
        elif isinstance(val, np.ndarray):
            self._Ii1_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ii1_prof')

    @property
    def Ii2_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ii2_prof

    @Ii2_prof.setter
    def Ii2_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ii2_prof = val
        elif isinstance(val, np.ndarray):
            self._Ii2_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ii2_prof')

    @property
    def Ii3_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._Ii3_prof

    @Ii3_prof.setter
    def Ii3_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._Ii3_prof = val
        elif isinstance(val, np.ndarray):
            self._Ii3_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a Ii3_prof')

    @property
    def G_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._G_prof

    @G_prof.setter
    def G_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._G_prof = val
        elif isinstance(val, np.ndarray):
            self._G_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a G_prof')

    @property
    def G1_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._G1_prof

    @G1_prof.setter
    def G1_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._G1_prof = val
        elif isinstance(val, np.ndarray):
            self._G1_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a G1_prof')

    @property
    def G2_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._G2_prof

    @G2_prof.setter
    def G2_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._G2_prof = val
        elif isinstance(val, np.ndarray):
            self._G2_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a G2_prof')

    @property
    def G3_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._G3_prof

    @G3_prof.setter
    def G3_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._G3_prof = val
        elif isinstance(val, np.ndarray):
            self._G3_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a G3_prof')

    @property
    def B_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._B_prof

    @B_prof.setter
    def B_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._B_prof = val
        elif isinstance(val, np.ndarray):
            self._B_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a B_prof')

    @property
    def B1_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._B1_prof

    @B1_prof.setter
    def B1_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._B1_prof = val
        elif isinstance(val, np.ndarray):
            self._B1_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a B1_prof')

    @property
    def B2_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._B2_prof

    @B2_prof.setter
    def B2_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._B2_prof = val
        elif isinstance(val, np.ndarray):
            self._B2_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a B2_prof')

    @property
    def B3_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._B3_prof

    @B3_prof.setter
    def B3_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._B3_prof = val
        elif isinstance(val, np.ndarray):
            self._B3_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a B3_prof')

    @property
    def n_customers(self) -> int:
        """
        Return the number of customers
        """
        return self._n_customers

    @n_customers.setter
    def n_customers(self, val: int):
        """
        Set the number of customers
        :param val: value greater than 0
        """
        try:
            val2 = int(val)
            if val2 > 0:
                self._n_customers = val2
            else:
                print("There must be at least one customer right?")
        except ValueError as e:
            print(e)

    @property
    def n_customers_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._n_customers_prof

    @n_customers_prof.setter
    def n_customers_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._n_customers_prof = val
        elif isinstance(val, np.ndarray):
            self._n_customers_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into n_customers_prof')

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

            # P
            y = self.P_prof.toarray()
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_1.set_title('Active power', fontsize=14)
            ax_1.set_ylabel('MW', fontsize=11)
            df.plot(ax=ax_1)

            # Q
            y = self.Q_prof.toarray()
            df = pd.DataFrame(data=y, index=time, columns=[self.name])
            ax_2.set_title('Reactive power', fontsize=14)
            ax_2.set_ylabel('MVAr', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

            if show_fig:
                plt.show()

    def initialize_rms(self):
        if self.rms_model.empty():

            Ql = Var("Ql")
            Pl = Var("Pl")

            self.rms_model.model = Block(
                algebraic_eqs=[
                    Pl - self.Pl0, #TODO: consider that self.P/Q should be constant variables/objects, in order for us to create events
                    Ql - self.Ql0
                ],
                algebraic_vars=[Pl, Ql],
                init_eqs={},
                init_vars=[],
                init_params_eq={},
                parameters=[],
                external_mapping={
                    DynamicVarType.P: Pl,
                    DynamicVarType.Q: Ql
                }
            )
