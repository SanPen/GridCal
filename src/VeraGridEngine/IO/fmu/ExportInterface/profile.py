# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Static capability analysis for Model Exchange export."""

from __future__ import annotations

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import BinOp, Expr, Var


class BlockMEProfile:
    """Describe whether one flattened symbolic block is ME-compatible."""

    __slots__ = ("kind", "supported", "reasons")

    def __init__(self, kind: str, supported: bool, reasons: tuple[str, ...]) -> None:
        """Create a fixed Model Exchange capability result.

        :param kind: Classified block shape.
        :param supported: Whether the shape is exportable.
        :param reasons: Explanations for unsupported shapes.
        :return: None.
        """

        self.kind: str = kind
        self.supported: bool = supported
        self.reasons: tuple[str, ...] = reasons


def _root_base_var(var: Var) -> Var | None:
    """Return the root state variable for one derivative variable.

    :param var: Derivative variable to inspect.
    :return: Root base variable, or ``None`` when no base exists.
    """

    base_var: Var | None = var.base_var
    while base_var is not None and base_var.base_var is not None:
        base_var = base_var.base_var
    return base_var


def _unwrap_assignment_target(expr: Expr, target_uid: int) -> Expr | None:
    """Extract the right-hand side of a simple symbolic assignment residual.

    :param expr: Algebraic residual expression.
    :param target_uid: UID of the assigned algebraic variable.
    :return: Assignment expression, or ``None`` for another residual shape.
    """

    if isinstance(expr, BinOp) and expr.op == "-":
        if isinstance(expr.left, Var) and expr.left.uid == target_uid:
            return expr.right
        if isinstance(expr.right, Var) and expr.right.uid == target_uid:
            return expr.left
    return None


def _expr_vars(expr: Expr) -> list[Var]:
    """Return variables referenced by one symbolic expression.

    :param expr: Symbolic expression.
    :return: Referenced variables.
    """

    return list(expr.get_vars())


def analyze_flat_block_for_me(flat_block: Block) -> BlockMEProfile:
    """Classify one flattened block against the supported ME profile.

    :param flat_block: Normalized symbolic block.
    :return: Typed capability result.
    """

    state_uids: set[int] = {var.uid for var in flat_block.state_vars}
    algebraic_by_uid: dict[int, tuple[int, Var]] = {
        var.uid: (index, var) for index, var in enumerate(flat_block.algebraic_vars)
    }
    input_uids: set[int] = {var.uid for var in flat_block.in_vars}
    reasons: list[str] = list()

    event_names: list[str] = [var.name for var in flat_block.event_dict]
    if (
        event_names
        and len(flat_block.state_vars) == 0
        and len(flat_block.algebraic_vars) == 0
        and len(flat_block.diff_vars) == 0
        and all(name.startswith("Ih_f_") or name.startswith("Ih_t_") for name in event_names)
    ):
        return BlockMEProfile(
            "history_runtime",
            False,
            ("The block is a Bergeron history runtime placeholder and is not exportable as FMI Model Exchange.",),
        )

    for diff_var in flat_block.diff_vars:
        base_var: Var | None = _root_base_var(diff_var)
        if base_var is None:
            reasons.append(
                f"Differential variable '{diff_var.name}' has no base variable; Model Exchange requires explicit continuous states."
            )
        elif base_var.uid in state_uids:
            pass
        elif base_var.uid in algebraic_by_uid:
            index: int
            algebraic_var: Var
            index, algebraic_var = algebraic_by_uid[base_var.uid]
            message: str = (
                f"Differential variable '{diff_var.name}' is based on algebraic variable '{algebraic_var.name}', not a state variable."
            )
            rhs: Expr | None = _unwrap_assignment_target(
                flat_block.algebraic_eqs[index], algebraic_var.uid
            )
            if rhs is not None and {var.uid for var in _expr_vars(rhs)} & input_uids:
                message += " Its algebraic relation depends on an FMU input and would require input derivatives."
            reasons.append(message)
        elif base_var.uid in input_uids:
            reasons.append(
                f"Differential variable '{diff_var.name}' is based directly on FMU input '{base_var.name}'."
            )
        else:
            reasons.append(
                f"Differential variable '{diff_var.name}' is based on unsupported variable '{base_var.name}'."
            )

    if reasons:
        return BlockMEProfile("implicit_dae", False, tuple(reasons))
    if flat_block.state_vars and flat_block.algebraic_vars:
        return BlockMEProfile("semi_explicit_dae", True, tuple())
    if flat_block.state_vars:
        return BlockMEProfile("ode", True, tuple())
    if flat_block.algebraic_vars:
        return BlockMEProfile("algebraic_only", True, tuple())
    return BlockMEProfile("empty", True, tuple())


def assert_block_supported_for_me(flat_block: Block) -> BlockMEProfile:
    """Reject unsupported block shapes and return the capability result.

    :param flat_block: Normalized symbolic block.
    :return: Validated capability result.
    :raises ValueError: If the block is outside the supported ME profile.
    """

    profile: BlockMEProfile = analyze_flat_block_for_me(flat_block)
    if profile.supported:
        return profile
    raise ValueError(" ".join(profile.reasons))
