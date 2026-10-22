# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import warnings

from VeraGridEngine.Utils.NumericalMethods.emt_sparse_solver_loader import load_sparse_solver_backend_provider
from VeraGridEngine.Utils.NumericalMethods.external_sparse_solver_interface import SparseLinearSolverBackendProvider
from VeraGridEngine.Utils.NumericalMethods.sparse_lu_selection import get_sparse_lu_provider_status, resolve_sparse_lu_provider
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import SparseSolver


def _report_sparse_solver_warning(message: str, logger: Logger | None) -> None:
    """
    Report a sparse solver resolution warning.

    :param message: Warning text.
    :param logger: Logger receiving the warning; a RuntimeWarning is emitted when None.
    :return: None
    """
    if logger is None:
        warnings.warn(message, RuntimeWarning, stacklevel=3)
    else:
        logger.add_warning(message)


def resolve_emt_sparse_solver_backend_provider(
        solver_type: SparseSolver,
        external_plugin_name: str,
        external_plugin_directory: str,
        allow_internal_fallback: bool,
        logger: Logger | None = None,
) -> SparseLinearSolverBackendProvider:
    """
    Resolve the EMT sparse solver backend provider.

    Internal providers and every fallback go through the sparse LU selection layer,
    which reports why a requested solver is unavailable and uses SciPy SuperLU.

    :param solver_type: Requested sparse solver type.
    :type solver_type: SparseSolver
    :param external_plugin_name: External plugin name.
    :type external_plugin_name: str
    :param external_plugin_directory: External plugin directory override.
    :type external_plugin_directory: str
    :param allow_internal_fallback: Whether internal fallback is allowed.
    :type allow_internal_fallback: bool
    :param logger: Logger receiving fallback warnings; RuntimeWarning is used when None.
    :type logger: Logger | None
    :return: Resolved backend provider.
    :rtype: SparseLinearSolverBackendProvider
    """
    if len(external_plugin_name) > 0:
        plugin_provider: SparseLinearSolverBackendProvider

        try:
            plugin_provider = load_sparse_solver_backend_provider(
                plugin_name=external_plugin_name,
                plugin_directory_override=external_plugin_directory,
            )
        except (FileNotFoundError, RuntimeError, AttributeError, TypeError, ValueError) as error:
            if allow_internal_fallback:
                _report_sparse_solver_warning(
                    f"External sparse solver plugin '{external_plugin_name}' could not be loaded: {error}",
                    logger,
                )
                return resolve_sparse_lu_provider(solver_type, logger)
            else:
                raise

        if plugin_provider.get_solver_type() == solver_type:
            if plugin_provider.is_available():
                return plugin_provider
            else:
                plugin_reason: str = plugin_provider.get_unavailable_reason()
                if len(plugin_reason) == 0:
                    plugin_reason = "plugin reported unavailable without a reason"
                else:
                    pass

                if allow_internal_fallback:
                    _report_sparse_solver_warning(
                        f"External sparse solver plugin '{external_plugin_name}' is unavailable: {plugin_reason}",
                        logger,
                    )
                    return resolve_sparse_lu_provider(solver_type, logger)
                else:
                    raise RuntimeError(
                        f"External sparse solver plugin '{external_plugin_name}' is unavailable and fallback is disabled: {plugin_reason}"
                    )
        else:
            raise ValueError(
                f"External sparse solver plugin '{external_plugin_name}' exposes {plugin_provider.get_solver_type()} instead of requested {solver_type}"
            )
    else:
        pass

    if allow_internal_fallback:
        return resolve_sparse_lu_provider(solver_type, logger)
    else:
        provider, reason = get_sparse_lu_provider_status(solver_type)
        if provider is None:
            raise RuntimeError(f"Sparse LU solver {solver_type.value} is unavailable: {reason}")
        else:
            return provider
