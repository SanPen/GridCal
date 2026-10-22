# SPDX-License-Identifier: MPL-2.0
"""Standalone SEQ reader; versioned objects retain data and diagnostics."""
from pathlib import Path
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, read_auxiliary_text
from VeraGridEngine.IO.raw.versioned.base.seq import RawSeq, Sequence35Layout
from VeraGridEngine.IO.raw.versioned.v33.seq import RawSeqV33
from VeraGridEngine.IO.raw.versioned.v34.seq import RawSeqV34
from VeraGridEngine.IO.raw.versioned.v35.seq import RawSeqV35
from VeraGridEngine.IO.raw.versioned.v36.seq import RawSeqV36


def parse_seq(text: str, source: str = '<seq>',
                version: int | PsseVersion = PsseVersion.V36,
                layout_35: Sequence35Layout = Sequence35Layout.V35_2) -> RawSeq:
    """Parse without modifying the working circuit.

    :param text: Complete file contents.
    :param source: Diagnostic source label.
    :param version: Explicit PSS/E major version, 33 through 36.
    :param layout_35: Explicit 35.0/35.1 or 35.2 NCS layout; applies to version 35.
    :return: Version-owned parsed data, including rejected records.
    """
    result: RawSeq
    if version == PsseVersion.V33 or version == 33:
        result = RawSeqV33(source)
    elif version == PsseVersion.V34 or version == 34:
        result = RawSeqV34(source)
    elif version == PsseVersion.V35 or version == 35:
        result = RawSeqV35(source, layout_35)
    elif version == PsseVersion.V36 or version == 36:
        result = RawSeqV36(source)
    else:
        result = RawSeq(source, version)
    result.parse(text)
    return result


def read_seq(file_name: str | Path,
               version: int | PsseVersion = PsseVersion.V36,
               layout_35: Sequence35Layout = Sequence35Layout.V35_2) -> RawSeq:
    """Read an encoded file and dispatch its selected version grammar.

    :param file_name: Input path.
    :param version: Explicit PSS/E major version.
    :param layout_35: Explicit minor-release layout for version 35.
    :return: Typed data with original source locations.
    """
    text: str = read_auxiliary_text(file_name)
    return parse_seq(text, str(file_name), version, layout_35)
