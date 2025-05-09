"""
MIT License

Copyright (c) 2018 Ross Wilson
Copyright (c) 2024, Santiago Peñate Vera

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

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

xgeo: longitude
ygeo: latitude
"""
from __future__ import annotations
from typing import List, Union, Tuple, Callable, TYPE_CHECKING
from enum import Enum
from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtGui import (QPainter, QColor, QPixmap, QCursor,
                           QMouseEvent, QKeyEvent, QWheelEvent,
                           QResizeEvent, QEnterEvent, QPaintEvent, QDragEnterEvent, QDragMoveEvent, QDropEvent)
from PySide6.QtWidgets import (QSizePolicy, QWidget, QGraphicsScene, QGraphicsView, QStackedLayout,
                               QGraphicsSceneMouseEvent, QGraphicsItem, QLabel, QGraphicsProxyWidget)

from GridCal.Gui.Diagrams.MapWidget.Tiles.tiles import Tiles

if TYPE_CHECKING:
    from GridCal.Gui.Diagrams.MapWidget.grid_map_widget import GridMapWidget


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


class MapDiagramScene(QGraphicsScene):
    """
    CustomScene
    """

    def __init__(self, parent: "MapWidget" = None) -> None:
        super().__init__(parent)

        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)  # For efficient item indexing

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        :param event:
        :return:
        """
        # print(f"Scene pressed at {event.scenePos()}")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        :param event:
        :return:
        """
        # print(f"Scene released at {event.scenePos()}")
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """

        :param event:
        :return:
        """
        super().mouseMoveEvent(event)


class MapView(QGraphicsView):
    """
    MapView
    """

    def __init__(self,
                 scene: QGraphicsScene,
                 map_widget: "MapWidget"):
        """

        :param scene:
        :param map_widget:
        """
        super().__init__(scene)

        self._scene: QGraphicsScene = scene

        self.map_widget = map_widget
        self.setStyleSheet("QGraphicsView { border: none; }")

        # Create a QLabel
        self.attribution_label = QLabel("Bottom Left Label")
        self.attribution_label.setStyleSheet("background-color: rgba(0, 0, 0, 0);"
                                             "color: rgba(150, 150, 150, 180);"
                                             "font-size:9pt")  # Semi-transparent yellow

        # Create a QGraphicsProxyWidget for the QLabel
        self.label_proxy_widget = QGraphicsProxyWidget()
        self.label_proxy_widget.setWidget(self.attribution_label)
        self.label_proxy_widget.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.update_label_position()

        # Add the proxy widget to the scene
        self._scene.addItem(self.label_proxy_widget)

        self.mouse_x = None
        self.mouse_y = None

        self.diagram_w = 25000
        self.diagram_H = 25000

        # self.in_item = False  # looks that it is written but never used
        self.pressed = False
        self.disable_move = False

        # updated later
        self.view_width = self.width()
        self.view_height = self.height()

        # Set initial zoom level (change the values as needed)
        initial_zoom_factor = 1.0
        self.schema_zoom = 1.0

        self.drag_mode = QGraphicsView.DragMode.ScrollHandDrag
        self.setDragMode(self.drag_mode)

        self.scale(initial_zoom_factor, initial_zoom_factor)

        self.setRubberBandSelectionMode(Qt.ItemSelectionMode.IntersectsItemShape)

        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)

    def set_notice(self, val: str):
        """

        :param val:
        :return:
        """
        self.attribution_label.setText(val)

    def selected_items(self) -> List[QGraphicsItem]:
        """
        Get the selected items
        :return:
        """
        return self._scene.selectedItems()

    def mousePressEvent(self, event: QMouseEvent):
        """

        :param event:
        :return:
        """
        self.map_widget.mousePressEvent(event)
        self.pressed = True
        self.disable_move = False

        # By pressing ctrl while dragging, we can move the grid
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.drag_mode = QGraphicsView.DragMode.RubberBandDrag
            self.map_widget.block_movement = True
        else:
            self.drag_mode = QGraphicsView.DragMode.ScrollHandDrag
            self.map_widget.block_movement = False

        self.setDragMode(self.drag_mode)

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """

        :param event:
        :return:
        """
        self.map_widget.mouseReleaseEvent(event)
        self.pressed = False
        self.disable_move = True
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """

        :param event:
        :return:
        """
        self.map_widget.mouseDoubleClickEvent(event)
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """

        :param event:
        :return:
        """
        if not self.disable_move:
            self.map_widget.mouseMoveEvent(event)
            self.center_schema()

        super().mouseMoveEvent(event)
        self.update_label_position()

    def keyPressEvent(self, event: QKeyEvent):
        """

        :param event:
        :return:
        """
        self.map_widget.keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        """

        :param event:
        :return:
        """
        self.map_widget.keyReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """

        :param event:
        :return:
        """
        zoom_0 = self.map_widget.level

        self.mouse_x = event.position().x()
        self.mouse_y = event.position().y()

        if event.angleDelta().y() > 0:
            new_level = zoom_0 + 1
        else:
            new_level = zoom_0 - 1

        if self.map_widget.tile_src.level_in_range(new_level):

            val = self.map_widget.set_zoom_level(level=new_level,
                                                 view_x=self.mouse_x,
                                                 view_y=self.mouse_y)

            if val:
                if event.angleDelta().y() > 0:
                    self.schema_zoom = self.schema_zoom * self.map_widget.zoom_factor
                    self.scale(
                        self.map_widget.zoom_factor,
                        self.map_widget.zoom_factor
                    )
                else:
                    self.schema_zoom = self.schema_zoom / self.map_widget.zoom_factor
                    self.scale(
                        1.0 / self.map_widget.zoom_factor,
                        1.0 / self.map_widget.zoom_factor
                    )
            else:
                # revert to the previous zoom
                self.map_widget.set_zoom_level(level=zoom_0,
                                               view_x=self.mouse_x,
                                               view_y=self.mouse_y)

            self.map_widget.wheelEvent(event)
            self.center_schema()
            self.update_label_position()

        else:
            print(f"Zoom {new_level} out of range...")

    def dragEnterEvent(self, event: QDragEnterEvent):
        """

        :param event:
        :return:
        """
        if event.mimeData().hasFormat('component/name'):
            event.accept()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """

        :param event:
        :return:
        """
        pass

    def dropEvent(self, event: QDropEvent):
        """

        :param event:
        :return:
        """
        super().dropEvent(event)
        self.map_widget.dropEvent(event)

    def resizeEvent(self, event: QResizeEvent = None):
        """
        Widget resized, recompute some state.
        """

        super().resizeEvent(event)
        self.map_widget.resizeEvent(event=event)

    def update_label_position(self):
        """
        Updates the position of the label to the bottom-left corner of the viewport.
        """
        view_width = self.viewport().width()
        view_height = self.viewport().height()

        # Set position relative to the bottom-left corner of the viewport
        self.label_proxy_widget.setPos(self.mapToScene(0, view_height - self.attribution_label.height()))

    def set_size_diagram(self) -> None:
        """

        :return:
        """
        # new widget size
        self.view_width = self.width()
        self.view_height = self.height()

    def set_scene_rect_diagram(self) -> None:
        """

        :return:
        """
        used_width = self.diagram_w
        used_height = self.diagram_H

        xToDiagram = -(used_width / 2)
        yToDiagram = -(used_height / 2)

        # Adjust the scene rect if needed
        self.setSceneRect(xToDiagram, yToDiagram, used_width, used_height)

        self.center_schema()

    def to_lat_lon(self, x: float, y: float) -> Tuple[float, float]:
        """
        Convert x, y position in the map to latitude and longitude
        :param x: x position in pixels
        :param y: y position in pixels
        :return: latitude, longitude
        """

        ix, iy = self.map_widget.geo_to_view(longitude=0, latitude=0)

        x2 = (x * self.schema_zoom) + ix
        y2 = (y * self.schema_zoom) + iy

        lon, lat = self.map_widget.view_to_geo_float(xview=x2, yview=y2)

        return lat, lon

    def to_x_y(self, lat: float, lon: float) -> Tuple[float, float]:
        """

        :param lat: latitude (deg)
        :param lon: longitude (deg)
        :return: x, y in the map
        """

        ix, iy = self.map_widget.geo_to_view(longitude=0.0, latitude=0.0)

        x, y = self.map_widget.geo_to_view(longitude=lon, latitude=lat)

        x = (x - ix) / self.schema_zoom
        y = (y - iy) / self.schema_zoom

        return x, y

    def center_schema(self) -> None:
        """
        This function centers the schema relative to the map according to lat. and long.
        """

        he = self.map_widget.height() / 2.0
        wi = self.map_widget.width() / 2.0

        lon, lat = self.map_widget.view_to_geo_float(xview=wi, yview=he)

        sx, sy = self.to_x_y(lat=lat, lon=lon)

        point = QPointF(sx - 5 / self.schema_zoom, sy - 5 / self.schema_zoom)

        self.map_widget.view.centerOn(point)

    def get_selected(self) -> List[QGraphicsItem]:
        """
        Get the selection
        :return:
        """
        return self._scene.selectedItems()


class MapWidget(QWidget):
    """
    Map widget
    """

    def __init__(self,
                 parent: Union[None, QWidget],
                 tile_src: Tiles,
                 start_level: int,
                 editor: GridMapWidget,
                 zoom_callback: Callable[[int], None],
                 position_callback: Callable[[float, float, int, int], None]):
        """
        Initialize the widget.
        :param parent: the GUI parent widget
        :param tile_src: a Tiles object, source of tiles
        :param start_level: level to initially display
        :param zoom_callback: zoom change callback function
        :param position_callback: position change callback function
        """

        super().__init__(parent)  # inherit all parent object setup

        # this is where you draw
        self.diagram_scene = MapDiagramScene(self)

        # pointer to the editor
        self.editor: GridMapWidget = editor

        # Create a layout for the view
        self.layout = QStackedLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setStyleSheet("background-color: transparent;")

        # the view is the transparent layer used to draw stuff
        self.view = MapView(scene=self.diagram_scene, map_widget=self)
        self.view.setBackgroundBrush(Qt.GlobalColor.transparent)

        # -------------------------------------------------------------------------
        # Internal vars
        # -------------------------------------------------------------------------
        # remember the tile source object
        self._tile_src: Tiles = tile_src.copy()
        self._tile_src.setCallback(self.on_tile_available)
        self.view.set_notice(val=self._tile_src.attribution_string)

        # the tile coordinates
        self.level: int = start_level

        # callbacks
        self.zoom_callback: Callable[[int], None] = zoom_callback
        self.position_callback: Callable[[float, float, int, int], None] = position_callback

        # define position and tile coords of the "key" tile
        self.key_tile_left = 0  # tile coordinates of key tile
        self.key_tile_top = 0
        self.key_tile_x_offset = 0  # view coordinates of key tile wrt view
        self.key_tile_y_offset = 0

        # we keep track of the cursor coordinates if cursor on map
        self.mouse_x: int = 0
        self.mouse_y: int = 0

        # state variables holding mouse buttons state
        self.left_button_down: bool = False
        self.mid_button_down: bool = False
        self.right_button_down: bool = False
        self._block_movement: bool = False

        # keyboard state variables
        self.shift_down = False
        self.zoom_factor = 2

        # when dragging, remember the initial start point
        self.start_drag_x: int = 0
        self.start_drag_y: int = 0

        self.view_llon = 0
        self.view_rlon = 0
        self.view_blat = 0
        self.view_tlat = 0

        # some cursors
        self.standard_cursor = QCursor(Qt.CursorShape.ArrowCursor)
        self.box_select_cursor = QCursor(Qt.CursorShape.CrossCursor)
        self.wait_cursor = QCursor(Qt.CursorShape.WaitCursor)
        self.drag_cursor = QCursor(Qt.CursorShape.OpenHandCursor)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(self.tile_width, self.tile_height)

        self.setMouseTracking(True)
        self.setEnabled(True)  # to receive key events?

        self.default_cursor = self.standard_cursor
        self.setCursor(self.standard_cursor)

        # do a "resize" after this function
        self.go_to_level_and_position(level=6, longitude=0, latitude=40)
        self.go_to_level_and_position(level=7, longitude=0, latitude=40)
        self.go_to_level_and_position(level=6, longitude=0, latitude=40)

        # add the widgets in a layered manner
        # self.layout.addWidget(self.notice_widget)
        self.layout.addWidget(self.view)  # Add the QGraphicsView to the layout

        self.setLayout(self.layout)  # Set the layout for the MapWidget

    @property
    def block_movement(self):
        return self._block_movement

    @block_movement.setter
    def block_movement(self, value: bool):
        self._block_movement = bool(value)

    @property
    def tile_src(self) -> Tiles:
        """
        Get the current tile source
        :return: Tiles
        """
        return self._tile_src

    @tile_src.setter
    def tile_src(self, tile_src: Tiles):
        """
        Set the current tile source
        :param tile_src: Tiles
        """

        level, longitude, latitude = self.get_level_and_position()

        if tile_src.tile_set_name != self._tile_src.tile_set_name:  # avoid changing tile sets to themselves
            self._tile_src: Tiles = tile_src.copy()
            self._tile_src.setCallback(self.on_tile_available)
            self.view.set_notice(val=self._tile_src.attribution_string)

            if self.GotoLevel(level):
                self.go_to_level_and_position(level=level, longitude=longitude, latitude=latitude)
                self.view.center_schema()
            else:
                while abs(self.view.schema_zoom - 0.015625) > 0.00001:
                    self.view.schema_zoom = self.view.schema_zoom / self.view.map_widget.zoom_factor
                    self.view.scale(1.0 / self.view.map_widget.zoom_factor, 1.0 / self.view.map_widget.zoom_factor)
                self.go_to_level_and_position(level=0, longitude=0, latitude=0)

    @property
    def max_level(self):
        """

        :return:
        """
        return self.tile_src.max_level

    @property
    def min_level(self):
        """

        :return:
        """
        return self.tile_src.min_level

    @property
    def tile_width(self):
        """

        :return:
        """
        return self.tile_src.tile_size_x

    @property
    def tile_height(self):
        """

        :return:
        """
        return self.tile_src.tile_size_y

    @property
    def num_tiles_x(self):
        """

        :return:
        """
        return self.tile_src.num_tiles_x

    @property
    def num_tiles_y(self):
        """

        :return:
        """
        return self.tile_src.num_tiles_y

    @property
    def map_width(self):
        """

        :return:
        """
        return self.num_tiles_x * self.tile_width  # virtual map width

    @property
    def map_height(self):
        """

        :return:
        """
        return self.num_tiles_y * self.tile_height  # virtual map height

    @property
    def view_width(self):
        """

        :return:
        """
        return self.width()

    @property
    def view_height(self):
        """

        :return:
        """
        return self.height()

    def on_tile_available(self, level: int, x: float, y: float, image: QPixmap, error: bool):
        """
        Called when a new 'net tile is available.

        level  the level the tile is for
        x, y   tile coordinates of the tile
        image  the tile image data
        error  True if there was an error

        We have enough information to redraw a specific tile,
        but we just redraw the widget.
        """

        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Mouse button pressed.
        :param event:
        :return:
        """
        super().mousePressEvent(event)

        b = event.button()
        if b == Qt.MouseButton.NoButton:
            pass

        elif b == Qt.MouseButton.LeftButton:
            self.left_button_down = True
            self.editor.object_editor_table.setModel(None)

        elif b == Qt.MouseButton.MiddleButton:
            self.mid_button_down = True

        elif b == Qt.MouseButton.RightButton:
            self.right_button_down = True

        else:
            pass

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Mouse button was released.

        event.x & event.y  view coords when released

        Could be end of a drag or point or box selection.  If it's the end of
        a drag we don't do a lot.  If a selection we process that.
        """
        pos = event.position()
        x = pos.x()
        y = pos.y()

        # cursor back to normal in case it was a box select
        self.setCursor(self.default_cursor)

        b = event.button()
        if b == Qt.MouseButton.NoButton:
            pass
        elif b == Qt.MouseButton.LeftButton:
            self.left_button_down = False

            if self.start_drag_x is None:
                # not dragging, possible point selection
                # get click point in view & global coords
                self.view_to_geo(x, y)

            # turn off dragging, if we were
            self.start_drag_x = self.start_drag_y = None

            longitude, latitude = self.view_to_geo(x, y)
            self.position_callback(latitude, longitude, x, y)

        elif b == Qt.MouseButton.MiddleButton:
            self.mid_button_down = False

        elif b == Qt.MouseButton.RightButton:
            self.right_button_down = False

        else:
            pass
            # print('mouseReleaseEvent: unknown button')

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """

        :param event:
        :return:
        """
        b = event.button()
        if b == Qt.MouseButton.NoButton:
            pass
        elif b == Qt.MouseButton.LeftButton:
            pass
        elif b == Qt.MouseButton.MiddleButton:
            pass
        elif b == Qt.MouseButton.RightButton:
            pass
        else:
            pass
            # print('mouseDoubleClickEvent: unknown button')

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Handle a mouse move event.

        If left mouse down, either drag the map or start a box selection.
        If we are off the map, ensure self.mouse_x, etc, are None.
        """
        if not self.block_movement:
            pos = event.position()
            x = pos.x()
            y = pos.y()

            mouse_geo = self.view_to_geo(x, y)

            # update remembered mouse position in case of zoom
            self.mouse_x = self.mouse_y = None
            if mouse_geo:
                self.mouse_x = x
                self.mouse_y = y

            if self.left_button_down:

                # we are dragging
                if self.start_drag_x is None:
                    # start of drag, set drag state
                    self.start_drag_x = x
                    self.start_drag_y = y

                # we don't move much - less than a tile width/height
                # drag the key tile in the X direction
                delta_x = self.start_drag_x - x
                self.key_tile_x_offset -= delta_x

                if self.key_tile_x_offset < -self.tile_width:  # too far left
                    self.key_tile_x_offset += self.tile_width
                    self.key_tile_left += 1

                if self.key_tile_x_offset > 0:  # too far right
                    self.key_tile_x_offset -= self.tile_width
                    self.key_tile_left -= 1

                # drag the key tile in the Y direction
                delta_y = self.start_drag_y - y
                self.key_tile_y_offset -= delta_y

                if self.key_tile_y_offset < -self.tile_height:  # too far up
                    self.key_tile_y_offset += self.tile_height
                    self.key_tile_top += 1

                if self.key_tile_y_offset > 0:  # too far down
                    self.key_tile_y_offset -= self.tile_height
                    self.key_tile_top -= 1

                # set key tile stuff so update() shows drag
                self.rectify_key_tile()

                # get ready for more drag
                self.start_drag_x = x
                self.start_drag_y = y

                self.update()  # force a repaint

    def keyPressEvent(self, event: QKeyEvent):
        """Capture a key press."""

        if event.key() == Qt.Key.Key_Shift:
            self.shift_down = True
            self.default_cursor = self.box_select_cursor
            self.setCursor(self.default_cursor)

        event.accept()

    def keyReleaseEvent(self, event: QKeyEvent):
        """Capture a key release."""

        key = event.key()
        if event.key() == Qt.Key.Key_Shift:
            self.shift_down = False
            self.default_cursor = self.standard_cursor
            self.setCursor(self.default_cursor)
        event.accept()

    def wheelEvent(self, event: QWheelEvent):
        """
        Handle a mouse wheel rotation.
        """
        self.editor.wheelEvent(event)

    def resizeEvent(self, event: QResizeEvent = None, updateDiagram: bool = True):
        """
        Widget resized, recompute some state.
        """
        if updateDiagram:
            self.view.set_size_diagram()

        # recalculate the "key" tile stuff
        self.rectify_key_tile()

        if updateDiagram:
            self.view.set_scene_rect_diagram()

    def enterEvent(self, event: QEnterEvent):
        """

        :param event:
        """
        self.setFocus()

    def leaveEvent(self, event: QEvent):
        """
        The mouse is leaving the widget.

        Raise a EVT_PYSLIPQT_POSITION event with positions set to None.
        We do this so user code can clear any mouse position data, for example.
        """

        self.mouse_x = 0
        self.mouse_y = 0

    def dropEvent(self, event: QDropEvent):
        """

        :param event:
        :return:
        """
        super().dropEvent(event)
        self.editor.dropEvent(event)

    def paintEvent(self, event: QPaintEvent):
        """
        Draw the base map and then the layers on top.
        """

        # The "key" tile position is maintained by other code, we just
        # assume it's set.  Figure out how to draw tiles, set up 'row_list' and
        # 'col_list' which are list of tile coords to draw (row and colums).

        col_list = []
        x_coord = self.key_tile_left
        x_pix_start = self.key_tile_x_offset
        while x_pix_start < self.view_width:
            col_list.append(x_coord)
            if x_coord >= self.num_tiles_x - 1:
                break
            x_coord = (x_coord + 1) % self.num_tiles_x
            x_pix_start += self.tile_height

        row_list = []
        y_coord = self.key_tile_top
        y_pix_start = self.key_tile_y_offset
        while y_pix_start < self.view_height:
            row_list.append(y_coord)
            if y_coord >= self.num_tiles_y - 1:
                break
            y_coord = (y_coord + 1) % self.num_tiles_y
            y_pix_start += self.tile_height

        # Ready to update the view
        # prepare the canvas
        painter = QPainter()
        painter.begin(self)

        # paste all background tiles onto the view
        x_pix = self.key_tile_x_offset
        for x in col_list:
            y_pix = self.key_tile_y_offset
            for y in row_list:
                painter.drawPixmap(x_pix, y_pix, self.tile_src.GetTile(x, y))
                y_pix += self.tile_height
            x_pix += self.tile_width

        painter.end()

    def geo_to_view(self, longitude: float, latitude: float) -> Union[None, Tuple[float, float]]:
        """
        Convert a geo coord to view.

        geo  tuple (xgeo, ygeo)

        Return a tuple (xview, yview) in view coordinates.
        Assumes point is in view.
        :param longitude:
        :param latitude:
        :return: x, y
        """

        # convert the Geo position to tile coordinates
        if longitude is not None:
            tx, ty = self.tile_src.Geo2Tile(longitude=longitude, latitude=latitude)

            # using the key_tile_* variables to convert to view coordinates
            xview = (tx - self.key_tile_left) * self.tile_width + self.key_tile_x_offset
            yview = (ty - self.key_tile_top) * self.tile_height + self.key_tile_y_offset

            return xview, yview
        else:
            return None

    # def geo_to_view_masked(self, longitude: float, latitude: float) -> Union[None, Tuple[float, float]]:
    #     """
    #     Convert a geo (lon+lat) position to view pixel coords.
    #     Return a tuple (xview, yview) of point if on-view,or None
    #     if point is off-view.
    #     :param longitude:
    #     :param latitude:
    #     :return: x, y
    #     """
    #
    #     if self.view_llon <= longitude <= self.view_rlon and self.view_blat <= latitude <= self.view_tlat:
    #         return self.geo_to_view(longitude, latitude)
    #
    #     return None

    def view_to_geo_float(self, xview: float, yview: float) -> Tuple[Union[None, float], Union[None, float]]:
        """
        Convert a view coords position to a geo coords position.
        Returns a tuple of geo coords (longitude, latitude) if the cursor is over map
        tiles, else returns None.
        Note: the 'key' tile information must be correct.
        :param xview: x position
        :param yview: y position
        :return: longitude, latitude
        """
        min_lon, max_lon, min_lat, max_lat = self.tile_src.GetExtent()

        x_from_key = xview - self.key_tile_x_offset
        y_from_key = yview - self.key_tile_y_offset

        # get view point as tile coordinates
        xtile: float = self.key_tile_left + x_from_key / self.tile_width
        ytile: float = self.key_tile_top + y_from_key / self.tile_height

        longitude, latitude = self.tile_src.Tile2Geo(xtile, ytile)

        if not (min_lon <= longitude <= max_lon):
            return None, None

        if not (min_lat <= latitude <= max_lat):
            return None, None

        return longitude, latitude

    def view_to_geo(self, xview: float, yview: float) -> Tuple[Union[None, float], Union[None, float]]:
        """
        Convert a view coords position to a geo coords position.
        Returns a tuple of geo coords (longitude, latitude) if the cursor is over map
        tiles, else returns None.
        Note: the 'key' tile information must be correct.
        :param xview: x position
        :param yview: y position
        :return: longitude, latitude
        """
        min_lon, max_lon, min_lat, max_lat = self.tile_src.GetExtent()

        x_from_key = xview - self.key_tile_x_offset
        y_from_key = yview - self.key_tile_y_offset

        # get view point as tile coordinates
        xtile: int = int(self.key_tile_left + x_from_key / self.tile_width)
        ytile: int = int(self.key_tile_top + y_from_key / self.tile_height)

        longitude, latitude = self.tile_src.Tile2Geo(xtile, ytile)

        if not (min_lon <= longitude <= max_lon):
            return None, None

        if not (min_lat <= latitude <= max_lat):
            return None, None

        return longitude, latitude

    ######
    # PEX - Point & EXtension.
    #
    # These functions encapsulate the code that finds the extent of an object.
    # They all return a tuple (point, extent) where 'point' is the placement
    # point of an object (or list of points for a polygon) and an 'extent'
    # tuple (lx, rx, ty, by) [left, right, top, bottom].
    ######

    def pex_point(self, place: Place, xgeo: float, latitude: float, x_off: float, y_off: float, radius: float):
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
        xview, yview = self.geo_to_view(xgeo, latitude)
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

    def pex_extent(self, place: Place, xgeo: float, latitude: float, x_off: float, y_off: float, w: int, h: int,
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
        vpoint = self.geo_to_view(xgeo, latitude)
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
        for lon, lat in poly:
            xview, yview = self.geo_to_view(longitude=lon, latitude=lat)
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

    def easy_lat_lon_to_x_y(self, lat: float, lon: float) -> Tuple[float, float]:
        """

        :param lat:
        :param lon:
        :return:
        """
        point, extent = self.pex_point(place=Place.Center,
                                       xgeo=lat,
                                       latitude=lon,
                                       x_off=0.0,
                                       y_off=0.0,
                                       radius=1)
        return point[0], point[1]

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

    def set_zoom_level(self,
                       level: int,
                       view_x: float | None = None,
                       view_y: float | None = None) -> bool:
        """
        Zoom to a map level.

        :param level:  map level to zoom to
        :param view_x: view x coordinate
        :param view_y: view y coordinate

        Change the map zoom level to that given. Returns True if the zoom
        succeeded, else False. If False is returned the method call has no effect.
        Same operation as .GotoLevel() except we try to maintain the geo position
        under the cursor.
        """

        # if not given cursor coords, assume view centre
        if view_x is None:
            view_x = self.view_width // 4

        if view_y is None:
            view_y = self.view_height // 4

        # get geo coords of view point
        longitude, latitude = self.view_to_geo_float(view_x, view_y)

        # get tile source to use the new level
        result = self.tile_src.set_level(level)

        if result:
            # zoom worked, adjust state variables
            self.level = level

            # move to new level
            self.tile_src.GetInfo(level)

            # finally, pan to original map centre (updates widget)
            self.pan_position(longitude, latitude, view_x, view_y)

            # to set some state variables
            self.resizeEvent()

        self.zoom_callback(level)

        return result

    def pan_position(self, longitude: float, latitude: float, view_x: int = None, view_y: int = None):
        """
        Pan the given geo position in the current map zoom level.

        We just adjust the key tile to place the required geo position at the
        given view coordinates.  If that is not possible, just centre in either
        the X or Y directions, or both.

        :param longitude:
        :param latitude:
        :param view_x:
        :param view_y:
        :return:
        """

        # if not given a "view", assume the view centre coordinates
        if view_x is None:
            view_x = self.view_width // 2

        if view_y is None:
            view_y = self.view_height // 2

        if longitude is None:
            return

        # convert the geo position to a tile position
        tile_x, tile_y = self.tile_src.Geo2Tile(longitude, latitude)

        # determine what the new key tile should be
        # figure out number of tiles from centre point to edges
        tx = view_x / self.tile_width
        ty = view_y / self.tile_height

        # calculate tile coordinates of the top-left corner of the view
        key_tx = tile_x - tx
        key_ty = tile_y - ty

        (key_tile_left, x_offset) = divmod(key_tx, 1)
        self.key_tile_left = int(key_tile_left)
        self.key_tile_x_offset = -int(x_offset * self.tile_width)

        (key_tile_top, y_offset) = divmod(key_ty, 1)
        self.key_tile_top = int(key_tile_top)
        self.key_tile_y_offset = -int(y_offset * self.tile_height)

        # adjust key tile, if necessary
        self.rectify_key_tile()

        # redraw the widget
        self.update()

    def rectify_key_tile(self) -> None:
        """
        Adjust state variables to ensure map centred if map is smaller than view.
        Otherwise don't allow edges to be exposed.
        Adjusts the "key" tile variables to ensure proper presentation.
        Relies on .map_width, .map_height and .key_tile_* being set.
        """

        # check map in X direction
        if self.map_width < self.view_width:
            # map < view, fits totally in view, centre in X
            self.key_tile_left = 0
            self.key_tile_x_offset = (self.view_width - self.map_width) // 2
        else:
            # if key tile out of map in X direction, rectify
            if self.key_tile_left < 0:
                self.key_tile_left = 0
                self.key_tile_x_offset = 0
            else:
                # if map left/right edges showing, cover them
                show_len = (self.num_tiles_x - self.key_tile_left) * self.tile_width + self.key_tile_x_offset
                if show_len < self.view_width:
                    # figure out key tile X to have right edge of map and view equal
                    tiles_showing = self.view_width / self.tile_width
                    int_tiles = int(tiles_showing)
                    self.key_tile_left = self.num_tiles_x - int_tiles - 1
                    self.key_tile_x_offset = -int((1.0 - (tiles_showing - int_tiles)) * self.tile_width)

        # now check map in Y direction
        if self.map_height < self.view_height:
            # map < view, fits totally in view, centre in Y
            self.key_tile_top = 0
            self.key_tile_y_offset = (self.view_height - self.map_height) // 2
        else:
            if self.key_tile_top < 0:
                # map top edge showing, cover
                self.key_tile_top = 0
                self.key_tile_y_offset = 0
            else:
                # if map bottom edge showing, cover
                show_len = (self.num_tiles_y - self.key_tile_top) * self.tile_height + self.key_tile_y_offset
                if show_len < self.view_height:
                    # figure out key tile Y to have bottom edge of map and view equal
                    tiles_showing = self.view_height / self.tile_height
                    int_tiles = int(tiles_showing)
                    self.key_tile_top = self.num_tiles_y - int_tiles - 1
                    self.key_tile_y_offset = -int((1.0 - (tiles_showing - int_tiles)) * self.tile_height)

    def zoom_level_position(self, level: int, longitude: float, latitude: float):
        """Zoom to a map level and pan to the given position in the map.

        level  map level to zoom to
        posn  a tuple (xgeo, ygeo)
        """

        if self.set_zoom_level(level):
            self.pan_position(longitude, latitude)

    def get_level_and_position(self, place=Place.Center):
        """Get the level and geo position of a cardinal point within the view.

        place  a placement string specifying the point in the view
               for which we require the geo position

        Returns a tuple (level, geo) where 'geo' is (geo_x, geo_y).
        """

        view_x, view_y = self.point_placement_view(place, 0, 0, 0, 0, )
        longitude, latitude = self.view_to_geo(view_x, view_y)

        return self.level, longitude, latitude

    def set_key_from_centre(self, longitude: float, latitude: float):
        """Set 'key' tile stuff from given geo at view centre.

        geo  geo coords of centre of view

        We need to assume little about which state variables are set.
        Only assume these are set:
            self.tile_width
            self.tile_height
        """
        if longitude is None:
            return

        ctile_tx, ctile_ty = self.tile_src.Geo2Tile(longitude, latitude)

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
        self.key_tile_x_offset = self.tile_width - xmargin
        self.key_tile_y_offset = self.tile_height - ymargin

        # centre map in view if map < view
        if self.key_tile_left < 0:
            self.key_tile_left = 0
            self.key_tile_x_offset = (self.view_width - self.map_width) // 2

        if self.key_tile_top < 0:
            self.key_tile_top = 0
            self.key_tile_y_offset = (self.view_height - self.map_height) // 2

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
            result = [int(v * 255) for v in tuple(colour.getRgbF())]
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

    ################################################################################
    # Below are the "external" API methods.
    ################################################################################

    ######
    # "add a layer" routines
    ######

    def GotoLevel(self, level: int):
        """
        Use a new tile level.
        :param: level  the new tile level to use.
        Returns True if all went well.
        """

        if not self.tile_src.set_level(level):
            return False  # couldn't change level

        self.level = level

        self.tile_src.GetInfo(level)

        # to set some state variables
        self.resizeEvent(updateDiagram=False)

        return True

    def go_to_position(self, longitude: float, latitude: float):
        """Set view to centre on a geo position in the current level.

        geo  a tuple (xgeo,ygeo) to centre view on

        Recalculates the key tile info.
        """
        if longitude is None:
            return

        # get fractional tile coords of required centre of view
        x_tile, y_tile = self.tile_src.Geo2Tile(longitude=longitude, latitude=latitude)

        # get view size in half widths and height
        w2 = self.view_width / 2
        h2 = self.view_height / 2

        # get tile coords of view left and top edges
        view_tile_x = x_tile - (w2 / self.tile_width)
        view_tile_y = y_tile - (h2 / self.tile_height)

        # calculate the key tile coords and offsets
        key_tile_x = int(view_tile_x)
        key_tile_y = int(view_tile_y)

        key_offset_x = - int((view_tile_x - key_tile_x) * self.tile_width)
        key_offset_y = - int((view_tile_y - key_tile_y) * self.tile_height)

        # update the key tile info
        self.key_tile_left = key_tile_x
        self.key_tile_top = key_tile_y
        self.key_tile_x_offset = key_offset_x
        self.key_tile_y_offset = key_offset_y

        # centre map in view if map < view
        if self.key_tile_left < 0 or self.key_tile_x_offset > 0:
            self.key_tile_left = 0
            self.key_tile_x_offset = (self.view_width - self.map_width) // 2

        if self.key_tile_top < 0 or self.key_tile_y_offset > 0:
            self.key_tile_top = 0
            self.key_tile_y_offset = (self.view_height - self.map_height) // 2

        # redraw the display
        self.update()

        self.position_callback(latitude, longitude, x_tile, y_tile)

    def go_to_level_and_position(self, level: int, longitude: float, latitude: float):
        """
        Goto a map level and set view to centre on a position.

        :param level: zoom level (int value)
        :param longitude: longitude (deg)
        :param latitude: latitude (deg)
        """

        if self.GotoLevel(level):
            self.go_to_position(longitude=longitude, latitude=latitude)

    def change_tile_set(self, tile_src: Tiles) -> Tiles:
        """
        Change the source of tiles.

        :param tile_src:  the new Tiles object to use

        Returns the previous Tiles object, None if none.

        Refreshes the display and tries to maintain the same position
        and zoom level.  May change the zoom level if the current level doesn't
        exist in the new Tiles.
        """

        # get level and geo position of view centre
        level, longitude, latitude = self.get_level_and_position()
        # print('level=%s, geo=(%s, %s)' % (str(level), str(longitude), str(latitude)))

        # remember old Tiles object
        old_tile_set = self.tile_src

        # get levels in new tile set and see if we can display at the current level
        new_levels = tile_src.levels
        new_max_level = tile_src.max_level
        new_min_level = tile_src.min_level

        if level > new_max_level:
            level = new_max_level

        if level < new_min_level:
            level = new_min_level

        # set new tile source and set some state
        self.tile_src = tile_src

        self.level = level

        # set callback from Tile source object when tile(s) available
        self.tile_src.setCallback(self.on_tile_available)

        # set the new zoom level to the old
        if not tile_src.set_level(self.level):
            # can't use old level, make sensible choice
            if self.level < self.min_level:
                self.level = self.min_level

            elif self.level > self.max_level:
                self.level = self.max_level

            # if we can't change level now, raise an error exception
            if not tile_src.set_level(self.level):
                raise Exception('Trying to use level %s in tile obj %s, '
                                'levels available are %s'
                                % (str(self.level),
                                   str(tile_src), str(tile_src.levels)))

        # TODO: MUST SET KEY TILE STUFF HERE
        self.set_key_from_centre(longitude, latitude)

        # back to old level+centre, and refresh the display
        self.zoom_level_position(level, longitude, latitude)

        return old_tile_set

    def get_selected(self) -> List[QGraphicsItem]:
        """
        Get the selection
        :return:
        """
        return self.view.get_selected()
