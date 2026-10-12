# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Own bounded CMake process trees used by host-native FMI tests."""

from __future__ import annotations

import ctypes
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import BinaryIO


class FmiThreeCmakeCommandResult:
    """Store one bounded CMake command outcome.

    :param return_code: Native process return code after complete teardown.
    :param diagnostic: Bounded tail of the command log.
    :param timed_out: Whether the command exceeded its execution limit.
    """

    __slots__ = ("return_code", "diagnostic", "timed_out")

    def __init__(
        self,
        return_code: int,
        diagnostic: str,
        timed_out: bool,
    ) -> None:
        """Store one completed and reaped command result.

        :param return_code: Native process return code after complete teardown.
        :param diagnostic: Bounded tail of the command log.
        :param timed_out: Whether the command exceeded its execution limit.
        :return: None.
        """

        self.return_code: int = return_code
        self.diagnostic: str = diagnostic
        self.timed_out: bool = timed_out


def _read_bounded_command_log(log_path: Path, maximum_bytes: int) -> str:
    """Read only the bounded tail of one CMake command log.

    :param log_path: Completed command log owned by the pytest directory.
    :param maximum_bytes: Positive maximum number of trailing bytes to read.
    :return: Decoded diagnostic without leading or trailing whitespace.
    """

    log_size: int = log_path.stat().st_size
    read_offset: int = max(0, log_size - maximum_bytes)
    with log_path.open("rb") as log_stream:
        log_stream.seek(read_offset)
        diagnostic_bytes: bytes = log_stream.read(maximum_bytes)
    return diagnostic_bytes.decode("utf-8", errors="replace").strip()


def _resolve_windows_taskkill_executable() -> Path:
    """Resolve the Windows tree-termination executable without PATH lookup.

    :return: Absolute ``taskkill.exe`` path from the Windows system directory.
    :raises RuntimeError: If Windows cannot report its system directory.
    """

    system_directory_buffer_size: int = 32768
    system_directory_buffer: ctypes.Array[ctypes.c_wchar] = (
        ctypes.create_unicode_buffer(system_directory_buffer_size)
    )
    system_directory_length: int = int(
        ctypes.windll.kernel32.GetSystemDirectoryW(
            system_directory_buffer,
            system_directory_buffer_size,
        )
    )
    if 0 < system_directory_length < system_directory_buffer_size:
        taskkill_path: Path = (
            Path(system_directory_buffer.value).resolve(strict=True) / "taskkill.exe"
        )
    else:
        raise RuntimeError("Windows did not return a bounded system directory")
    if taskkill_path.is_file():
        return taskkill_path
    else:
        raise RuntimeError(f"Windows taskkill executable is missing: {taskkill_path}")


def _terminate_windows_process_tree(
    process: subprocess.Popen[bytes],
    termination_grace_seconds: float,
) -> None:
    """Terminate and reap one Windows process tree by exact root PID.

    :param process: Running root process created in a new process group.
    :param termination_grace_seconds: Positive bound for tree termination.
    :return: None.
    :raises RuntimeError: If Windows cannot prove tree termination.
    """

    termination_deadline: float = time.monotonic() + termination_grace_seconds
    taskkill_path: Path = _resolve_windows_taskkill_executable()
    try:
        taskkill_result: subprocess.CompletedProcess[bytes] = subprocess.run(
            (str(taskkill_path), "/PID", str(process.pid), "/T", "/F"),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_remaining_termination_seconds(termination_deadline),
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Windows process-tree termination timed out") from error
    if taskkill_result.returncode == 0:
        pass
    else:
        raise RuntimeError(
            f"Windows process-tree termination failed with code "
            f"{taskkill_result.returncode}"
        )
    process.poll()
    if process.returncode is not None:
        pass
    else:
        try:
            process.wait(timeout=_remaining_termination_seconds(termination_deadline))
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                "Windows root process remained alive after taskkill"
            ) from error


def _posix_process_group_exists(process_group_id: int) -> bool:
    """Return whether a POSIX process group still has a live member.

    :param process_group_id: Process group created for the CMake command.
    :return: ``True`` while the operating system still reports the group.
    """

    try:
        os.killpg(process_group_id, 0)
        group_exists: bool = True
    except ProcessLookupError:
        group_exists = False
    except PermissionError:
        # A zombie-only Darwin group can briefly deny signal-zero inspection.
        # Denial cannot prove absence, so retain the existing bounded polling.
        group_exists = True
    return group_exists


def _send_posix_process_group_signal(
    process_group_id: int,
    signal_number: int,
) -> None:
    """Signal a POSIX process group that may finish concurrently.

    :param process_group_id: Process group created for the CMake command.
    :param signal_number: Operating-system signal selected by the caller.
    :return: None.
    """

    try:
        os.killpg(process_group_id, signal_number)
    except ProcessLookupError:
        # The group completing between inspection and signaling is a successful
        # teardown state; later group verification still proves that outcome.
        pass


def _remaining_termination_seconds(termination_deadline: float) -> float:
    """Return the positive time remaining in one teardown budget.

    :param termination_deadline: Monotonic deadline shared by teardown phases.
    :return: Positive number of seconds available to the next bounded wait.
    :raises RuntimeError: If the complete teardown budget has expired.
    """

    remaining_seconds: float = termination_deadline - time.monotonic()
    if remaining_seconds > 0.0:
        return remaining_seconds
    else:
        raise RuntimeError("The CMake process-tree termination budget expired")


def _wait_for_posix_process_group_exit(
    process: subprocess.Popen[bytes],
    process_group_id: int,
    termination_deadline: float,
) -> bool:
    """Wait within a finite bound for one POSIX process group to disappear.

    :param process: Root process reaped while the group terminates.
    :param process_group_id: Process group created for the CMake command.
    :param termination_deadline: Monotonic deadline shared by teardown phases.
    :return: ``True`` only when no group member remains.
    """

    process.poll()
    group_exists: bool = _posix_process_group_exists(process_group_id)
    while group_exists and time.monotonic() < termination_deadline:
        time.sleep(0.01)
        process.poll()
        group_exists = _posix_process_group_exists(process_group_id)
    return not group_exists


def _terminate_posix_process_group(
    process: subprocess.Popen[bytes],
    termination_grace_seconds: float,
) -> None:
    """Terminate and reap one POSIX process group with TERM then KILL.

    :param process: Running root process that owns a new session and group.
    :param termination_grace_seconds: Positive total bound for all teardown phases.
    :return: None.
    :raises RuntimeError: If any process-group member survives both phases.
    """

    termination_start: float = time.monotonic()
    termination_deadline: float = termination_start + termination_grace_seconds
    term_deadline: float = termination_start + termination_grace_seconds / 2.0
    process_group_id: int = process.pid
    if _posix_process_group_exists(process_group_id):
        _send_posix_process_group_signal(process_group_id, signal.SIGTERM)
    else:
        pass
    terminated_after_term: bool = _wait_for_posix_process_group_exit(
        process,
        process_group_id,
        term_deadline,
    )
    if terminated_after_term:
        pass
    else:
        _send_posix_process_group_signal(process_group_id, signal.SIGKILL)
    if _wait_for_posix_process_group_exit(
        process,
        process_group_id,
        termination_deadline,
    ):
        pass
    else:
        raise RuntimeError("POSIX CMake process group survived SIGKILL")
    process.poll()
    if process.returncode is not None:
        pass
    else:
        try:
            process.wait(timeout=_remaining_termination_seconds(termination_deadline))
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("POSIX root process was not reaped") from error


def run_fmi_three_cmake_command(
    command: tuple[str, ...],
    log_path: Path,
    command_timeout_seconds: float,
    termination_grace_seconds: float,
) -> FmiThreeCmakeCommandResult:
    """Run one CMake command with bounded output and process-tree ownership.

    :param command: Exact executable and argument tuple without shell expansion.
    :param log_path: Pytest-owned file receiving standard output and error.
    :param command_timeout_seconds: Positive execution-time limit.
    :param termination_grace_seconds: Positive process-tree teardown limit.
    :return: Completed result after the root and timeout descendants are reaped.
    :raises ValueError: If the command or either time limit is invalid.
    :raises RuntimeError: If a timed-out process tree cannot be terminated.
    """

    if len(command) > 0 and len(command[0]) > 0:
        pass
    else:
        raise ValueError("The CMake command must include an executable")
    if math.isfinite(command_timeout_seconds) and command_timeout_seconds > 0.0:
        pass
    else:
        raise ValueError("The CMake command timeout must be finite and positive")
    if (
        math.isfinite(termination_grace_seconds)
        and termination_grace_seconds > 0.0
    ):
        pass
    else:
        raise ValueError("The CMake termination grace must be finite and positive")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        creation_flags: int = subprocess.CREATE_NEW_PROCESS_GROUP
        start_new_session: bool = False
    else:
        creation_flags = 0
        start_new_session = True
    timed_out: bool = False
    with log_path.open("wb") as log_stream:
        command_log_stream: BinaryIO = log_stream
        process: subprocess.Popen[bytes] = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=command_log_stream,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
            start_new_session=start_new_session,
        )
        try:
            return_code: int = process.wait(timeout=command_timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            if sys.platform.startswith("win"):
                _terminate_windows_process_tree(
                    process=process,
                    termination_grace_seconds=termination_grace_seconds,
                )
            else:
                _terminate_posix_process_group(
                    process=process,
                    termination_grace_seconds=termination_grace_seconds,
                )
            if process.returncode is not None:
                return_code = process.returncode
            else:
                raise RuntimeError("The CMake root process has no terminal code")
    diagnostic: str = _read_bounded_command_log(
        log_path=log_path,
        maximum_bytes=4000,
    )
    return FmiThreeCmakeCommandResult(
        return_code=return_code,
        diagnostic=diagnostic,
        timed_out=timed_out,
    )
