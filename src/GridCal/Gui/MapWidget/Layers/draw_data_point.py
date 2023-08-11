
from typing import List, Dict, Tuple
from GridCal.Gui.MapWidget.Layers.place import Place


# version number of the widget
__version__ = '0.5'


class DrawDataPoint:

    def __init__(self,
                 p: List[Tuple[float, float]],
                 placement: Place,
                 width: int,
                 colour: Tuple[int, int, int, int],  # RGBA
                 offset_x: float,
                 offset_y: float,
                 udata: Dict):
        """

        :param p: list of points
        :param placement: placement type
        :param width: line width
        :param colour: colour tuple (R, G, B, A)
        :param offset_x: X offset in pixels
        :param offset_y: Y offset in pixels
        :param udata: dictionary of extra properties
        """
        self.p = p
        self.placement = placement
        self.width = width
        self.colour = colour
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.udata = udata
