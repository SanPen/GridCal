# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from typing import Tuple
import numba as nb
import numpy as np
from GridCalEngine.basic_structures import IntMat, Vec, Mat


@nb.njit(cache=True)
def compose_states(mttf: float, mttr: float, horizon: int, initially_working: bool = True):
    """
    Compose random states vector (on -> off -> on -> ...)
    :param mttf: Mean time to failure (h)
    :param mttr: Mean time to recovery (h)
    :param horizon: Time horizon (h)
    :param initially_working: is the component initially working?
    :return: Vector of states (size horizon) [1: on, 0: off]
    """
    active = np.zeros(int(horizon), dtype=nb.bool)

    if mttf == 0:
        return np.ones(int(horizon), dtype=nb.bool)

    if mttr == 0:
        return np.ones(int(horizon), dtype=nb.bool)

    if initially_working:
        # If it's working, first we simulate the failure, then the recovery
        factor_1 = mttf
        factor_2 = mttr
    else:
        # If it's not working, first we simulate the recovery, then the failure
        factor_1 = mttr
        factor_2 = mttf

    a: int = 0
    b: int = 0

    while b < horizon:

        # simulate failure
        duration = int(- mttf * np.log(np.random.rand()))
        b = a + duration
        if b > horizon:
            active[a:horizon] = 1
            return active
        else:
            active[a:b] = 1
        a = b

        # simulate recovery
        duration = int(- mttr * np.log(np.random.rand()))
        b = a + duration
        if b > horizon:
            active[a:horizon] = 0
            return active
        else:
            active[a:b] = 0
        a = b

    return active


@nb.njit(cache=True, parallel=True)
def generate_states_matrix(mttf: Vec, mttr: Vec, horizon: int, initially_working: bool = True):
    """
    Generate random states vector (on -> off -> on -> ...)
    :param mttf: Vector of Mean time to failure (h)
    :param mttr: Vector of Mean time to recovery (h)
    :param horizon: Time horizon (h)
    :param initially_working: is the component initially working?
    :return: matrix of states (size horizon, size mttf) [1: on, 0: off]
    """
    assert len(mttf) == len(mttr)

    n_elm = len(mttf)

    states = np.empty((horizon, n_elm), dtype=nb.bool)

    for k in nb.prange(n_elm):
        states[:, k] = compose_states(mttf[k], mttr[k], horizon, initially_working)

    return states


@nb.njit(cache=True)
def find_different_states(mat1: IntMat, mat2: IntMat):
    """
    Find different states
    :param mat1: Matrix 1 of states
    :param mat2: Matrix 1 of states
    :return: Array of states
    """
    assert mat1.shape == mat2.shape
    keep = np.zeros(mat1.shape[0], dtype=nb.bool)
    count = 0

    for t in range(mat1.shape[0]):
        diff = False
        k = 0
        while k < mat1.shape[1] and not diff:
            if mat1[t, k] != mat2[t, k]:
                diff = True
            k += 1

        if diff:
            keep[t] = True
            count += 1

    states = np.empty(count, dtype=nb.int64)
    n = 0
    for i, val in enumerate(keep):
        if val:
            states[n] = i
            n += 1

    return states


@nb.njit(cache=True)
def compute_loss_of_load(gen_pmax: Mat, load: Mat, dt: Vec):
    """
    Compute the loss of load
    :param gen_pmax: Matrix of available generation (MW)
    :param load: Matrix of load (MW)
    :param dt: Time step array (h)
    :return: loss of load values in MWh
    """
    assert gen_pmax.shape[0] == load.shape[0]

    nt = gen_pmax.shape[0]
    load_lost = 0
    for t in range(nt):
        max_gen_t = gen_pmax[t, :].sum()
        total_load_t = load[t, :].sum()

        if total_load_t > max_gen_t:
            load_lost += dt[t] * (total_load_t - max_gen_t)

    return load_lost


def get_transition_probabilities(lbda: Vec, mu: Vec) -> Tuple[Vec, Vec]:
    """
    Probability of the component being unavailable
    See: Power distribution system reliability p.67
    :param lbda: failure rate ( 1 / mttf)
    :param mu: repair rate (1 / mttr)
    :return: availability probability, unavailability probability
    """
    lbda2 = lbda * lbda
    mu2 = mu * mu
    p_unavailability = lbda2 / (lbda2 + 2.0 * lbda * mu + 2.0 * mu2)
    p_availability = 1.0 - p_unavailability

    return p_availability, p_unavailability


def compute_transition_probabilities(mttf: Vec, mttr: Vec,
                                     forced_mttf: None | float, forced_mttr: None | float) -> Tuple[Vec, Vec]:
    """
    Compute the transition probabilities
    :param mttf: Vector of mean-time-to-failures
    :param mttr: Vector of mean-time-to-recoveries
    :param forced_mttf: forced mttf value (used if not None)
    :param forced_mttr: forced mttr value (used if not None)
    :return: Probability of being up, Probability of being down
    """
    # compute the transition probabilities
    if forced_mttf is None:
        lbda = 1.0 / mttf
    else:
        lbda = 1.0 / np.full(len(mttf), forced_mttf)

    if forced_mttr is None:
        mu = 1.0 / mttr
    else:
        mu = 1.0 / np.full(len(mttr), forced_mttr)

    p_up, p_dwn = get_transition_probabilities(lbda=lbda, mu=mu)

    return p_up, p_dwn