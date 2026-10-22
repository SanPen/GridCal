# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import warnings
from copy import deepcopy
from typing import Dict, List, Set
import numpy as np

import scipy.sparse as sp
from scipy.sparse.linalg import MatrixRankWarning

from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicVector, SymbolicParamsVector, SymbolicDerivative, SymbolicJacobian
from VeraGridEngine.Utils.Symbolic.explicit_initialization_symbolic import build_explicit_init_graph
from VeraGridEngine.Utils.Symbolic.symbolic import eval_uid as eval_expr_uid, get_expression_vars
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr, BinOp, UnOp
from VeraGridEngine.enumerations import VarPowerFlowReferenceType, RmsInitializationMethod
from VeraGridEngine.basic_structures import Vec


def _block_has_complete_explicit_initialization(mdl: Block,
                                                init_guess: Dict[int, float | int | complex | None],
                                                uid2idx_vars: Dict[int, int]) -> bool:
    """
    Return whether a block can be safely initialized by explicit equations only.

    :param mdl: RMS symbolic block to inspect.
    :param init_guess: Initial values already seeded from power flow or previous blocks.
    :param uid2idx_vars: Global system variable index map.
    :return: ``True`` when every local state/algebraic variable has an explicit value source.
    """
    explicit_eq_uids: Set[int] = set()
    blk: Block
    init_var: Var
    event_var: Var
    event_value: Expr | Const
    local_vars: List[Var]
    var: Var

    # Collect equation targets before checking seeds, since child blocks can
    # initialize variables referenced by their parent.
    for blk in mdl.get_all_blocks():
        for init_var in blk.init_eqs.keys():
            if isinstance(init_var, Var):
                explicit_eq_uids.add(init_var.uid)
            else:
                pass
        for init_var in blk.diff_init_eqs.keys():
            if isinstance(init_var, Var):
                explicit_eq_uids.add(init_var.uid)
            else:
                pass

    for blk in mdl.get_all_blocks():
        # An event parameter without a supplied value also needs an equation.
        for event_var, event_value in blk.event_dict.items():
            if isinstance(event_var, Var) and isinstance(event_value, Const) and event_value.value is None:
                if event_var.uid in explicit_eq_uids:
                    pass
                else:
                    return False
            else:
                pass

        # Inspect both owned collections directly; no combined copy is needed
        # to decide whether all local unknowns have explicit value sources.
        for local_vars in (blk.state_vars, blk.algebraic_vars):
            for var in local_vars:
                if not isinstance(var, Var):
                    pass
                elif var.uid not in uid2idx_vars:
                    pass
                elif var.uid in init_guess and init_guess[var.uid] is not None:
                    pass
                elif var.uid in explicit_eq_uids:
                    pass
                else:
                    return False

    return True


def _select_rms_initialization_method(configured_method: RmsInitializationMethod,
                                      mdl: Block,
                                      init_guess: Dict[int, float | int | complex | None],
                                      uid2idx_vars: Dict[int, int]) -> RmsInitializationMethod:
    """
    Select the concrete initialization method for one RMS block.

    :param configured_method: User-selected initialization method.
    :param mdl: RMS symbolic block to initialize.
    :param init_guess: Initial values already seeded from power flow or previous blocks.
    :param uid2idx_vars: Global system variable index map.
    :return: Concrete initialization method to execute.
    """
    if configured_method == RmsInitializationMethod.Auto:
        if _block_has_complete_explicit_initialization(mdl=mdl,
                                                       init_guess=init_guess,
                                                       uid2idx_vars=uid2idx_vars):
            selected_method: RmsInitializationMethod = RmsInitializationMethod.Explicit
        else:
            selected_method = RmsInitializationMethod.PseudoTransient
    else:
        selected_method = configured_method

    return selected_method


def is_branch_like_pf_mapping(mdl: Block) -> bool:
    """
    Determine whether an RMS block exposes branch terminal power-flow references.

    :param mdl: RMS symbolic block to classify.
    :return: ``True`` when the block maps from/to terminal quantities, otherwise ``False``.
    """
    branch_reference_types: list[VarPowerFlowReferenceType] = [
        VarPowerFlowReferenceType.Pf,
        VarPowerFlowReferenceType.Qf,
        VarPowerFlowReferenceType.Pt,
        VarPowerFlowReferenceType.Qt,
        VarPowerFlowReferenceType.Pf_hvdc,
        VarPowerFlowReferenceType.Pt_hvdc,
        VarPowerFlowReferenceType.Vmf,
        VarPowerFlowReferenceType.Vaf,
        VarPowerFlowReferenceType.Vmt,
        VarPowerFlowReferenceType.Vat,
        VarPowerFlowReferenceType.Vf_dc,
        VarPowerFlowReferenceType.Vt_dc,
        VarPowerFlowReferenceType.Irf,
        VarPowerFlowReferenceType.Iif,
        VarPowerFlowReferenceType.Irt,
        VarPowerFlowReferenceType.Iit,
    ]
    is_branch_like: bool = False

    for pf_ref in branch_reference_types:
        if pf_ref in mdl.external_mapping:
            is_branch_like = True
        else:
            pass

    return is_branch_like


def get_pseudo_transient_freeze_references(mdl: Block) -> list[VarPowerFlowReferenceType]:
    """
    Get power-flow references that must be frozen during local pseudo-transient initialization.

    :param mdl: RMS symbolic block being initialized.
    :return: Ordered list of external mapping references to replace by PF constants.
    """
    if is_branch_like_pf_mapping(mdl=mdl):
        # Branch-like models receive fixed terminal quantities. Internal net P/Q
        # variables must remain solvable because wrapper equations may define them
        # from terminal powers with a sign convention.
        pf_var_references: list[VarPowerFlowReferenceType] = [
            VarPowerFlowReferenceType.Pf,
            VarPowerFlowReferenceType.Qf,
            VarPowerFlowReferenceType.Pt,
            VarPowerFlowReferenceType.Qt,
            VarPowerFlowReferenceType.Pf_hvdc,
            VarPowerFlowReferenceType.Pt_hvdc,
            VarPowerFlowReferenceType.Im,
            VarPowerFlowReferenceType.Vmf,
            VarPowerFlowReferenceType.Vaf,
            VarPowerFlowReferenceType.Vmt,
            VarPowerFlowReferenceType.Vat,
            VarPowerFlowReferenceType.Vdc,
            VarPowerFlowReferenceType.Vf_dc,
            VarPowerFlowReferenceType.Vt_dc,
            VarPowerFlowReferenceType.If_dc,
            VarPowerFlowReferenceType.It_dc,
            VarPowerFlowReferenceType.Irf,
            VarPowerFlowReferenceType.Iif,
            VarPowerFlowReferenceType.Irt,
            VarPowerFlowReferenceType.Iit,
        ]
    else:
        # Injection-like models initialize at the solved power-flow operating
        # point. Active/reactive power and terminal voltage/angle are therefore
        # fixed boundary values throughout the local pseudo-transient solve.
        pf_var_references = [
            VarPowerFlowReferenceType.P,
            VarPowerFlowReferenceType.Q,
            VarPowerFlowReferenceType.Vm,
            VarPowerFlowReferenceType.Va,
            VarPowerFlowReferenceType.Vdc,
        ]

    return pf_var_references


def align_event_anchor_for_frozen_pf_reference(mdl: Block,
                                               pf_var: Var,
                                               pf_val: float,
                                               pf_ref: VarPowerFlowReferenceType | None = None) -> list[Var]:
    """
    Align event-parameter anchors that define a frozen power-flow reference.

    :param mdl: RMS symbolic block being initialized.
    :param pf_var: External power-flow variable being frozen to a PF value.
    :param pf_val: Power-flow value assigned to the frozen variable.
    :param pf_ref: Power-flow reference kind being frozen.
    :return: Event anchor variables aligned to the frozen PF value.
    """
    aligned_vars: list[Var] = list()

    for blk in mdl.get_all_blocks():
        init_expr: Expr | Const | None = blk.init_eqs.get(pf_var, None)
        if isinstance(init_expr, Var):
            if init_expr in blk.event_dict:
                # If a PF terminal variable is initialized from an event anchor,
                # the anchor must carry the same PF value after the terminal is frozen.
                blk.event_dict[init_expr] = Const(float(pf_val))
                aligned_vars.append(init_expr)
            else:
                pass
        else:
            pass

        # Empty-init pseudo-transient still needs frozen PF terminals and their
        # event anchors to agree. Infer direct affine relations such as
        # ``Qf_vsc_control - Qf = 0`` when the explicit init equation is absent.
        for event_var in list(blk.event_dict.keys()):
            if isinstance(event_var, Var):
                if event_var in aligned_vars:
                    pass
                elif pf_ref == VarPowerFlowReferenceType.Vm and event_var.name in ("V0", "Vm0"):
                    # ZIP-like loads normalize voltage by a nominal event anchor.
                    # When explicit init equations are intentionally empty, keep
                    # that anchor at the frozen PF voltage magnitude.
                    blk.event_dict[event_var] = Const(float(pf_val))
                    aligned_vars.append(event_var)
                else:
                    if _event_var_name_matches_pf_anchor(event_var=event_var, pf_var=pf_var):
                        event_value: Const | Expr | None = _infer_event_anchor_value_from_pf_equations(
                            equations=blk.algebraic_eqs,
                            event_var=event_var,
                            pf_var=pf_var,
                            pf_val=float(pf_val),
                        )
                        if isinstance(event_value, Const) and event_value.value is not None:
                            blk.event_dict[event_var] = event_value
                            aligned_vars.append(event_var)
                        else:
                            pass
                    else:
                        pass
            else:
                pass

    return aligned_vars


def _event_var_name_matches_pf_anchor(event_var: Var, pf_var: Var) -> bool:
    """
    Return whether an event variable name looks like an anchor for a PF variable.

    :param event_var: Candidate event parameter.
    :param pf_var: Frozen power-flow variable.
    :return: ``True`` when equation-based alignment is safe to attempt.
    """
    event_name: str = event_var.name.lower().strip("_")
    pf_name: str = pf_var.name.lower().strip("_")

    if event_name.endswith("0"):
        matches: bool = False
    elif len(event_name) == 0 or len(pf_name) == 0:
        matches = False
    elif event_name in pf_name or pf_name in event_name:
        matches = True
    else:
        matches = False

    return matches


def _infer_event_anchor_value_from_pf_equations(equations: list[Expr],
                                                event_var: Var,
                                                pf_var: Var,
                                                pf_val: float) -> Const | None:
    """
    Infer an event-anchor value from simple equations involving a frozen PF variable.

    :param equations: Algebraic residual equations to inspect.
    :param event_var: Event parameter variable to align.
    :param pf_var: Frozen power-flow reference variable.
    :param pf_val: Numeric value assigned to ``pf_var``.
    :return: Constant event-anchor value, or ``None`` when no safe relation exists.
    """
    inferred_value: Const | None = None

    for equation in equations:
        if inferred_value is None:
            if _expression_contains_var_uid(expr=equation, var=event_var):
                if _expression_contains_var_uid(expr=equation, var=pf_var):
                    update_expr: Expr | None = _build_reference_update_from_residual(eq=equation, ref_var=event_var)
                    if update_expr is None:
                        pass
                    else:
                        update_vars: list[Var] = [var for var in get_expression_vars(update_expr) if isinstance(var, Var)]
                        if all(var.uid == pf_var.uid for var in update_vars):
                            try:
                                numeric_value: float = float(eval_expr_uid(update_expr, {pf_var.uid: float(pf_val)}))
                            except Exception:
                                numeric_value = np.nan

                            if np.isfinite(numeric_value):
                                inferred_value = Const(numeric_value)
                            else:
                                pass
                        else:
                            pass
                else:
                    pass
            else:
                pass
        else:
            pass

    return inferred_value


def _expression_contains_var_uid(expr: Expr, var: Var) -> bool:
    """
    Return whether an expression contains a variable with the requested UID.

    :param expr: Symbolic expression to inspect.
    :param var: Variable to find by UID.
    :return: ``True`` when ``expr`` contains ``var``.
    """
    contains_var: bool = False

    for expr_var in get_expression_vars(expr):
        if isinstance(expr_var, Var) and expr_var.uid == var.uid:
            contains_var = True
        else:
            pass

    return contains_var


def _add_optional_expr(left_expr: Expr | None, right_expr: Expr | None) -> Expr | None:
    """
    Add two optional symbolic expressions.

    :param left_expr: Left expression or ``None``.
    :param right_expr: Right expression or ``None``.
    :return: Sum expression or ``None`` when one side is missing.
    """
    if left_expr is None or right_expr is None:
        result: Expr | None = None
    else:
        result = (left_expr + right_expr).simplify()

    return result


def _sub_optional_expr(left_expr: Expr | None, right_expr: Expr | None) -> Expr | None:
    """
    Subtract two optional symbolic expressions.

    :param left_expr: Left expression or ``None``.
    :param right_expr: Right expression or ``None``.
    :return: Difference expression or ``None`` when one side is missing.
    """
    if left_expr is None or right_expr is None:
        result: Expr | None = None
    else:
        result = (left_expr - right_expr).simplify()

    return result


def _mul_optional_expr(left_expr: Expr | None, right_expr: Expr | None) -> Expr | None:
    """
    Multiply two optional symbolic expressions.

    :param left_expr: Left expression or ``None``.
    :param right_expr: Right expression or ``None``.
    :return: Product expression or ``None`` when one side is missing.
    """
    if left_expr is None or right_expr is None:
        result: Expr | None = None
    else:
        result = (left_expr * right_expr).simplify()

    return result


def _div_optional_expr(left_expr: Expr | None, right_expr: Expr | None) -> Expr | None:
    """
    Divide two optional symbolic expressions.

    :param left_expr: Left expression or ``None``.
    :param right_expr: Right expression or ``None``.
    :return: Quotient expression or ``None`` when one side is missing.
    """
    if left_expr is None or right_expr is None:
        result: Expr | None = None
    else:
        result = (left_expr / right_expr).simplify()

    return result


def _split_affine_reference_expression(expr: Expr, ref_var: Var) -> tuple[Expr | None, Expr | None]:
    """
    Split an expression into ``coefficient * ref_var + remainder``.

    :param expr: Residual expression to split.
    :param ref_var: Reference variable to isolate.
    :return: Tuple ``(coefficient, remainder)`` or ``(None, None)`` if not affine.
    """
    if isinstance(expr, Var):
        if expr.uid == ref_var.uid:
            coefficient: Expr | None = Const(1.0)
            remainder: Expr | None = Const(0.0)
        else:
            coefficient = Const(0.0)
            remainder = expr
    elif isinstance(expr, Const):
        coefficient = Const(0.0)
        remainder = expr
    elif isinstance(expr, UnOp):
        operand_coefficient, operand_remainder = _split_affine_reference_expression(expr=expr.operand, ref_var=ref_var)
        coefficient = None if operand_coefficient is None else (-operand_coefficient).simplify()
        remainder = None if operand_remainder is None else (-operand_remainder).simplify()
    elif isinstance(expr, BinOp):
        left_has_ref: bool = _expression_contains_var_uid(expr=expr.left, var=ref_var)
        right_has_ref: bool = _expression_contains_var_uid(expr=expr.right, var=ref_var)

        if expr.op == "+":
            left_coefficient, left_remainder = _split_affine_reference_expression(expr=expr.left, ref_var=ref_var)
            right_coefficient, right_remainder = _split_affine_reference_expression(expr=expr.right, ref_var=ref_var)
            coefficient = _add_optional_expr(left_expr=left_coefficient, right_expr=right_coefficient)
            remainder = _add_optional_expr(left_expr=left_remainder, right_expr=right_remainder)
        elif expr.op == "-":
            left_coefficient, left_remainder = _split_affine_reference_expression(expr=expr.left, ref_var=ref_var)
            right_coefficient, right_remainder = _split_affine_reference_expression(expr=expr.right, ref_var=ref_var)
            coefficient = _sub_optional_expr(left_expr=left_coefficient, right_expr=right_coefficient)
            remainder = _sub_optional_expr(left_expr=left_remainder, right_expr=right_remainder)
        elif expr.op == "*":
            if left_has_ref and right_has_ref:
                coefficient = None
                remainder = None
            elif left_has_ref:
                left_coefficient, left_remainder = _split_affine_reference_expression(expr=expr.left, ref_var=ref_var)
                coefficient = _mul_optional_expr(left_expr=left_coefficient, right_expr=expr.right)
                remainder = _mul_optional_expr(left_expr=left_remainder, right_expr=expr.right)
            elif right_has_ref:
                right_coefficient, right_remainder = _split_affine_reference_expression(expr=expr.right, ref_var=ref_var)
                coefficient = _mul_optional_expr(left_expr=right_coefficient, right_expr=expr.left)
                remainder = _mul_optional_expr(left_expr=right_remainder, right_expr=expr.left)
            else:
                coefficient = Const(0.0)
                remainder = expr
        elif expr.op == "/":
            if right_has_ref:
                coefficient = None
                remainder = None
            elif left_has_ref:
                left_coefficient, left_remainder = _split_affine_reference_expression(expr=expr.left, ref_var=ref_var)
                coefficient = _div_optional_expr(left_expr=left_coefficient, right_expr=expr.right)
                remainder = _div_optional_expr(left_expr=left_remainder, right_expr=expr.right)
            else:
                coefficient = Const(0.0)
                remainder = expr
        else:
            coefficient = None
            remainder = None
    else:
        if _expression_contains_var_uid(expr=expr, var=ref_var):
            coefficient = None
            remainder = None
        else:
            coefficient = Const(0.0)
            remainder = expr

    return coefficient, remainder


def _build_reference_update_from_residual(eq: Expr, ref_var: Var) -> Expr | None:
    """
    Build a reference update expression from a residual equation.

    :param eq: Residual equation interpreted as ``eq = 0``.
    :param ref_var: Reference variable to isolate.
    :return: Expression for ``ref_var`` or ``None`` when the equation is not safely affine.
    """
    coefficient, remainder = _split_affine_reference_expression(expr=eq, ref_var=ref_var)

    if coefficient is None or remainder is None:
        update_expr: Expr | None = None
    elif isinstance(coefficient, Const) and coefficient.value == 0.0:
        update_expr = None
    else:
        update_expr = ((-remainder) / coefficient).simplify()

    return update_expr


def _find_equilibrium_reference_update_eq(mdl: Block, ref_var: Var) -> Expr | None:
    """
    Infer a reference update expression from the model residual equations.

    :param mdl: Flattened RMS block used by pseudo-transient initialization.
    :param ref_var: Unresolved event/reference parameter being promoted.
    :return: Inferred update expression or ``None`` when no safe equation is found.
    """
    update_expr: Expr | None = None
    equations: list[Expr] = list()
    equations.extend(mdl.state_eqs)
    equations.extend(mdl.algebraic_eqs)

    for eq in equations:
        if update_expr is None:
            if _expression_contains_var_uid(expr=eq, var=ref_var):
                update_expr = _build_reference_update_from_residual(eq=eq, ref_var=ref_var)
            else:
                pass
        else:
            pass

    return update_expr


def _build_ordered_init_update_eqs(mdl: Block) -> Dict[Var, Expr | Const]:
    """
    Build init-equation update expressions with explicit dependency ordering.

    :param mdl: RMS symbolic block containing initialization equations.
    :return: Initialization equations with dependent init-equations substituted in topological order.
    """
    ordered_update_eqs: Dict[Var, Expr | Const] = dict()

    try:
        init_vars, dependencies, topo_order, _ = build_explicit_init_graph(mdl=mdl)
    except RuntimeError:
        init_vars = dict()
        dependencies = dict()
        topo_order = list()

    substitution_map: Dict[Var, Expr] = dict()
    for var in topo_order:
        eq: Expr | Const = init_vars[var]
        var_dependencies: List[Var] = dependencies[var]

        if var in var_dependencies:
            # A self-implicit init equation needs a scalar solve in explicit init.
            # Do not turn it into a direct pseudo-transient reference assignment.
            pass
        else:
            dependent_substitutions: Dict[Var, Expr] = dict()
            for dep in var_dependencies:
                dep_expr: Expr | None = substitution_map.get(dep, None)
                if dep_expr is None:
                    pass
                else:
                    dependent_substitutions[dep] = dep_expr

            if len(dependent_substitutions) > 0:
                update_eq: Expr | Const = eq.subs(dependent_substitutions).simplify()
            else:
                update_eq = eq

            ordered_update_eqs[var] = update_eq
            if isinstance(update_eq, Expr) and not isinstance(update_eq, Const):
                substitution_map[var] = update_eq
            else:
                pass

    return ordered_update_eqs


class PseudoTransientInitProblem:
    """
    Lightweight problem class for pseudo-transient initialization of a single device block.
    Similar interface to RmsProblemDae but for initialization only.
    """
    __slots__ = (
        "x_global",
        "block",
        "compiler_names_dict",
        "alias_names_dict",
        "_uid2idx_vars_global",
        "_variable_parameters",
        "_constant_parameters",
        "_event_params_fn",
        "_equilibrium_reference_update_eqs",
        "_ordered_init_update_eqs",
        "pseudo_transient_options",
        "equilibrium_references_as_equations",
        "equilibrium_references_as_params",
        "equilibrium_inputs_as_params",
        "_equilibrium_reference_eqs",
        "_diff_vars",
        "_all_vars",
        "_uid2idx_vars",
        "_uid2idx_diff",
        "_compiler_names_dict_local",
        "_alias_names_dict_local",
        "_state_vars",
        "_algebraic_vars",
        "_state_eqs",
        "_algebraic_eqs",
        "_has_full_numerical_jacobian",
        "_rhs_fn",
        "_derivative_fn",
        "_jacobian_fn",
        "_constant_params",
        "_variable_parameters_values",
        "_equilibrium_reference_values",
        "_equilibrium_reference_update_vars",
        "_equilibrium_reference_update_expressions",
        "_equilibrium_reference_update_indices",
        "_equilibrium_reference_update_fn",
        "_equilibrium_input_update_expressions",
        "_equilibrium_input_param_indices",
        "_equilibrium_input_update_indices",
        "_equilibrium_input_update_fn",
        "_n_states",
        "_n_vars",
        "_uid2idx_params",
        "_uid2idx_event_params",
    )

    def __init__(self,
                 block: Block,
                 x_global: Vec,
                 compiler_names_dict: Dict[int, str],
                 alias_names_dict: Dict[int, str],
                 uid2idx_vars: Dict[int, int],
                 variable_parameters: List[Var],
                 constant_parameters: List[Var],
                 equilibrium_reference_update_eqs: Dict[Var, Expr] | None = None,
                 ordered_init_update_eqs: Dict[Var, Expr | Const] | None = None,
                 pseudo_transient_options: object | None = None,
                 VARS_NAME: str = "vars",
                 DIFF_NAME: str = "diff",
                 VARIABLE_PARAMS_NAME: str = "vprms",
                 CONSTANT_PARAMS_NAME: str = "cprms"):
        """
        Initialize problem for pseudo-transient initialization.
        :param block:
        :param x_global:
        :param compiler_names_dict:
        :param alias_names_dict:
        :param uid2idx_vars:
        :param variable_parameters:
        :param constant_parameters:
        :param equilibrium_reference_update_eqs:
        :param ordered_init_update_eqs:
        :param pseudo_transient_options:
        :param VARS_NAME:
        :param DIFF_NAME:
        :param VARIABLE_PARAMS_NAME:
        :param CONSTANT_PARAMS_NAME:
        """

        self.x_global = x_global
        self.block = block
        self.compiler_names_dict = compiler_names_dict
        self.alias_names_dict = alias_names_dict
        self._uid2idx_vars_global = uid2idx_vars
        self._variable_parameters = list(variable_parameters)
        self._constant_parameters = constant_parameters
        self._event_params_fn: SymbolicParamsVector | None = None
        self._equilibrium_reference_update_eqs: Dict[Var, Expr] = (
            dict() if equilibrium_reference_update_eqs is None else dict(equilibrium_reference_update_eqs)
        )
        self._ordered_init_update_eqs: Dict[Var, Expr | Const] = (
            dict() if ordered_init_update_eqs is None else dict(ordered_init_update_eqs)
        )

        event_uid_map: dict[int, Expr | Const] = dict()
        mode_uid_map: dict[int, Expr | Const] = dict()
        param_uid_map: dict[int, Const] = dict()
        for blk in block.get_all_blocks():
            event_uid_map.update({v.uid: eq for v, eq in blk.event_dict.items() if isinstance(v, Var)})
            mode_uid_map.update({v.uid: eq for v, eq in blk.mode_dict.items() if isinstance(v, Var)})
            param_uid_map.update({v.uid: c for v, c in blk.parameters.items() if isinstance(v, Var)})
        fixed_parameter_uids: set[int] = set(event_uid_map.keys()) | set(mode_uid_map.keys()) | set(param_uid_map.keys())
        
        self.pseudo_transient_options: object | None = pseudo_transient_options
        if pseudo_transient_options is None:
            self.equilibrium_inputs_as_params: bool = False
            self.equilibrium_references_as_params: bool = False
            self.equilibrium_references_as_equations: bool = False
        else:
            self.equilibrium_inputs_as_params: bool = bool(pseudo_transient_options.equilibrium_inputs_as_params)
            self.equilibrium_references_as_params: bool = bool(pseudo_transient_options.equilibrium_references_as_params)
            self.equilibrium_references_as_equations: bool = bool(pseudo_transient_options.equilibrium_references_as_equations)

        equilibrium_input_uids: set[int] = set()
        if self.equilibrium_inputs_as_params:
            equilibrium_input_uids = {
                v.uid for v in block.in_vars
                if isinstance(v, Var)
                and isinstance(self._ordered_init_update_eqs.get(v, None), Expr)
                and not isinstance(self._ordered_init_update_eqs.get(v, None), Const)
            }
        else:
            pass

        equilibrium_update_dependency_eqs: List[Expr] = list()
        for in_var in block.in_vars:
            if isinstance(in_var, Var) and in_var.uid in equilibrium_input_uids:
                input_expr: Expr | Const | None = self._ordered_init_update_eqs.get(in_var, None)
                if isinstance(input_expr, Expr) and not isinstance(input_expr, Const):
                    equilibrium_update_dependency_eqs.append(input_expr)
                else:
                    pass
            else:
                pass

        if self.equilibrium_references_as_params or self.equilibrium_references_as_equations:
            for ref_expr in self._equilibrium_reference_update_eqs.values():
                if isinstance(ref_expr, Expr) and not isinstance(ref_expr, Const):
                    equilibrium_update_dependency_eqs.append(ref_expr)
                else:
                    pass
        else:
            pass

        # Get block's variables. Equilibrium inputs can be compiled as mutable
        # parameters so the generator/exciter equilibrium stays on the physical branch.
        self._state_vars = list(block.state_vars)
        self._algebraic_vars = [
            v for v in block.algebraic_vars
            if not (isinstance(v, Var) and v.uid in equilibrium_input_uids)
        ]

        # Ensure local init system is square whenever equations reference extra
        # free variables. Promote such vars to local algebraic unknowns.
        known_uids = {v.uid for v in self._state_vars + self._algebraic_vars if isinstance(v, Var)}
        eqs = list(block.state_eqs) + list(block.algebraic_eqs) + equilibrium_update_dependency_eqs
        for eq in eqs:
            for used_var in get_expression_vars(eq):
                if not isinstance(used_var, Var):
                    continue
                if used_var.uid in known_uids:
                    continue
                if used_var.uid in equilibrium_input_uids:
                    continue
                if used_var.uid in fixed_parameter_uids:
                    continue
                if used_var.uid in self.compiler_names_dict:
                    continue
                self._algebraic_vars.append(used_var)
                known_uids.add(used_var.uid)

        self._all_vars = self._state_vars + self._algebraic_vars
        self._n_vars = len(self._all_vars)
        self._n_states = len(self._state_vars)
        self._diff_vars = list(block.diff_vars)
        self._state_eqs = list(block.state_eqs)
        self._algebraic_eqs = list(block.algebraic_eqs)
        self._has_full_numerical_jacobian: bool = True

        # Build local indexing for this block initialization problem.
        self._uid2idx_vars = {v.uid: i for i, v in enumerate(self._all_vars)}
        self._uid2idx_diff = {v.uid: i for i, v in enumerate(self._diff_vars)}

        self._compiler_names_dict_local = dict(compiler_names_dict)
        self._alias_names_dict_local = dict(alias_names_dict)

        # Global boundary indices address x_global, never the smaller local
        # Newton vector. Keep local unknowns and mutable parameter channels
        # independent while freezing supplied finite external startup values.
        global_uid: int
        global_index: int
        for global_uid, global_index in self._uid2idx_vars_global.items():
            if (global_uid not in self._uid2idx_vars
                    and global_uid not in fixed_parameter_uids
                    and global_uid not in equilibrium_input_uids):
                boundary_value: float = float(self.x_global[global_index])
                if np.isfinite(boundary_value):
                    self._compiler_names_dict_local[global_uid] = repr(boundary_value)
                    self._alias_names_dict_local[global_uid] = f"boundary_{global_uid}"
                else:
                    pass
            else:
                pass

        for uid, i in self._uid2idx_vars.items():
            self._compiler_names_dict_local[uid] = f"{VARS_NAME}[{i}]"
            self._alias_names_dict_local[uid] = f"{VARS_NAME}_{i}"

        for uid, i in self._uid2idx_diff.items():
            self._compiler_names_dict_local[uid] = f"{DIFF_NAME}[{i}]"
            self._alias_names_dict_local[uid] = f"{DIFF_NAME}_{i}"

        for i, parameter_var in enumerate(self._variable_parameters):
            if isinstance(parameter_var, Var) and parameter_var.uid in fixed_parameter_uids:
                if parameter_var.uid in self._uid2idx_vars:
                    pass
                else:
                    self._compiler_names_dict_local[parameter_var.uid] = f"{VARIABLE_PARAMS_NAME}[{i}]"
                    self._alias_names_dict_local[parameter_var.uid] = f"{VARIABLE_PARAMS_NAME}_{i}"
            else:
                pass

        self._equilibrium_input_param_indices: list[int] = list()
        self._equilibrium_input_update_indices: list[int] = list()
        self._equilibrium_input_update_expressions: list[Expr] = list()
        self._equilibrium_input_update_fn: SymbolicVector | None = None

        for in_var in self.block.in_vars:
            if not isinstance(in_var, Var) or in_var.uid not in equilibrium_input_uids:
                continue
            else:
                pass
            pidx = self._ensure_variable_parameter(in_var)
            self._compiler_names_dict_local[in_var.uid] = f"{VARIABLE_PARAMS_NAME}[{pidx}]"
            self._alias_names_dict_local[in_var.uid] = f"{VARIABLE_PARAMS_NAME}_{pidx}"
            input_expr = self._ordered_init_update_eqs.get(in_var, None)
            if isinstance(input_expr, Expr) and not isinstance(input_expr, Const):
                self._equilibrium_input_param_indices.append(pidx)
                self._equilibrium_input_update_indices.append(pidx)
                self._equilibrium_input_update_expressions.append(input_expr)
            else:
                pass

        self._equilibrium_reference_update_vars: list[Var] = list()
        self._equilibrium_reference_update_indices: list[int] = list()
        self._equilibrium_reference_update_expressions: list[Expr] = list()
        self._equilibrium_reference_update_fn: SymbolicVector | None = None

        if self.equilibrium_references_as_params and not self.equilibrium_references_as_equations:
            for ref_var, ref_expr in self._equilibrium_reference_update_eqs.items():
                if isinstance(ref_var, Var) and isinstance(ref_expr, Expr) and not isinstance(ref_expr, Const):
                    vidx = self._uid2idx_vars.get(ref_var.uid, None)
                    if vidx is not None:
                        self._equilibrium_reference_update_vars.append(ref_var)
                        self._equilibrium_reference_update_indices.append(vidx)
                        self._equilibrium_reference_update_expressions.append(ref_expr)
                    else:
                        pass
                else:
                    pass
        else:
            pass

        # Some device-only blocks may keep open controller inputs in `in_vars`.
        # If those inputs are used in equations but are not part of state/algebraic
        # unknowns, ensure they still get a compiler mapping by freezing them to
        # their current numeric guess.
        for in_var in self.block.in_vars:
            if not isinstance(in_var, Var):
                continue
            if in_var.uid in self._compiler_names_dict_local:
                continue

            guessed_value = 0.0
            if in_var.uid in self._uid2idx_vars_global:
                guessed_value = float(self.x_global[self._uid2idx_vars_global[in_var.uid]])
            elif in_var in self.block.init_eqs:
                init_eq = self.block.init_eqs[in_var]
                if isinstance(init_eq, Const) and init_eq.value is not None:
                    guessed_value = float(init_eq.value)

            self._compiler_names_dict_local[in_var.uid] = repr(guessed_value)
            self._alias_names_dict_local[in_var.uid] = f"input_{in_var.uid}"
        
        # Initialize parameter arrays
        self._variable_parameters_values = np.zeros(len(self._variable_parameters), dtype=float)
        for i, p in enumerate(self._variable_parameters):
            if p.uid in event_uid_map:
                eq = event_uid_map[p.uid]
                if isinstance(eq, Const) and eq.value is not None:
                    self._variable_parameters_values[i] = float(eq.value)
            elif p.uid in mode_uid_map:
                eq = mode_uid_map[p.uid]
                if isinstance(eq, Const) and eq.value is not None:
                    self._variable_parameters_values[i] = float(eq.value)
        self._constant_params = np.array([
            (param_uid_map[p.uid].value if p.uid in param_uid_map and param_uid_map[p.uid] is not None else 0.0)
            for p in constant_parameters
        ], dtype=float)
        self._equilibrium_reference_values: dict[str, float] = dict()
        self._equilibrium_reference_eqs: list[Expr] = self._build_equilibrium_reference_equations()
        self._compile_equilibrium_input_update_function(VARS_NAME, DIFF_NAME, VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME)
        self._compile_equilibrium_reference_update_function(VARS_NAME, DIFF_NAME, VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME)
        
        # Compile functions
        self._compile_functions(VARS_NAME, DIFF_NAME, VARIABLE_PARAMS_NAME, CONSTANT_PARAMS_NAME)
        self._compile_event_params_function(VARIABLE_PARAMS_NAME, "glob_time")
        self.update_variable_params(0.0)
        self.update_variable_params(0.0)

        self._uid2idx_params: Dict[int, int] = dict()
        self._uid2idx_event_params: Dict[int, int] = dict()

    def _ensure_variable_parameter(self, var: Var) -> int:
        """

        :param var:
        :return:
        """
        for i, param in enumerate(self._variable_parameters):
            if isinstance(param, Var) and param.uid == var.uid:
                return i
        self._variable_parameters.append(var)
        return len(self._variable_parameters) - 1

    def _build_equilibrium_reference_equations(self) -> list[Expr]:
        """
        Build explicit residual equations for equilibrium reference variables.

        :return: Algebraic residual equations to append to the local pseudo-transient problem.
        """
        equations: list[Expr] = list()

        if not self.equilibrium_references_as_equations:
            return equations
        else:
            pass

        for ref_var, ref_expr in self._equilibrium_reference_update_eqs.items():
            if isinstance(ref_var, Var) and isinstance(ref_expr, Expr) and not isinstance(ref_expr, Const):
                if ref_var.uid in self._uid2idx_vars:
                    equations.append(ref_var - ref_expr)
                else:
                    pass
            else:
                pass

        return equations

    def _compile_equilibrium_input_update_function(self,
                                                   VARS_NAME: str,
                                                   DIFF_NAME: str,
                                                   VARIABLE_PARAMS_NAME: str,
                                                   CONSTANT_PARAMS_NAME: str) -> None:
        """
        Compile copied initialization equations for equilibrium input parameters.

        :param VARS_NAME: Symbolic variable vector name.
        :param DIFF_NAME: Symbolic derivative vector name.
        :param VARIABLE_PARAMS_NAME: Symbolic runtime parameter vector name.
        :param CONSTANT_PARAMS_NAME: Symbolic constant parameter vector name.
        :return: None.
        """
        if len(self._equilibrium_input_update_expressions) == 0:
            self._equilibrium_input_update_fn = None
        else:
            self._equilibrium_input_update_fn = SymbolicVector(
                self._equilibrium_input_update_expressions,
                self._compiler_names_dict_local,
                self._alias_names_dict_local,
                VARS_NAME,
                DIFF_NAME,
                VARIABLE_PARAMS_NAME,
                CONSTANT_PARAMS_NAME,
            )

    def _compile_equilibrium_reference_update_function(self,
                                                       VARS_NAME: str,
                                                       DIFF_NAME: str,
                                                       VARIABLE_PARAMS_NAME: str,
                                                       CONSTANT_PARAMS_NAME: str) -> None:
        """
        Compile copied initialization equations for unresolved reference parameters.

        :param VARS_NAME: Symbolic variable vector name.
        :param DIFF_NAME: Symbolic derivative vector name.
        :param VARIABLE_PARAMS_NAME: Symbolic runtime parameter vector name.
        :param CONSTANT_PARAMS_NAME: Symbolic constant parameter vector name.
        :return: None.
        """
        if len(self._equilibrium_reference_update_expressions) == 0:
            self._equilibrium_reference_update_fn = None
        else:
            self._equilibrium_reference_update_fn = SymbolicVector(
                self._equilibrium_reference_update_expressions,
                self._compiler_names_dict_local,
                self._alias_names_dict_local,
                VARS_NAME,
                DIFF_NAME,
                VARIABLE_PARAMS_NAME,
                CONSTANT_PARAMS_NAME,
            )

    def update_equilibrium_parameters(self, x: Vec) -> None:
        """

        :param x:
        :return:
        """
        if self.equilibrium_references_as_equations:
            return

        if self._equilibrium_input_update_fn is None and self._equilibrium_reference_update_fn is None:
            return
        else:
            pass

        if x.size == 0:
            return

        if self._equilibrium_input_update_fn is not None:
            dx_values: Vec = np.zeros(self.get_diff_var_number(), dtype=float)
            input_values: Vec = np.array(
                self._equilibrium_input_update_fn(x, dx_values, self._variable_parameters_values, self._constant_params),
                dtype=float,
                copy=False,
            )
            for update_idx, param_idx in enumerate(self._equilibrium_input_update_indices):
                if update_idx < input_values.size and 0 <= param_idx < len(self._variable_parameters_values):
                    self._variable_parameters_values[param_idx] = float(input_values[update_idx])
                else:
                    pass
        else:
            pass

        if self._equilibrium_reference_update_fn is not None:
            dx_values: Vec = np.zeros(self.get_diff_var_number(), dtype=float)
            reference_values: Vec = np.array(
                self._equilibrium_reference_update_fn(x, dx_values, self._variable_parameters_values, self._constant_params),
                dtype=float,
                copy=False,
            )
            for update_idx, ref_idx in enumerate(self._equilibrium_reference_update_indices):
                if update_idx < reference_values.size and 0 <= ref_idx < x.size:
                    value = float(reference_values[update_idx])
                    x[ref_idx] = value
                    self._equilibrium_reference_values[self._equilibrium_reference_update_vars[update_idx].name] = value
                else:
                    pass
        else:
            pass
    
    def _compile_functions(self, VARS_NAME: str, DIFF_NAME: str,
                           VARIABLE_PARAMS_NAME: str, CONSTANT_PARAMS_NAME: str):
        """
        Compile RHS and derivative functions for the block.
        :param VARS_NAME:
        :param DIFF_NAME:
        :param VARIABLE_PARAMS_NAME:
        :param CONSTANT_PARAMS_NAME:
        :return:
        """
        # Collect all equations
        all_eqs = list(self.block.state_eqs) + list(self.block.algebraic_eqs) + list(self._equilibrium_reference_eqs)
        # Compile RHS function
        if all_eqs:
            self._rhs_fn = SymbolicVector(
                all_eqs,
                self._compiler_names_dict_local,
                self._alias_names_dict_local,
                VARS_NAME,
                DIFF_NAME,
                VARIABLE_PARAMS_NAME,
                CONSTANT_PARAMS_NAME
            )
            self._jacobian_fn = SymbolicJacobian(
                eqs=all_eqs,
                variables=self._all_vars,
                compiler_names_dict=self._compiler_names_dict_local,
                alias_names_dict=self._alias_names_dict_local,
                VARS_NAME=VARS_NAME,
                DIFF_NAME=DIFF_NAME,
                EVENT_PARAMS_NAME=VARIABLE_PARAMS_NAME,
                PARAMS_NAME=CONSTANT_PARAMS_NAME,
                use_jit=True,
            )
        else:
            self._rhs_fn = None
            self._jacobian_fn = None
        
        # Compile derivative function
        self._derivative_fn = SymbolicDerivative(
            vars=self._all_vars,
            uid2idx_vars=self._uid2idx_vars,
            diff_vars=self._diff_vars,
            compiler_names_dict=self._compiler_names_dict_local
        )

    def _compile_event_params_function(self, VARIABLE_PARAMS_NAME: str, TIME_NAME: str) -> None:
        """

        :param VARIABLE_PARAMS_NAME:
        :param TIME_NAME:
        :return:
        """
        param_eqs: list[Expr | Const] = []
        for i, param in enumerate(self._variable_parameters):
            eq = self.block.event_dict.get(param, self.block.mode_dict.get(param))
            if eq is None or (isinstance(eq, Const) and eq.value is None):
                current = 0.0
                if i < len(self._variable_parameters_values):
                    current = float(self._variable_parameters_values[i])
                eq = Const(current)
            param_eqs.append(eq)

        self._event_params_fn = SymbolicParamsVector(
            eqs=param_eqs,
            compiler_names_dict=self._compiler_names_dict_local,
            alias_names_dict=self._alias_names_dict_local,
            EVENT_PARAMS_NAME=VARIABLE_PARAMS_NAME,
            TIME_NAME=TIME_NAME,
            use_jit=True,
        )
    
    def get_all_vars_number(self) -> int:
        return self._n_vars
    
    def get_states_number(self) -> int:
        return self._n_states
    
    def get_algebraic_var_number(self) -> int:
        return len(self._algebraic_vars)
    
    def get_diff_var_number(self) -> int:
        return len(self._diff_vars)
    
    def get_algebraic_vars(self):
        return self._algebraic_vars

    def algebraic_vars(self):
        return self._algebraic_vars

    def state_vars(self):
        return self._state_vars
    
    def rhs_algebraic(self, x: Vec, dx: Vec) -> Vec:
        """
        Evaluate algebraic residuals without advancing equilibrium updates.

        :param x: Original candidate in local state/algebraic order.
        :param dx: Derivative values held fixed during this evaluation.
        :return: Copied algebraic rows from one prepared full residual.
        """
        # Both components observe the same candidate even when the solver asks
        # for g before f or repeats a component during a line search.
        full_rhs: Vec = self._compute_rhs_full(x, dx, 1.0)
        return full_rhs[self._n_states:].copy()
    
    def rhs_state(self, x: Vec, dx: Vec) -> Vec:
        """
        Evaluate state residuals without advancing equilibrium updates.

        :param x: Original candidate in local state/algebraic order.
        :param dx: Derivative values held fixed during this evaluation.
        :return: Copied state rows, or an empty vector for a stateless block.
        """
        if self._rhs_fn is None or self._n_states == 0:
            return np.zeros(0, dtype=float)
        else:
            # Reuse the full owner so input/reference staging cannot diverge
            # from the algebraic component or from Jacobian probes.
            full_rhs: Vec = self._compute_rhs_full(x, dx, 1.0)
            return full_rhs[:self._n_states].copy()
    
    def get_dx(self, x: Vec, xn: Vec, dx: Vec, h: float) -> Vec:
        """
        Compute derivatives.
        :param x:
        :param xn:
        :param dx:
        :param h:
        :return:
        """
        return self._derivative_fn(x, xn, dx, h)
    
    def update_variable_params(self, t: float):
        """
        Update variable parameters at time t.
        :param t:
        :return:
        """
        if self._event_params_fn is None:
            return
        self._variable_parameters_values = np.array(
            self._event_params_fn(self._variable_parameters_values, float(t)),
            dtype=float,
            copy=True,
        )

    def _compute_numerical_jacobian(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        """
        Differentiate the prepared residual, including equilibrium updates.

        :param x: Original local candidate; perturbations use independent copies.
        :param dx: Derivatives held fixed across all residual probes.
        :param h: Step supplied to the existing compiled Jacobian when applicable.
        :return: CSC Jacobian; active updates use central finite differences.
        """
        n_total: int = self._n_vars
        if n_total == 0:
            return sp.csc_matrix((0, 0))
        else:
            pass

        # The compiled partial Jacobian treats mutable channels as constants.
        # It is valid only when input/reference preparation is inactive.
        active_updates: bool = not self.equilibrium_references_as_equations and (
            self._equilibrium_input_update_fn is not None or self._equilibrium_reference_update_fn is not None
        )
        if not active_updates and self._jacobian_fn is not None:
            try:
                return self._jacobian_fn(x, dx, self._variable_parameters_values, self._constant_params, h).tocsc()
            except Exception:
                # Retain the existing numerical fallback if compilation cannot
                # evaluate this candidate; each probe still observes one point.
                pass
        else:
            pass

        # Allocate the known residual/unknown shape once. Central differences
        # balance truncation and roundoff without inventing physical scales.
        row_count: int = len(self._state_eqs) + len(self._algebraic_eqs) + len(self._equilibrium_reference_eqs)
        base_eps: float = float(np.cbrt(np.finfo(float).eps))
        jacobian_dense: np.ndarray = np.zeros((row_count, n_total), dtype=float)
        column: int
        for column in range(n_total):
            step: float = base_eps * max(1.0, abs(float(x[column])))
            x_plus: Vec = x.copy()
            x_minus: Vec = x.copy()
            x_plus[column] += step
            x_minus[column] -= step
            rhs_plus: Vec = self._compute_rhs_full(x_plus, dx, h)
            rhs_minus: Vec = self._compute_rhs_full(x_minus, dx, h)
            jacobian_dense[:, column] = (rhs_plus - rhs_minus) / (2.0 * step)

        return sp.csc_matrix(jacobian_dense)

    def _compute_rhs_full(self, x: Vec, dx: Vec, h: float) -> Vec:
        """
        Evaluate one input-then-reference preparation transactionally.

        :param x: Original local candidate, preserved on every exit.
        :param dx: Fixed derivative values passed to the compiled residual.
        :param h: Existing interface step; preparation itself is step independent.
        :return: Independent full residual in state then algebraic row order.
        """
        if self._rhs_fn is None:
            return np.zeros(0, dtype=float)
        else:
            pass

        active_updates: bool = not self.equilibrium_references_as_equations and (
            self._equilibrium_input_update_fn is not None or self._equilibrium_reference_update_fn is not None
        )
        if active_updates:
            # The explicit update owner intentionally writes its candidate and
            # channels. Restrict those writes to this temporary evaluation and
            # restore existing channel/lookup contents even after an exception.
            candidate: Vec = x.copy()
            parameter_values: Vec = self._variable_parameters_values.copy()
            reference_values: dict[str, float] = self._equilibrium_reference_values.copy()
            try:
                self.update_equilibrium_parameters(candidate)
                return np.array(self._rhs_fn(candidate, dx, self._variable_parameters_values, self._constant_params),
                                dtype=float, copy=True)
            finally:
                self._variable_parameters_values[:] = parameter_values
                self._equilibrium_reference_values.clear()
                self._equilibrium_reference_values.update(reference_values)
        else:
            # Preserve the compiled path for ordinary or equation-based models,
            # copying its reusable result buffer before a subsequent evaluation.
            return np.array(self._rhs_fn(x, dx, self._variable_parameters_values, self._constant_params),
                            dtype=float, copy=True)

    def get_j11(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        """
        Jacobian of state equations w.r.t. state variables.
        :param x:
        :param dx:
        :param h:
        :return:
        """
        if self._n_states == 0:
            return sp.csc_matrix((0, 0))
        J_full = self._compute_numerical_jacobian(x, dx, h)
        return J_full[:self._n_states, :self._n_states]

    def get_j12(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        """
        Jacobian of state equations w.r.t. algebraic variables.
        :param x:
        :param dx:
        :param h:
        :return:
        """
        if self._n_states == 0:
            return sp.csc_matrix((0, self.get_algebraic_var_number()))
        J_full = self._compute_numerical_jacobian(x, dx, h)
        n_alg = self.get_algebraic_var_number()
        return J_full[:self._n_states, self._n_states:self._n_states + n_alg]

    def get_j21(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        """
        Jacobian of algebraic equations w.r.t. state variables.
        :param x:
        :param dx:
        :param h:
        :return:
        """
        n_alg = self.get_algebraic_var_number()
        if self._n_states == 0 or n_alg == 0:
            return sp.csc_matrix((n_alg, self._n_states))
        J_full = self._compute_numerical_jacobian(x, dx, h)
        return J_full[self._n_states:, :self._n_states]

    def get_j22(self, x: Vec, dx: Vec, h: float) -> sp.csc_matrix:
        """
        Jacobian of algebraic equations w.r.t. algebraic variables.
        :param x:
        :param dx:
        :param h:
        :return:
        """
        n_alg = self.get_algebraic_var_number()
        if n_alg == 0:
            return sp.csc_matrix((0, 0))
        if self._n_states == 0:
            return self._compute_numerical_jacobian(x, dx, h)
        J_full = self._compute_numerical_jacobian(x, dx, h)
        return J_full[self._n_states:, self._n_states:self._n_states + n_alg]

    @property
    def uid2idx_vars(self):
        return self._uid2idx_vars


def init_pseudo_transient(mdl: Block,
                          sys_vars: Dict[int, Var],
                          variable_parameters: List[Var],
                          event_parameters_eqs: List[Expr | Const],
                          constant_parameters: List[Var],
                          init_guess: Dict[int, float],
                          uid2idx_vars: Dict[int, int],
                          uid2idx_params: Dict[int, int],
                          uid2idx_event_params: Dict[int, int],
                          compiler_names_dict: Dict[int, str],
                          alias_names_dict: Dict[int, str],
                          VARIABLE_PARAMS_NAME: str,
                          TIME_NAME: str,
                          VARS_NAME: str,
                          DIFF_NAME: str,
                          CONSTANT_PARAMS_NAME: str,
                          dtau0: float = 1e-3,
                          max_iter: int = 100,
                          tol: float = 1e-6,
                          verbose: bool = False,
                          pseudo_transient_options: object | None = None) -> Dict[int, float | int | complex | None]:
    """
    Initialize a private model copy from supplied seeds before random retries.

    The first local candidate reuses finite UID values, with structural zero for
    unavailable coordinates. These are initial guesses, not fixed states or
    physical source defaults. Preparation or solver failure retains the random
    fallback within the existing total of fifty initialization attempts.

    :param mdl: Source block, preserved while initialization works on its copy.
    :param sys_vars: Global system variables indexed by UID.
    :param variable_parameters: Ordered runtime parameter variables.
    :param event_parameters_eqs: Runtime expressions receiving recovered constants.
    :param constant_parameters: Ordered physical parameter variables.
    :param init_guess: Existing UID seeds, updated with solved system coordinates.
    :param uid2idx_vars: Global system UID-to-coordinate mapping.
    :param uid2idx_params: Physical parameter UID-to-index mapping.
    :param uid2idx_event_params: Runtime parameter UID-to-index mapping.
    :param compiler_names_dict: Existing UID-to-vector expression bindings.
    :param alias_names_dict: Existing aliases used by compiled expressions.
    :param VARIABLE_PARAMS_NAME: Runtime parameter vector name for compilation.
    :param TIME_NAME: Runtime time symbol retained by the caller interface.
    :param VARS_NAME: System vector name for compilation.
    :param DIFF_NAME: Derivative vector name for compilation.
    :param CONSTANT_PARAMS_NAME: Physical parameter vector name for compilation.
    :param dtau0: Requested initial step; the current constructor retains its fixed step.
    :param max_iter: Requested iteration count; the current constructor retains its fixed count.
    :param tol: Requested residual tolerance, subject to existing acceptance floors.
    :param verbose: Enable existing solver diagnostics and optional plots.
    :param pseudo_transient_options: Existing local solver and equilibrium policies.
    :return: Global UID lookup with solved local values and other supplied entries retained.
    :raises RuntimeError: If attempts fail the residual guard and best effort is disabled.
    """
    # Import here to avoid circular imports
    from VeraGridEngine.Simulations.Rms.numerical.pseudo_transient import PseudoTransient, PseudoTransientOptions

    if pseudo_transient_options is None:
        pseudo_transient_options = PseudoTransientOptions(
            equilibrium_references_as_params=True,
        )
    else:
        pass

    # Work on a copy so initialization rewrites do not alter the original model.
    mdl_work = deepcopy(mdl)
    mdl_work.unify_blocks()

    # Initialization-only stabilization: relax hard limiter bounds to avoid
    # branch-locking/flat Jacobian regions during pseudo-transient startup.
    wide_limits = {
        "Pmax": 1e3,
        "Pmin": -1e3,
        "Uo": 1e3,
        "Uc": -1e3,
        "VaMaxPu": 1e3,
        "VaMinPu": -1e3,
        "EfeMaxPu": 1e3,
        "EfeMinPu": -1e3,
        "V_oelmax": 1e3,
        "V_oelmin": -1e3,
        "V_invmax": 1e3,
        "V_invmin": -1e3,
    }

    for blk in mdl_work.get_all_blocks():
        for var, value in list(blk.event_dict.items()):
            if not isinstance(var, Var):
                continue
            if var.name not in wide_limits:
                continue
            if not isinstance(value, Const):
                continue
            blk.event_dict[var] = Const(float(wide_limits[var.name]))

    # Build global snapshot vector from current init guess.
    x_global = np.zeros(len(uid2idx_vars), dtype=float)
    seeded_init_uids: set[int] = set()
    for uid, val in init_guess.items():
        if uid in uid2idx_vars and val is not None:
            gidx = uid2idx_vars[uid]
            if 0 <= gidx < x_global.size:
                float_val: float = float(val)
                if np.isfinite(float_val):
                    x_global[gidx] = float_val
                    seeded_init_uids.add(uid)
                else:
                    pass
            else:
                pass
        else:
            pass

    # Some models, notably ZIP loads, keep a nominal voltage event anchor
    # initialized from an input voltage. If init equations are deliberately
    # empty, recover that anchor directly from the already seeded connected input.
    for blk in mdl_work.get_all_blocks():
        voltage_input_value: float | None = None
        for input_var in blk.in_vars:
            if isinstance(input_var, Var) and input_var.name == "Vm" and input_var.uid in uid2idx_vars:
                input_idx: int = uid2idx_vars[input_var.uid]
                if 0 <= input_idx < x_global.size:
                    candidate_value: float = float(x_global[input_idx])
                    if np.isfinite(candidate_value):
                        voltage_input_value = candidate_value
                    else:
                        pass
                else:
                    pass
            else:
                pass

        if voltage_input_value is None:
            pass
        else:
            for event_var, event_value in list(blk.event_dict.items()):
                if isinstance(event_var, Var) and event_var.name in ("V0", "Vm0"):
                    if isinstance(event_value, Const) and event_value.value is None:
                        blk.event_dict[event_var] = Const(float(voltage_input_value))
                    else:
                        pass
                else:
                    pass

    # Freeze PF anchors in this local model. Branch-like models freeze terminal
    # quantities only, while injection-like models freeze their bus injection.
    pf_var_references: list[VarPowerFlowReferenceType] = get_pseudo_transient_freeze_references(mdl=mdl_work)
    has_explicit_init_eqs: bool = any(
        len(blk.init_eqs) > 0 for blk in mdl_work.get_all_blocks()
    )
    fixed_pf_var_uids: set[int] = set()
    for pf_ref in pf_var_references:
        if pf_ref not in mdl_work.external_mapping:
            continue
        pf_var = mdl_work.external_mapping[pf_ref]
        if not isinstance(pf_var, Var):
            continue
        if pf_var.uid not in uid2idx_vars:
            continue
        if pf_var.uid in seeded_init_uids:
            pf_val = x_global[uid2idx_vars[pf_var.uid]]
            aligned_event_anchors: list[Var] = align_event_anchor_for_frozen_pf_reference(
                mdl=mdl_work,
                pf_var=pf_var,
                pf_val=float(pf_val),
                pf_ref=pf_ref,
            )
            for aligned_var in aligned_event_anchors:
                if aligned_var.uid in uid2idx_event_params:
                    ep_idx: int = uid2idx_event_params[aligned_var.uid]
                    if 0 <= ep_idx < len(event_parameters_eqs):
                        event_parameters_eqs[ep_idx] = Const(float(pf_val))
                    else:
                        pass
                else:
                    pass

            if (
                has_explicit_init_eqs
                and pf_ref in (VarPowerFlowReferenceType.P, VarPowerFlowReferenceType.Q)
            ):
                # Generator/load power remains part of the square physical
                # residual, but pseudo-transient must not move the solved power
                # flow operating point. The solver applies a fixed-variable mask.
                fixed_pf_var_uids.add(pf_var.uid)
                continue

            for blk in mdl_work.get_all_blocks():
                remove_alg_idx = [i for i, v in enumerate(blk.algebraic_vars)
                                  if isinstance(v, Var) and v.uid == pf_var.uid]
                for i in reversed(remove_alg_idx):
                    del blk.algebraic_vars[i]

                blk.state_vars = [v for v in blk.state_vars if isinstance(v, Var) and v.uid != pf_var.uid]
                blk.diff_vars = [
                    v for v in blk.diff_vars
                    if isinstance(v, Var)
                    and v.uid != pf_var.uid
                    and not (isinstance(v.base_var, Var) and v.base_var.uid == pf_var.uid)
                ]

            mdl_work.update_model(pf_var, Const(pf_val))
        else:
            if verbose:
                print(
                    "[PseudoTransientInit] leaving PF anchor unfrozen because it has no finite seed: "
                    f"{pf_ref} -> {pf_var.name} (uid={pf_var.uid})"
                )
            else:
                pass

    # Static mapping may have resolved a parameter only in the global runtime
    # channel. Bind that existing value in the initialization-only copy before
    # promoting unresolved references; source declarations remain untouched.
    parameter_block: Block
    parameter_var: Var
    parameter_expression: Expr | Const
    for parameter_block in mdl_work.get_all_blocks():
        for parameter_var, parameter_expression in parameter_block.event_dict.items():
            if isinstance(parameter_expression, Const) and parameter_expression.value is None:
                parameter_index: int | None = uid2idx_event_params.get(parameter_var.uid, None)
                if parameter_index is not None:
                    runtime_expression: Expr | Const = event_parameters_eqs[parameter_index]
                    if isinstance(runtime_expression, Const) and runtime_expression.value is not None:
                        runtime_value: float = float(runtime_expression.value)
                        if np.isfinite(runtime_value):
                            parameter_block.event_dict[parameter_var] = Const(runtime_value)
                        else:
                            pass
                    else:
                        pass
                else:
                    pass
            else:
                pass

    ordered_init_update_eqs: Dict[Var, Expr | Const] = dict()
    locked_event_parameter_uids: set[int] = set()
    for blk in mdl_work.get_all_blocks():
        for event_var, event_value in blk.event_dict.items():
            if isinstance(event_var, Var) and isinstance(event_value, Const) and event_value.value is not None:
                locked_event_parameter_uids.add(event_var.uid)
            else:
                pass

    # Symbolic event expressions become local algebraic initialization
    # constraints ``event_parameter - expression = 0``. Adding both the
    # variable and its residual preserves a square pseudo-transient system.
    # Const(None) remains the legacy/external seeding form and keeps the former
    # inferred-reference update path because it has no owned expression.
    equilibrium_reference_update_eqs: Dict[Var, Expr] = dict()
    for blk in mdl_work.get_all_blocks():
        initializable_event_parameters: List[tuple[Var, Expr | Const]] = [
            (var, value)
            for var, value in blk.event_dict.items()
            if isinstance(var, Var) and (not isinstance(value, Const) or value.value is None)
        ]
        for var, event_expression in initializable_event_parameters:
            event_idx: int | None = uid2idx_event_params.get(var.uid, None)
            seeded_event_expression: Expr | Const | None = (
                event_parameters_eqs[event_idx]
                if event_idx is not None and 0 <= event_idx < len(event_parameters_eqs)
                else None
            )
            if (
                isinstance(seeded_event_expression, Const)
                and seeded_event_expression.value is not None
            ):
                blk.event_dict[var] = Const(float(seeded_event_expression.value))
                continue
            elif isinstance(event_expression, Const):
                update_expr: Expr | None = _find_equilibrium_reference_update_eq(
                    mdl=mdl_work,
                    ref_var=var,
                )
                if isinstance(update_expr, Expr) and not isinstance(update_expr, Const):
                    equilibrium_reference_update_eqs[var] = update_expr
                else:
                    pass
            else:
                initialization_expression: Expr = event_expression
                blk.algebraic_eqs.append((var - initialization_expression).simplify())

            event_is_algebraic: bool = any(
                algebraic_var.uid == var.uid
                for algebraic_var in blk.algebraic_vars
            )
            if event_is_algebraic:
                pass
            else:
                blk.algebraic_vars.append(var)
            del blk.event_dict[var]
    
    # Create problem for this device
    problem = PseudoTransientInitProblem(
        block=mdl_work,
        x_global=x_global,
        compiler_names_dict=compiler_names_dict,
        alias_names_dict=alias_names_dict,
        uid2idx_vars=uid2idx_vars,
        variable_parameters=variable_parameters,
        constant_parameters=constant_parameters,
        equilibrium_reference_update_eqs=equilibrium_reference_update_eqs,
        ordered_init_update_eqs=ordered_init_update_eqs,
        pseudo_transient_options=pseudo_transient_options,
        VARS_NAME=VARS_NAME,
        DIFF_NAME=DIFF_NAME,
        VARIABLE_PARAMS_NAME=VARIABLE_PARAMS_NAME,
        CONSTANT_PARAMS_NAME=CONSTANT_PARAMS_NAME
    )
    # Attach global index maps for richer diagnostics in the pseudo-transient solver.
    problem._uid2idx_params = uid2idx_params
    problem._uid2idx_event_params = uid2idx_event_params

    local_vars = list(problem._state_vars) + list(problem._algebraic_vars)
    if problem.get_all_vars_number() == 0:
        return dict(init_guess)

    # Use the existing PseudoTransient solver
    # Note: h parameter is not used for initialization, we set it to 1.0

    solver = PseudoTransient(
        problem=problem,
        h=1.0,
        dtau0=1e3,
        dtau_max=1e5,
        dtau_min=1e-5,
        tol=tol,
        max_iter=1000,
        verbose=verbose,
        reference_error_tol=-1,
        fixed_var_uids=list(fixed_pf_var_uids),
        options=pseudo_transient_options,
    )

    # Start rotor angles close to the network reference for pseudo-transient.
    # This is only a seed; delta remains a solved state afterwards.
    delta_seed = pseudo_transient_options.delta_seed

    delta_indices: np.ndarray = np.array([
        index for index, variable in enumerate(local_vars)
        if isinstance(variable, Var) and variable.name.lower().startswith("delta")
    ], dtype=int)

    # Reuse caller-owned values by UID, not global array position: promoted
    # references can occupy local slots outside the global system mapping.
    initial_seed: Vec = np.zeros(problem.get_all_vars_number(), dtype=float)
    seed_index: int
    seed_variable: Var
    for seed_index, seed_variable in enumerate(local_vars):
        seed_value: float | None = init_guess.get(seed_variable.uid, None)
        if seed_value is not None and np.isfinite(seed_value):
            initial_seed[seed_index] = float(seed_value)
        else:
            # Structural zero is a trial coordinate, never persisted as a
            # supplied physical datum; the solver must still determine it.
            pass

    fixed_local_indices: np.ndarray = np.array([
        index for index, variable in enumerate(local_vars)
        if variable.uid in fixed_pf_var_uids
    ], dtype=int)

    # The caller owns required accuracy; an undocumented floor can accept
    # recovered states that the assembled network cannot keep fixed consistently.
    residual_tol: float = float(tol)
    max_attempts: int = 50
    best_x_solution: Vec | None = None
    best_residual_inf: float = np.inf
    best_residual_pre_inf: float = np.inf
    best_residual_post_inf: float = np.inf
    last_error_message: str = ""
    x_solution: Vec | None = None

    for attempt_idx in range(max_attempts):
        if attempt_idx == 0:
            x0: Vec = initial_seed.copy()
        else:
            # A rejected supplied point retains the existing random backup,
            # without adding a fifty-first attempt or reseeding the generator.
            x0 = np.random.rand(problem.get_all_vars_number())
        if delta_seed is not None:
            x0[delta_indices] = delta_seed
        else:
            pass
        x0[fixed_local_indices] = initial_seed[fixed_local_indices]

        if verbose and max_attempts > 1:
            print(f"[PseudoTransientInit] initialization attempt {attempt_idx + 1}/{max_attempts}")
        else:
            pass

        try:
            # A finite seed can lie outside a reference expression's domain.
            # Preparation must share the existing retry guard with the solver.
            problem.update_equilibrium_parameters(x0)
            x_attempt, _ = solver.simulate(plot=bool(verbose), x0=x0)
        except Exception as exc:
            last_error_message = str(exc)
            if verbose:
                print(f"[PseudoTransientInit] attempt {attempt_idx + 1} failed during preparation or simulation: {exc}")
            else:
                pass
            continue

        dx_pre = np.zeros(problem.get_diff_var_number(), dtype=float)
        rhs_pre = np.r_[problem.rhs_state(x_attempt, dx_pre), problem.rhs_algebraic(x_attempt, dx_pre)]
        residual_pre_inf = float(np.linalg.norm(rhs_pre, np.inf)) if rhs_pre.size > 0 else 0.0
        if verbose:
            print(f"[PseudoTransientInit] residual_inf after pseudo={residual_pre_inf:.6e}")
        else:
            pass

        # Newton-Raphson polish on f(x)=0 using pseudo-transient output as seed.
        # Here f(x) is the stacked explicit RHS [f_state(x), g_algebraic(x)] with dx=0.
        dx_newton = np.zeros(problem.get_diff_var_number(), dtype=float)
        x_nr = np.array(x_attempt, dtype=float, copy=True)

        newton_max_iter = 25
        # Polish to the requested local accuracy before recovered states become
        # fixed seeds for the existing assembled consistency owner.
        newton_tol: float = float(tol)
        for it in range(newton_max_iter):
            if dx_newton.size > 0:
                dx_newton = np.array(problem.get_dx(x_nr, x_nr, dx_newton, h=1.0), dtype=float, copy=True)
            else:
                pass
            rhs_nr = np.r_[problem.rhs_state(x_nr, dx_newton), problem.rhs_algebraic(x_nr, dx_newton)]
            if rhs_nr.size == 0:
                break
            else:
                pass
            if not np.all(np.isfinite(rhs_nr)):
                break
            else:
                pass

            rhs_inf = float(np.linalg.norm(rhs_nr, np.inf))
            if verbose:
                print(f"[PseudoTransientInit][Newton] iter={it} rhs_inf={rhs_inf:.6e}")
            else:
                pass
            if rhs_inf <= newton_tol:
                break
            else:
                pass

            J_nr = problem._compute_numerical_jacobian(x_nr, dx_newton, h=1.0)
            use_lsqr = False
            try:
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always", MatrixRankWarning)
                    delta = sp.linalg.spsolve(J_nr, rhs_nr)
                    if any(issubclass(wi.category, MatrixRankWarning) for wi in w):
                        use_lsqr = True
                    else:
                        pass
            except Exception:
                use_lsqr = True

            if (not use_lsqr) and (
                delta is None
                or np.size(delta) == 0
                or (not np.all(np.isfinite(delta)))
                or (float(np.linalg.norm(np.asarray(delta, dtype=float), np.inf)) == 0.0)
            ):
                use_lsqr = True
            else:
                pass

            if use_lsqr:
                lsqr_out = sp.linalg.lsqr(
                    J_nr,
                    rhs_nr,
                    atol=1e-12,
                    btol=1e-12,
                    iter_lim=4 * max(1, x_nr.size),
                )
                delta = lsqr_out[0]
                if verbose:
                    print(
                        "[PseudoTransientInit][Newton] spsolve fallback to lsqr: "
                        f"istop={lsqr_out[1]} itn={lsqr_out[2]} r1norm={lsqr_out[3]:.6e}"
                    )
                else:
                    pass
            else:
                pass

            if delta is None or np.size(delta) == 0 or not np.all(np.isfinite(delta)):
                break
            else:
                pass

            alpha = 1.0
            accepted = False
            base_inf = rhs_inf
            for _ in range(8):
                x_try = x_nr - alpha * np.asarray(delta, dtype=float)
                x_try[fixed_local_indices] = initial_seed[fixed_local_indices]

                dx_try = dx_newton
                if dx_newton.size > 0:
                    dx_try = np.array(problem.get_dx(x_try, x_try, dx_newton, h=1.0), dtype=float, copy=True)
                else:
                    pass

                rhs_try = np.r_[problem.rhs_state(x_try, dx_try), problem.rhs_algebraic(x_try, dx_try)]
                if np.all(np.isfinite(rhs_try)):
                    trial_inf = float(np.linalg.norm(rhs_try, np.inf))
                    if trial_inf < base_inf:
                        x_nr = x_try
                        accepted = True
                        break
                    else:
                        pass
                else:
                    pass
                alpha *= 0.5

            if not accepted:
                break
            else:
                pass

        x_attempt = x_nr

        dx_post = np.zeros(problem.get_diff_var_number(), dtype=float)
        rhs_post = np.r_[problem.rhs_state(x_attempt, dx_post), problem.rhs_algebraic(x_attempt, dx_post)]
        residual_post_inf = float(np.linalg.norm(rhs_post, np.inf)) if rhs_post.size > 0 else 0.0
        if verbose:
            print(
                "[PseudoTransientInit] residual_inf after Newton="
                f"{residual_post_inf:.6e} (pre={residual_pre_inf:.6e})"
            )
        else:
            pass

        dx_check = np.zeros(problem.get_diff_var_number(), dtype=float)
        rhs_state = problem.rhs_state(x_attempt, dx_check)
        rhs_algeb = problem.rhs_algebraic(x_attempt, dx_check)
        residual_vec = np.r_[rhs_state, rhs_algeb]

        if not np.all(np.isfinite(residual_vec)):
            bad_idx = np.where(~np.isfinite(residual_vec))[0]
            bad_vals = residual_vec[bad_idx]
            last_error_message = (
                f"PseudoTransient final residual has NaN/Inf: bad_idx={bad_idx.tolist()}, "
                f"bad_vals={bad_vals.tolist()}"
            )
            if verbose:
                print(f"[PseudoTransientInit] attempt {attempt_idx + 1} rejected: {last_error_message}")
            else:
                pass
            continue
        else:
            pass

        residual_inf = float(np.linalg.norm(residual_vec, np.inf)) if residual_vec.size > 0 else 0.0
        if residual_inf < best_residual_inf:
            best_residual_inf = residual_inf
            best_residual_pre_inf = residual_pre_inf
            best_residual_post_inf = residual_post_inf
            best_x_solution = np.array(x_attempt, dtype=float, copy=True)
        else:
            pass

        if residual_inf <= residual_tol:
            x_solution = x_attempt
            break
        else:
            last_error_message = (
                f"PseudoTransient final residual too large: "
                f"||r||_inf={residual_inf:.6e} > {residual_tol:.6e}; "
                f"pre_newton={residual_pre_inf:.6e}, post_newton={residual_post_inf:.6e}"
            )
            if verbose:
                print(f"[PseudoTransientInit] random attempt {attempt_idx + 1} rejected: {last_error_message}")
            else:
                pass

    if x_solution is None:
        if best_x_solution is not None and bool(pseudo_transient_options.allow_best_effort_init):
            x_solution = best_x_solution
            print(
                "[PseudoTransientInit] WARNING: returning best-effort init despite residual guard: "
                f"best ||r||_inf={best_residual_inf:.6e} > {residual_tol:.6e}"
            )
        else:
            raise RuntimeError(
                f"PseudoTransient failed after {max_attempts} initialization attempts; "
                f"best ||r||_inf={best_residual_inf:.6e} > {residual_tol:.6e}; "
                f"best_pre_newton={best_residual_pre_inf:.6e}, "
                f"best_post_newton={best_residual_post_inf:.6e}; "
                f"last_error={last_error_message}"
            )
    else:
        pass

    # Update recovered values:
    # - system variables go to init_guess
    # - promoted runtime parameters go back to event_parameters_eqs as Const
    problem.update_equilibrium_parameters(x_solution)
    for local_idx, var in enumerate(local_vars):
        if local_idx >= len(x_solution):
            continue

        value = float(x_solution[local_idx])

        if var.uid in uid2idx_vars:
            init_guess[var.uid] = value
        elif var.uid in uid2idx_event_params:
            if var.uid in locked_event_parameter_uids:
                pass
            else:
                ep_idx = uid2idx_event_params[var.uid]
                if 0 <= ep_idx < len(event_parameters_eqs):
                    event_parameters_eqs[ep_idx] = Const(value)

    for pidx in problem._equilibrium_input_param_indices:
        if pidx < 0 or pidx >= len(problem._variable_parameters):
            continue
        else:
            pass
        if pidx >= len(problem._variable_parameters_values):
            continue
        else:
            pass
        var = problem._variable_parameters[pidx]
        value = float(problem._variable_parameters_values[pidx])
        if var.uid in uid2idx_event_params:
            ep_idx = uid2idx_event_params[var.uid]
            if 0 <= ep_idx < len(event_parameters_eqs):
                event_parameters_eqs[ep_idx] = Const(value)
            else:
                pass
        else:
            pass

    uid_bindings: dict[int, float] = {
        uid: float(value) for uid, value in init_guess.items() if value is not None
    }
    for var in variable_parameters:
        if not isinstance(var, Var) or var.uid not in uid2idx_event_params:
            continue
        ep_idx = uid2idx_event_params[var.uid]
        if 0 <= ep_idx < len(event_parameters_eqs):
            eq = event_parameters_eqs[ep_idx]
            if isinstance(eq, Const) and eq.value is not None:
                uid_bindings[var.uid] = float(eq.value)

    for ep_idx, eq in enumerate(list(event_parameters_eqs)):
        if not isinstance(eq, Expr) or isinstance(eq, Const):
            continue
        expr_vars = get_expression_vars(eq)
        if not any(isinstance(v, Var) and v.uid in uid2idx_vars for v in expr_vars):
            continue
        if not all(isinstance(v, Var) and v.uid in uid_bindings for v in expr_vars):
            continue
        try:
            value = float(eval_expr_uid(eq, uid_bindings))
        except Exception:  # TODO: except what?
            continue
        if np.isfinite(value):
            event_parameters_eqs[ep_idx] = Const(value)

    return init_guess
