from enum import Enum


class BranchType(Enum):
    Branch = 'branch',
    Line = 'line',
    Transformer = 'transformer',
    Reactance = 'reactance',
    Switch = 'switch'