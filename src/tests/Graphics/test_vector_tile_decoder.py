"""Fixed upstream references and malformed-input checks for the local MVT reader."""

import struct

import pytest

from VeraGrid.Gui.Diagrams.MapWidget.Tiles.vector_tile_decoder import (
    GeometryKind, decode, decode_geometry, decode_value, message_fields, read_varint,
)


def test_all_geometry_kinds_and_property_values_match_upstream_reference() -> None:
    """Decode an independent fixture produced by tilezen/mapbox-vector-tile 2.2.0."""
    payload: bytes = bytes.fromhex(
        '1ace010a08666978747572657312150813120a000001010202030304041801220309283c'
        '120b0814180122051102040404120c1802220809000212080e0b05'
        '12101802220c0902040a0404090e200a2828'
        '1225180322210900001a0800000807000f0902051a0002020000010f0910121a0800000807000f'
        '1a046e616d651a08706f7369746976651a086e656761746976651a07646563696d616c1a04666c6167'
        '22090a0745737061c3b1612202207b220b20d6ffffffffffffffff01220919000000000000f43f'
        '220238012880207802')
    layer: dict = decode(payload)['fixtures']
    features: list[dict] = layer['features']
    assert layer['extent'] == 4096 and layer['version'] == 2
    assert features[0]['id'] == 19
    assert features[0]['properties'] == dict(name='España', positive=123, negative=-42, decimal=1.25, flag=True)
    assert features[0]['geometry'] == dict(type='Point', coordinates=[20, 30])
    assert features[1]['geometry'] == dict(type='MultiPoint', coordinates=[[1, 2], [3, 4]])
    assert features[2]['geometry'] == dict(type='LineString', coordinates=[[0, 1], [4, 8], [-2, 5]])
    assert features[3]['geometry'] == dict(type='MultiLineString', coordinates=[[[1, 2], [3, 4]], [[10, 20], [30, 40]]])
    assert features[4]['geometry'] == dict(type='MultiPolygon', coordinates=[
        [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]], [[1, 1], [1, 2], [2, 2], [2, 1], [1, 1]]],
        [[[10, 10], [14, 10], [14, 14], [10, 14], [10, 10]]]])


@pytest.mark.parametrize('payload', (b'\x80', b'\x00', b'\x0a\x05abc', b'\x09\x00', b'\x0d\x00', b'\x0b'))
def test_invalid_protobuf_fields_are_rejected(payload: bytes) -> None:
    """
    Reject truncation and unsupported wire encodings at the message boundary.

    :param payload: Malformed protobuf bytes.
    """
    with pytest.raises(ValueError):
        list(message_fields(memoryview(payload)))


def test_varints_are_bounded_to_uint64() -> None:
    """Accept the uint64 maximum and reject overflow or unterminated encodings."""
    assert read_varint(memoryview(b'\xff' * 9 + b'\x01'), 0) == ((1 << 64) - 1, 10)
    with pytest.raises(ValueError):
        read_varint(memoryview(b'\xff' * 10), 0)


@pytest.mark.parametrize('commands,kind', (
    ([1], GeometryKind.Point),
    ([9, 0], GeometryKind.Point),
    ([10, 0, 0], GeometryKind.LineString),
    ([9, 0, 0, 18, 2], GeometryKind.LineString),
    ([15], GeometryKind.Polygon),
    ([9, 0, 0, 23], GeometryKind.Polygon),
))
def test_invalid_geometry_commands_are_rejected(commands: list[int], kind: GeometryKind) -> None:
    """
    Prevent malformed command counts from producing unbounded loops or partial paths.

    :param commands: Malformed geometry command sequence.
    :param kind: Geometry type being decoded.
    """
    with pytest.raises(ValueError):
        decode_geometry(commands, kind)


def test_scalar_wire_values_preserve_signed_and_floating_point_types() -> None:
    """Support the property encodings not all selected by the upstream fixture encoder."""
    assert decode_value(memoryview(b'\x15' + struct.pack('<f', 2.5))) == 2.5
    assert decode_value(memoryview(b'\x19' + struct.pack('<d', -1.25))) == -1.25
    assert decode_value(memoryview(b'\x30\x53')) == -42
    assert decode_value(memoryview(b'\x28\xff\xff\xff\xff\x0f')) == 4294967295
    assert decode_value(memoryview(b'\x38\x00')) is False


def test_property_value_validation_includes_trailing_fields() -> None:
    """A valid scalar prefix must not conceal a truncated protobuf field."""
    with pytest.raises(ValueError, match='Truncated'):
        decode_value(memoryview(b'\x38\x01\x80'))


def test_invalid_property_table_indices_are_rejected() -> None:
    """A feature must not reference nonexistent property keys or values."""
    # One layer named x: feature tags [0, 0], but no key or value table.
    with pytest.raises(ValueError, match='property index'):
        decode(bytes.fromhex('1a110a0178120a120200001801220209007802'))
