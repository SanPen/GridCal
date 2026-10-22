# SPDX-License-Identifier: MPL-2.0
"""Standalone ROP reader; versioned objects retain data and diagnostics."""
from pathlib import Path
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, read_auxiliary_text
from VeraGridEngine.IO.raw.versioned.base.rop import RawRop
from VeraGridEngine.IO.raw.versioned.v33.rop import RawRopV33
from VeraGridEngine.IO.raw.versioned.v34.rop import RawRopV34
from VeraGridEngine.IO.raw.versioned.v35.rop import RawRopV35
from VeraGridEngine.IO.raw.versioned.v36.rop import RawRopV36


def parse_rop(text: str, source: str = '<rop>',
                version: int | PsseVersion = PsseVersion.V36) -> RawRop:
    """Parse without modifying the working circuit.

    :param text: Complete file contents.
    :param source: Diagnostic source label.
    :param version: Explicit PSS/E major version, 33 through 36.
    :return: Version-owned parsed data, including rejected records.
    """
    result: RawRop
    if version == PsseVersion.V33 or version == 33:
        result = RawRopV33(source)
    elif version == PsseVersion.V34 or version == 34:
        result = RawRopV34(source)
    elif version == PsseVersion.V35 or version == 35:
        result = RawRopV35(source)
    elif version == PsseVersion.V36 or version == 36:
        result = RawRopV36(source)
    else:
        result = RawRop(source, version)
    result.parse(text)
    return result


def read_rop(file_name: str | Path,
               version: int | PsseVersion = PsseVersion.V36) -> RawRop:
    """Read an encoded file and dispatch its selected version grammar.

    :param file_name: Input path.
    :param version: Explicit PSS/E major version.
    :return: Typed data with original source locations.
    """
    text: str = read_auxiliary_text(file_name)
    return parse_rop(text, str(file_name), version)
