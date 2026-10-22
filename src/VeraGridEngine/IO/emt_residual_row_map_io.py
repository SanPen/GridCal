# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
File artifact of the EMT residual row map.

The artifact is a directory with raw little-endian int32 files
(``row_affinity.i32le``, ``opaque_rows.i32le``,
``nonlinear_support_columns.i32le``) and a canonical ``manifest.json`` written
last. The reader fails closed with ``ValueError`` on any integrity, structure,
limit or identity mismatch and only opens the fixed file names.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from typing import BinaryIO, Dict, List, Set, Tuple

import numpy as np
import numpy.typing as npt

from VeraGridEngine.enumerations import ResidualRowAffinityCode
from VeraGridEngine.Simulations.EMT.problems.emt_residual_row_classification import EmtResidualRowMap
from VeraGridEngine.Utils.canonical_json import canonical_json_bytes


def _affinity_code_table() -> Dict[str, int]:
    """
    Return the affinity code table written to and expected in the manifest.

    :return: Code name to integer code.
    """
    table: Dict[str, int] = dict()
    code: ResidualRowAffinityCode
    for code in ResidualRowAffinityCode:
        table[code.name] = int(code)
    return table


def _write_file_atomically(path: str, data: bytes) -> None:
    """
    Write bytes through a temporary file replaced into place.

    :param path: Destination path.
    :param data: Bytes to write.
    """
    temporary_path: str = path + ".tmp"
    handle: BinaryIO
    with open(temporary_path, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary_path, path)


def _read_bounded_regular_file(path: str, limit: int) -> bytes:
    """
    Read a regular, non-link file of at most ``limit`` bytes.

    The file is checked with ``os.lstat``, opened in binary mode, its descriptor
    compared with the ``lstat`` result and read with at most ``st_size + 1``
    bytes (never more than ``limit + 1``), so a file that grew is detected
    without allocating a buffer of the full limit.

    :param path: File path.
    :param limit: Maximum accepted size in bytes.
    :return: File contents.
    :raises ValueError: When the file is missing, a link, not a regular file,
        too large, replaced between checks, or cannot be read.
    """
    try:
        link_status: os.stat_result = os.lstat(path)
    except OSError as error:
        raise ValueError("Cannot inspect " + os.path.basename(path)) from error

    if stat.S_ISLNK(link_status.st_mode):
        raise ValueError(os.path.basename(path) + " is a symbolic link")
    elif not stat.S_ISREG(link_status.st_mode):
        raise ValueError(os.path.basename(path) + " is not a regular file")
    elif link_status.st_size > limit:
        raise ValueError(os.path.basename(path) + " exceeds its size limit")
    else:
        pass

    try:
        handle: BinaryIO
        with open(path, "rb") as handle:
            open_status: os.stat_result = os.fstat(handle.fileno())
            data: bytes = handle.read(link_status.st_size + 1)
    except OSError as error:
        raise ValueError("Cannot read " + os.path.basename(path)) from error

    if open_status.st_size != link_status.st_size:
        raise ValueError(os.path.basename(path) + " changed while it was opened")
    elif link_status.st_ino != 0 and (open_status.st_ino != link_status.st_ino or open_status.st_dev != link_status.st_dev):
        raise ValueError(os.path.basename(path) + " was replaced while it was opened")
    elif len(data) > limit:
        raise ValueError(os.path.basename(path) + " exceeds its size limit")
    elif len(data) != link_status.st_size:
        raise ValueError(os.path.basename(path) + " changed while it was read")
    else:
        return data


def _require_count(value: object, name: str) -> int:
    """
    Check that a manifest count is an int (not bool) and non-negative.

    :param value: Parsed manifest value.
    :param name: Field name used in error messages.
    :return: The count.
    :raises ValueError: When the value is not a non-negative int.
    """
    if type(value) is not int or value < 0:
        raise ValueError(name + " must be a non-negative int")
    else:
        return value


def _require_key_set(container: object, expected: Set[str], name: str) -> Dict[str, object]:
    """
    Check that a parsed manifest container is a dict with exactly the expected keys.

    :param container: Parsed manifest value.
    :param expected: Expected key set.
    :param name: Container name used in error messages.
    :return: The container.
    :raises ValueError: When the value is not a dict or its keys differ.
    """
    if type(container) is not dict:
        raise ValueError(name + " must be a JSON object")
    elif set(container.keys()) != expected:
        raise ValueError(name + " keys differ from the expected set")
    else:
        return container


def write_emt_residual_row_map(row_map: EmtResidualRowMap, directory: str) -> str:
    """
    Write a residual row map as little-endian int32 files and a canonical manifest.

    :param row_map: Residual row map to write.
    :param directory: Destination directory, created when missing.
    :return: Path of the written manifest.json.
    """
    os.makedirs(directory, exist_ok=True)
    arrays: List[Tuple[str, npt.NDArray[np.int32]]] = list()
    arrays.append(("row_affinity.i32le", row_map.get_row_affinity()))
    arrays.append(("opaque_rows.i32le", row_map.get_opaque_rows()))
    arrays.append(("nonlinear_support_columns.i32le", row_map.get_nonlinear_support_columns()))

    # Array files first, each replaced into place.
    files: Dict[str, Dict[str, object]] = dict()
    file_name: str
    values: npt.NDArray[np.int32]
    for file_name, values in arrays:
        data: bytes = values.astype("<i4").tobytes()
        _write_file_atomically(os.path.join(directory, file_name), data)
        entry: Dict[str, object] = dict()
        entry["byte_count"] = len(data)
        entry["element_count"] = int(values.shape[0])
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        files[file_name] = entry

    # Canonical manifest last, carrying the hash of its own payload.
    manifest: Dict[str, object] = dict()
    manifest["schema"] = row_map.get_schema()
    manifest["model_identity"] = row_map.get_model_identity()
    manifest["n_rows"] = row_map.get_n_rows()
    manifest["n_columns"] = row_map.get_n_columns()
    manifest["state_row_count"] = row_map.get_state_row_count()
    manifest["affinity_codes"] = _affinity_code_table()
    manifest["encoding"] = "int32-little-endian"
    manifest["layout_fingerprint"] = row_map.get_layout_fingerprint()
    manifest["semantics"] = row_map.get_semantics()
    manifest["files"] = files
    manifest["manifest_payload_sha256"] = hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()

    manifest_path: str = os.path.join(directory, "manifest.json")
    _write_file_atomically(manifest_path, canonical_json_bytes(manifest))
    return manifest_path


def read_emt_residual_row_map(directory: str,
                              expected_model_identity: str,
                              maximum_file_bytes: int = 268435456,
                              maximum_manifest_bytes: int = 1048576) -> EmtResidualRowMap:
    """
    Read and validate a residual row map artifact.

    :param directory: Artifact directory.
    :param expected_model_identity: Model identity the map must be bound to.
    :param maximum_file_bytes: Maximum size of each array file.
    :param maximum_manifest_bytes: Maximum size of manifest.json.
    :return: Validated residual row map with native int32 arrays.
    :raises ValueError: On any integrity, structure, limit or identity mismatch.
    """
    file_names: Tuple[str, str, str] = ("row_affinity.i32le", "opaque_rows.i32le", "nonlinear_support_columns.i32le")
    manifest_keys: Set[str] = set(("schema", "model_identity", "n_rows", "n_columns", "state_row_count", "affinity_codes", "encoding",
                                   "layout_fingerprint", "semantics", "files", "manifest_payload_sha256"))
    entry_keys: Set[str] = set(("byte_count", "element_count", "sha256"))
    hex_digits: str = "0123456789abcdef"

    # Directory: a real directory, neither a symbolic link nor a junction.
    try:
        directory_status: os.stat_result = os.lstat(directory)
    except OSError as error:
        raise ValueError("Cannot inspect the artifact directory") from error
    if stat.S_ISLNK(directory_status.st_mode):
        raise ValueError("The artifact directory is a symbolic link")
    elif not stat.S_ISDIR(directory_status.st_mode):
        raise ValueError("The artifact path is not a directory")
    elif os.name == "nt" and directory_status.st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT:
        raise ValueError("The artifact directory is a junction")
    else:
        pass

    # Manifest: bounded read, strict JSON, canonical bytes, fixed key sets.
    manifest_bytes: bytes = _read_bounded_regular_file(os.path.join(directory, "manifest.json"), maximum_manifest_bytes)
    try:
        parsed: object = json.loads(manifest_bytes.decode("utf-8"))
    except (ValueError, RecursionError) as error:
        raise ValueError("manifest.json is not valid UTF-8 JSON") from error
    manifest: Dict[str, object] = _require_key_set(parsed, manifest_keys, "manifest")
    if canonical_json_bytes(manifest) != manifest_bytes:
        raise ValueError("manifest.json is not in canonical form")
    else:
        pass

    n_rows: int = _require_count(manifest["n_rows"], "n_rows")
    n_columns: int = _require_count(manifest["n_columns"], "n_columns")
    state_row_count: int = _require_count(manifest["state_row_count"], "state_row_count")
    files: Dict[str, object] = _require_key_set(manifest["files"], set(file_names), "files")
    if manifest["encoding"] != "int32-little-endian":
        raise ValueError("Unsupported encoding")
    elif manifest["affinity_codes"] != _affinity_code_table():
        raise ValueError("The affinity code table differs")
    else:
        pass

    payload: Dict[str, object] = dict(manifest)
    payload.pop("manifest_payload_sha256")
    if manifest["manifest_payload_sha256"] != hashlib.sha256(canonical_json_bytes(payload)).hexdigest():
        raise ValueError("manifest_payload_sha256 differs")
    else:
        pass

    # Array files: fixed names, declared sizes and hashes, little-endian decoding.
    decoded: Dict[str, npt.NDArray[np.int32]] = dict()
    file_name: str
    for file_name in file_names:
        entry: Dict[str, object] = _require_key_set(files[file_name], entry_keys, file_name)
        byte_count: int = _require_count(entry["byte_count"], file_name + " byte_count")
        element_count: int = _require_count(entry["element_count"], file_name + " element_count")
        digest: object = entry["sha256"]
        if type(digest) is not str or len(digest) != 64 or not set(digest).issubset(set(hex_digits)):
            raise ValueError(file_name + " sha256 must be 64 lowercase hex characters")
        else:
            pass
        data: bytes = _read_bounded_regular_file(os.path.join(directory, file_name), maximum_file_bytes)
        if len(data) != byte_count or len(data) != 4 * element_count:
            raise ValueError(file_name + " size differs from the manifest")
        elif hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(file_name + " sha256 differs")
        else:
            decoded[file_name] = np.frombuffer(data, dtype="<i4").astype(np.int32)

    # Structural invariants, then semantics, fingerprint and identity.
    row_map: EmtResidualRowMap = EmtResidualRowMap(
        model_identity=manifest["model_identity"],
        n_rows=n_rows,
        n_columns=n_columns,
        state_row_count=state_row_count,
        row_affinity=decoded["row_affinity.i32le"],
        opaque_rows=decoded["opaque_rows.i32le"],
        nonlinear_support_columns=decoded["nonlinear_support_columns.i32le"],
    )
    if manifest["schema"] != row_map.get_schema():
        raise ValueError("Unsupported schema")
    elif manifest["semantics"] != row_map.get_semantics():
        raise ValueError("The semantic note differs")
    elif manifest["layout_fingerprint"] != row_map.get_layout_fingerprint():
        raise ValueError("layout_fingerprint differs")
    elif row_map.get_model_identity() != expected_model_identity:
        raise ValueError("model_identity differs from the expected identity")
    else:
        return row_map
