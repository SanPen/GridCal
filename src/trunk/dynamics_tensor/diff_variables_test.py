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
y = Var('y')
dt = Const('0.001')
dx = DiffVar('dx', base_var = x)
dx2 = DiffVar('dx2', base_var = dx)

a = dx.approximation_expr(dt)
print(a)
a = dx2.approximation_expr(dt)
print(a)

block = Block()