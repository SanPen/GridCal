from pathlib import Path

import pytest

from VeraGridEngine.enumerations import NativeCompilerFramework
from VeraGridEngine.IO.native_compiler.compiler_interface import NativeCompilerSelection, NativeCompilerToolset
from VeraGridEngine.IO.native_compiler.selected_interface import (
    load_saved_local_llvm_selection,
    resolve_native_compiler_toolset,
)


def _local_selection() -> NativeCompilerSelection:
    """Use a configured external LLVM installation for integration tests.

    :return: LOCAL_LLVM selection or a skip if none was configured.
    """

    selection: NativeCompilerSelection | None = load_saved_local_llvm_selection()
    if selection is None:
        pytest.skip("No external LLVM installation is configured")
    else:
        return selection


def test_local_llvm_requires_absolute_binary_root() -> None:
    """Reject a local provider selection whose binary root is relative."""

    selection: NativeCompilerSelection = NativeCompilerSelection(
        framework=NativeCompilerFramework.LOCAL_LLVM,
        binary_root=Path("llvm-bin"),
    )
    with pytest.raises(ValueError, match="absolute"):
        resolve_native_compiler_toolset(selection)


def test_local_llvm_rejects_incomplete_tool_root(tmp_path: Path) -> None:
    """Reject an explicit root that does not contain the complete toolset."""

    selection: NativeCompilerSelection = NativeCompilerSelection(
        framework=NativeCompilerFramework.LOCAL_LLVM,
        binary_root=tmp_path,
    )
    with pytest.raises(FileNotFoundError, match="required native compiler tool"):
        resolve_native_compiler_toolset(selection)


def test_explicit_provider_failure_does_not_fallback(tmp_path: Path) -> None:
    """Keep a failed LOCAL_LLVM selection from falling back to another provider."""

    selection: NativeCompilerSelection = NativeCompilerSelection(
        framework=NativeCompilerFramework.LOCAL_LLVM,
        binary_root=tmp_path,
    )
    with pytest.raises(FileNotFoundError):
        resolve_native_compiler_toolset(selection)


def test_local_llvm_resolves_explicit_toolset() -> None:
    """Resolve and authenticate an explicitly rooted local LLVM toolset."""

    toolset: NativeCompilerToolset = resolve_native_compiler_toolset(_local_selection())
    assert toolset.framework == NativeCompilerFramework.LOCAL_LLVM
    assert toolset.compiler_path.is_file()
    assert len(toolset.tool_hashes) == 2
    toolset.assert_unchanged()
