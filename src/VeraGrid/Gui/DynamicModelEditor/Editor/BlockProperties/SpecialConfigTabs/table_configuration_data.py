# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Detached numeric drafts shared by block-specific table editors."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import (
    Comparison,
    Expr,
    Var,
    string_to_symbolic,
)


def generate_curve_points_from_expression(
        expression_text: str,
        x_minimum: float,
        x_maximum: float,
        point_count: int,
) -> tuple[tuple[tuple[float, float], ...], str | None]:
    """Generate finite curve points from one restricted symbolic expression.

    The expression language is the same restricted language used by the
    VeraGrid symbolic parser. Only ``x`` is available as a variable, ``pi``
    and ``e`` are available as constants, and the returned samples are
    detached numeric values suitable for table storage.

    :param expression_text: Mathematical expression defining ``f(x)``.
    :param x_minimum: First x coordinate to sample.
    :param x_maximum: Last x coordinate to sample.
    :param point_count: Number of evenly spaced coordinates, including limits.
    :return: Generated ``(x, y)`` points and an optional validation message.
    """
    normalized_expression: str = expression_text.strip()
    normalized_x_minimum: float = float(x_minimum)
    normalized_x_maximum: float = float(x_maximum)
    generated_points: tuple[tuple[float, float], ...] = tuple()

    # Validate the complete sampling contract before parsing or allocating the
    # result so invalid user input never replaces the current lookup table.
    if len(normalized_expression) == 0:
        validation_error: str | None = "Enter an expression for f(x)"
    elif not math.isfinite(normalized_x_minimum) or not math.isfinite(normalized_x_maximum):
        validation_error = "The x limits must be finite"
    elif normalized_x_maximum <= normalized_x_minimum:
        validation_error = "The maximum x value must be greater than the minimum"
    elif point_count < 2:
        validation_error = "At least two generated points are required"
    elif point_count > 10000:
        validation_error = "No more than 10000 generated points are allowed"
    else:
        validation_error = None

    if validation_error is None:
        x_variable: Var = Var("x")
        symbol_namespace: dict[str, Expr | float] = dict()
        symbol_namespace["x"] = x_variable
        symbol_namespace["pi"] = math.pi
        symbol_namespace["e"] = math.e
        try:
            parsed_expression: Expr | Comparison | None = string_to_symbolic(
                normalized_expression,
                symbol_namespace,
            )
        except (SyntaxError, ValueError) as parser_error:
            validation_error = f"Invalid f(x) expression: {parser_error}"
            parsed_expression = None
        else:
            if isinstance(parsed_expression, Expr):
                pass
            else:
                validation_error = "f(x) must be a numeric expression"
    else:
        parsed_expression = None

    if validation_error is None and isinstance(parsed_expression, Expr):
        # The output size is known from the requested sample count. Allocate
        # both axes once and fill y explicitly because symbolic expressions are
        # scalar evaluators rather than NumPy-vectorized callables.
        x_values: np.ndarray = np.linspace(
            normalized_x_minimum,
            normalized_x_maximum,
            num=point_count,
            dtype=float,
        )
        y_values: np.ndarray = np.empty(point_count, dtype=float)
        point_index: int
        for point_index in range(point_count):
            x_value: float = float(x_values[point_index])
            try:
                y_value: float = float(parsed_expression.eval(x=x_value))
            except (ArithmeticError, TypeError, ValueError) as evaluation_error:
                validation_error = (
                    f"f(x) cannot be evaluated at x={x_value:g}: "
                    f"{evaluation_error}"
                )
            else:
                if math.isfinite(y_value):
                    y_values[point_index] = y_value
                else:
                    validation_error = (
                        f"f(x) must produce a finite value at x={x_value:g}"
                    )

            if validation_error is None:
                pass
            else:
                break

        if validation_error is None:
            mutable_points: list[tuple[float, float]] = list()
            for point_index in range(point_count):
                mutable_points.append((
                    float(x_values[point_index]),
                    float(y_values[point_index]),
                ))
            generated_points = tuple(mutable_points)
        else:
            pass
    else:
        pass

    return generated_points, validation_error


def build_sorted_axis_indexes(axis_values: Sequence[float]) -> list[int]:
    """Return the stable ascending index order for one numeric axis.

    The returned indexes allow an editor to reorder an axis and its dependent
    samples together without losing their association.

    :param axis_values: Numeric axis values in their current order.
    :return: Stable ascending indexes into ``axis_values``.
    """
    values_array: np.ndarray = np.asarray(axis_values, dtype=float)
    sorted_indexes_array: np.ndarray = np.argsort(values_array, kind="stable")
    result: list[int] = sorted_indexes_array.astype(int).tolist()
    return result


def normalize_curve_points(
        points: Sequence[Sequence[float]],
) -> tuple[tuple[float, float], ...]:
    """Copy curve points into one finite, immutable numeric representation.

    :param points: Rows containing exactly one x and one y coordinate.
    :return: Normalized ``(x, y)`` rows.
    :raises ValueError: If a row has the wrong width or a non-finite value.
    """
    normalized_points: list[tuple[float, float]] = list()
    row_index: int
    for row_index in range(len(points)):
        point: Sequence[float] = points[row_index]
        if len(point) == 2:
            x_value: float = float(point[0])
            y_value: float = float(point[1])
        else:
            raise ValueError(
                f"Curve row {row_index + 1} must contain exactly two values"
            )
        if math.isfinite(x_value) and math.isfinite(y_value):
            normalized_points.append((x_value, y_value))
        else:
            raise ValueError(
                f"Curve row {row_index + 1} must contain finite values"
            )
    return tuple(normalized_points)


def normalize_lookup_matrix(
        x_values: Sequence[float],
        y_values: Sequence[float],
        z_values: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[tuple[float, ...], ...]]:
    """Copy lookup-matrix axes and samples into finite immutable tuples.

    :param x_values: Horizontal-axis coordinates.
    :param y_values: Vertical-axis coordinates.
    :param z_values: Row-major samples indexed as ``[y][x]``.
    :return: Normalized ``(x_values, y_values, z_values)``.
    :raises ValueError: If dimensions disagree or a value is not finite.
    """
    normalized_x: list[float] = list()
    normalized_y: list[float] = list()
    normalized_z: list[tuple[float, ...]] = list()
    x_index: int
    y_index: int
    for x_index in range(len(x_values)):
        x_value: float = float(x_values[x_index])
        if math.isfinite(x_value):
            normalized_x.append(x_value)
        else:
            raise ValueError(f"Lookup-matrix x value {x_index + 1} must be finite")
    for y_index in range(len(y_values)):
        y_value: float = float(y_values[y_index])
        if math.isfinite(y_value):
            normalized_y.append(y_value)
        else:
            raise ValueError(f"Lookup-matrix y value {y_index + 1} must be finite")

    if len(z_values) == len(normalized_y):
        pass
    else:
        raise ValueError("Lookup-matrix row count must match the y-axis size")

    for y_index in range(len(z_values)):
        source_row: Sequence[float] = z_values[y_index]
        if len(source_row) == len(normalized_x):
            pass
        else:
            raise ValueError(
                f"Lookup-matrix row {y_index + 1} must match the x-axis size"
            )
        normalized_row: list[float] = list()
        for x_index in range(len(source_row)):
            z_value: float = float(source_row[x_index])
            if math.isfinite(z_value):
                normalized_row.append(z_value)
            else:
                raise ValueError(
                    f"Lookup-matrix value ({y_index + 1}, {x_index + 1}) must be finite"
                )
        normalized_z.append(tuple(normalized_row))

    return tuple(normalized_x), tuple(normalized_y), tuple(normalized_z)


def validate_strictly_increasing_axis(values: Sequence[float], axis_name: str) -> str | None:
    """Return an error when one numeric axis is not strictly increasing.

    :param values: Axis coordinates in display order.
    :param axis_name: User-facing axis name included in validation feedback.
    :return: Validation message or ``None`` when the axis is valid.
    """
    result: str | None = None
    point_index: int
    for point_index in range(len(values) - 1):
        if float(values[point_index + 1]) > float(values[point_index]):
            pass
        elif result is None:
            result = f"{axis_name} values must be strictly increasing"
        else:
            pass
    return result


class CurveTableDraft:
    """Detached editable snapshot of one two-column numeric curve."""

    __slots__ = ("_points", "_original_points")

    def __init__(self, points: Sequence[Sequence[float]]) -> None:
        """Capture the accepted curve without retaining mutable input objects.

        :param points: Initial two-column point sequence.
        :return: None.
        """
        normalized_points: tuple[tuple[float, float], ...] = normalize_curve_points(points)
        self._points: tuple[tuple[float, float], ...] = normalized_points
        self._original_points: tuple[tuple[float, float], ...] = normalized_points

    def get_points(self) -> tuple[tuple[float, float], ...]:
        """Return the current immutable point snapshot.

        :return: Current ``(x, y)`` points.
        """
        return self._points

    def set_points(self, points: Sequence[Sequence[float]]) -> None:
        """Replace the draft with normalized numeric points.

        :param points: Replacement two-column point sequence.
        :return: None.
        """
        self._points = normalize_curve_points(points)

    def set_point(self, row_index: int, x_value: float, y_value: float) -> bool:
        """Replace one row while keeping all other rows immutable.

        :param row_index: Zero-based row to replace.
        :param x_value: Replacement x coordinate.
        :param y_value: Replacement y coordinate.
        :return: Whether the row index and values were accepted.
        """
        if 0 <= row_index < len(self._points):
            replacement: tuple[float, float] = normalize_curve_points(
                ((x_value, y_value),)
            )[0]
            mutable_points: list[tuple[float, float]] = list(self._points)
            mutable_points[row_index] = replacement
            self._points = tuple(mutable_points)
            result: bool = True
        else:
            result = False
        return result

    def insert_point(self, row_index: int, x_value: float, y_value: float) -> bool:
        """Insert one row at a valid boundary in the current sequence.

        :param row_index: Zero-based insertion position.
        :param x_value: New x coordinate.
        :param y_value: New y coordinate.
        :return: Whether the insertion position and values were accepted.
        """
        if 0 <= row_index <= len(self._points):
            new_point: tuple[float, float] = normalize_curve_points(
                ((x_value, y_value),)
            )[0]
            mutable_points: list[tuple[float, float]] = list(self._points)
            mutable_points.insert(row_index, new_point)
            self._points = tuple(mutable_points)
            result: bool = True
        else:
            result = False
        return result

    def remove_rows(self, row_indexes: Sequence[int]) -> None:
        """Remove valid row indexes without depending on their input order.

        :param row_indexes: Zero-based rows selected for removal.
        :return: None.
        """
        removed_indexes: set[int] = set()
        row_index: int
        for row_index in row_indexes:
            if 0 <= row_index < len(self._points):
                removed_indexes.add(row_index)
            else:
                pass
        retained_points: list[tuple[float, float]] = list()
        point: tuple[float, float]
        for row_index, point in enumerate(self._points):
            if row_index in removed_indexes:
                pass
            else:
                retained_points.append(point)
        self._points = tuple(retained_points)

    def sort_by_x(self) -> None:
        """Sort rows stably by x while retaining each x/y association.

        :return: None.
        """
        x_values: tuple[float, ...] = tuple(point[0] for point in self._points)
        sorted_indexes: list[int] = build_sorted_axis_indexes(x_values)
        sorted_points: list[tuple[float, float]] = list()
        row_index: int
        for row_index in sorted_indexes:
            sorted_points.append(self._points[row_index])
        self._points = tuple(sorted_points)

    def validate(self,
                 minimum_point_count: int = 2,
                 strictly_increasing_x: bool = True,
                 strictly_monotonic_y: bool = False) -> str | None:
        """Validate curve cardinality and axis ordering requirements.

        :param minimum_point_count: Minimum number of complete rows.
        :param strictly_increasing_x: Whether x must increase between rows.
        :param strictly_monotonic_y: Whether y must increase or decrease strictly.
        :return: Validation message or ``None`` when valid.
        """
        if len(self._points) >= minimum_point_count:
            result: str | None = None
        else:
            result = f"The table requires at least {minimum_point_count} points"

        if result is None and strictly_increasing_x:
            x_values: tuple[float, ...] = tuple(point[0] for point in self._points)
            result = validate_strictly_increasing_axis(x_values, "X")
        else:
            pass

        if result is None and strictly_monotonic_y:
            y_values: tuple[float, ...] = tuple(point[1] for point in self._points)
            increasing: bool = True
            decreasing: bool = True
            point_index: int
            for point_index in range(len(y_values) - 1):
                if y_values[point_index + 1] > y_values[point_index]:
                    decreasing = False
                elif y_values[point_index + 1] < y_values[point_index]:
                    increasing = False
                else:
                    increasing = False
                    decreasing = False
            if increasing or decreasing:
                pass
            else:
                result = "Y values must be strictly monotonic"
        else:
            pass
        return result

    def has_changes(self) -> bool:
        """Return whether the current points differ from the accepted baseline.

        :return: Whether the draft contains unapplied changes.
        """
        return self._points != self._original_points

    def accept(self) -> None:
        """Promote the current points to the clean baseline.

        :return: None.
        """
        self._original_points = self._points


class LookupMatrixDraft:
    """Detached editable snapshot of one rectangular two-dimensional lookup."""

    __slots__ = (
        "_x_values",
        "_y_values",
        "_z_values",
        "_original_x_values",
        "_original_y_values",
        "_original_z_values",
    )

    def __init__(self,
                 x_values: Sequence[float],
                 y_values: Sequence[float],
                 z_values: Sequence[Sequence[float]]) -> None:
        """Capture one rectangular matrix without retaining mutable inputs.

        :param x_values: Initial horizontal-axis coordinates.
        :param y_values: Initial vertical-axis coordinates.
        :param z_values: Initial row-major samples.
        :return: None.
        """
        normalized_values: tuple[
            tuple[float, ...],
            tuple[float, ...],
            tuple[tuple[float, ...], ...],
        ] = normalize_lookup_matrix(x_values, y_values, z_values)
        self._x_values: tuple[float, ...] = normalized_values[0]
        self._y_values: tuple[float, ...] = normalized_values[1]
        self._z_values: tuple[tuple[float, ...], ...] = normalized_values[2]
        self._original_x_values: tuple[float, ...] = self._x_values
        self._original_y_values: tuple[float, ...] = self._y_values
        self._original_z_values: tuple[tuple[float, ...], ...] = self._z_values

    def get_values(
            self,
    ) -> tuple[tuple[float, ...], tuple[float, ...], tuple[tuple[float, ...], ...]]:
        """Return immutable axes and row-major samples.

        :return: Current ``(x_values, y_values, z_values)``.
        """
        return self._x_values, self._y_values, self._z_values

    def set_values(self,
                   x_values: Sequence[float],
                   y_values: Sequence[float],
                   z_values: Sequence[Sequence[float]]) -> None:
        """Replace axes and samples as one dimensionally consistent operation.

        :param x_values: Replacement horizontal-axis coordinates.
        :param y_values: Replacement vertical-axis coordinates.
        :param z_values: Replacement row-major samples.
        :return: None.
        """
        normalized_values: tuple[
            tuple[float, ...],
            tuple[float, ...],
            tuple[tuple[float, ...], ...],
        ] = normalize_lookup_matrix(x_values, y_values, z_values)
        self._x_values = normalized_values[0]
        self._y_values = normalized_values[1]
        self._z_values = normalized_values[2]

    def validate(self, minimum_axis_size: int = 2) -> str | None:
        """Validate minimum dimensions and strict axis ordering.

        :param minimum_axis_size: Minimum coordinate count on each axis.
        :return: Validation message or ``None`` when valid.
        """
        if len(self._x_values) >= minimum_axis_size:
            result: str | None = None
        else:
            result = f"The X axis requires at least {minimum_axis_size} values"
        if result is None and len(self._y_values) < minimum_axis_size:
            result = f"The Y axis requires at least {minimum_axis_size} values"
        else:
            pass
        if result is None:
            result = validate_strictly_increasing_axis(self._x_values, "X")
        else:
            pass
        if result is None:
            result = validate_strictly_increasing_axis(self._y_values, "Y")
        else:
            pass
        return result

    def has_changes(self) -> bool:
        """Return whether axes or samples differ from their accepted baseline.

        :return: Whether the draft contains unapplied changes.
        """
        return (
            self._x_values != self._original_x_values
            or self._y_values != self._original_y_values
            or self._z_values != self._original_z_values
        )

    def accept(self) -> None:
        """Promote the current matrix to the clean baseline.

        :return: None.
        """
        self._original_x_values = self._x_values
        self._original_y_values = self._y_values
        self._original_z_values = self._z_values
