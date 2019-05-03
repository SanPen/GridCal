from research.three_phase.Engine.Devices.branch import *
from research.three_phase.Engine.Devices.bus import *


class TransformerType1p:

    def __init__(self, name, conn_f: Connection, conn_t: Connection, r, x,  Vf_rate, Vt_rate, rating=1e-6):
        """
        Single phase transformer constructor
        :param conn_f: Connection type at the from bus
        :param conn_t: Connection type at the to bus
        :param r: leakage resistance in per unit
        :param x: leakage reactance in per unit
        :param Vf_rate: Voltage rate at the "from" side in kV
        :param Vt_rate: Voltage rate at the "to" side in kV
        :param rating: Power rating in MVA
        """

        self.name = name

        # from-bus connection
        self.conn_f = conn_f

        # to-bus connection
        self.conn_t = conn_t

        # voltage rate at the from side
        self.Vf = Vf_rate

        # voltage rate at the to side
        self.Vt = Vt_rate

        # power rating in MVA
        self.Srate = rating

        # resistance
        self.r = r

        # reactance
        self.x = x

        self.number_of_phases = 1

    def get_ABCD(self, tap_f=1.0, tap_t=1.0):
        """
        ABCD parameters of a single-phase transformer depending on the connections
        Reference: Load Flow Optimization and Optimal Power Flow - J.C. Das, pag 332 (2017)

        | If |   | A  B |   | Vf |
        |    | = |      | * |    |
        | It |   | C  D |   | Vt |

        :param tap_f: tap value at the from side
        :param tap_t:  tap value at the to side
        :return: A, B, C, D parameters (float values not matrices)
        """

        yt = 1.0 / (self.r + 1j * self.x)

        # tap changer coefficients
        ka = tap_f * tap_f
        kb = tap_f * tap_t
        kc = tap_t * tap_f
        kd = tap_t * tap_t

        return yt / ka, -yt / kb, -yt / kc, yt / kd


class TransformerType3p:

    def __init__(self, name, conn_f: Connection, conn_t: Connection, r, x, Vf_rate, Vt_rate, rating=1e-6):
        """
        Three-phase transformer type
        :param conn_f: Connection type at the from bus
        :param conn_t: Connection type at the to bus
        :param r: leakage resistance in per unit
        :param x: leakage reactance in per unit
        :param Vf_rate: Voltage rate at the "from" side in kV
        :param Vt_rate: Voltage rate at the "to" side in kV
        :param rating: power rating in MVA
        """

        self.name = name

        # from-bus connection
        self.conn_f = conn_f

        # to-bus connection
        self.conn_t = conn_t

        # voltage rate at the from side
        self.Vf = Vf_rate

        # voltage rate at the to side
        self.Vt = Vt_rate

        # power rating in MVA
        self.Srate = rating

        self.number_of_phases = 3

        # resistance
        self.r = r

        # reactance
        self.x = x

    def get_ABCD(self, tap_f=1.0, tap_t=1.0):
        """
        ABCD parameters of a three-phase transformer depending on the connections
        Reference: Load Flow Optimization and Optimal Power Flow - J.C. Das, pag 332 (2017)

        | If |   | A  B |   | Vf |
        |    | = |      | * |    |
        | It |   | C  D |   | Vt |

        :param tap_f: tap value at the from side
        :param tap_t: tap value at the to side
        :return: A, B, C, D parameters (4 matrices of 3x3)
        """

        # single-phase transformer admittance
        yt = 1.0 / (self.r + 1j * self.x)

        # fundamental sub matrices
        YI = np.array([[yt, 0, 0], [0, yt, 0], [0, 0, yt]])
        YII = (1 / 3) * np.array([[2 * yt, -yt, -yt], [-yt, 2 * yt, -yt], [-yt, -yt, 2 * yt]])
        YIII = (1 / np.sqrt(3)) * np.array([[-yt, yt, 0], [0, -yt, yt], [yt, 0, -yt]])

        # tap changer coefficients
        ka = tap_f * tap_f
        kb = tap_f * tap_t
        kc = tap_t * tap_f
        kd = tap_t * tap_t

        if self.conn_f == Connection.WyeG and self.conn_t == Connection.WyeG:

            # YI, YI, -YI, -YI = A, D, B, C
            A, B, C, D = YI / ka, -YI / kb, -YI / kc, YI / kd

        elif self.conn_f == Connection.WyeG and self.conn_t == Connection.Wye:

            # YII, YII, -YII, -YII = A, D, B, C
            A, B, C, D = YII / ka, -YII / kb, -YII / kc, YII / kd

        elif self.conn_f == Connection.Wye and self.conn_t == Connection.WyeG:

            # YII, YII, -YII, -YII = A, D, B, C
            A, B, C, D = YII / ka, -YII / kb, -YII / kc, YII / kd

        elif self.conn_f == Connection.Wye and self.conn_t == Connection.Wye:

            # YII, YII, -YII, -YII = A, D, B, C
            A, B, C, D = YII / ka, -YII / kb, -YII / kc, YII / kd

        elif self.conn_f == Connection.WyeG and self.conn_t == Connection.Delta:

            # YI, YII, YIII, YIII.transpose() = A, D, B, C
            A, B, C, D = YI / ka, YIII / kb, YIII.transpose() / kc, YII / kd

        elif self.conn_f == Connection.Wye and self.conn_t == Connection.Delta:

            # YII, YII, YIII, YIII.transpose() = A, D, B, C
            A, B, C, D = YII / ka, YIII / kb, YIII.transpose() / kc, YII / kd

        elif self.conn_f == Connection.Delta and self.conn_t == Connection.Wye:

            # YII, YIII, YIII.transpose(), YIII = A, D, B, C
            A, B, C, D = YII / ka, YIII.transpose() / kb, YIII / kc, YIII / kd

        elif self.conn_f == Connection.Delta and self.conn_t == Connection.WyeG:

            # YII, YII, YIII.transpose(), YIII = A, D, B, C
            A, B, C, D = YII / ka, YIII.transpose() / kb, YIII / kc, YII / kd

        elif self.conn_f == Connection.Delta and self.conn_t == Connection.Delta:

            # YII, YII, -YII, -YII = A, D, B, C
            A, B, C, D = YII / ka, -YII / kb, -YII / kc, YII / kd

        else:
            raise Exception('Transformer connections not understood')

        return A, B, C, D, A, D


class Transformer(Branch):

    def __init__(self, name, transformer_type, bus_from: Bus, bus_to: Bus,
                 conn_from=Phases.ABC, conn_to=Phases.ABC):
        """
        Model of a three-phase transformer
        :param name: name of the line
        :param transformer_type: transformer type object
        :param bus_from: bus from object
        :param bus_to: bus to object
        :param conn_from: vector of connection in the bus from i.e. [0, 1, 2]
        :param conn_to: vector of connection in the bus to, i.e. [0, 1, 2]
        :param rating: transformer rating in MVA
        """
        self.name = name

        self.f = bus_from

        self.t = bus_to

        self.tap_f = 1.0

        self.tap_t = 1.0

        self.rating = transformer_type.Srate

        self.transformer_type = transformer_type

        self.number_of_phases = transformer_type.number_of_phases

        self.phases_from = conn_from

        self.phases_to = conn_to

        # check connection compatibility
        if len(self.phases_from) != len(self.phases_to):
            raise Exception('Wrong phases')

        if len(self.phases_from) != self.transformer_type.number_of_phases:
            raise Exception('The number of phases of the line type do not match the specified connection phases')

        if self.f.Vnom != self.transformer_type.Vf:
            raise Exception(self.name + ':The transformer rated voltage at the from side does not '
                                        'match the bus rated voltage')

        if self.t.Vnom != self.transformer_type.Vt:
            raise Exception(self.name + ':The transformer rated voltage at the to side does not '
                                        'match the bus rated voltage')

    def get_ABCD(self, Sbase):
        """
        get the ABCD parameters
        | If |   | A  B |   | Vf |
        |    | = |      | * |    |
        | It |   | C  D |   | Vt |

        :param Sbase: Base power in MVA (not used, but kept form interface compatibility)
        """
        return self.transformer_type.get_ABCD(self.tap_f, self.tap_t)

    def __str__(self):
        return self.name

