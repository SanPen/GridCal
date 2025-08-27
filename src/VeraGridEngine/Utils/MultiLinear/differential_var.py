# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import time
import numpy as np
import math
import uuid
from typing import Optional

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr, BinOp, UnOp, Func, cos, sin
from enum import Enum
from scipy.sparse import csc_matrix
import numba as nb
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Dict, Mapping, Union, List, Sequence, Tuple, Set

# from VeraGridEngine.Utils.Symbolic.events import EventParam

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
    lag: int = field(default=None) 

    # Registry to ensure uniqueness
    _registry: ClassVar[Dict[Tuple[int, int], "LagVar"] ]= {}
    
    def __post_init__(self):
        # Optionally, you could add checks here to ensure base_var is an instance of Var
        if not isinstance(self.base_var, Var):
            raise TypeError(f"base_var must be an argument") 
        key = (self.base_var.uid, self.lag)
        if key in self._registry:
            raise ValueError(f"DiffVar for base_var {key} already exists.")
        self._registry[key] = self
        return self

    def __eq__(self, other):
        return isinstance(other, LagVar) and self.base_var.uid == other.base_var.uid and self.lag == other.lag

    def __hash__(self):
        return hash((self.base_var, self.lag))
    
    @classmethod
    def get_or_create(cls, name, base_var: Var, lag: int) -> "LagVar":
        key = (base_var.uid, lag)
        if key not in cls._registry:
            return cls(name=name, base_var=base_var, lag = lag)
        return cls._registry[key]

    def populate_initial_lag(self, x0:float, dx0:np.ndarray, lag_x:float, dt: Optional[Var], h:float):
        #function that initializes the lag of the same order for the same original_var
        diff_order = self.lag 

        if diff_order == 1:
            return x0
        elif diff_order == 2:
            return x0 - dt*dx0[0]
        else:
            res = x0 - dt*dx0[0]

        for i in range(1, diff_order + 1):
            val = (diff_order +1 -i)*(dt**(i))*((-1)**(i))*dx0[i-1] 
            res += val
        return res.eval(dt = h)
        

@dataclass(frozen = True)
class DiffVar(Var):
    """
    Any variable
    """
    base_var:  Var = field(default=None)  

    # Class-level registry
    _registry: ClassVar[Dict[int, "DiffVar"]] = {}
    _absolute_registry: ClassVar[Dict[Tuple[int, int], "DiffVar"]] = {}

    def __post_init__(self):
        key = self.base_var.uid
        if not isinstance(self.base_var, Var):
            raise TypeError(f"base_var must be an argument of type Var") 
        if key in self._registry:
            raise ValueError(f"DiffVar for base_var {key} already exists.")
        self._registry[key] = self

        # Register by (origin_var.uid, diff_order)
        origin_uid = self.origin_var.uid
        order = self.diff_order
        self._absolute_registry[(origin_uid, order)] = self

        return self

    @classmethod
    def get_or_create(cls, name: str, base_var: Var) -> "DiffVar":
        key = base_var.uid
        if key in cls._registry:
            return cls._registry[key]
        return cls(name=name, base_var=base_var)

    def __eq__(self, other):
        return isinstance(other, DiffVar) and self.base_var.uid == other.base_var.uid 

    def __hash__(self):
        return hash((self.base_var))

    @property
    def diff_order(self) -> int:
        order = 0
        var = self
        while isinstance(var, DiffVar):
            var = var.base_var
            order += 1
        return order
    
    @property
    def origin_var(self) -> Var:
        origin = self.base_var
        while isinstance(origin, DiffVar):
            origin = origin.base_var
        return origin
    
    @classmethod
    def get_by_origin_and_order(cls, origin_var: Var, order: int) -> "DiffVar":
        key = (origin_var.uid, order)
        if key not in cls._absolute_registry:
            raise KeyError(f"No DiffVar found for origin UID={origin_var.uid} and order={order}")
        return cls._absolute_registry[key]

    def populate_initial_lag(self, x0:float, dx0:np.ndarray, lag_x:float, dt: Optional[Const]):
        #function that initializes the lag of the same order for the same original_var
        diff_order = self.diff_order 
        central_difference = True

        for i in range(diff_order):
            res += (dt**(i+1))*(-1)**(i+1)*dx0[i] 
        return res.eval()

    def approximation_expr(self, dt: Optional[Const]) -> Expr:
        """
        Computes the n-th backward finite difference approximation of the derivative
        using the closed-form backward difference formula.
        """
        origin_name = self.origin_var.name
        lag_total = self.diff_order
        if self.diff_order == 1:
            lag_var_2 = LagVar.get_or_create(
                f"{origin_name}_lag_{2}",
                base_var=self.origin_var,
                lag=2
            )
            return (self.origin_var - lag_var_2)/2*dt, lag_total
        
        # Compute the sum: ∑_{i=0}^{n} (-1)^i * C(n, i) * f(x - i*dt)
        terms = []
        for i in range(lag_total + 1):
            if i == 0:
                lag_var = self.origin_var
            else:
                lag_var = LagVar.get_or_create(
                f"{origin_name}_lag_{i}",
                base_var=self.origin_var,
                lag=i
            )
            coeff = (-1)**i * math.comb(lag_total, i)
            terms.append(coeff * lag_var)

        finite_diff_sum = sum(terms)

        # Divide by dt^n for n-th derivative
        result = finite_diff_sum / dt**lag_total
        return result.simplify(), lag_total