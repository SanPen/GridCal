# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import TextIO

from VeraGridEngine.enumerations import NativeCompilerFramework
from VeraGridEngine.IO.file_system import get_create_veragrid_folder
from VeraGridEngine.IO.native_compiler.compiler_interface import NativeCompilerSelection, NativeCompilerToolset
from VeraGridEngine.IO.native_compiler.local_llvm_interface import LocalLlvmCompilerHandler, resolve_local_llvm_toolset
from VeraGridEngine.IO.native_compiler.pygslv_interface import PygslvCompilerHandler
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.Utils.Compiler.interface import Compiler, CompilerInterface


def resolve_native_compiler(selection: NativeCompilerSelection | None = None, logger: Logger | None = None) -> Compiler | None:
    """Create the shared facade for a selected provider or the existing OS default.

    :param selection: Explicit provider, saved local LLVM choice, or the generic OS default.
    :param logger: Optional logger retaining selection/setup failures.
    :return: Caller-owned facade, or None when the selected provider is unavailable.
    """
    selected: NativeCompilerSelection | None = selection if selection is not None else load_saved_local_llvm_selection()
    shared_logger: Logger = logger if logger is not None else Logger()
    if selected is None:
        # With no explicit or valid saved choice, retain Santiago's OS compiler order.
        return Compiler(logger=shared_logger)
    else:
        pass
    handler: CompilerInterface
    try:
        if selected.framework == NativeCompilerFramework.LOCAL_LLVM:
            handler = LocalLlvmCompilerHandler(resolve_local_llvm_toolset(selected), shared_logger)
        elif selected.framework == NativeCompilerFramework.PYGSLV:
            if selected.binary_root is None and selected.support_root is None and selected.sdk_root is None:
                handler = PygslvCompilerHandler(shared_logger)
            else:
                shared_logger.add_error("pygslv is an in-process provider and does not accept executable roots")
                return None
        else:
            shared_logger.add_error("Unsupported native compiler provider")
            return None
    except (OSError, RuntimeError, ValueError) as error:
        shared_logger.add_error("Selected native compiler is unavailable: " + str(error))
        return None
    else:
        if handler.setup_valid:
            return Compiler(logger=shared_logger, compiler_handler=handler)
        else:
            return None


def resolve_native_compiler_toolset(selection: NativeCompilerSelection) -> NativeCompilerToolset:
    """Resolve exactly the selected provider without fallback.

    :param selection: Explicit provider selection.
    :return: Authenticated compiler toolset from that provider only.
    """

    # Keep selection validation at the stable entry point before resolving roots.
    if selection.framework == NativeCompilerFramework.LOCAL_LLVM:
        return resolve_local_llvm_toolset(selection)
    else:
        raise ValueError("Unsupported native compiler provider")


def load_saved_local_llvm_selection() -> NativeCompilerSelection | None:
    """Read the machine-local LLVM choice without importing a model or executing code.

    :return: Valid absolute LLVM roots, or None for a missing or invalid profile.
    """

    profile_path: Path = Path.home() / ".VeraGrid" / "native_compiler_selection.json"
    if profile_path.is_file() and not profile_path.is_symlink():
        pass
    else:
        return None
    try:
        # Accept one versioned shape so unrelated JSON cannot become a command.
        raw_profile: object = json.loads(profile_path.read_text(encoding="utf-8"))
        if isinstance(raw_profile, dict):
            profile: dict[str, object] = raw_profile
        else:
            return None
        expected_keys: set[str] = set((
            "schema_version", "framework", "binary_root", "support_root", "sdk_root",
        ))
        schema_value: object = profile["schema_version"] if "schema_version" in profile else None
        framework_value: object = profile["framework"] if "framework" in profile else None
        if (
            set(profile.keys()) == expected_keys
            and isinstance(schema_value, int)
            and not isinstance(schema_value, bool)
            and schema_value == 1
            and isinstance(framework_value, str)
            and framework_value == "LOCAL_LLVM"
        ):
            pass
        else:
            return None
        binary_text: object = profile["binary_root"]
        support_text: object = profile["support_root"]
        sdk_text: object = profile["sdk_root"]
        if isinstance(binary_text, str) and len(binary_text) > 0:
            binary_root: Path = Path(binary_text)
        else:
            return None
        if support_text is None:
            support_root: Path | None = None
        elif isinstance(support_text, str) and len(support_text) > 0:
            support_root = Path(support_text)
        else:
            return None
        if sdk_text is None:
            sdk_root: Path | None = None
        elif isinstance(sdk_text, str) and len(sdk_text) > 0:
            sdk_root = Path(sdk_text)
        else:
            return None
        if binary_root.is_absolute() and (support_root is None or support_root.is_absolute()) and (sdk_root is None or sdk_root.is_absolute()):
            selection: NativeCompilerSelection = NativeCompilerSelection(
                NativeCompilerFramework.LOCAL_LLVM, binary_root, support_root, sdk_root,
            )
            resolve_local_llvm_toolset(selection)
            return selection
        else:
            return None
    except (OSError, ValueError, TypeError, RuntimeError, json.JSONDecodeError):
        return None


def save_local_llvm_selection(selection: NativeCompilerSelection) -> None:
    """Atomically remember an explicitly chosen, authenticated LLVM installation.

    The caller must establish link or worker usability before calling this function.

    :param selection: Explicit LLVM roots selected by the user.
    :return: None.
    """

    if selection.framework == NativeCompilerFramework.LOCAL_LLVM:
        toolset: NativeCompilerToolset = resolve_local_llvm_toolset(selection)
    else:
        raise ValueError("Only an explicit LOCAL_LLVM selection can be remembered")
    profile_directory: Path = Path(get_create_veragrid_folder())
    profile_path: Path = profile_directory / "native_compiler_selection.json"
    profile: dict[str, object] = dict(
        schema_version=1,
        framework="LOCAL_LLVM",
        binary_root=str(toolset.binary_root),
        support_root=None if toolset.support_root is None else str(toolset.support_root),
        sdk_root=None if toolset.sdk_root is None else str(toolset.sdk_root),
    )
    # A temporary sibling keeps readers on the previous complete selection.
    file_descriptor: int
    temporary_name: str
    file_descriptor, temporary_name = tempfile.mkstemp(prefix="native_compiler_selection-", suffix=".tmp", dir=profile_directory)
    temporary_path: Path = Path(temporary_name)
    profile_stream: TextIO
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as profile_stream:
            profile_stream.write(json.dumps(profile, sort_keys=True, ensure_ascii=True) + "\n")
            profile_stream.flush()
            os.fsync(profile_stream.fileno())
        temporary_path.replace(profile_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
        else:
            pass
