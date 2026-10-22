# SPDX-License-Identifier: MPL-2.0
"""File ownership of registered PSS/E circuit properties."""
from enum import Enum


class PsseFileType(Enum):
    """Keep auxiliary documents distinct from RAW/RAWX network sections."""

    RAW = '.raw'
    SUB = '.sub'
    MON = '.mon'
    CON = '.con'
    DYR = '.dyr'
    SEQ = '.seq'
    ROP = '.rop'
    GCP = '.gcp'
    LOC = '.loc'
