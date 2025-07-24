from __future__ import annotations

from typing import Callable, Iterable, List, Tuple, Union

from ortools.math_opt.python.mathopt import SolverType
from ortools.math_opt.python.model import Model
from ortools.math_opt.python.variables import Variable as LpVar
from ortools.math_opt.python.linear_constraints import LinearConstraint as LpCst
from ortools.math_opt.python.solve import solve
from ortools.math_opt.python.bounded_expressions import BoundedExpression as LpCstBounded
from ortools.math_opt.python.variables import LinearExpression as LpExp
from GridCalEngine.enumerations import MIPSolvers
from GridCalEngine.basic_structures import Logger


###############################################################################
# Helper utilities                                                             
###############################################################################

def _solver_type_from_enum(solver_type: MIPSolvers) -> SolverType:
    """Map ``GridCalEngine.enumerations.MIPSolvers`` → math_opt.SolverType."""
    SolverType.HIGHS
    return solver_type.value


def get_available_mip_solvers() -> List[str]:
    """Return the list of *names* (e.g. ``"SCIP"``) that are compiled in."""

    available: list[str] = []
    for st in SolverType:
        # Preferred path (>= 9.9) ----------------------------------------------------
        is_supported = getattr(st, "is_supported", None)
        if callable(is_supported):
            if is_supported():
                available.append(st.name)
            continue

        # Fallback path --------------------------------------------------------------
        try:
            # Solving an *empty* model is practically free.
            _ = solve(Model(), solver_type=st)
            available.append(st.name)
        except (NotImplementedError, RuntimeError, ValueError):
            # *NotImplementedError* → solver not compiled; *RuntimeError* / *ValueError*
            # for other cases where the call chain fails early.
            pass

    return available

    return [st.name for st in SolverType if st.is_supported()]




def set_var_bounds(var: LpVar, lb: float, ub: float) -> None:  # API compatibility shim
    var.lb = lb
    var.ub = ub


###############################################################################
# The main wrapper class                                                       
###############################################################################

class LpModel:
    """Thin compatibility layer over :pymod:`ortools.math_opt`."""

    # --- Status codes kept identical to the old *pywraplp* values ----------------
    OPTIMAL = 0
    FEASIBLE = 1
    INFEASIBLE = 2
    UNBOUNDED = 3
    ABNORMAL = 4
    MODEL_INVALID = 5
    NOT_SOLVED = 6

    INFINITY: float = 1e20
    originally_infeasible: bool = False

    # -------------------------------------------------------------------------
    def __init__(self, solver_type: MIPSolvers):
        self.solver_type: MIPSolvers = solver_type
        self._solver_type_ortools: SolverType = _solver_type_from_enum(solver_type)

        self.model: Model = Model()
        self._result = None  # type: ignore

        self._var_names: set[str] = set()
        self.logger = Logger()

    # ------------------------------------------------------------------ building
    def add_int(self, lb: int, ub: int, name: str = "") -> LpVar:
        if name and name in self._var_names:
            raise ValueError(f"Variable name already taken: {name}")
        self._var_names.add(name)
        return self.model.add_variable(lb=lb, ub=ub, integer=True, name=name)

    def add_var(self, lb: float, ub: float, name: str = "") -> LpVar:
        if name and name in self._var_names:
            raise ValueError(f"Variable name already taken: {name}")
        self._var_names.add(name)
        return self.model.add_variable(lb=lb, ub=ub, integer=False, name=name)

    def add_cst(self, cst: Union[LpCstBounded, LpExp, bool], name: str = "") -> Union[LpCst, int]:
        if name and name in self._var_names:
            raise ValueError(f"Constraint name already taken: {name}")
        self._var_names.add(name)

        if isinstance(cst, bool):
            return 0  # satisfied or contradictory tautology → nothing to add
        return self.model.add_linear_constraint(cst, name=name)

    @staticmethod
    def sum(exprs: Iterable[LpExp]) -> LpExp:  # shadow built‑in sum to keep the API
        return sum(exprs)

    # -------------------------------------------------------------- objective
    def minimize(self, obj_function: LpExp) -> None:
        self.model.minimize(obj_function)

    # -------------------------------------------------------------------- solve
    def solve(
            self,
            robust: bool = True,  # ignored for now
            show_logs: bool = False,
            progress_text: Callable[[str], None] | None = None,
    ) -> int:
        if progress_text is not None:
            progress_text(f"Solving model with {self.solver_type.value}…")

        self._result = solve(
            self.model,
            solver_type=self._solver_type_ortools,
        )

        # Map *math_opt* termination → legacy status codes
        term = self._result.termination.reason
        status_map = {
            term.OPTIMAL: self.OPTIMAL,
            term.FEASIBLE: self.FEASIBLE,
            term.INFEASIBLE: self.INFEASIBLE,
            term.UNBOUNDED: self.UNBOUNDED,
        }
        return status_map.get(term, self.NOT_SOLVED)

    # --------------------------------------------------------------- inspectors
    def fobj_value(self) -> float:
        if self._result is None:
            raise RuntimeError("Model has not been solved yet.")
        return self._result.objective_value

    def is_mip(self):
        return [v.integer for v in self.model.variables]

    def get_value(self, x: Union[float, int, LpVar, LpExp, LpCst, LpCstBounded]) -> float:
        if isinstance(x, (float, int)):
            return float(x)
        if self._result is None:
            raise RuntimeError("Model has not been solved yet.")

        if isinstance(x, LpVar):
            return self._result.variable_values.get(x, 0.0)
        if isinstance(x, LpExp):
            return self._result.evaluate(x)
        if isinstance(x, LpCstBounded):
            return self._result.evaluate(x.expression)
        raise TypeError(f"Unrecognised type {type(x)}")

    def get_dual_value(self, cst: LpCst) -> float:
        if self._result is None:
            raise RuntimeError("Model has not been solved yet.")
        return self._result.dual_values.get(cst, 0.0)

    # ---------------------------------------------------------------- misc tools
    @classmethod
    def status2string(cls, stat: int) -> str:
        mapping = {
            cls.OPTIMAL: "optimal",
            cls.FEASIBLE: "feasible",
            cls.INFEASIBLE: "infeasible",
            cls.UNBOUNDED: "unbounded",
            cls.ABNORMAL: "abnormal",
            cls.MODEL_INVALID: "model invalid",
            cls.NOT_SOLVED: "not solved",
        }
        return mapping.get(stat, "unknown")
