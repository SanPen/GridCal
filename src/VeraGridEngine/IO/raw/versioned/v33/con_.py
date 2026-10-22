# SPDX-License-Identifier: MPL-2.0
"""POM 33.10 section 8.1.4 defines legacy events; no categories or node-breaker records. Extended shunt controls arrived in 35.2."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, BusInputMode
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport
from VeraGridEngine.IO.raw.versioned.base.con_ import RawCon


class RawConV33(RawCon):
    """PSS/E 33 CON data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<con>', bus_mode: BusInputMode = BusInputMode.NUMBERS) -> None:
        """Select the documented PSS/E 33 grammar.

        :param source: Diagnostic source label.
        :param bus_mode: Initial identifier interpretation.
        """
        super().__init__(source, bus_mode, PsseVersion.V33)
        self.bus_mode_support = FeatureSupport.NO
        self.category_support = FeatureSupport.NO
        self.node_support = FeatureSupport.NO
        self.swshunt_control = FeatureSupport.NO
        self.extended_isolation = FeatureSupport.NO
