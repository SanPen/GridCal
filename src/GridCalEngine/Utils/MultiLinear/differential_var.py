# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import time
import numpy as np
import math
import uuid
from typing import Optional

from GridCalEngine.Utils.Symbolic.block import Block
from GridCalEngine.Utils.Symbolic.block_solver import BlockSolver
from GridCalEngine.Utils.Symbolic.symbolic import Var, Const, Expr, BinOp, UnOp, Func, cos, sin
from enum import Enum
from scipy.sparse import csc_matrix
import numba as nb
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Dict, Mapping, Union, List, Sequence, Tuple, Set

# from GridCalEngine.Utils.Symbolic.events import EventParam

NUMBER = Union[int, float]
NAME = 'name'


# -----------------------------------------------------------------------------
# UUID helper
# -----------------------------------------------------------------------------

def _new_uid() -> int:
    """Generate a fresh UUID‑v4 string."""
    return uuid.uuid4().int

def _collect_vars(expr: Expr, out: Set[Var]) -> None:
    """
    Collect variables in a deterministic order
    Depth-first, left-to-right variable harvest.
    :param expr: Some expression
    :param out: List to fill
    :return: None
    """
    if isinstance(expr, Var):
        if expr not in out:
            out.add(expr)
    elif isinstance(expr, BinOp):
        _collect_vars(expr.left, out)
        _collect_vars(expr.right, out)
    elif isinstance(expr, UnOp):
        _collect_vars(expr.operand, out)
    elif isinstance(expr, Func):
        _collect_vars(expr.arg, out)


def _all_vars(expressions: Sequence[Expr]) -> List[Var]:
    """
    Collect all variables in a list of expressions
    :param expressions: Any iterable of expressions
    :return: List of non-repeated variables
    """
    res: Set[Var] = set()
    for e in expressions:
        _collect_vars(e, res)
    return list(res)

@dataclass(frozen = True)
class LagVar(Var):
    base_var: Var = field(default=None)  
    lag: int = 1

    # Registry to ensure uniqueness
    _registry: ClassVar[Dict[Tuple[int, int], "LagVar"] ]= {}

    def __new__(cls, name:str, base_var: Var, lag: int = 1):
        if not isinstance(base_var, Var):
            raise TypeError("base_var must be a Var")

        key = (base_var.uid, lag)
        if key in cls._registry:
            return cls._registry[key]

        self = super().__new__(cls)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "base_var", base_var)
        object.__setattr__(self, "lag", lag)
        cls._registry[key] = self
        return self
    
    def __post_init__(self):
        # Optionally, you could add checks here to ensure base_var is an instance of Var
        if not isinstance(self.base_var, Var):
            raise TypeError(f"base_var must be an argument") 

    def __eq__(self, other):
        return isinstance(other, LagVar) and self.base_var.uid == other.base_var.uid and self.lag == other.lag

    def __hash__(self):
        return hash((self.base_var, self.lag))

@dataclass(frozen = True)
class DiffVar(Var):
    """
    Any variable
    """
    base_var:  Var = field(default=None)  

    # Class-level registry
    _registry: ClassVar[Dict[Any, "DiffVar"]] = {}

    def __new__(cls, name: str, base_var: Var):
        key = base_var.uid
        if key in cls._registry:
            return cls._registry[key]

        # compute origin_var
        origin = base_var
        while isinstance(origin, DiffVar):
            origin = origin.base_var

        # create and set fields
        self = super().__new__(cls)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "origin_var", origin)
        object.__setattr__(self, "base_var", base_var)

        cls._registry[key] = self
        return self

    def __post_init__(self):
        # Optionally, you could add checks here to ensure base_var is an instance of Var
        if not isinstance(self.base_var, Var):
            raise TypeError(f"base_var must be an argument") 

    def __eq__(self, other):
        return isinstance(other, DiffVar) and self.base_var.uid == other.base_var.uid 

    def __hash__(self):
        return hash((self.base_var))

    def approximation_expr(self, dt, recursive_expr:Expr = None, lag_total = 0) -> Expr:
        #We Recursively compute the value of the approximate differential expression
        if recursive_expr is None:
            recursive_expr = 0
        else: 
            all_vars = _all_vars([recursive_expr])
            for var in all_vars:
                for lag in range(lag_total, -1, -1):
                    if isinstance(var, LagVar) and var.lag == lag:
                        origin_name = self.origin_var.name
                        new_lag = LagVar(origin_name +'_lag_'+str(var.lag+1), base_var = self.origin_var, lag = var.lag+1)
                        recursive_expr = recursive_expr.subs({var:new_lag})

        #If the base variable is not a DiffVar we can exit the recursive loop
        if not isinstance(self.base_var, DiffVar):
            origin_name = self.origin_var.name
            return ((self.base_var - LagVar(origin_name+'_lag_'+str(1), base_var = self.origin_var, lag = 1)) - recursive_expr) / dt, lag_total+1

        origin_name = self.origin_var.name
        lag0 = LagVar(origin_name +'_lag_'+str(0), base_var = self.origin_var, lag = 0)
        lag1 = LagVar(origin_name +'_lag_'+str(1), base_var = self.origin_var, lag = 1)
        new_recursive_expression = ((lag0-lag1) - recursive_expr)/(dt)
        return self.base_var.approximation_expr(dt, new_recursive_expression.simplify(), lag_total+1), lag_total+1