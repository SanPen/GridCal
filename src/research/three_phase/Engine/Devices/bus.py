from research.three_phase.Engine.Devices.load import *
from research.three_phase.Engine.Devices.generator import *


class Bus:

    def __init__(self, name, number_of_phases, Vnom=10.0, is_slack=False, x=0, y=0):
        """
        Bus constructor
        :param number_of_phases: number of phases available
        :param Vnom: Line (L-L) nominal voltage in kV
        :param is_slack: set the bus as slack or not
        :param x: x position
        :param y: y position
        """

        self.name = name

        self.Vnom = Vnom

        self.number_of_phases = number_of_phases

        self.x = x

        self.y = y

        # vector marking the number of available phases
        # self.phases = np.zeros(self.number_of_phases, dtype=int)

        self.loads = list()

        self.generators = list()

        self.is_slack = is_slack

    def add_generator(self, elm: Generator):
        """
        Add generator
        :param elm: generator instance
        """
        if elm.number_of_phases > self.number_of_phases:
            raise Exception("The generator phases exceed the buses phases!")

        self.generators.append(elm)

    def add_load(self, elm: LoadSIY):
        """
        Add load
        :param elm: load instance
        """
        if elm.number_of_phases > self.number_of_phases:
            raise Exception("The load phases exceed the buses phases!")

        self.loads.append(elm)

    def apply_YISV(self, k, data, Sbase, n_phase):
        """
        Get the bus-connected values
        :param k: bus index in the circuit
        :param data: CircuitMatrixInputs instance
        :param Sbase: Circuit base power in MVA
        :param n_phase: Circuit number of phases
        :return: Y, I, S, V, bus type
        """
        vm = np.ones(n_phase, dtype=np.float)  # voltage module
        va = np.linspace(0, 2*np.pi, n_phase+1)[:n_phase]  # voltage angle  (0, 2pi/3, -2pi/3) generalized for n phases
        S = np.zeros(n_phase, dtype=np.complex)
        I = np.zeros(n_phase, dtype=np.complex)
        Y = np.zeros(n_phase, dtype=np.complex)

        # exponential load parameters
        P0 = np.zeros(n_phase, dtype=np.float)
        Q0 = np.zeros(n_phase, dtype=np.float)
        V0 = np.zeros(n_phase, dtype=np.float)
        exp_p = np.zeros(n_phase, dtype=np.float)
        exp_q = np.zeros(n_phase, dtype=np.float)

        # polynomial load parameters
        A = np.zeros(n_phase, dtype=np.float)
        B = np.zeros(n_phase, dtype=np.float)
        C = np.zeros(n_phase, dtype=np.float)

        # determine the bus type
        if self.is_slack:
            tpe = BusTypes.Ref
        else:
            if len(self.generators) > 0:
                tpe = BusTypes.PV
            else:
                tpe = BusTypes.PQ

        # traverse the connected loads
        n_exp = 0
        n_poly = 0
        for elm in self.loads:
            if elm.type == LoadTypes.ZIP:
                s_, i_, y_ = elm.getLP2d()
                S[elm.phases] -= s_[elm.phases]
                Y[elm.phases] -= y_[elm.phases]
                I[elm.phases] -= i_[elm.phases]

            elif elm.type == LoadTypes.Exponential:
                if n_exp >= 1:
                    raise Exception('Only one exponential load is allowed per node')

                P0, Q0, exp_p, exp_q, V0 = elm.getLP2d()
                n_exp += 1

            elif elm.type == LoadTypes.Polynomial:
                if n_poly >= 1:
                    raise Exception('Only one polynomial load is allowed per node')

                A[elm.phases], B[elm.phases], C[elm.phases] = elm.getLP2d()
                n_poly += 1

            else:
                raise Exception(elm.name + ': The load type is not supported')

        # traverse the connected generators
        for elm in self.generators:
            p_, v_ = elm.getLP2d()
            S[elm.phases] += p_[elm.phases]
            vm *= v_

        # Assign the values in the data structure
        data.Vbus[n_phase * k: n_phase * k + n_phase] = vm * np.exp(1j * va)
        data.Sbus[n_phase * k: n_phase * k + n_phase] += S / Sbase
        data.Ibus[n_phase * k: n_phase * k + n_phase] += I / Sbase
        data.Ybus_sh[n_phase * k: n_phase * k + n_phase] += Y / Sbase
        data.bus_types[n_phase * k: n_phase * k + n_phase] = tpe.value

        data.P0[n_phase * k: n_phase * k + n_phase] = P0 / Sbase
        data.Q0[n_phase * k: n_phase * k + n_phase] = Q0 / Sbase
        data.V0[n_phase * k: n_phase * k + n_phase] = V0
        data.exp_p[n_phase * k: n_phase * k + n_phase] = exp_p
        data.exp_q[n_phase * k: n_phase * k + n_phase] = exp_q

        data.A[n_phase * k: n_phase * k + n_phase] = A
        data.B[n_phase * k: n_phase * k + n_phase] = B
        data.C[n_phase * k: n_phase * k + n_phase] = C

    def __str__(self):
        return self.name

