# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import pdb
from typing import List, Any, Dict

import numpy as np

from GridCalEngine.Utils.Symbolic.symbolic import Const


class Event:
    def __init__(self,
                 prop: Any | None = None,
                 time_step: int = 0.0,
                 value: float = 0.0):
        self._prop = prop
        self._time_step = time_step
        self._value = value

    @property
    def prop(self):
        return self._prop

    @property
    def value(self):
        return self._value

    @property
    def time_step(self):
        return self._time_step



class Events:
    def __init__(self, events: List[Event]):
        self._events = events
        self._n_events = len(events)

    def sort_by_time_step(self):
        self._events.sort(key=lambda e: e.time_step)

    def build_triplets_list(self):
        rows = np.ndarray(self._n_events)
        cols = np.ndarray(self._n_events, dtype=object)
        values = np.ndarray(self._n_events)
        for i, event in enumerate(self._events):
            rows[i] = event.time_step
            cols[i] = event.prop
            values[i] = event.value

        return rows, cols, values


    @property
    def events(self):
        return self._events
