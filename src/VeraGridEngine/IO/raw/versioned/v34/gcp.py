# SPDX-License-Identifier: MPL-2.0
"""PSS/E 34 inherits the headerless POM 33 §11.21.1 capability grammar.

A version-34-specific capability file specification was not available in the
local manuals. This inheritance requires verification against native exports.
"""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion
from VeraGridEngine.IO.raw.versioned.base.gcp import RawGcp
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport


class RawGcpV34(RawGcp):
    """Explicit version profile for machine capability curves."""

    __slots__ = ()

    def __init__(self, source: str = '<gcp>') -> None:
        """Select the documented layout.

        :param source: Diagnostic source label.
        """
        super().__init__(source, PsseVersion.V34)
        self.has_header = False
        self.minimum_points = 1
        self.infer_origin = True
        self.format_support = FeatureSupport.UNVERIFIED
