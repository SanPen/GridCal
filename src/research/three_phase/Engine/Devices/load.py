import numpy as np

from research.three_phase.Engine.general import *


class Load:
    """
    Load class template
    """
    def get_values(self):
        pass


class LoadSIY(Load):

    def __init__(self, name, S, I, Y,
                 conn=Phases.ABC,
                 conn_type=Connection.Delta):
        """
        Load constructor for the S-I-Y models (variant of the Z-I-P model)
        :param name: name of the element
        :param S: vector of complex power in MW + jMVA
        :param I: vector of complex current in MW + jMVA
        :param Y: vector of complex admittance in MW + jMVA
        :param conn: phases of connection
        :param conn_type: type of connection (Wye or Delta)

        If the connection is Delta the vectors contain [AB, BC, CA]
        If the connection is wye the vectors contain [AN, BN, CN]
        """

        self.name = name

        # type of the load object
        self.type = LoadTypes.ZIP

        # power in MW + jMVA
        self.S = S

        # current in MW + jMVA
        self.I = I

        # admittance in MW + jMVA
        self.Y = Y

        # connection type
        self.conn_type = conn_type

        # vector of the used phases
        self.phases = np.array(conn)

        # number of phases
        self.number_of_phases = len(self.phases)

        # if self.conn_type != Connection.PositiveSequence:
        #     if len(self.S) != len(self.phases):
        #         raise Exception(self.name + ': The power array does not match the specified phases')
        #
        #     if len(self.I) != len(self.phases):
        #         raise Exception(self.name + ': The current array does not match the specified phases')
        #
        #     if len(self.Y) != len(self.phases):
        #         raise Exception(self.name + ': The admittance array does not match the specified phases')
        # else:
        #     if self.number_of_phases != 1:
        #         raise Exception(self.name + ': Positive sequence requires to have exactly one phase: 0')

    def get_values(self):
        """
        Returns the wye-connected power, current and admittance
        :return: Wye-connected power
        """
        if self.number_of_phases == 3:
            if self.conn_type == Connection.Wye:
                return self.S, self.I, self.Y
            else:
                return delta_to_wye(self.S), delta_to_wye(self.I), delta_to_wye(self.Y)
        else:
            return self.S, self.I, self.Y


class LoadExp(Load):

    def __init__(self, name, P0, Q0, V0, exp_p, exp_q,
                 conn=Phases.ABC,
                 conn_type=Connection.Delta):
        """
        Load constructor for the exponential load model
        P = P0 * (V / V0)^exp_p
        Q = Q0 * (V / V0)^exp_q
        :param name: name of the element
        :param P0: Per unit active power at the per unit voltage V0  (vector of values per phase)
        :param Q0: Per unit reactive power at the per unit voltage V0 (vector of values per phase)
        :param V0: Nominal voltage in per unit [typical value: 1] (vector of values per phase)
        :param exp_p: active power exponent [typical values 0.4~0.8] (vector of values per phase)
        :param exp_q: reactive power exponent [typical values 2~3](vector of values per phase)
        :param conn: phases of connection
        :param conn_type: type of connection (Wye or Delta)

        If the connection is Delta the vectors contain [AB, BC, CA]
        If the connection is wye the vectors contain [AN, BN, CN]
        """

        self.name = name

        # type of the load object
        self.type = LoadTypes.Exponential

        # load model parameters
        self.P0 = P0
        self.Q0 = Q0
        self.V0 = V0
        self.exp_p = exp_p
        self.exp_q = exp_q

        # connection type
        self.conn_type = conn_type

        # vector of the used phases
        self.phases = np.array(conn)

        # number of phases
        self.number_of_phases = len(self.phases)

    def get_values(self):
        """
        Returns the wye-connected power, current and admittance
        :return: P0, Q0, ExpP, ExpQ, V0 to conform the exponential model
        """

        if self.number_of_phases == 3:
            if self.conn_type == Connection.Wye:
                return self.P0, self.Q0, self.exp_p, self.exp_p, self.V0
            else:
                return delta_to_wye(self.P0), delta_to_wye(self.Q0), self.exp_p, self.exp_p, self.V0
        else:
            return self.P0, self.Q0, self.exp_p, self.exp_p, self.V0

