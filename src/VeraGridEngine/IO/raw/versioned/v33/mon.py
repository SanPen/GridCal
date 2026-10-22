# SPDX-License-Identifier: MPL-2.0
"""POM 33.10 section 8.1.3: three interface ratings; simple selectors. ALL BUSES and primary KV selectors are legacy."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, BusInputMode
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport
from VeraGridEngine.IO.raw.versioned.base.mon import RawMon


class RawMonV33(RawMon):
    """PSS/E 33 MON data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<mon>', bus_mode: BusInputMode = BusInputMode.NUMBERS) -> None:
        """Select the documented PSS/E 33 grammar.

        :param source: Diagnostic source label.
        :param bus_mode: Initial identifier interpretation.
        """
        super().__init__(source, bus_mode, PsseVersion.V33)
        self.bus_mode_support = FeatureSupport.NO
        self.extended_selectors = FeatureSupport.NO
        self.singular_tie = FeatureSupport.NO
        self.node_support = FeatureSupport.NO
        self.rating_limit = 3
        self.rating_exact_count = 3
