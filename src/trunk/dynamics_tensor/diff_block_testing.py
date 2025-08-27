# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import sys, os
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

# from VeraGridEngine.Utils.Symbolic.events import Events, Event
from VeraGridEngine.Devices.Dynamic.events import RmsEvents, RmsEvent
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.MultiLinear.multilinearize import *
from VeraGridEngine.Utils.MultiLinear.differential_var import DiffVar, LagVar
from VeraGridEngine.Utils.MultiLinear.diff_blocksolver import DiffBlock, DiffBlockSolver
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
import VeraGridEngine.api as gce

w = Var('w')
x = Var('x')
y = Var('y')
z = Var("z")

dt = Const(0.001)
#dt = Var('dt')
dx = DiffVar.get_or_create('dx', base_var = x)
dy = DiffVar.get_or_create('dy', base_var = y)
dx2 = DiffVar.get_or_create('dx2', base_var = dx)
dy2 = DiffVar.get_or_create('dy2', base_var = dy)
dx3 = DiffVar.get_or_create('dx3', base_var = dx2)

if dx2.uid == dx3.uid:
    print("They have the same uid given that they have the same base var")

lag1 = LagVar.get_or_create('lag1', base_var= x, lag =1)
lag2 = LagVar.get_or_create('lag2', base_var= x, lag =2)
dx_approx, b = dx.approximation_expr(dt)
dy_approx, b = dy.approximation_expr(dt)

block1 = DiffBlock(
    algebraic_eqs=[
        dx + y,
        dy - x + z,
    ],
    algebraic_vars=[x,y],
    diff_vars=[dx, dy, dx2, dy2],
)

block2 = Block(
    state_eqs=[
        dx
    ],
    state_vars=[w],
    algebraic_eqs=[
        z - 2
    ],
    algebraic_vars=[z],
    parameters=[]
)

big_block = DiffBlock(
    children=[block1, block2],
    in_vars=[]
)

slv = DiffBlockSolver(big_block)
print(sys)