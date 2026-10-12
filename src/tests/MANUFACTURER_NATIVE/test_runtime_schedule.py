# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import math
import sys
from typing import cast, Tuple

import numpy as np
import pytest

from VeraGridEngine.enumerations import (
    IeeeCigreDllPlatform,
    NativeModelInterface,
)
from VeraGridEngine.IO.manufacturer_native.runtime_host import ManufacturerNativeWorkerHost
from VeraGridEngine.IO.manufacturer_native.runtime_session import (
    ManufacturerNativeRuntimeSession,
    _RuntimeBinding,
    _RuntimeWorkerGroup,
    _scheduled_sample_time,
)
from VeraGridEngine.Utils.procedural_logic import ProceduralProblem


class _RecordingHost:
    """Record accepted native sample calls without loading manufacturer code."""

    __slots__ = ("sample_times",)

    def __init__(self) -> None:
        """Create an empty call record.

        :return: None.
        """
        self.sample_times: list[float] = list()

    def sample_batch(
            self,
            sample_time: float,
            samples: Tuple[Tuple[str, Tuple[int | float, ...]], ...],
    ) -> Tuple[Tuple[str, Tuple[int | float, ...]], ...]:
        """Record one accepted boundary and return empty output vectors.

        :param sample_time: Accepted boundary passed to manufacturer code.
        :param samples: Ordered instance identifiers and accepted inputs.
        :return: Matching identifiers with empty outputs.
        """
        self.sample_times.append(sample_time)
        result: list[Tuple[str, Tuple[int | float, ...]]] = list()
        instance_id: str
        inputs: Tuple[int | float, ...]
        for instance_id, inputs in samples:
            result.append((instance_id, tuple()))
        return tuple(result)


class _EmptyProblem:
    """Supply the empty constant vector required by an input-free binding."""

    __slots__ = ()

    def get_parameters_values(self) -> list[object]:
        """Return no constant parameters.

        :return: Empty constant parameter list.
        """
        return list()


def _runtime_session(sample_time: float) -> Tuple[
        ManufacturerNativeRuntimeSession, _RuntimeBinding, _RecordingHost,
]:
    """Build the smallest real session graph needed by scheduling tests.

    :param sample_time: Fixed model period in seconds.
    :return: Runtime session, its sole binding and the recording host.
    """
    recording_host: _RecordingHost = _RecordingHost()
    worker_host: ManufacturerNativeWorkerHost = cast(ManufacturerNativeWorkerHost, recording_host)
    group: _RuntimeWorkerGroup = _RuntimeWorkerGroup(
        "0" * 64,
        IeeeCigreDllPlatform.WINDOWS_X64,
        NativeModelInterface.IEEE_CIGRE_V1_1,
        worker_host,
    )
    binding: _RuntimeBinding = object.__new__(_RuntimeBinding)
    binding.instance_id = "controller-0"
    binding.input_sources = tuple()
    binding.output_indices = tuple()
    binding.sample_time = sample_time
    binding.next_sample_index = 1
    group.bindings.append(binding)

    session: ManufacturerNativeRuntimeSession = object.__new__(ManufacturerNativeRuntimeSession)
    session._bindings = [binding]
    session._groups = [group]
    session._initialized = True
    session._closed = False
    session._problem = cast(ProceduralProblem, _EmptyProblem())
    return session, binding, recording_host


def _move_forward(value: float, steps: int) -> float:
    """Move a finite value forward by an exact count of binary64 values.

    :param value: Starting binary64 value.
    :param steps: Number of representable forward steps.
    :return: Advanced binary64 value.
    """
    result: float = value
    step_index: int
    for step_index in range(steps):
        result = math.nextafter(result, math.inf)
    return result


@pytest.mark.parametrize("sample_time", (5e-6, 1e-5))
def test_fast_converter_boundaries_are_selected_exactly(sample_time: float) -> None:
    """Five and ten microsecond boundaries must not be rounded or skipped.

    :param sample_time: Real fast-converter period under test.
    :return: None.
    """
    session: ManufacturerNativeRuntimeSession
    binding: _RuntimeBinding
    host: _RecordingHost
    session, binding, host = _runtime_session(sample_time)

    assert session.get_next_sample_time(0.0, sample_time / 2.0) is None
    assert session.get_next_sample_time(0.0, sample_time) == sample_time
    assert binding.next_sample_index == 1
    assert host.sample_times == list()


def test_smallest_positive_boundary_is_not_suppressed() -> None:
    """The first positive binary64 period must remain a solver boundary."""
    sample_time: float = math.nextafter(0.0, 1.0)
    session: ManufacturerNativeRuntimeSession
    binding: _RuntimeBinding
    host: _RecordingHost
    session, binding, host = _runtime_session(sample_time)

    assert session.get_next_sample_time(0.0, sample_time) == sample_time
    session.commit_boundary(0.0, np.zeros(0), np.zeros(0))

    assert binding.next_sample_index == 1
    assert host.sample_times == list()


def test_nonadvancing_large_index_fails_explicitly() -> None:
    """A rounded indexed boundary must fail instead of being silently skipped."""
    session: ManufacturerNativeRuntimeSession
    binding: _RuntimeBinding
    host: _RecordingHost
    session, binding, host = _runtime_session(1e-5)
    binding.next_sample_index = 2 ** 53
    previous_time: float = _scheduled_sample_time(binding.next_sample_index, binding.sample_time)

    with pytest.raises(RuntimeError, match="did not advance"):
        session.get_next_sample_time(previous_time, math.inf)

    assert host.sample_times == list()


def test_index_conversion_and_schedule_overflow_fail_explicitly() -> None:
    """Binary64 conversion and multiplication overflow must be distinguished."""
    with pytest.raises(OverflowError, match="index exceeds binary64"):
        _scheduled_sample_time(10 ** 400, 1.0)

    with pytest.raises(OverflowError, match="schedule overflowed"):
        _scheduled_sample_time(2, sys.float_info.max)


def test_exact_boundary_commits_once() -> None:
    """An exact accepted boundary must call the manufacturer once."""
    sample_time: float = 5e-6
    session: ManufacturerNativeRuntimeSession
    binding: _RuntimeBinding
    host: _RecordingHost
    session, binding, host = _runtime_session(sample_time)

    session.commit_boundary(sample_time, np.zeros(0), np.zeros(0))

    assert host.sample_times == [sample_time]
    assert binding.next_sample_index == 2


def test_forward_four_ulp_delay_commits_once() -> None:
    """A solver rounding delay of four ULPs remains the same boundary."""
    sample_time: float = 5e-6
    delayed_time: float = _move_forward(sample_time, 4)
    session: ManufacturerNativeRuntimeSession
    binding: _RuntimeBinding
    host: _RecordingHost
    session, binding, host = _runtime_session(sample_time)

    session.commit_boundary(delayed_time, np.zeros(0), np.zeros(0))

    assert host.sample_times == [delayed_time]
    assert binding.next_sample_index == 2


def test_commit_rejects_delay_beyond_four_ulp() -> None:
    """A late solver result beyond the directional allowance must fail."""
    sample_time: float = 5e-6
    delayed_time: float = _move_forward(sample_time, 5)
    session: ManufacturerNativeRuntimeSession
    binding: _RuntimeBinding
    host: _RecordingHost
    session, binding, host = _runtime_session(sample_time)

    with pytest.raises(RuntimeError, match="passed an IEEE/CIGRE forced sample boundary"):
        session.commit_boundary(delayed_time, np.zeros(0), np.zeros(0))

    assert host.sample_times == list()
    assert binding.next_sample_index == 1


def test_commit_never_calls_before_the_boundary() -> None:
    """An earlier accepted solver time must leave vendor state untouched."""
    sample_time: float = 5e-6
    earlier_time: float = math.nextafter(sample_time, 0.0)
    session: ManufacturerNativeRuntimeSession
    binding: _RuntimeBinding
    host: _RecordingHost
    session, binding, host = _runtime_session(sample_time)

    session.commit_boundary(earlier_time, np.zeros(0), np.zeros(0))

    assert host.sample_times == list()
    assert binding.next_sample_index == 1
