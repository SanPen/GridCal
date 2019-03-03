"""
Experiments on the Delta-Wye configuration

Santiago Peñate Vera, 2018
"""

from research.three_phase.Engine.Devices.generator import *


def P2R(radii, angles):
    return radii * np.exp(1j*angles)


def R2P(x):
    return np.abs(x), np.angle(x)


def get_star(val):
    a = val * np.exp(0j)
    b = val * np.exp(np.deg2rad(120)*1j)
    c = val * np.exp(np.deg2rad(-120)*1j)
    return np.array([a, b, c])


def polar(vec):
    val = '\n'
    for i in range(3):
        val += str(np.abs(vec[i])) + '<' + str(np.angle(vec[i], True)) + "\n"
    return val


def experiment_1():
    """
    This experiment checks whether if the Delta-Star conversion is reversible.

    Result: It is only reversible when the Initial Start connection is balanced.
    If the Triangle is not equilateral, then the transformation is not reversible.

    """
    # Load in Delta with 140+70j kW connected in CA
    # The L-L array is [AB, BC, CA]
    SLN = get_star(10)

    print('SLN: ', polar(SLN))

    SLL = wye_to_delta(SLN)
    print('SLL: ', polar(SLL))

    SLN2 = delta_to_wye(SLL)
    print('SLN2: ', polar(SLN2))


def experiment_2():
    """
    This experiment checks if the Matrix D (star->delta transformation) has the inverse that is declares as D_dw

    Result: Yes D_dw is the inverse of D_wd

    Note: D_wd is singular, but the closes inverse is D_dw
    """
    D_wd = np.array([[1, -1, 0], [0, 1, -1], [-1, 0, 1]], dtype=np.complex)  # used in wye_to_delta
    D_dw = (1 / 3) * np.array([[1, 0, -1], [-1, 1, 0], [0, -1, 1]], dtype=np.complex)  # delta_to_wye

    D_dw2 = np.linalg.pinv(D_wd)

    print("\n\n")
    print(D_wd)
    print(D_dw)
    print(D_dw - D_dw2)  # check true


def experiment_3():
    """

    """
    # In L-L configuration the array is [AB, BC, CA]
    SLL = np.array([140+70j, 0, 0])
    print('SLL: ', SLL)

    SLN = delta_to_wye(SLL)
    print('SLN: ', SLN)



if __name__ == "__main__":

    experiment_1()

    experiment_2()
    #
    experiment_3()


