# SPDX-License-Identifier: MPL-2.0
"""Standalone MON reader; grammar and typed objects live in versioned/."""
from pathlib import Path

from VeraGridEngine.IO.raw.psse_auxiliary import (
    AuxiliaryFormat, BusInputMode, PsseAuxiliaryFile, PsseVersion,
    parse_command_file, read_auxiliary_text,
)
from VeraGridEngine.IO.raw.versioned.base.mon import RawMon
from VeraGridEngine.IO.raw.versioned.v33.mon import RawMonV33
from VeraGridEngine.IO.raw.versioned.v34.mon import RawMonV34
from VeraGridEngine.IO.raw.versioned.v35.mon import RawMonV35
from VeraGridEngine.IO.raw.versioned.v36.mon import RawMonV36


def parse_mon(text: str, source: str = '<mon>',
                bus_mode: BusInputMode = BusInputMode.NUMBERS,
                version: int | PsseVersion = PsseVersion.V36) -> RawMon:
    """Tokenize once and dispatch to the explicitly selected version grammar.

    :param text: Complete MON input.
    :param source: Diagnostic source label.
    :param bus_mode: Initial bus reference mode.
    :param version: PSS/E major version, 33 through 36.
    :return: Concrete version object, retaining syntax and typed definitions.
    """
    syntax: PsseAuxiliaryFile = parse_command_file(text, AuxiliaryFormat.MON, source, bus_mode, version)
    result: RawMon
    if syntax.version == PsseVersion.V33:
        result = RawMonV33(source, bus_mode)
    elif syntax.version == PsseVersion.V34:
        result = RawMonV34(source, bus_mode)
    elif syntax.version == PsseVersion.V35:
        result = RawMonV35(source, bus_mode)
    elif syntax.version == PsseVersion.V36:
        result = RawMonV36(source, bus_mode)
    else:
        result = RawMon(source, bus_mode, version)
    if syntax.version is not None:
        result.parse(syntax)
    else:
        result.logger = syntax.logger
    return result


def read_mon(file_name: str | Path, bus_mode: BusInputMode = BusInputMode.NUMBERS,
               version: int | PsseVersion = PsseVersion.V36) -> RawMon:
    """Read an encoded auxiliary file without changing any network objects.

    :param file_name: Input path.
    :param bus_mode: Initial bus reference mode.
    :param version: PSS/E major version, 33 through 36.
    :return: Version-specific typed MON data and diagnostics.
    """
    text: str = read_auxiliary_text(file_name)
    return parse_mon(text, source=str(file_name), bus_mode=bus_mode, version=version)
