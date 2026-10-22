# SPDX-License-Identifier: MPL-2.0
"""PSS/E 35 SEQ layout: POM 33 §5.5.1 / DataFormats sequence chapters.

35 profile targets 35.2; converter sections differ from earlier minor releases.
"""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion
from VeraGridEngine.IO.raw.versioned.base.seq import RawSeq, SequenceSection, Sequence35Layout


class RawSeqV35(RawSeq):
    """Version-owned sequence section order and extensions."""
    __slots__ = ()

    def __init__(self, source: str = '<seq>', layout: Sequence35Layout = Sequence35Layout.V35_2) -> None:
        """Select documented fields.

        :param source: Diagnostic source label.
        :param layout: Explicit minor-release NCS layout (DataFormats 35.2 §3.13).
        """
        super().__init__(source, PsseVersion.V35)
        self.reference_angle = True
        self.expanded_induction = True
        self.shunt_ids = True
        self.sections = (
            SequenceSection.SYSTEM,
            SequenceSection.GENERATOR,
            SequenceSection.LOAD,
            SequenceSection.BRANCH,
            SequenceSection.MUTUAL,
            SequenceSection.TRANSFORMER,
            SequenceSection.SWITCHED_SHUNT,
            SequenceSection.FIXED_SHUNT,
            SequenceSection.INDUCTION,
            SequenceSection.NCS_CHARACTERISTICS,
            SequenceSection.NCS_GENERATOR,
        )
        if layout == Sequence35Layout.V35_0:
            self.sections = self.sections[:-2] + (SequenceSection.LEGACY_NCS,)
        else:
            pass
