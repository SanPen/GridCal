# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Tuple

from VeraGridEngine.IO.native_compiler.compiler_interface import NativeCompilerSelection, NativeCompilerToolset
from VeraGridEngine.IO.native_compiler.selected_interface import (
    load_saved_local_llvm_selection,
    resolve_native_compiler_toolset,
)


def build_fixture(toolset: NativeCompilerToolset,
                  source: Path,
                  output: Path,
                  definitions: Tuple[str, ...]) -> Tuple[str, ...]:
    """Compile one pinned PE32 fixture mode.

    :param toolset: Authenticated local LLVM compiler, linker and support roots.
    :param source: Shared fixture source.
    :param output: Destination DLL.
    :param definitions: Exact ordered compile-time mode definitions.
    :return: Exact ordered arguments.
    """
    arguments: list[str] = list((
        *toolset.compiler_prefix_arguments,
        "--target=i686-w64-windows-gnu", "-std=c11", "-O2", "-shared", "-Wall", "-Wextra",
        "-Werror", "-Wno-unused-command-line-argument", "-fno-ident",
        "-Wl,--no-insert-timestamp", "-Wl,--nxcompat", "-Wl,--dynamicbase",
    ))
    definition: str
    for definition in definitions:
        arguments.append("-D" + definition + "=1")
    arguments.extend(("-o", output.name, source.name))
    # Recheck the selected tools around each build so provenance remains exact.
    toolset.assert_unchanged()
    subprocess.run([str(toolset.compiler_path), *arguments], check=True, cwd=str(source.parent))
    toolset.assert_unchanged()
    suffix: str
    for suffix in (".lib", ".exp"):
        auxiliary: Path = output.with_suffix(suffix)
        if auxiliary.exists():
            auxiliary.unlink()
        else:
            pass
    return tuple(arguments)


def main() -> None:
    """Build every fixture twice and publish only byte-identical PE32 results.

    :return: None.
    """
    root: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "manufacturer_native"
        / "windows_x86"
    )
    source: Path = root / "fixture.c"
    selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
    if selection is None:
        raise RuntimeError("Configure an external LLVM installation before building PE32 fixtures")
    else:
        toolset: NativeCompilerToolset = resolve_native_compiler_toolset(selection)
    normal: Path = root / "fixture_normal_x86.dll"
    null_model: Path = root / "fixture_null_get_info_x86.dll"
    qualified: Path = root / "fixture_qualified_x86.dll"

    # The protocol fixture preserves distinct nonzero ABI codes for the golden
    # lifecycle, while the two companion modes isolate their one intended case.
    normal_arguments: Tuple[str, ...] = build_fixture(toolset, source, normal, tuple())
    normal_bytes: bytes = normal.read_bytes()
    normal.unlink()
    if normal_arguments != build_fixture(toolset, source, normal, tuple()) or normal.read_bytes() != normal_bytes:
        raise RuntimeError("NORMAL PE32 fixture build is not reproducible")
    else:
        pass

    null_definitions: Tuple[str, ...] = ("NULL_GET_INFO",)
    null_arguments: Tuple[str, ...] = build_fixture(
        toolset, source, null_model, null_definitions,
    )
    null_bytes: bytes = null_model.read_bytes()
    null_model.unlink()
    if (
            null_arguments != build_fixture(toolset, source, null_model, null_definitions)
            or null_model.read_bytes() != null_bytes
    ):
        raise RuntimeError("NULL_GET_INFO PE32 fixture build is not reproducible")
    else:
        pass

    qualified_definitions: Tuple[str, ...] = ("QUALIFIED",)
    qualified_arguments: Tuple[str, ...] = build_fixture(
        toolset, source, qualified, qualified_definitions,
    )
    qualified_bytes: bytes = qualified.read_bytes()
    qualified.unlink()
    if (
            qualified_arguments != build_fixture(toolset, source, qualified, qualified_definitions)
            or qualified.read_bytes() != qualified_bytes
    ):
        raise RuntimeError("QUALIFIED PE32 fixture build is not reproducible")
    else:
        pass


if __name__ == "__main__":
    main()
