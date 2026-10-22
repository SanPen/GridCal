# SPDX-License-Identifier: MPL-2.0
"""DataFormats 36.5 section 12.4 retains the documented 35.2 event shapes."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, BusInputMode
from VeraGridEngine.IO.raw.versioned.v35.con_ import RawConV35


class RawConV36(RawConV35):
    """PSS/E 36 CON data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<con>', bus_mode: BusInputMode = BusInputMode.NUMBERS) -> None:
        """Select the documented PSS/E 36 grammar.

        :param source: Diagnostic source label.
        :param bus_mode: Initial identifier interpretation.
        """
        super().__init__(source, bus_mode)
        self.version = PsseVersion.V36
