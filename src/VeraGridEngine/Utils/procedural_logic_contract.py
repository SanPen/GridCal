# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import Dict, Iterable, Protocol, TypeVar

from VeraGridEngine.basic_structures import Vec
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory


ExpressionT = TypeVar("ExpressionT")
ProceduralLogicData = Dict[str, object]


class ProceduralLogicEntryContract(Protocol[ExpressionT]):
    """Declare the behavior a symbolic block requires from procedural logic."""

    __slots__ = ()

    def to_data(self) -> ProceduralLogicData:
        """Return the declarative representation of this logic entry.

        :return: Typed declarative logic data.
        """
        ...

    def remap(
            self,
            var_mapping: Dict[ExpressionT | str, ExpressionT],
    ) -> "ProceduralLogicEntryContract[ExpressionT]":
        """Clone this entry against a symbolic-variable mapping.

        :param var_mapping: Source expressions and names mapped to replacements.
        :return: Remapped procedural logic entry.
        """
        ...

    def remap_with_structural_vars(
            self,
            var_mapping: Dict[ExpressionT | str, ExpressionT],
            structural_var_mapping: Dict[int, ExpressionT],
    ) -> "ProceduralLogicEntryContract[ExpressionT]":
        """Clone this entry with symbolic and stable structural mappings.

        :param var_mapping: Source expressions and names mapped to replacements.
        :param structural_var_mapping: Stable source identities mapped to cloned variables.
        :return: Remapped procedural logic entry.
        """
        ...


class ProceduralLogicCodecContract(Protocol[ExpressionT]):
    """Declare fail-closed reconstruction of declarative procedural entries."""

    __slots__ = ()

    def parse_entries(
            self,
            entries: Iterable[ProceduralLogicData],
            var_factory: VarFactory | None = None,
    ) -> Iterable[ProceduralLogicEntryContract[ExpressionT]]:
        """Reconstruct typed procedural entries from declarative data.

        :param entries: Declarative procedural entries.
        :param var_factory: Optional factory required by entries holding live variables.
        :return: Reconstructed typed entries.
        """
        ...

class ManufacturerNativeRuntimeSessionProtocol(Protocol):
    """Dependency-neutral driver-owned native session used by boundary logic."""

    __slots__ = ()

    def preflight(self, problem: object, logic_entries: Iterable[object], model_mode: int) -> None:
        """Resolve providers, mappings, limits and workers before native startup.

        :param problem: Numerical problem exposing compiled variable maps.
        :param logic_entries: Runtime procedural entries owned by the updater.
        :param model_mode: Exact IEEE/CIGRE EMT or RMS mode value.
        :return: None.
        """
        ...

    def initialize(self, t: float, x: Vec, params: Vec) -> None:
        """Seed held native outputs once from the complete t0 guess.

        :param t: Required zero startup time.
        :param x: Complete finite initialization state.
        :param params: Mutable runtime parameter vector.
        :return: None.
        """
        ...

    def get_next_sample_time(self, t_prev: float, t_target: float) -> float | None:
        """Return the earliest fixed native sample boundary in an interval.

        :param t_prev: Previous accepted solver time.
        :param t_target: Proposed target time.
        :return: Earliest boundary or ``None``.
        """
        ...

    def commit_boundary(self, t: float, x: Vec, params: Vec) -> None:
        """Commit due native instances after the solver accepts a boundary.

        :param t: Accepted boundary time.
        :param x: Accepted state vector.
        :param params: Mutable runtime parameters receiving held outputs.
        :return: None.
        """
        ...

    def close(self) -> None:
        """Close every worker owned by the session.

        :return: None.
        """
        ...
