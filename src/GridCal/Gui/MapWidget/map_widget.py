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

from typing import List, Dict, Union, Tuple, Callable
from PySide6.QtCore import Qt, QTimer, QPoint, QPointF, QEvent
from PySide6.QtWidgets import QSizePolicy, QWidget, QMessageBox
from PySide6.QtGui import QPainter, QColor, QPixmap, QPen, QFont, QFontMetrics, QPolygon, QBrush, QCursor, \
    QMouseEvent, QKeyEvent, QWheelEvent, QResizeEvent, QEnterEvent, QPaintEvent

from GridCal.Gui.MapWidget.map_events import LevelEvent, PositionEvent, SelectEvent, BoxSelectEvent
from GridCal.Gui.MapWidget.logger import log
from GridCal.Gui.MapWidget.Layers.point_layer import PointLayer, PointData
from GridCal.Gui.MapWidget.Layers.polygon_layer import PolygonLayer, PolygonData
from GridCal.Gui.MapWidget.Layers.polyline_layer import PolylineLayer, PolylineData
from GridCal.Gui.MapWidget.Layers.text_layer import TextLayer, TextData
from GridCal.Gui.MapWidget.Layers.image_layer import ImageLayer, ImageData
from GridCal.Gui.MapWidget.Layers.layer_types import LayerType
from GridCal.Gui.MapWidget.Layers.place import Place
from GridCal.Gui.MapWidget.Tiles.tiles import Tiles

# version number of the widget
__version__ = '0.5'


class MapWidget(QWidget):
    """
    Map widget
    """

    # default point attributes - map relative
    DefaultPointPlacement = Place.Center
    DefaultPointRadius = 3
    DefaultPointColour = 'red'
    DefaultPointOffsetX = 0
    DefaultPointOffsetY = 0
    DefaultPointData = None

    # default point attributes - view relative
    DefaultPointViewPlacement = Place.Center
    DefaultPointViewRadius = 3
    DefaultPointViewColour = 'red'
    DefaultPointViewOffsetX = 0
    DefaultPointViewOffsetY = 0
    DefaultPointViewData = None

    # default image attributes - map relative
    DefaultImagePlacement = Place.NorthWest
    DefaultImageRadius = 0
    DefaultImageColour = 'black'
    DefaultImageOffsetX = 0
    DefaultImageOffsetY = 0
    DefaultImageData = None

    # default image attributes - view relative
    DefaultImageViewPlacement = Place.NorthWest
    DefaultImageViewRadius = 0
    DefaultImageViewColour = 'black'
    DefaultImageViewOffsetX = 0
    DefaultImageViewOffsetY = 0
    DefaultImageViewData = None

    # default text attributes - map relative
    DefaultTextPlacement = Place.NorthWest
    DefaultTextRadius = 2
    DefaultTextColour = 'black'
    DefaultTextTextColour = 'black'
    DefaultTextOffsetX = 5
    DefaultTextOffsetY = 1
    DefaultTextFontname = 'Helvetica'
    DefaultTextFontSize = 10
    DefaultTextData = None

    # default text attributes - view relative
    DefaultTextViewPlacement = Place.NorthWest
    DefaultTextViewRadius = 0
    DefaultTextViewColour = 'black'
    DefaultTextViewTextColour = 'black'
    DefaultTextViewOffsetX = 0
    DefaultTextViewOffsetY = 0
    DefaultTextViewFontname = 'Helvetica'
    DefaultTextViewFontSize = 10
    DefaultTextViewData = None

    # default polygon attributes - map view
    DefaultPolygonPlacement = Place.Center
    DefaultPolygonWidth = 1
    DefaultPolygonColour = 'red'
    DefaultPolygonClose = False
    DefaultPolygonFilled = False
    DefaultPolygonFillcolour = 'blue'
    DefaultPolygonOffsetX = 0
    DefaultPolygonOffsetY = 0
    DefaultPolygonData = None

    # default polygon attributes - view relative
    DefaultPolygonViewPlacement = Place.Center
    DefaultPolygonViewWidth = 1
    DefaultPolygonViewColour = 'red'
    DefaultPolygonViewClose = False
    DefaultPolygonViewFilled = False
    DefaultPolygonViewFillcolour = 'blue'
    DefaultPolygonViewOffsetX = 0
    DefaultPolygonViewOffsetY = 0
    DefaultPolygonViewData = None

    # default polyline attributes - map view
    DefaultPolylinePlacement = Place.Center
    DefaultPolylineWidth = 1
    DefaultPolylineColour = 'red'
    DefaultPolylineOffsetX = 0
    DefaultPolylineOffsetY = 0
    DefaultPolylineData = None

    # default polyline attributes - view relative
    DefaultPolylineViewPlacement = Place.Center
    DefaultPolylineViewWidth = 1
    DefaultPolylineViewColour = 'red'
    DefaultPolylineViewOffsetX = 0
    DefaultPolylineViewOffsetY = 0
    DefaultPolylineViewData = None

    # layer type values
    # (TypePoint, TypeImage, TypeText, TypePolygon, TypePolyline) = range(5)

    # cursor types
    StandardCursor = Qt.ArrowCursor
    BoxSelectCursor = Qt.CrossCursor
    WaitCursor = Qt.WaitCursor
    DragCursor = Qt.OpenHandCursor

    # box select constants
    BoxSelectPenColor = QColor(255, 0, 0, 128)
    BoxSelectPenStyle = Qt.DashLine
    BoxSelectPenWidth = 2

    def __init__(self,
                 parent: QWidget,
                 tile_src: Tiles,
                 start_level: int,
                 zoom_callback: Callable[[int], None],
                 position_callback: Callable[[float, float], None],
                 **kwargs):
        """Initialize the pySlipQt widget.

        parent       the GUI parent widget
        tile_src     a Tiles object, source of tiles
        start_level  level to initially display
        kwargs       keyword args passed through to the underlying QLabel
        """

        super().__init__(parent, **kwargs)  # inherit all parent object setup

        # remember the tile source object
        self.tile_src = tile_src
        self.tile_size_x = 256
        self.tile_size_y = 256

        # the tile coordinates
        self.level: int = start_level

        # view and map limits
        self.view_width = 0  # width/height of the view
        self.view_height = 0  # changes when the widget changes size

        # set tile and levels stuff
        self.max_level = max(tile_src.levels)  # max level displayed
        self.min_level = min(tile_src.levels)  # min level displayed
        self.tile_width = tile_src.tile_size_x  # width of tile in pixels
        self.tile_height = tile_src.tile_size_y  # height of tile in pixels
        self.num_tiles_x = tile_src.num_tiles_x  # number of map tiles in X direction
        self.num_tiles_y = tile_src.num_tiles_y  # number of map tiles in Y direction
        self.wrap_x = False  # True if tiles wrap in X direction
        self.wrap_y = False  # True if tiles wrap in Y direction

        self.map_width = self.num_tiles_x * self.tile_width  # virtual map width
        self.map_height = self.num_tiles_y * self.tile_height  # virtual map height

        self.next_layer_id = 1  # source of unique layer IDs

        self.tiles_max_level = max(tile_src.levels)  # maximum level in tile source
        self.tiles_min_level = min(tile_src.levels)  # minimum level in tile source

        # box select state
        self.sbox_w = None  # width/height of box select rectangle
        self.sbox_h = None
        self.sbox_1_x = None  # view coords of start corner of select box
        self.sbox_1_y = None  # if selecting, self.sbox_1_x != NOne

        # define position and tile coords of the "key" tile
        self.key_tile_left = 0  # tile coordinates of key tile
        self.key_tile_top = 0
        self.key_tile_xoffset = 0  # view coordinates of key tile wrt view
        self.key_tile_yoffset = 0

        # we keep track of the cursor coordinates if cursor on map
        self.mouse_x = None
        self.mouse_y = None

        # state variables holding mouse buttons state
        self.left_mbutton_down = False
        self.mid_mbutton_down = False
        self.right_mbutton_down = False

        # keyboard state variables
        self.shift_down = False

        # when dragging, remember the initial start point
        self.start_drag_x = None
        self.start_drag_y = None

        # layer state variables
        self.layer_mapping: Dict[int, Union[
            PointLayer, PolygonLayer, PolylineLayer, TextLayer, ImageLayer]] = dict()  # maps layer ID to layer data
        self.layer_z_order = list()  # layer Z order, contains layer IDs

        self.map_llon = 0.0
        self.map_rlon = 0.0
        self.map_blat = 0.0
        self.map_tlat = 0.0

        self.view_llon = 0
        self.view_rlon = 0
        self.view_blat = 0
        self.view_tlat = 0

        # some cursors
        self.standard_cursor = QCursor(self.StandardCursor)
        self.box_select_cursor = QCursor(self.BoxSelectCursor)
        self.wait_cursor = QCursor(self.WaitCursor)
        self.drag_cursor = QCursor(self.DragCursor)

        # set up dispatch dictionaries for layer select handlers
        # for point select
        self.layerPSelHandler = {LayerType.Point: self.sel_point_in_layer,
                                 LayerType.Image: self.sel_image_in_layer,
                                 LayerType.Text: self.sel_text_in_layer,
                                 LayerType.Polygon: self.sel_polygon_in_layer,
                                 LayerType.Polyline: self.sel_polyline_in_layer}

        # for box select
        self.layerBSelHandler = {LayerType.Point: self.sel_box_points_in_layer,
                                 LayerType.Image: self.sel_box_images_in_layer,
                                 LayerType.Text: self.sel_box_texts_in_layer,
                                 LayerType.Polygon: self.sel_box_polygons_in_layer,
                                 LayerType.Polyline: self.sel_box_polylines_in_layer}

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(self.tile_width, self.tile_height)

        tile_src.setCallback(self.on_tile_available)

        self.setMouseTracking(True)
        self.setEnabled(True)  # to receive key events?

        self.default_cursor = self.standard_cursor
        self.setCursor(self.standard_cursor)

        # do a "resize" after this function
        QTimer.singleShot(10, self.resizeEvent)

        # callbacks
        self.zoom_callback: Callable[[int], None] = zoom_callback
        self.position_callback: Callable[[float, float], None] = position_callback

    def on_tile_available(self, level: int, x: float, y: float, image: QPixmap, error: bool):
        """Called when a new 'net tile is available.

        level  the level the tile is for
        x, y   tile coordinates of the tile
        image  the tile image data
        error  True if there was an error

        We have enough information to redraw a specific tile,
        but we just redraw the widget.
        """

        self.update()

    def dump_event(self, msg, event):
        """Dump an event to the log.

        Print attributes and values for non_dunder attributes.
        """

        log('dump_event: %s:' % msg)
        for attr in dir(event):
            if not attr.startswith('__'):
                log('    event.%s=%s' % (attr, str(getattr(event, attr))))

    # def raise_event(self, etype, **kwargs):
    #     """Raise event with attributes in 'kwargs'.
    #
    #     etype  type of event to raise
    #     kwargs  a dictionary of attributes to attach to event
    #     """
    #
    #     event = PySlipQtEvent(etype, **kwargs)
    #     self.pyslipqt_event_dict[etype](event)

    def mousePressEvent(self, event):
        """Mouse button pressed."""

        click_x = event.x()
        click_y = event.y()

        # assume we aren't dragging
        self.start_drag_x = self.start_drag_y = None

        b = event.button()
        if b == Qt.NoButton:
            pass
        elif b == Qt.LeftButton:
            self.left_mbutton_down = True
            if self.shift_down:
                (self.sbox_w, self.sbox_h) = (0, 0)
                (self.sbox_1_x, self.sbox_1_y) = (click_x, click_y)
        elif b == Qt.MidButton:
            self.mid_mbutton_down = True
        elif b == Qt.RightButton:
            self.right_mbutton_down = True
        else:
            log('mousePressEvent: unknown button')

    def mouseReleaseEvent(self, event):
        """Mouse button was released.

        event.x & event.y  view coords when released

        Could be end of a drag or point or box selection.  If it's the end of
        a drag we don't do a lot.  If a selection we process that.
        """

        x = event.x()
        y = event.y()
        clickpt_v = (x, y)

        # cursor back to normal in case it was a box select
        self.setCursor(self.default_cursor)

        # we need a repaint to remove any selection box, but NOT YET!
        delayed_paint = self.sbox_1_x  # True if box select active

        b = event.button()
        if b == Qt.NoButton:
            pass
        elif b == Qt.LeftButton:
            self.left_mbutton_down = False
            # legacy code from pySlip, leave just in case we need it
            #            # if required, ignore this event
            #            if self.ignore_next_up:
            #                self.ignore_next_up = False
            #                return
            #            # we need a repaint to remove any selection box, but NOT YET!
            #            delayed_paint = self.sbox_1_x       # True if box select active

            if self.sbox_1_x:
                # we are doing a box select,
                # get canonical selection box in view coordinates
                (ll_vx, ll_vy, tr_vx, tr_vy) = self.sel_box_canonical()

                # get lower-left and top-right view tuples
                ll_v = (ll_vx, ll_vy)
                tr_v = (tr_vx, tr_vy)

                # convert view to geo coords
                ll_g = self.view_to_geo(ll_vx, ll_vy)
                tr_g = self.view_to_geo(tr_vx, tr_vy)

                # check each layer for a box select event, work on copy of
                # '.layer_z_order' as user response could change layer order
                for lid in self.layer_z_order[:]:
                    l = self.layer_mapping[lid]
                    # if layer visible and selectable
                    if l.selectable and l.visible:
                        if l.map_rel:
                            # map-relative, get all points selected (if any)
                            result = self.layerBSelHandler[l.type](l, ll_g, tr_g)
                        else:
                            # view-relative
                            result = self.layerBSelHandler[l.type](l, ll_v, tr_v)

                        if result:
                            (sel, data, relsel) = result

                            BoxSelectEvent(mposn=None,
                                           vposn=None,
                                           layer_id=lid,
                                           selection=sel,
                                           relsel=relsel).emit_event()

                        else:
                            # raise an empty EVT_PYSLIPQT_BOXSELECT event
                            BoxSelectEvent(mposn=None,
                                           vposn=None,
                                           layer_id=lid,
                                           selection=None,
                                           relsel=None).emit_event()

                        # user code possibly updated screen, must repaint
                        delayed_paint = True
                self.sbox_1_x = self.sbox_1_y = None
            else:
                if self.start_drag_x is None:
                    # not dragging, possible point selection
                    # get click point in view & global coords
                    clickpt_g = self.view_to_geo(x, y)
                    #                    if clickpt_g is None:
                    #                        return          # we clicked off the map

                    # check each layer for a point select handler, we work on a
                    # copy as user click-handler code could change order
                    for lid in self.layer_z_order[:]:
                        l = self.layer_mapping[lid]
                        # if layer visible and selectable
                        if l.selectable and l.visible:
                            result = self.layerPSelHandler[l.type](l, clickpt_v, clickpt_g)
                            if result:
                                (sel, relsel) = result

                                # raise the EVT_PYSLIPQT_SELECT event
                                SelectEvent(mposn=clickpt_g,
                                            vposn=clickpt_v,
                                            layer_id=lid,
                                            selection=sel,
                                            relsel=relsel).emit_event()
                            else:
                                # raise an empty EVT_PYSLIPQT_SELECT event
                                SelectEvent(mposn=clickpt_g,
                                            vposn=clickpt_v,
                                            layer_id=lid,
                                            selection=None,
                                            relsel=None).emit_event()



            # turn off dragging, if we were
            self.start_drag_x = self.start_drag_y = None

            # turn off box selection mechanism
            self.sbox_1_x = self.sbox_1_y = None

            # force PAINT event if required
            if delayed_paint:
                self.update()

            mouse_geo = self.view_to_geo(x, y)
            self.position_callback(mouse_geo[0], mouse_geo[1])

        elif b == Qt.MidButton:
            self.mid_mbutton_down = False
        elif b == Qt.RightButton:
            self.right_mbutton_down = False
        else:
            log('mouseReleaseEvent: unknown button')

    def mouseDoubleClickEvent(self, event):
        """

        :param event:
        :return:
        """
        b = event.button()
        if b == Qt.NoButton:
            pass
        elif b == Qt.LeftButton:
            pass
        elif b == Qt.MidButton:
            pass
        elif b == Qt.RightButton:
            pass
        else:
            log('mouseDoubleClickEvent: unknown button')

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Handle a mouse move event.
       
        If left mouse down, either drag the map or start a box selection.
        If we are off the map, ensure self.mouse_x, etc, are None.
        """

        x = event.x()
        y = event.y()

        mouse_geo = self.view_to_geo(x, y)

        # update remembered mouse position in case of zoom
        self.mouse_x = self.mouse_y = None
        if mouse_geo:
            self.mouse_x = x
            self.mouse_y = y

        if self.left_mbutton_down:
            if self.shift_down:
                # we are starting a box select
                if self.sbox_1_x == -1:
                    # mouse down before SHIFT down, fill in box start point
                    self.sbox_1_x = x
                    self.sbox_1_y = y

                # set select box start point at mouse position
                self.sbox_w, self.sbox_h = x - self.sbox_1_x, y - self.sbox_1_y
            else:
                # we are dragging
                if self.start_drag_x is None:
                    # start of drag, set drag state
                    (self.start_drag_x, self.start_drag_y) = (x, y)

                # we don't move much - less than a tile width/height
                # drag the key tile in the X direction
                delta_x = self.start_drag_x - x
                self.key_tile_xoffset -= delta_x
                if self.key_tile_xoffset < -self.tile_width:  # too far left
                    self.key_tile_xoffset += self.tile_width
                    self.key_tile_left += 1
                if self.key_tile_xoffset > 0:  # too far right
                    self.key_tile_xoffset -= self.tile_width
                    self.key_tile_left -= 1

                # drag the key tile in the Y direction
                delta_y = self.start_drag_y - y
                self.key_tile_yoffset -= delta_y
                if self.key_tile_yoffset < -self.tile_height:  # too far up
                    self.key_tile_yoffset += self.tile_height
                    self.key_tile_top += 1
                if self.key_tile_yoffset > 0:  # too far down
                    self.key_tile_yoffset -= self.tile_height
                    self.key_tile_top -= 1

                # set key tile stuff so update() shows drag
                self.rectify_key_tile()

                # get ready for more drag
                self.start_drag_x, self.start_drag_y = x, y

            self.update()  # force a repaint

        # emit the event for mouse position
        PositionEvent(mposn=mouse_geo, vposn=(x, y)).emit_event()
        # self.position_callback(mouse_geo[0], mouse_geo[1])

    def keyPressEvent(self, event: QKeyEvent):
        """Capture a key press."""

        if event.key() == Qt.Key_Shift:
            self.shift_down = True
            self.default_cursor = self.box_select_cursor
            self.setCursor(self.default_cursor)
            if self.left_mbutton_down:
                # start of a box select
                self.sbox_1_x = -1  # special value, means fill X,Y on mouse down
        event.accept()

    def keyReleaseEvent(self, event: QKeyEvent):
        """Capture a key release."""

        key = event.key()
        if event.key() == Qt.Key_Shift:
            self.shift_down = False
            self.default_cursor = self.standard_cursor
            self.setCursor(self.default_cursor)
        event.accept()

    def wheelEvent(self, event: QWheelEvent):
        """
        Handle a mouse wheel rotation.
        """

        if event.angleDelta().y() > 0:
            new_level = self.level + 1
        else:
            new_level = self.level - 1

        self.zoom_level(new_level, self.mouse_x, self.mouse_y)

    def resizeEvent(self, event: QResizeEvent = None):
        """
        Widget resized, recompute some state.
        """

        # new widget size
        self.view_width = self.width()
        self.view_height = self.height()

        # recalculate the "key" tile stuff
        self.rectify_key_tile()

    def enterEvent(self, event: QEnterEvent):
        self.setFocus()

    def leaveEvent(self, event: QEvent):
        """
        The mouse is leaving the widget.

        Raise a EVT_PYSLIPQT_POSITION event with positions set to None.
        We do this so user code can clear any mouse position data, for example.
        """

        self.mouse_x = None
        self.mouse_y = None

        # self.raise_event(MapWidget.EVT_PYSLIPQT_POSITION, mposn=None, vposn=None)
        PositionEvent(mposn=None, vposn=None).emit_event()

    def paintEvent(self, event: QPaintEvent):
        """
        Draw the base map and then the layers on top.
        """

        # The "key" tile position is maintained by other code, we just
        # assume it's set.  Figure out how to draw tiles, set up 'row_list' and
        # 'col_list' which are list of tile coords to draw (row and colums).

        col_list = []
        x_coord = self.key_tile_left
        x_pix_start = self.key_tile_xoffset
        while x_pix_start < self.view_width:
            col_list.append(x_coord)
            if not self.wrap_x and x_coord >= self.num_tiles_x - 1:
                break
            x_coord = (x_coord + 1) % self.num_tiles_x
            x_pix_start += self.tile_height

        row_list = []
        y_coord = self.key_tile_top
        y_pix_start = self.key_tile_yoffset
        while y_pix_start < self.view_height:
            row_list.append(y_coord)
            if not self.wrap_y and y_coord >= self.num_tiles_y - 1:
                break
            y_coord = (y_coord + 1) % self.num_tiles_y
            y_pix_start += self.tile_height

        # Ready to update the view
        # prepare the canvas
        painter = QPainter()
        painter.begin(self)

        # paste all background tiles onto the view
        x_pix = self.key_tile_xoffset
        for x in col_list:
            y_pix = self.key_tile_yoffset
            for y in row_list:
                painter.drawPixmap(x_pix, y_pix, self.tile_src.GetTile(x, y))
                y_pix += self.tile_height
            x_pix += self.tile_width

        # now draw the layers
        for layer_id in self.layer_z_order:
            layer = self.layer_mapping[layer_id]
            if layer.visible and self.level in layer.show_levels and len(layer.data) > 0:
                layer.painter(painter, layer.data, map_rel=layer.map_rel)

        # draw selection rectangle, if any
        if self.sbox_1_x:
            # draw the select box, transparent fill
            painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
            pen = QPen(MapWidget.BoxSelectPenColor, MapWidget.BoxSelectPenWidth, MapWidget.BoxSelectPenStyle)
            painter.setPen(pen)
            painter.drawRect(self.sbox_1_x, self.sbox_1_y, self.sbox_w, self.sbox_h)

        painter.end()

    def normalize_key_after_drag(self, delta_x=None, delta_y=None):
        """After drag, set "key" tile correctly.

        delta_x  the X amount dragged (pixels), None if not dragged in X
        delta_y  the Y amount dragged (pixels), None if not dragged in Y

        The 'key' tile was correct, but we've moved the map in the X and Y
        directions.  Normalize the 'key' tile taking into account whether
        we are wrapping X or Y directions.

        Dragging left gets a positive delta_x, up gets a positive delta_y.
        We call this routine to initialize things after zoom (for instance),
        passing 0 drag deltas.
        """

        if self.wrap_x:
            # wrapping in X direction, move 'key' tile in X
            self.key_tile_xoffset -= delta_x

            # normalize .key_tile_left value
            while self.key_tile_xoffset > 0:
                # 'key' tile too far right, move one left
                self.key_tile_left -= 1
                self.key_tile_xoffset -= self.tile_width

            while self.key_tile_xoffset <= -self.tile_width:
                # 'key' tile too far left, move one right
                self.key_tile_left += 1
                self.key_tile_xoffset += self.tile_width
            self.key_tile_left = (self.key_tile_left + self.num_tiles_x) % self.num_tiles_x
        else:
            # not wrapping in X direction
            if self.map_width <= self.view_width:
                # if map <= view, don't drag, ensure centred
                self.key_tile_xoffset = (self.view_width - self.map_width) // 2
            else:
                # maybe drag, but don't expose background on left or right sides
                # remember old 'key' tile left value
                old_left = self.key_tile_left

                # move key tile by amount of X drag
                self.key_tile_xoffset -= delta_x

                while self.key_tile_xoffset > 0:
                    # 'key' tile too far right
                    self.key_tile_left -= 1
                    self.key_tile_xoffset -= self.tile_width

                while self.key_tile_xoffset <= -self.tile_width:
                    # 'key' tile too far left
                    self.key_tile_left += 1
                    self.key_tile_xoffset += self.tile_width
                self.key_tile_left = (self.key_tile_left + self.num_tiles_x) % self.num_tiles_x

                if delta_x < 0:
                    # was dragged to the right, don't allow left edge to show
                    if self.key_tile_left > old_left:
                        self.key_tile_left = 0
                        self.key_tile_xoffset = 0
                else:
                    # if dragged too far, reset key tile data
                    if self.key_tile_left > self.max_key_left:
                        self.key_tile_left = self.max_key_left
                        self.key_tile_xoffset = self.max_key_xoffset
                    elif self.key_tile_left == self.max_key_left:
                        if self.key_tile_xoffset < self.max_key_xoffset:
                            self.key_tile_xoffset = self.max_key_xoffset

        if self.wrap_y:
            # wrapping in Y direction, move 'key' tile
            self.key_tile_yoffset -= delta_y

            # normalize .key_tile_top value
            while self.key_tile_yoffset > 0:
                # 'key' tile too far right, move one left
                self.key_tile_top -= 1
                self.key_tile_yoffset -= self.tile_height

            while self.key_tile_yoffset <= -self.tile_height:
                # 'key' tile too far left, move one right
                self.key_tile_top += 1
                self.key_tile_yoffset += self.tile_height
            self.key_tile_top = (self.key_tile_top + self.num_tiles_y) % self.num_tiles_y
        else:
            # not wrapping in the Y direction
            if self.map_height <= self.view_height:
                # if map <= view, don't drag, ensure centred
                self.key_tile_yoffset = (self.view_height - self.map_height) // 2
            else:
                # remember old 'key' tile left value
                old_top = self.key_tile_top

                # map > view, allow drag, but don't go past the edge
                self.key_tile_yoffset -= delta_y

                while self.key_tile_yoffset > 0:
                    # 'key' tile too far right
                    self.key_tile_top -= 1
                    self.key_tile_yoffset -= self.tile_height

                while self.key_tile_yoffset <= -self.tile_height:
                    # 'key' tile too far left
                    self.key_tile_top += 1
                    self.key_tile_yoffset += self.tile_height
                self.key_tile_top = (self.key_tile_top + self.num_tiles_y) % self.num_tiles_y

                if delta_y < 0:
                    # was dragged to the top, don't allow bottom edge to show
                    if self.key_tile_top > old_top:
                        self.key_tile_top = 0
                        self.key_tile_yoffset = 0
                else:
                    # if dragged too far, reset key tile data
                    if self.key_tile_top > self.max_key_top:
                        self.key_tile_top = self.max_key_top
                        self.key_tile_yoffset = self.max_key_yoffset
                    elif self.key_tile_top == self.max_key_top:
                        if self.key_tile_yoffset < self.max_key_yoffset:
                            self.key_tile_yoffset = self.max_key_yoffset

    def tile_frac_to_parts(self, t_frac, length):
        """Split a tile coordinate into integer and fractional parts.

        frac  a fractional tile coordinate
        length  size of tile width or height

        Return (int, frac) parts of 't_frac'.
        """

        int_part = int(t_frac)
        frac_part = int((t_frac - int_part) * length)

        return int_part, frac_part

    # UNUSED
    def tile_parts_to_frac(self, t_coord, t_offset, length):
        """Convert a tile coord plus offset to a fractional tile value.

        t_coord   the tile integer coordinate
        t_offset  the pixel further offset
        length    the width orr height of the tile

        Returns a fractional tile coordinate.
        """

        return t_coord + t_offset / length

    # UNUSED
    def zoom_tile(self, c_tile, scale):
        """Zoom into centre tile at given scale.

        c_tile  tuple (x_frac, y_frac) of fractional tile coords for point
        scale   2.0 if zooming in, 0.5 if zooming out

        Returns a tuple (zx_frac, zy_frac) of fractional coordinates of the
        point after the zoom.
        """

        # unpack the centre tile coords
        (x_frac, y_frac) = c_tile

        # convert tile fractional coords to tile # + offset
        (tile_left, tile_xoff) = self.tile_frac_to_parts(x_frac, self.tile_width)
        (tile_top, tile_yoff) = self.tile_frac_to_parts(y_frac, self.tile_height)

        if scale > 1:
            # assume scale is 2
            # a simple doubling of fractional coordinates
            if tile_xoff < self.tile_width // 2:
                tile_left = tile_left * 2
                tile_xoff = tile_xoff * 2
            else:
                tile_left = tile_left * 2 + 1
                tile_xoff = tile_xoff * 2 - self.tile_width

            if tile_yoff < self.tile_height // 2:
                tile_top = tile_top * 2
                tile_yoff = tile_yoff * 2
            else:
                tile_top = tile_top * 2 + 1
                tile_yoff = tile_yoff * 2 % self.tile_height
        else:
            # assume scale is 0.5
            # a simple halving of fractional coordinates
            tile_left = tile_left // 2
            if tile_left % 2 == 0:
                # point in left half of 2x2
                tile_xoff = tile_xoff // 2
            else:
                # point in right half of 2x2
                tile_xoff = (tile_xoff + self.tile_width) // 2

            tile_top = tile_top // 2
            if tile_top % 2 == 0:
                # point in top half of 2x2
                tile_yoff = tile_yoff // 2
            else:
                # point in bottom half of 2x2
                tile_yoff = (tile_yoff + self.tile_height) // 2

        zx_frac = self.tile_parts_to_frac(tile_left, tile_xoff, self.tile_width)
        zy_frac = self.tile_parts_to_frac(tile_top, tile_yoff, self.tile_height)

        return zx_frac, zy_frac

    # def add_layer(self,
    #               painter,
    #               data: List,
    #               map_rel: bool,
    #               visible: bool,
    #               show_levels: List[int],
    #               selectable: bool,
    #               name: str,
    #               ltype: int):
    #     """Add a generic layer to the system.
    #
    #     painter      the function used to paint the layer
    #     data         actual layer data (depends on layer type)
    #     map_rel      True if points are map relative, else view relative
    #     visible      True if layer is to be immediately shown, else False
    #     show_levels  list of levels at which to auto-show the layer
    #     selectable   True if select operates on this layer
    #     name         name for this layer
    #     ltype        flag for layer 'type'
    #
    #     Returns unique ID of the new layer.
    #     """
    #
    #     # get unique layer ID
    #     layer_id = self.next_layer_id
    #     self.next_layer_id += 1
    #
    #     # prepare the show_level value
    #     if show_levels is None:
    #         show_levels = range(self.tiles_min_level, self.tiles_max_level + 1)[:]
    #
    #     # create layer, add unique ID to Z order list
    #     layer = MapLayer(layer_id=layer_id,
    #                      painter=painter,
    #                      data=data,
    #                      map_rel=map_rel,
    #                      visible=visible,
    #                      show_levels=show_levels,
    #                      selectable=selectable,
    #                      name=name,
    #                      ltype=ltype)
    #
    #     self.layer_mapping[layer_id] = layer
    #     self.layer_z_order.append(layer_id)
    #
    #     # force display of new layer if it's visible
    #     if visible:
    #         self.update()
    #
    #     return layer_id

    def getLayer(self, lid) -> Union[PointLayer, PolygonLayer, PolylineLayer, TextLayer, ImageLayer]:
        """
        Get a layer
        :param lid:
        :return:
        """
        return self.layer_mapping[lid]

    def setLayerData(self, lid: int, data: List) -> None:
        """

        :param lid:
        :param data:
        :return:
        """
        self.layer_mapping[lid].data = data

    def setLayerSelectable(self, lid: int, selectable: bool = False) -> None:
        """Update the .selectable attribute for a layer.

        lid         ID of the layer we are going to update
        selectable  new .selectable attribute value (True or False)
        """

        # just in case id is None
        if lid:
            layer = self.layer_mapping[lid]
            layer.selectable = selectable

    def draw_point_layer(self, painter: QPainter, data: List[PointData], map_rel: bool):
        """Draw a points layer.

        draw_context    the active device context to draw on
        data            an iterable of point tuples:
                        (x, y, place, radius, colour, x_off, y_off, udata)
        map_rel         points relative to map if True, else relative to view
        """

        # speed up drawing by caching the current pen colour
        cache_pcolour = None

        # draw points on map/view
        for entry in data:

            if map_rel:
                pt, ex = self.pex_point(place=entry.placement,
                                        xgeo=entry.x,
                                        ygeo=entry.y,
                                        x_off=entry.offset_x,
                                        y_off=entry.offset_y,
                                        radius=entry.radius)
            else:
                pt, ex = self.pex_point_view(place=entry.placement,
                                             xview=entry.x,
                                             yview=entry.y,
                                             x_off=entry.offset_x,
                                             y_off=entry.offset_y,
                                             radius=entry.radius)

            if pt and entry.radius:  # don't draw if not on screen or zero radius
                if cache_pcolour != entry.colour:
                    qcolour = QColor(*entry.colour)
                    pen = QPen(qcolour, entry.radius, Qt.SolidLine)
                    painter.setPen(pen)
                    painter.setBrush(qcolour)
                    cache_pcolour = entry.colour
                pt_x, pt_y = pt
                painter.drawEllipse(QPoint(pt_x, pt_y), entry.radius, entry.radius)

    def draw_image_layer(self, painter: QPainter, images: List[ImageData], map_rel):
        """Draw an image Layer on the view.

        draw_context       the active device context to draw on
        images             a sequence of image tuple sequences
                           (x,y,pmap,w,h,placement,offset_x,offset_y,idata)
        map_rel            points relative to map if True, else relative to view
        """

        # get correct pex function
        # we do this once here rather than many times inside the loop
        # pex = self.pex_extent_view
        # if map_rel:
        #     pex = self.pex_extent

        # speed up drawing by caching previous point colour
        cache_pcolour = None

        # draw the images
        # (lon, lat, pmap, w, h, place, x_off, y_off, pradius, pcolour, idata)
        for entry in images:

            # place, xgeo, ygeo, x_off, y_off, w, h, image
            if map_rel:
                pt, ex = self.pex_extent(place=entry.placement,
                                         xgeo=entry.lon,
                                         ygeo=entry.lat,
                                         x_off=entry.offset_x,
                                         y_off=entry.offset_y,
                                         w=entry.w,
                                         h=entry.h,
                                         image=True)
            else:
                pt, ex = self.pex_extent_view(place=entry.placement,
                                              xview=entry.lon,
                                              yview=entry.lat,
                                              x_off=entry.offset_x,
                                              y_off=entry.offset_y,
                                              w=entry.w,
                                              h=entry.h,
                                              image=True)

            if pt and entry.radius:
                # if we need to change colours
                if cache_pcolour != entry.colour:
                    qcolour = QColor(*entry.colour)
                    pen = QPen(qcolour, entry.radius, Qt.SolidLine)
                    painter.setPen(pen)
                    painter.setBrush(qcolour)
                    cache_pcolour = entry.colour

                # draw the image 'point'
                (px, py) = pt
                painter.drawEllipse(QPoint(px, py), entry.radius, entry.radius)

            if ex:
                # draw the image itself
                (ix, _, iy, _) = ex
                painter.drawPixmap(QPoint(ix, iy), entry.pmap)

    def draw_text_layer(self, painter: QPainter, data: List[TextData], map_rel: bool):
        """Draw a text Layer on the view.

        draw_context       the active device context to draw on
        text               a list of TextData
        map_rel            points relative to map if True, else relative to view
        """

        # get correct pex function for mode (map/view)
        pex = self.pex_extent_view
        if map_rel:
            pex = self.pex_extent

        # set some caching to speed up mostly unchanging data
        cache_textcolour = None
        cache_font = None
        cache_colour = None

        # draw text on map/view
        # (lon, lat, tdata, place, radius, colour, textcolour, fontname, fontsize, x_off, y_off, data)
        for entry in data:
            # set font characteristics so we can calculate text width/height
            if cache_font != (entry.fontname, entry.fontsize):
                font = QFont(entry.fontname, entry.fontsize)
                painter.setFont(font)
                cache_font = (entry.fontname, entry.fontsize)
                font_metrics = QFontMetrics(font)
            else:
                font_metrics = QFontMetrics(cache_font)

            qrect = font_metrics.boundingRect(entry.tdata)
            w = qrect.width()  # text string width and height
            h = qrect.height()

            # get point + extent information (each can be None if off-view)
            if map_rel:
                (pt, ex) = self.pex_extent(place=entry.placement,
                                           xgeo=entry.lon,
                                           ygeo=entry.lat,
                                           x_off=entry.offset_x,
                                           y_off=entry.offset_y,
                                           w=w,
                                           h=h)
            else:
                (pt, ex) = self.pex_extent_view(place=entry.placement,
                                                xview=entry.lon,
                                                yview=entry.lat,
                                                x_off=entry.offset_x,
                                                y_off=entry.offset_y,
                                                w=w,
                                                h=h)

            if pt and entry.radius:  # don't draw point if off screen or zero radius
                (pt_x, pt_y) = pt
                if cache_colour != entry.colour:
                    qcolour = QColor(*entry.colour)
                    pen = QPen(qcolour, entry.radius, Qt.SolidLine)
                    painter.setPen(pen)
                    painter.setBrush(qcolour)
                    cache_colour = entry.colour
                painter.drawEllipse(QPoint(pt_x, pt_y), entry.radius, entry.radius)

            if ex:  # don't draw text if off screen
                (lx, _, _, by) = ex
                if cache_textcolour != entry.textcolour:
                    qcolour = QColor(*entry.textcolour)
                    pen = QPen(qcolour, entry.radius, Qt.SolidLine)
                    painter.setPen(pen)
                    cache_textcolour = entry.textcolour
                painter.drawText(QPointF(lx, by), entry.tdata)

    def draw_polygon_layer(self, painter: QPainter, data: List[PolygonData], map_rel: bool):
        """Draw a polygon layer.

        draw_context       the active device context to draw on
        data               an iterable of polygon tuples:
                           (p, placement, width, colour, closed,
                           filled, fillcolour, offset_x, offset_y, udata)
                           where p is an iterable of points: (x, y)
        map_rel            points relative to map if True, else relative to view
        """

        # draw polygons
        cache_colour_width = None  # speed up mostly unchanging data
        cache_fillcolour = (0, 0, 0, 0)

        painter.setBrush(QBrush(QColor(*cache_fillcolour)))  # initial brush is transparent

        # (p, place, width, colour, closed, filled, fillcolour, x_off, y_off, udata)
        for entry in data:

            if map_rel:
                poly, extent = self.pex_polygon(place=entry.placement,
                                                poly=entry.p,
                                                x_off=entry.offset_x,
                                                y_off=entry.offset_y)
            else:
                poly, extent = self.pex_polygon_view(place=entry.placement,
                                                     poly=entry.p,
                                                     x_off=entry.offset_x,
                                                     y_off=entry.offset_y)

            if poly:
                if (entry.colour, entry.width) != cache_colour_width:
                    painter.setPen(QPen(QColor(*entry.colour), entry.width, Qt.SolidLine))
                    cache_colour = (entry.colour, entry.width)

                if entry.filled and (entry.fillcolour != cache_fillcolour):
                    painter.setBrush(QBrush(QColor(*entry.fillcolour), Qt.SolidPattern))
                    cache_fillcolour = entry.fillcolour

                qpoly = [QPoint(*p) for p in poly]
                painter.drawPolygon(QPolygon(qpoly))

    def draw_polyline_layer(self, painter: QPainter, data: List[PolylineData], map_rel: bool):
        """Draw a polyline layer.

        draw_context      the active device context to draw on
        data              an iterable of polyline tuples:
                          (p, placement, width, colour, offset_x, offset_y, udata)
                          where p is an iterable of points: (x, y)
        map_rel           points relative to map if True, else relative to view
        """

        # brush is always transparent
        painter.setBrush(QBrush(QColor(0, 0, 0, 0)))

        # draw polyline(s)
        cache_colour_width = None  # speed up mostly unchanging data

        for entry in data:

            if map_rel:
                poly, extent = self.pex_polygon(place=entry.placement,
                                                poly=entry.polyline,
                                                x_off=entry.offset_x,
                                                y_off=entry.offset_y)
            else:
                poly, extent = self.pex_polygon_view(place=entry.placement,
                                                     poly=entry.polyline,
                                                     x_off=entry.offset_x,
                                                     y_off=entry.offset_y)

            if poly:
                if cache_colour_width != (entry.colour, entry.width):
                    painter.setPen(QPen(QColor(*entry.colour), entry.width, Qt.SolidLine))
                    cache_colour_width = (entry.colour, entry.width)

                polygon = QPolygon([QPoint(x, y) for x, y in poly])
                painter.drawPolyline(polygon)

    def geo_to_view(self, xgeo: float, ygeo: float) -> Union[None, Tuple[float, float]]:
        """Convert a geo coord to view.

        geo  tuple (xgeo, ygeo)

        Return a tuple (xview, yview) in view coordinates.
        Assumes point is in view.
        """

        # convert the Geo position to tile coordinates
        if xgeo is not None:
            tx, ty = self.tile_src.Geo2Tile(xgeo, ygeo)

            # using the key_tile_* variables to convert to view coordinates
            xview = (tx - self.key_tile_left) * self.tile_width + self.key_tile_xoffset
            yview = (ty - self.key_tile_top) * self.tile_height + self.key_tile_yoffset

            return xview, yview
        else:
            return None

    # UNUSED
    def geo_to_view_masked(self, xgeo: float, ygeo: float) -> Union[None, Tuple[float, float]]:
        """Convert a geo (lon+lat) position to view pixel coords.

        geo  tuple (xgeo, ygeo)

        Return a tuple (xview, yview) of point if on-view,or None
        if point is off-view.
        """

        if self.view_llon <= xgeo <= self.view_rlon and self.view_blat <= ygeo <= self.view_tlat:
            return self.geo_to_view(xgeo, ygeo)

        return None

    def view_to_geo(self, xview: float, yview: float) -> Tuple[Union[None, float], Union[None, float]]:
        """Convert a view coords position to a geo coords position.

        view  tuple of view coords (xview, yview)

        Returns a tuple of geo coords (xgeo, ygeo) if the cursor is over map
        tiles, else returns None.

        Note: the 'key' tile information must be correct.
        """

        min_xgeo, max_xgeo, min_ygeo, max_ygeo = self.tile_src.GetExtent()

        x_from_key = xview - self.key_tile_xoffset
        y_from_key = yview - self.key_tile_yoffset

        # get view point as tile coordinates
        xtile = self.key_tile_left + x_from_key / self.tile_width
        ytile = self.key_tile_top + y_from_key / self.tile_height

        xgeo, ygeo = self.tile_src.Tile2Geo(xtile, ytile)

        if self.wrap_x and self.wrap_y:
            return xgeo, ygeo

        if not self.wrap_x:
            if not (min_xgeo <= xgeo <= max_xgeo):
                return None, None

        if not self.wrap_y:
            if not (min_ygeo <= ygeo <= max_ygeo):
                return None, None

        return xgeo, ygeo

    ######
    # PEX - Point & EXtension.
    #
    # These functions encapsulate the code that finds the extent of an object.
    # They all return a tuple (point, extent) where 'point' is the placement
    # point of an object (or list of points for a polygon) and an 'extent'
    # tuple (lx, rx, ty, by) [left, right, top, bottom].
    ######

    def pex_point(self, place: Place, xgeo: float, ygeo: float, x_off: float, y_off: float, radius: float):
        """Convert point object geo position to point & extent in view coords.

        place         placement string
        geo           point position tuple (xgeo, ygeo)
        x_off, y_off  X and Y offsets
        radius        radius of the point

        Return a tuple of point and extent origins (point, extent) where 'point'
        is (px, py) and extent is (elx, erx, ety, eby) (both in view coords).
        Return None for extent if extent is completely off-view.

        The 'extent' here is the extent of the point+radius.
        """

        # get point view coords
        xview, yview = self.geo_to_view(xgeo, ygeo)
        point = self.point_placement(place, xview, yview, x_off, y_off)
        (px, py) = point

        # extent = (left, right, top, bottom) in view coords
        elx = px - radius
        erx = px + radius
        ety = py - radius
        eby = py + radius
        extent = (elx, erx, ety, eby)

        # decide if point extent is off-view
        if erx < 0 or elx > self.view_width or eby < 0 or ety > self.view_height:
            extent = None

        return point, extent

    def pex_point_view(self, place: Place, xview: float, yview: float, x_off: float, y_off: float, radius: float):
        """Convert point object view position to point & extent in view coords.

        place         placement string
        view          point position tuple (xview, yview)
        x_off, y_off  X and Y offsets

        Return a tuple of point and extent origins (point, extent) where 'point'
        is (px, py) and extent is (elx, erx, ety, eby) (both in view coords).
        Return None for point or extent if completely off-view.

        The 'extent' here is the extent of the point+radius.
        """

        # get point view coords and perturb point to placement
        point = self.point_placement_view(place, xview, yview, x_off, y_off)
        (px, py) = point

        # extent = (left, right, top, bottom) in view coords
        elx = px - radius
        erx = px + radius
        ety = py - radius
        eby = py + radius
        extent = (elx, erx, ety, eby)

        # decide if extent is off-view
        if erx < 0 or elx > self.view_width or eby < 0 or ety > self.view_height:
            extent = None

        return point, extent

    def pex_extent(self, place: Place, xgeo: float, ygeo: float, x_off: float, y_off: float, w: int, h: int,
                   image=False):
        """Convert object geo position to position & extent in view coords.

        place         placement string
        geo           point position tuple (xgeo, ygeo)
        x_off, y_off  X and Y offsets
        w, h          width and height of extent in pixels
        image         True if we are placing an image.  Required because an image
                      and text extents have DIFFERENT ORIGINS!

        Return a tuple ((px, py), (elx, erx, ety, eby)) of point and extent
        data where '(px, py)' is the point and '(elx, erx, ety, eby)' is the
        extent.  Both point and extent are in view coordinates.

        Return None for point or extent if either is completely off-view.

        An extent object can be either an image object or a text object.
        """

        # get point view coords
        vpoint = self.geo_to_view(xgeo, ygeo)
        (vpx, vpy) = vpoint

        # get extent limits
        # must take into account 'place', 'x_off' and 'y_off'
        point = self.extent_placement(place, vpx, vpy, x_off, y_off, w, h, image=image)
        (px, py) = point

        # extent = (left, right, top, bottom) in view coords
        # this is different for images
        elx = px
        erx = px + w
        if image:
            ety = py
            eby = py + h
        else:
            ety = py - h
            eby = py

        extent = (elx, erx, ety, eby)

        # decide if point is off-view
        if vpx < 0 or vpx > self.view_width or vpy < 0 or vpy > self.view_height:
            vpoint = None

        # decide if extent is off-view
        if erx < 0 or elx > self.view_width or eby < 0 or ety > self.view_height:
            # no extent if ALL of extent is off-view
            extent = None

        return vpoint, extent

    def pex_extent_view(self, place, xview, yview, x_off, y_off, w, h, image=False):
        """Convert object view position to point & extent in view coords.

        place         placement string
        view          point position tuple (xview, yview) (view coords)
        x_off, y_off  X and Y offsets
        w, h          width and height of extent in pixels
        image         True if we are placing an image.  Required because an image
                      and text extents have DIFFERENT ORIGINS!

        Return a tuple of point and extent origins (point, extent) where 'point'
        is (px, py) and extent is (elx, erx, ety, eby) (both in view coords).
        Return None for extent if extent is completely off-view.

        Takes size of extent object into consideration.
        """

        # get point view coords and perturb point to placement origin
        # we ignore offsets for the point as they apply to the extent only

        point = self.point_placement_view(place, xview, yview, 0, 0)

        # get extent view coords (ix and iy)
        (px, py) = point
        (ix, iy) = self.extent_placement(place, px, py, x_off, y_off, w, h, image=False)

        # extent = (left, right, top, bottom) in view coords
        # this is different for images
        if image:
            # perturb extent coords to edges of image
            if place == Place.Center:
                elx = px - w / 2
                ety = py - h / 2
            elif place == Place.CenterNorth:
                elx = px - w / 2
                ety = py + y_off
            elif place == Place.NorthEast:
                elx = px - w - x_off
                ety = py + y_off
            elif place == Place.CenterEast:
                elx = px - w - x_off
                ety = py - h / 2
            elif place == Place.SouthEast:
                elx = px - w - x_off
                ety = py - h - y_off
            elif place == Place.CenterSouth:
                elx = px - w / 2
                ety = py - h - y_off
            elif place == Place.SouthWest:
                elx = px + x_off
                ety = py - h - y_off
            elif place == Place.CenterWest:
                elx = px + x_off
                ety = py - h / 2
            elif place == Place.NorthWest:
                elx = px + x_off
                ety = py + y_off
            else:
                raise Exception('Unsupported place: ' + place)

            erx = elx + w
            eby = ety + h
        else:
            elx = ix
            erx = ix + w
            ety = iy - h
            eby = iy

        extent = (elx, erx, ety, eby)

        # decide if point is off-view
        if px < 0 or px > self.view_width or py < 0 or py > self.view_height:
            point = None

        # decide if extent is off-view
        if erx < 0 or elx > self.view_width or eby < 0 or ety > self.view_height:
            extent = None

        return point, extent

    def pex_polygon(self, place: Place, poly: List[Tuple[float, float]], x_off: float, y_off: float):
        """Convert polygon/line obj geo position to points & extent in view coords.

        place         placement
        poly          list of point position tuples (xgeo, ygeo)
        x_off, y_off  X and Y offsets

        Return a tuple of point and extent (point, extent) where 'point' is a
        list of (px, py) and extent is (elx, erx, ety, eby) (both in view coords).
        Return None for extent if extent is completely off-view.
        """

        # get polygon/line points in perturbed view coordinates
        view_points = []
        for xgeo, ygeo in poly:
            xview, yview = self.geo_to_view(xgeo, ygeo)
            point = self.point_placement(place, xview, yview, x_off, y_off)
            view_points.append(point)

        # extent = (left, right, top, bottom) in view coords
        elx = min(view_points, key=lambda x: x[0])[0]
        erx = max(view_points, key=lambda x: x[0])[0]
        ety = min(view_points, key=lambda x: x[1])[1]
        eby = max(view_points, key=lambda x: x[1])[1]
        extent = (elx, erx, ety, eby)

        # decide if extent is off-view
        res_ex = None  # assume extent is off-view
        for px, py in view_points:
            if (0 <= px < self.view_width) and (0 <= py < self.view_height):
                res_ex = extent  # at least some of extent is on-view
                break

        return view_points, res_ex

    def pex_polygon_view(self, place: Place, poly: List[Tuple[float, float]], x_off: float, y_off: float):
        """Convert polygon/line obj view position to points & extent in view coords.

        place         placement string
        poly          list of point position tuples (xview, yview)
        x_off, y_off  X and Y offsets

        Return a tuple of point and extent origins (point, extent) where 'point'
        is a list of (px, py) and extent is (elx, erx, ety, eby) (both in view
        coords).  Return None for extent if extent is completely off-view.
        """

        # get polygon/line points in view coordinates
        view = []
        for (xview, yview) in poly:
            point = self.point_placement_view(place, xview, yview, x_off, y_off)
            view.append(point)

        # get extent - max/min x and y
        # extent = (left, right, top, bottom) in view coords
        elx = min(view, key=lambda x: x[0])[0]
        erx = max(view, key=lambda x: x[0])[0]
        ety = min(view, key=lambda x: x[1])[1]
        eby = max(view, key=lambda x: x[1])[1]
        extent = (elx, erx, ety, eby)

        # decide if polygon/line or extent are off-view
        res_ex = None
        for (px, py) in view:
            if (0 <= px < self.view_width) and (0 <= py < self.view_height):
                res_ex = extent
                break

        return view, res_ex

    ######
    # Placement routines instead of original 'exec' code.
    # Code in test_assumptions.py shows this is faster.
    ######

    @staticmethod
    def point_placement(place: Place, x: float, y: float, x_off: float, y_off: float):
        """Perform map-relative placement for a single point.

        place         placement key string
        x, y          point view coordinates
        x_off, y_off  the X and Y offset values

        Returns a tuple (x, y) in view coordinates.
        """

        # adjust the X, Y coordinates relative to the origin
        if place == Place.Center:
            pass
        elif place == Place.NorthWest:
            x += x_off
            y += y_off
        elif place == Place.CenterNorth:
            y += y_off
        elif place == Place.NorthEast:
            x += -x_off
            y += y_off
        elif place == Place.CenterEast:
            x += -x_off
        elif place == Place.SouthEast:
            x += -x_off
            y += -y_off
        elif place == Place.CenterSouth:
            y += -y_off
        elif place == Place.SouthWest:
            x += x_off
            y += -y_off
        elif place == Place.CenterWest:
            x += x_off
        else:
            raise Exception('Unsupported place: ' + place.value)

        return x, y

    def point_placement_view(self, place: Place, x: float, y: float, x_off: float, y_off: float):
        """Perform view-relative placement for a single point.

        place         placement key string
        x, y          point view coordinates
        x_off, y_off  the X and Y offset values

        Returns a tuple (x, y) in view coordinates.
        """

        dcw = self.view_width
        dch = self.view_height
        dcw2 = dcw / 2
        dch2 = dch / 2

        # adjust the X, Y coordinates relative to the origin
        # offsets are always away from the nearest edge
        if place == Place.Center:
            x += dcw2
            y += dch2
        elif place == Place.NorthWest:
            x += x_off
            y += y_off
        elif place == Place.CenterNorth:
            x += dcw2
            y += y_off
        elif place == Place.NorthEast:
            x += dcw - x_off
            y += y_off
        elif place == Place.CenterEast:
            x += dcw - x_off
            y += dch2
        elif place == Place.SouthEast:
            x += dcw - x_off
            y += dch - y_off
        elif place == Place.CenterSouth:
            x += dcw2
            y += dch - y_off
        elif place == Place.SouthWest:
            x += x_off
            y += dch - y_off
        elif place == Place.CenterWest:
            x += x_off
            y += dch2
        else:
            raise Exception('Unsupported place: ' + place.value)

        return x, y

    @staticmethod
    def extent_placement(place: Place, x: float, y: float, x_off: float, y_off: float, w: int, h: int,
                         image: bool = False):
        """Perform map-relative placement of an extent.

        place         placement key string
        x, y          view coords of point
        x_off, y_off  offset from point (pixels)
        w, h          width, height of the extent (pixels)
        image         True if we are placing an image.  Required because an image
                      and text extents have DIFFERENT ORIGINS!

        Returns a tuple (x, y).
        """

        w2 = w / 2
        h2 = h / 2

        if image:
            if place == Place.Center:
                x += -w2
                y += -h2
            elif place == Place.NorthWest:
                x += x_off
                y += y_off
            elif place == Place.CenterNorth:
                x += -w2
                y += y_off
            elif place == Place.NorthEast:
                x += -x_off - w
                y += y_off
            elif place == Place.CenterEast:
                x += -x_off - w
                y += -h2
            elif place == Place.SouthEast:
                x += -x_off - w
                y += -y_off - h
            elif place == Place.CenterSouth:
                x += -w2
                y += -y_off - h
            elif place == Place.SouthWest:
                x += x_off
                y += -y_off - h
            elif place == Place.CenterWest:
                x += x_off
                y += -h2
            else:
                raise Exception('Unsupported place: ' + place.value)
        else:
            if place == Place.Center:
                x += -w2
                y += h2
            elif place == Place.NorthWest:
                x += x_off
                y += y_off + h
            elif place == Place.CenterNorth:
                x += -w2
                y += y_off + h
            elif place == Place.NorthEast:
                x += -x_off - w
                y += y_off + h
            elif place == Place.CenterEast:
                x += -x_off - w
                y += h2
            elif place == Place.SouthEast:
                x += -x_off - w
                y += -y_off
            elif place == Place.CenterSouth:
                x += -w2
                y += -y_off
            elif place == Place.SouthWest:
                x += x_off
                y += -y_off
            elif place == Place.CenterWest:
                x += x_off
                y += h2
            else:
                raise Exception('Unsupported place: ' + place.value)

        return x, y

    def zoom_level(self, level: int, view_x: int = None, view_y: int = None):
        """Zoom to a map level.

        level  map level to zoom to
        view   view coords of cursor
               (if not given, assume view centre)

        Change the map zoom level to that given. Returns True if the zoom
        succeeded, else False. If False is returned the method call has no effect.
        Same operation as .GotoLevel() except we try to maintain the geo position
        under the cursor.
        """

        # log(f'zoom_level: level={level}, view={view_x, view_y}')

        # if not given cursor coords, assume view centre
        if view_x is None:
            view_x = self.view_width // 2

        if view_y is None:
            view_y = self.view_height // 2

        # get geo coords of view point
        xgeo, ygeo = self.view_to_geo(view_x, view_y)

        # get tile source to use the new level
        result = self.tile_src.UseLevel(level)

        if result:
            # zoom worked, adjust state variables
            self.level = level

            # move to new level
            self.num_tiles_x, self.num_tiles_y, _, _ = self.tile_src.GetInfo(level)
            self.map_width = self.num_tiles_x * self.tile_width
            self.map_height = self.num_tiles_y * self.tile_height
            self.map_llon, self.map_rlon, self.map_blat, self.map_tlat = self.tile_src.extent

            # finally, pan to original map centre (updates widget)
            self.pan_position(xgeo, ygeo, view_x, view_y)

            # to set some state variables
            self.resizeEvent()

            # raise the EVT_PYSLIPQT_LEVEL event
            LevelEvent(level=level).emit_event()

        self.zoom_callback(level)

        return result

    def pan_position(self, xgeo: float, ygeo: float, view_x: int = None, view_y: int = None):
        """Pan the given geo position in the current map zoom level.

        geo   a tuple (xgeo, ygeo)
        view  a tuple of view coordinates (view_x, view_y)
              (if not given, assume view centre)

        We just adjust the key tile to place the required geo position at the
        given view coordinates.  If that is not possible, just centre in either
        the X or Y directions, or both.
        """

        # log(f'pan_position: geo={xgeo, ygeo}, view={view_x, view_y}')

        # if not given a "view", assume the view centre coordinates
        if view_x is None:
            view_x = self.view_width // 2

        if view_y is None:
            view_y = self.view_height // 2

        # log(f'view_x={view_x}, view_y={view_y}')

        if xgeo is None:
            return

        # convert the geo posn to a tile position
        (tile_x, tile_y) = self.tile_src.Geo2Tile(xgeo, ygeo)

        # determine what the new key tile should be
        # figure out number of tiles from centre point to edges
        tx = view_x / self.tile_width
        ty = view_y / self.tile_height

        # calculate tile coordinates of the top-left corner of the view
        key_tx = tile_x - tx
        key_ty = tile_y - ty

        (key_tile_left, x_offset) = divmod(key_tx, 1)
        self.key_tile_left = int(key_tile_left)
        self.key_tile_xoffset = -int(x_offset * self.tile_width)

        (key_tile_top, y_offset) = divmod(key_ty, 1)
        self.key_tile_top = int(key_tile_top)
        self.key_tile_yoffset = -int(y_offset * self.tile_height)

        # adjust key tile, if necessary
        self.rectify_key_tile()

        # redraw the widget
        self.update()

    def rectify_key_tile(self) -> None:
        """Adjust state variables to ensure map centred if map is smaller than
        view.  Otherwise don't allow edges to be exposed.

        Adjusts the "key" tile variables to ensure proper presentation.

        Relies on .map_width, .map_height and .key_tile_* being set.
        """

        # check map in X direction
        if self.map_width < self.view_width:
            # map < view, fits totally in view, centre in X
            self.key_tile_left = 0
            self.key_tile_xoffset = (self.view_width - self.map_width) // 2
        else:
            # if key tile out of map in X direction, rectify
            if self.key_tile_left < 0:
                self.key_tile_left = 0
                self.key_tile_xoffset = 0
            else:
                # if map left/right edges showing, cover them
                show_len = (self.num_tiles_x - self.key_tile_left) * self.tile_width + self.key_tile_xoffset
                if show_len < self.view_width:
                    # figure out key tile X to have right edge of map and view equal
                    tiles_showing = self.view_width / self.tile_width
                    int_tiles = int(tiles_showing)
                    self.key_tile_left = self.num_tiles_x - int_tiles - 1
                    self.key_tile_xoffset = -int((1.0 - (tiles_showing - int_tiles)) * self.tile_width)

        # now check map in Y direction
        if self.map_height < self.view_height:
            # map < view, fits totally in view, centre in Y
            self.key_tile_top = 0
            self.key_tile_yoffset = (self.view_height - self.map_height) // 2
        else:
            if self.key_tile_top < 0:
                # map top edge showing, cover
                self.key_tile_top = 0
                self.key_tile_yoffset = 0
            else:
                # if map bottom edge showing, cover
                show_len = (self.num_tiles_y - self.key_tile_top) * self.tile_height + self.key_tile_yoffset
                if show_len < self.view_height:
                    # figure out key tile Y to have bottom edge of map and view equal
                    tiles_showing = self.view_height / self.tile_height
                    int_tiles = int(tiles_showing)
                    self.key_tile_top = self.num_tiles_y - int_tiles - 1
                    self.key_tile_yoffset = -int((1.0 - (tiles_showing - int_tiles)) * self.tile_height)

    def zoom_level_position(self, level: int, xgeo: float, ygeo: float):
        """Zoom to a map level and pan to the given position in the map.

        level  map level to zoom to
        posn  a tuple (xgeo, ygeo)
        """

        if self.zoom_level(level):
            self.pan_position(xgeo, ygeo)

    def get_i18n_kw(self, kwargs, kws, default):
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

    def get_level_and_position(self, place=Place.Center):
        """Get the level and geo position of a cardinal point within the view.

        place  a placement string specifying the point in the view
               for which we require the geo position

        Returns a tuple (level, geo) where 'geo' is (geo_x, geo_y).
        """

        view_x, view_y = self.point_placement_view(place, 0, 0, 0, 0, )
        xgeo, ygeo = self.view_to_geo(view_x, view_y)

        return self.level, xgeo, ygeo

    def set_key_from_centre(self, xgeo: float, ygeo: float):
        """Set 'key' tile stuff from given geo at view centre.

        geo  geo coords of centre of view

        We need to assume little about which state variables are set.
        Only assume these are set:
            self.tile_width
            self.tile_height
        """
        if xgeo is None:
            return

        ctile_tx, ctile_ty = self.tile_src.Geo2Tile(xgeo, ygeo)

        int_ctile_tx = int(ctile_tx)
        int_ctile_ty = int(ctile_ty)

        frac_ctile_tx = ctile_tx - int_ctile_tx
        frac_ctile_ty = ctile_ty - int_ctile_ty

        ctile_xoff = self.view_width // 2 - self.tile_width * frac_ctile_tx
        ctile_yoff = self.view_height // 2 - self.tile_height * frac_ctile_ty

        num_whole_x = ctile_xoff // self.tile_width
        num_whole_y = ctile_yoff // self.tile_height

        xmargin = ctile_xoff - num_whole_x * self.tile_width
        ymargin = ctile_yoff - num_whole_y * self.tile_height

        # update the 'key' tile state variables
        self.key_tile_left = int_ctile_tx - num_whole_x - 1
        self.key_tile_top = int_ctile_ty - num_whole_y - 1
        self.key_tile_xoffset = self.tile_width - xmargin
        self.key_tile_yoffset = self.tile_height - ymargin

        # centre map in view if map < view
        if self.key_tile_left < 0:
            self.key_tile_left = 0
            self.key_tile_xoffset = (self.view_width - self.map_width) // 2

        if self.key_tile_top < 0:
            self.key_tile_top = 0
            self.key_tile_yoffset = (self.view_height - self.map_height) // 2

    ######
    #
    ######

    @staticmethod
    def colour_to_internal(colour: Union[str, QColor, Tuple[int, int, int, int]]):
        """
        Convert a colour in one of various forms to an internal format.

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
                msg = ("Colour value '%s' is not in the form '(r, g, b, a)'"
                       % str(colour))
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

    def sel_box_canonical(self):
        """'Canonicalize' a selection box limits.

        Uses instance variables (all in view coordinates):
            self.sbox_1_x    X position of box select start
            self.sbox_1_y    Y position of box select start
            self.sbox_w      width of selection box (start to finish)
            self.sbox_h      height of selection box (start to finish)

        Four ways to draw the selection box (starting in each of the four
        corners), so four cases.

        The sign of the width/height values are decided with respect to the
        origin at view top-left corner.  That is, a negative width means
        the box was started at the right and swept to the left.  A negative
        height means the selection started low and swept high in the view.

        Returns a tuple (llx, llr, urx, ury) where llx is lower left X, ury is
        upper right corner Y, etc.  All returned values in view coordinates.
        """

        if self.sbox_h >= 0:
            if self.sbox_w >= 0:
                # 2
                ll_corner_vx = self.sbox_1_x
                ll_corner_vy = self.sbox_1_y + self.sbox_h
                tr_corner_vx = self.sbox_1_x + self.sbox_w
                tr_corner_vy = self.sbox_1_y
            else:
                # 1
                ll_corner_vx = self.sbox_1_x + self.sbox_w
                ll_corner_vy = self.sbox_1_y + self.sbox_h
                tr_corner_vx = self.sbox_1_x
                tr_corner_vy = self.sbox_1_y
        else:
            if self.sbox_w >= 0:
                # 3
                ll_corner_vx = self.sbox_1_x
                ll_corner_vy = self.sbox_1_y
                tr_corner_vx = self.sbox_1_x + self.sbox_w
                tr_corner_vy = self.sbox_1_y + self.sbox_h
            else:
                # 4
                ll_corner_vx = self.sbox_1_x + self.sbox_w
                ll_corner_vy = self.sbox_1_y
                tr_corner_vx = self.sbox_1_x
                tr_corner_vy = self.sbox_1_y + self.sbox_h

        return ll_corner_vx, ll_corner_vy, tr_corner_vx, tr_corner_vy

    ######
    # Select helpers - get objects that were selected
    ######

    def sel_point_in_layer(self, layer: PointLayer, view_pt: Tuple[float, float], map_pt: Tuple[float, float]):
        """Determine if clicked location selects a point in layer data.

        layer    layer object we are looking in
        view_pt  click location tuple (view coords)
        map_pt   click location tuple (geo coords)

        We must look for the nearest point to the selection point.

        Return None (no selection) or (point, data, None) of selected point
        where point is [(x,y,attrib)] where X and Y are map or view relative
        depending on layer.map_rel.  'data' is the data object associated with
        each selected point.  The None is a placeholder for the relative
        selection point, which is meaningless for point selection.
        """

        # TODO: speed this up?  Do we need to??
        # http://en.wikipedia.org/wiki/Kd-tree
        # would need to create kd-tree in AddLayer() (slower)

        result = None
        delta = layer.delta
        dist = 9999999.0  # more than possible

        # get correct pex function (map-rel or view-rel)
        # pex = self.pex_point_view
        # if layer.map_rel:
        #     pex = self.pex_point

        # find selected point on map/view
        (view_x, view_y) = view_pt
        # (x, y, place, radius, colour, x_off, y_off, udata)
        for entry in layer.data:

            if layer.map_rel:
                vp, _ = self.pex_point(place=entry.placement,
                                       xgeo=entry.x,
                                       ygeo=entry.y,
                                       x_off=entry.offset_x,
                                       y_off=entry.offset_y,
                                       radius=entry.radius)
            else:
                vp, _ = self.pex_point_view(place=entry.placement,
                                            xview=entry.x,
                                            yview=entry.y,
                                            x_off=entry.offset_x,
                                            y_off=entry.offset_y,
                                            radius=entry.radius)

            if vp:
                (vx, vy) = vp
                d = (vx - view_x) * (vx - view_x) + (vy - view_y) * (vy - view_y)
                if d < dist:
                    rpt = (entry.x, entry.y, {'placement': entry.placement,
                                              'radius': entry.radius,
                                              'colour': entry.colour,
                                              'offset_x': entry.offset_x,
                                              'offset_y': entry.offset_y,
                                              'data': entry.udata})
                    result = ([rpt], None)
                    dist = d

        if dist <= layer.delta:
            return result
        return None

    def sel_box_points_in_layer(self, layer: PointLayer, ll: Tuple[float, float], ur: Tuple[float, float]):
        """Get list of points inside box.

        layer  reference to layer object we are working on
        ll     lower-left corner point of selection box (geo or view)
        ur     upper-right corner point of selection box (geo or view)

        Return a tuple (selection, data, relsel) where 'selection' is a list of
        selected point positions (xgeo,ygeo), 'data' is a list of userdata
        objects associated with the selected points and 'relsel' is always None
        as this is meaningless for box selects.

        If nothing is selected return None.
        """

        # get a list of points inside the selection box
        selection = []
        data = []

        # get correct pex function and box limits in view coords
        (blx, bby) = ll
        (brx, bty) = ur
        if layer.map_rel:
            (blx, bby) = self.geo_to_view(blx, bby)
            (brx, bty) = self.geo_to_view(brx, bty)

        # get points selection
        # x, y, place, radius, colour, x_off, y_off, udata
        for entry in layer.data:

            if layer.map_rel:
                vp, _ = self.pex_point(place=entry.placement,
                                       xgeo=entry.x,
                                       ygeo=entry.y,
                                       x_off=entry.offset_x,
                                       y_off=entry.offset_y,
                                       radius=entry.radius)
            else:
                vp, _ = self.pex_point_view(place=entry.placement,
                                            xview=entry.x,
                                            yview=entry.y,
                                            x_off=entry.offset_x,
                                            y_off=entry.offset_y,
                                            radius=entry.radius)

            if vp:
                (vpx, vpy) = vp
                if blx <= vpx <= brx and bby >= vpy >= bty:
                    selection.append((entry.x, entry.y, {'placement': entry.placement,
                                                         'radius': entry.radius,
                                                         'colour': entry.colour,
                                                         'offset_x': entry.offset_x,
                                                         'offset_y': entry.offset_y}))
                    data.append(entry.udata)

        if selection:
            return selection, data, None
        return None

    def sel_image_in_layer(self, layer: ImageLayer, view_pt: Tuple[float, float], geo_pt: Tuple[float, float]):
        """Decide if click location selects image object(s) in layer data.

        layer    layer object we are looking in
        view_pt  click location tuple (view coords)
        geo_pt   click location (geo coords)

        Returns either None if no selection or a tuple (selection, relsel)
        where 'selection' is a tuple (xgeo,ygeo) or (xview,yview) of the object
        placement view_pt and 'relsel' is the relative position within the
        selected object of the mouse click.

        Note that there could conceivably be more than one image selectable in
        the layer at the mouse click position but only the first found is
        returned as selected.
        """

        result = None

        # get correct pex function and click view_pt into view coords
        if layer.map_rel:
            clickpt = geo_pt
        else:
            clickpt = view_pt

        xclick, yclick = clickpt
        view_x, view_y = view_pt

        # selected an image?
        # x, y, bmp, w, h, place, x_off, y_off, radius, colour, udata
        for entry in layer.data:

            if layer.map_rel:
                _, e = self.pex_extent(place=entry.placement,
                                       xgeo=entry.lon,
                                       ygeo=entry.lat,
                                       x_off=entry.offset_x,
                                       y_off=entry.offset_y,
                                       w=entry.w,
                                       h=entry.h)
            else:
                _, e = self.pex_extent_view(place=entry.placement,
                                            xview=entry.lon,
                                            yview=entry.lat,
                                            x_off=entry.offset_x,
                                            y_off=entry.offset_y,
                                            w=entry.w,
                                            h=entry.h)

            if e:
                (lx, rx, ty, by) = e
                if lx <= view_x <= rx and ty <= view_y <= by:
                    selection = [(entry.lon, entry.lat, {'placement': entry.placement,
                                                         'radius': entry.radius,
                                                         'colour': entry.colour,
                                                         'offset_x': entry.offset_x,
                                                         'offset_y': entry.offset_y,
                                                         'data': entry.udata})]
                    relsel = (int(xclick - lx), int(yclick - ty))
                    result = (selection, relsel)
                    break

        return result

    def sel_box_images_in_layer(self, layer: ImageLayer, ll: Tuple[float, float], ur: Tuple[float, float]):
        """Get list of images inside selection box.

        layer  reference to layer object we are working on
        ll     lower-left corner point of selection box (geo or view coords)
        ur     upper-right corner point of selection box (geo or view coords)

        Return a tuple (selection, data) where 'selection' is a list of
        selected point positions (xgeo,ygeo) and 'data' is a list of userdata
        objects associated withe selected points.

        If nothing is selected return None.
        """

        # get correct pex function and box limits in view coords
        vboxlx, vboxby = ll
        vboxrx, vboxty = ur
        if layer.map_rel:
            vboxlx, vboxby = self.geo_to_view(vboxlx, vboxby)
            vboxrx, vboxty = self.geo_to_view(vboxrx, vboxty)

        # select images in map/view
        selection = []
        data = []
        # x, y, bmp, w, h, place, x_off, y_off, radius, colour, udata
        for entry in layer.data:

            if layer.map_rel:
                _, e = self.pex_extent(place=entry.placement,
                                       xgeo=entry.lon,
                                       ygeo=entry.lat,
                                       x_off=entry.offset_x,
                                       y_off=entry.offset_y,
                                       w=entry.w,
                                       h=entry.h)
            else:
                _, e = self.pex_extent_view(place=entry.placement,
                                            xview=entry.lon,
                                            yview=entry.lat,
                                            x_off=entry.offset_x,
                                            y_off=entry.offset_y,
                                            w=entry.w,
                                            h=entry.h)

            if e:
                li, ri, ti, bi = e  # image extents (view coords)
                if vboxlx <= li and ri <= vboxrx and vboxty <= ti and bi <= vboxby:
                    selection.append((entry.lon, entry.lat, {'placement': entry.placement,
                                                             'radius': entry.radius,
                                                             'colour': entry.colour,
                                                             'offset_x': entry.offset_x,
                                                             'offset_y': entry.offset_y}))
                    data.append(entry.udata)

        if not selection:
            return None
        return selection, data, None

    def sel_text_in_layer(self, layer: TextLayer, view_point: Tuple[float, float], geo_point: Tuple[float, float]):
        """Determine if clicked location selects a text object in layer data.

        layer       layer object we are looking in
        view_point  click location tuple (view coordinates)
        geo_point   click location tuple (geo coordinates)

        Return ([(x, y, attr)], None) for the selected text object, or None if
        no selection.  The x and y coordinates are view/geo depending on
        the layer.map_rel value.

        ONLY SELECTS ON POINT, NOT EXTENT.
        """

        result = None
        delta = layer.delta
        dist = 9999999.0

        # get correct pex function and mouse click in view coords
        if layer.map_rel:
            clickpt = geo_point
        else:
            clickpt = view_point

        xclick, yclick = clickpt
        view_x, view_y = view_point

        # select text in map/view layer
        # x, y, text, place, radius, colour, tcolour, fname, fsize, x_off, y_off, udata
        for entry in layer.data:

            if layer.map_rel:
                vp, ex = self.pex_point(place=entry.placement,
                                        xgeo=entry.lon,
                                        ygeo=entry.lat,
                                        x_off=0,
                                        y_off=0,
                                        radius=entry.radius)
            else:
                vp, ex = self.pex_point_view(place=entry.placement,
                                             xview=entry.lon,
                                             yview=entry.lat,
                                             x_off=0,
                                             y_off=0,
                                             radius=entry.radius)

            if vp:
                (px, py) = vp
                d = (px - view_x) ** 2 + (py - view_y) ** 2
                if d < dist:
                    selection = (entry.lon, entry.lat, {'placement': entry.placement,
                                                        'radius': entry.radius,
                                                        'colour': entry.colour,
                                                        'textcolour': entry.textcolour,
                                                        'fontname': entry.fontname,
                                                        'fontsize': entry.fontsize,
                                                        'offset_x': entry.offset_x,
                                                        'offset_y': entry.offset_y,
                                                        'data': entry.udata})
                    result = ([selection], None)
                    dist = d

        if dist <= delta:
            return result

        return None

    def sel_box_texts_in_layer(self, layer: TextLayer, ll: Tuple[float, float], ur: Tuple[float, float]):
        """Get list of text objects inside box ll-ur.

        layer  reference to layer object we are working on
        ll     lower-left corner point of selection box (geo or view)
        ur     upper-right corner point of selection box (geo or view)

        The 'll' and 'ur' points are in view or geo coords, depending on
        the layer.map_rel value.

        Returns (selection, data, None) where 'selection' is a list of text
        positions (geo or view, depending on layer.map_rel) plus attributes
        and 'data' is a list of userdata objects associated with the selected
        text objects.

        Returns None if no selection.

        Selects on text extent and point.
        """

        selection = []
        data = []

        # get correct pex function and box limits in view coords
        if layer.map_rel:
            ll = self.geo_to_view(ll[0], ll[1])
            ur = self.geo_to_view(ur[0], ur[1])
        (lx, by) = ll
        (rx, ty) = ur

        # get texts inside box
        # x, y, text, place, radius, colour, tcolour, fname, fsize, x_off, y_off, udata
        for entry in layer.data:

            if layer.map_rel:
                vp, ex = self.pex_point(place=entry.placement,
                                        xgeo=entry.lon,
                                        ygeo=entry.lat,
                                        x_off=0,
                                        y_off=0,
                                        radius=entry.radius)
            else:
                vp, ex = self.pex_point_view(place=entry.placement,
                                             xview=entry.lon,
                                             yview=entry.lat,
                                             x_off=0,
                                             y_off=0,
                                             radius=entry.radius)

            if vp:
                px, py = vp
                if lx <= px <= rx and ty <= py <= by:
                    sel = (entry.lon, entry.lat, {'placement': entry.placement,
                                                  'radius': entry.radius,
                                                  'colour': entry.colour,
                                                  'textcolour': entry.textcolour,
                                                  'fontname': entry.fontname,
                                                  'fontsize': entry.fontsize,
                                                  'offset_x': entry.offset_x,
                                                  'offset_y': entry.offset_y, })
                    selection.append(sel)
                    data.append(entry.udata)

        if selection:
            return selection, data, None
        return None

    def sel_polygon_in_layer(self, layer: PolygonLayer, view_pt: Tuple[float, float], map_pt: Tuple[float, float]):
        """Get first polygon object clicked in layer data.

        layer    layer object we are looking in
        view_pt  tuple of click position (xview,yview)
        map_pt   tuple of click position (xgeo,ygeo)

        Returns an iterable: ((x,y), udata) of the first polygon selected.
        Returns None if no polygon selected.
        """

        result = None

        # get correct 'view_pt in polygon' routine
        # sel_pt = view_pt
        # pip = self.point_in_polygon_view
        # if layer.map_rel:
        #     sel_pt = map_pt
        #     pip = self.point_in_polygon_geo

        # check polyons in layer, choose first view_pt is inside
        # (poly, place, width, colour, close, filled, fcolour, x_off, y_off, udata)
        for entry in layer.data:

            if layer.map_rel:
                ok = self.point_in_polygon_geo(poly=entry.p,
                                               geo=map_pt,
                                               placement=entry.placement,
                                               offset_x=entry.offset_x,
                                               offset_y=entry.offset_y)
            else:
                ok = self.point_in_polygon_view(poly=entry.p,
                                                view=view_pt,
                                                place=entry.placement,
                                                x_off=entry.offset_x,
                                                y_off=entry.offset_y)

            if ok:
                sel = (entry.p, {'placement': entry.placement,
                                 'offset_x': entry.offset_x,
                                 'offset_y': entry.offset_y,
                                 'data': entry.udata})
                result = ([sel], None)
                break

        return result

    def sel_box_polygons_in_layer(self, layer: PolygonLayer, p1: Tuple[float, float], p2: Tuple[float, float]):
        """Get list of polygons inside box p1-p2 in given layer.

        layer  reference to layer object we are working on
        p1     bottom-left corner point of selection box (geo or view)
        p2     top-right corner point of selection box (geo or view)

        Return a tuple (selection, data, None) where 'selection' is a list of
        iterables of vertex positions and 'data' is a list of data objects
        associated with each polygon selected.
        """

        selection = []
        data = []

        # get correct pex function and box limits in view coords
        if layer.map_rel:
            p1 = self.geo_to_view(p1[0], p1[1])
            p2 = self.geo_to_view(p2[0], p2[1])
        (lx, by) = p1
        (rx, ty) = p2

        # check polygons in layer
        # poly, place, width, colour, close, filled, fcolour, x_off, y_off, udata
        for entry in layer.data:

            if layer.map_rel:
                pex = self.pex_polygon
                pt, ex = self.pex_polygon(place=entry.placement,
                                          poly=entry.p,
                                          x_off=entry.offset_x,
                                          y_off=entry.offset_y)
            else:
                pt, ex = self.pex_polygon_view(place=entry.placement,
                                               poly=entry.p,
                                               x_off=entry.offset_x,
                                               y_off=entry.offset_y)

            if ex:
                plx, prx, pty, pby = ex
                if lx <= plx and prx <= rx and ty <= pty and pby <= by:
                    sel = (entry.p, {'placement': entry.placement,
                                     'offset_x': entry.offset_x,
                                     'offset_y': entry.offset_y})
                    selection.append(sel)
                    data.append(entry.udata)

        if not selection:
            return None, None, None
        return selection, data, None

    def sel_polyline_in_layer(self, layer: PolylineLayer, view_pt: Tuple[float, float], map_pt: Tuple[float, float]):
        """
        Get first polyline object clicked in layer data.

        layer    layer object we are looking in
        view_pt  tuple of click position in view coords
        map_pt   tuple of click position in geo coords

        Returns a tuple (sel, seg) if a polyline was selected.  'sel' is the
        tuple (poly, attrib) and 'seg' is a tuple (pt1, pt2) of nearest segment
        endview_pts.  Returns None if no polyline selected.
        """

        result = None
        delta = layer.delta

        # # get correct 'view_pt in polyline' routine
        # pip = self.point_near_polyline_view
        # point = view_pt
        #
        # if layer.map_rel:
        #     pip = self.point_near_polyline_geo
        #     point = map_pt

        # check polylines in layer, choose first where view_pt is close enough
        # polyline, place, width, colour, x_off, y_off, udata
        for entry in layer.data:

            if layer.map_rel:
                seg = self.point_near_polyline_geo(point=map_pt,
                                                   poly=entry.polyline,
                                                   placement=entry.placement,
                                                   offset_x=entry.offset_x,
                                                   offset_y=entry.offset_y,
                                                   delta=delta)
            else:
                seg = self.point_near_polyline_view(point=view_pt,
                                                    polyline=entry.polyline,
                                                    place=entry.placement,
                                                    x_off=entry.offset_x,
                                                    y_off=entry.offset_y,
                                                    delta=delta)

            if seg:
                sel = (entry.polyline, {'placement': entry.placement,
                                        'offset_x': entry.offset_x,
                                        'offset_y': entry.offset_y,
                                        'data': entry.udata})
                result = ([sel], seg)
                break

        return result

    def sel_box_polylines_in_layer(self, layer: PolylineLayer, p1: Tuple[float, float], p2: Tuple[float, float]):
        """Get list of polylines inside box p1-p2 in given layer.

        layer  reference to layer object we are working on
        p1     bottom-left corner point of selection box (geo or view)
        p2     top-right corner point of selection box (geo or view)

        Return a tuple (selection, data, None) where 'selection' is a list of
        iterables of vertex positions plus attributes and 'data' is a list of
        data objects associated with each polyline selected.
        """

        selection = []

        # get correct pex function and box limits in view coords
        if layer.map_rel:
            p1 = self.geo_to_view(p1[0], p1[1])
            p2 = self.geo_to_view(p2[0], p2[1])
        (lx, by) = p1
        (rx, ty) = p2

        # check polygons in layer
        # (poly, place, width, colour, x_off, y_off, udata)
        for entry in layer.data:

            if layer.map_rel:
                pt, ex = self.pex_polygon(place=entry.placement,
                                          poly=entry.polyline,
                                          x_off=entry.offset_x,
                                          y_off=entry.offset_y)
            else:
                pt, ex = self.pex_polygon_view(place=entry.placement,
                                               poly=entry.polyline,
                                               x_off=entry.offset_x,
                                               y_off=entry.offset_y)

            if ex:
                (plx, prx, pty, pby) = ex
                if lx <= plx and prx <= rx and ty <= pty and pby <= by:
                    sel = (entry.polyline, {'placement': entry.placement,
                                            'offset_x': entry.offset_x,
                                            'offset_y': entry.offset_y,
                                            'data': entry.udata})
                    selection.append(sel)

        if not selection:
            return None, None, None

        return selection, None, None

    ######
    # Polygon/polyline utility routines
    ######

    @staticmethod
    def point_inside_polygon(point: Tuple[float, float], poly: List[Tuple[float, float]]):
        """Decide if point is inside polygon.

        point  tuple of (x,y) coordinates of point in question (geo or view)
        poly   polygon in form [(x1,y1), (x2,y2), ...]

        Returns True if point is properly inside polygon.
        May return True or False if point on edge of polygon.

        Slightly modified version of the 'published' algorithm found on the 'net.
        Instead of indexing into the poly, create a new poly that 'wraps around'.
        Even with the extra code, it runs in 2/3 the time.
        """

        (x, y) = point

        # we want a *copy* of original iterable plus extra wraparound point
        l_poly = list(poly)
        l_poly.append(l_poly[0])  # ensure poly wraps around

        inside = False

        (p1x, p1y) = l_poly[0]

        for (p2x, p2y) in l_poly:
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            (p1x, p1y) = (p2x, p2y)

        return inside

    def point_in_polygon_geo(self, poly: List[Tuple[float, float]], geo: Tuple[float, float],
                             placement: Place, offset_x: float, offset_y: float):
        """Decide if a point is inside a map-relative polygon.

        poly       an iterable of (x,y) where x,y are in geo coordinates
        geo        tuple (xgeo, ygeo) of point position
        placement  a placement string
        offset_x   X offset in pixels
        offset_y   Y offset in pixels

        The 'geo' point, while in geo coordinates, must be a click point
        within the view.

        Returns True if point is inside the polygon.
        """

        return self.point_inside_polygon(geo, poly)

    def point_in_polygon_view(self, poly: List[Tuple[float, float]], view: Tuple[float, float], place: Place,
                              x_off: float, y_off: float):
        """Decide if a point is inside a view-relative polygon.

        poly      an iterable of (x,y) where x,y are in view (pixel) coordinates
        ptx       point X coordinate (view)
        pty       point Y coordinate (view)
        place     a placement string
        offset_x  X offset in pixels
        offset_y  Y offset in pixels

        Returns True if point is inside the polygon.
        """

        # convert polygon and placement into list of (x,y) tuples
        view_poly = []
        for (x, y) in poly:
            (x, y) = self.point_placement_view(place, x, y, x_off, y_off)
            view_poly.append((x, y))

        # decide if (ptx,pty) is inside polygon
        return self.point_inside_polygon(view, view_poly)

    def point_near_polyline_geo(self, point: Tuple[float, float], poly: List[Tuple[float, float]],
                                placement: Place, offset_x: float, offset_y: float, delta: int):
        """Decide if a point is near a map-relative polyline.

        point      tuple (xgeo, ygeo) of point position
        poly       an iterable of (x,y) where x,y are in geo coordinates
        placement  a placement string
        offset_x   X offset in pixels
        offset_y   Y offset in pixels
        delta      distance (squared) before selection allowed

        The 'geo' point, while in geo coordinates, must be a click point
        within the view.

        Returns nearest line segment of polyline that is 'close enough'
        to the point.  Returns None if no segment close enough.
        """

        return self.point_near_polyline(point, poly, delta=delta)

    def point_near_polyline_view(self, point: Tuple[float, float], polyline: List[Tuple[float, float]],
                                 place: Place, x_off: float, y_off: float, delta: int):
        """Decide if a point is near a view-relative polyline.

        point     a tuple (viewx, viewy) of selection point in view coordinates
        polyline  an iterable of (x,y) where x,y are in view (pixel) coordinates
        place     a placement string
        offset_x  X offset in pixels
        offset_y  Y offset in pixels
        delta     distance (squared) before selection allowed

        Returns nearest line segment of polyline that is 'close enough'
        to the point.  Returns None if no segment close enough.
        """

        # dict to convert selected segment back to orig coords
        back_to_orig = {}

        # convert polyline and placement into list of (x,y) tuples
        view_poly = []
        for (x, y) in polyline:
            (vx, vy) = self.point_placement_view(place, x, y, x_off, y_off)
            view_poly.append((vx, vy))
            back_to_orig[(vx, vy)] = (x, y)

        # decide if (ptx,pty) is inside polyline (gets nearest segment)
        seg = self.point_near_polyline(point, view_poly, delta=delta)

        if seg:
            (s1, s2) = seg
            s1 = back_to_orig[s1]
            s2 = back_to_orig[s2]
            return s1, s2

        return None, None

    def point_near_polyline(self, point: Tuple[float, float], polyline: List[Tuple[float, float]], delta: int = 50):
        """Decide if point is within 'delta' of the given polyline.

        point     point (x, y)
        polyline  iterable of (x, y) point tuples
        delta     maximum distance before 'not close enough'

        Returns nearest line segment of polyline that is 'close enough'
        to the point.  Returns None if no segment close enough.
        """

        result = None
        last_delta = delta + 1

        last_pp = polyline[0]
        for pp in polyline[1:]:
            d = self.point_segment_distance(point, last_pp, pp)
            if d < last_delta:
                result = (last_pp, pp)
                last_delta = d
            last_pp = pp

        if last_delta > delta:
            result = None

        return result

    @staticmethod
    def point_segment_distance(point: Tuple[float, float], s1: Tuple[float, float], s2: Tuple[float, float]):
        """
        Get distance from a point to segment defined by the points (s1, s2).

        point   tuple (x, y)
        s1, s2  tuples (x, y) of segment endpoints

        Returns the distance squared.
        """

        (ptx, pty) = point
        (s1x, s1y) = s1
        (s2x, s2y) = s2

        px = s2x - s1x
        py = s2y - s1y
        div = float(px ** 2 + py ** 2)
        if div != 0:
            u = ((ptx - s1x) * px + (pty - s1y) * py) / div
        else:
            u = 0

        if u > 1:
            u = 1
        elif u < 0:
            u = 0

        dx = s1x + u * px - ptx
        dy = s1y + u * py - pty

        return dx ** 2 + dy ** 2

    def info(self, msg: str):
        """
        Display an information message, log and graphically.
        """

        log_msg = '# ' + msg
        length = len(log_msg)
        prefix = '#### Information '
        banner = prefix + '#' * (80 - len(log_msg) - len(prefix))
        log(banner)
        log(log_msg)
        log(banner)

        QMessageBox.information(self, 'Information', msg)

    def warn(self, msg: str):
        """
        Display a warning message, log and graphically.
        """

        log_msg = '# ' + msg
        length = len(log_msg)
        prefix = '#### Warning '
        banner = prefix + '#' * (80 - len(log_msg) - len(prefix))
        log(banner)
        log(log_msg)
        log(banner)

        QMessageBox.warning(self, 'Information', msg)

    ################################################################################
    # Below are the "external" API methods.
    ################################################################################

    ######
    # "add a layer" routines
    ######

    def AddPointLayer(self,
                      data: List[PointData],
                      map_rel: bool = True,
                      visible: bool = True,
                      show_levels: List[int] = None,
                      selectable: bool = False,
                      name: str = '<points_layer>'):
        """Add a layer of points, map or view relative.

        points       iterable of point data:
                         (x, y, [optional: attributes])
                     where x & y are either lon&lat (map) or x&y (view) coords
                     and attributes is an optional dictionary of attributes for
                     _each point_ with keys like:
                         'placement'  a placement string
                         'radius'     radius of point in pixels
                         'colour'     colour of point
                         'offset_x'   X offset
                         'offset_y'   Y offset
                         'data'       point user data object
        map_rel      points are map relative if True, else view relative
        visible      True if the layer is visible
        show_levels  list of levels at which layer is auto-shown (or None==all)
        selectable   True if select operates on this layer
        name         the 'name' of the layer - mainly for debug
        kwargs       a layer-specific attributes dictionary, has keys:
                         'placement'  a placement string
                         'radius'     radius of point in pixels
                         'colour'     colour of point
                         'offset_x'   X offset
                         'offset_y'   Y offset
                         'data'       point user data object
        """

        # # merge global and layer defaults
        # if map_rel:
        #     default_placement = kwargs.get('placement', self.DefaultPointPlacement)
        #     default_radius = kwargs.get('radius', self.DefaultPointRadius)
        #     default_colour = self.get_i18n_kw(kwargs, ('colour', 'color'),
        #                                       self.DefaultPointColour)
        #     default_offset_x = kwargs.get('offset_x', self.DefaultPointOffsetX)
        #     default_offset_y = kwargs.get('offset_y', self.DefaultPointOffsetY)
        #     default_data = kwargs.get('data', self.DefaultPointData)
        # else:
        #     default_placement = kwargs.get('placement', self.DefaultPointViewPlacement)
        #     default_radius = kwargs.get('radius', self.DefaultPointViewRadius)
        #     default_colour = self.get_i18n_kw(kwargs, ('colour', 'color'), self.DefaultPointViewColour)
        #     default_offset_x = kwargs.get('offset_x', self.DefaultPointViewOffsetX)
        #     default_offset_y = kwargs.get('offset_y', self.DefaultPointViewOffsetY)
        #     default_data = kwargs.get('data', self.DefaultPointData)
        #
        # # create draw data iterable for draw method
        # draw_data = []  # list to hold draw data
        #
        # for point in points:
        #     if len(point) == 3:
        #         x, y, attributes = point
        #     elif len(point) == 2:
        #         x, y = point
        #         attributes = {}
        #     else:
        #         msg = ('Point data must be iterable of tuples: '
        #                '(x, y[, dict])\n'
        #                'Got: %s' % str(point))
        #         raise Exception(msg)
        #
        #     # plug in any required polygon values (override globals+layer)
        #     placement = attributes.get('placement', default_placement)
        #     radius = attributes.get('radius', default_radius)
        #     colour = self.get_i18n_kw(attributes, ('colour', 'color'),
        #                               default_colour)
        #     offset_x = attributes.get('offset_x', default_offset_x)
        #     offset_y = attributes.get('offset_y', default_offset_y)
        #     udata = attributes.get('data', default_data)
        #
        #     # check values that can be wrong
        #     if not placement:
        #         placement = default_placement
        #
        #     # convert various colour formats to internal (r, g, b, a)
        #     colour = self.colour_to_internal(colour)
        #
        #     # append another point to draw data list
        #     draw_data.append((float(x), float(y), placement,
        #                       radius, colour, offset_x, offset_y, udata))
        #
        # return self.add_layer(self.draw_point_layer, draw_data, map_rel,
        #                       visible=visible, show_levels=show_levels,
        #                       selectable=selectable, name=name,
        #                       ltype=LayerType.TypePoint)

        # get unique layer ID
        layer_id = self.next_layer_id
        self.next_layer_id += 1

        # prepare the show_level value
        if show_levels is None:
            show_levels = range(self.tiles_min_level, self.tiles_max_level + 1)[:]

        # create layer, add unique ID to Z order list
        layer = PointLayer(layer_id=layer_id,
                           painter=self.draw_point_layer,
                           data=data,
                           map_rel=map_rel,
                           visible=visible,
                           show_levels=show_levels,
                           selectable=selectable,
                           name=name)

        self.layer_mapping[layer_id] = layer
        self.layer_z_order.append(layer_id)

        # force display of new layer if it's visible
        if visible:
            self.update()

        return layer_id

    def AddImageLayer(self,
                      data: List[ImageData],
                      map_rel=True,
                      visible=True,
                      show_levels=None,
                      selectable=False,
                      name='<image_layer>'):
        """
        Add a layer of images, map or view relative.
        The hotspot is placed at (lon, lat) or (x, y).  'placement' controls
        where the image is displayed relative to the hotspot.
        :param data: List[ImageData]
        :param map_rel: points drawn relative to map if True, else view relative
        :param visible: True if the layer is to be immediately visible
        :param show_levels: list of levels at which layer is auto-shown (or None)
        :param selectable: True if select operates on this layer
        :param name: name of this layer
        :return:
        """

        # merge global and layer defaults
        # if map_rel:
        #     default_placement = kwargs.get('placement', self.DefaultImagePlacement)
        #     default_radius = kwargs.get('radius', self.DefaultImageRadius)
        #     default_colour = kwargs.get('colour', self.DefaultImageColour)
        #     default_offset_x = kwargs.get('offset_x', self.DefaultImageOffsetX)
        #     default_offset_y = kwargs.get('offset_y', self.DefaultImageOffsetY)
        #     default_data = kwargs.get('data', self.DefaultImageData)
        # else:
        #     default_placement = kwargs.get('placement', self.DefaultImageViewPlacement)
        #     default_radius = kwargs.get('radius', self.DefaultImageViewRadius)
        #     default_colour = kwargs.get('colour', self.DefaultImageViewColour)
        #     default_offset_x = kwargs.get('offset_x', self.DefaultImageViewOffsetX)
        #     default_offset_y = kwargs.get('offset_y', self.DefaultImageViewOffsetY)
        #     default_data = kwargs.get('data', self.DefaultImageViewData)
        #
        # # define cache variables for the image informtion
        # # used to minimise file access - just caches previous file informtion
        # fname_cache = None
        # pmap_cache = None
        # w_cache = None
        # h_cache = None
        #
        # # load all image files, convert to bitmaps, create draw_data iterable
        # draw_data = []
        # for d in data:
        #     if len(d) == 4:
        #         (lon, lat, fname, attributes) = d
        #     elif len(d) == 3:
        #         (lon, lat, fname) = d
        #         attributes = {}
        #     else:
        #         msg = ('Image data must be iterable of tuples: '
        #                '(x, y, fname[, dict])\nGot: %s' % str(d))
        #         raise Exception(msg)
        #
        #     # get image specific values, if any
        #     placement = attributes.get('placement', default_placement)
        #     radius = attributes.get('radius', default_radius)
        #     colour = attributes.get('colour', default_colour)
        #     offset_x = attributes.get('offset_x', default_offset_x)
        #     offset_y = attributes.get('offset_y', default_offset_y)
        #     udata = attributes.get('data', None)
        #
        #     if fname == fname_cache:
        #         pmap = pmap_cache
        #         w = w_cache
        #         h = h_cache
        #     else:
        #         fname_cache = fname
        #         pmap_cache = pmap = QPixmap(fname)
        #         size = pmap.size()
        #         h = h_cache = size.height()
        #         w = w_cache = size.width()
        #
        #     # check values that can be wrong
        #     if not placement:
        #         placement = default_placement
        #
        #     # convert various colour formats to internal (r, g, b, a)
        #     colour = self.colour_to_internal(colour)
        #
        #     draw_data.append((float(lon), float(lat), pmap, w, h, placement,
        #                       offset_x, offset_y, radius, colour, udata))
        #
        # return self.add_layer(self.draw_image_layer, draw_data, map_rel,
        #                       visible=visible, show_levels=show_levels,
        #                       selectable=selectable, name=name,
        #                       ltype=LayerType.TypeImage)

        # get unique layer ID
        layer_id = self.next_layer_id
        self.next_layer_id += 1

        # prepare the show_level value
        if show_levels is None:
            show_levels = range(self.tiles_min_level, self.tiles_max_level + 1)[:]

        # create layer, add unique ID to Z order list
        layer = ImageLayer(layer_id=layer_id,
                           painter=self.draw_image_layer,
                           data=data,
                           map_rel=map_rel,
                           visible=visible,
                           show_levels=show_levels,
                           selectable=selectable,
                           name=name)

        self.layer_mapping[layer_id] = layer
        self.layer_z_order.append(layer_id)

        # force display of new layer if it's visible
        if visible:
            self.update()

        return layer_id

    def AddTextLayer(self,
                     data: List[TextData],
                     map_rel=True,
                     visible=True,
                     show_levels=None,
                     selectable=False,
                     name='<text_layer>'):
        """Add a text layer to the map or view.

        text         list of sequence of (lon, lat, text[, dict]) coordinates
                     (optional 'dict' contains point-specific attributes)
        map_rel      points drawn relative to map if True, else view relative
        visible      True if the layer is to be immediately visible
        show_levels  list of levels at which layer is auto-shown
        selectable   True if select operates on this layer
        name         name of this layer
        kwargs       a dictionary of changeable text attributes
                         (placement, radius, fontname, fontsize, colour, data)
                     these supply any data missing in 'data'
        """

        # # merge global and layer defaults
        # if map_rel:
        #     default_placement = kwargs.get('placement', self.DefaultTextPlacement)
        #     default_radius = kwargs.get('radius', self.DefaultTextRadius)
        #     default_fontname = kwargs.get('fontname', self.DefaultTextFontname)
        #     default_fontsize = kwargs.get('fontsize', self.DefaultTextFontSize)
        #     default_colour = self.get_i18n_kw(kwargs, ('colour', 'color'),
        #                                       self.DefaultTextColour)
        #     default_textcolour = self.get_i18n_kw(kwargs,
        #                                           ('textcolour', 'textcolor'),
        #                                           self.DefaultTextTextColour)
        #     default_offset_x = kwargs.get('offset_x', self.DefaultTextOffsetX)
        #     default_offset_y = kwargs.get('offset_y', self.DefaultTextOffsetY)
        #     default_data = kwargs.get('data', self.DefaultTextData)
        # else:
        #     default_placement = kwargs.get('placement', self.DefaultTextViewPlacement)
        #     default_radius = kwargs.get('radius', self.DefaultTextViewRadius)
        #     default_fontname = kwargs.get('fontname', self.DefaultTextViewFontname)
        #     default_fontsize = kwargs.get('fontsize', self.DefaultTextViewFontSize)
        #     default_colour = self.get_i18n_kw(kwargs, ('colour', 'color'),
        #                                       self.DefaultTextViewColour)
        #     default_textcolour = self.get_i18n_kw(kwargs,
        #                                           ('textcolour', 'textcolor'),
        #                                           self.DefaultTextViewTextColour)
        #     default_offset_x = kwargs.get('offset_x', self.DefaultTextViewOffsetX)
        #     default_offset_y = kwargs.get('offset_y', self.DefaultTextViewOffsetY)
        #     default_data = kwargs.get('data', self.DefaultTextData)
        #
        # # create data iterable ready for drawing
        # draw_data = []
        # for t in text:
        #     if len(t) == 4:
        #         (lon, lat, tdata, attributes) = t
        #     elif len(t) == 3:
        #         (lon, lat, tdata) = t
        #         attributes = {}
        #     else:
        #         msg = ('Text data must be iterable of tuples: '
        #                '(lon, lat, text, [dict])\n'
        #                'Got: %s' % str(t))
        #         raise Exception(msg)
        #
        #     # plug in any required defaults
        #     placement = attributes.get('placement', default_placement)
        #     radius = attributes.get('radius', default_radius)
        #     fontname = attributes.get('fontname', default_fontname)
        #     fontsize = attributes.get('fontsize', default_fontsize)
        #     colour = self.get_i18n_kw(attributes, ('colour', 'color'),
        #                               default_colour)
        #     textcolour = self.get_i18n_kw(attributes,
        #                                   ('textcolour', 'textcolor'),
        #                                   default_textcolour)
        #     offset_x = attributes.get('offset_x', default_offset_x)
        #     offset_y = attributes.get('offset_y', default_offset_y)
        #     udata = attributes.get('data', default_data)
        #
        #     # check values that can be wrong
        #     if not placement:
        #         placement = default_placement
        #
        #     # convert various colour formats to internal (r, g, b, a)
        #     colour = self.colour_to_internal(colour)
        #     textcolour = self.colour_to_internal(textcolour)
        #
        #     draw_data.append((float(lon), float(lat), tdata, placement,
        #                       radius, colour, textcolour, fontname, fontsize,
        #                       offset_x, offset_y, udata))
        #
        # return self.add_layer(self.draw_text_layer, draw_data, map_rel,
        #                       visible=visible, show_levels=show_levels,
        #                       selectable=selectable, name=name,
        #                       ltype=LayerType.TypeText)

        # get unique layer ID
        layer_id = self.next_layer_id
        self.next_layer_id += 1

        # prepare the show_level value
        if show_levels is None:
            show_levels = range(self.tiles_min_level, self.tiles_max_level + 1)[:]

        # create layer, add unique ID to Z order list
        layer = TextLayer(layer_id=layer_id,
                          painter=self.draw_text_layer,
                          data=data,
                          map_rel=map_rel,
                          visible=visible,
                          show_levels=show_levels,
                          selectable=selectable,
                          name=name)

        self.layer_mapping[layer_id] = layer
        self.layer_z_order.append(layer_id)

        # force display of new layer if it's visible
        if visible:
            self.update()

        return layer_id

    def AddPolygonLayer(self,
                        data: List[PolygonData],
                        map_rel=True,
                        visible=True,
                        show_levels=None,
                        selectable=False,
                        name='<polygon_layer>'):
        """Add a layer of polygon data to the map.

        data         iterable of polygon tuples:
                         (points[, attributes])
                     where points is another iterable of (x, y) tuples and
                     attributes is a dictionary of polygon attributes:
                         placement   a placement string (view-relative only)
                         width       width of polygon edge lines
                         colour      colour of edge lines
                         close       if True closes polygon
                         filled      polygon is filled (implies closed)
                         fillcolour  fill colour
                         offset_x    X offset
                         offset_y    Y offset
                         data        polygon user data object
        map_rel      points drawn relative to map if True, else view relative
        visible      True if the layer is to be immediately visible
        show_levels  list of levels at which layer is auto-shown (or None)
        selectable   True if select operates on this layer
        name         name of this layer
        kwargs       extra keyword args, layer-specific:
                         placement   placement string (view-rel only)
                         width       width of polygons in pixels
                         colour      colour of polygon edge lines
                         close       True if polygon is to be closed
                         filled      if True, fills polygon
                         fillcolour  fill colour
                         offset_x    X offset
                         offset_y    Y offset
                         data        polygon user data object
        """

        # # merge global and layer defaults
        # if map_rel:
        #     default_placement = kwargs.get('placement',
        #                                    self.DefaultPolygonPlacement)
        #     default_width = kwargs.get('width', self.DefaultPolygonWidth)
        #     default_colour = self.get_i18n_kw(kwargs, ('colour', 'color'),
        #                                       self.DefaultPolygonColour)
        #     default_close = kwargs.get('closed', self.DefaultPolygonClose)
        #     default_filled = kwargs.get('filled', self.DefaultPolygonFilled)
        #     default_fillcolour = self.get_i18n_kw(kwargs,
        #                                           ('fillcolour', 'fillcolor'),
        #                                           self.DefaultPolygonFillcolour)
        #     default_offset_x = kwargs.get('offset_x', self.DefaultPolygonOffsetX)
        #     default_offset_y = kwargs.get('offset_y', self.DefaultPolygonOffsetY)
        #     default_data = kwargs.get('data', self.DefaultPolygonData)
        # else:
        #     default_placement = kwargs.get('placement',
        #                                    self.DefaultPolygonViewPlacement)
        #     default_width = kwargs.get('width', self.DefaultPolygonViewWidth)
        #     default_colour = self.get_i18n_kw(kwargs, ('colour', 'color'),
        #                                       self.DefaultPolygonViewColour)
        #     default_close = kwargs.get('closed', self.DefaultPolygonViewClose)
        #     default_filled = kwargs.get('filled', self.DefaultPolygonViewFilled)
        #     default_fillcolour = self.get_i18n_kw(kwargs,
        #                                           ('fillcolour', 'fillcolor'),
        #                                           self.DefaultPolygonViewFillcolour)
        #     default_offset_x = kwargs.get('offset_x', self.DefaultPolygonViewOffsetX)
        #     default_offset_y = kwargs.get('offset_y', self.DefaultPolygonViewOffsetY)
        #     default_data = kwargs.get('data', self.DefaultPolygonViewData)
        #
        # # create draw_data iterable
        # draw_data = []
        # for d in data:
        #     if len(d) == 2:
        #         (p, attributes) = d
        #     elif len(d) == 1:
        #         p = d
        #         attributes = {}
        #     else:
        #         msg = ('Polygon data must be iterable of tuples: '
        #                '(points, [attributes])\n'
        #                'Got: %s' % str(d))
        #         raise Exception(msg)
        #
        #     # get polygon attributes
        #     placement = attributes.get('placement', default_placement)
        #     width = attributes.get('width', default_width)
        #     colour = self.get_i18n_kw(attributes, ('colour', 'color'),
        #                               default_colour)
        #     close = attributes.get('closed', default_close)
        #     filled = attributes.get('filled', default_filled)
        #     if filled:
        #         close = True
        #     fillcolour = self.get_i18n_kw(attributes,
        #                                   ('fillcolour', 'fillcolor'),
        #                                   default_fillcolour)
        #     offset_x = attributes.get('offset_x', default_offset_x)
        #     offset_y = attributes.get('offset_y', default_offset_y)
        #     udata = attributes.get('data', default_data)
        #
        #     # if polygon is to be filled, ensure closed
        #     if close:
        #         p = list(p)  # must get a *copy*
        #         p.append(p[0])
        #
        #     # check values that can be wrong
        #     if not placement:
        #         placement = default_placement
        #
        #     # convert various colour formats to internal (r, g, b, a)
        #     colour = self.colour_to_internal(colour)
        #     fillcolour = self.colour_to_internal(fillcolour)
        #
        #     # append this polygon to the layer data
        #     draw_data.append((p, placement, width, colour, close,
        #                       filled, fillcolour, offset_x, offset_y, udata))
        #
        # return self.add_layer(self.draw_polygon_layer, draw_data, map_rel,
        #                       visible=visible, show_levels=show_levels,
        #                       selectable=selectable, name=name,
        #                       ltype=LayerType.TypePolygon)

        # get unique layer ID
        layer_id = self.next_layer_id
        self.next_layer_id += 1

        # prepare the show_level value
        if show_levels is None:
            show_levels = range(self.tiles_min_level, self.tiles_max_level + 1)[:]

        # create layer, add unique ID to Z order list
        layer = PolygonLayer(layer_id=layer_id,
                             painter=self.draw_polygon_layer,
                             data=data,
                             map_rel=map_rel,
                             visible=visible,
                             show_levels=show_levels,
                             selectable=selectable,
                             name=name)

        self.layer_mapping[layer_id] = layer
        self.layer_z_order.append(layer_id)

        # force display of new layer if it's visible
        if visible:
            self.update()

        return layer_id

    def AddPolylineLayer(self,
                         data: List[PolylineData],
                         map_rel=True,
                         visible=True,
                         show_levels=None,
                         selectable=False,
                         name='<polyline>'):
        """Add a layer of polyline data to the map.

        data         iterable of polyline tuples:
                         (points[, attributes])
                     where points is another iterable of (x, y) tuples and
                     attributes is a dictionary of polyline attributes:
                         placement   a placement string (view-relative only)
                         width       width of polyline edge lines
                         colour      colour of edge lines
                         offset_x    X offset
                         offset_y    Y offset
                         data        polyline user data object
        map_rel      points drawn relative to map if True, else view relative
        visible      True if the layer is to be immediately visible
        show_levels  list of levels at which layer is auto-shown (or None)
        selectable   True if select operates on this layer
        name         name of this layer
        kwargs       extra keyword args, layer-specific:
                         placement   placement string (view-rel only)
                         width       width of polyline in pixels
                         colour      colour of polyline edge lines
                         offset_x    X offset
                         offset_y    Y offset
                         data        polygon user data object
        """

        # # merge global and layer defaults
        # if map_rel:
        #     default_placement = kwargs.get('placement', self.DefaultPolygonPlacement)
        #     default_width = kwargs.get('width', self.DefaultPolygonWidth)
        #     default_colour = self.get_i18n_kw(kwargs, ('colour', 'color'), self.DefaultPolygonColour)
        #     default_offset_x = kwargs.get('offset_x', self.DefaultPolygonOffsetX)
        #     default_offset_y = kwargs.get('offset_y', self.DefaultPolygonOffsetY)
        #     default_data = kwargs.get('data', self.DefaultPolygonData)
        # else:
        #     default_placement = kwargs.get('placement', self.DefaultPolygonViewPlacement)
        #     default_width = kwargs.get('width', self.DefaultPolygonViewWidth)
        #     default_colour = self.get_i18n_kw(kwargs, ('colour', 'color'), self.DefaultPolygonViewColour)
        #     default_offset_x = kwargs.get('offset_x', self.DefaultPolygonViewOffsetX)
        #     default_offset_y = kwargs.get('offset_y', self.DefaultPolygonViewOffsetY)
        #     default_data = kwargs.get('data', self.DefaultPolygonViewData)
        #
        # # create draw_data iterable
        # draw_data = []
        # for d in data:
        #     if len(d) == 2:
        #         (p, attributes) = d
        #     elif len(d) == 1:
        #         p = d
        #         attributes = {}
        #     else:
        #         msg = ('Polyline data must be iterable of tuples: (polyline, [attributes])\n'
        #                'Got: %s' % str(d))
        #         raise Exception(msg)
        #
        #     # get polygon attributes
        #     placement = attributes.get('placement', default_placement)
        #     width = attributes.get('width', default_width)
        #     colour = self.get_i18n_kw(attributes, ('colour', 'color'), default_colour)
        #     offset_x = attributes.get('offset_x', default_offset_x)
        #     offset_y = attributes.get('offset_y', default_offset_y)
        #     udata = attributes.get('data', default_data)
        #
        #     # check values that can be wrong
        #     if not placement:
        #         placement = default_placement
        #
        #     # convert various colour formats to internal (r, g, b, a)
        #     colour = self.colour_to_internal(colour)
        #
        #     draw_data.append((p, placement, width, colour, offset_x, offset_y, udata))
        #
        # return self.add_layer(painter=self.draw_polyline_layer,
        #                       data=draw_data,
        #                       map_rel=map_rel,
        #                       visible=visible,
        #                       show_levels=show_levels,
        #                       selectable=selectable,
        #                       name=name,
        #                       ltype=LayerType.TypePolyline)

        # get unique layer ID
        layer_id = self.next_layer_id
        self.next_layer_id += 1

        # prepare the show_level value
        if show_levels is None:
            show_levels = range(self.tiles_min_level, self.tiles_max_level + 1)[:]

        # create layer, add unique ID to Z order list
        layer = PolylineLayer(layer_id=layer_id,
                              painter=self.draw_polyline_layer,
                              data=data,
                              map_rel=map_rel,
                              visible=visible,
                              show_levels=show_levels,
                              selectable=selectable,
                              name=name)

        self.layer_mapping[layer_id] = layer
        self.layer_z_order.append(layer_id)

        # force display of new layer if it's visible
        if visible:
            self.update()

        return layer_id

    def ShowLayer(self, layer_id: int):
        """
        Show a layer.
        layer_id  the layer layer_id
        """

        self.layer_mapping[layer_id].visible = True
        self.update()

    def HideLayer(self, layer_id: int):
        """
        Hide a layer.
        id  the layer id
        """

        self.layer_mapping[layer_id].visible = False
        self.update()

    def DeleteLayer(self, layer_id: int):
        """
        Delete a layer.
        id  the layer id
        """

        # just in case we got None
        if layer_id is not None:
            if layer_id in self.layer_mapping:

                # see if what we are about to remove might be visible
                layer = self.layer_mapping[layer_id]
                visible = layer.visible

                del layer
                self.layer_z_order.remove(layer_id)

                # if layer was visible, refresh display
                if visible:
                    self.update()

    def PushLayerToBack(self, layer_id: int):
        """
        Make layer specified be drawn at back of Z order.
        id  ID of the layer to push to the back
        """

        self.layer_z_order.remove(layer_id)
        self.layer_z_order.insert(0, layer_id)
        self.update()

    def PopLayerToFront(self, layer_id: int):
        """
        Make layer specified be drawn at front of Z order.
        id  ID of the layer to pop to the front
        """

        self.layer_z_order.remove(layer_id)
        self.layer_z_order.append(layer_id)
        self.update()

    def PlaceLayerBelowLayer(self, below_layer_id: int, top_layer_id: int):
        """
        Place a layer so it will be drawn behind another layer.
        below  ID of layer to place underneath 'top'
        top    ID of layer to be drawn *above* 'below'
        """

        self.layer_z_order.remove(below_layer_id)
        i = self.layer_z_order.index(top_layer_id)
        self.layer_z_order.insert(i, below_layer_id)
        self.update()

    def SetLayerShowLevels(self, layer_id: int, show_levels=None):
        """
        Update the show_levels list for a layer.

        id           ID of the layer we are going to update
        show_levels  new layer show list

        If 'show_levels' is None reset the displayable levels to
        all levels in the current tileset.
        """

        # if we actually got an 'id' change the .show_levels value
        if layer_id:
            layer = self.layer_mapping[layer_id]

            # if not given a 'show_levels' show all levels available
            if not show_levels:
                show_levels = range(self.tiles_min_level,
                                    self.tiles_max_level + 1)[:]

            layer.show_levels = show_levels

            # always update the display, there may be a change
            self.update()

    def GotoLevel(self, level: int):
        """
        Use a new tile level.

        level  the new tile level to use.

        Returns True if all went well.
        """

        if not self.tile_src.UseLevel(level):
            return False  # couldn't change level

        self.level = level
        (self.num_tiles_x, self.num_tiles_y, _, _) = self.tile_src.GetInfo(level)
        self.map_width = self.num_tiles_x * self.tile_width
        self.map_height = self.num_tiles_y * self.tile_height
        (self.map_llon, self.map_rlon,
         self.map_blat, self.map_tlat) = self.tile_src.extent

        # to set some state variables
        self.resizeEvent()

        # raise level change event
        LevelEvent(level=level).emit_event()

        return True

    def GotoPosition(self, xgeo: float, ygeo: float):
        """Set view to centre on a geo position in the current level.

        geo  a tuple (xgeo,ygeo) to centre view on

        Recalculates the key tile info.
        """
        if xgeo is None:
            return

        # get fractional tile coords of required centre of view
        xtile, ytile = self.tile_src.Geo2Tile(xgeo, ygeo)

        # get view size in half widths and height
        w2 = self.view_width / 2
        h2 = self.view_height / 2

        # get tile coords of view left and top edges
        view_tile_x = xtile - (w2 / self.tile_width)
        view_tile_y = ytile - (h2 / self.tile_height)

        # calculate the key tile coords and offsets
        keytile_x = int(view_tile_x)
        keytile_y = int(view_tile_y)

        keyoffset_x = - int((view_tile_x - keytile_x) * self.tile_width)
        keyoffset_y = - int((view_tile_y - keytile_y) * self.tile_height)

        # update the key tile info
        self.key_tile_left = keytile_x
        self.key_tile_top = keytile_y
        self.key_tile_xoffset = keyoffset_x
        self.key_tile_yoffset = keyoffset_y

        # centre map in view if map < view
        if self.key_tile_left < 0 or self.key_tile_xoffset > 0:
            self.key_tile_left = 0
            self.key_tile_xoffset = (self.view_width - self.map_width) // 2

        if self.key_tile_top < 0 or self.key_tile_yoffset > 0:
            self.key_tile_top = 0
            self.key_tile_yoffset = (self.view_height - self.map_height) // 2

        # redraw the display
        self.update()

        self.position_callback(xgeo, ygeo)

    def GotoLevelAndPosition(self, level: int, longitude: float, latitude: float):
        """Goto a map level and set view to centre on a position.

        level  the map level to use
        geo    a tuple (xgeo,ygeo) to centre view on

        Does nothing if we can't use desired level.
        """

        if self.GotoLevel(level):
            self.GotoPosition(xgeo=longitude, ygeo=latitude)

    def ZoomToArea(self, longitude: float, latitude: float, size: int):
        """Set view to level and position to view an area.

        geo   a tuple (xgeo,ygeo) to centre view on
        size  a tuple (width,height) of area in geo coordinates

        Centre an area and zoom to view such that the area will fill
        approximately 50% of width or height, whichever is greater.

        Use the ppd_x and ppd_y values in the level 'tiles' file.
        """

        # unpack area width/height (geo coords)
        (awidth, aheight) = size

        # step through levels (smallest first) and check view size (degrees)
        level = 0
        for level in self.tile_src.levels:
            (_, _, ppd_x, ppd_y) = self.tile_src.getInfo(level)
            view_deg_width = self.view_width / ppd_x
            view_deg_height = self.view_height / ppd_y

            # if area >= 50% of view, finished
            if awidth >= view_deg_width / 2 or aheight >= view_deg_height / 2:
                break

        self.GotoLevelAndPosition(level=level, longitude=longitude, latitude=latitude)

    def ChangeTileSet(self, tile_src):
        """Change the source of tiles.

        tile_src  the new tileset object to use

        Returns the previous tileset object, None if none.

        Refreshes the display and tries to maintain the same position
        and zoom level.  May change the zoom level if the current level doesn't
        exist in the new tileset.
        """

        log('ChangeTileSet: tile_src=%s' % str(tile_src))

        # get level and geo position of view centre
        level, xgeo, ygeo = self.get_level_and_position()
        log('level=%s, geo=(%s, %s)' % (str(level), str(xgeo), str(ygeo)))

        # remember old tileset
        old_tileset = self.tile_src

        # get levels in new tileset and see if we can display at the current level
        new_levels = tile_src.levels
        new_max_level = tile_src.max_level
        new_min_level = tile_src.min_level
        if level > new_max_level:
            level = new_max_level
        if level < new_min_level:
            level = new_min_level

        # set new tile source and set some state
        self.tile_src = tile_src
        self.tile_size_x = tile_src.tile_size_x
        self.tile_size_y = tile_src.tile_size_y
        self.level = level

        result = self.tile_src.GetInfo(level)
        (num_tiles_x, num_tiles_y, ppd_x, ppd_y) = result
        self.map_width = self.tile_size_x * num_tiles_x
        self.map_height = self.tile_size_y * num_tiles_y
        self.ppd_x = ppd_x
        self.ppd_y = ppd_y

        # set tile levels stuff - allowed levels, etc
        self.tiles_max_level = max(tile_src.levels)
        self.tiles_min_level = min(tile_src.levels)

        # set callback from Tile source object when tile(s) available
        self.tile_src.setCallback(self.on_tile_available)

        # set the new zoom level to the old
        if not tile_src.UseLevel(self.level):
            # can't use old level, make sensible choice
            if self.level < self.tiles_min_level:
                self.level = self.tiles_min_level
            elif self.level > self.tiles_max_level:
                self.level = self.tiles_max_level

            # if we can't change level now, raise an error exception
            if not tile_src.UseLevel(self.level):
                raise Exception('Trying to use level %s in tile obj %s, '
                                'levels available are %s'
                                % (str(self.level),
                                   str(tile_src), str(tile_src.levels)))

        # TODO: MUST SET KEY TILE STUFF HERE
        self.set_key_from_centre(xgeo, ygeo)

        # back to old level+centre, and refresh the display
        #        self.GotoLevelAndPosition(level, geo)
        self.zoom_level_position(level, xgeo, ygeo)

        return old_tileset
