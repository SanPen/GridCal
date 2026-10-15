"""Draw OpenMapTiles vector data using Qt, without a browser or native bridge."""

from enum import Enum
from typing import Any

from VeraGrid.Gui.Diagrams.MapWidget.Tiles.vector_tile_decoder import decode
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen


class MapStyle(Enum):
    """Qt basemap palettes, independent of the MapLibre style language."""

    Colour = 'colour'
    Light = 'light'
    Dark = 'dark'


class MapColours:
    """Fixed colours shared by all features in one rendered tile."""

    __slots__ = ('land', 'water', 'park', 'urban', 'building', 'road', 'motorway', 'border', 'text', 'halo')

    def __init__(self, style: MapStyle) -> None:
        """
        Select the palette once, outside the feature drawing loops.

        :param style: Requested Qt map palette.
        """
        values: tuple[str, ...]
        if style == MapStyle.Dark:
            values = ('#242424', '#111b25', '#23312a', '#2e2e2e', '#383838',
                      '#555555', '#88806b', '#777777', '#d3d3d3', '#242424')
        elif style == MapStyle.Light:
            values = ('#f7f7f5', '#d4dadc', '#e2e8df', '#eeeeec', '#dededb',
                      '#ffffff', '#b9b9b6', '#aaaaaa', '#555555', '#ffffff')
        else:
            values = ('#f3efdf', '#abcddd', '#c9ddba', '#e8e3d8', '#d6cbbd',
                      '#ffffff', '#e7bc72', '#a59ba5', '#454545', '#faf8ef')
        self.land: QColor = QColor(values[0])
        self.water: QColor = QColor(values[1])
        self.park: QColor = QColor(values[2])
        self.urban: QColor = QColor(values[3])
        self.building: QColor = QColor(values[4])
        self.road: QColor = QColor(values[5])
        self.motorway: QColor = QColor(values[6])
        self.border: QColor = QColor(values[7])
        self.text: QColor = QColor(values[8])
        self.halo: QColor = QColor(values[9])


def feature_label_rank(feature: dict[str, Any]) -> float:
    """
    Prioritize important places before reserving space for smaller labels.

    :param feature: Decoded OpenMapTiles feature.
    :return: Numeric rank; unranked features sort last.
    """
    properties: dict[str, Any] = feature.get('properties', dict())
    rank: Any = properties.get('rank', 100)
    if isinstance(rank, (int, float)):
        return float(rank)
    else:
        return 100.0


def append_line(path: QPainterPath, points: list[list[float]], scale: float,
                offset_x: float, offset_y: float, close: bool) -> None:
    """
    Transform one vector line or polygon ring into output tile pixels.

    :param path: Painter path receiving this ring.
    :param points: Coordinates in the source tile's extent.
    :param scale: Source coordinate to output pixel scale, including overzoom.
    :param offset_x: Horizontal source crop offset in output pixels.
    :param offset_y: Vertical source crop offset in output pixels.
    :param close: Whether to close this polygon ring.
    """
    if len(points) > 0:
        path.moveTo(points[0][0] * scale - offset_x, points[0][1] * scale - offset_y)
        index: int
        for index in range(1, len(points)):
            point: list[float] = points[index]
            path.lineTo(point[0] * scale - offset_x, point[1] * scale - offset_y)
        if close:
            path.closeSubpath()
        else:
            pass
    else:
        pass


def geometry_path(geometry: dict[str, Any], scale: float,
                  offset_x: float, offset_y: float) -> QPainterPath:
    """
    Convert decoded line and polygon geometries, preserving polygon holes.

    :param geometry: GeoJSON geometry produced by the vector-tile decoder.
    :param scale: Coordinate to pixel scale.
    :param offset_x: Source crop's horizontal pixel offset.
    :param offset_y: Source crop's vertical pixel offset.
    :return: Qt path with odd-even fill for polygon holes.
    """
    path: QPainterPath = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    coordinates: list[Any] = geometry.get('coordinates', list())
    geometry_type: str = geometry.get('type', '')
    part: list[Any]
    if geometry_type == 'LineString':
        append_line(path, coordinates, scale, offset_x, offset_y, False)
    elif geometry_type in ('Polygon', 'MultiLineString'):
        for part in coordinates:
            append_line(path, part, scale, offset_x, offset_y, geometry_type == 'Polygon')
    elif geometry_type == 'MultiPolygon':
        ring: list[list[float]]
        for part in coordinates:
            for ring in part:
                append_line(path, ring, scale, offset_x, offset_y, True)
    else:
        pass
    return path


class VectorTileRenderer:
    """Render keyless OpenFreeMap data to the existing Qt tile cache format."""

    __slots__ = ('colours',)

    def __init__(self, style: MapStyle) -> None:
        """
        Prepare the fixed Qt palette.

        :param style: Colour, light or dark basemap.
        """
        self.colours: MapColours = MapColours(style)

    def render(self, payload: bytes, level: int, source_level: int,
               x: int, y: int) -> bytes:
        """
        Decode and draw a source vector tile, cropping for overzoom as needed.

        :param payload: Uncompressed Mapbox Vector Tile protobuf bytes.
        :param level: Requested desktop tile zoom.
        :param source_level: Available vector data zoom (usually at most 14).
        :param x: Requested desktop tile column.
        :param y: Requested desktop tile row.
        :return: PNG bytes; failures propagate to the tile worker's error handler.
        """
        layers: dict[str, Any] = decode(payload)
        image: QImage = QImage(256, 256, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(self.colours.land)
        painter: QPainter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        factor: int = 2 ** (level - source_level)
        offset_x: float = float((x % factor) * 256)
        offset_y: float = float((y % factor) * 256)
        try:
            # Draw broad surfaces before roads and boundaries, then add labels.
            layer_name: str
            for layer_name in ('landcover', 'landuse', 'park', 'water', 'waterway',
                               'building', 'aeroway', 'transportation', 'boundary'):
                layer: dict[str, Any] | None = layers.get(layer_name, None)
                if layer is not None:
                    extent: int = layer.get('extent', 4096)
                    if extent > 0:
                        scale: float = 256.0 * factor / extent
                        feature: dict[str, Any]
                        for feature in layer.get('features', list()):
                            self.draw_feature(painter, layer_name, feature, scale, offset_x, offset_y, level)
                    else:
                        pass
                else:
                    pass
            self.draw_labels(painter, layers, factor, offset_x, offset_y, level)
        finally:
            # QImage painting is safe in workers; QPixmap creation stays in Qt's GUI thread.
            painter.end()
        data: QByteArray = QByteArray()
        buffer: QBuffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        saved: bool = image.save(buffer, 'PNG')
        buffer.close()
        if saved:
            return bytes(data)
        else:
            raise ValueError('Could not encode the Qt vector map tile')

    def draw_feature(self, painter: QPainter, layer_name: str, feature: dict[str, Any],
                     scale: float, offset_x: float, offset_y: float, level: int) -> None:
        """
        Paint one surface, road or boundary using OpenMapTiles classifications.

        :param painter: Active tile painter.
        :param layer_name: Source layer's name.
        :param feature: Decoded geometry and properties.
        :param scale: Source-to-output scale.
        :param offset_x: Crop offset in pixels.
        :param offset_y: Crop offset in pixels.
        :param level: Requested zoom, controlling road widths and minor detail.
        """
        geometry: dict[str, Any] = feature.get('geometry', dict())
        properties: dict[str, Any] = feature.get('properties', dict())
        feature_class: str = properties.get('class', '')
        path: QPainterPath = geometry_path(geometry, scale, offset_x, offset_y)
        bounds: QRectF = QRectF(-8.0, -8.0, 272.0, 272.0)
        if path.isEmpty() or not path.boundingRect().intersects(bounds):
            return
        else:
            pass
        colour: QColor = self.colours.urban
        width: float = 1.0
        if layer_name in ('water', 'waterway'):
            colour = self.colours.water
        elif layer_name == 'building':
            colour = self.colours.building
        elif layer_name in ('landcover', 'park'):
            colour = self.colours.park
        elif layer_name == 'transportation':
            if feature_class in ('motorway', 'trunk', 'primary', 'secondary'):
                colour = self.colours.motorway
                width = max(1.0, min(6.0, (level - 5) * 0.5))
            elif feature_class in ('path', 'track', 'service', 'minor', 'tertiary', 'street'):
                colour = self.colours.road
                width = max(0.5, min(4.0, (level - 10) * 0.5))
            else:
                colour = self.colours.border
                width = 0.5
        elif layer_name == 'boundary':
            colour = self.colours.border
            width = 0.6
        else:
            pass
        geometry_type: str = geometry.get('type', '')
        if geometry_type in ('Polygon', 'MultiPolygon'):
            painter.fillPath(path, colour)
        else:
            pen: QPen = QPen(colour, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            if layer_name == 'boundary':
                pen.setStyle(Qt.PenStyle.DashLine)
            else:
                pass
            painter.strokePath(path, pen)

    def draw_labels(self, painter: QPainter, layers: dict[str, Any], factor: int,
                    offset_x: float, offset_y: float, level: int) -> None:
        """
        Place readable text labels without overlapping labels within a tile.

        :param painter: Active tile painter.
        :param layers: Decoded tile layers.
        :param factor: Overzoom multiplier.
        :param offset_x: Crop offset in pixels.
        :param offset_y: Crop offset in pixels.
        :param level: Requested zoom, controlling label sizes and road names.
        """
        # shortcut: labels collide per tile, use a viewport label pass if cross-tile placement is required.
        occupied: list[QRectF] = [QRectF() for _ in range(128)]
        count: int = 0
        layer_name: str
        for layer_name in ('place', 'water_name', 'transportation_name'):
            layer: dict[str, Any] | None = layers.get(layer_name, None)
            if layer is not None and (layer_name != 'transportation_name' or level >= 14):
                extent: int = layer.get('extent', 4096)
                if extent <= 0:
                    return
                else:
                    pass
                scale: float = 256.0 * factor / extent
                features: list[dict[str, Any]] = sorted(layer.get('features', list()), key=feature_label_rank)
                feature: dict[str, Any]
                for feature in features:
                    properties: dict[str, Any] = feature.get('properties', dict())
                    name: Any = properties.get('name:latin', properties.get('name', ''))
                    if isinstance(name, str) and 0 < len(name) <= 80 and count < len(occupied):
                        geometry: dict[str, Any] = feature.get('geometry', dict())
                        coordinates: list[Any] = geometry.get('coordinates', list())
                        anchor: QPointF | None = None
                        if geometry.get('type', '') == 'Point' and len(coordinates) == 2:
                            anchor = QPointF(coordinates[0] * scale - offset_x,
                                             coordinates[1] * scale - offset_y)
                        else:
                            path: QPainterPath = geometry_path(geometry, scale, offset_x, offset_y)
                            if not path.isEmpty() and path.length() > 60.0:
                                anchor = path.pointAtPercent(0.5)
                            else:
                                pass
                        if anchor is not None:
                            font: QFont = QFont('Sans Serif')
                            font.setPixelSize(13 if properties.get('class', '') in ('city', 'country') else 10)
                            text: QPainterPath = QPainterPath()
                            text.addText(QPointF(0.0, 0.0), font, name)
                            rectangle: QRectF = text.boundingRect()
                            text.translate(anchor.x() - rectangle.center().x(), anchor.y() - rectangle.center().y())
                            rectangle = text.boundingRect().adjusted(-2.0, -2.0, 2.0, 2.0)
                            fits: bool = QRectF(0.0, 0.0, 256.0, 256.0).contains(rectangle)
                            index: int
                            for index in range(count):
                                if occupied[index].intersects(rectangle):
                                    fits = False
                                else:
                                    pass
                            if fits:
                                painter.strokePath(text, QPen(self.colours.halo, 2.5))
                                painter.fillPath(text, self.colours.text)
                                occupied[count] = rectangle
                                count += 1
                            else:
                                pass
                        else:
                            pass
                    else:
                        pass
            else:
                pass
