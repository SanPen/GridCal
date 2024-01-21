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
import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import random
from collections import deque
from gym_env import GridCalEnv  # Assuming GridCalEnv is defined as per your previous code
from GridCalEngine.api import *


class DQN(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(DQN, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Linear(256, output_dim)
        )

    def forward(self, x):
        return self.net(x)


GAMMA = 0.99  # discount factor
EPSILON = 1.0  # for epsilon-greedy policy
EPSILON_MIN = 0.01
EPSILON_DECAY = 0.995
LEARNING_RATE = 0.001
MEMORY_SIZE = 100000
BATCH_SIZE = 20
TARGET_UPDATE = 10  # Frequency of updating the target network
NUM_EPISODES = 1000  # Example value, adjust based on your specific requirements

fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')
circuit_ = FileOpen(fname).open()
env = GridCalEnv(grid=circuit_,
                 forced_mttf=10.0,
                 forced_mttr=1.0)  # Initialize your environment with appropriate parameters
n_actions = env.action_space.shape[0]  # Number of binary actions in the action space
n_states = env.observation_space.shape[0]  # Dimension of the observation space

policy_net = DQN(n_states, n_actions)
target_net = DQN(n_states, n_actions)
target_net.load_state_dict(policy_net.state_dict())
target_net.eval()  # set the target_net to evaluation mode

optimizer = optim.Adam(policy_net.parameters(), lr=LEARNING_RATE)
memory = deque(maxlen=MEMORY_SIZE)


def optimize_model():
    if len(memory) < BATCH_SIZE:
        return
    transitions = random.sample(memory, BATCH_SIZE)
    # Unpack transitions and compute loss
    # Update policy network
    # ...


for episode in range(NUM_EPISODES):
    state = env.reset()
    total_reward = 0
    done = False
    while not done:
        state_tensor = torch.from_numpy(state).float()
        # Epsilon-greedy policy
        if random.random() > EPSILON:
            action = policy_net(state_tensor).max(1)[1].view(1, 1)
        else:
            action = torch.tensor([[random.randrange(n_actions)]], dtype=torch.long)

        # state, reward, done, truncated, info
        next_state, reward, done, truncated, info = env.step(action.item())
        memory.append((state, action, next_state, reward, done))

        state = next_state
        total_reward += reward
        optimize_model()

    # Update epsilon
    EPSILON = max(EPSILON_MIN, EPSILON_DECAY * EPSILON)
    # Update the target network
    if episode % TARGET_UPDATE == 0:
        target_net.load_state_dict(policy_net.state_dict())

print("Training complete")
