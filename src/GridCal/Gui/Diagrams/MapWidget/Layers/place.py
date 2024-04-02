from enum import Enum


class Place(Enum):
    """
    places to draw in the map
    """

    Center = "cc"
    NorthWest = "nw"
    CenterNorth = "cn"
    NorthEast = "ne"
    CenterEast = "ce"
    SouthEast = "se"
    CenterSouth = "cs"
    SouthWest = "sw"
    CenterWest = "cw"
