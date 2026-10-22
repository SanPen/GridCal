# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Canonical JSON serialisation used to fingerprint interchange artifacts.

The canonical form is ``json.dumps`` with sorted keys, compact separators,
ASCII escaping and no NaN, encoded as UTF-8 without BOM or trailing newline.
Only dictionaries with string keys, lists, strings and integers are accepted.
"""

from __future__ import annotations

import json
from typing import List, Tuple


def canonical_json_bytes(payload: object) -> bytes:
    """
    Serialise a payload to canonical JSON bytes.

    The payload is validated iteratively before serialisation: it may contain
    only ``dict`` with ``str`` keys, ``list``, ``str`` and ``int`` (``bool`` is
    rejected), and no container may be nested deeper than 8 levels, the
    top-level container being depth 1.

    :param payload: Value to serialise.
    :return: Canonical UTF-8 JSON bytes.
    :raises ValueError: When the payload contains an unsupported type, a
        non-string key or nesting deeper than 8 levels.
    """
    maximum_depth: int = 8

    # Iterative type and depth validation (no recursion).
    pending: List[Tuple[object, int]] = list()
    pending.append((payload, 1))
    while len(pending) > 0:
        node: object
        depth: int
        node, depth = pending.pop()
        node_type: type = type(node)
        if node_type is dict:
            if depth > maximum_depth:
                raise ValueError("Canonical JSON nesting deeper than " + str(maximum_depth) + " levels")
            else:
                pass
            key: object
            value: object
            for key, value in node.items():
                if type(key) is not str:
                    raise ValueError("Canonical JSON keys must be str")
                else:
                    pending.append((value, depth + 1))
        elif node_type is list:
            if depth > maximum_depth:
                raise ValueError("Canonical JSON nesting deeper than " + str(maximum_depth) + " levels")
            else:
                pass
            item: object
            for item in node:
                pending.append((item, depth + 1))
        elif node_type is str or node_type is int:
            pass
        else:
            raise ValueError("Canonical JSON does not accept values of type " + node_type.__name__)

    # Serialisation with the canonical options.
    try:
        text: str = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except RecursionError as error:
        raise ValueError("Canonical JSON nesting exceeds the interpreter recursion limit") from error
    return text.encode("utf-8")
