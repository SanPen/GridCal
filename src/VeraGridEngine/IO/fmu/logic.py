# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Serialize the procedural logic shared by both FMU export modes."""

from __future__ import annotations

from typing import Any

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.procedural_logic import procedural_logic_to_dict
from VeraGridEngine.IO.fmu.CosimulationInterface.export_ir import ExportLogicEntry as CoSimulationLogicEntry
from VeraGridEngine.IO.fmu.ExportInterface.export_ir import ExportLogicEntry as ModelExchangeLogicEntry


def build_co_simulation_logic_entries(block: Block) -> tuple[CoSimulationLogicEntry, ...]:
    """Serialize procedural logic accepted by Co-Simulation export.

    :param block: Flattened symbolic model.
    :return: Co-Simulation logic entries.
    """
    supported_types: set[str] = {
        "fixed_sample",
        "sampled_value",
        "flipflop",
        "pickup_dropoff",
        "reset_on_rising_edge",
        "delayed_threshold_latch",
    }
    serialized: list[dict[str, Any]] = procedural_logic_to_dict(block.procedural_logic)
    entries: list[CoSimulationLogicEntry] = list()
    for index, item in enumerate(serialized):
        logic_type: str = str(item.get("logic_type", ""))
        if logic_type not in supported_types:
            raise ValueError(f"Unsupported Co-Simulation procedural logic type: {logic_type!r}")
        entries.append(CoSimulationLogicEntry(index, logic_type, str(item.get("name", "")), dict(item)))
    return tuple(entries)


def build_model_exchange_logic_entries(block: Block) -> tuple[ModelExchangeLogicEntry, ...]:
    """Serialize procedural logic accepted by Model Exchange export.

    :param block: Flattened symbolic model.
    :return: Model Exchange logic entries.
    """
    supported_types: set[str] = {"fixed_sample", "sampled_value", "flipflop"}
    serialized: list[dict[str, Any]] = procedural_logic_to_dict(block.procedural_logic)
    entries: list[ModelExchangeLogicEntry] = list()
    for index, item in enumerate(serialized):
        logic_type: str = str(item.get("logic_type", ""))
        if logic_type not in supported_types:
            raise ValueError(f"Unsupported Model Exchange procedural logic type: {logic_type!r}")
        entries.append(ModelExchangeLogicEntry(index, logic_type, str(item.get("name", "")), dict(item)))
    return tuple(entries)


def export_logic_manifest(entries: tuple[Any, ...]) -> list[dict[str, Any]]:
    """Serialize logic entries for a debug resource.

    :param entries: Co-Simulation or Model Exchange logic entries.
    :return: JSON-compatible logic records.
    """
    return [dict(entry.data) for entry in entries]
