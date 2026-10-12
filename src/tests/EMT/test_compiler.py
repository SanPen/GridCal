# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

# ==============================================================================
# Module: Structural Compiler Verification Suite
# ==============================================================================

from typing import List, Callable

import numpy as np
import numba as nb
import pytest

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Func
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler, MatrixVectorizedCompiler, EagerEquationCompiler
from VeraGridEngine.enumerations import DynamicIntegrationMethod


def _create_decay_equation() -> tuple[Var, Var, Expr]:
    """
    Create a canonical decay equation: dx/dt + x = 0.

    :returns: Tuple of (x, dx, decay_eq) representing the decay system.
    """
    x: Var = Var('x')
    dx: Var = Var(name='dx', base_var=x)
    decay_eq: Expr = dx + x
    return x, dx, decay_eq


def test_trapezoidal_residual_math() -> None:
    """
    Verifies the implicit Trapezoidal substitution for decay equation.

    Tests that the compiled residual correctly implements:
    dx_new = (2/h)*(x - x0) - dx0
    res = dx_new + x
    """
    x, dx, decay_eq = _create_decay_equation()

    compiler: EquationCompiler = EquationCompiler(
        list([x]),
        method=DynamicIntegrationMethod.DaeTrapezoidal
    )
    step_fn: Callable = compiler.compile(list([decay_eq]))

    h: float = 0.1
    h2: np.ndarray = np.zeros(1, dtype=np.float64)

    states: np.ndarray = np.array(list([1.0]), dtype=np.float64)
    params: np.ndarray = np.zeros(0, dtype=np.float64)
    history: np.ndarray = np.array(list([1.0]), dtype=np.float64)
    d_history: np.ndarray = np.array(list([-1.0]), dtype=np.float64)

    res: np.ndarray = step_fn(states, params, history, d_history, h, h2)

    assert abs(float(res[0]) - 2.0) < 1e-6, f"Expected 2.0, got {float(res[0])}"


def test_matrix_vectorized_clustering_logic() -> None:
    """
    Validates the MatrixVectorizedCompiler used in SVS Structural Clustering.

    Ensures a single template can be applied to multiple nodes simultaneously.
    """
    x, dx, decay_eq = _create_decay_equation()

    vec_compiler: MatrixVectorizedCompiler = MatrixVectorizedCompiler(
        list([x]),
        parameters=list(),
        method=DynamicIntegrationMethod.DaeTrapezoidal
    )
    py_func: Callable = vec_compiler.compile_matrix_kernel(
        decay_eq,
        func_name="vec_decay",
        template_vars=list([x])
    )
    vec_kernel: Callable = nb.njit(fastmath=True)(py_func)

    indices: np.ndarray = np.array(list([list([0]), list([1]), list([2])]), dtype=np.int32)
    states: np.ndarray = np.array(list([1.0, 1.2, 1.5]), dtype=np.float64)
    params: np.ndarray = np.zeros(0, dtype=np.float64)
    history: np.ndarray = np.array(list([1.0, 1.2, 1.5]), dtype=np.float64)
    d_hist: np.ndarray = np.array(list([-1.0, -1.2, -1.5]), dtype=np.float64)
    h: float = 0.1

    res: np.ndarray = vec_kernel(states, params, history, d_hist, h, indices, history)

    expected: np.ndarray = np.array(list([2.0, 2.4, 3.0]), dtype=np.float64)
    np.testing.assert_allclose(res, expected, rtol=1e-7)


def test_truncation_error_order() -> None:
    """
    Mathematical proof of O(h^2) convergence for the Trapezoidal JIT kernel.

    Residual error should drop by factor of 4 when h is halved.
    """
    x, dx, decay_eq = _create_decay_equation()

    compiler: EquationCompiler = EquationCompiler(
        list([x]),
        method=DynamicIntegrationMethod.DaeTrapezoidal
    )
    step_fn: Callable = compiler.compile(list([decay_eq]))

    x0: float = 1.0
    dx0: float = -1.0
    h2: np.ndarray = np.zeros(1, dtype=np.float64)
    h_c: float = 0.1
    h_f: float = 0.05
    params: np.ndarray = np.zeros(0, dtype=np.float64)

    states_c: np.ndarray = np.array(list([np.exp(-h_c)]), dtype=np.float64)
    hist_c: np.ndarray = np.array(list([x0]), dtype=np.float64)
    d_hist_c: np.ndarray = np.array(list([dx0]), dtype=np.float64)
    res_c: np.ndarray = step_fn(states_c, params, hist_c, d_hist_c, h_c, h2)

    states_f: np.ndarray = np.array(list([np.exp(-h_f)]), dtype=np.float64)
    hist_f: np.ndarray = np.array(list([x0]), dtype=np.float64)
    d_hist_f: np.ndarray = np.array(list([dx0]), dtype=np.float64)
    res_f: np.ndarray = step_fn(states_f, params, hist_f, d_hist_f, h_f, h2)

    ratio: float = float(abs(res_c[0]) / abs(res_f[0]))
    print(f"\n[MATH] Empirical Convergence Ratio: {ratio:.2f} (Expected ~4.0)")
    assert ratio > 3.8, f"Expected ratio > 3.8, got {ratio}"


def test_oscillator_energy_conservation() -> None:
    """
    Physical verification: Trapezoidal rule must conserve energy in a Hamiltonian system.

    System: x'' + x = 0 (Undamped Oscillator).
    """
    pos: Var = Var('pos')
    vel: Var = Var('vel')
    d_pos: Var = Var(name='d_pos', base_var=pos)
    d_vel: Var = Var(name='d_vel', base_var=vel)

    eqs: List[Expr] = list([d_pos - vel, d_vel + pos])
    compiler: EquationCompiler = EquationCompiler(
        list([pos, vel]),
        method=DynamicIntegrationMethod.DaeTrapezoidal
    )
    kernel: Callable = compiler.compile(eqs)

    h: float = 0.01
    h2: np.ndarray = np.zeros(2, dtype=np.float64)
    hist: np.ndarray = np.array(list([1.0, 0.0]), dtype=np.float64)
    d_hist: np.ndarray = np.array(list([0.0, -1.0]), dtype=np.float64)
    params: np.ndarray = np.zeros(0, dtype=np.float64)

    states_new: np.ndarray = np.array(list([np.cos(h), -np.sin(h)]), dtype=np.float64)
    res: np.ndarray = kernel(states_new, params, hist, d_hist, h, h2)

    np.testing.assert_allclose(res, np.zeros(2, dtype=np.float64), atol=1e-4)

    e_init: float = 0.5 * (1.0 ** 2 + 0.0 ** 2)
    e_final: float = 0.5 * (float(states_new[0]) ** 2 + float(states_new[1]) ** 2)
    assert abs(e_init - e_final) < 1e-5, f"Energy not conserved: {e_init} vs {e_final}"


@pytest.mark.parametrize("method", list([DynamicIntegrationMethod.DaeBackEuler,
                                       DynamicIntegrationMethod.DaeTrapezoidal,
                                       DynamicIntegrationMethod.DaeBDF2]))
@pytest.mark.parametrize("eager", list([False, True]))
@pytest.mark.parametrize("use_cse", list([False, True]))
@pytest.mark.parametrize("reverse", list([False, True]))
def test_codegen_cache_preserves_derivative_history_layout(
        method: DynamicIntegrationMethod, eager: bool, use_cse: bool, reverse: bool) -> None:
    """
    Verify scalar cache bindings against independent residual and JVP formulas.

    :param method: Existing first-order discretization to verify.
    :param eager: Whether to exercise the strict in-place compiler ABI.
    :param use_cse: Whether repeated nonlinear terms use common subexpressions.
    :param reverse: Whether to reverse cache priming, with a distinct expression.
    :return: None; assertions verify numerics, binding identity and valid reuse.
    """
    x: Var = Var('cache_x')
    y: Var = Var('cache_y')
    dx: Var = Var('cache_dx', base_var=x)
    dy: Var = Var('cache_dy', base_var=y)
    p: Var = Var('cache_p')
    q: Var = Var('cache_q')
    states: np.ndarray = np.array(list([0.2, 0.4]), dtype=np.float64)
    history: np.ndarray = np.array(list([0.1, 0.3]), dtype=np.float64)
    d_history: np.ndarray = np.array(list([3.0, 7.0]), dtype=np.float64)
    history2: np.ndarray = np.array(list([-0.05, 0.15]), dtype=np.float64)
    params: np.ndarray = np.array(list([0.13, 0.29]), dtype=np.float64)
    seeds: np.ndarray = np.array(list([0.7, -0.4]), dtype=np.float64)
    h: float = 0.1
    epsilon: float = 1e-6
    offset: float = 0.123 if reverse else 0.124
    alpha: float
    derivative_values: np.ndarray
    if method == DynamicIntegrationMethod.DaeBackEuler:
        alpha = 1.0 / h
        derivative_values = (states - history) / h
    elif method == DynamicIntegrationMethod.DaeTrapezoidal:
        alpha = 2.0 / h
        derivative_values = alpha * (states - history)
    else:
        alpha = 1.5 / h
        derivative_values = (1.5 * states - 2.0 * history + 0.5 * history2) / h

    # Change used history, state and parameter slots independently. Distinct
    # offsets ensure both priming orders start cold even in one pytest process.
    contexts: list[tuple[bool, bool, bool]] = list([
        (False, False, False), (False, False, True),
        (True, False, False), (False, True, False)])
    context_order: range = range(3, -1, -1) if reverse else range(4)
    residual_functions: np.ndarray = np.empty((3, 4), dtype=object)
    ad_functions: np.ndarray = np.empty((3, 4), dtype=object)
    generation: int
    context_index: int
    compiler: EquationCompiler
    kernel: Callable
    ad_kernel: Callable
    repeated_kernel: Callable
    repeated_ad: Callable
    signature: object
    ad_signature: object
    for generation in range(3):
        owner_x: Var
        owner_y: Var
        owner_dx: Var
        owner_dy: Var
        owner_p: Var
        owner_q: Var
        expression_x: Var
        expression_dx: Var
        expression_p: Var
        if generation == 2:
            owner_x = Var('renamed_cache_x')
            owner_y = Var('renamed_cache_y')
            owner_dx = Var('renamed_cache_dx', base_var=owner_x)
            owner_dy = Var('renamed_cache_dy', base_var=owner_y)
            owner_p = Var('renamed_cache_p')
            owner_q = Var('renamed_cache_q')
        else:
            owner_x, owner_y, owner_dx, owner_dy, owner_p, owner_q = x, y, dx, dy, p, q
        if generation == 1:
            expression_x = Var('alias_cache_x', uid=x.uid)
            expression_dx = Var('alias_cache_dx', uid=dx.uid, base_var=expression_x)
            expression_p = Var('alias_cache_p', uid=p.uid)
        else:
            expression_x, expression_dx, expression_p = owner_x, owner_dx, owner_p
        shared: Expr = expression_dx * expression_x + expression_p + offset
        equations: list[Expr] = list([expression_dx * expression_x,
                                     -shared + shared * shared + Func(arg=shared, op='sin')])
        for context_index in context_order:
            swap_state: bool
            swap_parameter: bool
            swap_history: bool
            swap_state, swap_parameter, swap_history = contexts[context_index]
            variables: list[Var] = list([owner_y, owner_x]) if swap_state else list([owner_x, owner_y])
            parameters: list[Var] = list([owner_q, owner_p]) if swap_parameter else list([owner_p, owner_q])
            derivatives: list[Var] = list([owner_dy, owner_dx]) if swap_history else list([owner_dx, owner_dy])
            if eager:
                compiler = EagerEquationCompiler(variables, parameters, derivatives, method)
                kernel, signature = compiler.compile(equations, use_cse=use_cse)
                ad_kernel, ad_signature = compiler.compile_ad_kernel(equations, use_cse=use_cse)
            else:
                compiler = EquationCompiler(variables, parameters, derivatives, method)
                kernel = compiler.compile(equations, use_cse=use_cse)
                ad_kernel = compiler.compile_ad_kernel(equations, use_cse=use_cse)
            residual_functions[generation, context_index] = kernel
            ad_functions[generation, context_index] = ad_kernel
            state_index: int = 1 if swap_state else 0
            parameter_index: int = 1 if swap_parameter else 0
            history_index: int = 1 if swap_history else 0
            derivative: float = float(derivative_values[state_index])
            if method == DynamicIntegrationMethod.DaeTrapezoidal:
                derivative -= float(d_history[history_index])
            else:
                pass
            value: float = derivative * float(states[state_index])
            shared_value: float = value + float(params[parameter_index]) + offset
            expected: np.ndarray = np.array(list([value, -shared_value + shared_value * shared_value
                                                  + np.sin(shared_value)]))
            slope: float = (derivative + alpha * float(states[state_index])) * float(seeds[state_index])
            expected_jvp: np.ndarray = np.array(list([slope, (-1.0 + 2.0 * shared_value
                                                              + np.cos(shared_value)) * slope]))
            output: np.ndarray = np.zeros(2)
            jvp: np.ndarray = np.zeros(2)
            plus: np.ndarray = np.zeros(2)
            minus: np.ndarray = np.zeros(2)
            if isinstance(compiler, EagerEquationCompiler):
                kernel(states, params, history, d_history, h, output, history2)
                ad_kernel(states, seeds, params, history, d_history, h, jvp, history2)
                kernel(states + epsilon * seeds, params, history, d_history, h, plus, history2)
                kernel(states - epsilon * seeds, params, history, d_history, h, minus, history2)
                repeated_kernel, signature = compiler.compile(equations, use_cse=use_cse)
                repeated_ad, ad_signature = compiler.compile_ad_kernel(equations, use_cse=use_cse)
            else:
                output = kernel(states, params, history, d_history, h, history2)
                jvp = ad_kernel(states, seeds, params, history, d_history, h, history2)
                plus = kernel(states + epsilon * seeds, params, history, d_history, h, history2)
                minus = kernel(states - epsilon * seeds, params, history, d_history, h, history2)
                repeated_kernel = compiler.compile(equations, use_cse=use_cse)
                repeated_ad = compiler.compile_ad_kernel(equations, use_cse=use_cse)
            np.testing.assert_allclose(output, expected, rtol=1e-12, atol=1e-12)
            np.testing.assert_allclose(jvp, expected_jvp, rtol=1e-12, atol=1e-12)
            np.testing.assert_allclose(jvp, (plus - minus) / (2.0 * epsilon), rtol=1e-7, atol=1e-7)
            assert repeated_kernel is kernel and repeated_ad is ad_kernel
            # Renaming and same-UID aliases preserve identical used bindings.
            assert kernel is residual_functions[0, context_index]
            assert ad_kernel is ad_functions[0, context_index]

    assert residual_functions[0, 0] is not residual_functions[0, 2]
    assert residual_functions[0, 0] is not residual_functions[0, 3]
    assert ad_functions[0, 0] is not ad_functions[0, 2]
    assert ad_functions[0, 0] is not ad_functions[0, 3]
    if method == DynamicIntegrationMethod.DaeTrapezoidal:
        assert residual_functions[0, 0] is not residual_functions[0, 1]
        assert ad_functions[0, 0] is not ad_functions[0, 1]
    else:
        pass

    # A missing mapping uses the existing state-index fallback. The unused y
    # history mapping may disappear without changing x's generated expressions.
    shared = dx * x + p + offset
    equations = list([dx * x, -shared + shared * shared + Func(arg=shared, op='sin')])
    derivative_options: list[list[Var] | None] = list([None, list(), list([dx])])
    diff_vars: list[Var] | None
    for diff_vars in derivative_options:
        if eager:
            compiler = EagerEquationCompiler(list([x, y]), list([p, q]), diff_vars, method)
            repeated_kernel, signature = compiler.compile(equations, use_cse=use_cse)
            repeated_ad, ad_signature = compiler.compile_ad_kernel(equations, use_cse=use_cse)
        else:
            compiler = EquationCompiler(list([x, y]), list([p, q]), diff_vars, method)
            repeated_kernel = compiler.compile(equations, use_cse=use_cse)
            repeated_ad = compiler.compile_ad_kernel(equations, use_cse=use_cse)
        assert repeated_kernel is residual_functions[0, 0]
        assert repeated_ad is ad_functions[0, 0]

    # Nested residual visitors discretize dx directly even when dx is separately
    # mapped. Verify their existing formulas without adding nested AD support.
    if method != DynamicIntegrationMethod.DaeBDF2:
        d2x: Var = Var('cache_d2x', base_var=dx)
        nested_states: np.ndarray = np.array(list([0.2, 0.4, 0.9]))
        nested_history: np.ndarray = np.array(list([0.1, 0.3, 0.8]))
        nested_d_history: np.ndarray = np.array(list([3.0, 7.0, 5.0]))
        nested_functions: np.ndarray = np.empty((2, 2), dtype=object)
        mapping_index: int
        history_order: range = range(1, -1, -1) if reverse else range(2)
        nested_term: Expr = d2x * x + offset
        nested_equations: list[Expr] = list([nested_term, -nested_term + nested_term * nested_term])
        for mapping_index in range(2):
            variables = list([x, y, dx]) if mapping_index == 0 else list([x, y, q])
            parameters = list([p, q]) if mapping_index == 0 else list([p, dx])
            for history_index in history_order:
                derivatives = list([dx, dy]) if history_index == 0 else list([dy, dx])
                if eager:
                    compiler = EagerEquationCompiler(variables, parameters, derivatives, method)
                    kernel, signature = compiler.compile(nested_equations, use_cse=use_cse)
                    output = np.zeros(2)
                    kernel(nested_states, params, nested_history, nested_d_history, h, output, nested_history)
                else:
                    compiler = EquationCompiler(variables, parameters, derivatives, method)
                    kernel = compiler.compile(nested_equations, use_cse=use_cse)
                    output = kernel(nested_states, params, nested_history, nested_d_history, h, nested_history)
                first_derivative: float = (float(nested_states[0]) - float(nested_history[0])) / h
                if method == DynamicIntegrationMethod.DaeTrapezoidal:
                    first_derivative = 2.0 * first_derivative - float(nested_d_history[history_index])
                else:
                    pass
                nested_value: float = (first_derivative - float(nested_d_history[0])) / h * float(nested_states[0]) + offset
                expected = np.array(list([nested_value, -nested_value + nested_value * nested_value]))
                np.testing.assert_allclose(output, expected, rtol=1e-12, atol=1e-12)
                nested_functions[mapping_index, history_index] = kernel
                assert kernel is nested_functions[0, history_index]
        if method == DynamicIntegrationMethod.DaeTrapezoidal:
            assert nested_functions[0, 0] is not nested_functions[0, 1]
        else:
            pass
        # Reading dx as a top-level node must retain its mapped value rather
        # than inherit the direct-discretization context of nested recursion.
        mapped_equations: list[Expr] = list([dx * x])
        for mapping_index in range(2):
            variables = list([x, y, dx]) if mapping_index == 0 else list([x, y, q])
            parameters = list([p, q]) if mapping_index == 0 else list([p, dx])
            if eager:
                compiler = EagerEquationCompiler(variables, parameters, list([dy, dx]), method)
                kernel, signature = compiler.compile(mapped_equations, use_cse=use_cse)
                output = np.zeros(1)
                kernel(nested_states, params, nested_history, nested_d_history, h, output, nested_history)
            else:
                compiler = EquationCompiler(variables, parameters, list([dy, dx]), method)
                kernel = compiler.compile(mapped_equations, use_cse=use_cse)
                output = kernel(nested_states, params, nested_history, nested_d_history, h, nested_history)
            mapped_value: float = float(nested_states[2]) if mapping_index == 0 else float(params[1])
            np.testing.assert_allclose(output, np.array(list([mapped_value * float(nested_states[0])])),
                                       rtol=1e-12, atol=1e-12)
    else:
        pass


@pytest.mark.parametrize("method", list([DynamicIntegrationMethod.DaeBackEuler,
                                       DynamicIntegrationMethod.DaeTrapezoidal,
                                       DynamicIntegrationMethod.DaeBDF2]))
@pytest.mark.parametrize("eager", list([False, True]))
@pytest.mark.parametrize("use_cse", list([False, True]))
@pytest.mark.parametrize("reverse", list([False, True]))
def test_codegen_cache_distinguishes_dynamic_and_explicit_ad_seeds(
        method: DynamicIntegrationMethod, eager: bool, use_cse: bool, reverse: bool) -> None:
    """
    Verify dynamic, empty and selected AD seeds across warm cache construction.

    :param method: Existing integration method supplying the derivative formula.
    :param eager: Whether kernels use the strict in-place ABI.
    :param use_cse: Whether the shared nonlinear term is emitted through CSE.
    :param reverse: Whether the empty selection primes before dynamic seeds.
    :return: None; assertions check independent JVPs, finite differences and reuse.
    """
    x: Var = Var('seed_x')
    y: Var = Var('seed_y')
    dx: Var = Var('seed_dx', base_var=x)
    dy: Var = Var('seed_dy', base_var=y)
    states: np.ndarray = np.array(list([0.2, 0.4]))
    history: np.ndarray = np.array(list([0.1, 0.3]))
    d_history: np.ndarray = np.array(list([3.0, 7.0]))
    history2: np.ndarray = np.array(list([-0.05, 0.15]))
    params: np.ndarray = np.zeros(0)
    seeds: np.ndarray = np.array(list([0.7, -0.4]))
    h: float = 0.1
    epsilon: float = 1e-6
    offset: float = 0.223 if reverse else 0.224
    shared: Expr = dx * x + dy * y + offset
    equations: list[Expr] = list([shared, -shared + shared * shared + Func(arg=shared, op='sin')])
    compiler: EquationCompiler
    residual_kernel: Callable
    signature: object
    if eager:
        compiler = EagerEquationCompiler(list([x, y]), list(), list([dx, dy]), method)
        residual_kernel, signature = compiler.compile(equations, use_cse=use_cse)
    else:
        compiler = EquationCompiler(list([x, y]), list(), list([dx, dy]), method)
        residual_kernel = compiler.compile(equations, use_cse=use_cse)
    alpha: float
    derivative_values: np.ndarray
    if method == DynamicIntegrationMethod.DaeBackEuler:
        alpha = 1.0 / h
        derivative_values = (states - history) / h
    elif method == DynamicIntegrationMethod.DaeTrapezoidal:
        alpha = 2.0 / h
        derivative_values = alpha * (states - history) - d_history
    else:
        alpha = 1.5 / h
        derivative_values = (1.5 * states - 2.0 * history + 0.5 * history2) / h
    shared_value: float = float(np.dot(derivative_values, states)) + offset
    gradient: np.ndarray = derivative_values + alpha * states
    selections: list[set[int] | None] = list([None, set(), set([0]), set([1]), set([0, 1])])
    selection_order: range = range(4, -1, -1) if reverse else range(5)
    functions: np.ndarray = np.empty(5, dtype=object)
    selection_index: int
    selection: set[int] | None
    kernel: Callable
    repeated: Callable
    for selection_index in selection_order:
        selection = selections[selection_index]
        direction: np.ndarray = seeds.copy() if selection is None else np.zeros(2)
        if selection is None:
            pass
        else:
            active_index: int
            for active_index in selection:
                direction[active_index] = 1.0
        if isinstance(compiler, EagerEquationCompiler):
            kernel, signature = compiler.compile_ad_kernel(equations, use_cse=use_cse, active_indices=selection)
            repeated, signature = compiler.compile_ad_kernel(equations, use_cse=use_cse, active_indices=selection)
        else:
            kernel = compiler.compile_ad_kernel(equations, use_cse=use_cse, active_indices=selection)
            repeated = compiler.compile_ad_kernel(equations, use_cse=use_cse, active_indices=selection)
        assert kernel is repeated
        functions[selection_index] = kernel
        slope: float = float(np.dot(gradient, direction))
        expected: np.ndarray = np.array(list([slope, (-1.0 + 2.0 * shared_value + np.cos(shared_value)) * slope]))
        output: np.ndarray = np.zeros(2)
        plus: np.ndarray = np.zeros(2)
        minus: np.ndarray = np.zeros(2)
        if isinstance(compiler, EagerEquationCompiler):
            kernel(states, seeds, params, history, d_history, h, output, history2)
            residual_kernel(states + epsilon * direction, params, history, d_history, h, plus, history2)
            residual_kernel(states - epsilon * direction, params, history, d_history, h, minus, history2)
        else:
            output = kernel(states, seeds, params, history, d_history, h, history2)
            plus = residual_kernel(states + epsilon * direction, params, history, d_history, h, history2)
            minus = residual_kernel(states - epsilon * direction, params, history, d_history, h, history2)
        np.testing.assert_allclose(output, expected, rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(output, (plus - minus) / (2.0 * epsilon), rtol=1e-7, atol=1e-7)
        # A different runtime seed vector changes only dynamic JVPs; selected
        # indices continue to supply unit directions through the same kernel.
        alternate: np.ndarray = np.zeros(2)
        alternate_direction: np.ndarray = -seeds if selection is None else direction
        alternate_slope: float = float(np.dot(gradient, alternate_direction))
        alternate_expected: np.ndarray = np.array(list([alternate_slope,
            (-1.0 + 2.0 * shared_value + np.cos(shared_value)) * alternate_slope]))
        if isinstance(compiler, EagerEquationCompiler):
            kernel(states, -seeds, params, history, d_history, h, alternate, history2)
        else:
            alternate = kernel(states, -seeds, params, history, d_history, h, history2)
        np.testing.assert_allclose(alternate, alternate_expected, rtol=1e-12, atol=1e-12)
    assert functions[0] is not functions[1]
    if isinstance(compiler, EagerEquationCompiler):
        repeated, signature = compiler.compile_ad_kernel(equations, use_cse=use_cse, active_indices=set([1, 0]))
    else:
        repeated = compiler.compile_ad_kernel(equations, use_cse=use_cse, active_indices=set([1, 0]))
    assert repeated is functions[4]


# if __name__ == "__main__":
#     import pytest
#     pytest.main([__file__, "-v"])
