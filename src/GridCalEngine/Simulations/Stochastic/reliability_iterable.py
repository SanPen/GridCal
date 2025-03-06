# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import Tuple, Union
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions, multi_island_pf_nc, PowerFlowResults
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from GridCalEngine.basic_structures import Vec, IntVec,Logger


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


class ReliabilityIterable:
    """
    RealTimeStateEnumeration
    """

    def __init__(self, grid: MultiCircuit,
                 forced_mttf: Union[None, float] = None,
                 forced_mttr: Union[None, float] = None,
                 logger: Logger = Logger()):
        """

        :param grid: MultiCircuit
        :param forced_mttf: override the branches MTTF with this value
        :param forced_mttr: override the branches MTTR with this value
        """
        self.grid = grid

        # number of time steps
        self.nt = grid.get_time_number()

        # time index
        self.t_idx = 0

        self.logger = logger

        # declare the power flow options
        self.pf_options = PowerFlowOptions()

        # compile the time step
        nc = compile_numerical_circuit_at(self.grid, t_idx=None, logger=logger)

        # compute the transition probabilities
        if forced_mttf is None:
            lbda = 1.0 / nc.passive_branch_data.mttf
        else:
            lbda = 1.0 / np.full(nc.nbr, forced_mttf)

        if forced_mttr is None:
            mu = 1.0 / nc.passive_branch_data.mttr
        else:
            mu = 1.0 / np.full(nc.nbr, forced_mttr)

        self.p_up, self.p_dwn = get_transition_probabilities(lbda=lbda, mu=mu)

    def __iter__(self) -> "ReliabilityIterable":
        return self

    def __next__(self) -> Tuple[IntVec, PowerFlowResults]:

        if self.nt == 0:  # no time steps, no fun
            print('No time steps :/')
            raise StopIteration

        # compile the time step
        nc = compile_numerical_circuit_at(self.grid, t_idx=self.t_idx, logger=self.logger)

        # determine the Markov states
        p = np.random.random(nc.nbr)
        br_active = (p > self.p_dwn).astype(int)

        # apply the transitioning states
        nc.passive_branch_data.active = br_active

        pf_res = multi_island_pf_nc(nc=nc, options=self.pf_options)

        # determine the next state
        if self.t_idx < (self.nt - 1):
            # advance to the next step
            self.t_idx += 1
        else:
            # raise StopIteration
            self.t_idx = 0  # restart

        return br_active, pf_res
