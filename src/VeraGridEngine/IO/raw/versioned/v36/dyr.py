# SPDX-License-Identifier: MPL-2.0
"""Retain the supported DYR schemas. Unknown or changed model layouts remain unsupported rather than being inferred."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion
from VeraGridEngine.IO.raw.versioned.v35.dyr import RawDyrV35


class RawDyrV36(RawDyrV35):
    """PSS/E 36 DYR data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<dyr>') -> None:
        """Select the documented PSS/E 36 grammar.

        :param source: Diagnostic source label.
        """
        super().__init__(source)
        self.version = PsseVersion.V36
