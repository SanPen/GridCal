# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from VeraGridEngine.IO.fmu.ExportInterface.export_ir import ExportModel, StorageSegment


class ResolvedStorage:
    """Storage location of one exported variable."""

    __slots__ = ("segment", "index")

    def __init__(self, segment: StorageSegment, index: int) -> None:
        """:param segment: Runtime storage segment.
        :param index: Index within the segment.
        """
        self.segment = segment
        self.index = index


class CVariableResolver:
    __slots__ = (
        "export_model",
        "by_uid",
        "by_name",
    )

    def __init__(self, export_model: ExportModel):
        """Initialize the object state.

        :param export_model: Function input.
        :return: None.
        """
        self.export_model = export_model
        self.by_uid = {variable.uid: variable for variable in export_model.variables}
        self.by_name = {variable.name: variable for variable in export_model.variables}

    @staticmethod
    def _segment_expr(segment: StorageSegment, index: int) -> str:
        """Execute the `_segment_expr` operation.

        :param segment: Function input.
        :param index: Function input.
        :return: Function result.
        """
        if segment == StorageSegment.STATES:
            return f"instance->states[{index}]"
        if segment == StorageSegment.DERIVATIVES:
            return f"instance->derivatives[{index}]"
        if segment == StorageSegment.ALGEBRAICS:
            return f"instance->algebraics[{index}]"
        if segment == StorageSegment.INPUTS:
            return f"instance->inputs[{index}]"
        if segment == StorageSegment.CONST_PARAMS:
            return f"instance->const_params[{index}]"
        if segment == StorageSegment.RUNTIME_PARAMS:
            return f"instance->runtime_params[{index}]"
        raise ValueError(f"Unsupported storage segment: {segment}")

    def resolve_var(self, uid: int) -> str:
        """Execute the `resolve_var` operation.

        :param uid: Function input.
        :return: Function result.
        """
        variable = self.by_uid[uid]
        return self._segment_expr(variable.storage_segment, variable.storage_index)

    def resolve_target(self, uid: int) -> str:
        """Execute the `resolve_target` operation.

        :param uid: Function input.
        :return: Function result.
        """
        variable = self.by_uid[uid]
        return self._segment_expr(variable.storage_segment, variable.storage_index)

    def resolve_special(self, name: str) -> str | None:
        """Execute the `resolve_special` operation.

        :param name: Function input.
        :return: Function result.
        """
        if name == "glob_time":
            return "instance->time"
        if name == "h":
            raise ValueError("The symbolic step variable 'h' is not supported in Model Exchange export")
        variable = self.by_name.get(name)
        if variable is None:
            return None
        return self.resolve_var(variable.uid)
