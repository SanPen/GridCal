# # Decode-only Mapbox Vector Tiles
#
# Geometry assembly is adapted from `decoder.py` in
# [tilezen/mapbox-vector-tile 2.2.0](https://github.com/tilezen/mapbox-vector-tile/tree/v2.2.0),
# under the MIT licence reproduced below (Copyright 2014 Mapzen).
#
# VeraGrid changes:
#
# - Replaced generated protobuf messages with a bounded standard-library wire reader.
# - Retained geometry assembly for points, lines, polygons, holes and multipart shapes.
# - Exposed only `decode(payload)`, returning GeoJSON-compatible layer dictionaries
#   with tile-local, top-down coordinates for Qt painting.
# - Removed encoding, geometry repair, configurable coordinate transforms and the
#   protobuf, Shapely and pyclipper dependencies.
# - Added explicit validation for truncated fields, overflowing integers, invalid
#   geometry commands and property indices.
#
# This is a maintained local adaptation, not a drop-in replacement for the full
# upstream package. It accepts MVT versions 1 and 2 and protobuf wire types 0, 1,
# 2 and 5. Protobuf groups and future MVT versions are not supported.
#
# The MIT License (MIT)
#
# Copyright (c) 2014 Mapzen
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import struct
from collections.abc import Iterator
from enum import Enum
from typing import Any


class GeometryKind(Enum):
    """Geometry identifiers defined by the Mapbox Vector Tile specification."""

    Point = 1
    LineString = 2
    Polygon = 3


class GeometryCommand(Enum):
    """Commands in a vector tile's delta-encoded geometry stream."""

    MoveTo = 1
    LineTo = 2
    ClosePath = 7


def read_varint(data: memoryview, position: int) -> tuple[int, int]:
    """
    Read one bounded protobuf uint64 without reading past the message.

    :param data: Current protobuf message.
    :param position: First byte of the integer.
    :return: Integer and the first position after its encoding.
    """
    result: int = 0
    shift: int
    for shift in range(0, 70, 7):
        if position >= len(data):
            raise ValueError('Truncated vector tile varint')
        else:
            pass
        value: int = data[position]
        position += 1
        if shift == 63 and value > 1:
            raise ValueError('Vector tile varint exceeds uint64')
        else:
            pass
        result |= (value & 127) << shift
        if value < 128:
            return result, position
        else:
            pass
    raise ValueError('Unterminated vector tile varint')


def message_fields(data: memoryview) -> Iterator[tuple[int, int, int | memoryview]]:
    """
    Read scalar and length-delimited fields, including unknown extension fields.

    :param data: One bounded protobuf message.
    :return: Iterator of field number, wire type and integer or byte-view value.
    """
    position: int = 0
    while position < len(data):
        tag: int
        tag, position = read_varint(data, position)
        number: int = tag >> 3
        wire: int = tag & 7
        if not 0 < number <= 536870911:
            raise ValueError('Invalid vector tile field number')
        else:
            pass
        if wire == 0:
            value: int
            value, position = read_varint(data, position)
            yield number, wire, value
        else:
            size: int
            if wire == 1:
                size = 8
            elif wire == 2:
                size, position = read_varint(data, position)
            elif wire == 5:
                size = 4
            else:
                raise ValueError('Unsupported vector tile protobuf wire type')
            end: int = position + size
            if end > len(data):
                raise ValueError('Truncated vector tile field')
            else:
                pass
            yield number, wire, data[position:end]
            position = end


def packed_integers(data: memoryview) -> list[int]:
    """
    Read packed uint32 tags or geometry commands with overflow validation.

    :param data: Packed protobuf integer payload.
    :return: Unsigned integers in their original order.
    """
    result: list[int] = list()
    position: int = 0
    while position < len(data):
        value: int
        value, position = read_varint(data, position)
        if value > 4294967295:
            raise ValueError('Vector tile packed value exceeds uint32')
        else:
            result.append(value)
    return result


def decode_value(data: memoryview) -> str | int | float | bool:
    """
    Decode one MVT property value, including signed integers and IEEE floats.

    :param data: Protobuf Value message.
    :return: Property value in its Python scalar representation.
    """
    result: str | int | float | bool | None = None
    number: int
    wire: int
    value: int | memoryview
    for number, wire, value in message_fields(data):
        if number == 1 and wire == 2 and isinstance(value, memoryview):
            result = bytes(value).decode('utf-8')
        elif number == 2 and wire == 5 and isinstance(value, memoryview):
            result = struct.unpack('<f', value)[0]
        elif number == 3 and wire == 1 and isinstance(value, memoryview):
            result = struct.unpack('<d', value)[0]
        elif number in (4, 5, 6, 7) and wire == 0 and isinstance(value, int):
            if number == 4:
                result = value - (1 << 64) if value >= (1 << 63) else value
            elif number == 6:
                result = (value >> 1) ^ -(value & 1)
            elif number == 7:
                result = bool(value)
            else:
                result = value
        else:
            pass
    # Consume the entire value message, so a valid prefix cannot hide truncation.
    if result is None:
        raise ValueError('Vector tile property has no supported value')
    else:
        return result


def decode_geometry(commands: list[int], kind: GeometryKind) -> dict[str, Any]:
    """
    Assemble top-down GeoJSON geometry from MVT drawing commands.

    :param commands: Packed MoveTo, LineTo and ClosePath commands with deltas.
    :param kind: Point, line or polygon geometry kind.
    :return: Geometry with the tile's native integer coordinates.
    """
    position: int = 0
    x: int = 0
    y: int = 0
    coordinates: list[list[int]] = list()
    parts: list[list[list[int]]] = list()
    while position < len(commands):
        command: GeometryCommand = GeometryCommand(commands[position] & 7)
        count: int = commands[position] >> 3
        position += 1
        if count == 0:
            raise ValueError('Empty vector tile geometry command')
        else:
            pass
        if command == GeometryCommand.ClosePath:
            if kind != GeometryKind.Polygon or count != 1 or not coordinates:
                raise ValueError('Invalid vector tile ClosePath command')
            else:
                pass
            if coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])
            else:
                pass
            parts.append(coordinates)
            coordinates = list()
        else:
            if position + count * 2 > len(commands):
                raise ValueError('Truncated vector tile geometry coordinates')
            elif command == GeometryCommand.LineTo and (kind == GeometryKind.Point or not coordinates):
                raise ValueError('Vector tile LineTo requires an active line or ring')
            else:
                pass
            if command == GeometryCommand.MoveTo and kind != GeometryKind.Point:
                if count != 1:
                    raise ValueError('Vector tile line or ring requires one MoveTo coordinate')
                elif coordinates:
                    if kind == GeometryKind.Polygon and coordinates[0] != coordinates[-1]:
                        coordinates.append(coordinates[0])
                    else:
                        pass
                    parts.append(coordinates)
                    coordinates = list()
                else:
                    pass
            else:
                pass
            index: int
            for index in range(count):
                delta_x: int = commands[position]
                delta_y: int = commands[position + 1]
                position += 2
                x += (delta_x >> 1) ^ -(delta_x & 1)
                y += (delta_y >> 1) ^ -(delta_y & 1)
                coordinates.append(list((x, y)))
    if kind == GeometryKind.Point:
        return dict(type='Point', coordinates=coordinates[0]) if len(coordinates) == 1 else dict(
            type='MultiPoint', coordinates=coordinates)
    else:
        pass
    if coordinates:
        if kind == GeometryKind.Polygon and coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])
        else:
            pass
        parts.append(coordinates)
    else:
        pass
    if kind == GeometryKind.LineString:
        if not parts:
            return dict(type='LineString', coordinates=list())
        else:
            pass
        return dict(type='LineString', coordinates=parts[0]) if len(parts) == 1 else dict(
            type='MultiLineString', coordinates=parts)
    else:
        pass
    # Upstream winding-based assembly associates holes with their exterior ring.
    polygons: list[list[list[list[int]]]] = list()
    polygon: list[list[list[int]]] = list()
    winding: int = 0
    ring: list[list[int]]
    for ring in parts:
        area: int = sum(ring[index][0] * ring[index + 1][1] - ring[index + 1][0] * ring[index][1]
                        for index in range(len(ring) - 1))
        if area != 0:
            sign: int = 1 if area > 0 else -1
            if winding == 0:
                winding = sign
            else:
                pass
            if sign == winding:
                if polygon:
                    polygons.append(polygon)
                else:
                    pass
                polygon = list((ring,))
            else:
                polygon.append(ring)
        else:
            pass
    if polygon:
        polygons.append(polygon)
    else:
        pass
    return dict(type='Polygon', coordinates=polygons[0]) if len(polygons) == 1 else dict(
        type='MultiPolygon', coordinates=polygons)


def decode_feature(data: memoryview, keys: list[str], values: list[Any]) -> dict[str, Any]:
    """
    Decode a feature after the layer's shared property tables are available.

    :param data: Protobuf Feature message.
    :param keys: Layer property names.
    :param values: Layer property values.
    :return: GeoJSON-compatible feature with native top-down tile coordinates.
    """
    identifier: int = 0
    kind: int = 0
    tags: list[int] = list()
    commands: list[int] = list()
    number: int
    wire: int
    value: int | memoryview
    for number, wire, value in message_fields(data):
        if number == 1 and wire == 0 and isinstance(value, int):
            identifier = value
        elif number == 3 and wire == 0 and isinstance(value, int):
            kind = value
        elif number in (2, 4):
            target: list[int] = tags if number == 2 else commands
            if wire == 2 and isinstance(value, memoryview):
                target.extend(packed_integers(value))
            elif wire == 0 and isinstance(value, int) and value <= 4294967295:
                target.append(value)
            else:
                raise ValueError('Invalid vector tile integer field')
        else:
            pass
    if len(tags) % 2 != 0:
        raise ValueError('Vector tile property tags must be paired')
    else:
        pass
    properties: dict[str, Any] = dict()
    index: int
    for index in range(0, len(tags), 2):
        key: int = tags[index]
        item: int = tags[index + 1]
        if key >= len(keys) or item >= len(values):
            raise ValueError('Vector tile property index is outside its layer table')
        else:
            properties[keys[key]] = values[item]
    return dict(type='Feature', id=identifier, properties=properties,
                geometry=decode_geometry(commands, GeometryKind(kind)))


def decode_layer(data: memoryview) -> tuple[str, dict[str, Any]]:
    """
    Collect layer tables before decoding features, regardless of protobuf field order.

    :param data: Protobuf Layer message.
    :return: Layer name and decoded feature collection.
    """
    name: str = ''
    extent: int = 4096
    version: int = 1
    keys: list[str] = list()
    values: list[Any] = list()
    features: list[memoryview] = list()
    number: int
    wire: int
    value: int | memoryview
    for number, wire, value in message_fields(data):
        if wire == 2 and isinstance(value, memoryview):
            if number == 1:
                name = bytes(value).decode('utf-8')
            elif number == 2:
                features.append(value)
            elif number == 3:
                keys.append(bytes(value).decode('utf-8'))
            elif number == 4:
                values.append(decode_value(value))
            else:
                pass
        elif wire == 0 and isinstance(value, int):
            if number == 5:
                extent = value
            elif number == 15:
                version = value
            else:
                pass
        else:
            pass
    if not name or not 0 < extent <= 4294967295 or version not in (1, 2):
        raise ValueError('Invalid vector tile layer name, extent or version')
    else:
        pass
    return name, dict(type='FeatureCollection', extent=extent, version=version,
                      features=[decode_feature(feature, keys, values) for feature in features])


def decode(payload: bytes) -> dict[str, Any]:
    """
    Decode an MVT v1/v2 tile for the Qt map renderer without external packages.

    :param payload: Uncompressed protobuf tile bytes.
    :return: Layer names mapped to feature collections; coordinates increase downwards.
    """
    layers: dict[str, Any] = dict()
    number: int
    wire: int
    value: int | memoryview
    for number, wire, value in message_fields(memoryview(payload)):
        if number == 3 and wire == 2 and isinstance(value, memoryview):
            name: str
            layer: dict[str, Any]
            name, layer = decode_layer(value)
            if name in layers:
                raise ValueError('Duplicate vector tile layer name')
            else:
                layers[name] = layer
        else:
            pass
    return layers
