import numpy as np

from research.three_phase.Engine.general import *


class Generator:

    def __init__(self, name, P, v=1.0, conn=Phases.ABC, conn_type=Connection.Delta):
        """
        Generator constructor
        :param name: name of the element
        :param P: active power array in MW
        :param v: voltage set point (single value)
        :param conn: phases of connection
        :param conn_type: type of connection (Wye or Delta)
        """

        self.name = name

        # active power in MW
        self.P = P

        # voltage set point in per unit
        self.v = v

        # connection type
        self.conn_type = conn_type

        # vector of the used phases
        self.phases = np.array(conn)

        # number of phases
        self.number_of_phases = len(self.phases)

        if self.conn_type != Connection.PositiveSequence:
            if len(self.P) != 3:
                raise Exception(self.name + ': The power array must have 3 values '
                                            'since the connection implied a 3-phase system')
            else:
                pass
        else:
            pass

    def get_values(self):
        """
        Returns the wye-connected power and the voltage set point
        :return: Wye-connected power
        """
        if self.number_of_phases == 3:
            if self.conn_type == Connection.Wye:
                return self.P, self.v
            else:
                return delta_to_wye(self.P), self.v
        else:
            return self.P, self.v

