# SPDX-License-Identifier: MPL-2.0
"""CheatSheets 35.2 section 1.4; ReleaseNotes 35.2 pages 9-11 add switched-shunt controls and extended isolation."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, BusInputMode
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport
from VeraGridEngine.IO.raw.versioned.v34.con_ import RawConV34


class RawConV35(RawConV34):
    """PSS/E 35 CON data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<con>', bus_mode: BusInputMode = BusInputMode.NUMBERS) -> None:
        """Select the documented PSS/E 35 grammar.

        :param source: Diagnostic source label.
        :param bus_mode: Initial identifier interpretation.
        """
        super().__init__(source, bus_mode)
        self.version = PsseVersion.V35
        self.bus_mode_support = FeatureSupport.YES
        self.category_support = FeatureSupport.YES
        self.node_support = FeatureSupport.YES
        self.swshunt_control = FeatureSupport.YES
        self.extended_isolation = FeatureSupport.YES
