from typing import Union
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from VeraGridEngine.enumerations import DeviceType, BuildStatus
from VeraGridEngine.Devices.Parents.load_parent import LoadParent
from VeraGridEngine.Devices.profile import Profile
from VeraGridEngine.Utils.Symbolic.block import Block, Var, Const, DynamicVarType
from VeraGridEngine.Utils.Symbolic.symbolic import piecewise

result = piecewise(0, 1, 5, 2)

# print(4*18+2*2+13*4+2*11)

print(97/71)

print(172/150)


# print(result)