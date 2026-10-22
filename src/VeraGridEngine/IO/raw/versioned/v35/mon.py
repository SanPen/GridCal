# SPDX-License-Identifier: MPL-2.0
"""CheatSheets 35.2 section 1.3; ReleaseNotes 35.2 pages 10-11 explicitly add ranges, extra KV filters and TIE alias."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, BusInputMode
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport
from VeraGridEngine.IO.raw.versioned.v34.mon import RawMonV34


class RawMonV35(RawMonV34):
    """PSS/E 35 MON data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<mon>', bus_mode: BusInputMode = BusInputMode.NUMBERS) -> None:
        """Select the documented PSS/E 35 grammar.

        :param source: Diagnostic source label.
        :param bus_mode: Initial identifier interpretation.
        """
        super().__init__(source, bus_mode)
        self.version = PsseVersion.V35
        self.bus_mode_support = FeatureSupport.YES
        self.extended_selectors = FeatureSupport.YES
        self.singular_tie = FeatureSupport.YES
        self.node_support = FeatureSupport.YES
        self.rating_limit = 12
