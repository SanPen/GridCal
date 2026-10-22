# SPDX-License-Identifier: MPL-2.0
"""CheatSheets 35.2 section 1.2: 32-character labels. ReleaseNotes 35.2 page 11 adds bus mode directives."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, BusInputMode
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport
from VeraGridEngine.IO.raw.versioned.v34.sub import RawSubV34


class RawSubV35(RawSubV34):
    """PSS/E 35 SUB data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<sub>', bus_mode: BusInputMode = BusInputMode.NUMBERS) -> None:
        """Select the documented PSS/E 35 grammar.

        :param source: Diagnostic source label.
        :param bus_mode: Initial identifier interpretation.
        """
        super().__init__(source, bus_mode)
        self.version = PsseVersion.V35
        self.label_limit = 32
        self.bus_mode_support = FeatureSupport.YES
