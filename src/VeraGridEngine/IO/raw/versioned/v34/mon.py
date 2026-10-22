# SPDX-License-Identifier: MPL-2.0
"""Legacy MON grammar. The local 34.1 manual documents RAW ratings and nodes, not MON syntax: expanded MON support stays unverified."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, BusInputMode
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport
from VeraGridEngine.IO.raw.versioned.v33.mon import RawMonV33


class RawMonV34(RawMonV33):
    """PSS/E 34 MON data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<mon>', bus_mode: BusInputMode = BusInputMode.NUMBERS) -> None:
        """Select the documented PSS/E 34 grammar.

        :param source: Diagnostic source label.
        :param bus_mode: Initial identifier interpretation.
        """
        super().__init__(source, bus_mode)
        self.version = PsseVersion.V34
        self.node_support = FeatureSupport.UNVERIFIED
        self.rating_limit = None
        self.rating_exact_count = None
