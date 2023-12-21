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
from typing import Tuple, Optional
import numpy as np
import gym
from gym import spaces
from gym.core import ObsType
from GridCalEngine.api import *
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions, multi_island_pf_nc, PowerFlowResults


class GridCalEnv(gym.Env):
    """
    Custom Environment for simulating electrical grid operation using GridCal and OpenAI Gym
    """

    metadata = {'render.modes': ['human']}

    def __init__(self, grid: MultiCircuit, forced_mttf=10.0, forced_mttr=1.0):
        """

        :param grid: MultiCircuit
        :param forced_mttf: override the branches MTTF with this value
        :param forced_mttr: override the branches MTTR with this value
        """
        super(GridCalEnv, self).__init__()

        self.grid: MultiCircuit = grid

        # number of time steps
        self.nt = grid.get_time_number()

        # time index
        self.t_idx = 0

        # declare the power flow options
        self.pf_options = PowerFlowOptions()

        # compile the time step
        nc = compile_numerical_circuit_at(self.grid, t_idx=None)

        # initialize the last status
        self.last_status = nc.branch_data.active.copy()

        # compute the transition probabilities
        lbda = 1.0 / nc.branch_data.mttf if forced_mttf is None else 1.0 / np.full(nc.nbr, forced_mttf)
        mu = 1.0 / nc.branch_data.mttr if forced_mttr is None else 1.0 / np.full(nc.nbr, forced_mttr)
        self.p_up, self.p_dwn = get_transition_probabilities(lbda=lbda, mu=mu)

        # Define action and observation space
        # Action space: Assuming binary actions for each branch (on/off)
        self.action_space = spaces.MultiBinary(nc.nbr)

        # Observation space: Assuming observations include voltages at each bus
        # Modify this based on the specific details of your grid and what you want the AI to observe
        self.observation_space = spaces.Box(low=0, high=np.inf, shape=(nc.nbus,), dtype=np.float32)

        # Initialize state
        self.state = None
        self.reset()

    def step(self, action) -> Tuple[ObsType, float, bool, bool, dict]:
        """
        Run one timestep of the environment's dynamics.

        When end of episode is reached, you are responsible for calling :meth:`reset` to reset this environment's state.
        Accepts an action and returns either a tuple `(observation, reward, terminated, truncated, info)`.

        Args:
            action (ActType): an action provided by the agent

        Returns:
            observation (object): this will be an element of the environment's :attr:`observation_space`.
                This may, for instance, be a numpy array containing the positions and velocities of certain objects.
            reward (float): The amount of reward returned as a result of taking the action.
            terminated (bool): whether a `terminal state` (as defined under the MDP of the task) is reached.
                In this case further step() calls could return undefined results.
            truncated (bool): whether a truncation condition outside the scope of the MDP is satisfied.
                Typically a timelimit, but could also be used to indicate agent physically going out of bounds.
                Can be used to end the episode prematurely before a `terminal state` is reached.
            info (dictionary): `info` contains auxiliary diagnostic information
                (helpful for debugging, learning, and logging).
                This might, for instance, contain: metrics that describe the agent's performance state, variables
                that are hidden from observations, or individual reward terms that are combined to produce the
                total reward. It also can contain information that distinguishes truncation and termination, however
                this is deprecated in favour of returning two booleans, and will be removed in a future version.
        """

        # compile the time step
        nc = compile_numerical_circuit_at(self.grid, t_idx=self.t_idx)

        # regardless of the profile branch status, set the status of the simulation
        nc.branch_data.active = self.last_status

        # Apply action - switch branches on/off based on action
        # Note: This is a simplified representation. The actual implementation
        # would depend on how the grid responds to these actions
        for i, branch_status in enumerate(action):
            nc.branch_data.active[i] = int(branch_status)

        # Simulate one step in the environment
        # This would involve running a power flow simulation for the current grid state
        pf_results = multi_island_pf_nc(nc=nc, options=self.pf_options)

        # determine the Markov states
        p = np.random.random(nc.nbr)
        br_active = (p > self.p_dwn).astype(int)

        # apply the transitioning states
        nc.branch_data.active = br_active
        self.last_status = br_active

        # determine the next state
        if self.t_idx < (self.nt - 1):
            # advance to the next step
            self.t_idx += 1
        else:
            # raise StopIteration
            self.t_idx = 0  # restart

        # Calculate reward
        # Reward function needs to be defined based on the goals (e.g., stability, efficiency)
        reward = self.calculate_reward(nc=nc, pf_results=pf_results)

        # Check if simulation is done (based on your criteria)
        done = self.is_done(nc=nc, pf_results=pf_results)

        # do not truncate...
        truncated = False

        # Set placeholder for info (additional data you might want to track)
        info = {}

        # Update state with new observations
        self.state = self.last_status

        return self.state, reward, done, truncated, info

    def reset(self,
              *,
              seed: Optional[int] = None,
              options: Optional[dict] = None) -> Tuple[ObsType, dict]:
        """

        :param seed:
        :param options:
        :return:
        """
        # Reset the environment to an initial state
        # This might involve setting the grid to a default state
        # and running an initial power flow simulation

        # time index
        self.t_idx = 0

        # declare the power flow options
        self.pf_options = PowerFlowOptions()

        # compile the time step
        nc = compile_numerical_circuit_at(self.grid, t_idx=None)

        # initialize the last status
        self.last_status = nc.branch_data.active.copy()

        # Simulate one step in the environment
        # This would involve running a power flow simulation for the current grid state
        pf_results = multi_island_pf_nc(nc=nc, options=self.pf_options)

        # TODO: is it?
        self.state = self.last_status

        return self.state

    def render(self, mode='human', close=False):
        # Render the environment to the screen or other interface
        # This could be as simple as printing state information, or more complex like a graphical display
        print(f"Current State: {self.state}")

    def calculate_reward(self, nc: NumericalCircuit, pf_results: PowerFlowResults) -> float:
        """
        Compute the reward
        :param nc: NumericalCircuit
        :param pf_results: PowerFlowResults
        :return: reward value
        """
        reward = 0.0

        # Constants
        Overload_Threshold = 1.0  # loading factor threshold for overloading

        # Reward for maintaining voltage within limits
        vm = np.abs(pf_results.voltage)
        voltage_reward = np.sum(nc.bus_data.Vmin < vm < nc.bus_data.Vmax)
        reward += voltage_reward

        # Penalize voltage deviations
        voltage_penalty = nc.nbus - voltage_reward  # the opposite
        reward -= voltage_penalty

        # Penalize overloading
        overload_penalty = sum(pf_results.loading.real > 1.0)
        reward -= overload_penalty

        return reward

    def is_done(self, nc: NumericalCircuit, pf_results: PowerFlowResults) -> bool:
        """
        Check if the stuff is done
        :param nc: NumericalCircuit
        :param pf_results: PowerFlowResults
        :return: Stopping condition
        """
        vm = np.abs(pf_results.voltage)
        over_idx = np.where(vm > nc.bus_data.Vmax)[0]
        under_idx = np.where(vm < nc.bus_data.Vmin)[0]
        overload_idx = np.where(np.abs(pf_results.loading.real) > nc.branch_data.contingency_rates)

        # if there is any voltage under or over the voltage limits or any critical overload, stop
        return len(under_idx) > 0 or len(over_idx) > 0 or len(overload_idx) > 0
