# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

from VeraGridEngine.enumerations import IeeeCigreDllPlatform, NativeModelInterface
from VeraGridEngine.IO.manufacturer_native.binary_validation import (
    _inspect_native_binary,
    inspect_windows_pe_machine,
)
from VeraGridEngine.IO.manufacturer_native.inspection import (
    ManufacturerNativeInspectionResult,
    inspect_manufacturer_native,
)


def test_pe32_fixture_matches_only_windows_x86() -> None:
    """Accept the real PE32 fixture only for its declared x86 platform.

    :return: None.
    """
    fixture: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "manufacturer_native"
        / "windows_x86"
        / "fixture_normal_x86.dll"
    )
    data: bytes = fixture.read_bytes()

    assert inspect_windows_pe_machine(data) == 0x014c
    byte_size: int
    imports: tuple[str, ...]
    byte_size, imports = _inspect_native_binary(
        fixture,
        IeeeCigreDllPlatform.WINDOWS_X86,
        64 * 1024 * 1024,
    )
    assert byte_size == len(data)
    assert "kernel32.dll" in imports
    with pytest.raises(ValueError, match="machine does not match"):
        _inspect_native_binary(
            fixture,
            IeeeCigreDllPlatform.WINDOWS_X64,
            64 * 1024 * 1024,
        )


def test_pe_machine_reader_rejects_truncation_and_reports_tampering() -> None:
    """Reject an incomplete PE and expose a modified COFF machine exactly.

    :return: None.
    """
    fixture: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "manufacturer_native"
        / "windows_x86"
        / "fixture_normal_x86.dll"
    )
    data: bytes = fixture.read_bytes()
    pe_offset: int = struct.unpack_from("<I", data, 0x3c)[0]
    tampered: bytearray = bytearray(data)
    struct.pack_into("<H", tampered, pe_offset + 4, 0x8664)

    assert inspect_windows_pe_machine(bytes(tampered)) == 0x8664
    with pytest.raises(ValueError, match="not a PE image"):
        inspect_windows_pe_machine(data[:128])


def test_pe32_qualification_uses_packaged_worker() -> None:
    """Qualify a real PE32 provider through the reviewed packaged worker.

    :return: None.
    """
    if sys.platform != "win32" or struct.calcsize("P") != 8:
        pytest.skip("Windows x86 worker qualification requires a 64-bit Windows host")

    fixture: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "manufacturer_native"
        / "windows_x86"
        / "fixture_qualified_x86.dll"
    )

    result: ManufacturerNativeInspectionResult = inspect_manufacturer_native(
        source_path=fixture,
        platform=IeeeCigreDllPlatform.WINDOWS_X86,
        native_interface=NativeModelInterface.IEEE_CIGRE_V1_1,
        vendor_declares_no_late_loading=True,
        vendor_declares_instance_isolation=True,
    )

    assert result.platform == IeeeCigreDllPlatform.WINDOWS_X86
    assert result.binary_size == fixture.stat().st_size
    assert result.model_info.native_interface == NativeModelInterface.IEEE_CIGRE_V1_1
    assert result.model_info.model_name == "GoldenModel"
