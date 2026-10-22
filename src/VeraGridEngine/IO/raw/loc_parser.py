# SPDX-License-Identifier: MPL-2.0
"""Standalone LOC reader; versioned objects retain data and diagnostics."""
from pathlib import Path
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, read_auxiliary_text
from VeraGridEngine.IO.raw.versioned.base.loc import RawLoc
from VeraGridEngine.IO.raw.versioned.v33.loc import RawLocV33
from VeraGridEngine.IO.raw.versioned.v34.loc import RawLocV34
from VeraGridEngine.IO.raw.versioned.v35.loc import RawLocV35
from VeraGridEngine.IO.raw.versioned.v36.loc import RawLocV36


def parse_loc(text: str, source: str = '<loc>',
                version: int | PsseVersion = PsseVersion.V36) -> RawLoc:
    """Parse without modifying the working circuit.

    :param text: Complete file contents.
    :param source: Diagnostic source label.
    :param version: Explicit PSS/E major version, 33 through 36.
    :return: Version-owned parsed data, including rejected records.
    """
    result: RawLoc
    if version == PsseVersion.V33 or version == 33:
        result = RawLocV33(source)
    elif version == PsseVersion.V34 or version == 34:
        result = RawLocV34(source)
    elif version == PsseVersion.V35 or version == 35:
        result = RawLocV35(source)
    elif version == PsseVersion.V36 or version == 36:
        result = RawLocV36(source)
    else:
        result = RawLoc(source, version)
    result.parse(text)
    return result


def read_loc(file_name: str | Path,
               version: int | PsseVersion = PsseVersion.V36) -> RawLoc:
    """Read an encoded file and dispatch its selected version grammar.

    :param file_name: Input path.
    :param version: Explicit PSS/E major version.
    :return: Typed data with original source locations.
    """
    text: str = read_auxiliary_text(file_name)
    return parse_loc(text, str(file_name), version)
