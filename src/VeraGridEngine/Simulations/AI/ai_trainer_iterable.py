# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import Union
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions, multi_island_pf_nc, PowerFlowResults
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Simulations.Reliability.reliability2 import compute_transition_probabilities
from VeraGridEngine.Simulations.Stochastic.stochastic_power_flow_input import StochasticPowerFlowInput
from VeraGridEngine.basic_structures import Logger


class AiIterable:
    """
    AI-ready power flow stochastic iterable
    """

    def __init__(self, grid: MultiCircuit,
                 forced_mttf: Union[None, float] = None,
                 forced_mttr: Union[None, float] = None,
                 pf_options=PowerFlowOptions(),
                 modify_injections: bool = True,
                 modify_branches_state: bool = True,
                 logger: Logger = Logger()):
        """

        :param grid: MultiCircuit
        :param forced_mttf: override the branches MTTF with this value
        :param forced_mttr: override the branches MTTR with this value
        """
        self.grid = grid

        self.logger = logger

        # declare the power flow options
        self.pf_options = pf_options

        self.modify_injections = modify_injections
        self.modify_branches_state = modify_branches_state

        # compile the time step
        nc = compile_numerical_circuit_at(self.grid, t_idx=None, logger=logger)

        # compute the transition probabilities
        self.p_up_branches, self.p_dwn_branches = compute_transition_probabilities(mttf=nc.passive_branch_data.mttf,
                                                                                   mttr=nc.passive_branch_data.mttr,
                                                                                   forced_mttf=forced_mttf,
                                                                                   forced_mttr=forced_mttr)

        self.p_up_gen, self.p_dwn_gen = compute_transition_probabilities(mttf=nc.generator_data.mttf,
                                                                         mttr=nc.generator_data.mttr,
                                                                         forced_mttf=forced_mttf,
                                                                         forced_mttr=forced_mttr)

        if not grid.has_time_series:
            raise ValueError("The grid must have time series declared!")

        self.mc_input = StochasticPowerFlowInput(self.grid)

        # compile the time step
        self.nc = compile_numerical_circuit_at(self.grid, t_idx=None, logger=self.logger)
        self.base_branch_active = self.nc.passive_branch_data.active.copy()

    def __iter__(self) -> "AiIterable":
        return self

    def __next__(self) -> PowerFlowResults:

        if self.modify_branches_state:
            # determine the Markov states
            p = np.random.random(self.nc.nbr)
            br_active = (p > self.p_dwn_branches).astype(int)

            # apply the transitioning states
            self.nc.passive_branch_data.active = br_active

        if self.modify_injections:
            # sample monte-carlo injections
            x = np.random.random(self.nc.nbus)
            Sbus = self.mc_input.get_at(x=x) / self.nc.Sbase

            pf_res = multi_island_pf_nc(nc=self.nc, options=self.pf_options, Sbus_input=Sbus)

        else:
            # just run without injections variation, and pick the ones from the numerical circuit
            pf_res = multi_island_pf_nc(nc=self.nc, options=self.pf_options)

        return pf_res

    def reset(self):
        """
        Reset the iterable
        """
        self.nc = compile_numerical_circuit_at(self.grid, t_idx=None, logger=self.logger)
        self.base_branch_active = self.nc.passive_branch_data.active.copy()

