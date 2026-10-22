# SPDX-License-Identifier: MPL-2.0
"""POM 33.10 section 8.1.2: 12-character labels. Bus mode directives arrived in 35.2."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion, BusInputMode
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport
from VeraGridEngine.IO.raw.versioned.base.sub import RawSub


class RawSubV33(RawSub):
    """PSS/E 33 SUB data; inherit only unchanged grammar."""

    __slots__ = ()

    def __init__(self, source: str = '<sub>', bus_mode: BusInputMode = BusInputMode.NUMBERS) -> None:
        """Select the documented PSS/E 33 grammar.

        :param source: Diagnostic source label.
        :param bus_mode: Initial identifier interpretation.
        """
        super().__init__(source, bus_mode, PsseVersion.V33)
        self.label_limit = 12
        self.bus_mode_support = FeatureSupport.NO
