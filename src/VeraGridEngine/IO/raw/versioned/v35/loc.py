# SPDX-License-Identifier: MPL-2.0
"""PSS/E 35 LOC interpretation: GUI 33 §3.6.8 / DataFormats 36 §17.

The older GUI layout permits optional endpoints; 36 specifies both endpoints.
GUI 35 documents bus locations; the branch layout inherits GUI 33 and needs
verification against native 35 exports.
"""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion
from VeraGridEngine.IO.raw.versioned.base.loc import RawLoc, BranchLocationLayout
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport


class RawLocV35(RawLoc):
    """Version-owned branch endpoint interpretation."""
    __slots__ = ()

    def __init__(self, source: str = '<loc>') -> None:
        """Select the documented location layout.

        :param source: Diagnostic source label.
        """
        super().__init__(source, PsseVersion.V35)
        self.branch_layout = BranchLocationLayout.OPTIONAL_ENDPOINTS
        self.branch_layout_support = FeatureSupport.UNVERIFIED
