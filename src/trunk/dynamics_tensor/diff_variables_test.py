# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import sys, os, inspect
file_directory = os.path.dirname(os.path.abspath(__file__))
up_two_directories = os.path.join(file_directory, '..', '..')
up_two_directories = os.path.abspath(up_two_directories)
sys.path.insert(0,up_two_directories)
print(up_two_directories)
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math
import numpy as np
from matplotlib import pyplot as plt

# from GridCalEngine.Utils.Symbolic.events import Events, Event
from GridCalEngine.Devices.Dynamic.events import RmsEvents, RmsEvent
from GridCalEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin
from GridCalEngine.Utils.Symbolic.block import Block
from GridCalEngine.Utils.MultiLinear.multilinearize import *
from GridCalEngine.Utils.MultiLinear.differential_var  import DiffVar, LagVar
from GridCalEngine.Utils.MultiLinear.diff_blocksolver  import DiffBlock, DiffBlockSolver
from GridCalEngine.Utils.Symbolic.block_solver import BlockSolver
import GridCalEngine.api as gce

x = Var('x')
y_var = Var('y')
dt = Const(0.00001)
#dt = Var('dt')
dx = DiffVar.get_or_create('dx', base_var = x)
dy = DiffVar.get_or_create('dy', base_var = y_var)
d2x = DiffVar.get_or_create('d2x', base_var = dx)
d2y = DiffVar.get_or_create('d2y', base_var = dy)
d3x = DiffVar.get_or_create('d3x', base_var = d2x)

if d2x.uid == d3x.uid:
    print("They have the same uid given that they have the same base var")

lag1 = LagVar.get_or_create('lag1', base_var= x, lag =1)
lag2 = LagVar.get_or_create('lag2', base_var= x, lag =2)
dx_approx, b = dx.approximation_expr(dt)
print(dx_approx)
a, b = d2x.approximation_expr(dt)
print(a)
a, b = d3x.approximation_expr(dt)
print(a)
dy_approx, b = dy.approximation_expr(dt)

diff_block = DiffBlock(
    algebraic_eqs=[
        dx + y_var,
        dy - x,
    ],
    algebraic_vars=[x,y_var],
    diff_vars=[dx, dy, d2x, d2y],
)

slv = DiffBlockSolver(diff_block)

vars_mapping = {
    x:1,
    y_var:0
}

div_vars_mapping = {
    dx:0,
    dy:1,
}

my_events = RmsEvents([])
params_mapping = {slv.dt: 0.001}


x0  = slv.build_init_vars_vector(vars_mapping)
dx0 = slv.build_init_diffvars_vector(div_vars_mapping)
params0 = slv.build_init_params_vector(params_mapping)

vars_in_order = slv.sort_vars(vars_mapping)

time_start = time.time()
t, y = slv.simulate(
    t0=0,
    t_end=10.0,
    h=0.001,
    x0=x0,
    dx0 = dx0,
    params0=params0,
    events_list= my_events,
    method="implicit_euler",
    verbose = False
)
time_end = time.time()
print(f'time is {time_end - time_start}')
slv.save_simulation_to_csv('simulation_results.csv', t, y)

fig = plt.figure(figsize=(14, 10))

#Generator state variables
plt.plot(t, y[:, slv.get_var_idx(x)], label="x (pu)", color='red')
plt.plot(t, y[:, slv.get_var_idx(y_var)], label="y (pu)", color='yellow')
plt.plot(t, np.cos(t), label="cos(t)", linestyle='--', color='blue')

plt.legend(loc='upper right', ncol=2)
plt.xlabel("Time (s)")
plt.ylabel("Values (pu)")
plt.title("Small System: Control Proof")
#plt.xlim(0, 10)
#plt.ylim(0.85, 1.15)
plt.tight_layout()
plt.grid(True)
plt.tight_layout()
plt.show()