# SPDX-License-Identifier: MPL-2.0
"""PSS/E 36 SEQ layout: POM 33 §5.5.1 / DataFormats sequence chapters.

35 profile targets 35.2; converter sections differ from earlier minor releases.
"""
from VeraGridEngine.IO.raw.psse_auxiliary import PsseVersion
from VeraGridEngine.IO.raw.versioned.base.seq import RawSeq, SequenceSection


class RawSeqV36(RawSeq):
    """Version-owned sequence section order and extensions."""
    __slots__ = ()

    def __init__(self, source: str = '<seq>') -> None:
        """Select documented fields.

        :param source: Diagnostic source label.
        """
        super().__init__(source, PsseVersion.V36)
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
