

from enum import Enum


class RegulatingControlModeKind(Enum):
    voltage = 'voltage'
    activePower = 'activePower'
    reactivePower = 'reactivePower'
    currentFlow = 'currentFlow'
    admittance = 'admittance'
    timeScheduled = 'timeScheduled'
    temperature = 'temperature'
    powerFactor = 'powerFactor'

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return TransformerControlType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))