# Copyright (c) 2018 Santiago Peñate Vera


from matplotlib import pyplot as plt
import numpy as np

import matplotlib.mlab as mlab
import math
from GridCal.Engine.calculation_engine import *

np.set_printoptions(precision=8, suppress=True, linewidth=320)


def plot_normal(ax, arr):
    """

    :param ax:
    :param mu:
    :param variance:
    :return:
    """
    mu = arr.mean()
    variance = arr.var()
    sigma = math.sqrt(variance)
    x = np.linspace(mu - 6 * sigma, mu + 6 * sigma, 100)

    if mu != 0 and sigma != 0:
        ax.plot(x, mlab.normpdf(x, mu, sigma))


def analize_impedances(circuit: Circuit):

    properties = ['R', 'X', 'G', 'B']
    p = len(properties)
    n = len(circuit.branches)
    vals = zeros((n, p))

    for i, branch in enumerate(circuit.branches):

        for j in range(p):
            vals[i, j] = getattr(branch, properties[j])

    axs = [None] * p
    fig = plt.figure(figsize=(16, 10))
    k = int(math.sqrt(p))
    for j in range(p):

        x = vals[:, j]
        mu = x.mean()
        variance = x.var()
        sigma = math.sqrt(variance)
        r = (mu - 6 * sigma, mu + 6 * sigma)

        # print checks
        l = np.where(x < r[0])[0]
        u = np.where(x > r[1])[0]

        print(properties[j], r, '\n\t', l, '\n\t', u)

        # plot
        axs[j] = fig.add_subplot(k, k, j + 1)
        axs[j].hist(x, bins=100, range=r, density=None, weights=None,
                    cumulative=False, bottom=None, histtype='bar',
                    align='mid', orientation='vertical', normed=True)
        axs[j].plot(x, zeros(n), 'o')
        axs[j].set_title(properties[j])

########################################################################################################################
#  MAIN
########################################################################################################################
if __name__ == "__main__":


    grid = MultiCircuit()
    # grid.load_file('lynn5buspq.xlsx')
    # grid.load_file('IEEE30.xlsx')
    # grid.load_file('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE 145 Bus.xlsx')
    grid.load_file('/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Europe winter 2009 model.xlsx')
    grid.compile()

    circuit = grid.circuits[0]

    analize_impedances(circuit)
    plt.show()