from enum import Enum
import numpy as np


class BusTypes(Enum):
    Ref = 0,
    PQ = 1,
    PV = 2


class Connection(Enum):
    Delta = 0,  # Delta connection
    Wye = 1,  # Wye (Star) connection isolated from ground
    WyeG = 2  # Wye (Star) connection connected from ground
    PositiveSequence = 3  # When running a positive sequence the connection does not matter


class LoadTypes(Enum):
    ZIP = 0,
    Exponential = 1,
    Polynomial = 2


class Phases:
    ABC = [0, 1, 2]
    ACB = [0, 2, 1]
    CBA = [2, 1, 0]
    A = [0]
    B = [1]
    C = [2]
    AB = [0, 1]
    BA = [1, 0]
    AC = [0, 2]
    CA = [2, 0]
    BC = [1, 2]
    CB = [2, 1]


class PowerFlowMethods(Enum):
    GaussSeidel = 1,
    NewtonRaphson = 2,
    LevenbergMarquardt = 3,
    LinearAC = 4,
    GaussRaphson = 5,
    ZMatrix = 6


def seq_to_abc(seq):
    """
    Convert sequence vector to ABC full matrix
    Kersting p.136 / Computer Analysis of power systems p. 43
    :param seq: vector of the 0, 1, 2 sequence components
    :return: 3x3 matrix
    """

    if len(seq) == 2:
        k1 = (2.0 * seq[1] + seq[0]) / 3.0
        k2 = (seq[0] - seq[1]) / 3.0
        return np.array([[k1, k2, k2], [k2, k1, k2], [k2, k2, k1]])
    elif len(seq) == 3:
        a = np.exp(2j * np.pi / 3)
        a2 = a * a
        k1 = seq[0] + seq[1] + seq[2]
        k2 = seq[0] + a * seq[1] + a2 * seq[2]
        k3 = seq[0] + a2 * seq[1] + a * seq[2]
        return np.array([[k1, k2, k3], [k3, k1, k2], [k2, k3, k1]])


def wye_to_delta(vector):
    """
    Transform Wye connection to Delta connection
    :param vector: vector of 3 values
    :return: Delta connected values
    """
    D = np.array([[1, -1, 0], [0, 1, -1], [-1, 0, 1]])
    return D.dot(vector)


def delta_to_wye(vector):
    """
    Transform Delta connection to Wye connection
    :param vector: vector of 3 values
    :return: Wye connected values
    """
    D = (1 / 3) * np.array([[1, 0, -1], [-1, 1, 0], [0, -1, 1]])
    return D.dot(vector)

