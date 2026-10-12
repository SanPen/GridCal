# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import math
from typing import Dict, List, Tuple

import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.Diagrams.graphic_location import GraphicLocation
from VeraGridEngine.Devices.Diagrams.schematic_diagram import SchematicDiagram
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import (BusGraphicType,
                                         DeviceType,
                                         SchematicRouteKind)
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_objects import ElmTerm, IntGrf, IntGrfcon, IntGrfnet


DGS_POSITION_SCALE: float = 5.0
DGS_BUS_WIDTH_SCALE: float = 50.0
DGS_BUS_HEIGHT_SCALE: float = 40.0
DGS_CONNECTIVITY_BUS_SCALE: float = 8.0
DGS_SUBSTATION_WIDTH_SCALE: float = 120.0
DGS_SUBSTATION_HEIGHT_SCALE: float = 90.0
DGS_POLYLINE_MERGE_TOLERANCE: float = 1e-6
DGS_BRANCH_SYMBOL_DEFAULT_SIZE: float = 40.0
DGS_CHILD_Y_STRETCH: float = 1.82
DGS_ARRANGEMENT_MIN_SCALE: float = 0.2
DGS_ARRANGEMENT_MAX_SCALE: float = 2.0


def normalize_dgs_ref_id(raw_value: str | None) -> str:
    """
    Normalize one DGS reference string to its terminal identifier.

    :param raw_value: Raw DGS pointer or identifier.
    :return: Last path token or an empty string.
    """
    if raw_value is None:
        return ""
    else:
        text_value: str = str(raw_value)

    if "\\" in text_value:
        return text_value.split("\\")[-1]
    else:
        return text_value


def transform_dgs_coordinate_pair(x_value: float, y_value: float) -> Tuple[float, float]:
    """
    Convert one PowerFactory diagram coordinate pair to VeraGrid schematic coordinates.

    :param x_value: DGS X coordinate.
    :param y_value: DGS Y coordinate.
    :return: VeraGrid schematic coordinates.
    """
    x_coord: float = float(x_value) * DGS_POSITION_SCALE
    y_coord: float = float(-y_value) * DGS_POSITION_SCALE
    return x_coord, y_coord


def transform_dgs_center_to_top_left(center_x_value: float,
                                     center_y_value: float,
                                     width_value: float,
                                     height_value: float) -> Tuple[float, float]:
    """
    Convert one DGS symbol center into the top-left coordinate used by VeraGrid widgets.

    PowerFactory stores graphic objects by their geometric center, while VeraGrid stores
    node widgets by their top-left point. The conversion must therefore happen after the
    imported size is known.

    :param center_x_value: DGS center X coordinate.
    :param center_y_value: DGS center Y coordinate.
    :param width_value: VeraGrid widget width.
    :param height_value: VeraGrid widget height.
    :return: Top-left VeraGrid position.
    """
    center_x: float
    center_y: float
    center_x, center_y = transform_dgs_coordinate_pair(center_x_value, center_y_value)
    return center_x - width_value * 0.5, center_y - height_value * 0.5


def stretch_child_diagram_position(x_value: float, y_value: float) -> Tuple[float, float]:
    """
    Stretch child-diagram coordinates vertically to reduce substation overlap.

    :param x_value: Scene X coordinate.
    :param y_value: Scene Y coordinate.
    :return: Stretched scene coordinates.
    """
    return float(x_value), float(y_value) * DGS_CHILD_Y_STRETCH


def stretch_child_route_points(route_points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Stretch child-diagram route points vertically.

    :param route_points: Route points.
    :return: Stretched route points.
    """
    stretched_points: List[Tuple[float, float]] = list()
    point: Tuple[float, float]

    for point in route_points:
        stretched_points.append(stretch_child_diagram_position(point[0], point[1]))

    return stretched_points


def build_location_bounds(location: GraphicLocation) -> Tuple[float, float, float, float]:
    """
    Return the axis-aligned bounds of one imported diagram location.

    :param location: Diagram location.
    :return: Left, top, right and bottom coordinates.
    """
    left_value: float = float(location.x)
    top_value: float = float(location.y)
    right_value: float = left_value + float(location.w)
    bottom_value: float = top_value + float(location.h)
    return left_value, top_value, right_value, bottom_value


def is_point_inside_location(point: Tuple[float, float], location: GraphicLocation) -> bool:
    """
    Check whether one route point lies inside one node rectangle.

    :param point: Scene point.
    :param location: Candidate node location.
    :return: ``True`` when the point lies inside the rectangle.
    """
    left_value: float
    top_value: float
    right_value: float
    bottom_value: float
    left_value, top_value, right_value, bottom_value = build_location_bounds(location=location)
    point_x: float = float(point[0])
    point_y: float = float(point[1])

    if left_value <= point_x <= right_value and top_value <= point_y <= bottom_value:
        return True
    else:
        return False


def get_point_to_location_distance(point: Tuple[float, float], location: GraphicLocation) -> float:
    """
    Return the Euclidean distance from one point to one rectangle.

    :param point: Scene point.
    :param location: Rectangle location.
    :return: Euclidean distance to the rectangle boundary or zero inside.
    """
    left_value: float
    top_value: float
    right_value: float
    bottom_value: float
    left_value, top_value, right_value, bottom_value = build_location_bounds(location=location)
    point_x: float = float(point[0])
    point_y: float = float(point[1])

    if point_x < left_value:
        delta_x: float = left_value - point_x
    elif point_x > right_value:
        delta_x = point_x - right_value
    else:
        delta_x = 0.0

    if point_y < top_value:
        delta_y: float = top_value - point_y
    elif point_y > bottom_value:
        delta_y = point_y - bottom_value
    else:
        delta_y = 0.0

    return float((delta_x * delta_x + delta_y * delta_y) ** 0.5)


def orient_route_points_for_owners(route_points: List[Tuple[float, float]],
                                   from_location: GraphicLocation | None,
                                   to_location: GraphicLocation | None) -> List[Tuple[float, float]]:
    """
    Orient one imported route so its endpoints match the from/to owners.

    Some DGS graphical routes are exported in the opposite direction of the electrical
    ``bus_from``/``bus_to`` relation. Using them verbatim pushes anchors to the wrong side
    of the bus bars. This helper compares both possible orientations and keeps the better one.

    :param route_points: Imported route points.
    :param from_location: From-owner location.
    :param to_location: To-owner location.
    :return: Properly oriented route points.
    """
    if len(route_points) < 2:
        return list(route_points)
    elif from_location is None or to_location is None:
        return list(route_points)
    else:
        first_point: Tuple[float, float] = route_points[0]
        last_point: Tuple[float, float] = route_points[-1]
        direct_score: float = (get_point_to_location_distance(first_point, from_location) +
                               get_point_to_location_distance(last_point, to_location))
        reversed_score: float = (get_point_to_location_distance(first_point, to_location) +
                                 get_point_to_location_distance(last_point, from_location))

        if reversed_score + 1e-9 < direct_score:
            return list(reversed(route_points))
        else:
            return list(route_points)


def extend_route_points_to_owner_locations(route_points: List[Tuple[float, float]],
                                           from_location: GraphicLocation | None,
                                           to_location: GraphicLocation | None) -> List[Tuple[float, float]]:
    """Extend a source route to endpoint owners omitted by a reduced DGS view.

    PowerFactory regional diagrams may terminate an external branch at the
    displayed busbar even though its electrical cubicle belongs to an omitted
    internal connectivity node.  Once the detailed substation arrangement has
    been expanded into the VeraGrid diagram, this helper adds the short lead
    needed to reach the real endpoint owner.

    :param route_points: Imported and endpoint-oriented route.
    :param from_location: From-owner location, when visible.
    :param to_location: To-owner location, when visible.
    :return: Route whose first and last points reach their real owners.
    """
    extended_points: List[Tuple[float, float]] = list(route_points)

    if len(extended_points) == 0:
        return extended_points

    if from_location is not None and not is_point_inside_location(extended_points[0], from_location):
        from_center: Tuple[float, float] = get_location_center(from_location)
        append_points: List[Tuple[float, float]] = [from_center]
        first_point: Tuple[float, float] = extended_points[0]
        if abs(from_center[0] - first_point[0]) > 1e-9 and abs(from_center[1] - first_point[1]) > 1e-9:
            append_points.append((first_point[0], from_center[1]))
        append_points.extend(extended_points)
        extended_points = append_points

    if to_location is not None and not is_point_inside_location(extended_points[-1], to_location):
        to_center: Tuple[float, float] = get_location_center(to_location)
        last_point: Tuple[float, float] = extended_points[-1]
        if abs(to_center[0] - last_point[0]) > 1e-9 and abs(to_center[1] - last_point[1]) > 1e-9:
            extended_points.append((last_point[0], to_center[1]))
        extended_points.append(to_center)

    return extended_points


def append_route_point_if_new(points: List[Tuple[float, float]], point: Tuple[float, float]) -> None:
    """
    Append one route point when it differs from the previous one.

    :param points: Mutable route point list.
    :param point: Candidate point.
    :return: ``None``.
    """
    if len(points) == 0:
        points.append(point)
    elif are_dgs_points_close(points[-1], point):
        point = point
    else:
        points.append(point)


def are_route_points_equal(point_a: Tuple[float, float], point_b: Tuple[float, float]) -> bool:
    """
    Compare two route points with a small tolerance.

    :param point_a: First point.
    :param point_b: Second point.
    :return: ``True`` when both coordinates match within tolerance.
    """
    return abs(float(point_a[0]) - float(point_b[0])) <= 1e-9 and abs(float(point_a[1]) - float(point_b[1])) <= 1e-9


def orthogonalize_route_points(route_points: List[Tuple[float, float]],
                               protected_points: List[Tuple[float, float]] | None = None) -> List[Tuple[float, float]]:
    """
    Replace diagonal segments by Manhattan elbows.

    The substation one-line graphics in PowerFactory are effectively orthogonal. Even
    when the imported polyline contains diagonal shortcuts, VeraGrid should render the
    corridor with 90-degree elbows for readability and to avoid visual collisions.

    :param route_points: Imported route points.
    :param protected_points: Optional points that must survive route simplification.
    :return: Orthogonalized route.
    """
    if len(route_points) < 2:
        return list(route_points)
    else:
        orthogonal_points: List[Tuple[float, float]] = list()
        point_index: int = 0

    append_route_point_if_new(orthogonal_points, route_points[0])

    while point_index < len(route_points) - 1:
        point_a: Tuple[float, float] = route_points[point_index]
        point_b: Tuple[float, float] = route_points[point_index + 1]
        delta_x: float = float(point_b[0]) - float(point_a[0])
        delta_y: float = float(point_b[1]) - float(point_a[1])

        if abs(delta_x) <= 1e-9 or abs(delta_y) <= 1e-9:
            append_route_point_if_new(orthogonal_points, point_b)
        else:
            elbow_point: Tuple[float, float] = (float(point_b[0]), float(point_a[1]))
            append_route_point_if_new(orthogonal_points, elbow_point)
            append_route_point_if_new(orthogonal_points, point_b)

        point_index += 1

    return simplify_collinear_route_points(route_points=orthogonal_points, protected_points=protected_points)


def simplify_collinear_route_points(route_points: List[Tuple[float, float]],
                                    protected_points: List[Tuple[float, float]] | None = None) -> List[Tuple[float, float]]:
    """
    Remove redundant collinear points from one already orthogonal route.

    :param route_points: Candidate route points.
    :param protected_points: Optional route points that must not be removed.
    :return: Simplified route points.
    """
    simplified_points: List[Tuple[float, float]] = list(route_points)
    protected_route_points: List[Tuple[float, float]] = list() if protected_points is None else list(protected_points)
    changed_any_point: bool = True

    while changed_any_point:
        changed_any_point = False
        point_index: int = 1

        while point_index < len(simplified_points) - 1:
            previous_point: Tuple[float, float] = simplified_points[point_index - 1]
            current_point: Tuple[float, float] = simplified_points[point_index]
            next_point: Tuple[float, float] = simplified_points[point_index + 1]

            keep_current_point: bool = False
            protected_point: Tuple[float, float]

            for protected_point in protected_route_points:
                if are_route_points_equal(current_point, protected_point):
                    keep_current_point = True
                else:
                    protected_point = protected_point

            if keep_current_point:
                point_index += 1
            elif abs(float(previous_point[0]) - float(current_point[0])) <= 1e-9 and abs(float(current_point[0]) - float(next_point[0])) <= 1e-9:
                simplified_points.pop(point_index)
                changed_any_point = True
            elif abs(float(previous_point[1]) - float(current_point[1])) <= 1e-9 and abs(float(current_point[1]) - float(next_point[1])) <= 1e-9:
                simplified_points.pop(point_index)
                changed_any_point = True
            else:
                point_index += 1

    return simplified_points


def snap_nearly_orthogonal_route_points(route_points: List[Tuple[float, float]],
                                        tolerance: float = 2.0) -> List[Tuple[float, float]]:
    """
    Snap almost-horizontal and almost-vertical segments to exact orthogonal coordinates.

    Small numerical offsets introduced by trimming imported routes against rectangle
    boundaries can leave 1-pixel diagonal segments. Those are visually obvious in the
    substation one-line even though they are only numerical noise.

    :param route_points: Candidate route points.
    :param tolerance: Maximum deviation considered numerical noise.
    :return: Snapped route points.
    """
    if len(route_points) < 2:
        return list(route_points)
    else:
        snapped_points: List[Tuple[float, float]] = list()
        point_index: int = 0

    snapped_points.append((float(route_points[0][0]), float(route_points[0][1])))

    while point_index < len(route_points) - 1:
        previous_point: Tuple[float, float] = snapped_points[-1]
        next_point: Tuple[float, float] = route_points[point_index + 1]
        delta_x: float = float(next_point[0]) - float(previous_point[0])
        delta_y: float = float(next_point[1]) - float(previous_point[1])

        if abs(delta_x) <= tolerance:
            snapped_points.append((float(previous_point[0]), float(next_point[1])))
        elif abs(delta_y) <= tolerance:
            snapped_points.append((float(next_point[0]), float(previous_point[1])))
        else:
            snapped_points.append((float(next_point[0]), float(next_point[1])))

        point_index += 1

    return snapped_points


def get_segment_rectangle_exit_point(inside_point: Tuple[float, float],
                                     outside_point: Tuple[float, float],
                                     location: GraphicLocation) -> Tuple[float, float]:
    """
    Compute the first intersection between one inside-to-outside segment and one rectangle.

    :param inside_point: Segment point known to lie inside the rectangle.
    :param outside_point: Segment point known to lie outside the rectangle.
    :param location: Rectangle location.
    :return: Exit point on the rectangle boundary.
    """
    left_value: float
    top_value: float
    right_value: float
    bottom_value: float
    left_value, top_value, right_value, bottom_value = build_location_bounds(location=location)
    x0: float = float(inside_point[0])
    y0: float = float(inside_point[1])
    x1: float = float(outside_point[0])
    y1: float = float(outside_point[1])
    candidates: List[Tuple[float, float, float]] = list()
    dx_value: float = x1 - x0
    dy_value: float = y1 - y0
    t_value: float
    y_value: float
    x_value: float

    if abs(dx_value) > 1e-12:
        t_value = (left_value - x0) / dx_value
        y_value = y0 + t_value * dy_value

        if 0.0 <= t_value <= 1.0 and top_value <= y_value <= bottom_value:
            candidates.append((t_value, left_value, y_value))
        else:
            t_value = t_value

        t_value = (right_value - x0) / dx_value
        y_value = y0 + t_value * dy_value

        if 0.0 <= t_value <= 1.0 and top_value <= y_value <= bottom_value:
            candidates.append((t_value, right_value, y_value))
        else:
            t_value = t_value
    else:
        dx_value = dx_value

    if abs(dy_value) > 1e-12:
        t_value = (top_value - y0) / dy_value
        x_value = x0 + t_value * dx_value

        if 0.0 <= t_value <= 1.0 and left_value <= x_value <= right_value:
            candidates.append((t_value, x_value, top_value))
        else:
            t_value = t_value

        t_value = (bottom_value - y0) / dy_value
        x_value = x0 + t_value * dx_value

        if 0.0 <= t_value <= 1.0 and left_value <= x_value <= right_value:
            candidates.append((t_value, x_value, bottom_value))
        else:
            t_value = t_value
    else:
        dy_value = dy_value

    candidates.sort(key=get_exit_point_sort_key)

    if len(candidates) == 0:
        return inside_point
    else:
        return candidates[0][1], candidates[0][2]


def get_exit_point_sort_key(entry: Tuple[float, float, float]) -> float:
    """
    Return the segment parameter used to select the first rectangle exit point.

    :param entry: Candidate intersection triple.
    :return: Segment parameter.
    """
    return float(entry[0])


def trim_route_points_against_location_start(route_points: List[Tuple[float, float]],
                                             location: GraphicLocation) -> Tuple[List[Tuple[float, float]], Tuple[float, float]]:
    """
    Remove the leading polyline portion that lies inside one owner rectangle.

    :param route_points: Imported route points.
    :param location: Owner rectangle.
    :return: Trimmed route and boundary anchor.
    """
    if len(route_points) == 0:
        return list(), (0.0, 0.0)
    else:
        pass

    inside_indexes: List[int] = list()
    point_index: int = 0

    while point_index < len(route_points):
        if is_point_inside_location(route_points[point_index], location=location):
            inside_indexes.append(point_index)
            point_index += 1
        else:
            break

    if len(inside_indexes) == 0:
        return list(route_points), route_points[0]
    elif len(route_points) == len(inside_indexes):
        return list(route_points), route_points[0]
    else:
        last_inside_index: int = inside_indexes[-1]
        first_outside_index: int = last_inside_index + 1
        boundary_point: Tuple[float, float] = get_segment_rectangle_exit_point(route_points[last_inside_index],
                                                                               route_points[first_outside_index],
                                                                               location=location)
        trimmed_points: List[Tuple[float, float]] = [boundary_point]
        trimmed_points.extend(route_points[first_outside_index:])
        return trimmed_points, boundary_point


def trim_route_points_against_location_end(route_points: List[Tuple[float, float]],
                                           location: GraphicLocation) -> Tuple[List[Tuple[float, float]], Tuple[float, float]]:
    """
    Remove the trailing polyline portion that lies inside one owner rectangle.

    :param route_points: Imported route points.
    :param location: Owner rectangle.
    :return: Trimmed route and boundary anchor.
    """
    reversed_points: List[Tuple[float, float]] = list(reversed(route_points))
    trimmed_reversed_points: List[Tuple[float, float]]
    boundary_point: Tuple[float, float]
    trimmed_reversed_points, boundary_point = trim_route_points_against_location_start(route_points=reversed_points,
                                                                                        location=location)
    return list(reversed(trimmed_reversed_points)), boundary_point


def build_local_attachment_from_scene_point(location: GraphicLocation,
                                            scene_point: Tuple[float, float]) -> Dict[str, object]:
    """
    Convert one scene anchor point into the persisted local attachment payload.

    :param location: Owner location.
    :param scene_point: Scene anchor point.
    :return: Persisted attachment payload.
    """
    attachment: Dict[str, object] = dict()
    attachment["anchor_x"] = float(scene_point[0]) - float(location.x)
    attachment["anchor_y"] = float(scene_point[1]) - float(location.y)
    attachment["anchor_auto"] = False
    return attachment


def is_two_terminal_schematic_branch(branch: ALL_DEV_TYPES) -> bool:
    """
    Return whether a device implements the two-terminal route contract.

    Multi-terminal devices such as :class:`Transformer3W` may own DGS graphic
    records, but their endpoints are not exposed through ``bus_from`` and
    ``bus_to``.  Keeping the supported classes explicit prevents the schematic
    importer from confusing those devices with ordinary two-terminal branches.

    :param branch: Candidate API device.
    :return: ``True`` only for devices with two-terminal schematic endpoints.
    """
    if isinstance(branch,
                  (dev.Line,
                   dev.DcLine,
                   dev.Transformer2W,
                   dev.HvdcLine,
                   dev.VSC,
                   dev.UPFC,
                   dev.Winding,
                   dev.Switch,
                   dev.SeriesReactance)):
        return True
    else:
        return False


def resolve_branch_owner_devices_for_diagram(branch: ALL_DEV_TYPES,
                                             diagram: SchematicDiagram) -> Tuple[ALL_DEV_TYPES | None, ALL_DEV_TYPES | None]:
    """
    Resolve the visible endpoint owners used by one diagram for one branch.

    Child diagrams own the physical buses directly. The reduced root diagram owns
    the parent substations instead, so the owner resolution must follow the actually
    visible object stored in the diagram.

    :param branch: Branch API object.
    :param diagram: Target diagram.
    :return: Visible owner devices for the from and to endpoints.
    """
    from_owner: ALL_DEV_TYPES | None = None
    to_owner: ALL_DEV_TYPES | None = None

    # The route algorithm only applies to explicit two-terminal devices.  A
    # three-winding transformer is rendered by its dedicated representation.
    if not is_two_terminal_schematic_branch(branch=branch):
        return None, None
    else:
        pass

    if diagram.query_point(branch.bus_from) is None:
        if branch.bus_from is None or branch.bus_from.substation is None:
            from_owner = None
        else:
            from_owner = branch.bus_from.substation
    else:
        from_owner = branch.bus_from

    if diagram.query_point(branch.bus_to) is None:
        if branch.bus_to is None or branch.bus_to.substation is None:
            to_owner = None
        else:
            to_owner = branch.bus_to.substation
    else:
        to_owner = branch.bus_to

    return from_owner, to_owner


def set_imported_branch_route_and_attachments(diagram: SchematicDiagram,
                                              branch: ALL_DEV_TYPES,
                                              route_points: List[Tuple[float, float]],
                                              graphic: IntGrf | None = None,
                                              enforce_orthogonal: bool = False,
                                              branch_location_override: GraphicLocation | None = None) -> None:
    """
    Persist one imported branch route together with endpoint boundary anchors.

    :param diagram: Target diagram.
    :param branch: Imported branch object.
    :param route_points: Imported route points.
    :param graphic: Optional DGS graphical object for inline symbol geometry.
    :param enforce_orthogonal: Whether imported diagonal segments must be converted to Manhattan routes.
    :param branch_location_override: Optional already-transformed inline-symbol location.
    :return: ``None``.
    """
    if len(route_points) < 2:
        return
    elif not is_two_terminal_schematic_branch(branch=branch):
        # Multi-terminal graphics do not define a single from/to route.
        return
    else:
        pass

    from_owner: ALL_DEV_TYPES | None
    to_owner: ALL_DEV_TYPES | None
    from_owner, to_owner = resolve_branch_owner_devices_for_diagram(branch=branch, diagram=diagram)
    trimmed_points: List[Tuple[float, float]] = list(route_points)

    if branch_location_override is not None:
        branch_location = branch_location_override
        protected_points = [get_location_center(branch_location)]
    elif graphic is None or not should_store_branch_symbol_geometry(branch):
        branch_location = GraphicLocation(api_object=branch)
        protected_points: List[Tuple[float, float]] = list()
    else:
        symbol_width: float
        symbol_height: float
        symbol_width, symbol_height = get_branch_symbol_size(api_object=branch, graphic=graphic)
        symbol_x: float
        symbol_y: float
        symbol_x, symbol_y = transform_dgs_center_to_top_left(graphic.rCenterX,
                                                              graphic.rCenterY,
                                                              symbol_width,
                                                              symbol_height)
        if enforce_orthogonal:
            symbol_x, symbol_y = stretch_child_diagram_position(symbol_x, symbol_y)
        else:
            symbol_x = symbol_x
        branch_location = GraphicLocation(api_object=branch,
                                          x=symbol_x,
                                          y=symbol_y,
                                          w=symbol_width,
                                          h=symbol_height,
                                          r=float(graphic.iRot))
        protected_points = [get_location_center(branch_location)]

    # The branch placeholder must exist before persisting attachments and route metadata,
    # otherwise a later ``set_point()`` call would replace the temporary location and drop
    # the imported structured payload.
    diagram.set_point(device=branch,
                      location=branch_location)

    from_location: GraphicLocation | None = None
    to_location: GraphicLocation | None = None

    if from_owner is None:
        from_owner = from_owner
    else:
        from_location = diagram.query_point(from_owner)

    if to_owner is None:
        to_owner = to_owner
    else:
        to_location = diagram.query_point(to_owner)

    if should_use_imported_branch_route(branch):
        trimmed_points = orient_route_points_for_owners(route_points=trimmed_points,
                                                        from_location=from_location,
                                                        to_location=to_location)
        trimmed_points = extend_route_points_to_owner_locations(route_points=trimmed_points,
                                                                from_location=from_location,
                                                                to_location=to_location)
    elif graphic is None:
        trimmed_points = trimmed_points
    else:
        trimmed_points = build_symbol_axis_route_points(branch_location=branch_location,
                                                        from_location=from_location,
                                                        to_location=to_location)

    if enforce_orthogonal:
        trimmed_points = orthogonalize_route_points(route_points=trimmed_points,
                                                    protected_points=protected_points)
    else:
        trimmed_points = trimmed_points

    if from_owner is None:
        from_owner = from_owner
    else:
        if from_location is None:
            from_location = from_location
        else:
            trimmed_points, from_anchor_point = trim_route_points_against_location_start(route_points=trimmed_points,
                                                                                         location=from_location)
            diagram.set_attachment(api_object=branch,
                                   endpoint="from",
                                   attachment=build_local_attachment_from_scene_point(location=from_location,
                                                                                      scene_point=from_anchor_point))

    if enforce_orthogonal:
        trimmed_points = orthogonalize_route_points(route_points=trimmed_points,
                                                    protected_points=protected_points)
    else:
        trimmed_points = trimmed_points

    if to_owner is None:
        to_owner = to_owner
    else:
        if to_location is None:
            to_location = to_location
        else:
            trimmed_points, to_anchor_point = trim_route_points_against_location_end(route_points=trimmed_points,
                                                                                     location=to_location)
            diagram.set_attachment(api_object=branch,
                                   endpoint="to",
                                   attachment=build_local_attachment_from_scene_point(location=to_location,
                                                                                      scene_point=to_anchor_point))

    if enforce_orthogonal:
        trimmed_points = orthogonalize_route_points(route_points=trimmed_points,
                                                    protected_points=protected_points)
        trimmed_points = snap_nearly_orthogonal_route_points(route_points=trimmed_points)
        trimmed_points = simplify_collinear_route_points(route_points=trimmed_points,
                                                         protected_points=protected_points)
        diagram.set_branch_route_points(api_object=branch,
                                        points=trimmed_points,
                                        kind=SchematicRouteKind.MANUAL_ORTHOGONAL,
                                        locked=True)
    else:
        trimmed_points = simplify_collinear_route_points(route_points=trimmed_points,
                                                         protected_points=protected_points)
        diagram.set_branch_route_points(api_object=branch,
                                        points=trimmed_points,
                                        kind=SchematicRouteKind.MANUAL_POLYLINE,
                                        locked=True)


def get_bus_graphic_type_from_dgs_terminal(elmterm: ElmTerm) -> BusGraphicType:
    """
    Map one PowerFactory terminal usage code to the VeraGrid bus graphic type.

    :param elmterm: DGS terminal object.
    :return: Preferred VeraGrid graphic type.
    """
    usage_code: int = int(elmterm.iUsage)

    if usage_code == 0:
        return BusGraphicType.BusBar
    elif usage_code == 1:
        return BusGraphicType.Connectivity
    elif usage_code == 2:
        return BusGraphicType.Connectivity
    else:
        return BusGraphicType.BusBar


def build_preferred_position_by_object_id(dgs_grid: DgsCircuit) -> Dict[str, Tuple[float, float]]:
    """
    Build one stable global position map for object import.

    The same electrical object can appear in several PowerFactory diagrams. This
    helper prefers the root diagram references first and only then falls back to the
    first remaining occurrence so the import stays deterministic.

    :param dgs_grid: Parsed DGS circuit.
    :return: Stable object-position mapping.
    """
    positions_by_object_id: Dict[str, Tuple[float, float]] = dict()
    static_diagram_ids: set[str] = build_static_diagram_ids(dgs_grid=dgs_grid)
    graphics_by_diagram_id: Dict[str, List[IntGrf]] = build_graphics_by_diagram_id(dgs_grid=dgs_grid)
    preferred_root_diagram_ids: List[str] = list()
    elmnet: object
    graphic: IntGrf

    for elmnet in dgs_grid.elmnets:
        root_diagram_id: str = normalize_dgs_ref_id(elmnet.pDiagram)
        if root_diagram_id != "":
            preferred_root_diagram_ids.append(root_diagram_id)
        else:
            root_diagram_id = root_diagram_id

    ordered_diagram_ids: List[str] = list()
    for diagram_id in preferred_root_diagram_ids:
        if diagram_id in static_diagram_ids and diagram_id not in ordered_diagram_ids:
            ordered_diagram_ids.append(diagram_id)
    for diagram_id in sorted(static_diagram_ids):
        if diagram_id not in ordered_diagram_ids:
            ordered_diagram_ids.append(diagram_id)

    for diagram_id in ordered_diagram_ids:
        for graphic in graphics_by_diagram_id.get(diagram_id, list()):
            object_id: str = normalize_dgs_ref_id(graphic.pDataObj)
            if object_id != "" and object_id not in positions_by_object_id:
                positions_by_object_id[object_id] = (float(graphic.rCenterX), float(graphic.rCenterY))

    return positions_by_object_id


def extract_dgs_connection_points(connection: IntGrfcon) -> List[Tuple[float, float]]:
    """
    Decode one exported PowerFactory graphical-connection polyline.

    :param connection: DGS graphical connection row.
    :return: Ordered polyline points.
    """
    if len(connection.points) > 0:
        return list(connection.points)
    elif len(connection.rX) > 0 and len(connection.rY) > 0:
        point_count: int = min(len(connection.rX), len(connection.rY))
        return list(zip(connection.rX[:point_count], connection.rY[:point_count]))
    else:
        pass

    # Compatibility with programmatically constructed rows and older cached
    # objects which predate the variable-length vector representation.
    x_values: List[float] = [
        float(connection.rX_0),
        float(connection.rX_1),
        float(connection.rX_2),
        float(connection.rX_3),
        float(connection.rX_4),
        float(connection.rX_5),
        float(connection.rX_6),
        float(connection.rX_7),
        float(connection.rX_8),
        float(connection.rX_9),
    ]
    y_values: List[float] = [
        float(connection.rY_0),
        float(connection.rY_1),
        float(connection.rY_2),
        float(connection.rY_3),
        float(connection.rY_4),
        float(connection.rY_5),
        float(connection.rY_6),
        float(connection.rY_7),
        float(connection.rY_8),
        float(connection.rY_9),
    ]
    point_count_x: int = min(int(connection.rX_SIZEROW), len(x_values))
    point_count_y: int = min(int(connection.rY_SIZEROW), len(y_values))
    point_count: int = min(point_count_x, point_count_y)
    points: List[Tuple[float, float]] = list()
    point_index: int = 0

    while point_index < point_count:
        points.append((x_values[point_index], y_values[point_index]))
        point_index += 1

    return points


def are_dgs_points_close(point_a: Tuple[float, float], point_b: Tuple[float, float]) -> bool:
    """
    Check whether two DGS polyline points coincide within merge tolerance.

    :param point_a: First point.
    :param point_b: Second point.
    :return: ``True`` when the points are effectively identical.
    """
    delta_x: float = abs(float(point_a[0]) - float(point_b[0]))
    delta_y: float = abs(float(point_a[1]) - float(point_b[1]))

    if delta_x <= DGS_POLYLINE_MERGE_TOLERANCE and delta_y <= DGS_POLYLINE_MERGE_TOLERANCE:
        return True
    else:
        return False


def merge_dgs_connection_polylines(polyline_a: List[Tuple[float, float]],
                                   polyline_b: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Merge the two half-polylines exported around one branch symbol.

    :param polyline_a: First side polyline.
    :param polyline_b: Second side polyline.
    :return: One complete route.
    """
    if len(polyline_a) == 0:
        return list(polyline_b)
    else:
        pass

    if len(polyline_b) == 0:
        return list(polyline_a)
    else:
        pass

    first_a: Tuple[float, float] = polyline_a[0]
    last_a: Tuple[float, float] = polyline_a[-1]
    first_b: Tuple[float, float] = polyline_b[0]
    last_b: Tuple[float, float] = polyline_b[-1]
    merged: List[Tuple[float, float]] = list()

    if are_dgs_points_close(first_a, first_b):
        merged = list(reversed(polyline_a))
        merged.extend(polyline_b[1:])
    elif are_dgs_points_close(last_a, last_b):
        merged = list(polyline_a)
        reversed_tail: List[Tuple[float, float]] = list(reversed(polyline_b))
        merged.extend(reversed_tail[1:])
    elif are_dgs_points_close(last_a, first_b):
        merged = list(polyline_a)
        merged.extend(polyline_b[1:])
    elif are_dgs_points_close(first_a, last_b):
        merged = list(polyline_b)
        merged.extend(polyline_a[1:])
    else:
        merged = list(polyline_a)
        merged.extend(polyline_b)

    return merged


def build_connections_by_graphic_id(dgs_grid: DgsCircuit) -> Dict[str, List[IntGrfcon]]:
    """
    Group graphical connection rows by their owning graphical object.

    :param dgs_grid: Parsed DGS circuit.
    :return: Graphical connections indexed by graphical object id.
    """
    connections_by_graphic_id: Dict[str, List[IntGrfcon]] = dict()
    connection: IntGrfcon

    for connection in dgs_grid.intgrfcons:
        graphic_id: str = normalize_dgs_ref_id(connection.fold_id)
        existing_connections: List[IntGrfcon] | None = connections_by_graphic_id.get(graphic_id, None)

        if graphic_id == "":
            graphic_id = graphic_id
        elif existing_connections is None:
            connections_by_graphic_id[graphic_id] = [connection]
        else:
            existing_connections.append(connection)

    return connections_by_graphic_id


def build_graphics_by_diagram_id(dgs_grid: DgsCircuit) -> Dict[str, List[IntGrf]]:
    """
    Group graphical rows by their parent schematic identifier.

    :param dgs_grid: Parsed DGS circuit.
    :return: Graphical rows indexed by diagram id.
    """
    graphics_by_diagram_id: Dict[str, List[IntGrf]] = dict()
    diagram_ids: set[str] = {
        normalize_dgs_ref_id(diagram.ID)
        for diagram in dgs_grid.intgrfnets
        if normalize_dgs_ref_id(diagram.ID) != ""
    }
    parent_by_id: Dict[str, str] = dict()

    for graphic in dgs_grid.intgrfs:
        parent_by_id[normalize_dgs_ref_id(graphic.ID)] = normalize_dgs_ref_id(graphic.fold_id)
    for folder in dgs_grid.intfolders:
        parent_by_id[normalize_dgs_ref_id(folder.ID)] = normalize_dgs_ref_id(folder.fold_id)
    for group in dgs_grid.intgrfgroups:
        parent_by_id[normalize_dgs_ref_id(group.ID)] = normalize_dgs_ref_id(group.fold_id)

    for graphic in dgs_grid.intgrfs:
        object_id: str = normalize_dgs_ref_id(graphic.pDataObj)
        candidate_id: str = normalize_dgs_ref_id(graphic.fold_id)
        visited_ids: set[str] = set()

        while candidate_id != "" and candidate_id not in diagram_ids and candidate_id not in visited_ids:
            visited_ids.add(candidate_id)
            candidate_id = parent_by_id.get(candidate_id, "")

        if object_id == "" or candidate_id not in diagram_ids:
            continue

        graphics_by_diagram_id.setdefault(candidate_id, list()).append(graphic)

    return graphics_by_diagram_id


def resolve_dgs_container_owner_id(
        initial_owner_id: str,
        parent_by_id: Dict[str, str],
) -> str:
    """Resolve the first non-container owner above one DGS object.

    PowerFactory can nest a static diagram below any number of ``IntFolder``
    or ``IntGrfgroup`` rows.  Following those parent links is therefore
    required before deciding whether the diagram belongs to a static network
    object.  A malformed cycle is rejected instead of being classified from a
    partial ancestry chain.

    :param initial_owner_id: Direct ``pDataFolder`` reference of the diagram.
    :param parent_by_id: Container identifier to parent identifier mapping.
    :return: First owner outside the container map, or an empty string for a cycle.
    """
    owner_id: str = normalize_dgs_ref_id(initial_owner_id)
    visited_ids: set[str] = set()

    while owner_id != "" and owner_id in parent_by_id and owner_id not in visited_ids:
        visited_ids.add(owner_id)
        owner_id = parent_by_id.get(owner_id, "")

    if owner_id in visited_ids:
        return ""
    else:
        return owner_id


def build_static_diagram_ids(dgs_grid: DgsCircuit) -> set[str]:
    """Return the strict whitelist of static electrical diagram identifiers.

    Dynamic and free-form diagrams are intentionally never inferred from names
    or ``iType``.  A diagram is drawable only when PowerFactory associates it
    with a static network/site/substation object, either as its data folder or
    through that object's explicit ``pDiagram`` reference.
    """
    static_owner_ids: set[str] = set()
    referenced_diagram_ids: set[str] = set()

    for owner in [*dgs_grid.elmnets, *dgs_grid.elmsites, *dgs_grid.elmsubstats]:
        owner_id: str = normalize_dgs_ref_id(owner.ID)
        if owner_id != "":
            static_owner_ids.add(owner_id)
        diagram_id: str = normalize_dgs_ref_id(getattr(owner, "pDiagram", ""))
        if diagram_id != "":
            referenced_diagram_ids.add(diagram_id)

    dynamic_owner_ids: set[str] = set()
    dynamic_collections: List[list] = [
        dgs_grid.elmcomps,
        dgs_grid.elmdsls,
        dgs_grid.blkdefs,
        dgs_grid.blkdivs,
        dgs_grid.blkfroms,
        dgs_grid.blkgotos,
        dgs_grid.blkmuls,
        dgs_grid.blkrefs,
        dgs_grid.blksigs,
        dgs_grid.blkslots,
        dgs_grid.blksums,
        dgs_grid.blkswts,
    ]
    for collection in dynamic_collections:
        for dynamic_object in collection:
            dynamic_id: str = normalize_dgs_ref_id(dynamic_object.ID)
            if dynamic_id != "":
                dynamic_owner_ids.add(dynamic_id)

    # A static diagram can be nested below several generic folders or graphic
    # groups.  Resolve those containers before comparing the final owner with
    # the network/site/substation whitelist.
    parent_by_id: Dict[str, str] = dict()
    for folder in dgs_grid.intfolders:
        folder_id: str = normalize_dgs_ref_id(folder.ID)
        if folder_id != "":
            parent_by_id[folder_id] = normalize_dgs_ref_id(folder.fold_id)
        else:
            pass
    for group in dgs_grid.intgrfgroups:
        group_id: str = normalize_dgs_ref_id(group.ID)
        if group_id != "":
            parent_by_id[group_id] = normalize_dgs_ref_id(group.fold_id)
        else:
            pass

    # Some exports omit a usable diagram-owner chain.  In that case the
    # presence of a known electrical object is sufficient static evidence,
    # while dynamic roots remain excluded explicitly below.
    static_object_ids: set[str] = set(static_owner_ids)
    static_collections: List[list] = [
        dgs_grid.elmterms,
        dgs_grid.elmasms,
        dgs_grid.elmcoups,
        dgs_grid.elmgenstats,
        dgs_grid.elmvscs,
        dgs_grid.elmvscmonos,
        dgs_grid.elmlnes,
        dgs_grid.elmzpus,
        dgs_grid.elmscaps,
        dgs_grid.elmsinds,
        dgs_grid.elmlods,
        dgs_grid.elmlodlvs,
        dgs_grid.elmlodlvps,
        dgs_grid.elmshnts,
        dgs_grid.elmsvss,
        dgs_grid.elmsyms,
        dgs_grid.elmtr2s,
        dgs_grid.elmtr3s,
        dgs_grid.elmtr4s,
        dgs_grid.elmxnets,
    ]
    for collection in static_collections:
        for static_object in collection:
            static_object_id: str = normalize_dgs_ref_id(static_object.ID)
            if static_object_id != "":
                static_object_ids.add(static_object_id)
            else:
                pass

    graphics_by_diagram_id: Dict[str, List[IntGrf]] = build_graphics_by_diagram_id(
        dgs_grid=dgs_grid,
    )

    static_diagram_ids: set[str] = set()
    for diagram in dgs_grid.intgrfnets:
        diagram_id: str = normalize_dgs_ref_id(diagram.ID)
        direct_owner_id: str = normalize_dgs_ref_id(diagram.pDataFolder)
        owner_id: str = resolve_dgs_container_owner_id(
            initial_owner_id=direct_owner_id,
            parent_by_id=parent_by_id,
        )
        # Type 1 is PowerFactory's graphic/block-diagram domain in the supplied
        # exports. It is excluded even if a future export happens to store that
        # diagram below a static project object.
        if int(diagram.iType) == 1 or owner_id in dynamic_owner_ids:
            pass
        else:
            has_static_graphic: bool = False
            graphic: IntGrf
            for graphic in graphics_by_diagram_id.get(diagram_id, list()):
                graphic_object_id: str = normalize_dgs_ref_id(graphic.pDataObj)
                if graphic_object_id in static_object_ids:
                    has_static_graphic = True
                else:
                    pass

            if (
                    owner_id in static_owner_ids
                    or diagram_id in referenced_diagram_ids
                    or has_static_graphic
            ):
                static_diagram_ids.add(diagram_id)
            else:
                pass

    return static_diagram_ids


def get_root_diagram_score(candidate_id: str,
                           intgrfnet_by_id: Dict[str, IntGrfnet],
                           graphics_by_diagram_id: Dict[str, List[IntGrf]],
                           substation_by_id: Dict[str, dev.Substation]) -> Tuple[int, int, int]:
    """
    Score one candidate root diagram.

    :param candidate_id: Candidate diagram id.
    :param intgrfnet_by_id: Diagram objects indexed by id.
    :param graphics_by_diagram_id: Graphical objects indexed by diagram id.
    :param substation_by_id: Imported substations indexed by DGS id.
    :return: Comparable score tuple.
    """
    graphic_entries: List[IntGrf] = graphics_by_diagram_id.get(candidate_id, list())
    substation_count: int = 0
    graphic: IntGrf

    for graphic in graphic_entries:
        object_id: str = normalize_dgs_ref_id(graphic.pDataObj)
        if substation_by_id.get(object_id, None) is None:
            object_id = object_id
        else:
            substation_count += 1

    intgrfnet_candidate: IntGrfnet | None = intgrfnet_by_id.get(candidate_id, None)
    named_bonus: int = 0

    if intgrfnet_candidate is None:
        named_bonus = 0
    else:
        lower_name: str = str(intgrfnet_candidate.loc_name).strip().lower()
        if lower_name in {"graphic", "diagram", "diagrams"}:
            named_bonus = 0
        else:
            named_bonus = 1

    return substation_count, named_bonus, len(graphic_entries)


def select_preferred_root_diagram_id(dgs_grid: DgsCircuit,
                                     intgrfnet_by_id: Dict[str, IntGrfnet],
                                     graphics_by_diagram_id: Dict[str, List[IntGrf]],
                                     substation_by_id: Dict[str, dev.Substation]) -> str:
    """
    Select the grid-level overview diagram that actually groups the substations.

    :param dgs_grid: Parsed DGS circuit.
    :param intgrfnet_by_id: Diagram objects indexed by id.
    :param graphics_by_diagram_id: Graphical objects indexed by diagram id.
    :param substation_by_id: Imported substations indexed by DGS id.
    :return: Preferred root diagram id or an empty string.
    """
    candidate_ids: List[str] = list()
    elmnet: object
    intgrfnet: IntGrfnet

    for elmnet in dgs_grid.elmnets:
        elmnet_id: str = normalize_dgs_ref_id(elmnet.ID)
        referenced_diagram_id: str = normalize_dgs_ref_id(elmnet.pDiagram)

        if referenced_diagram_id != "":
            candidate_ids.append(referenced_diagram_id)
        else:
            referenced_diagram_id = referenced_diagram_id

        for intgrfnet in dgs_grid.intgrfnets:
            parent_folder_id: str = normalize_dgs_ref_id(intgrfnet.pDataFolder)
            diagram_id: str = normalize_dgs_ref_id(intgrfnet.ID)

            if parent_folder_id == elmnet_id and diagram_id != "":
                candidate_ids.append(diagram_id)
            else:
                parent_folder_id = parent_folder_id

    unique_candidate_ids: List[str] = sorted(set(candidate_ids))
    best_id: str = ""
    best_score: Tuple[int, int, int] = (-1, -1, -1)
    candidate_id: str

    for candidate_id in unique_candidate_ids:
        if candidate_id not in intgrfnet_by_id:
            continue
        current_score: Tuple[int, int, int] = get_root_diagram_score(candidate_id=candidate_id,
                                                                      intgrfnet_by_id=intgrfnet_by_id,
                                                                      graphics_by_diagram_id=graphics_by_diagram_id,
                                                                      substation_by_id=substation_by_id)
        if current_score > best_score:
            best_score = current_score
            best_id = candidate_id
        else:
            pass

    return best_id


def build_dgs_branch_route_points_for_graphic(graphic: IntGrf,
                                              connections_by_graphic_id: Dict[str, List[IntGrfcon]]) -> List[Tuple[float, float]]:
    """
    Build one full VeraGrid branch route from the PowerFactory connector rows.

    :param graphic: Branch graphical object.
    :param connections_by_graphic_id: Graphical connection rows grouped by graphical object id.
    :return: Full route points in VeraGrid coordinates.
    """
    graphic_id: str = normalize_dgs_ref_id(graphic.ID)
    raw_connections: List[IntGrfcon] = connections_by_graphic_id.get(graphic_id, list())
    ordered_connections: List[IntGrfcon] = sorted(
        [connection for connection in raw_connections if len(extract_dgs_connection_points(connection)) > 0],
        key=get_intgrfcon_order_key,
    )
    route_points_dgs: List[Tuple[float, float]] = list()
    transformed_points: List[Tuple[float, float]] = list()
    point: Tuple[float, float]

    if len(ordered_connections) == 0:
        return route_points_dgs
    elif len(ordered_connections) == 1:
        route_points_dgs = extract_dgs_connection_points(ordered_connections[0])
    else:
        left_points: List[Tuple[float, float]] = extract_dgs_connection_points(ordered_connections[0])
        right_points: List[Tuple[float, float]] = extract_dgs_connection_points(ordered_connections[1])
        graphic_center: Tuple[float, float] = (float(graphic.rCenterX), float(graphic.rCenterY))

        def squared_distance(point: Tuple[float, float]) -> float:
            return ((point[0] - graphic_center[0]) ** 2
                    + (point[1] - graphic_center[1]) ** 2)

        # PowerFactory commonly terminates each connector at a different edge
        # of the inline symbol, so exact endpoint equality is not a valid merge
        # requirement. Orient side zero outer-to-inner and side one
        # inner-to-outer, preserving the symbol gap as part of the route.
        if squared_distance(left_points[0]) < squared_distance(left_points[-1]):
            left_points.reverse()
        if squared_distance(right_points[-1]) < squared_distance(right_points[0]):
            right_points.reverse()

        route_points_dgs = list(left_points)
        if are_dgs_points_close(route_points_dgs[-1], right_points[0]):
            route_points_dgs.extend(right_points[1:])
        else:
            route_points_dgs.extend(right_points)

    for point in route_points_dgs:
        transformed_points.append(transform_dgs_coordinate_pair(point[0], point[1]))

    return transformed_points


def get_intgrfcon_order_key(connection: IntGrfcon) -> int:
    """
    Return the deterministic route order of one DGS connector half.

    :param connection: Connector row.
    :return: Side order.
    """
    connector_number: int = int(connection.iDatConNr)
    return connector_number if connector_number >= 0 else 1_000_000


def get_substation_size_from_graphic(graphic: IntGrf) -> Tuple[float, float]:
    """
    Convert one PowerFactory substation rectangle size to a schematic size.

    :param graphic: DGS graphical object for one substation proxy.
    :return: Width and height in schematic pixels.
    """
    width: float = max(float(graphic.rSizeX) * DGS_SUBSTATION_WIDTH_SCALE, 180.0)
    height: float = max(float(graphic.rSizeY) * DGS_SUBSTATION_HEIGHT_SCALE, 90.0)
    return width, height


def get_bus_size_from_graphic(bus: dev.Bus, graphic: IntGrf) -> Tuple[float, float]:
    """
    Convert one PowerFactory terminal symbol size to a VeraGrid bus size.

    :param bus: VeraGrid bus.
    :param graphic: DGS graphical object.
    :return: Width and height in schematic pixels.
    """
    if bus.graphic_type == BusGraphicType.Connectivity:
        width: float = max(float(graphic.rSizeX) * DGS_CONNECTIVITY_BUS_SCALE, DGS_CONNECTIVITY_BUS_SCALE)
        height: float = max(float(graphic.rSizeY) * DGS_CONNECTIVITY_BUS_SCALE, DGS_CONNECTIVITY_BUS_SCALE)
        return width, height
    else:
        width = max(float(graphic.rSizeX) * DGS_BUS_WIDTH_SCALE, 180.0)
        height = max(float(graphic.rSizeY) * DGS_BUS_HEIGHT_SCALE, 40.0)
        return width, height


def should_hide_imported_bus_label(bus: dev.Bus) -> bool:
    """
    Return whether one imported bus label should be hidden by default.

    :param bus: Imported bus.
    :return: ``True`` when the label is auxiliary noise.
    """
    if bus.graphic_type == BusGraphicType.Connectivity and not str(bus.name).startswith("Terminal"):
        return True
    else:
        return False


def should_hide_imported_branch_label(api_object: ALL_DEV_TYPES) -> bool:
    """
    Return whether one imported branch label should be hidden by default.

    :param api_object: Imported branch.
    :return: ``True`` when the label is auxiliary noise.
    """
    if isinstance(api_object, (dev.Switch, dev.Transformer2W, dev.SeriesReactance)):
        return True
    else:
        return False


def get_branch_symbol_size(api_object: ALL_DEV_TYPES,
                           graphic: IntGrf | None = None) -> Tuple[float, float]:
    """
    Return the nominal schematic symbol size used by the current branch widgets.

    :param api_object: Branch API object.
    :param graphic: Optional imported graphical object carrying source dimensions.
    :return: Symbol width and height.
    """
    if graphic is None:
        if isinstance(api_object, dev.Transformer2W):
            return 80.0, 80.0
        elif isinstance(api_object, dev.VSC):
            return 68.0, 68.0
        elif isinstance(api_object, dev.UPFC):
            return 48.0, 48.0
        elif isinstance(api_object, (dev.HvdcLine, dev.SeriesReactance, dev.Switch)):
            return 30.0, 30.0
        else:
            return DGS_BRANCH_SYMBOL_DEFAULT_SIZE, DGS_BRANCH_SYMBOL_DEFAULT_SIZE
    else:
        if isinstance(api_object, dev.Transformer2W):
            # Imported 2W transformers must keep the same visual scale users expect from
            # manually created schematic transformers. A smaller imported symbol makes
            # the branch look detached from the bay and much harder to read.
            scale_value: float = 80.0
            minimum_size: float = 80.0
        elif isinstance(api_object, dev.VSC):
            scale_value = 22.0
            minimum_size = 18.0
        elif isinstance(api_object, dev.UPFC):
            scale_value = 20.0
            minimum_size = 16.0
        elif isinstance(api_object, (dev.HvdcLine, dev.SeriesReactance)):
            scale_value = 18.0
            minimum_size = 14.0
        elif isinstance(api_object, dev.Switch):
            scale_value = 10.5
            minimum_size = 9.0
        else:
            scale_value = 18.0
            minimum_size = 14.0

        width: float = max(float(graphic.rSizeX) * scale_value, minimum_size)
        height: float = max(float(graphic.rSizeY) * scale_value, minimum_size)
        return width, height


def should_store_branch_symbol_geometry(api_object: ALL_DEV_TYPES) -> bool:
    """
    Return whether one branch uses a visible inline symbol in the schematic editor.

    :param api_object: Branch API object.
    :return: ``True`` when the branch has an inline symbol.
    """
    return isinstance(api_object,
                      (dev.Transformer2W,
                       dev.VSC,
                       dev.UPFC,
                       dev.HvdcLine,
                       dev.SeriesReactance,
                       dev.Switch))


def should_use_imported_branch_route(api_object: ALL_DEV_TYPES) -> bool:
    """
    Return whether one branch should keep the imported polyline route.

    Inline substation devices such as switches and short transformer symbols often use
    very local graphical stubs in DGS that do not match the electrical owner buses used
    by VeraGrid. For those devices the imported symbol position is still useful, but the
    route itself should be rebuilt orthogonally from the real endpoints.

    :param api_object: Branch API object.
    :return: ``True`` when the imported route should be preserved.
    """
    if isinstance(api_object, (dev.Switch, dev.Transformer2W, dev.SeriesReactance)):
        return False
    else:
        return True


def get_location_center(location: GraphicLocation) -> Tuple[float, float]:
    """
    Return the rectangle center of one location.

    :param location: Diagram location.
    :return: Center point.
    """
    return float(location.x) + float(location.w) * 0.5, float(location.y) + float(location.h) * 0.5


def build_symbol_axis_route_points(branch_location: GraphicLocation,
                                   from_location: GraphicLocation | None,
                                   to_location: GraphicLocation | None) -> List[Tuple[float, float]]:
    """
    Build one orthogonal route that passes through the imported inline-symbol axis.

    :param branch_location: Imported branch-symbol location.
    :param from_location: From-owner location.
    :param to_location: To-owner location.
    :return: Orthogonal route points.
    """
    if from_location is None or to_location is None:
        return list()
    else:
        start_center_x: float
        start_center_y: float
        end_center_x: float
        end_center_y: float
        start_center_x, start_center_y = get_location_center(from_location)
        end_center_x, end_center_y = get_location_center(to_location)
        symbol_center_x: float
        symbol_center_y: float
        symbol_center_x, symbol_center_y = get_location_center(branch_location)
        route_points: List[Tuple[float, float]] = list()

        route_points.append((start_center_x, start_center_y))

        if abs(start_center_x - symbol_center_x) > 1e-9:
            route_points.append((symbol_center_x, start_center_y))
        else:
            symbol_center_x = symbol_center_x

        route_points.append((symbol_center_x, symbol_center_y))

        if abs(end_center_y - symbol_center_y) > 1e-9:
            route_points.append((symbol_center_x, end_center_y))
        else:
            end_center_y = end_center_y

        route_points.append((end_center_x, end_center_y))
        return route_points


def is_supported_injection_api_object(api_object: ALL_DEV_TYPES) -> bool:
    """
    Return whether one API object is rendered as a bus child graphic.

    :param api_object: Candidate API object.
    :return: ``True`` when the object is rendered as a bus child.
    """
    return isinstance(api_object,
                      (dev.Generator,
                       dev.StaticGenerator,
                       dev.Battery,
                       dev.Load,
                       dev.ExternalGrid,
                       dev.Shunt,
                       dev.ControllableShunt,
                       dev.CurrentInjection))


def get_injection_graphic_size(api_object: ALL_DEV_TYPES) -> Tuple[float, float]:
    """
    Return the nominal child-graphic footprint used by the current VeraGrid widgets.

    :param api_object: Injection-like API object.
    :return: Width and height in pixels.
    """
    if isinstance(api_object, dev.Load):
        return 20.0, 20.0
    elif isinstance(api_object, dev.Shunt):
        return 20.0, 40.0
    else:
        return 40.0, 40.0


def infer_injection_dock_side(bus_location: GraphicLocation,
                              injection_location: GraphicLocation) -> str:
    """
    Infer the preferred dock side of one imported child relative to its owner bus.

    :param bus_location: Owner bus location.
    :param injection_location: Imported child location.
    :return: Persisted side key.
    """
    bus_center_x: float = float(bus_location.x) + float(bus_location.w) * 0.5
    bus_center_y: float = float(bus_location.y) + float(bus_location.h) * 0.5
    injection_center_x: float = float(injection_location.x) + float(injection_location.w) * 0.5
    injection_center_y: float = float(injection_location.y) + float(injection_location.h) * 0.5
    delta_x: float = injection_center_x - bus_center_x
    delta_y: float = injection_center_y - bus_center_y

    if abs(delta_x) > abs(delta_y):
        if delta_x < 0.0:
            return "left"
        else:
            return "right"
    else:
        if delta_y < 0.0:
            return "top"
        else:
            return "bottom"


def set_imported_injection_layout(diagram: SchematicDiagram,
                                  api_object: ALL_DEV_TYPES,
                                  graphic: IntGrf,
                                  stretch_vertical: bool = True) -> None:
    """
    Persist the imported child position and manual dock metadata for one injection-like device.

    :param diagram: Target child schematic.
    :param api_object: Injection-like API object.
    :param graphic: Matching DGS graphical object.
    :return: ``None``.
    """
    owner_bus: dev.Bus | None = api_object.bus

    if owner_bus is None:
        return
    else:
        owner_bus_location = diagram.query_point(owner_bus)

    if owner_bus_location is None:
        return
    else:
        child_width: float
        child_height: float
        child_width, child_height = get_injection_graphic_size(api_object=api_object)
        child_x: float
        child_y: float
        child_x, child_y = transform_dgs_center_to_top_left(graphic.rCenterX,
                                                            graphic.rCenterY,
                                                            child_width,
                                                            child_height)
        if stretch_vertical:
            child_x, child_y = stretch_child_diagram_position(child_x, child_y)
        child_location = GraphicLocation(api_object=api_object,
                                         x=child_x,
                                         y=child_y,
                                         w=child_width,
                                         h=child_height,
                                         r=float(graphic.iRot),
                                         draw_labels=True)
        diagram.set_point(device=api_object, location=child_location)
        dock = diagram.sync_injection_dock(api_object=api_object,
                                           owner_device=owner_bus,
                                           side=infer_injection_dock_side(bus_location=owner_bus_location,
                                                                          injection_location=child_location))
        dock["auto_layout"] = False
        dock["nexus_route_kind"] = SchematicRouteKind.AUTO_ORTHOGONAL.value
        diagram.set_dock(api_object=api_object, dock=dock)


def is_branch_inter_substation(branch: ALL_DEV_TYPES) -> bool:
    """
    Check whether one branch connects two different imported substations.

    :param branch: Candidate branch object.
    :return: ``True`` when the branch spans distinct substations.
    """
    if not is_two_terminal_schematic_branch(branch=branch):
        return False
    else:
        pass

    bus_from: dev.Bus | None = branch.bus_from
    bus_to: dev.Bus | None = branch.bus_to

    if bus_from is None or bus_to is None:
        return False
    elif bus_from.substation is None or bus_to.substation is None:
        return False
    elif bus_from.substation == bus_to.substation:
        return False
    else:
        return True


def get_substation_id_sort_key(entry: Tuple[str, str], substation_by_id: Dict[str, dev.Substation]) -> Tuple[str, str]:
    """
    Build the ordering key for child diagrams.

    :param entry: Pair of substation id and diagram id.
    :param substation_by_id: Imported substations indexed by DGS id.
    :return: Stable lexical sort key.
    """
    substation: dev.Substation | None = substation_by_id.get(entry[0], None)

    if substation is None:
        return entry[0], entry[1]
    else:
        return substation.name, entry[1]


def do_locations_overlap(location_a: GraphicLocation, location_b: GraphicLocation) -> bool:
    """
    Return whether two imported rectangles overlap.

    :param location_a: First location.
    :param location_b: Second location.
    :return: ``True`` when the rectangles overlap.
    """
    left_a: float
    top_a: float
    right_a: float
    bottom_a: float
    left_b: float
    top_b: float
    right_b: float
    bottom_b: float
    left_a, top_a, right_a, bottom_a = build_location_bounds(location=location_a)
    left_b, top_b, right_b, bottom_b = build_location_bounds(location=location_b)

    if right_a <= left_b or right_b <= left_a or bottom_a <= top_b or bottom_b <= top_a:
        return False
    else:
        return True


def separate_overlapping_locations(locations: List[GraphicLocation],
                                   iteration_limit: int = 12,
                                   gap_value: float = 20.0) -> None:
    """
    Resolve residual rectangle overlaps with a small deterministic relaxation pass.

    The imported reduced overview is already close to its intended layout. The goal of
    this pass is not to invent a new arrangement, only to push apart any remaining proxy
    rectangles that would otherwise hide each other in VeraGrid.

    :param locations: Mutable rectangle locations.
    :param iteration_limit: Maximum relaxation passes.
    :param gap_value: Extra clearance inserted between separated rectangles.
    :return: ``None``.
    """
    pass_index: int = 0

    while pass_index < iteration_limit:
        moved_any_location: bool = False
        location_index_a: int = 0

        while location_index_a < len(locations):
            location_a: GraphicLocation = locations[location_index_a]
            location_index_b: int = location_index_a + 1

            while location_index_b < len(locations):
                location_b: GraphicLocation = locations[location_index_b]

                if do_locations_overlap(location_a=location_a, location_b=location_b):
                    left_a: float
                    top_a: float
                    right_a: float
                    bottom_a: float
                    left_b: float
                    top_b: float
                    right_b: float
                    bottom_b: float
                    left_a, top_a, right_a, bottom_a = build_location_bounds(location=location_a)
                    left_b, top_b, right_b, bottom_b = build_location_bounds(location=location_b)
                    overlap_x: float = min(right_a, right_b) - max(left_a, left_b)
                    overlap_y: float = min(bottom_a, bottom_b) - max(top_a, top_b)

                    if overlap_x <= overlap_y:
                        shift_value: float = overlap_x * 0.5 + gap_value * 0.5

                        if left_a <= left_b:
                            location_a.x -= shift_value
                            location_b.x += shift_value
                        else:
                            location_a.x += shift_value
                            location_b.x -= shift_value
                    else:
                        shift_value = overlap_y * 0.5 + gap_value * 0.5

                        if top_a <= top_b:
                            location_a.y -= shift_value
                            location_b.y += shift_value
                        else:
                            location_a.y += shift_value
                            location_b.y -= shift_value

                    moved_any_location = True
                else:
                    location_b = location_b

                location_index_b += 1

            location_index_a += 1

        if moved_any_location:
            pass_index += 1
        else:
            return


def build_elmterm_by_id(dgs_grid: DgsCircuit) -> Dict[str, ElmTerm]:
    """
    Index DGS terminals by normalized identifier.

    :param dgs_grid: Parsed DGS circuit.
    :return: Terminal index.
    """
    terminals_by_id: Dict[str, ElmTerm] = dict()
    elmterm: ElmTerm

    for elmterm in dgs_grid.elmterms:
        terminals_by_id[normalize_dgs_ref_id(elmterm.ID)] = elmterm

    return terminals_by_id


def get_graphic_scene_center(graphic: IntGrf) -> Tuple[float, float]:
    """Return one DGS graphic center in VeraGrid scene coordinates."""
    return transform_dgs_coordinate_pair(graphic.rCenterX, graphic.rCenterY)


def build_arrangement_similarity_transform(source_graphics_by_object_id: Dict[str, IntGrf],
                                           target_graphics_by_object_id: Dict[str, IntGrf]) -> Tuple[float, float, float,
                                                                                                   float, float] | None:
    """Fit a stable similarity transform between a substation and grid view.

    Shared busbars are the authoritative anchors.  Two anchors recover scale,
    rotation and translation; a single anchor falls back to the relative symbol
    size and translation.  Scale limits keep unusually small overview symbols
    usable without changing the arrangement topology.

    :return: ``scale, cosine, sine, translate_x, translate_y`` or ``None``.
    """
    shared_object_ids: List[str] = sorted(set(source_graphics_by_object_id).intersection(target_graphics_by_object_id))
    if len(shared_object_ids) == 0:
        return None

    source_anchor_id: str = shared_object_ids[0]
    target_anchor_id: str = source_anchor_id
    source_anchor: Tuple[float, float] = get_graphic_scene_center(source_graphics_by_object_id[source_anchor_id])
    target_anchor: Tuple[float, float] = get_graphic_scene_center(target_graphics_by_object_id[target_anchor_id])
    scale_value: float
    cosine_value: float = 1.0
    sine_value: float = 0.0

    if len(shared_object_ids) >= 2:
        best_pair: Tuple[str, str] | None = None
        best_distance_squared: float = -1.0
        left_index: int = 0

        while left_index < len(shared_object_ids) - 1:
            right_index: int = left_index + 1
            while right_index < len(shared_object_ids):
                left_id: str = shared_object_ids[left_index]
                right_id: str = shared_object_ids[right_index]
                source_left: Tuple[float, float] = get_graphic_scene_center(source_graphics_by_object_id[left_id])
                source_right: Tuple[float, float] = get_graphic_scene_center(source_graphics_by_object_id[right_id])
                delta_x: float = source_right[0] - source_left[0]
                delta_y: float = source_right[1] - source_left[1]
                distance_squared: float = delta_x * delta_x + delta_y * delta_y
                if distance_squared > best_distance_squared:
                    best_distance_squared = distance_squared
                    best_pair = (left_id, right_id)
                right_index += 1
            left_index += 1

        if best_pair is not None and best_distance_squared > 1e-12:
            source_anchor_id = best_pair[0]
            target_anchor_id = best_pair[0]
            source_anchor = get_graphic_scene_center(source_graphics_by_object_id[source_anchor_id])
            target_anchor = get_graphic_scene_center(target_graphics_by_object_id[target_anchor_id])
            source_second: Tuple[float, float] = get_graphic_scene_center(source_graphics_by_object_id[best_pair[1]])
            target_second: Tuple[float, float] = get_graphic_scene_center(target_graphics_by_object_id[best_pair[1]])
            source_delta_x: float = source_second[0] - source_anchor[0]
            source_delta_y: float = source_second[1] - source_anchor[1]
            target_delta_x: float = target_second[0] - target_anchor[0]
            target_delta_y: float = target_second[1] - target_anchor[1]
            source_distance: float = math.hypot(source_delta_x, source_delta_y)
            target_distance: float = math.hypot(target_delta_x, target_delta_y)
            scale_value = target_distance / source_distance
            source_angle: float = math.atan2(source_delta_y, source_delta_x)
            target_angle: float = math.atan2(target_delta_y, target_delta_x)
            rotation_angle: float = target_angle - source_angle
            cosine_value = math.cos(rotation_angle)
            sine_value = math.sin(rotation_angle)
        else:
            scale_value = 1.0
    else:
        source_graphic: IntGrf = source_graphics_by_object_id[source_anchor_id]
        target_graphic: IntGrf = target_graphics_by_object_id[target_anchor_id]
        source_extent: float = max(abs(float(source_graphic.rSizeX)), abs(float(source_graphic.rSizeY)), 1e-9)
        target_extent: float = max(abs(float(target_graphic.rSizeX)), abs(float(target_graphic.rSizeY)), 1e-9)
        scale_value = target_extent / source_extent

    scale_value = max(DGS_ARRANGEMENT_MIN_SCALE, min(DGS_ARRANGEMENT_MAX_SCALE, scale_value))
    rotated_source_x: float = scale_value * (cosine_value * source_anchor[0] - sine_value * source_anchor[1])
    rotated_source_y: float = scale_value * (sine_value * source_anchor[0] + cosine_value * source_anchor[1])
    translate_x: float = target_anchor[0] - rotated_source_x
    translate_y: float = target_anchor[1] - rotated_source_y
    return scale_value, cosine_value, sine_value, translate_x, translate_y


def transform_arrangement_point(point: Tuple[float, float],
                                transform: Tuple[float, float, float, float, float]) -> Tuple[float, float]:
    """Apply a substation-to-grid similarity transform to one scene point."""
    scale_value, cosine_value, sine_value, translate_x, translate_y = transform
    transformed_x: float = scale_value * (cosine_value * point[0] - sine_value * point[1]) + translate_x
    transformed_y: float = scale_value * (sine_value * point[0] + cosine_value * point[1]) + translate_y
    return transformed_x, transformed_y


def get_transformed_graphic_location(api_object: ALL_DEV_TYPES,
                                     graphic: IntGrf,
                                     transform: Tuple[float, float, float, float, float],
                                     width: float,
                                     height: float,
                                     minimum_width: float,
                                     minimum_height: float,
                                     draw_labels: bool = True) -> GraphicLocation:
    """Build a location for one detailed object embedded in a grid diagram."""
    scale_value: float = transform[0]
    transformed_center: Tuple[float, float] = transform_arrangement_point(
        point=get_graphic_scene_center(graphic),
        transform=transform,
    )
    transformed_width: float = max(float(width) * scale_value, minimum_width)
    transformed_height: float = max(float(height) * scale_value, minimum_height)
    rotation_angle_degrees: float = math.degrees(math.atan2(transform[2], transform[1]))
    return GraphicLocation(
        api_object=api_object,
        x=transformed_center[0] - transformed_width * 0.5,
        y=transformed_center[1] - transformed_height * 0.5,
        w=transformed_width,
        h=transformed_height,
        r=float(graphic.iRot) + rotation_angle_degrees,
        draw_labels=draw_labels,
    )


def build_substation_detail_diagram(diagram_id: str,
                                    substation: dev.Substation,
                                    source_diagram: IntGrfnet | None,
                                    graphics_by_diagram_id: Dict[str, List[IntGrf]],
                                    connections_by_graphic_id: Dict[str, List[IntGrfcon]],
                                    terminals_by_id: Dict[str, ElmTerm],
                                    bus_by_term_id: Dict[str, dev.Bus],
                                    api_objects_by_dgs_id: Dict[str, List[ALL_DEV_TYPES]]) -> SchematicDiagram:
    """Materialize one complete PowerFactory substation arrangement."""
    diagram_name: str = substation.name
    if source_diagram is not None and source_diagram.loc_name != "":
        diagram_name = source_diagram.loc_name
    detailed_diagram = SchematicDiagram(idtag=diagram_id, name=diagram_name)
    diagram_graphics: List[IntGrf] = graphics_by_diagram_id.get(diagram_id, list())

    for graphic in diagram_graphics:
        object_id: str = normalize_dgs_ref_id(graphic.pDataObj)
        bus: dev.Bus | None = bus_by_term_id.get(object_id, None)
        elmterm: ElmTerm | None = terminals_by_id.get(object_id, None)
        if bus is None or elmterm is None:
            continue
        bus.graphic_type = get_bus_graphic_type_from_dgs_terminal(elmterm=elmterm)
        width, height = get_bus_size_from_graphic(bus=bus, graphic=graphic)
        x_pos, y_pos = transform_dgs_center_to_top_left(graphic.rCenterX, graphic.rCenterY, width, height)
        x_pos, y_pos = stretch_child_diagram_position(x_pos, y_pos)
        detailed_diagram.set_point(
            device=bus,
            location=GraphicLocation(
                api_object=bus,
                x=x_pos,
                y=y_pos,
                w=width,
                h=height,
                r=float(graphic.iRot),
                draw_labels=not should_hide_imported_bus_label(bus),
            ),
        )

    seen_device_ids: set[str] = set()
    for graphic in diagram_graphics:
        object_id = normalize_dgs_ref_id(graphic.pDataObj)
        diagram_objects: List[ALL_DEV_TYPES] = api_objects_by_dgs_id.get(object_id, list())
        if len(diagram_objects) == 0:
            continue
        diagram_api_object: ALL_DEV_TYPES = diagram_objects[0]
        if diagram_api_object.idtag in seen_device_ids:
            continue
        if is_supported_injection_api_object(diagram_api_object):
            set_imported_injection_layout(diagram=detailed_diagram,
                                          api_object=diagram_api_object,
                                          graphic=graphic)
        elif isinstance(diagram_api_object, (dev.Transformer3W, dev.TransformerNW)):
            width = max(float(graphic.rSizeX) * 18.0, 40.0)
            height = max(float(graphic.rSizeY) * 18.0, 40.0)
            x_pos, y_pos = transform_dgs_center_to_top_left(graphic.rCenterX, graphic.rCenterY, width, height)
            x_pos, y_pos = stretch_child_diagram_position(x_pos, y_pos)
            detailed_diagram.set_point(
                device=diagram_api_object,
                location=GraphicLocation(api_object=diagram_api_object,
                                         x=x_pos,
                                         y=y_pos,
                                         w=width,
                                         h=height,
                                         r=float(graphic.iRot)),
            )
        else:
            route_points: List[Tuple[float, float]] = build_dgs_branch_route_points_for_graphic(
                graphic=graphic,
                connections_by_graphic_id=connections_by_graphic_id,
            )
            route_points = stretch_child_route_points(route_points)
            if len(route_points) >= 2:
                set_imported_branch_route_and_attachments(diagram=detailed_diagram,
                                                          branch=diagram_api_object,
                                                          route_points=route_points,
                                                          graphic=graphic,
                                                          enforce_orthogonal=True)
                branch_location: GraphicLocation | None = detailed_diagram.query_point(diagram_api_object)
                if branch_location is not None:
                    branch_location.draw_labels = not should_hide_imported_branch_label(diagram_api_object)
        seen_device_ids.add(diagram_api_object.idtag)

    return detailed_diagram


def expand_substation_arrangements_into_grid_diagram(
        diagram: SchematicDiagram,
        diagram_id: str,
        diagram_graphics: List[IntGrf],
        child_diagram_id_by_substation_id: Dict[str, str],
        substation_by_id: Dict[str, dev.Substation],
        graphics_by_diagram_id: Dict[str, List[IntGrf]],
        terminals_by_id: Dict[str, ElmTerm],
        bus_by_term_id: Dict[str, dev.Bus],
        api_objects_by_dgs_id: Dict[str, List[ALL_DEV_TYPES]]) -> None:
    """Embed complete internal switchgear for substations reduced in a grid view."""
    target_terminal_graphics_by_substation_id: Dict[str, Dict[str, IntGrf]] = dict()

    for graphic in diagram_graphics:
        object_id: str = normalize_dgs_ref_id(graphic.pDataObj)
        if object_id in substation_by_id:
            continue
        elmterm: ElmTerm | None = terminals_by_id.get(object_id, None)
        bus: dev.Bus | None = bus_by_term_id.get(object_id, None)
        if elmterm is None or bus is None or bus.substation is None:
            continue
        substation_id: str = str(bus.substation.idtag)
        target_terminal_graphics_by_substation_id.setdefault(substation_id, dict())[object_id] = graphic

    for substation_id, target_graphics_by_object_id in target_terminal_graphics_by_substation_id.items():
        detail_diagram_id: str = child_diagram_id_by_substation_id.get(substation_id, "")
        if detail_diagram_id == "" or detail_diagram_id == diagram_id:
            continue
        source_graphics: List[IntGrf] = graphics_by_diagram_id.get(detail_diagram_id, list())
        source_terminal_graphics_by_object_id: Dict[str, IntGrf] = dict()
        for source_graphic in source_graphics:
            source_object_id: str = normalize_dgs_ref_id(source_graphic.pDataObj)
            source_bus: dev.Bus | None = bus_by_term_id.get(source_object_id, None)
            if source_bus is not None and source_bus.substation is not None and str(source_bus.substation.idtag) == substation_id:
                source_terminal_graphics_by_object_id[source_object_id] = source_graphic

        transform = build_arrangement_similarity_transform(
            source_graphics_by_object_id=source_terminal_graphics_by_object_id,
            target_graphics_by_object_id=target_graphics_by_object_id,
        )
        if transform is None:
            continue

        # Buses must exist before switches so their real electrical endpoints
        # can own the route attachments.
        for object_id, source_graphic in source_terminal_graphics_by_object_id.items():
            bus = bus_by_term_id[object_id]
            if diagram.query_point(bus) is not None:
                continue
            elmterm = terminals_by_id[object_id]
            bus.graphic_type = get_bus_graphic_type_from_dgs_terminal(elmterm=elmterm)
            width, height = get_bus_size_from_graphic(bus=bus, graphic=source_graphic)
            minimum_size: float = DGS_CONNECTIVITY_BUS_SCALE if bus.graphic_type == BusGraphicType.Connectivity else 40.0
            diagram.set_point(
                device=bus,
                location=get_transformed_graphic_location(
                    api_object=bus,
                    graphic=source_graphic,
                    transform=transform,
                    width=width,
                    height=height,
                    minimum_width=minimum_size,
                    minimum_height=minimum_size,
                    draw_labels=not should_hide_imported_bus_label(bus),
                ),
            )

        seen_switch_ids: set[str] = set()
        for source_graphic in source_graphics:
            source_object_id = normalize_dgs_ref_id(source_graphic.pDataObj)
            diagram_objects: List[ALL_DEV_TYPES] = api_objects_by_dgs_id.get(source_object_id, list())
            if len(diagram_objects) == 0 or not isinstance(diagram_objects[0], dev.Switch):
                continue
            switch: dev.Switch = diagram_objects[0]
            if switch.idtag in seen_switch_ids:
                continue
            if switch.bus_from is None or switch.bus_to is None:
                continue
            if switch.bus_from.substation is None or switch.bus_to.substation is None:
                continue
            if str(switch.bus_from.substation.idtag) != substation_id or str(switch.bus_to.substation.idtag) != substation_id:
                continue
            switch_width, switch_height = get_branch_symbol_size(api_object=switch, graphic=source_graphic)
            switch_location: GraphicLocation = get_transformed_graphic_location(
                api_object=switch,
                graphic=source_graphic,
                transform=transform,
                width=switch_width,
                height=switch_height,
                minimum_width=9.0,
                minimum_height=9.0,
                draw_labels=not should_hide_imported_branch_label(switch),
            )
            # Switch routing is rebuilt through the transformed symbol and the
            # actual endpoint buses. The source connector points are only a
            # fallback contract for the branch routine's minimum route length.
            from_location: GraphicLocation | None = diagram.query_point(switch.bus_from)
            to_location: GraphicLocation | None = diagram.query_point(switch.bus_to)
            if from_location is None or to_location is None:
                continue
            route_points = build_symbol_axis_route_points(branch_location=switch_location,
                                                          from_location=from_location,
                                                          to_location=to_location)
            if len(route_points) >= 2:
                set_imported_branch_route_and_attachments(
                    diagram=diagram,
                    branch=switch,
                    route_points=route_points,
                    graphic=source_graphic,
                    enforce_orthogonal=True,
                    branch_location_override=switch_location,
                )
                seen_switch_ids.add(switch.idtag)


def import_dgs_substations_and_schematic_diagrams(dgs_grid: DgsCircuit,
                                                  grid: dev.MultiCircuit,
                                                  bus_by_term_id: Dict[str, dev.Bus],
                                                  zone_by_id: Dict[str, dev.Zone],
                                                  api_objects_by_dgs_id: Dict[str, List[ALL_DEV_TYPES]],
                                                  logger: Logger) -> None:
    """
    Import PowerFactory substation metadata and hierarchical schematics from DGS.

    :param dgs_grid: Parsed DGS circuit.
    :param grid: Target VeraGrid circuit.
    :param bus_by_term_id: Imported buses indexed by DGS terminal id.
    :param zone_by_id: Imported zones indexed by DGS id.
    :param api_objects_by_dgs_id: Imported runtime objects indexed by DGS id.
    :param logger: Import logger.
    :return: ``None``.
    """
    static_diagram_ids: set[str] = build_static_diagram_ids(dgs_grid=dgs_grid)
    graphics_by_diagram_id: Dict[str, List[IntGrf]] = build_graphics_by_diagram_id(dgs_grid=dgs_grid)
    connections_by_graphic_id: Dict[str, List[IntGrfcon]] = build_connections_by_graphic_id(dgs_grid=dgs_grid)
    terminals_by_id: Dict[str, ElmTerm] = build_elmterm_by_id(dgs_grid=dgs_grid)
    intgrfnet_by_id: Dict[str, IntGrfnet] = dict()
    substation_by_id: Dict[str, dev.Substation] = dict()
    zone_by_name: Dict[str, dev.Zone] = dict()
    bus_idtags_by_substation_id: Dict[str, List[str]] = dict()
    child_diagram_id_by_substation_id: Dict[str, str] = dict()
    zone: dev.Zone
    dgs_substation: object
    dgs_term: ElmTerm
    diagram_object: IntGrfnet

    for zone in zone_by_id.values():
        zone_by_name[zone.name] = zone

    for dgs_substation in dgs_grid.elmsubstats:
        substation_id: str = normalize_dgs_ref_id(dgs_substation.ID)
        substation_name: str = dgs_substation.loc_name if dgs_substation.loc_name != "" else f"Substation_{substation_id}"
        zone_id: str = normalize_dgs_ref_id(dgs_substation.cpZone)
        substation_zone: dev.Zone | None = zone_by_id.get(zone_id, None)

        if substation_zone is None:
            substation_zone = zone_by_name.get(substation_name, None)
        else:
            pass

        substation = dev.Substation(name=substation_name,
                                    idtag=substation_id,
                                    code="",
                                    latitude=float(dgs_substation.GPSlat),
                                    longitude=float(dgs_substation.GPSlon),
                                    zone=substation_zone)
        grid.add_substation(obj=substation)
        substation_by_id[substation_id] = substation

    for dgs_term in dgs_grid.elmterms:
        term_id: str = normalize_dgs_ref_id(dgs_term.ID)
        bus: dev.Bus | None = bus_by_term_id.get(term_id, None)

        if bus is None:
            bus = bus
        else:
            zone_id: str = normalize_dgs_ref_id(dgs_term.cpZone)
            substation_id: str = normalize_dgs_ref_id(dgs_term.cpSubstat)

            if substation_id == "":
                substation_id = normalize_dgs_ref_id(dgs_term.fold_id)
            else:
                pass

            if substation_id == "":
                substation = None
            else:
                substation = substation_by_id.get(substation_id, None)

            if substation is None:
                substation = substation
            else:
                bus.substation = substation
                registered_bus_ids: List[str] | None = bus_idtags_by_substation_id.get(substation_id, None)

                if registered_bus_ids is None:
                    bus_idtags_by_substation_id[substation_id] = [bus.idtag]
                else:
                    registered_bus_ids.append(bus.idtag)

            if zone_id != "":
                bus_zone: dev.Zone | None = zone_by_id.get(zone_id, None)

                if bus_zone is None:
                    bus_zone = bus_zone
                else:
                    bus.zone = bus_zone
            elif bus.substation is not None and bus.substation.zone is not None:
                bus.zone = bus.substation.zone
            else:
                zone_id = zone_id

    for diagram_object in dgs_grid.intgrfnets:
        diagram_id: str = normalize_dgs_ref_id(diagram_object.ID)
        if diagram_id in static_diagram_ids:
            intgrfnet_by_id[diagram_id] = diagram_object

    for dgs_substation in dgs_grid.elmsubstats:
        substation_id: str = normalize_dgs_ref_id(dgs_substation.ID)
        direct_diagram_id: str = normalize_dgs_ref_id(dgs_substation.pDiagram)

        if direct_diagram_id in static_diagram_ids:
            child_diagram_id_by_substation_id[substation_id] = direct_diagram_id
        else:
            for diagram_object in intgrfnet_by_id.values():
                folder_id: str = normalize_dgs_ref_id(diagram_object.pDataFolder)
                diagram_id: str = normalize_dgs_ref_id(diagram_object.ID)

                if folder_id == substation_id and diagram_id != "":
                    child_diagram_id_by_substation_id[substation_id] = diagram_id
                    break
                else:
                    folder_id = folder_id

    root_diagram_id: str = select_preferred_root_diagram_id(dgs_grid=dgs_grid,
                                                            intgrfnet_by_id=intgrfnet_by_id,
                                                            graphics_by_diagram_id=graphics_by_diagram_id,
                                                            substation_by_id=substation_by_id)

    # Substation arrangements are deliberately materialized before every grid
    # or site view. They are both user-facing diagrams and the authoritative
    # geometry source used to expand reduced regional schematics below.
    imported_substation_diagram_ids: set[str] = set()
    ordered_substation_entries: List[Tuple[str, str]] = sorted(
        child_diagram_id_by_substation_id.items(),
        key=lambda entry: get_substation_id_sort_key(entry=entry, substation_by_id=substation_by_id),
    )
    for child_substation_id, child_diagram_id in ordered_substation_entries:
        if child_diagram_id in imported_substation_diagram_ids:
            continue
        child_diagram: SchematicDiagram = build_substation_detail_diagram(
            diagram_id=child_diagram_id,
            substation=substation_by_id[child_substation_id],
            source_diagram=intgrfnet_by_id.get(child_diagram_id, None),
            graphics_by_diagram_id=graphics_by_diagram_id,
            connections_by_graphic_id=connections_by_graphic_id,
            terminals_by_id=terminals_by_id,
            bus_by_term_id=bus_by_term_id,
            api_objects_by_dgs_id=api_objects_by_dgs_id,
        )
        if len(child_diagram.data) > 0:
            grid.add_diagram(child_diagram)
            imported_substation_diagram_ids.add(child_diagram_id)

    if root_diagram_id != "":
        root_diagram_object: IntGrfnet | None = intgrfnet_by_id.get(root_diagram_id, None)
        root_diagram_name: str = "DGS root schematic"

        if root_diagram_object is None:
            root_diagram_name = "DGS root schematic"
        elif root_diagram_object.loc_name != "":
            root_diagram_name = root_diagram_object.loc_name
        else:
            root_diagram_name = "DGS root schematic"

        root_diagram: SchematicDiagram = SchematicDiagram(idtag=root_diagram_id, name=root_diagram_name)
        seen_branch_ids: set[str] = set()
        root_graphic: IntGrf

        # First materialize every visible grouped substation so branch attachment resolution
        # can work against the final rectangle set instead of a partial dictionary.
        for root_graphic in graphics_by_diagram_id.get(root_diagram_id, list()):
            object_id: str = normalize_dgs_ref_id(root_graphic.pDataObj)
            substation: dev.Substation | None = substation_by_id.get(object_id, None)
            bus: dev.Bus | None = bus_by_term_id.get(object_id, None)

            if substation is not None:
                width: float
                height: float
                width, height = get_substation_size_from_graphic(root_graphic)
                x_pos: float
                y_pos: float
                x_pos, y_pos = transform_dgs_center_to_top_left(root_graphic.rCenterX,
                                                                root_graphic.rCenterY,
                                                                width,
                                                                height)
                location_metadata: Dict[str, object] = dict()
                location_metadata["collapsed_bus_idtags"] = list(bus_idtags_by_substation_id.get(object_id, list()))
                child_diagram_id: str = child_diagram_id_by_substation_id.get(object_id, "")

                if child_diagram_id != "":
                    location_metadata["dgs_child_diagram_id"] = child_diagram_id
                else:
                    child_diagram_id = child_diagram_id

                root_diagram.set_point(device=substation,
                                       location=GraphicLocation(api_object=substation,
                                                                x=x_pos,
                                                                y=y_pos,
                                                                w=width,
                                                                h=height,
                                                                 r=float(root_graphic.iRot),
                                                                 layout_metadata=location_metadata))
            elif bus is not None:
                elmterm: ElmTerm | None = terminals_by_id.get(object_id, None)
                if elmterm is not None:
                    bus.graphic_type = get_bus_graphic_type_from_dgs_terminal(elmterm=elmterm)
                width, height = get_bus_size_from_graphic(bus=bus, graphic=root_graphic)
                x_pos, y_pos = transform_dgs_center_to_top_left(root_graphic.rCenterX,
                                                                root_graphic.rCenterY,
                                                                width,
                                                                height)
                root_diagram.set_point(
                    device=bus,
                    location=GraphicLocation(api_object=bus,
                                             x=x_pos,
                                             y=y_pos,
                                             w=width,
                                             h=height,
                                             r=float(root_graphic.iRot),
                                             draw_labels=not should_hide_imported_bus_label(bus)),
                )

        root_substation_group = root_diagram.query_by_type(DeviceType.SubstationDevice)

        if root_substation_group is None:
            root_substation_group = root_substation_group
        else:
            separate_overlapping_locations(locations=list(root_substation_group.locations.values()))

        expand_substation_arrangements_into_grid_diagram(
            diagram=root_diagram,
            diagram_id=root_diagram_id,
            diagram_graphics=graphics_by_diagram_id.get(root_diagram_id, list()),
            child_diagram_id_by_substation_id=child_diagram_id_by_substation_id,
            substation_by_id=substation_by_id,
            graphics_by_diagram_id=graphics_by_diagram_id,
            terminals_by_id=terminals_by_id,
            bus_by_term_id=bus_by_term_id,
            api_objects_by_dgs_id=api_objects_by_dgs_id,
        )

        # Once the grouped substations exist and have been de-overlapped, import the inter-zone branches.
        for root_graphic in graphics_by_diagram_id.get(root_diagram_id, list()):
            object_id = normalize_dgs_ref_id(root_graphic.pDataObj)

            if substation_by_id.get(object_id, None) is None:
                branch_devices: List[ALL_DEV_TYPES] | None = api_objects_by_dgs_id.get(object_id, None)

                if branch_devices is None or len(branch_devices) == 0:
                    branch_devices = branch_devices
                else:
                    branch_api_object = branch_devices[0]

                    if is_supported_injection_api_object(branch_api_object):
                        branch_api_object = branch_api_object
                    elif branch_api_object.idtag in seen_branch_ids:
                        branch_api_object = branch_api_object
                    elif is_branch_inter_substation(branch_api_object):
                        route_points = build_dgs_branch_route_points_for_graphic(graphic=root_graphic,
                                                                                connections_by_graphic_id=connections_by_graphic_id)

                        if len(route_points) >= 2:
                            set_imported_branch_route_and_attachments(diagram=root_diagram,
                                                                      branch=branch_api_object,
                                                                      route_points=route_points,
                                                                      graphic=root_graphic,
                                                                      enforce_orthogonal=False)
                        else:
                            route_points = route_points

                        seen_branch_ids.add(branch_api_object.idtag)
                    else:
                        branch_api_object = branch_api_object
            else:
                object_id = object_id

        if len(root_diagram.data) > 0:
            grid.add_diagram(root_diagram)
    else:
        root_diagram_id = root_diagram_id

    sortable_child_entries: List[Tuple[str, str]] = list(child_diagram_id_by_substation_id.items())
    sortable_entries_with_keys: List[Tuple[Tuple[str, str], Tuple[str, str]]] = list()
    child_entry: Tuple[str, str]

    # Decorate-sort-undecorate keeps the ordering logic explicit without adding one more helper class.
    for child_entry in sortable_child_entries:
        sortable_entries_with_keys.append((get_substation_id_sort_key(entry=child_entry,
                                                                      substation_by_id=substation_by_id),
                                           child_entry))

    sortable_entries_with_keys.sort()
    sortable_child_entries = list()

    for _, child_entry in sortable_entries_with_keys:
        sortable_child_entries.append(child_entry)

    for child_entry in sortable_child_entries:
        child_substation_id: str = child_entry[0]
        child_diagram_id: str = child_entry[1]
        if child_diagram_id in imported_substation_diagram_ids:
            continue
        child_diagram_object: IntGrfnet | None = intgrfnet_by_id.get(child_diagram_id, None)
        child_diagram_name: str = substation_by_id[child_substation_id].name

        if child_diagram_object is None:
            child_diagram_name = substation_by_id[child_substation_id].name
        elif child_diagram_object.loc_name != "":
            child_diagram_name = child_diagram_object.loc_name
        else:
            child_diagram_name = substation_by_id[child_substation_id].name

        child_diagram: SchematicDiagram = SchematicDiagram(idtag=child_diagram_id, name=child_diagram_name)
        seen_branch_ids: set[str] = set()
        graphic: IntGrf

        for graphic in graphics_by_diagram_id.get(child_diagram_id, list()):
            object_id: str = normalize_dgs_ref_id(graphic.pDataObj)
            bus: dev.Bus | None = bus_by_term_id.get(object_id, None)
            elmterm: ElmTerm | None = terminals_by_id.get(object_id, None)

            if bus is None or elmterm is None:
                bus = bus
            else:
                bus.graphic_type = get_bus_graphic_type_from_dgs_terminal(elmterm=elmterm)
                width, height = get_bus_size_from_graphic(bus=bus, graphic=graphic)
                x_pos: float
                y_pos: float
                x_pos, y_pos = transform_dgs_center_to_top_left(graphic.rCenterX,
                                                                graphic.rCenterY,
                                                                width,
                                                                height)
                x_pos, y_pos = stretch_child_diagram_position(x_pos, y_pos)
                child_diagram.set_point(device=bus,
                                        location=GraphicLocation(api_object=bus,
                                                                 x=x_pos,
                                                                 y=y_pos,
                                                                 w=width,
                                                                 h=height,
                                                                 r=float(graphic.iRot),
                                                                 draw_labels=not should_hide_imported_bus_label(bus)))

        for graphic in graphics_by_diagram_id.get(child_diagram_id, list()):
            object_id = normalize_dgs_ref_id(graphic.pDataObj)
            diagram_objects = api_objects_by_dgs_id.get(object_id, None)

            if diagram_objects is None or len(diagram_objects) == 0:
                diagram_objects = diagram_objects
            else:
                diagram_api_object = diagram_objects[0]

                if is_supported_injection_api_object(diagram_api_object):
                    set_imported_injection_layout(diagram=child_diagram,
                                                  api_object=diagram_api_object,
                                                  graphic=graphic)
                elif diagram_api_object.idtag in seen_branch_ids:
                    diagram_api_object = diagram_api_object
                else:
                    route_points = build_dgs_branch_route_points_for_graphic(graphic=graphic,
                                                                            connections_by_graphic_id=connections_by_graphic_id)
                    route_points = stretch_child_route_points(route_points)
                    if len(route_points) >= 2:
                        set_imported_branch_route_and_attachments(diagram=child_diagram,
                                                                  branch=diagram_api_object,
                                                                  route_points=route_points,
                                                                  graphic=graphic,
                                                                  enforce_orthogonal=True)
                        branch_location = child_diagram.query_point(diagram_api_object)

                        if branch_location is None:
                            branch_location = branch_location
                        else:
                            branch_location.draw_labels = not should_hide_imported_branch_label(diagram_api_object)
                    else:
                        route_points = route_points

                    seen_branch_ids.add(diagram_api_object.idtag)

        if len(child_diagram.data) > 0:
            grid.add_diagram(child_diagram)

    # Materialize any remaining static network/site diagrams.  The historical
    # importer above retains the preferred root and substation presentation;
    # this pass covers alternate ElmNet views and ElmSite overviews without
    # ever admitting an ownerless or dynamic-model diagram.
    imported_diagram_ids: set[str] = {
        str(diagram.idtag)
        for diagram in grid.get_diagrams()
        if isinstance(diagram, SchematicDiagram)
    }
    for diagram_id in sorted(static_diagram_ids):
        if diagram_id in imported_diagram_ids:
            continue

        source_diagram: IntGrfnet | None = intgrfnet_by_id.get(diagram_id, None)
        if source_diagram is None:
            continue
        diagram_name: str = source_diagram.loc_name if source_diagram.loc_name != "" else f"DGS schematic {diagram_id}"
        schematic = SchematicDiagram(idtag=diagram_id, name=diagram_name)
        diagram_graphics: List[IntGrf] = graphics_by_diagram_id.get(diagram_id, list())

        # Endpoint owners must exist before routes and docks are restored.
        for graphic in diagram_graphics:
            object_id: str = normalize_dgs_ref_id(graphic.pDataObj)
            substation: dev.Substation | None = substation_by_id.get(object_id, None)
            bus: dev.Bus | None = bus_by_term_id.get(object_id, None)

            if substation is not None:
                width, height = get_substation_size_from_graphic(graphic=graphic)
                x_pos, y_pos = transform_dgs_center_to_top_left(
                    graphic.rCenterX, graphic.rCenterY, width, height,
                )
                location_metadata: Dict[str, object] = {
                    "collapsed_bus_idtags": list(bus_idtags_by_substation_id.get(object_id, list())),
                }
                child_diagram_id: str = child_diagram_id_by_substation_id.get(object_id, "")
                if child_diagram_id != "":
                    location_metadata["dgs_child_diagram_id"] = child_diagram_id
                schematic.set_point(
                    device=substation,
                    location=GraphicLocation(
                        api_object=substation,
                        x=x_pos,
                        y=y_pos,
                        w=width,
                        h=height,
                        r=float(graphic.iRot),
                        layout_metadata=location_metadata,
                    ),
                )
            elif bus is not None:
                elmterm: ElmTerm | None = terminals_by_id.get(object_id, None)
                if elmterm is not None:
                    bus.graphic_type = get_bus_graphic_type_from_dgs_terminal(elmterm=elmterm)
                width, height = get_bus_size_from_graphic(bus=bus, graphic=graphic)
                x_pos, y_pos = transform_dgs_center_to_top_left(
                    graphic.rCenterX, graphic.rCenterY, width, height,
                )
                schematic.set_point(
                    device=bus,
                    location=GraphicLocation(
                        api_object=bus,
                        x=x_pos,
                        y=y_pos,
                        w=width,
                        h=height,
                        r=float(graphic.iRot),
                        draw_labels=not should_hide_imported_bus_label(bus),
                    ),
                )

        expand_substation_arrangements_into_grid_diagram(
            diagram=schematic,
            diagram_id=diagram_id,
            diagram_graphics=diagram_graphics,
            child_diagram_id_by_substation_id=child_diagram_id_by_substation_id,
            substation_by_id=substation_by_id,
            graphics_by_diagram_id=graphics_by_diagram_id,
            terminals_by_id=terminals_by_id,
            bus_by_term_id=bus_by_term_id,
            api_objects_by_dgs_id=api_objects_by_dgs_id,
        )

        seen_device_ids: set[str] = set()
        for graphic in diagram_graphics:
            object_id = normalize_dgs_ref_id(graphic.pDataObj)
            diagram_objects: List[ALL_DEV_TYPES] = api_objects_by_dgs_id.get(object_id, list())
            if len(diagram_objects) == 0:
                continue

            diagram_api_object: ALL_DEV_TYPES = diagram_objects[0]
            if diagram_api_object.idtag in seen_device_ids:
                continue

            if is_supported_injection_api_object(diagram_api_object):
                set_imported_injection_layout(
                    diagram=schematic,
                    api_object=diagram_api_object,
                    graphic=graphic,
                    stretch_vertical=False,
                )
            elif isinstance(diagram_api_object, (dev.Transformer3W, dev.TransformerNW)):
                width = max(float(graphic.rSizeX) * 18.0, 40.0)
                height = max(float(graphic.rSizeY) * 18.0, 40.0)
                x_pos, y_pos = transform_dgs_center_to_top_left(
                    graphic.rCenterX, graphic.rCenterY, width, height,
                )
                schematic.set_point(
                    device=diagram_api_object,
                    location=GraphicLocation(
                        api_object=diagram_api_object,
                        x=x_pos,
                        y=y_pos,
                        w=width,
                        h=height,
                        r=float(graphic.iRot),
                    ),
                )
            else:
                route_points: List[Tuple[float, float]] = build_dgs_branch_route_points_for_graphic(
                    graphic=graphic,
                    connections_by_graphic_id=connections_by_graphic_id,
                )
                if len(route_points) >= 2:
                    set_imported_branch_route_and_attachments(
                        diagram=schematic,
                        branch=diagram_api_object,
                        route_points=route_points,
                        graphic=graphic,
                        enforce_orthogonal=False,
                    )
            seen_device_ids.add(diagram_api_object.idtag)

        if len(schematic.data) > 0:
            grid.add_diagram(schematic)

    final_imported_diagram_ids: set[str] = {
        str(diagram.idtag)
        for diagram in grid.get_diagrams()
        if isinstance(diagram, SchematicDiagram)
    }
    undrawn_static_count: int = len(static_diagram_ids - final_imported_diagram_ids)
    if undrawn_static_count > 0:
        logger.add_warning(
            msg="Static DGS schematics contained no supported drawable objects",
            value=undrawn_static_count,
            expected_value=len(static_diagram_ids),
        )
