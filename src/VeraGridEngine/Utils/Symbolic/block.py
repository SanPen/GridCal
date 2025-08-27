# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Tuple, Sequence, List, Dict, Any

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr
from VeraGridEngine.enumerations import DynamicVarType


def _new_uid() -> int:
    """
    Generate a fresh UUID‑v4 string.
    :return: UUIDv4 in integer format
    """
    return uuid.uuid4().int


def _serialize_expr_list(exprs: List[Expr]) -> List[Dict[str, Any]]:
    """

    :param exprs:
    :return:
    """
    return [expr.to_dict() for expr in exprs]


def _serialize_var_list(vars_: List[Var | Const]) -> List[Dict[str, Any]]:
    """
    Serialize list of variables or constants
    :param vars_: list of Var or Const
    :return: List of dictionaries with the serialized data
    """
    return [v.to_dict() for v in vars_]


def _deserialize_expr_list(expr_dicts: List[Dict[str, Any]]) -> List[Expr]:
    """

    :param expr_dicts:
    :return:
    """
    return [Expr.from_dict(d) for d in expr_dicts]


def _deserialize_var_list(var_dicts: List[Dict[str, Any]]) -> List[Var | Const]:
    """
    De-serialize previously serialized data into List of Vars or Const
    :param var_dicts: List of serialized data
    :return: List of Vars or Const
    """
    result = list()
    for d in var_dicts:
        if d["type"] == "Var":
            result.append(Var(name=d["name"], uid=d["uid"]))
        elif d["type"] == "Const":
            result.append(Const(value=d["value"], uid=d["uid"]))
        else:
            raise ValueError(f"Unknown variable type {d['type']}")
    return result


@dataclass(frozen=False)
class Block:
    """
    This represents a group of equations or a group of blocks
    """
    uid: int = field(default_factory=_new_uid)

    # internal vars
    state_vars: List[Var] = field(default_factory=list)
    state_eqs: List[Expr] = field(default_factory=list)
    algebraic_vars: List[Var] = field(default_factory=list)
    algebraic_eqs: List[Expr] = field(default_factory=list)

    # initialization
    init_eqs: Dict[Var, Expr] = field(default_factory=dict)
    init_params_eq: Dict[str, Expr] = field(default_factory=dict)
    init_vars: List[Var] = field(default_factory=list)

    external_mapping: Dict[DynamicVarType, Var] = field(default_factory=dict)
    var_mapping: Dict[str, Var] = field(default_factory=dict)

    # parameters
    parameters: List[Var | Const] = field(default_factory=list)

    name: str = ""

    # vars to make this recursive
    children: list["Block"] = field(default_factory=list)
    in_vars: List[Var] = field(default_factory=list)
    out_vars: List[Var] = field(default_factory=list)

    def __post_init__(self) -> None:
        # if len(self.algebraic_vars) != len(self.algebraic_eqs):
        #     raise ValueError(
        #         f"algebraic_vars and algebraic_eqs must have the same length: vars is {len(self.algebraic_vars)}, eqs is {len(self.algebraic_eqs)}")
        # if len(self.state_vars) != len(self.state_eqs):
        #     raise ValueError("state_vars and state_eqs must have the same length")
        self.var_mapping = {v.name: v for v in self.algebraic_vars}

    def empty(self):
        return (len(self.state_vars) + len(self.algebraic_vars)) == 0

    def E(self, d: DynamicVarType) -> Var:
        return self.external_mapping[d]

    def V(self, d: str) -> Var:
        return self.var_mapping[d]

    def add(self, val: "Block"):
        """
        Add another block
        :param val: Block
        """
        self.children.append(val)

    def get_all_blocks(self) -> List[Block]:
        """
        Depth-first collection of all *primitive* Blocks.
        """

        flat: List[Block] = [self]
        for el in self.children:
            flat.extend(el.get_all_blocks())

        return flat

    def get_vars(self) -> List[Var]:
        """
        Get a list of algebraic + state vars
        :return: List[Var]
        """
        return self.algebraic_vars + self.state_vars

    def to_dict(self) -> Dict[str, List[Dict[str, Any]] | int]:
        return {
            "uid": self.uid,
            "state_vars": _serialize_var_list(self.state_vars),
            "state_eqs": _serialize_expr_list(self.state_eqs),
            "algebraic_vars": _serialize_var_list(self.algebraic_vars),
            "algebraic_eqs": _serialize_expr_list(self.algebraic_eqs),
            "parameters": _serialize_var_list(self.parameters),
            "name": self.name,
            "children": [child.to_dict() for child in self.children],
            "in_vars": _serialize_var_list(self.in_vars),
            "out_vars": _serialize_var_list(self.out_vars),
        }

    @staticmethod
    def parse(data: Dict[str, List[Dict[str, Any]] | int]) -> "Block":
        return Block(
            uid=data["uid"],
            state_vars=_deserialize_var_list(data["state_vars"]),
            state_eqs=_deserialize_expr_list(data["state_eqs"]),
            algebraic_vars=_deserialize_var_list(data["algebraic_vars"]),
            algebraic_eqs=_deserialize_expr_list(data["algebraic_eqs"]),
            parameters=_deserialize_var_list(data["parameters"]),
            name=data.get("name", ""),
            children=[Block.parse(child) for child in data.get("children", [])],
            in_vars=_deserialize_var_list(data.get("in_vars", [])),
            out_vars=_deserialize_var_list(data.get("out_vars", [])),
        )

    def copy(self) -> "Block":
        """
        Make a deep copy of this
        :return: deep copy Block
        """
        return Block.parse(data=self.to_dict())

    def __eq__(self, other):
        if isinstance(other, Block):
            return self.to_dict() == other.to_dict()
        else:
            return False


# ----------------------------------------------------------------------------------------------------------------------
# Pre defined blocks
# ----------------------------------------------------------------------------------------------------------------------

def constant(value: float, name: str = "const") -> Tuple[Var, Block]:
    y = Var(name)
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - Const(value)])
    return y, blk


def gain(k: float, u: Var | Const, name: str = "gain_out") -> Tuple[Var, Block]:
    y = Var(name)
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - Const(k) * u])
    return y, blk


def adder(inputs: Sequence[Var | Const], name: str = "sum_out") -> Tuple[Var, Block]:
    if len(inputs) == 0:
        raise ValueError("adder() needs at least one input variable")
    y = Var(name)
    expr: Expr = inputs[0]
    for v in inputs[1:]:
        expr += v
    blk = Block(algebraic_vars=[y], algebraic_eqs=[y - expr])
    return y, blk


def integrator(u: Var | Const, name: str = "x") -> Tuple[Var, Block]:
    x = Var(name)
    blk = Block(state_vars=[x], state_eqs=[u])
    return x, blk


def pi_controller(err: Var, kp: float, ki: float, name: str = "pi") -> Block:
    up, blk_kp = gain(kp, err, f"{name}_up")
    ie, blk_int = integrator(err, f"{name}_int")
    ui, blk_ki = gain(ki, ie, f"{name}_ui")
    u, blk_sum = adder([up, ui], f"{name}_u")
    return Block(name="",
                 children=[blk_kp, blk_int, blk_ki, blk_sum],
                 in_vars=[err],
                 out_vars=[u])
