import GridCalEngine.api as gce
import pandas as pd
from scipy import sparse
import numpy as np
import timeit
from jax import grad, hessian
import jax.numpy as jnp
import random
import math
from GridCalEngine.basic_structures import CxVec, Vec
from acopf_functions import *


def import_grid(nc):
    return


def grid_parameters(nc:gce.NumericalCircuit):

    #Number of buses
    #Number of lines

    N = nc.nbus
    L = nc.nbr

    #Line connections in FROM topology
    LINES = []
    for l in range(L):
        LINES.append((nc.branch_data.F, nc.branch_data.T))

    #If nothing is specified, power limits are set to 0, voltages are ser to 1 (nominal) and maximum power allowed
    # through a line is set to infinite.

    P_U = np.zeros(N)
    P_L = np.zeros(N)
    Q_U = np.zeros(N)
    Q_L = np.zeros(N)
    V_U = np.ones(N)
    V_L = np.ones(N)

    #S_MAX = np.array([99999]*L)

    for n in N:
        V_U[n] = nc.bus_data.Vmax[n]
        V_L[n] = nc.bus_data.Vmin[n]

    #Generator limits
    GEN_BUSES = nc.generator_data.get_bus_indices()
    for b in GEN_BUSES:
        P_U[b] = nc.generator_data.pmax[b]
        P_L[b] = nc.generator_data.pmin[b]
        Q_U[b] = nc.generator_data.qmax[b]
        Q_L[b] = nc.generator_data.qmin[b]

    #Branch limits
    S_MAX = nc.branch_rates()
    DELTA_MAX = [0.5] * L

    #Load parameters
    PD = np.zeros(N)
    QD = np.zeros(N)
    LOAD_BUSES = nc.load_data.get_bus_indices()

    for b in LOAD_BUSES:
        PD[b] = np.real(nc.load_data.S)
        QD[b] = np.real(nc.load_data.S)

    return N, L, LINES, V_U, V_L, P_U, P_L, Q_U, Q_L, PD, QD, SMAX, DELTA_MAX


def line_imp_adm(nc, LINES):

    Y_MATRIX = nc.YBus

    return Y_MATRIX


def indexing():



    return


def problem_sizing():

    NV = 0
    NE = 0
    NI = 0

    return
