from __future__ import annotations

import numpy as np
import pytest

from VeraGridEngine.Simulations.Rms.initialization_rms import run_rms_consistent_initialization
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import RmsInitializationMethod


class _ScalarRmsInitializationProblem:
    """Minimal RMS problem contract for the global consistent-Newton stage."""

    __slots__ = (
        "y", "options", "init_guess", "event_params_init_dict", "sys_block",
        "state_vars", "state_eqs", "algebraic_vars", "algebraic_eqs",
        "variable_parameters", "event_parameters_eqs", "event_parameters_eqs0",
        "uid2idx_vars", "uid2idx_event_params",
    )

    VARS_NAME = "x"
    DIFF_NAME = "dx"
    VARIABLE_PARAMS_NAME = "event_x"
    CONSTANT_PARAMS_NAME = "params"

    def __init__(self) -> None:
        """Set up a scalar algebraic problem with a deliberately wrong guess.

        :return: None.
        """
        self.y = Var("y")
        self.options = RmsOptions(
            initialization_method=RmsInitializationMethod.ConsistentNewton,
            tolerance=1.0e-10,
            max_iter=20,
        )
        self.init_guess = {self.y.uid: 9.0}
        self.event_params_init_dict = {}
        self.sys_block = Block(children=[], in_vars=[])
        self.state_vars = []
        self.state_eqs = []
        self.algebraic_vars = [self.y]
        self.algebraic_eqs = [self.y - Const(2.0)]
        self.variable_parameters = []
        self.event_parameters_eqs = []
        self.event_parameters_eqs0 = []
        self.uid2idx_vars = {self.y.uid: 0}
        self.uid2idx_event_params = {}

    def get_x0(self) -> np.ndarray:
        """Return the current scalar state guess.

        :return: Initial unknown vector.
        """
        return np.asarray([self.init_guess[self.y.uid]], dtype=np.float64)

    def get_dx0(self) -> np.ndarray:
        """Return the empty derivative vector.

        :return: Empty derivative vector.
        """
        return np.zeros(0, dtype=np.float64)

    def get_eventparams0(self) -> np.ndarray:
        """Return the empty event parameter vector.

        :return: Empty event parameter vector.
        """
        return np.zeros(0, dtype=np.float64)

    def get_parameters_values(self) -> list[Const]:
        """Return the absent constant parameters.

        :return: Empty parameter list.
        """
        return []

    def get_compiler_names_dict(self) -> dict[int, str]:
        """Name the only compiled unknown.

        :return: UID to compiler name mapping.
        """
        return {self.y.uid: "x[0]"}

    def get_alias_names_dict(self) -> dict[int, str]:
        """Name the only alias in the initialization problem.

        :return: UID to alias mapping.
        """
        return {self.y.uid: "x_0"}


class _MissingStateInitializationProblem(_ScalarRmsInitializationProblem):
    """Scalar state with dynamics but deliberately no explicit init equation."""

    __slots__ = ("x",)

    def __init__(self) -> None:
        """Replace the algebraic variable with an uninitialized state.

        :return: None.
        """
        super().__init__()
        self.x = self.y
        self.init_guess = {}
        self.state_vars = [self.x]
        self.state_eqs = [self.x - Const(3.0)]
        self.algebraic_vars = []
        self.algebraic_eqs = []

    def get_x0(self) -> np.ndarray:
        """Supply a neutral guess for the state equilibrium solve.

        :return: Initial state vector.
        """
        return np.asarray([0.0], dtype=np.float64)


class _NonConvergingRmsInitializationProblem(_ScalarRmsInitializationProblem):
    """Scalar initialization problem with an unsatisfiable residual."""

    __slots__ = ()

    def __init__(self) -> None:
        """
        Replace the solvable residual with a non-zero constant equation.

        :return: None.
        """
        super().__init__()

        # A constant non-zero residual cannot be reduced by changing the only
        # unknown, so it provides a deterministic non-convergence scenario.
        self.algebraic_eqs = [Const(1.0)]


def test_consistent_newton_is_an_rms_initialization_option() -> None:
    """Expose the global solver as an RMS initialization choice.

    :return: None.
    """
    assert "ConsistentNewton" in RmsInitializationMethod.list()


def test_consistent_newton_solves_initialized_algebraic_variables() -> None:
    """Correct an algebraic guess using its initialized residual.

    :return: None.
    """
    problem: _ScalarRmsInitializationProblem = _ScalarRmsInitializationProblem()
    logger: Logger = Logger()

    converged: bool = run_rms_consistent_initialization(
        problem=problem,
        options=problem.options,
        logger=logger,
    )

    assert converged
    assert np.isclose(problem.init_guess[problem.y.uid], 2.0, atol=1.0e-10)
    assert len(logger.entries) == 0


def test_consistent_newton_uses_equilibrium_for_state_without_init_eq() -> None:
    """Use the state equilibrium when no explicit initial equation exists.

    :return: None.
    """
    problem: _MissingStateInitializationProblem = _MissingStateInitializationProblem()

    converged: bool = run_rms_consistent_initialization(
        problem=problem,
        options=problem.options,
        logger=None,
    )

    assert converged
    assert np.isclose(problem.init_guess[problem.x.uid], 3.0, atol=1.0e-10)


def test_auto_non_convergence_adds_one_warning() -> None:
    """
    Report one warning when Auto keeps a non-converged initialization candidate.

    :return: None.
    """
    problem: _NonConvergingRmsInitializationProblem = _NonConvergingRmsInitializationProblem()
    problem.options.initialization_method = RmsInitializationMethod.Auto
    logger: Logger = Logger()

    converged: bool = run_rms_consistent_initialization(
        problem=problem,
        options=problem.options,
        logger=logger,
    )

    assert converged is False
    assert logger.warning_count() == 1
    assert logger.error_count() == 0
    assert logger.entries[0].device_class == "RMS"
    assert logger.entries[0].device_property == "initialization"
    assert "Auto mode is continuing" in logger.entries[0].msg


def test_consistent_newton_non_convergence_logs_error_before_raising() -> None:
    """
    Record one error before strict consistent initialization stops construction.

    :return: None.
    """
    problem: _NonConvergingRmsInitializationProblem = _NonConvergingRmsInitializationProblem()
    logger: Logger = Logger()

    with pytest.raises(RuntimeError, match="simulation construction is stopping"):
        run_rms_consistent_initialization(
            problem=problem,
            options=problem.options,
            logger=logger,
        )

    assert logger.warning_count() == 0
    assert logger.error_count() == 1
    assert logger.entries[0].device_class == "RMS"
    assert logger.entries[0].device_property == "initialization"
