# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Residual row map export of EMT problems: map, fingerprint, file artifact and fail-closed reader."""

from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
from typing import BinaryIO, Dict, List, Tuple

import numpy as np
import numpy.typing as npt
import pytest

from tests.Base.test_dynamic_results_save_load import _build_emt_driver
from tests.EMT.test_kundur_emt_initialization import _build_kundur_problem
from VeraGridEngine.enumerations import ExpressionAffinity, ResidualRowAffinityCode
from VeraGridEngine.IO.emt_residual_row_map_io import read_emt_residual_row_map, write_emt_residual_row_map
from VeraGridEngine.Simulations.EMT.emt_driver import EmtSimulationDriver
from VeraGridEngine.Simulations.EMT.emt_problem_factory import build_emt_problem
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.problems.emt_residual_row_classification import (
    EmtResidualRowClassification,
    EmtResidualRowMap,
    build_emt_residual_row_map,
    classify_emt_residual_rows,
)
from VeraGridEngine.Utils.canonical_json import canonical_json_bytes
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var


@pytest.fixture(scope="module")
def kundur_problem() -> EmtProblemDae:
    """
    Build the self-contained Kundur EMT problem once for this module.

    :return: Kundur EMT problem.
    """
    return _build_kundur_problem()[0]


@pytest.fixture(scope="module")
def kundur_map(kundur_problem: EmtProblemDae) -> EmtResidualRowMap:
    """
    Build the Kundur residual row map once for this module.

    :param kundur_problem: Kundur EMT problem.
    :return: Residual row map bound to the identity "kundur".
    """
    return build_emt_residual_row_map(kundur_problem, "kundur")


def _synthetic_problem() -> EmtProblemTemplate:
    """
    Build a three-row EMT problem: one affine state row, one affine and one nonlinear algebraic row.

    :return: Problem.
    """
    x: Var = Var("x")
    y: Var = Var("y")
    z: Var = Var("z")
    block: Block = Block(name="synthetic", state_vars=list((x,)), state_eqs=list((y - x,)), algebraic_vars=list((y, z)),
                         algebraic_eqs=list((y - Const(2.0) * x, z - y * y)))
    return EmtProblemTemplate(sys_block=block, static_parameter_values_mapping=dict(), glob_time=Var("time"))


def _semantic_note() -> str:
    """
    Return the normative semantic note of the sealed requirement, verbatim.

    :return: Note.
    """
    return ("Rows and columns follow VeraGrid solver order: state rows (d_x - f) then algebraic rows; state unknowns then algebraic unknowns. "
            "Codes: CONSTANT=0, EXCITATION=1, AFFINE=2, NONLINEAR=3. The Jacobian rows of AFFINE rows are invariant while constant parameters, "
            "the step size h and the integration method are unchanged; runtime parameters and time change only residual values, never the "
            "Jacobian of AFFINE rows. Opaque rows are coded NONLINEAR and their support is every unknown. Binding to the consumer program is "
            "through model_identity, which the consumer must check.")


def _assert_immutable_int32(values: npt.NDArray[np.int32]) -> None:
    """
    Assert that an exported array is native int32, C-contiguous and permanently read-only.

    :param values: Exported array.
    :return: None.
    """
    assert values.dtype == np.dtype(np.int32)
    assert values.dtype.isnative
    assert values.flags.c_contiguous
    assert not values.flags.writeable
    with pytest.raises(ValueError):
        values.setflags(write=True)


def test_code_table() -> None:
    """
    The versioned affinity code table is CONSTANT=0, EXCITATION=1, AFFINE=2, NONLINEAR=3.

    :return: None.
    """
    assert int(ResidualRowAffinityCode.CONSTANT) == 0
    assert int(ResidualRowAffinityCode.EXCITATION) == 1
    assert int(ResidualRowAffinityCode.AFFINE) == 2
    assert int(ResidualRowAffinityCode.NONLINEAR) == 3
    assert len(ResidualRowAffinityCode) == 4


def test_kundur_map_matches_classification_and_columns(kundur_problem: EmtProblemDae, kundur_map: EmtResidualRowMap) -> None:
    """
    Kundur codes match the classification row by row and support columns follow uid2idx_vars.

    :param kundur_problem: Kundur EMT problem.
    :param kundur_map: Kundur residual row map.
    :return: None.
    """
    classification: EmtResidualRowClassification = classify_emt_residual_rows(kundur_problem)
    codes: Dict[ExpressionAffinity, int] = dict()
    affinity: ExpressionAffinity
    for affinity in ExpressionAffinity:
        codes[affinity] = int(ResidualRowAffinityCode[affinity.name])
    expected_codes: List[int] = list()
    for affinity in classification.get_row_affinities():
        expected_codes.append(codes[affinity])
    expected_columns: List[int] = list()
    uid: int
    for uid in classification.get_nonlinear_support_uids():
        expected_columns.append(kundur_problem.uid2idx_vars[uid])
    expected_columns.sort()
    columns: npt.NDArray[np.int32] = kundur_map.get_nonlinear_support_columns()

    assert kundur_map.get_n_rows() == 537
    assert kundur_map.get_n_columns() == 537
    assert kundur_map.get_state_row_count() == 220
    assert kundur_map.get_model_identity() == "kundur"
    assert kundur_map.get_schema() == "veragrid-emt-residual-row-map-v1"
    assert kundur_map.get_row_affinity().tolist() == expected_codes
    assert kundur_map.get_opaque_rows().tolist() == list(classification.get_opaque_row_indices())
    assert columns.tolist() == expected_columns
    assert bool(np.any(columns < 220)) and bool(np.any(columns >= 220))


@pytest.mark.parametrize("mismatch", ["state", "algebraic"])
def test_builder_rejects_misaligned_blocks(mismatch: str) -> None:
    """
    Misaligned state or algebraic blocks are rejected before classification.

    The state case moves the state variable to the algebraic list, so the total
    stays square; the algebraic case adds an algebraic variable without equation.

    :param mismatch: Which block is made misaligned.
    :return: None.
    """
    problem: EmtProblemTemplate = _synthetic_problem()
    if mismatch == "state":
        problem.get_algebraic_vars().append(problem.get_state_vars().pop())
    else:
        problem.get_algebraic_vars().append(Var("w"))
    with pytest.raises(ValueError):
        build_emt_residual_row_map(problem, "misaligned")


def test_arrays_are_immutable_int32_contiguous_after_build_and_read(kundur_map: EmtResidualRowMap, tmp_path: object) -> None:
    """
    Exported arrays are native int32, C-contiguous and read-only after build and after read.

    :param kundur_map: Kundur residual row map.
    :param tmp_path: Temporary directory.
    :return: None.
    """
    write_emt_residual_row_map(kundur_map, str(tmp_path))
    read_map: EmtResidualRowMap = read_emt_residual_row_map(str(tmp_path), "kundur")
    row_map: EmtResidualRowMap
    for row_map in (kundur_map, read_map):
        _assert_immutable_int32(row_map.get_row_affinity())
        _assert_immutable_int32(row_map.get_opaque_rows())
        _assert_immutable_int32(row_map.get_nonlinear_support_columns())


def _invariant_case_arguments(case: str) -> Dict[str, object]:
    """
    Return constructor arguments of a valid five-row map altered to break one invariant.

    :param case: Invariant case name.
    :return: Keyword arguments for EmtResidualRowMap.
    """
    arguments: Dict[str, object] = dict()
    arguments["model_identity"] = "case"
    arguments["n_rows"] = 5
    arguments["n_columns"] = 5
    arguments["state_row_count"] = 2
    arguments["row_affinity"] = np.array((2, 3, 2, 3, 0), dtype=np.int32)
    arguments["opaque_rows"] = np.array((1,), dtype=np.int32)
    arguments["nonlinear_support_columns"] = np.array((0, 3), dtype=np.int32)
    if case == "valid":
        pass
    elif case == "identity_empty":
        arguments["model_identity"] = ""
    elif case == "identity_too_long":
        arguments["model_identity"] = "a" * 257
    elif case == "identity_tab":
        arguments["model_identity"] = "a\tb"
    elif case == "identity_non_ascii":
        arguments["model_identity"] = "café"
    elif case == "identity_not_str":
        arguments["model_identity"] = 7
    elif case == "n_rows_bool":
        arguments["n_rows"] = True
    elif case == "n_rows_float":
        arguments["n_rows"] = 5.0
    elif case == "n_rows_negative":
        arguments["n_rows"] = -1
    elif case == "n_columns_not_square":
        arguments["n_columns"] = 6
    elif case == "state_row_count_negative":
        arguments["state_row_count"] = -1
    elif case == "state_row_count_above_rows":
        arguments["state_row_count"] = 6
    elif case == "array_not_numpy":
        arguments["opaque_rows"] = list((1,))
    elif case == "array_bool_dtype":
        arguments["opaque_rows"] = np.array((True,), dtype=np.bool_)
    elif case == "array_float_dtype":
        arguments["opaque_rows"] = np.array((1.0,), dtype=np.float64)
    elif case == "array_two_dimensional":
        arguments["opaque_rows"] = np.array(((1,),), dtype=np.int32)
    elif case == "array_outside_int32":
        arguments["nonlinear_support_columns"] = np.array((0, 2147483648), dtype=np.int64)
    elif case == "affinity_length":
        arguments["row_affinity"] = np.array((2, 3, 2, 3), dtype=np.int32)
    elif case == "affinity_code_above":
        arguments["row_affinity"] = np.array((2, 3, 2, 3, 4), dtype=np.int32)
    elif case == "affinity_code_negative":
        arguments["row_affinity"] = np.array((2, 3, 2, 3, -1), dtype=np.int32)
    elif case == "opaque_unsorted":
        arguments["opaque_rows"] = np.array((3, 1), dtype=np.int32)
    elif case == "opaque_duplicate":
        arguments["opaque_rows"] = np.array((1, 1), dtype=np.int32)
    elif case == "opaque_out_of_range":
        arguments["opaque_rows"] = np.array((5,), dtype=np.int32)
    elif case == "opaque_not_nonlinear":
        arguments["opaque_rows"] = np.array((0,), dtype=np.int32)
    elif case == "support_unsorted":
        arguments["nonlinear_support_columns"] = np.array((3, 0), dtype=np.int32)
    elif case == "support_negative":
        arguments["nonlinear_support_columns"] = np.array((-1, 3), dtype=np.int32)
    elif case == "support_out_of_range":
        arguments["nonlinear_support_columns"] = np.array((0, 5), dtype=np.int32)
    else:
        raise AssertionError("Unknown invariant case " + case)
    return arguments


@pytest.mark.parametrize("case", ["identity_empty", "identity_too_long", "identity_tab", "identity_non_ascii", "identity_not_str", "n_rows_bool",
                                  "n_rows_float", "n_rows_negative", "n_columns_not_square", "state_row_count_negative",
                                  "state_row_count_above_rows", "array_not_numpy", "array_bool_dtype", "array_float_dtype",
                                  "array_two_dimensional", "array_outside_int32", "affinity_length", "affinity_code_above",
                                  "affinity_code_negative", "opaque_unsorted", "opaque_duplicate", "opaque_out_of_range",
                                  "opaque_not_nonlinear", "support_unsorted", "support_negative", "support_out_of_range"])
def test_constructor_rejects_each_invariant(case: str) -> None:
    """
    The constructor accepts the valid base map and rejects each broken invariant with ValueError.

    :param case: Invariant case name.
    :return: None.
    """
    valid: EmtResidualRowMap = _construct_map(_invariant_case_arguments("valid"))
    assert valid.get_n_rows() == 5
    with pytest.raises(ValueError):
        _construct_map(_invariant_case_arguments(case))


def _construct_map(arguments: Dict[str, object]) -> EmtResidualRowMap:
    """
    Call the EmtResidualRowMap constructor with explicit keyword arguments.

    :param arguments: Constructor arguments by name.
    :return: Residual row map.
    """
    return EmtResidualRowMap(model_identity=arguments["model_identity"], n_rows=arguments["n_rows"], n_columns=arguments["n_columns"],
                             state_row_count=arguments["state_row_count"], row_affinity=arguments["row_affinity"],
                             opaque_rows=arguments["opaque_rows"], nonlinear_support_columns=arguments["nonlinear_support_columns"])


def _nested_list(depth: int) -> List[object]:
    """
    Build a list nested to the given depth (the outer list is depth 1).

    :param depth: Nesting depth.
    :return: Nested list.
    """
    nested: List[object] = list()
    level: int
    for level in range(depth - 1):
        nested = list((nested,))
    return nested


def test_canonical_json_golden_and_type_rejection() -> None:
    """
    Canonical JSON has sorted keys and compact separators, and rejects unsupported types and deep nesting.

    :return: None.
    """
    payload: Dict[str, object] = dict()
    payload["b"] = list((1, -2))
    payload["a"] = "xé"
    inner: Dict[str, object] = dict()
    inner["d"] = 0
    payload["c"] = inner

    assert canonical_json_bytes(payload) == b'{"a":"x\\u00e9","b":[1,-2],"c":{"d":0}}'
    assert canonical_json_bytes(_nested_list(8)) == b"[" * 8 + b"]" * 8
    rejected: object
    for rejected in (1.0, float("nan"), True, None, dict(((1, 2),)), _nested_list(9)):
        with pytest.raises(ValueError):
            canonical_json_bytes(rejected)


def test_synthetic_fingerprint_golden() -> None:
    """
    The synthetic three-row problem has a fixed map and fingerprint.

    :return: None.
    """
    row_map: EmtResidualRowMap = build_emt_residual_row_map(_synthetic_problem(), "synthetic-identity")

    assert row_map.get_row_affinity().tolist() == list((2, 2, 3))
    assert row_map.get_opaque_rows().tolist() == list()
    assert row_map.get_nonlinear_support_columns().tolist() == list((1, 2))
    assert row_map.get_layout_fingerprint() == "9d4f0d6668405fd4afccceef6aa807b23f3496d0dc74b4df94c32022ab495240"


def test_fingerprint_independent_of_uids_and_bound_to_identity(kundur_map: EmtResidualRowMap) -> None:
    """
    A fresh Kundur build (new random uids) keeps the fingerprint; another identity or model changes it.

    :param kundur_map: Kundur residual row map.
    :return: None.
    """
    fresh_problem: EmtProblemDae = _build_kundur_problem()[0]
    fresh: EmtResidualRowMap = build_emt_residual_row_map(fresh_problem, "kundur")
    other_identity: EmtResidualRowMap = build_emt_residual_row_map(fresh_problem, "kundur-other")
    built: EmtSimulationDriver = _build_emt_driver()
    two_bus_problem: EmtProblemDae = build_emt_problem(grid=built.grid, options=built.options, pf_results=None, pf_results_3ph=built.pf_results_3Ph)
    two_bus: EmtResidualRowMap = build_emt_residual_row_map(two_bus_problem, "kundur")

    assert fresh.get_layout_fingerprint() == kundur_map.get_layout_fingerprint()
    assert other_identity.get_layout_fingerprint() != kundur_map.get_layout_fingerprint()
    assert two_bus.get_n_rows() != kundur_map.get_n_rows()
    assert two_bus.get_layout_fingerprint() != kundur_map.get_layout_fingerprint()


def test_written_files_are_little_endian_and_manifest_canonical(kundur_map: EmtResidualRowMap, tmp_path: object) -> None:
    """
    Array files are raw little-endian int32 and the manifest is canonical with exact file entries.

    :param kundur_map: Kundur residual row map.
    :param tmp_path: Temporary directory.
    :return: None.
    """
    directory: str = str(tmp_path)
    manifest_path: str = write_emt_residual_row_map(kundur_map, directory)
    manifest_bytes: bytes
    handle: BinaryIO
    with open(manifest_path, "rb") as handle:
        manifest_bytes = handle.read()
    manifest: Dict[str, object] = json.loads(manifest_bytes.decode("utf-8"))

    assert canonical_json_bytes(manifest) == manifest_bytes
    assert manifest["encoding"] == "int32-little-endian"
    assert manifest["layout_fingerprint"] == kundur_map.get_layout_fingerprint()
    payload: Dict[str, object] = dict(manifest)
    payload.pop("manifest_payload_sha256")
    assert manifest["manifest_payload_sha256"] == hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    arrays: List[Tuple[str, npt.NDArray[np.int32]]] = list((("row_affinity.i32le", kundur_map.get_row_affinity()),
                                                            ("opaque_rows.i32le", kundur_map.get_opaque_rows()),
                                                            ("nonlinear_support_columns.i32le", kundur_map.get_nonlinear_support_columns())))
    file_name: str
    values: npt.NDArray[np.int32]
    for file_name, values in arrays:
        expected: bytearray = bytearray()
        value: int
        for value in values.tolist():
            expected.extend(struct.pack("<i", value))
        data: bytes
        handle: BinaryIO
        with open(os.path.join(directory, file_name), "rb") as handle:
            data = handle.read()
        assert data == bytes(expected)
        assert manifest["files"][file_name] == dict(byte_count=len(data), element_count=int(values.shape[0]), sha256=hashlib.sha256(data).hexdigest())


def test_round_trip(kundur_map: EmtResidualRowMap, tmp_path: object) -> None:
    """
    Write then read gives identical arrays and fingerprint, including bytes 0x1A and 0x0D 0x0A.

    :param kundur_map: Kundur residual row map.
    :param tmp_path: Temporary directory.
    :return: None.
    """
    awkward: EmtResidualRowMap = EmtResidualRowMap(model_identity="awkward bytes", n_rows=2574, n_columns=2574, state_row_count=0,
                                                   row_affinity=np.zeros(2574, dtype=np.int32), opaque_rows=np.zeros(0, dtype=np.int32),
                                                   nonlinear_support_columns=np.array((26, 2573), dtype=np.int32))
    row_map: EmtResidualRowMap
    for row_map in (kundur_map, awkward):
        directory: str = os.path.join(str(tmp_path), row_map.get_model_identity().replace(" ", "_"))
        write_emt_residual_row_map(row_map, directory)
        read_map: EmtResidualRowMap = read_emt_residual_row_map(directory, row_map.get_model_identity())

        assert read_map.get_layout_fingerprint() == row_map.get_layout_fingerprint()
        assert read_map.get_n_rows() == row_map.get_n_rows()
        assert read_map.get_state_row_count() == row_map.get_state_row_count()
        assert read_map.get_row_affinity().tobytes() == row_map.get_row_affinity().tobytes()
        assert read_map.get_opaque_rows().tobytes() == row_map.get_opaque_rows().tobytes()
        assert read_map.get_nonlinear_support_columns().tobytes() == row_map.get_nonlinear_support_columns().tobytes()
    support_bytes: bytes
    handle: BinaryIO
    with open(os.path.join(str(tmp_path), "awkward_bytes", "nonlinear_support_columns.i32le"), "rb") as handle:
        support_bytes = handle.read()
    assert support_bytes == b"\x1a\x00\x00\x00\x0d\x0a\x00\x00"


def _load_manifest(directory: str) -> Dict[str, object]:
    """
    Load the manifest of an artifact.

    :param directory: Artifact directory.
    :return: Parsed manifest.
    """
    handle: BinaryIO
    with open(os.path.join(directory, "manifest.json"), "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def _store_manifest_bytes(directory: str, data: bytes) -> None:
    """
    Replace the manifest bytes of an artifact.

    :param directory: Artifact directory.
    :param data: New manifest bytes.
    :return: None.
    """
    handle: BinaryIO
    with open(os.path.join(directory, "manifest.json"), "wb") as handle:
        handle.write(data)


def _store_manifest(directory: str, manifest: Dict[str, object], refresh_payload_hash: bool) -> None:
    """
    Write a manifest in canonical form, optionally refreshing its payload hash.

    :param directory: Artifact directory.
    :param manifest: Manifest to write.
    :param refresh_payload_hash: Recompute manifest_payload_sha256 so later checks are reached.
    :return: None.
    """
    if refresh_payload_hash:
        payload: Dict[str, object] = dict(manifest)
        payload.pop("manifest_payload_sha256", None)
        manifest["manifest_payload_sha256"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    else:
        pass
    _store_manifest_bytes(directory, canonical_json_bytes(manifest))


def _store_array_file(directory: str, file_name: str, data: bytes, manifest: Dict[str, object], element_count: int) -> None:
    """
    Replace an array file and its manifest entry consistently.

    :param directory: Artifact directory.
    :param file_name: Array file name.
    :param data: New file bytes.
    :param manifest: Manifest to update and store.
    :param element_count: Declared element count.
    :return: None.
    """
    handle: BinaryIO
    with open(os.path.join(directory, file_name), "wb") as handle:
        handle.write(data)
    manifest["files"][file_name] = dict(byte_count=len(data), element_count=element_count, sha256=hashlib.sha256(data).hexdigest())
    _store_manifest(directory, manifest, True)


def _create_symlink_or_skip(target: str, link: str, target_is_directory: bool) -> None:
    """
    Create a symbolic link, skipping the test when the OS refuses it.

    :param target: Link target.
    :param link: Link path.
    :param target_is_directory: Whether the target is a directory.
    :return: None.
    """
    try:
        os.symlink(target, link, target_is_directory=target_is_directory)
    except OSError:
        pytest.skip("The operating system refused to create a symbolic link")


def _prepare_failure_case(case: str, directory: str) -> Tuple[str, str, int, int]:
    """
    Tamper with a freshly written Kundur artifact to produce one failure class.

    :param case: Failure class name.
    :param directory: Directory holding the valid artifact.
    :return: Directory to read, expected identity, file limit and manifest limit.
    """
    read_directory: str = directory
    identity: str = "kundur"
    file_limit: int = 268435456
    manifest_limit: int = 1048576
    manifest: Dict[str, object] = _load_manifest(directory)
    manifest_bytes: bytes = canonical_json_bytes(manifest)
    affinity_name: str = "row_affinity.i32le"
    if case == "directory_is_file":
        read_directory = os.path.join(directory, "manifest.json")
    elif case == "missing_manifest":
        os.remove(os.path.join(directory, "manifest.json"))
    elif case == "missing_array_file":
        os.remove(os.path.join(directory, affinity_name))
    elif case == "array_file_is_directory":
        os.remove(os.path.join(directory, affinity_name))
        os.mkdir(os.path.join(directory, affinity_name))
    elif case == "symlinked_array_file":
        os.replace(os.path.join(directory, affinity_name), os.path.join(directory, "real.bin"))
        _create_symlink_or_skip(os.path.join(directory, "real.bin"), os.path.join(directory, affinity_name), False)
    elif case == "symlinked_directory":
        read_directory = directory + "_link"
        _create_symlink_or_skip(directory, read_directory, True)
    elif case == "junction_directory":
        if os.name != "nt":
            pytest.skip("Directory junctions exist only on Windows")
        else:
            read_directory = directory + "_junction"
            created: subprocess.CompletedProcess = subprocess.run(["cmd.exe", "/c", "mklink", "/J", read_directory, directory], capture_output=True)
            assert created.returncode == 0, created.stderr
    elif case == "manifest_over_limit":
        manifest_limit = len(manifest_bytes) - 1
    elif case == "array_file_over_limit":
        file_limit = 4
    elif case == "invalid_utf8":
        _store_manifest_bytes(directory, b"\xff" + manifest_bytes)
    elif case == "invalid_json":
        _store_manifest_bytes(directory, manifest_bytes[:-1])
    elif case == "nested_9_levels":
        manifest["semantics"] = _nested_list(8)
        _store_manifest_bytes(directory, json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    elif case == "nested_900_levels":
        manifest["semantics"] = _nested_list(899)
        _store_manifest_bytes(directory, json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    elif case == "nested_500000_levels":
        _store_manifest_bytes(directory, b'{"a":' + b"[" * 499999 + b"]" * 499999 + b"}")
    elif case == "non_canonical_whitespace":
        _store_manifest_bytes(directory, json.dumps(manifest, sort_keys=True, indent=1).encode("utf-8"))
    elif case == "crlf":
        _store_manifest_bytes(directory, manifest_bytes + b"\r\n")
    elif case == "duplicate_key":
        _store_manifest_bytes(directory, b'{"schema":"other",' + manifest_bytes[1:])
    elif case == "nan":
        _store_manifest_bytes(directory, manifest_bytes.replace(b'"n_rows":537', b'"n_rows":NaN'))
    elif case == "float_scalar":
        _store_manifest_bytes(directory, manifest_bytes.replace(b'"n_rows":537', b'"n_rows":537.0'))
    elif case == "bool_scalar":
        _store_manifest_bytes(directory, manifest_bytes.replace(b'"n_rows":537', b'"n_rows":true'))
    elif case == "top_level_array":
        _store_manifest_bytes(directory, b"[]")
    elif case == "extra_manifest_key":
        manifest["extra"] = 1
        _store_manifest(directory, manifest, True)
    elif case == "missing_manifest_key":
        manifest.pop("semantics")
        _store_manifest(directory, manifest, True)
    elif case == "files_as_list":
        manifest["files"] = list()
        _store_manifest(directory, manifest, True)
    elif case == "file_entry_not_object":
        manifest["files"][affinity_name] = 5
        _store_manifest(directory, manifest, True)
    elif case == "extra_file_entry":
        manifest["files"]["extra.i32le"] = dict(manifest["files"][affinity_name])
        _store_manifest(directory, manifest, True)
    elif case == "missing_file_entry":
        manifest["files"].pop(affinity_name)
        _store_manifest(directory, manifest, True)
    elif case == "extra_file_key":
        manifest["files"][affinity_name]["dtype"] = "i32le"
        _store_manifest(directory, manifest, True)
    elif case == "missing_file_key":
        manifest["files"][affinity_name].pop("sha256")
        _store_manifest(directory, manifest, True)
    elif case == "count_is_dict":
        manifest["files"][affinity_name]["element_count"] = dict()
        _store_manifest(directory, manifest, True)
    elif case == "count_is_str":
        manifest["files"][affinity_name]["byte_count"] = "2148"
        _store_manifest(directory, manifest, True)
    elif case == "count_is_negative":
        manifest["files"][affinity_name]["element_count"] = -537
        _store_manifest(directory, manifest, True)
    elif case == "malformed_sha256":
        manifest["files"][affinity_name]["sha256"] = manifest["files"][affinity_name]["sha256"].upper()
        _store_manifest(directory, manifest, True)
    elif case == "schema":
        manifest["schema"] = "veragrid-emt-residual-row-map-v2"
        _store_manifest(directory, manifest, True)
    elif case == "encoding":
        manifest["encoding"] = "int32-big-endian"
        _store_manifest(directory, manifest, True)
    elif case == "affinity_codes":
        manifest["affinity_codes"]["AFFINE"] = 5
        _store_manifest(directory, manifest, True)
    elif case == "semantics":
        manifest["semantics"] = "Affine rows stay affine forever."
        _store_manifest(directory, manifest, True)
    elif case == "byte_count":
        manifest["files"][affinity_name]["byte_count"] = 2144
        _store_manifest(directory, manifest, True)
    elif case == "element_count":
        manifest["files"][affinity_name]["element_count"] = 536
        _store_manifest(directory, manifest, True)
    elif case == "size_not_multiple_of_4":
        handle: BinaryIO
        with open(os.path.join(directory, affinity_name), "rb") as handle:
            extended: bytes = handle.read() + b"\x00"
        _store_array_file(directory, affinity_name, extended, manifest, 537)
    elif case == "file_sha256":
        handle: BinaryIO
        with open(os.path.join(directory, affinity_name), "r+b") as handle:
            handle.write(b"\x00")
    elif case == "manifest_payload_sha256":
        manifest["manifest_payload_sha256"] = "0" * 64
        _store_manifest(directory, manifest, False)
    elif case == "layout_fingerprint":
        manifest["layout_fingerprint"] = "0" * 64
        _store_manifest(directory, manifest, True)
    elif case == "structural_invariant":
        _store_array_file(directory, "opaque_rows.i32le", struct.pack("<ii", 5, 3), manifest, 2)
    elif case == "wrong_model_identity":
        identity = "another model"
    else:
        raise AssertionError("Unknown failure case " + case)
    return read_directory, identity, file_limit, manifest_limit


@pytest.mark.parametrize("case", ["directory_is_file", "missing_manifest", "missing_array_file", "array_file_is_directory", "symlinked_array_file",
                                  "symlinked_directory", "junction_directory", "manifest_over_limit", "array_file_over_limit", "invalid_utf8",
                                  "invalid_json", "nested_9_levels", "nested_900_levels", "nested_500000_levels", "non_canonical_whitespace",
                                  "crlf", "duplicate_key", "nan", "float_scalar", "bool_scalar", "top_level_array", "extra_manifest_key",
                                  "missing_manifest_key", "files_as_list", "file_entry_not_object", "extra_file_entry", "missing_file_entry",
                                  "extra_file_key", "missing_file_key", "count_is_dict", "count_is_str", "count_is_negative",
                                  "malformed_sha256", "schema", "encoding", "affinity_codes", "semantics", "byte_count", "element_count",
                                  "size_not_multiple_of_4", "file_sha256", "manifest_payload_sha256", "layout_fingerprint",
                                  "structural_invariant", "wrong_model_identity"])
def test_reader_rejects_each_failure_class(case: str, kundur_map: EmtResidualRowMap, tmp_path: object) -> None:
    """
    Every failure class makes the reader raise ValueError; the untouched artifact reads back.

    :param case: Failure class name.
    :param kundur_map: Kundur residual row map.
    :param tmp_path: Temporary directory.
    :return: None.
    """
    directory: str = os.path.join(str(tmp_path), "artifact")
    write_emt_residual_row_map(kundur_map, directory)
    assert read_emt_residual_row_map(directory, "kundur").get_layout_fingerprint() == kundur_map.get_layout_fingerprint()
    read_directory: str
    identity: str
    file_limit: int
    manifest_limit: int
    read_directory, identity, file_limit, manifest_limit = _prepare_failure_case(case, directory)
    try:
        raised: pytest.ExceptionInfo
        with pytest.raises(ValueError) as raised:
            read_emt_residual_row_map(read_directory, identity, maximum_file_bytes=file_limit, maximum_manifest_bytes=manifest_limit)
    finally:
        if (case == "junction_directory" or case == "symlinked_directory") and os.name == "nt":
            os.rmdir(read_directory)
        elif case == "symlinked_directory":
            os.unlink(read_directory)
        else:
            pass
    if case == "nested_9_levels" or case == "nested_900_levels":
        assert "deeper than 8" in str(raised.value)
    elif case == "junction_directory":
        assert "junction" in str(raised.value)
    elif case == "nested_500000_levels":
        assert "not valid UTF-8 JSON" in str(raised.value)
    else:
        pass


def test_semantic_note(kundur_map: EmtResidualRowMap, tmp_path: object) -> None:
    """
    The semantic note is returned by the getter, written to the manifest and contained in the class docstring.

    :param kundur_map: Kundur residual row map.
    :param tmp_path: Temporary directory.
    :return: None.
    """
    write_emt_residual_row_map(kundur_map, str(tmp_path))
    note: str = _semantic_note()

    assert kundur_map.get_semantics() == note
    assert _load_manifest(str(tmp_path))["semantics"] == note
    assert " ".join(note.split()) in " ".join(EmtResidualRowMap.__doc__.split())
