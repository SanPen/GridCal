"""
A "slip map" widget for PySide6.

So why is this widget called 'pySlip'?

Well, in the OpenStreetMap world[1], a 'slippy map' is a browser map view
served by a tile server that can be panned and zoomed in the same way as
popularised by Google maps.  Such a map feels 'slippery', I guess.

Rather than 'slippy' I went for the slightly more formal 'pySlip' since the
thing is written in Python and therefore must have the obligatory 'py' prefix.

Even though this was originally written for a geographical application, the
*underlying* system only assumes a cartesian 2D coordinate system.  The tile
source must translate between the underlying coordinates and whatever coordinate
system the tiles use.  So pySlip could be used to present a game map, 2D CAD
view, etc, as well as Mercator tiles provided either locally from the filesystem
or from the internet (OpenStreetMap, for example).

[1] http://wiki.openstreetmap.org/index.php/Slippy_Map

Some semantics:
    map   the whole map
    view  is the view of the map through the widget
          (view may be smaller than map, or larger)
"""

from typing import Callable, List, Union, Tuple
from PySide6.QtGui import QColor


class MapLayer:
    """
    A Layer object.
    """

    DefaultDelta = 50  # default selection delta

    def __init__(self,
                 layer_id: int = 0,
                 painter: Callable = None,
                 data: List = None,
                 map_rel: bool = True,
                 visible: bool = False,
                 show_levels: List[int] = None,
                 selectable: bool = False,
                 name: str = "<no name given>",
                 ltype: int = None) -> None:
        """
        Initialise the Layer object.

        id           unique layer ID
        painter      render function
        data         the layer data
        map_rel      True if layer is map-relative, else layer-relative
        visible      layer visibility
        show_levels  list of levels at which to auto-show the level
        selectable   True if select operates on this layer, else False
        name         the name of the layer (for debug)
        ltype        a layer 'type' flag
        """

        self.painter = painter  # routine to draw layer
        self.data = data  # data that defines the layer
        self.map_rel = map_rel  # True if layer is map relative
        self.visible = visible  # True if layer visible
        self.show_levels = show_levels  # None or list of levels to auto-show
        self.selectable = selectable  # True if we can select on this layer
        self.delta = self.DefaultDelta  # minimum distance for selection
        self.name = name  # name of this layer
        self.type = ltype  # type of layer
        self.layer_id = layer_id  # ID of this layer

        self.valid_placements = ['cc', 'nw', 'cn', 'ne', 'ce', 'se', 'cs', 'sw', 'cw']

    @staticmethod
    def colour_to_internal(colour: Union[str, QColor, List[int]]) -> Tuple[int]:
        """Convert a colour in one of various forms to an internal format.

        colour  either a HEX string ('#RRGGBBAA')
                or a tuple (r, g, b, a)
                or a colour name ('red')

        Returns internal form:  (r, g, b, a)
        """

        if isinstance(colour, str):
            # expect '#RRGGBBAA' form
            if len(colour) != 9 or colour[0] != '#':
                # assume it's a colour *name*
                # we should do more checking of the name here, though it looks
                # like PySide6 defaults to a colour if the name isn't recognized
                c = QColor(colour)
                result = (c.red(), c.blue(), c.green(), c.alpha())
            else:
                # we try for a colour like '#RRGGBBAA'
                r = int(colour[1:3], 16)
                g = int(colour[3:5], 16)
                b = int(colour[5:7], 16)
                a = int(colour[7:9], 16)
                result = (r, g, b, a)
        elif isinstance(colour, QColor):
            # if it's a QColor, get float RGBA values, convert to ints
            result = [int(v * 255) for v in colour.getRgbF()]
        else:

            # we assume a list or tuple
            try:
                len_colour = len(colour)
            except TypeError:
                msg = ("Colour value '%s' is not in the form '(r, g, b, a)'" % str(colour))
                raise Exception(msg)

            if len_colour != 4:
                msg = ("Colour value '%s' is not in the form '(r, g, b, a)'"
                       % str(colour))
                raise Exception(msg)
            result = []
            for v in colour:
                try:
                    v = int(v)
                except ValueError:
                    msg = ("Colour value '%s' is not in the form '(r, g, b, a)'"
                           % str(colour))
                    raise Exception(msg)
                if v < 0 or v > 255:
                    msg = ("Colour value '%s' is not in the form '(r, g, b, a)'"
                           % str(colour))
                    raise Exception(msg)
                result.append(v)
            result = tuple(result)

        return result

    @staticmethod
    def get_i18n_kw(kwargs, kws, default):
        """Get alternate international keyword value.

        kwargs   dictionary to look for keyword value
        kws      iterable of keyword spelling strings
        default  default value if no keyword found

        Returns the keyword value.
        """

        result = None
        for kw_str in kws[:-1]:
            result = kwargs.get(kw_str, None)
            if result:
                break
        else:
            result = kwargs.get(kws[-1], default)

        return result

    def setData(self,
                data,
                default_placement='cc',
                default_width=1,
                default_colour='red',
                default_offset_x=0,
                default_offset_y=0,
                default_data=None):
        """

        :param data:
        :param default_placement:
        :param default_width:
        :param default_colour:
        :param default_offset_x:
        :param default_offset_y:
        :param default_data:
        :return:
        """

        # create draw_data iterable
        self.data = []
        for data_entry in data:

            if len(data_entry) == 2:
                polyline_points, attributes = data_entry

            elif len(data_entry) == 1:
                polyline_points = data_entry
                attributes = {}

            else:
                msg = ('Polyline data must be iterable of tuples: (polyline, [attributes])\n'
                       'Got: %s' % str(data_entry))
                raise Exception(msg)

            # get polygon attributes
            placement = attributes.get('placement', default_placement)
            width = attributes.get('width', default_width)
            colour = self.get_i18n_kw(attributes, ('colour', 'color'), default_colour)
            offset_x = attributes.get('offset_x', default_offset_x)
            offset_y = attributes.get('offset_y', default_offset_y)
            udata = attributes.get('data', default_data)

            # check values that can be wrong
            if not placement:
                placement = default_placement
            placement = placement.lower()

            if placement not in self.valid_placements:
                msg = ("Polyline placement value is invalid, got '%s'" % str(placement))
                raise Exception(msg)

            # convert various colour formats to internal (r, g, b, a)
            rgba = self.colour_to_internal(colour)

            self.data.append((polyline_points, placement, width, rgba, offset_x, offset_y, udata))

    def __str__(self):
        return ('<pySlipQt Layer: id=%d, name=%s, map_rel=%s, visible=%s>'
                % (self.layer_id, self.name, str(self.map_rel), str(self.visible)))
