# SPDX-License-Identifier: MPL-2.0
"""PSS/E 33 OPF layout: POM 33 §14.9 / DataFormats OPF chapters.

33/34: BCOST,CTYP,STATUS,CTBL; 35/36: BCOST,STATUS,CTYP,CTBL.
"""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion
from VeraGridEngine.IO.raw.versioned.base.rop import RawRop


class RawRopV33(RawRop):
    """Version-owned OPF column ordering."""
    __slots__ = ()

    def __init__(self, source: str = '<rop>') -> None:
        """Select the documented adjustable-shunt layout.

        :param source: Diagnostic source label.
        """
        super().__init__(source, PsseVersion.V33)
        self.status_before_cost = False
