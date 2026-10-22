# SPDX-License-Identifier: MPL-2.0
"""Shared legacy SUB grammar. The local 34.1 DataFormats manual has no SUB chapter; label expansion is not asserted."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, BusInputMode
from VeraGridEngine.IO.raw.versioned.v33.sub import RawSubV33


class RawSubV34(RawSubV33):
    """PSS/E 34 SUB data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<sub>', bus_mode: BusInputMode = BusInputMode.NUMBERS) -> None:
        """Select the documented PSS/E 34 grammar.

        :param source: Diagnostic source label.
        :param bus_mode: Initial identifier interpretation.
        """
        super().__init__(source, bus_mode)
        self.version = PsseVersion.V34
        self.label_limit = None
