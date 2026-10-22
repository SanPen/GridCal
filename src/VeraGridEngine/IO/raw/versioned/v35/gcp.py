# SPDX-License-Identifier: MPL-2.0
"""PSS/E 35 capability format; POM 33 §11.21.1 / DataFormats 35 §7 / 36 §10."""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion
from VeraGridEngine.IO.raw.versioned.base.gcp import RawGcp
from VeraGridEngine.IO.raw.versioned.base.auxiliary import FeatureSupport


class RawGcpV35(RawGcp):
    """Explicit version profile for machine capability curves."""

    __slots__ = ()

    def __init__(self, source: str = '<gcp>') -> None:
        """Select the documented layout.

        :param source: Diagnostic source label.
        """
        super().__init__(source, PsseVersion.V35)
        self.has_header = True
        self.minimum_points = 2
        self.infer_origin = False
        self.format_support = FeatureSupport.YES
