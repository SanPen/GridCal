# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from typing import List, Any, Dict
from VeraGridEngine.Utils.Symbolic.symbolic import Var
import numpy as np


class RmsEvent:
    def __init__(self,
                 device_type: str,
                 device_name: str,
                 variable: str,
                 time_step: int = 0.0,
                 value: float = 0.0):
        self._device_type = device_type
        self._device_name = device_name
        self._variable = variable
        self._value = value
        self._time_step = time_step


    @property
    def device_type(self):
        return self._device_type

    @property
    def device_name(self):
        return self._device_name

    @property
    def variable(self):
        return self._variable

    @property
    def value(self):
        return self._value

    @property
    def time_step(self):
        return self._time_step


class RmsEvents:
    def __init__(self, events: List[RmsEvent]):
        self._events = events
        self._n_events = len(events)

    def sort_by_time_step(self):
        self._events.sort(key=lambda e: e.time_step)

    def build_triplets_list(self):
        rows = np.zeros(self._n_events)
        cols = np.zeros(self._n_events, dtype=object)
        values = np.zeros(self._n_events)
        for i, event in enumerate(self._events):
            rows[i] = event.time_step
            cols[i] = event.variable
            values[i] = event.value

        return rows, cols, values

    @property
    def events(self):
        return self._events
