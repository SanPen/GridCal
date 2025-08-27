# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import time
import numpy as np
import math
from typing import Optional

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr, Func, cos, sin

def multilinearize_expr(expr:Func, b:Block):
    new_algebs = []
    new_algebs_eq = []
    new_states = []
    new_states_eq = []
    if expr.name == 'sin':
        u_sin = Var('usin_' + str(expr.arg.uid))
        v_sin = Var('vsin_' + str(expr.arg.uid))
        u_cos = Var('ucos_' + str(expr.arg.uid))
        v_cos = Var('vcos_' + str(expr.arg.uid))
        delta = Var('delta' + str(expr.arg.uid))
        delta_dt = Var('delta_dt' + str(expr.arg.uid))

        new_states = [u_sin, delta]
        new_states_eq = [u_cos*delta_dt, delta_dt]

        new_algebs = [v_sin, u_cos, u_sin]
        new_algebs_eq = [u_sin - v_sin,
                         u_cos - v_cos,
                         u_cos*v_cos + u_sin*v_sin -1,
                         delta - expr.arg]


        new_block = Block( state_eqs     = new_states_eq,
                           state_vars    = new_states,
                           algebraic_eqs = new_algebs_eq,
                           algebraic_vars= new_algebs
                          )

        b.algebraic_eqs = [e.subs({expr: u_sin}) for e in b.algebraic_eqs]
        b.algebraic_eqs = [e.subs({cos(expr.arg): u_cos}) for e in b.algebraic_eqs]

    elif expr.name == 'sqrt':
        u1 = Var('u1_' + str(expr.arg.uid))
        u2 = Var('u2_' + str(expr.arg.uid))

        new_states = []
        new_states_eq = []

        new_algebs = [u1, u2]
        new_algebs_eq = [u1-u2,
                         u1*u2 - expr.arg]


        new_block = Block( state_eqs     = new_states_eq,
                           state_vars    = new_states,
                           algebraic_eqs = new_algebs_eq,
                           algebraic_vars= new_algebs
                          )
        b.algebraic_eqs = [e.subs({expr: u1}) for e in b.algebraic_eqs]


    elif expr.name == 'exp':
        u = Var('u1_' + str(expr.arg.uid))

        new_states = [u]
        new_states_eq = [u*expr.arg.diff()]

        new_algebs = []
        new_algebs_eq = []

        new_block = Block( state_eqs     = new_states_eq,
                           state_vars    = new_states,
                           algebraic_eqs = new_algebs_eq,
                           algebraic_vars= new_algebs
                          )
        b.algebraic_eqs = [e.subs({expr: u}) for e in b.algebraic_eqs]


    elif expr.name == 'log':
        u = Var('u1_' + str(expr.arg.uid))

        new_states = [u]
        new_states_eq = [u*expr.arg.diff()]

        new_algebs = []
        new_algebs_eq = []

        new_block = Block( state_eqs     = new_states_eq,
                           state_vars    = new_states,
                           algebraic_eqs = new_algebs_eq,
                           algebraic_vars= new_algebs
                          )
        
        b.algebraic_eqs = [e.subs({expr: u}) for e in b.algebraic_eqs]
    
    else:
        print(expr)

    return new_block

def non_multilinear_vars(expr: Expr, vars: list[str | Var]) -> list:
    """
    Return a list of variables for which the expression is not linear
    (i.e., second derivative w.r.t. that variable is not zero).
    """
    non_multilinear = []
    for var in vars:
        second_derivative = expr.diff(var, order=2).simplify()
        if isinstance(second_derivative, Const):
            if second_derivative.value != 0:
                non_multilinear.append(var)
        else:
        # not a constant → definitely not zero
            non_multilinear.append(var)
    return non_multilinear

def contains_func(expr: Expr) -> Optional[Expr]:
    if isinstance(expr, Func):
        return expr

    if hasattr(expr, "arg"):  # e.g., UnOp or Func
        return contains_func(expr.arg)

    if hasattr(expr, "left") and hasattr(expr, "right"):  # BinOp
        return contains_func(expr.left) or contains_func(expr.right)

    return None

def find_deepest_non_multilinear(expr: Expr, vars: list[Var | str]) -> Optional[Expr]:
    # first check children
    if isinstance(expr, Func):
        inner = find_deepest_non_multilinear(expr.arg, vars)
        if inner:
            return inner
        # if arg is ok, but Func itself is problematic, return self
        return expr
    if hasattr(expr, "left") and hasattr(expr, "right"):
        left = find_deepest_non_multilinear(expr.left, vars)
        if left:
            return left
        right = find_deepest_non_multilinear(expr.right, vars)
        if right:
            return right
    if hasattr(expr, "arg"):
        return find_deepest_non_multilinear(expr.arg, vars)

    # if leaf node, check multilinearity
    if isinstance(expr, Expr):
        if any(
            not (isinstance(d := expr.diff(v, 2).simplify(), Const) and d.value == 0)
            for v in vars
        ):
            return expr

    return None

def multilinearize_block(b :Block) -> Block:
    additional_blocks = []
    all_vars = b.get_vars()
    for eq in b.algebraic_eqs:
        non_ml_vars = non_multilinear_vars(eq, all_vars)
        while non_ml_vars:
            non_ml_expr = find_deepest_non_multilinear(eq, all_vars)
            print(non_ml_expr)
            auxiliary_block = multilinearize_expr(non_ml_expr, b)
            additional_blocks.append(auxiliary_block)
            non_ml_vars = non_multilinear_vars(eq, all_vars)
            
    result = Block(
        children=[b] + additional_blocks
    )
    return result

