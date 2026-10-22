# SPDX-License-Identifier: MPL-2.0
"""Shared legacy CON grammar. Local 34.1 documentation does not establish category or node-breaker CON syntax; these are explicitly unverified."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, BusInputMode
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport
from VeraGridEngine.IO.raw.versioned.v33.con_ import RawConV33


class RawConV34(RawConV33):
    """PSS/E 34 CON data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<con>', bus_mode: BusInputMode = BusInputMode.NUMBERS) -> None:
        """Select the documented PSS/E 34 grammar.

        :param source: Diagnostic source label.
        :param bus_mode: Initial identifier interpretation.
        """
        super().__init__(source, bus_mode)
        self.version = PsseVersion.V34
        self.category_support = FeatureSupport.UNVERIFIED
        self.node_support = FeatureSupport.UNVERIFIED
