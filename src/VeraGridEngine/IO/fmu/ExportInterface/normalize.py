# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Any, Iterable, cast

from VeraGridEngine.IO.fmu.model import FmuModelSnapshot, flatten_block, reconstruct_block
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import BinOp, Const, UnOp, Var

def _simplify_expr(expr: Any) -> Any:
    """Execute the `_simplify_expr` operation.

    :param expr: Function input.
    :return: Function result.
    """
    return expr.simplify()


class TransferBlockData:
    """Normalized transfer-block data."""

    __slots__ = ("output_var", "input_var", "input_expr", "export_in_vars", "remaining_algebraic_vars", "remaining_algebraic_eqs", "den_coeffs", "num_coeffs")

    def __init__(self, output_var: Any, input_var: Any, input_expr: Any, export_in_vars: tuple[Any, ...], remaining_algebraic_vars: tuple[Any, ...], remaining_algebraic_eqs: tuple[Any, ...], den_coeffs: tuple[Any, ...], num_coeffs: tuple[Any, ...]) -> None:
        """:param output_var: Transfer output variable.
        :param input_var: Transfer input variable.
        :param input_expr: Input expression.
        :param export_in_vars: External input variables.
        :param remaining_algebraic_vars: Remaining algebraic variables.
        :param remaining_algebraic_eqs: Remaining algebraic equations.
        :param den_coeffs: Denominator coefficients.
        :param num_coeffs: Numerator coefficients.
        """
        self.output_var = output_var
        self.input_var = input_var
        self.input_expr = input_expr
        self.export_in_vars = export_in_vars
        self.remaining_algebraic_vars = remaining_algebraic_vars
        self.remaining_algebraic_eqs = remaining_algebraic_eqs
        self.den_coeffs = den_coeffs
        self.num_coeffs = num_coeffs


class FlatTransferMatch:
    """Flattened transfer-block match."""

    __slots__ = ("output_var", "input_var", "input_expr", "output_chain", "input_chain", "main_equation_index", "input_assignment_index", "export_in_vars", "den_coeffs", "num_coeffs")

    def __init__(self, output_var: Any, input_var: Any, input_expr: Any, output_chain: tuple[Any, ...], input_chain: tuple[Any, ...], main_equation_index: int, input_assignment_index: int | None, export_in_vars: tuple[Any, ...], den_coeffs: tuple[Any, ...], num_coeffs: tuple[Any, ...]) -> None:
        """:param output_var: Transfer output variable.
        :param input_var: Transfer input variable.
        :param input_expr: Input expression.
        :param output_chain: Output derivative chain.
        :param input_chain: Input derivative chain.
        :param main_equation_index: Main equation index.
        :param input_assignment_index: Input assignment index.
        :param export_in_vars: External input variables.
        :param den_coeffs: Denominator coefficients.
        :param num_coeffs: Numerator coefficients.
        """
        self.output_var = output_var
        self.input_var = input_var
        self.input_expr = input_expr
        self.output_chain = output_chain
        self.input_chain = input_chain
        self.main_equation_index = main_equation_index
        self.input_assignment_index = input_assignment_index
        self.export_in_vars = export_in_vars
        self.den_coeffs = den_coeffs
        self.num_coeffs = num_coeffs


def _is_zero_expr(expr: Any) -> bool:
    """Execute the `_is_zero_expr` operation.

    :param expr: Function input.
    :return: Function result.
    """
    expr = _simplify_expr(expr)
    if isinstance(expr, Const):
        return expr.value in {0, 0.0, None}
    return False


def _contains_uid(expr: Any, target_uids: set[int]) -> bool:
    """Execute the `_contains_uid` operation.

    :param expr: Function input.
    :param target_uids: Function input.
    :return: Function result.
    """
    return any(var.uid in target_uids for var in expr.get_vars())


def _merge_coeff_maps(left: dict[int, Any], right: dict[int, Any], sign: int = 1) -> dict[int, Any]:
    """Execute the `_merge_coeff_maps` operation.

    :param left: Function input.
    :param right: Function input.
    :param sign: Function input.
    :return: Function result.
    """
    result = dict(left)
    for uid, value in right.items():
        if uid in result:
            result[uid] = _simplify_expr(result[uid] + value if sign > 0 else result[uid] - value)
        else:
            result[uid] = _simplify_expr(value if sign > 0 else Const(0.0) - value)
    return result


def _mul_expr(expr: Any, factor: Any) -> Any:
    """Execute the `_mul_expr` operation.

    :param expr: Function input.
    :param factor: Function input.
    :return: Function result.
    """
    if _is_zero_expr(expr) or _is_zero_expr(factor):
        return Const(0.0)
    return _simplify_expr(expr * factor)


def _div_expr(expr: Any, divisor: Any) -> Any:
    """Execute the `_div_expr` operation.

    :param expr: Function input.
    :param divisor: Function input.
    :return: Function result.
    """
    if _is_zero_expr(expr):
        return Const(0.0)
    return _simplify_expr(expr / divisor)


def _extract_affine(expr: Any, target_uids: set[int]) -> tuple[dict[int, Any], Any]:
    """Execute the `_extract_affine` operation.

    :param expr: Function input.
    :param target_uids: Function input.
    :return: Function result.
    """
    if isinstance(expr, Const):
        return {}, expr
    if isinstance(expr, Var):
        if expr.uid in target_uids:
            return {expr.uid: Const(1.0)}, Const(0.0)
        return {}, expr
    if isinstance(expr, UnOp):
        if expr.op != "-":
            raise ValueError(f"Unsupported unary operator {expr.op!r}")
        coeffs, const_term = _extract_affine(expr.operand, target_uids)
        return {uid: Const(0.0) - value for uid, value in coeffs.items()}, Const(0.0) - const_term
    if isinstance(expr, BinOp):
        if expr.op == "+":
            left_coeffs, left_const = _extract_affine(expr.left, target_uids)
            right_coeffs, right_const = _extract_affine(expr.right, target_uids)
            return _merge_coeff_maps(left_coeffs, right_coeffs), _simplify_expr(left_const + right_const)
        if expr.op == "-":
            left_coeffs, left_const = _extract_affine(expr.left, target_uids)
            right_coeffs, right_const = _extract_affine(expr.right, target_uids)
            return _merge_coeff_maps(left_coeffs, right_coeffs, sign=-1), _simplify_expr(left_const - right_const)
        if expr.op == "*":
            left_coeffs, left_const = _extract_affine(expr.left, target_uids)
            right_coeffs, right_const = _extract_affine(expr.right, target_uids)
            if left_coeffs and right_coeffs:
                raise ValueError("Non-linear product in transfer-function lowering")
            if left_coeffs:
                return {uid: _mul_expr(value, right_const) for uid, value in left_coeffs.items()}, _mul_expr(left_const, right_const)
            if right_coeffs:
                return {uid: _mul_expr(value, left_const) for uid, value in right_coeffs.items()}, _mul_expr(left_const, right_const)
            return {}, _simplify_expr(left_const * right_const)
        if expr.op == "/":
            left_coeffs, left_const = _extract_affine(expr.left, target_uids)
            right_coeffs, right_const = _extract_affine(expr.right, target_uids)
            if right_coeffs:
                raise ValueError("Transfer-function lowering does not support target variables in denominators")
            return {uid: _div_expr(value, right_const) for uid, value in left_coeffs.items()}, _div_expr(left_const, right_const)
    raise ValueError(f"Unsupported expression node in transfer-function lowering: {type(expr).__name__}")


def _root_var(var: Any) -> Any:
    """Execute the `_root_var` operation.

    :param var: Function input.
    :return: Function result.
    """
    current = var
    while current.base_var is not None:
        current = current.base_var
    return current


def _collect_chain(root: Any, diff_vars: list[Any]) -> list[Any]:
    """Execute the `_collect_chain` operation.

    :param root: Function input.
    :param diff_vars: Function input.
    :return: Function result.
    """
    chain = [root]
    members = [var for var in diff_vars if _root_var(var).uid == root.uid]
    chain.extend(sorted(members, key=lambda item: item.diff_order))
    return chain


def _unwrap_assignment_target(expr: Any, target_uid: int) -> Any | None:
    """Execute the `_unwrap_assignment_target` operation.

    :param expr: Function input.
    :param target_uid: Function input.
    :return: Function result.
    """
    if isinstance(expr, BinOp) and expr.op == "-":
        if isinstance(expr.left, Var) and expr.left.uid == target_uid:
            return expr.right
        if isinstance(expr.right, Var) and expr.right.uid == target_uid:
            return expr.left
    return None


def _equation_target_uid(expr: Any) -> int | None:
    """Execute the `_equation_target_uid` operation.

    :param expr: Function input.
    :return: Function result.
    """
    if isinstance(expr, Var):
        return expr.uid
    if isinstance(expr, BinOp) and expr.op in {"-", "+"}:
        left_target = _equation_target_uid(expr.left)
        if left_target is not None:
            return left_target
        if isinstance(expr.right, Var):
            return expr.right.uid
    return None


def _substitute_expr(expr: Any, mapping: dict[Any, Any]) -> Any:
    """Execute the `_substitute_expr` operation.

    :param expr: Function input.
    :param mapping: Function input.
    :return: Function result.
    """
    return _simplify_expr(expr.subs(mapping))


def _collect_external_input_vars(expr: Any, internal_uids: set[int]) -> tuple[Any, ...]:
    """Execute the `_collect_external_input_vars` operation.

    :param expr: Function input.
    :param internal_uids: Function input.
    :return: Function result.
    """
    ordered: list[Any] = []
    seen: set[int] = set()
    for var in expr.get_vars():
        if var.uid in internal_uids or var.uid in seen:
            continue
        ordered.append(var)
        seen.add(var.uid)
    return tuple(ordered)


def _parameter_uids(block: Any) -> set[int]:
    """Execute the `_parameter_uids` operation.

    :param block: Function input.
    :return: Function result.
    """
    uids: set[int] = set()
    for var in block.event_dict.keys():
        uids.add(var.uid)
    for var in block.mode_dict.keys():
        uids.add(var.uid)
    for var in block.parameters.keys():
        uids.add(var.uid)
    return uids


def _match_transfer_block(block: Any) -> TransferBlockData | None:
    """Execute the `_match_transfer_block` operation.

    :param block: Function input.
    :return: Function result.
    """
    if block.children:
        return None
    algebraic_vars = list(block.algebraic_vars)
    algebraic_eqs = list(block.algebraic_eqs)
    if not algebraic_vars or len(algebraic_vars) != len(algebraic_eqs):
        return None
    if block.state_vars:
        return None
    if not block.diff_vars:
        return None

    output_var = (block.out_vars or [algebraic_vars[0]])[0]
    diff_vars = list(block.diff_vars)
    root_vars = { _root_var(var).uid: _root_var(var) for var in diff_vars }
    output_root = _root_var(output_var)
    output_chain = _collect_chain(output_root, diff_vars)
    if len(output_chain) <= 1:
        return None

    internal_root_uids = {var.uid for var in algebraic_vars} | {var.uid for var in diff_vars} | _parameter_uids(block)
    removable_uids = {var.uid for var in algebraic_vars[1:] if var.uid not in root_vars}

    changed = True
    while changed:
        changed = False
        for variable_index in range(1, len(algebraic_vars)):
            variable = algebraic_vars[variable_index]
            if variable.uid not in removable_uids:
                continue
            equation_index: int | None = None
            replacement = None
            for candidate_index, equation in enumerate(algebraic_eqs):
                replacement = _unwrap_assignment_target(equation, variable.uid)
                if replacement is not None:
                    equation_index = candidate_index
                    break
            if replacement is None or _contains_uid(replacement, {variable.uid}):
                continue
            mapping = {variable: replacement}
            algebraic_vars.pop(variable_index)
            if equation_index is not None:
                algebraic_eqs.pop(equation_index)
            algebraic_eqs = [_substitute_expr(eq, mapping) for eq in algebraic_eqs]
            changed = True
            break

    explicit_inputs = list(block.in_vars)
    if explicit_inputs:
        if len(explicit_inputs) != 1:
            return None
        input_var = explicit_inputs[0]
    else:
        input_roots = [root for uid, root in root_vars.items() if uid != output_root.uid]
        if len(input_roots) != 1:
            return None
        input_var = input_roots[0]

    input_chain = _collect_chain(_root_var(input_var), diff_vars)
    target_chain = output_chain + input_chain
    target_uids = {var.uid for var in target_chain}

    main_equation_index = None
    preferred_output_uids = {var.uid for var in output_chain[1:]}
    if preferred_output_uids:
        for index, equation in enumerate(algebraic_eqs):
            if _contains_uid(equation, preferred_output_uids):
                main_equation_index = index
                break
    if main_equation_index is None:
        for index, equation in enumerate(algebraic_eqs):
            if _contains_uid(equation, {var.uid for var in output_chain}):
                main_equation_index = index
                break
    if main_equation_index is None:
        return None

    try:
        coeff_map, const_term = _extract_affine(algebraic_eqs[main_equation_index], target_uids)
    except ValueError:
        return None
    if not _is_zero_expr(const_term):
        return None

    den_coeffs = tuple(coeff_map.get(var.uid, Const(0.0)) for var in output_chain)
    num_coeffs = tuple(Const(0.0) - coeff_map.get(var.uid, Const(0.0)) for var in input_chain)
    if len(den_coeffs) <= 1:
        return None
    if _is_zero_expr(den_coeffs[-1]):
        return None

    input_expr = input_var
    input_assignment_index: int | None = None
    if len(input_chain) > 1:
        for index, equation in enumerate(algebraic_eqs):
            if index == main_equation_index:
                continue
            replacement = _unwrap_assignment_target(equation, input_var.uid)
            if replacement is not None:
                input_expr = replacement
                input_assignment_index = index
                break

    remaining_algebraic_vars = [
        variable
        for variable in algebraic_vars
        if variable.uid != output_var.uid and not (input_assignment_index is not None and variable.uid == input_var.uid)
    ]
    remaining_algebraic_eqs = [
        equation
        for index, equation in enumerate(algebraic_eqs)
        if index != main_equation_index and index != input_assignment_index
    ]

    export_in_vars = tuple(explicit_inputs) if explicit_inputs and input_assignment_index is None else _collect_external_input_vars(input_expr, internal_root_uids)

    return TransferBlockData(
        output_var=output_var,
        input_var=input_var,
        input_expr=input_expr,
        export_in_vars=export_in_vars,
        remaining_algebraic_vars=tuple(remaining_algebraic_vars),
        remaining_algebraic_eqs=tuple(remaining_algebraic_eqs),
        den_coeffs=den_coeffs,
        num_coeffs=num_coeffs,
    )


def _state_name(base: str, index: int) -> str:
    """Execute the `_state_name` operation.

    :param base: Function input.
    :param index: Function input.
    :return: Function result.
    """
    return f"me_tf_state_{index}_{base}"


def _lower_transfer_block_inplace(block: Any, data: TransferBlockData) -> None:
    """Execute the `_lower_transfer_block_inplace` operation.

    :param block: Function input.
    :param data: Function input.
    :return: Function result.
    """
    order = len(data.den_coeffs) - 1
    leading = data.den_coeffs[-1]
    beta = [Const(0.0) for _ in range(order + 1)]
    for index, coeff in enumerate(data.num_coeffs[: order + 1]):
        beta[index] = _div_expr(coeff, leading)
    alpha = [_div_expr(coeff, leading) for coeff in data.den_coeffs[:-1]]
    direct_term = beta[order]
    output_coeffs = [_simplify_expr(beta[index] - alpha[index] * direct_term) for index in range(order)]

    state_vars = [Var(_state_name(data.output_var.name, index + 1)) for index in range(order)]
    diff_vars = [Var(f"d_{state.name}", base_var=state) for state in state_vars]
    state_eqs: list[Any] = []
    for index in range(order - 1):
        state_eqs.append(state_vars[index + 1])
    rhs = data.input_expr
    for index, coeff in enumerate(alpha):
        rhs = _simplify_expr(rhs - coeff * state_vars[index])
    state_eqs.append(_simplify_expr(rhs))

    algebraic_vars: list[Any] = list(data.remaining_algebraic_vars)
    algebraic_eqs: list[Any] = list(data.remaining_algebraic_eqs)

    output_expr = _simplify_expr(direct_term * data.input_expr)
    for coeff, state in zip(output_coeffs, state_vars, strict=True):
        output_expr = _simplify_expr(output_expr + coeff * state)
    algebraic_vars.insert(0, data.output_var)
    algebraic_eqs.insert(0, _simplify_expr(data.output_var - output_expr))

    init_eqs = dict(block.init_eqs)
    valid_algebraic_uids = {var.uid for var in algebraic_vars}
    for variable in list(init_eqs.keys()):
        if variable.uid in {var.uid for var in block.algebraic_vars} and variable.uid not in valid_algebraic_uids:
            init_eqs.pop(variable)
    init_eqs[data.output_var] = output_expr
    if order > 0:
        if _is_zero_expr(alpha[0]):
            init_eqs[state_vars[0]] = Const(0.0)
        else:
            init_eqs[state_vars[0]] = _simplify_expr(data.input_expr / alpha[0])
    for state in state_vars[1:]:
        init_eqs[state] = Const(0.0)

    diff_init_eqs = {diff_var: expr for diff_var, expr in zip(diff_vars, state_eqs, strict=True)}

    block.state_vars = state_vars
    block.state_eqs = state_eqs
    block.diff_vars = diff_vars
    block.algebraic_vars = algebraic_vars
    block.algebraic_eqs = algebraic_eqs
    block.init_eqs = init_eqs
    block.diff_init_eqs = diff_init_eqs
    block.in_vars = list(data.export_in_vars)
    block.out_vars = [data.output_var]
    block.var_mapping = {var.name: var for var in block.algebraic_vars + block.state_vars + block.diff_vars}


def _lower_transfer_blocks_inplace(block: Any) -> bool:
    """Execute the `_lower_transfer_blocks_inplace` operation.

    :param block: Function input.
    :return: Function result.
    """
    changed = False
    for child in list(block.children):
        changed = _lower_transfer_blocks_inplace(child) or changed
    data = _match_transfer_block(block)
    if data is not None:
        _lower_transfer_block_inplace(block, data)
        changed = True
    return changed


def _build_transfer_realization(output_var: Any, input_expr: Any, den_coeffs: tuple[Any, ...], num_coeffs: tuple[Any, ...]) -> tuple[list[Any], list[Any], list[Any], Any]:
    """Execute the `_build_transfer_realization` operation.

    :param output_var: Function input.
    :param input_expr: Function input.
    :param den_coeffs: Function input.
    :param num_coeffs: Function input.
    :return: Function result.
    """
    order = len(den_coeffs) - 1
    leading = den_coeffs[-1]
    beta = [Const(0.0) for _ in range(order + 1)]
    for index, coeff in enumerate(num_coeffs[: order + 1]):
        beta[index] = _div_expr(coeff, leading)
    alpha = [_div_expr(coeff, leading) for coeff in den_coeffs[:-1]]
    direct_term = beta[order]
    output_coeffs = [_simplify_expr(beta[index] - alpha[index] * direct_term) for index in range(order)]

    state_vars = [Var(_state_name(output_var.name, index + 1)) for index in range(order)]
    diff_vars = [Var(f"d_{state.name}", base_var=state) for state in state_vars]
    state_eqs: list[Any] = []
    for index in range(order - 1):
        state_eqs.append(state_vars[index + 1])
    rhs = input_expr
    for index, coeff in enumerate(alpha):
        rhs = _simplify_expr(rhs - coeff * state_vars[index])
    state_eqs.append(_simplify_expr(rhs))

    output_expr = _simplify_expr(direct_term * input_expr)
    for coeff, state in zip(output_coeffs, state_vars, strict=True):
        output_expr = _simplify_expr(output_expr + coeff * state)
    return state_vars, diff_vars, state_eqs, output_expr


def _match_transfer_pattern_in_flat_block(block: Any, output_var: Any) -> FlatTransferMatch | None:
    """Execute the `_match_transfer_pattern_in_flat_block` operation.

    :param block: Function input.
    :param output_var: Function input.
    :return: Function result.
    """
    algebraic_vars = list(block.algebraic_vars)
    algebraic_eqs = list(block.algebraic_eqs)
    diff_vars = list(block.diff_vars)
    if output_var not in algebraic_vars or not algebraic_eqs or not diff_vars:
        return None

    output_chain = tuple(_collect_chain(_root_var(output_var), diff_vars))
    if len(output_chain) <= 1:
        return None

    root_uids = {_root_var(var).uid for var in diff_vars}
    algebraic_uid_set = {var.uid for var in algebraic_vars}
    state_uid_set = {var.uid for var in block.state_vars}
    input_uid_set = {var.uid for var in block.in_vars}
    parameter_uid_set = _parameter_uids(block)
    internal_root_uids = algebraic_uid_set | {var.uid for var in diff_vars} | state_uid_set | parameter_uid_set

    main_equation_index = None
    preferred_output_uids = {var.uid for var in output_chain[1:]}
    if preferred_output_uids:
        for index, equation in enumerate(algebraic_eqs):
            if _contains_uid(equation, preferred_output_uids):
                main_equation_index = index
                break
    if main_equation_index is None:
        for index, equation in enumerate(algebraic_eqs):
            if _contains_uid(equation, {var.uid for var in output_chain}):
                main_equation_index = index
                break
    if main_equation_index is None:
        return None

    vars_in_main: list[Any] = list(algebraic_eqs[main_equation_index].get_vars())
    input_roots: list[Any] = []
    seen_roots: set[int] = set()
    output_uids = {var.uid for var in output_chain}
    for var in vars_in_main:
        if var.uid in output_uids:
            continue
        root = _root_var(var)
        if root.uid in seen_roots:
            continue
        if root.uid in parameter_uid_set:
            continue
        if root.uid not in algebraic_uid_set and root.uid not in state_uid_set and root.uid not in input_uid_set:
            continue
        input_roots.append(root)
        seen_roots.add(root.uid)
    if len(input_roots) != 1:
        return None

    input_var = input_roots[0]
    input_chain = tuple(_collect_chain(_root_var(input_var), diff_vars))
    target_uids = {var.uid for var in output_chain + input_chain}
    try:
        coeff_map, const_term = _extract_affine(algebraic_eqs[main_equation_index], target_uids)
    except ValueError:
        return None
    if not _is_zero_expr(const_term):
        return None

    input_expr = input_var
    input_assignment_index: int | None = None
    if len(input_chain) > 1 and input_var.uid in algebraic_uid_set:
        for index, equation in enumerate(algebraic_eqs):
            if index == main_equation_index:
                continue
            replacement = _unwrap_assignment_target(equation, input_var.uid)
            if replacement is None or _contains_uid(replacement, {input_var.uid}):
                continue
            input_expr = replacement
            input_assignment_index = index
            break

    den_coeffs = tuple(coeff_map.get(var.uid, Const(0.0)) for var in output_chain)
    num_coeffs = tuple(Const(0.0) - coeff_map.get(var.uid, Const(0.0)) for var in input_chain)
    if len(den_coeffs) <= 1 or _is_zero_expr(den_coeffs[-1]):
        return None

    export_in_vars = _collect_external_input_vars(input_expr, internal_root_uids)
    return FlatTransferMatch(
        output_var=output_var,
        input_var=input_var,
        input_expr=input_expr,
        output_chain=output_chain,
        input_chain=input_chain,
        main_equation_index=main_equation_index,
        input_assignment_index=input_assignment_index,
        export_in_vars=export_in_vars,
        den_coeffs=den_coeffs,
        num_coeffs=num_coeffs,
    )


def _lower_transfer_pattern_in_flat_block_inplace(block: Any, match: FlatTransferMatch) -> None:
    """Execute the `_lower_transfer_pattern_in_flat_block_inplace` operation.

    :param block: Function input.
    :param match: Function input.
    :return: Function result.
    """
    state_vars, new_diff_vars, state_eqs, output_expr = _build_transfer_realization(match.output_var, match.input_expr, match.den_coeffs, match.num_coeffs)

    algebraic_vars = list(block.algebraic_vars)
    algebraic_eqs = list(block.algebraic_eqs)
    state_var_list = list(block.state_vars)
    state_eq_list = list(block.state_eqs)
    diff_var_list = list(block.diff_vars)
    init_eqs = dict(block.init_eqs)
    diff_init_eqs = dict(block.diff_init_eqs)
    in_vars = list(block.in_vars)

    index_skip = {match.main_equation_index}
    if match.input_assignment_index is not None:
        index_skip.add(match.input_assignment_index)
        algebraic_eqs = [_substitute_expr(eq, {match.input_var: match.input_expr}) for eq in algebraic_eqs]

    old_diff_uids = {var.uid for var in match.output_chain[1:] + match.input_chain[1:]}
    algebraic_vars = [
        var for var in algebraic_vars
        if var.uid != match.output_var.uid and not (match.input_assignment_index is not None and var.uid == match.input_var.uid)
    ]
    algebraic_eqs = [eq for index, eq in enumerate(algebraic_eqs) if index not in index_skip]
    diff_var_list = [var for var in diff_var_list if var.uid not in old_diff_uids]

    algebraic_vars.insert(0, match.output_var)
    algebraic_eqs.insert(0, _simplify_expr(match.output_var - output_expr))
    state_var_list.extend(state_vars)
    state_eq_list.extend(state_eqs)
    diff_var_list.extend(new_diff_vars)

    valid_algebraic_uids = {var.uid for var in algebraic_vars}
    for variable in list(init_eqs.keys()):
        if variable.uid not in valid_algebraic_uids and variable.uid != match.output_var.uid and variable.uid == match.input_var.uid:
            init_eqs.pop(variable)
    init_eqs[match.output_var] = output_expr
    if state_vars:
        alpha0 = _div_expr(match.den_coeffs[0], match.den_coeffs[-1]) if len(match.den_coeffs) > 1 else Const(0.0)
        if _is_zero_expr(alpha0):
            init_eqs[state_vars[0]] = Const(0.0)
        else:
            init_eqs[state_vars[0]] = _simplify_expr(match.input_expr / alpha0)
        for state in state_vars[1:]:
            init_eqs[state] = Const(0.0)
    for old_uid in old_diff_uids:
        for diff_var in list(diff_init_eqs.keys()):
            if diff_var.uid == old_uid:
                diff_init_eqs.pop(diff_var)
    diff_init_eqs.update({diff_var: expr for diff_var, expr in zip(new_diff_vars, state_eqs, strict=True)})

    merged_inputs: list[Any] = []
    seen_input_uids: set[int] = set()
    for var in in_vars + list(match.export_in_vars):
        if var.uid in seen_input_uids or var.uid == match.input_var.uid:
            continue
        merged_inputs.append(var)
        seen_input_uids.add(var.uid)

    block.algebraic_vars = algebraic_vars
    block.algebraic_eqs = algebraic_eqs
    block.state_vars = state_var_list
    block.state_eqs = state_eq_list
    block.diff_vars = diff_var_list
    block.init_eqs = init_eqs
    block.diff_init_eqs = diff_init_eqs
    block.in_vars = merged_inputs
    block.var_mapping = {var.name: var for var in block.algebraic_vars + block.state_vars + block.diff_vars}


def _lower_transfer_patterns_in_flat_block_inplace(block: Any) -> bool:
    """Execute the `_lower_transfer_patterns_in_flat_block_inplace` operation.

    :param block: Function input.
    :return: Function result.
    """
    changed_any = False
    changed = True
    while changed:
        changed = False
        candidates = []
        root_uids = {_root_var(var).uid for var in list(block.diff_vars)}
        for variable in list(block.algebraic_vars):
            if variable.uid in root_uids:
                candidates.append(variable)
        for candidate in candidates:
            match = _match_transfer_pattern_in_flat_block(block, candidate)
            if match is None:
                continue
            _lower_transfer_pattern_in_flat_block_inplace(block, match)
            changed = True
            changed_any = True
            break
    return changed_any


def _realign_algebraic_system_inplace(block: Any) -> bool:
    """Execute the `_realign_algebraic_system_inplace` operation.

    :param block: Function input.
    :return: Function result.
    """
    algebraic_vars = list(block.algebraic_vars)
    algebraic_eqs = list(block.algebraic_eqs)
    if len(algebraic_vars) != len(algebraic_eqs):
        return False

    remaining = list(enumerate(algebraic_eqs))
    ordered: list[Any] = []
    changed = False
    for variable in algebraic_vars:
        match_pos: int | None = None
        for pos, (_, equation) in enumerate(remaining):
            if _equation_target_uid(equation) == variable.uid:
                match_pos = pos
                break
        if match_pos is None:
            return False
        original_index, equation = remaining.pop(match_pos)
        if original_index != len(ordered):
            changed = True
        ordered.append(equation)

    if not changed:
        return False
    block.algebraic_eqs = ordered
    return True


def _promote_explicit_diff_states_inplace(block: Any) -> bool:
    """Execute the `_promote_explicit_diff_states_inplace` operation.

    :param block: Function input.
    :return: Function result.
    """
    changed_any = False
    for child in list(block.children):
        changed_any = _promote_explicit_diff_states_inplace(child) or changed_any

    changed = True
    while changed:
        changed = False
        algebraic_vars = list(block.algebraic_vars)
        algebraic_eqs = list(block.algebraic_eqs)
        diff_uid_set = {var.uid for var in list(block.diff_vars)}
        algebraic_uids = {var.uid for var in algebraic_vars}
        state_uids = {var.uid for var in block.state_vars}
        for diff_var in list(block.diff_vars):
            base_var = diff_var.base_var
            if base_var is None or base_var.uid not in algebraic_uids or base_var.uid in state_uids:
                continue
            equation_index: int | None = None
            rhs_expr = None
            for index, equation in enumerate(algebraic_eqs):
                candidate = _unwrap_assignment_target(equation, diff_var.uid)
                if candidate is None or _contains_uid(candidate, {diff_var.uid}):
                    continue
                if _contains_uid(candidate, diff_uid_set - {diff_var.uid}):
                    continue
                equation_index = index
                rhs_expr = candidate
                break
            if equation_index is None or rhs_expr is None:
                continue

            block.algebraic_vars = [var for var in algebraic_vars if var.uid != base_var.uid]
            block.algebraic_eqs = [equation for index, equation in enumerate(algebraic_eqs) if index != equation_index]
            block.state_vars = list(block.state_vars) + [base_var]
            block.state_eqs = list(block.state_eqs) + [_simplify_expr(rhs_expr)]
            block.diff_init_eqs = dict(block.diff_init_eqs)
            block.diff_init_eqs[diff_var] = _simplify_expr(rhs_expr)
            block.var_mapping = {var.name: var for var in block.algebraic_vars + block.state_vars + list(block.diff_vars)}
            changed = True
            changed_any = True
            break
    return changed_any


def prepare_flat_block_for_me(snapshot: FmuModelSnapshot) -> Block:
    """Execute the `prepare_flat_block_for_me` operation.

    :param snapshot: Function input.
    :return: Function result.
    """
    block = reconstruct_block(snapshot)
    _lower_transfer_blocks_inplace(block)
    flat_block = flatten_block(block)
    changed = True
    while changed:
        changed = False
        changed = _lower_transfer_patterns_in_flat_block_inplace(flat_block) or changed
        changed = _promote_explicit_diff_states_inplace(flat_block) or changed
        changed = _realign_algebraic_system_inplace(flat_block) or changed
    return flat_block
