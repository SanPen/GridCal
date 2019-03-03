from research.three_phase.Engine.Devices.branch import *
from research.three_phase.Engine.Devices.bus import *


class LineTypeSeq:

    def __init__(self, name, Z_SEQ, Ysh_SEQ):
        """
        3-phase branch defined from the positive sequence elements
        :param name: name of the line type object
        :param Z_SEQ: vector with the sequence impedances in Ohm/km
        :param Ysh_SEQ: vector with the shunt sequence impedances in Siemens/km
        """
        self.name = name

        self.number_of_phases = 3

        self.z_SEQ = Z_SEQ

        self.ysh_SEQ = Ysh_SEQ

    def getABCD(self, line_length, y_base):
        """
        get the line ABCD parameters

        | If |   | A  B |   | Vf |
        |    | = |      | * |    |
        | It |   | C  D |   | Vt |

        :param line_length: line length in km
        :param y_base: base admittance in Siemens
        """
        y = seq_to_abc(1.0 / (self.z_SEQ * line_length))
        y_sh = seq_to_abc(self.ysh_SEQ * line_length)

        As = y
        Ds = y
        A = y + y_sh / 2.0
        B = - y
        C = - y
        D = y + y_sh / 2.0

        return A / y_base, B / y_base, C / y_base, D / y_base, As / y_base, Ds / y_base


class LineTypeABC:

    def __init__(self, name, phases, zABC, ysh_ABC):
        """
        Rectangular full 3-phase branch
        :param name: Name of the line type
        :param phases: Number of phases
        :param zABC: phases x phases impedance matrix in Ohm/km
        :param ysh_ABC: phases x phases shunt admittance matrix in Siemens/km
        """
        self.name = name

        self.number_of_phases = phases

        self.zABC = zABC

        self.ysh_ABC = ysh_ABC

    def getABCD(self, line_length, y_base):
        """
        get the line ABCD parameters

        | If |   | A  B |   | Vf |
        |    | = |      | * |    |
        | It |   | C  D |   | Vt |

        :param line_length: line length in km
        :param y_base: Base admittance in Siemens
        """
        Yseries = np.linalg.inv(self.zABC * line_length)

        As = Yseries
        Ds = Yseries
        A = Yseries #+ self.ysh_ABC * line_length / 2.0
        B = - Yseries
        C = - Yseries
        D = Yseries #+ self.ysh_ABC * line_length / 2.0

        return A / y_base, B / y_base, C / y_base, D / y_base, As / y_base, Ds / y_base


class Line(Branch):

    def __init__(self, name, line_type, bus_from: Bus, bus_to: Bus,
                 conn_from=Phases.ABC, conn_to=Phases.ABC, length=1.0, rating=1e-6):
        """
        n_phase line
        :param name: name of the line
        :param bus_from: bus from object
        :param bus_to: bus to object
        :param conn_from: vector of connection in the bus from i.e. [0, 1, 2]
        :param conn_to: vector of connection in the bus to, i.e. [0, 1, 2]
        :param line_type: line type
        :param length: line length in km
        :param rating: transformer rating in MVA
        """
        self.name = name

        self.f = bus_from

        self.t = bus_to

        self.rating = rating

        self.line_type = line_type

        self.number_of_phases = line_type.number_of_phases

        self.length = length

        self.phases_from = np.array(conn_from)

        self.phases_to = np.array(conn_to)

        # check connection compatibility
        if len(self.phases_from) != len(self.phases_to):
            raise Exception('Wrong phases')

        if len(self.phases_from) != self.line_type.number_of_phases:
            raise Exception('The number of phases of the line type does not match the specified connection phases')

        if (self.f.Vnom / self.t.Vnom) > 1.05 or (self.t.Vnom / self.f.Vnom) > 1.05:
            raise Exception('The line ' + self.name +
                            ' is connected between buses which nominal voltage differ more than a 5%')

    def get_ABCD(self, Sbase):
        """
        get the ABCD parameters

        | If |   | A  B |   | Vf |
        |    | = |      | * |    |
        | It |   | C  D |   | Vt |
        :param Sbase: Circuit base power in MVA
        """

        # compute the base admittance
        y_base = Sbase / (self.f.Vnom * self.f.Vnom)

        return self.line_type.getABCD(self.length, y_base)

    def __str__(self):
        return self.name
