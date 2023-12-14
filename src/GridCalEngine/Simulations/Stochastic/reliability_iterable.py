# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import numpy as np
from typing import Tuple
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit, compile_numerical_circuit_at
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.Simulations.driver_template import DriverTemplate
from GridCalEngine.basic_structures import Vec, IntVec


def staeady_state_probability(lbda: Vec, mu: Vec) -> Tuple[Vec, Vec]:
    """
    Probability of the component beign unavailable
    See: Power distriution system reliability p.67
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

    def __init__(self, grid: MultiCircuit):

        self.grid = grid

        # number of time steps
        self.nt = grid.get_time_number()

        # time index
        self.t_idx = 0

    def __iter__(self) -> "ReliabilityIterable":
        return self

    def __next__(self) -> IntVec:

        if self.nt == 0:  # no time steps, no fun
            print('No time steps :/')
            raise StopIteration

        # compile the time step
        nc = compile_numerical_circuit_at(self.grid, t_idx=self.t_idx)

        # compute the transition probabilities
        lbda = 1.0 / nc.branch_data.mttf
        mu = 1.0 / nc.branch_data.mttr
        p_up, p_dwn = staeady_state_probability(lbda=lbda, mu=mu)

        # determine the Markov states
        p = np.random.random(nc.nbr)
        br_active = (p > p_dwn).astype(int)

        # apply the transitioning states
        nc.branch_data.active = br_active

        # determine the next state
        if self.t_idx < (self.nt - 1):
            # advance to the next step
            self.t_idx += 1
        else:
            # raise StopIteration
            self.t_idx = 0  # restart

        return br_active
