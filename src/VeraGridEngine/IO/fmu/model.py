# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, TypedDict, cast

from VeraGridEngine.Utils.Symbolic.block import Block, flatten_block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.Utils.procedural_logic import ProceduralLogicCodec

SNAPSHOT_SCHEMA_VERSION = 1


class FmuBlockType(TypedDict):
    """Serialized Python type identity of the source block."""

    module: str
    qualname: str


class FmuModelSnapshot(TypedDict):
    """Versioned serialized FMU source model."""

    schema_version: int
    block_type: FmuBlockType
    block: Dict[str, Any]


def _require_string_key_mapping(value: object, context: str) -> Dict[str, object]:
    """Validate one JSON object before it crosses into symbolic reconstruction.

    :param value: Parsed JSON value expected to contain a mapping.
    :param context: Domain description included in validation failures.
    :return: Independent mapping whose keys are all strings.
    """
    if isinstance(value, dict):
        validated_mapping: Dict[str, object] = dict()
        raw_key: object
        raw_value: object
        for raw_key, raw_value in value.items():
            if isinstance(raw_key, str):
                validated_mapping[raw_key] = raw_value
            else:
                raise TypeError(f"{context} keys must be strings")
        else:
            pass
        return validated_mapping
    else:
        raise TypeError(f"{context} must be a mapping")


def build_model_snapshot(model: Block) -> FmuModelSnapshot:
    """Build the versioned declarative FMU snapshot for one symbolic block.

    ``Block.to_dict`` already preserves nullable external mappings, so snapshot
    creation reads the canonical block without temporarily mutating its graph.

    :param model: Canonical symbolic block to serialize.
    :return: Versioned snapshot containing declarative block data and type metadata.
    """
    block_payload: Dict[str, Any] = model.to_dict()
    block_type_data: FmuBlockType = dict()
    block_type_data["module"] = type(model).__module__
    block_type_data["qualname"] = type(model).__qualname__

    snapshot: FmuModelSnapshot = dict()
    snapshot["schema_version"] = SNAPSHOT_SCHEMA_VERSION
    snapshot["block_type"] = block_type_data
    snapshot["block"] = block_payload
    return snapshot


def reconstruct_block(snapshot: FmuModelSnapshot) -> Block:
    """Reconstruct a symbolic block from a validated declarative snapshot.

    :param snapshot: Versioned snapshot or legacy direct block payload.
    :return: Reconstructed block with procedural logic decoded explicitly.
    """
    block_payload: Dict[str, object] = _require_string_key_mapping(
        value=snapshot["block"],
        context="FMU block snapshot payload",
    )
    return Block.parse(
        data=block_payload,
        procedural_logic_codec=ProceduralLogicCodec(),
    )


def save_snapshot(snapshot: FmuModelSnapshot, path: str | Path) -> Path:
    """Persist one declarative snapshot as deterministic UTF-8 JSON.

    :param snapshot: Validated snapshot data to persist.
    :param path: Destination file path.
    :return: Resolved destination represented as a ``Path`` instance.
    """
    output_path: Path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_snapshot: str = json.dumps(snapshot, indent=2, sort_keys=True)
    output_path.write_text(serialized_snapshot, encoding="utf-8")
    return output_path


def load_snapshot(path: str | Path) -> FmuModelSnapshot:
    """Load and validate the top-level mapping of one JSON snapshot.

    :param path: Existing UTF-8 snapshot file.
    :return: Snapshot mapping with validated string keys.
    """
    serialized_snapshot: str = Path(path).read_text(encoding="utf-8")
    parsed_snapshot: object = json.loads(serialized_snapshot)
    loaded_snapshot: Dict[str, object] = _require_string_key_mapping(
        value=parsed_snapshot,
        context="FMU model snapshot",
    )
    return cast(FmuModelSnapshot, loaded_snapshot)


def _validate_no_duplicate_names(vars_list: List[Var], label: str) -> None:
    """Execute the `_validate_no_duplicate_names` operation.

    :param vars_list: Function input.
    :param label: Function input.
    :return: Function result.
    """
    names = [var.name for var in vars_list]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Duplicate {label} names in flattened model: {', '.join(duplicates)}")


def validate_flat_block(block: Block) -> None:
    """Execute the `validate_flat_block` operation.

    :param block: Function input.
    :return: Function result.
    """
    _validate_no_duplicate_names(block.state_vars, "state")
    _validate_no_duplicate_names(block.algebraic_vars, "algebraic")
    _validate_no_duplicate_names(block.diff_vars, "differential")

    if len(block.state_vars) != len(block.state_eqs):
        raise ValueError(
            f"FMU export requires one state equation per state variable; got {len(block.state_vars)} states and {len(block.state_eqs)} state equations"
        )
    if len(block.algebraic_vars) != len(block.algebraic_eqs):
        raise ValueError(
            f"FMU export requires one algebraic equation per algebraic variable; got {len(block.algebraic_vars)} algebraics and {len(block.algebraic_eqs)} algebraic equations"
        )

    known_uids = {var.uid for var in block.state_vars + block.algebraic_vars + block.diff_vars}
    known_uids.update(var.uid for var in block.parameters.keys())
    known_uids.update(var.uid for var in block.event_dict.keys())
    known_uids.update(var.uid for var in block.mode_dict.keys())

    missing_outputs = sorted(var.name for var in block.out_vars if var.uid not in known_uids)
    if missing_outputs:
        raise ValueError(f"Output vars must exist in the flattened model symbol table: {', '.join(missing_outputs)}")

    missing_params = sorted(var.name for var, value in block.parameters.items() if not isinstance(value, Const) or value.value is None)
    if missing_params:
        raise ValueError(f"Constant parameters without concrete values are not exportable: {', '.join(missing_params)}")


def flatten_model(snapshot: FmuModelSnapshot) -> Block:
    """Execute the `flatten_model` operation.

    :param snapshot: Function input.
    :return: Function result.
    """
    block_copy: Block = reconstruct_block(snapshot)
    flat_block: Block = flatten_block(block_copy)
    validate_flat_block(flat_block)
    return flat_block
