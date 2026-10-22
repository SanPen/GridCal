# SPDX-License-Identifier: MPL-2.0
"""Standalone GCP reader; versioned objects retain data and diagnostics."""
from pathlib import Path
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, read_auxiliary_text
from VeraGridEngine.IO.raw.versioned.base.gcp import RawGcp
from VeraGridEngine.IO.raw.versioned.v33.gcp import RawGcpV33
from VeraGridEngine.IO.raw.versioned.v34.gcp import RawGcpV34
from VeraGridEngine.IO.raw.versioned.v35.gcp import RawGcpV35
from VeraGridEngine.IO.raw.versioned.v36.gcp import RawGcpV36


def parse_gcp(text: str, source: str = '<gcp>',
                version: int | PsseVersion = PsseVersion.V36) -> RawGcp:
    """Parse without modifying the working circuit.

    :param text: Complete file contents.
    :param source: Diagnostic source label.
    :param version: Explicit PSS/E major version, 33 through 36.
    :return: Version-owned parsed data, including rejected records.
    """
    result: RawGcp
    if version == PsseVersion.V33 or version == 33:
        result = RawGcpV33(source)
    elif version == PsseVersion.V34 or version == 34:
        result = RawGcpV34(source)
    elif version == PsseVersion.V35 or version == 35:
        result = RawGcpV35(source)
    elif version == PsseVersion.V36 or version == 36:
        result = RawGcpV36(source)
    else:
        result = RawGcp(source, version)
    result.parse(text)
    return result


def read_gcp(file_name: str | Path,
               version: int | PsseVersion = PsseVersion.V36) -> RawGcp:
    """Read an encoded file and dispatch its selected version grammar.

    :param file_name: Input path.
    :param version: Explicit PSS/E major version.
    :return: Typed data with original source locations.
    """
    text: str = read_auxiliary_text(file_name)
    return parse_gcp(text, str(file_name), version)
