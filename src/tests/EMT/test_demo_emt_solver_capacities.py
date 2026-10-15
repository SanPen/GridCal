# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# ==============================================================================
# GENERALIZED EMT BERGERON LINE MODEL & STANDALONE DEMO
# ==============================================================================
import time
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import os

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple

from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.explicit_initialization_symbolic import (
    ExplicitInitializationResult,
    SymbolicVectorSingleEquationCompiler,
    build_symbolic_vector_single_equation_compiler,
    init_explicit_common,
)
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.enumerations import EmtSolverTypes
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver

class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = []

    def __init__(self,
                 sys_block: Block,
                 glob_time: Var):

        static_parameter_values_mapping: Dict[Var, Const] = dict(sys_block.parameters)

        super().__init__(
            sys_block=sys_block,
            glob_time=glob_time,
            static_parameter_values_mapping=static_parameter_values_mapping,
        )

        self._run_explicit_initialization()

    def _run_explicit_initialization(self) -> None:
        """
        Run the common explicit initializer used by production EMT problems.

        :return: None.
        :rtype: None
        """
        # Adapt the generic test problem to the exact common initialization
        # engine called by ``EmtProblemDae``.
        sys_vars: Dict[int, Var] = {v.uid: v for v in (self._state_vars + self._algebraic_vars)}
        sys_diff_vars: Dict[int, Var] = {dv.uid: dv for dv in self._diff_vars}
        compile_single_equation: SymbolicVectorSingleEquationCompiler = (
            build_symbolic_vector_single_equation_compiler(
                compiler_names_dict=self.get_compiler_names_dict(),
                alias_names_dict=self.get_alias_names_dict(),
                vars_name=self.VARS_NAME,
                diff_name=self.DIFF_NAME,
                event_params_name=self.VARIABLE_PARAMS_NAME,
                params_name=self.CONSTANT_PARAMS_NAME,
            )
        )
        result: ExplicitInitializationResult = init_explicit_common(
            mdl=self.sys_block,
            sys_vars=sys_vars,
            sys_diff_vars=sys_diff_vars,
            variable_parameters=self.get_variable_parameters(),
            event_parameters_eqs=self.event_parameters_eqs,
            constant_parameters=self.get_constant_parameters(),
            init_guess=self.init_guess,
            event_param_init_dict=self.event_params_init_dict,
            diff_init_guess=self.diff_init_guess,
            uid2idx_vars=self.uid2idx_vars,
            uid2idx_diff=self.uid2idx_diff,
            uid2idx_params=self.uid2idx_params,
            uid2idx_event_params=self.uid2idx_event_params,
            params_array=self.get_parameters_values(),
            compile_single_equation=compile_single_equation,
            event_params_array_seed=self.event_params_values,
        )

        if result.converged:
            self.rebuild_runtime_param_vectors()
        else:
            raise RuntimeError(result.message)

    def get_init_guess_table(self,
                             include_all_vars: bool = True,
                             only_in_init_guess: bool = False,
                             tol_zero: float = 1e-12) -> pd.DataFrame:
        """
        Return a table with uid, alias/name and initial value for each variable.

        include_all_vars:
            - True: include all state+algebraic vars, even if not in init_guess (value=0).
            - False: include only uids present in init_guess (or only_in_init_guess=True).

        only_in_init_guess:
            - True: filter to only those explicitly initialized (uid in init_guess).
            - False: keep everything (depending on include_all_vars).

        tol_zero:
            threshold to flag values close to zero.
        """
        # Build x0 and dx0 from current guesses
        x0 = self.get_x0()
        dx0 = self.get_dx0()

        uid2idx_vars = self.uid2idx_vars
        uid2idx_diff = self.uid2idx_diff

        # Define the sets we want to process: (Variables, Guess_Source, Index_Map, Vector, Label)
        data_sets = [
            (list(self.get_state_vars()) + list(self.get_algebraic_vars()), self.init_guess, uid2idx_vars, x0, "Var"),
            (list(self.get_diff_vars()), self.diff_init_guess, uid2idx_diff, dx0, "DiffVar")
        ]

        rows = []
        for vars_list, guess_dict, idx_map, vector, var_type in data_sets:
            for v in vars_list:
                uid = v.uid
                idx = idx_map.get(uid, None)
                val = float(vector[idx]) if idx is not None else 0.0

                in_guess = uid in guess_dict

                keep_row = True
                if only_in_init_guess and (not in_guess):
                    keep_row = False
                if (not include_all_vars) and (not in_guess):
                    keep_row = False

                if keep_row:
                    alias = self._alias_names_dict.get(uid, None)

                    rows.append({
                        "uid": uid,
                        "type": var_type,
                        "idx": idx,  # add this
                        "alias": alias,
                        "name": v.name,
                        "value": val,
                        "in_init_guess": in_guess,
                        "is_zero": abs(val) <= tol_zero,
                    })
                else:
                    pass

        df = pd.DataFrame(rows)

        # Nice ordering: Group by type, then initialization status
        if not df.empty:
            df = df.sort_values(["type", "idx"], ascending=[False, True])

        return df

# -----------------------------------------------------------------------------
# Bergeron line test helpers
# -----------------------------------------------------------------------------

class BoundaryUpdateWrapper(ABC):
    __slots__ = []

    @abstractmethod
    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        pass


class BergeronBoundaryUpdater(BoundaryUpdateWrapper):
    __slots__ = ['line', 'step_counter']

    def __init__(self, line: 'BergeronLineModel'):
        self.line = line
        self.step_counter: int = 0

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        self.line.update_history(self.step_counter, x, params)
        self.step_counter += 1


# ==============================================================================
# 1. GENERALIZED BERGERON MODEL (For emt_line.py)
# ==============================================================================
class BergeronLineModel:
    """
    Generalized N-phase implicit Bergeron Line Model.
    Designed to be instantiated in EmtProblemDae and solved via JitAdSolver.
    """
    __slots__ = [
        'name', 'Gc', 'H', 'num_phases', 'n_delay', 'buf_vf', 'buf_vt',
        'buf_if', 'buf_it', 'Ih_f', 'Ih_t', 'block', 'v_f_vars', 'v_t_vars',
        'idx_vf', 'idx_vt', 'idx_hf', 'idx_ht'
    ]

    def __init__(self, name: str, Gc: np.ndarray, H: np.ndarray, tau: float, h: float):
        self.idx_ht = None
        self.idx_vf = None
        self.idx_hf = None
        self.idx_vt = None
        self.v_t_vars = None
        self.v_f_vars = None
        self.name: str = name
        self.Gc: np.ndarray = np.asarray(Gc, dtype=np.float64)
        self.H: np.ndarray = np.asarray(H, dtype=np.float64)
        self.num_phases: int = self.Gc.shape[0]
        self.n_delay: int = max(1, int(round(tau / h)))

        # Circular buffers for history tracking
        self.buf_vf: np.ndarray = np.zeros((self.n_delay + 1, self.num_phases), dtype=np.float64)
        self.buf_vt: np.ndarray = np.zeros((self.n_delay + 1, self.num_phases), dtype=np.float64)
        self.buf_if: np.ndarray = np.zeros((self.n_delay + 1, self.num_phases), dtype=np.float64)
        self.buf_it: np.ndarray = np.zeros((self.n_delay + 1, self.num_phases), dtype=np.float64)

        self.Ih_f: List[Var] = list()
        self.Ih_t: List[Var] = list()
        for i in range(self.num_phases):
            self.Ih_f.append(Var(f"Ih_f_{name}_ph{i}"))
            self.Ih_t.append(Var(f"Ih_t_{name}_ph{i}"))

        # DAE Block: Map event parameters to initial Const(0.0)
        event_dict: Dict[Var, Expr] = dict()
        for var in self.Ih_f + self.Ih_t:
            event_dict[var] = Const(0.0)

        self.block: Block = Block(
            name=f"Bergeron_{name}",
            event_dict=event_dict
        )

    def get_nodal_injections(self, v_f_vars: List[Var], v_t_vars: List[Var]) -> Tuple[List[Expr], List[Expr]]:
        """
        Returns symbolic KCL current injections for the From and To buses.
        """
        self.v_f_vars = v_f_vars
        self.v_t_vars = v_t_vars

        i_f_exprs: List[Expr] = list()
        i_t_exprs: List[Expr] = list()

        for i in range(self.num_phases):
            i_f = sum(self.Gc[i, j] * self.v_f_vars[j] for j in range(self.num_phases)) + self.Ih_f[i]
            i_t = sum(self.Gc[i, j] * self.v_t_vars[j] for j in range(self.num_phases)) + self.Ih_t[i]

            i_f_exprs.append(i_f)
            i_t_exprs.append(i_t)

        return i_f_exprs, i_t_exprs

    def setup_indices(self, problem: GenericEmtProblem, vprms_offset: int = 0) -> None:
        """Maps symbolic UIDs to numerical array indices for the solver."""

        self.idx_vf = np.array([problem.uid2idx_vars[v.uid] for v in self.v_f_vars], dtype=np.int32)
        self.idx_vt = np.array([problem.uid2idx_vars[v.uid] for v in self.v_t_vars], dtype=np.int32)
        self.idx_hf = np.array([problem.uid2idx_event_params[p.uid] + vprms_offset for p in self.Ih_f], dtype=np.int32)
        self.idx_ht = np.array([problem.uid2idx_event_params[p.uid] + vprms_offset for p in self.Ih_t], dtype=np.int32)

    def update_history(self, step_counter: int, x_prev: np.ndarray, full_params: np.ndarray) -> None:
        """Evaluates history equations right before the Newton iteration."""
        k_curr: int = step_counter % (self.n_delay + 1)
        k_delay: int = (step_counter - self.n_delay) % (self.n_delay + 1)

        # 1. Read converged voltages from t_{n-1} using advanced indexing
        v_f_now = x_prev[self.idx_vf]
        v_t_now = x_prev[self.idx_vt]

        self.buf_vf[k_curr, :] = v_f_now
        self.buf_vt[k_curr, :] = v_t_now

        hf_vals = full_params[self.idx_hf]
        ht_vals = full_params[self.idx_ht]

        i_f_now = self.Gc @ v_f_now + hf_vals
        i_t_now = self.Gc @ v_t_now + ht_vals

        self.buf_if[k_curr, :] = i_f_now
        self.buf_it[k_curr, :] = i_t_now

        # 3. Retrieve delayed state (t_{n-1} - tau)
        v_f_tau = self.buf_vf[k_delay, :]
        v_t_tau = self.buf_vt[k_delay, :]
        i_f_tau = self.buf_if[k_delay, :]
        i_t_tau = self.buf_it[k_delay, :]

        # 4. Bergeron matrix math (Incident and reflected waves)
        X_f = -self.Gc @ v_t_tau - i_t_tau
        Y_f = -self.Gc @ v_f_tau - i_f_tau
        X_t = -self.Gc @ v_f_tau - i_f_tau
        Y_t = -self.Gc @ v_t_tau - i_t_tau

        I_mat = np.eye(self.num_phases)
        I_hist_f = 0.5 * ((I_mat + self.H) @ X_f + (I_mat - self.H) @ Y_f)
        I_hist_t = 0.5 * ((I_mat + self.H) @ X_t + (I_mat - self.H) @ Y_t)

        full_params[self.idx_hf] = I_hist_f
        full_params[self.idx_ht] = I_hist_t


# ==============================================================================
# 2. STANDALONE DEMO (Validation test)
# ==============================================================================
def create_test_system_bergeron(R_load: float) -> Tuple[Block, BergeronLineModel, float, float, Var, Var]:
    """
    Creates a test grid: Ideal Voltage Source (Step) -> Line -> Resistive Load
    """
    Zc: float = 350.0
    tau: float = 0.005
    h: float = 1e-4
    V_step: float = 100.0

    Gc_mat: np.ndarray = np.array([[1.0 / Zc]])
    H_mat: np.ndarray = np.array([[1.0]])

    line = BergeronLineModel("L1", Gc=Gc_mat, H=H_mat, tau=tau, h=h)

    v_f = Var("v_f")
    v_t = Var("v_t")

    i_f_exprs, i_t_exprs = line.get_nodal_injections([v_f], [v_t])
    i_t_line = i_t_exprs[0]

    kcl_f = v_f - V_step

    if R_load > 1e6:
        kcl_t = i_t_line
    else:
        kcl_t = i_t_line + (v_t / R_load)

    sys_block = Block(
        name="TestGrid",
        algebraic_vars=[v_f, v_t],
        algebraic_eqs=[kcl_f, kcl_t]
    )
    sys_block.add(line.block)

    return sys_block, line, h, tau, v_f, v_t


def run_test_bergeron(case_name: str, R_load: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Executes a single test case using JitAdSolver."""
    print(f"\n--- Running Test: {case_name} (R_load = {R_load} ohm) ---")

    sys_block, line, h, tau, v_f_var, v_t_var = create_test_system_bergeron(R_load)
    sys_block.unify_blocks()
    glob_time = Var("t_glob")

    problem = GenericEmtProblem(sys_block=sys_block, glob_time=glob_time)
    line.setup_indices(problem, vprms_offset=0)
    line_updater = BergeronBoundaryUpdater(line)

    solver = JitAdSolver(
        problem=problem,
        t0=0.0,
        t_end=0.03,
        h=h,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False
    )

    t_arr, y_arr, dy_arr, _, _ = solver.simulate(boundary_updater=line_updater)

    idx_vf: int = problem.get_var_idx(v_f_var)
    idx_vt: int = problem.get_var_idx(v_t_var)

    v_f_sol = y_arr[:, idx_vf]
    v_t_sol = y_arr[:, idx_vt]

    return t_arr, v_f_sol, v_t_sol, tau

# -----------------------------------------------------------------------------
# Mechanical system test helpers
# -----------------------------------------------------------------------------
def create_mechanical_system(vf: VarFactory) -> Tuple[Block, Var]:
    # state vars
    theta = vf.add_var("theta")
    omega = vf.add_var("omega")

    # algebraic vars
    Tm = vf.add_var("Tm")
    Te = vf.add_var("Te")

    # parameters
    D = vf.add_var("D")
    H = vf.add_var("H")
    omega_ref = vf.add_var("omega_ref")

    # derivatives
    d_theta = vf.add_diff_var(name="d_theta", base_var=theta)
    d_omega = vf.add_diff_var(name="d_omega", base_var=omega)

    state_vars: List[Var] = list([theta, omega])
    diff_vars: List[Var] = list([d_theta, d_omega])
    state_eqs: List[Expr] = list([
        omega,
        (Tm - Te - D * (omega - omega_ref)) / (2 * H)
    ])
    algebraic_vars: List[Var] = list([Tm, Te])
    algebraic_eqs: List[Expr] = list([
        Tm - Const(1),
        Te - Const(1)
    ])

    parameters: Dict[Var, Const] = dict({
        D: Const(2.0),
        H: Const(5.0),
        omega_ref: Const(1.0),
    })

    init_eqs: Dict[Var, Const] = dict({
        theta: Const(0.0),
        omega: Const(1.0),
        Tm: Const(1.0),
        Te: Const(1.0)
    })

    diff_init_eqs: Dict[Var, Const] = dict({
        d_theta: Const(1.0),
        d_omega: Const(0.0),
    })

    block = Block(
        name="MechanicalSystem",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        algebraic_vars=algebraic_vars,
        algebraic_eqs=algebraic_eqs,
        parameters=parameters,
        init_eqs=init_eqs,
        diff_init_eqs=diff_init_eqs
    )

    return block, theta

def run_case_mechanical_system(backend_str: EmtSolverTypes,
             h: float,
             t_end: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    print("\n" + "=" * 70)
    print(f"Running Mechanical system | Backend: {backend_str}")
    print("=" * 70)

    vf = VarFactory()
    block, vin_var = create_mechanical_system(vf=vf)
    block.unify_blocks()
    glob_time = vf.add_var("t_glob")

    problem = GenericEmtProblem(sys_block=block, glob_time=glob_time)
    problem.set_newton_trace_collector(NewtonTraceCollector())

    df = problem.get_init_guess_table()
    print(f"{df}")

    integration_method = DynamicIntegrationMethod.DaeTrapezoidal
    predictor_method = DynamicIntegrationMethod.OdeEuler

    if backend_str == EmtSolverTypes.Symbolic:
        solver = JitSymbolicSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=integration_method, pred_method=predictor_method, verbose=True
        )
    elif backend_str == EmtSolverTypes.Automatic:
        solver = JitAdSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=integration_method, verbose=False
        )
    elif backend_str == EmtSolverTypes.StructuralAD:
        solver = StructuralVectorizedSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=integration_method, verbose=False
        )
    elif backend_str == EmtSolverTypes.StructuralCompiled:
        solver = StructuralCompiledSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=integration_method, verbose=False
        )
    else:
        raise ValueError(f"Unknown backend : {backend_str}")

    t_start: float = time.time()

    t_arr, y_arr, dy_arr, _, _ = solver.simulate()

    elapsed: float = time.time() - t_start

    print(f"Elapsed time : {elapsed:.4f} s")

    collector = problem.get_newton_trace_collector()
    if collector:
        print(f"Newton iters : {len(collector.records)}")
    else:
        pass

    return t_arr, y_arr, dy_arr


# -----------------------------------------------------------------------------
# Buck converter helpers
# -----------------------------------------------------------------------------

class PWMControllerWrapper(BoundaryUpdateWrapper):
    __slots__ = ['t_sw', 'duty', 'v_in', 'offset', 'idx']

    def __init__(self, t_sw: float, duty: float, v_in: float, offset: int, idx: int):
        self.t_sw: float = t_sw
        self.duty: float = duty
        self.v_in: float = v_in
        self.offset: int = offset
        self.idx: int = idx

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        t_mod: float = t % self.t_sw
        if t_mod < (self.duty * self.t_sw):
            val: float = self.v_in
        else:
            val: float = 0.0
        params[self.offset + self.idx] = val


# -----------------------------------------------------------------------------
# Model definition
# -----------------------------------------------------------------------------

def create_buck_converter_system(vf: VarFactory) -> Tuple[Block, Var]:
    i_L = vf.add_var("i_L")
    v_C = vf.add_var("v_C")

    Vin_sw = vf.add_var("Vin_sw")
    R = vf.add_var("R")
    L = vf.add_var("L")
    C = vf.add_var("C")

    d_i_L = vf.add_diff_var(name = "d_i_L", base_var=i_L)
    d_v_C = vf.add_diff_var(name ="d_v_C",base_var=v_C)

    state_vars: List[Var] = list([i_L, v_C])
    diff_vars: List[Var] = list([d_i_L, d_v_C])
    state_eqs: List[Expr] = list([
        (Vin_sw - v_C) / L,
        (i_L - v_C / R) / C,
    ])

    parameters: Dict[Var, Const] = dict({
        Vin_sw: Const(0.0),
        R: Const(5.0),
        L: Const(100e-6),
        C: Const(470e-6),
    })

    block = Block(
        name="BuckConverter",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        parameters=parameters,
    )

    return block, Vin_sw


# -----------------------------------------------------------------------------
# Simulation runner
# -----------------------------------------------------------------------------
def run_case_buck_converter(backend_str: EmtSolverTypes) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    print("\n" + "=" * 70)
    print(f"Running Buck Converter | Backend: {backend_str}")
    print("=" * 70)

    # --- Electrical / control parameters ---
    V_IN: float = 48.0
    V_OUT_REF: float = 12.0
    F_SW: float = 20e3
    T_SW: float = 1.0 / F_SW
    DUTY: float = V_OUT_REF / V_IN

    DT: float = 1e-6
    T_TOTAL: float = 0.020

    vf = VarFactory()
    block, vin_var = create_buck_converter_system(vf=vf)
    block.unify_blocks()
    # glob_time = Var("t_glob")
    glob_time = vf.add_var("t_glob")

    problem = GenericEmtProblem(sys_block=block, glob_time=glob_time)
    problem.set_newton_trace_collector(NewtonTraceCollector())

    integration_method = DynamicIntegrationMethod.DaeTrapezoidal
    # integration_method = DynamicIntegrationMethod.DaeBDF2

    if backend_str == EmtSolverTypes.Symbolic:
        solver = JitSymbolicSolver(
            problem, t0=0.0, t_end=T_TOTAL, h=DT,
            method=integration_method, verbose=False
        )
    elif backend_str == EmtSolverTypes.Automatic:
        solver = JitAdSolver(
            problem, t0=0.0, t_end=T_TOTAL, h=DT,
            method=integration_method, verbose=False
        )
    elif backend_str ==EmtSolverTypes.StructuralAD:
        solver = StructuralVectorizedSolver(
            problem, t0=0.0, t_end=T_TOTAL, h=DT,
            method=integration_method, verbose=False
        )
    elif backend_str ==EmtSolverTypes.StructuralCompiled:
        solver = StructuralCompiledSolver(
            problem, t0=0.0, t_end=T_TOTAL, h=DT,
            method=integration_method, verbose=False
        )
    else:
        raise ValueError(f"Unknown backend : {backend_str}")

    offset: int = problem.get_variable_parameter_number()
    idx: int = problem.uid2idx_params[vin_var.uid]
    pwm_updater = PWMControllerWrapper(T_SW, DUTY, V_IN, offset, idx)

    t_start: float = time.time()

    t_arr, y_arr, dy_arr, _, _ = solver.simulate(boundary_updater=pwm_updater)


    elapsed: float = time.time() - t_start

    idx_iL: int = problem.get_var_idx(block.state_vars[0])
    idx_vC: int = problem.get_var_idx(block.state_vars[1])

    sol_i: np.ndarray = y_arr[:, idx_iL]
    sol_v: np.ndarray = y_arr[:, idx_vC]

    print(f"Elapsed time : {elapsed:.4f} s")
    print(f"Final V_out  : {sol_v[-1]:.6f} V")
    print(f"Final I_L    : {sol_i[-1]:.6f} A")

    collector = problem.get_newton_trace_collector()
    if collector:
        print(f"Newton iters : {len(collector.records)}")
    else:
        pass

    return t_arr, sol_v, sol_i, elapsed

# -----------------------------------------------------------------------------
# TESTS:
# Bergeron line test: test boundary updaters
# Mechanical system test: test derivatives update against all 4 solvers
# Buck converter: check procedural against all 4 solvers
# -----------------------------------------------------------------------------
def test_demo_bergeron_line():
    name = "demo_bergeron_line.csv"

    fname = os.path.join(os.path.dirname(__file__), '..', 'data', 'dynamics', name)
    reference_df = pd.read_csv(fname)

    t1, vf1, vt1, tau = run_test_bergeron("Open Circuit", R_load=1e9)
    t2, vf2, vt2, _ = run_test_bergeron("Matched Load", R_load=350.0)

    vf1 = np.atleast_2d(vf1).T if vf1.ndim == 1 else vf1
    vt1 = np.atleast_2d(vt1).T if vt1.ndim == 1 else vt1
    vf2 = np.atleast_2d(vf2).T if vf2.ndim == 1 else vf2
    vt2 = np.atleast_2d(vt2).T if vt2.ndim == 1 else vt2

    res = np.concatenate((vf1, vt1, vf2, vt2), axis=1)

    cols_vf1 = [f"vf1{i}" for i in range(vf1.shape[1])]
    cols_vt1 = [f"vt1{i}" for i in range(vt1.shape[1])]
    cols_vf2 = [f"vf2{i}" for i in range(vf2.shape[1])]
    cols_vt2 = [f"vt2{i}" for i in range(vt2.shape[1])]
    cols = cols_vf1 + cols_vt1 + cols_vf2 + cols_vt2

    results_df = pd.DataFrame(res, index=t1, columns=cols)
    results_df.index.name = "time_s"

    assert_frame_equal(
        results_df.reset_index(drop=True),
        reference_df.reset_index(drop=True),
        check_dtype=False,
        check_index_type=False,
        atol=1e-6
    )

def test_demo_mechanical_system() -> None:
    # retrieve reference results df
    name = "demo_check_derivatives.csv"
    fname = os.path.join(os.path.dirname(__file__), '..', 'data', 'dynamics', name)
    reference_df = pd.read_csv(fname)

    h = 1e-6
    t_end = 0.01

    t_sym_sd, y_sd, dy_sd = run_case_mechanical_system(backend_str=EmtSolverTypes.Symbolic, h=h, t_end=t_end)
    t_sym_ad, y_ad, dy_ad = run_case_mechanical_system(backend_str=EmtSolverTypes.Automatic, h=h, t_end=t_end)
    t_sym_vec, y_vec, dy_vec = run_case_mechanical_system(backend_str=EmtSolverTypes.StructuralAD, h=h, t_end=t_end)
    t_sym_comp, y_comp, dy_comp = run_case_mechanical_system(backend_str=EmtSolverTypes.StructuralCompiled, h=h,
                                                                    t_end=t_end)

    res = np.concatenate((y_sd, dy_sd, y_ad, dy_ad, y_vec, dy_vec, y_comp, dy_comp), axis=1)

    cols_y_sd = [f"y_sd{i}" for i in range(y_sd.shape[1])]
    cols_dy_sd = [f"dy_sd{i}" for i in range(dy_sd.shape[1])]
    cols_y_ad = [f"y_ad{i}" for i in range(y_ad.shape[1])]
    cols_dy_ad = [f"dy_ad{i}" for i in range(dy_ad.shape[1])]
    cols_y_vec = [f"y_vec{i}" for i in range(y_vec.shape[1])]
    cols_dy_vec = [f"dy_vec{i}" for i in range(dy_vec.shape[1])]
    cols_y_comp = [f"y_comp{i}" for i in range(y_comp.shape[1])]
    cols_dy_comp = [f"dy_comp{i}" for i in range(dy_comp.shape[1])]
    cols = cols_y_sd + cols_dy_sd + cols_y_ad + cols_dy_ad + cols_y_vec + cols_dy_vec + cols_y_comp + cols_dy_comp

    results_df = pd.DataFrame(res, index=t_sym_sd, columns=cols)
    results_df.index.name = "time_s"

    assert_frame_equal(
        results_df.reset_index(drop=True),
        reference_df.reset_index(drop=True),
        check_dtype=False,
        check_index_type=False,
        atol=1e-6
    )


def test_demo_emt_buck_converter() -> None:
    t_sym, v_sym, i_sym, time_sym = run_case_buck_converter(EmtSolverTypes.Symbolic)
    t_ad, v_ad, i_ad, time_ad = run_case_buck_converter(EmtSolverTypes.Automatic)
    t_vec, v_vec, i_vec, time_vec = run_case_buck_converter(EmtSolverTypes.StructuralAD)
    t_comp, v_comp, i_comp, time_comp = run_case_buck_converter(EmtSolverTypes.StructuralCompiled)

    print("\n" + "-" * 70)
    print("COMPARISON SUMMARY (NEW SOLVERS)")
    print("-" * 70)
    print(f"SD (Symbolic) time : {time_sym:.4f} s")
    print(f"AD time            : {time_ad:.4f} s")
    print(f"StructuralVectorizedSolver time        : {time_vec:.4f} s")
    print(f"StructuralCompiledSolver time        : {time_comp:.4f} s")

    err_ad_v = np.max(np.abs(v_sym - v_ad))
    err_vec_v = np.max(np.abs(v_sym - v_vec))
    err_comp_v = np.max(np.abs(v_sym - v_comp))

    print("-" * 30)
    print(f"Max Error AD vs SD      : {err_ad_v:.3e}")
    print(f"Max Error StructuralVectorizedSolver vs SD  : {err_vec_v:.3e}")
    print(f"Max Error StructuralCompiledSolver vs SD  : {err_comp_v:.3e}")

    assert np.allclose(v_sym[-100:], v_ad[-100:], atol=1e-5), "AD Solver Failed Accuracy Check!"
    assert np.allclose(v_sym[-100:], v_vec[-100:], atol=1e-5), "StructuralVectorizedSolver Solver Failed Accuracy Check!"
    assert np.allclose(v_sym[-100:], v_comp[-100:],
                       atol=1e-5), "StructuralCompiledSolver Solver Failed Accuracy Check!"

