# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import ctypes
import hashlib
import math
from multiprocessing import get_context
from multiprocessing.connection import Connection
from multiprocessing.context import BaseContext
from multiprocessing.process import BaseProcess
import os
from pathlib import Path
import shutil
import select
import subprocess
import tempfile
import time
from types import TracebackType
from typing import BinaryIO, Callable
import zipfile

from VeraGridEngine.Devices.Dynamic.manufacturer_native_model import (
    ManufacturerNativeBinarySource,
    ManufacturerNativeBinaryVariant,
)


class NativeWorkerLimits:
    """Finite transport, process and allocation limits for native workers."""

    __slots__ = (
        "maximum_binary_bytes", "maximum_frame_bytes", "response_timeout_seconds",
        "graceful_join_timeout_seconds", "terminate_join_timeout_seconds",
        "kill_join_timeout_seconds", "maximum_workers", "maximum_instances_per_session",
        "maximum_instances_per_worker", "maximum_scalar_slots_per_instance",
        "maximum_state_scalars_per_instance", "maximum_instance_buffer_bytes",
        "maximum_worker_buffer_bytes", "maximum_session_buffer_bytes",
    )

    def __init__(self,
                 maximum_binary_bytes: int = 512 * 1024 * 1024,
                 maximum_frame_bytes: int = 64 * 1024 * 1024,
                 response_timeout_seconds: float = 5.0,
                 graceful_join_timeout_seconds: float = 1.0,
                 terminate_join_timeout_seconds: float = 1.0,
                 kill_join_timeout_seconds: float = 1.0,
                 maximum_workers: int = 64,
                 maximum_instances_per_session: int = 16_384,
                 maximum_instances_per_worker: int = 4_096,
                 maximum_scalar_slots_per_instance: int = 1_048_576,
                 maximum_state_scalars_per_instance: int = 10_000_000,
                 maximum_instance_buffer_bytes: int = 512 * 1024 * 1024,
                 maximum_worker_buffer_bytes: int = 2 * 1024 * 1024 * 1024,
                 maximum_session_buffer_bytes: int = 4 * 1024 * 1024 * 1024) -> None:
        """Validate and store all parent-side limits.

        :param maximum_binary_bytes: Maximum primary library size.
        :param maximum_frame_bytes: Maximum request or response frame size.
        :param response_timeout_seconds: Default worker response deadline.
        :param graceful_join_timeout_seconds: Graceful process join deadline.
        :param terminate_join_timeout_seconds: Terminate escalation deadline.
        :param kill_join_timeout_seconds: Kill escalation deadline.
        :param maximum_workers: Maximum workers per simulation session.
        :param maximum_instances_per_session: Maximum instances per session.
        :param maximum_instances_per_worker: Maximum instances per worker.
        :param maximum_scalar_slots_per_instance: Maximum input/output scalar slots.
        :param maximum_state_scalars_per_instance: Maximum host-owned state scalars.
        :param maximum_instance_buffer_bytes: Maximum buffers per instance.
        :param maximum_worker_buffer_bytes: Maximum buffers per worker.
        :param maximum_session_buffer_bytes: Maximum buffers per session.
        :return: None.
        """
        integer_limits: tuple[int, ...] = (
            maximum_binary_bytes, maximum_frame_bytes, maximum_workers,
            maximum_instances_per_session, maximum_instances_per_worker,
            maximum_scalar_slots_per_instance, maximum_state_scalars_per_instance,
            maximum_instance_buffer_bytes, maximum_worker_buffer_bytes,
            maximum_session_buffer_bytes,
        )
        if any(value <= 0 or value > 0xffffffffffffffff for value in integer_limits):
            raise ValueError("Native worker integer limits must fit positive uint64")
        else:
            pass
        timeout_limits: tuple[float, ...] = (
            response_timeout_seconds, graceful_join_timeout_seconds,
            terminate_join_timeout_seconds, kill_join_timeout_seconds,
        )
        if any(not math.isfinite(value) or value <= 0.0 for value in timeout_limits):
            raise ValueError("Native worker timeouts must be finite and positive")
        else:
            pass
        self.maximum_binary_bytes: int = maximum_binary_bytes
        self.maximum_frame_bytes: int = maximum_frame_bytes
        self.response_timeout_seconds: float = response_timeout_seconds
        self.graceful_join_timeout_seconds: float = graceful_join_timeout_seconds
        self.terminate_join_timeout_seconds: float = terminate_join_timeout_seconds
        self.kill_join_timeout_seconds: float = kill_join_timeout_seconds
        self.maximum_workers: int = maximum_workers
        self.maximum_instances_per_session: int = maximum_instances_per_session
        self.maximum_instances_per_worker: int = maximum_instances_per_worker
        self.maximum_scalar_slots_per_instance: int = maximum_scalar_slots_per_instance
        self.maximum_state_scalars_per_instance: int = maximum_state_scalars_per_instance
        self.maximum_instance_buffer_bytes: int = maximum_instance_buffer_bytes
        self.maximum_worker_buffer_bytes: int = maximum_worker_buffer_bytes
        self.maximum_session_buffer_bytes: int = maximum_session_buffer_bytes


class StagedNativeLibrary:
    """Unique owner of one content-bound private native library snapshot."""

    __slots__ = ("_root", "_parent", "_library_path", "_closed")

    def __init__(self, root: Path, parent: Path, library_path: Path) -> None:
        """Store a verified private snapshot and its cleanup boundary.

        :param root: Exact temporary child owned by this object.
        :param parent: Caller-selected or system temporary parent.
        :param library_path: Verified private primary library path.
        :return: None.
        """
        self._root: Path = root.resolve()
        self._parent: Path = parent.resolve()
        self._library_path: Path = library_path.resolve()
        self._closed: bool = False

    def get_library_path(self) -> Path:
        """Return the verified private primary library.

        :return: Absolute staged library path.
        """
        return self._library_path

    def is_closed(self) -> bool:
        """Return whether cleanup has completed.

        :return: Closed state.
        """
        return self._closed

    def close(self) -> None:
        """Remove only this owner's exact private staging child.

        :return: None.
        """
        if self._closed:
            pass
        else:
            if self._root.parent != self._parent or not self._root.name.startswith("veragrid_native_stage_"):
                raise RuntimeError("Native staging ownership boundary is invalid")
            else:
                pass
            # Windows can retain a short image-section lock after the worker
            # exits. Retry only that transient condition and keep cleanup bounded.
            cleanup_deadline: float = time.monotonic() + 5.0
            removed: bool = False
            while not removed:
                try:
                    shutil.rmtree(self._root)
                    removed = True
                except FileNotFoundError:
                    removed = True
                except PermissionError:
                    if time.monotonic() >= cleanup_deadline:
                        raise
                    else:
                        time.sleep(0.01)
            self._closed = True

    def __enter__(self) -> "StagedNativeLibrary":
        """Return this active staging owner.

        :return: Active staging owner.
        """
        return self

    def __exit__(self,
                 exc_tpe: type[BaseException] | None,
                 exc_value: BaseException | None,
                 traceback_value: TracebackType | None) -> None:
        """Release staging after context exit.

        :param exc_tpe: Raised exception type, when present.
        :param exc_value: Raised exception, when present.
        :param traceback_value: Raised exception traceback, when present.
        :return: None.
        """
        self.close()


def _copy_native_source(source: ManufacturerNativeBinarySource,
                        destination: Path,
                        maximum_bytes: int) -> tuple[int, str]:
    """Copy one source stream into a private exclusive file while hashing it.

    :param source: File or source-archive locator.
    :param destination: Exclusive private destination path.
    :param maximum_bytes: Maximum accepted byte count.
    :return: Exact byte count and lowercase SHA-256.
    """
    source_stream: BinaryIO
    source_archive: zipfile.ZipFile | None = None
    if len(source.file_path) > 0:
        source_stream = open(source.file_path, "rb")
    else:
        source_archive = zipfile.ZipFile(source.archive_path, "r")
        source_stream = source_archive.open(source.archive_member, "r")
    digest = hashlib.sha256()
    byte_count: int = 0
    try:
        with destination.open("xb") as destination_stream:
            reading: bool = True
            while reading:
                chunk: bytes = source_stream.read(1024 * 1024)
                if len(chunk) == 0:
                    reading = False
                else:
                    byte_count += len(chunk)
                    if byte_count > maximum_bytes:
                        raise ValueError("Manufacturer native library exceeds its staging limit")
                    else:
                        digest.update(chunk)
                        destination_stream.write(chunk)
    finally:
        source_stream.close()
        if source_archive is not None:
            source_archive.close()
        else:
            pass
    return byte_count, digest.hexdigest()


def stage_native_library(source: ManufacturerNativeBinarySource,
                         variant: ManufacturerNativeBinaryVariant,
                         limits: NativeWorkerLimits,
                         staging_parent: Path | None = None) -> StagedNativeLibrary:
    """Create a private content-bound snapshot from one manufacturer source.

    :param source: Nonpersistent file or archive member locator.
    :param variant: Expected persistent content identity.
    :param limits: Finite staging and process limits.
    :param staging_parent: Optional caller-owned parent directory.
    :return: Unique staging owner.
    """
    if source.platform != variant.platform:
        raise ValueError("Manufacturer native source and variant platforms differ")
    else:
        pass
    if staging_parent is None:
        parent: Path = Path(tempfile.gettempdir()).resolve()
    else:
        parent = staging_parent.resolve()
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("Native staging parent must be a regular directory")
    else:
        pass
    root: Path = Path(tempfile.mkdtemp(prefix="veragrid_native_stage_", dir=str(parent))).resolve()
    library_path: Path = root / (variant.content_sha256 + variant.extension)
    try:
        byte_count: int
        content_sha256: str
        byte_count, content_sha256 = _copy_native_source(
            source=source,
            destination=library_path,
            maximum_bytes=limits.maximum_binary_bytes,
        )
        if byte_count != variant.byte_size or content_sha256 != variant.content_sha256:
            raise ValueError("Staged manufacturer native bytes do not match the persistent identity")
        else:
            pass
        return StagedNativeLibrary(root=root, parent=parent, library_path=library_path)
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise


class NativeWorkerProcessOwner:
    """Single owner for a spawned native worker process and byte transport."""

    __slots__ = ("_staging", "_limits", "_process", "_connection", "_closed", "_exit_code")

    def __init__(self, staging: StagedNativeLibrary, limits: NativeWorkerLimits) -> None:
        """Prepare process ownership without spawning or loading native code.

        :param staging: Private library snapshot retained through worker death.
        :param limits: Finite transport and shutdown limits.
        :return: None.
        """
        if staging.is_closed():
            raise ValueError("Closed native staging cannot be supervised")
        else:
            pass
        self._staging: StagedNativeLibrary = staging
        self._limits: NativeWorkerLimits = limits
        self._process: BaseProcess | None = None
        self._connection: Connection | None = None
        self._closed: bool = False
        self._exit_code: int | None = None

    def start(self, worker_target: Callable[[Connection, str, int], None]) -> None:
        """Spawn one fixed module-level worker target.

        :param worker_target: Type-explicit child entry receiving connection, library path and frame limit.
        :return: None.
        """
        if self._process is not None or self._closed:
            raise RuntimeError("Native worker owner can start exactly once")
        else:
            pass
        context: BaseContext = get_context("spawn")
        parent_connection: Connection
        child_connection: Connection
        parent_connection, child_connection = context.Pipe(duplex=True)
        process: BaseProcess = context.Process(
            target=worker_target,
            args=(child_connection, str(self._staging.get_library_path()), self._limits.maximum_frame_bytes),
        )
        self._connection = parent_connection
        self._process = process
        try:
            process.start()
        except BaseException:
            child_connection.close()
            if process.pid is not None:
                self.close()
            else:
                parent_connection.close()
                self._connection = None
                self._process = None
            raise
        child_connection.close()

    def request(self, frame: bytes, timeout_seconds: float | None = None) -> bytes:
        """Exchange one bounded frame with the single in-flight worker.

        :param frame: Encoded request frame.
        :param timeout_seconds: Optional finite response deadline override.
        :return: Encoded worker response frame.
        """
        if len(frame) > self._limits.maximum_frame_bytes:
            raise ValueError("Native worker request exceeds the frame limit")
        else:
            pass
        connection: Connection | None = self._connection
        process: BaseProcess | None = self._process
        if connection is None or process is None or self._closed:
            raise RuntimeError("Native worker is unavailable")
        else:
            pass
        timeout: float = self._limits.response_timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        if not math.isfinite(timeout) or timeout <= 0.0 or timeout > 60.0:
            raise ValueError("Native worker request timeout must be finite in (0, 60]")
        else:
            pass
        try:
            connection.send_bytes(frame)
            available: bool = connection.poll(timeout)
            if not available:
                self.close()
                raise TimeoutError("Native worker response timed out")
            else:
                response: bytes = connection.recv_bytes(self._limits.maximum_frame_bytes)
        except (EOFError, OSError) as ex:
            self.close()
            raise RuntimeError("Native worker transport failed") from ex
        return response

    def close(self) -> None:
        """Close transport, prove child death through bounded escalation, then release staging.

        :return: None.
        """
        if self._closed:
            pass
        else:
            connection: Connection | None = self._connection
            if connection is not None:
                try:
                    connection.close()
                except (OSError, ValueError):
                    pass
                self._connection = None
            else:
                pass
            process: BaseProcess | None = self._process
            if process is not None:
                process.join(timeout=self._limits.graceful_join_timeout_seconds)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=self._limits.terminate_join_timeout_seconds)
                else:
                    pass
                if process.is_alive():
                    process.kill()
                    process.join(timeout=self._limits.kill_join_timeout_seconds)
                else:
                    pass
                if process.is_alive() or process.exitcode is None:
                    raise RuntimeError("Native worker death could not be proven; staging retained")
                else:
                    self._exit_code = process.exitcode
                    process.close()
                    self._process = None
            else:
                pass
            self._staging.close()
            self._closed = True


class ExternalNativeWorkerProcessOwner:
    """Own one packaged native worker connected through dedicated one-way pipes."""

    __slots__ = (
        "_staging", "_limits", "_process", "_request_write", "_response_read",
        "_closed", "_exit_code",
    )

    def __init__(self, staging: StagedNativeLibrary, limits: NativeWorkerLimits) -> None:
        """Prepare ownership of one external worker and its staged vendor binary.

        :param staging: Private library snapshot retained through worker death.
        :param limits: Finite transport and shutdown limits.
        :return: None.
        """
        if staging.is_closed():
            raise ValueError("Closed native staging cannot be supervised")
        else:
            pass
        self._staging: StagedNativeLibrary = staging
        self._limits: NativeWorkerLimits = limits
        self._process: subprocess.Popen[bytes] | None = None
        self._request_write: int | None = None
        self._response_read: int | None = None
        self._closed: bool = False
        self._exit_code: int | None = None

    def start(self, executable_path: Path) -> None:
        """Launch one absolute verified worker with exactly two inherited pipe ends.

        :param executable_path: Packaged native worker already verified by its manifest.
        :return: None.
        """
        if self._process is not None or self._closed:
            raise RuntimeError("External native worker owner can start exactly once")
        else:
            pass
        resolved_executable: Path = executable_path.resolve()
        if not resolved_executable.is_file() or resolved_executable.is_symlink():
            raise ValueError("External native worker executable must be a regular file")
        else:
            pass
        if os.name != "nt":
            self._start_posix(resolved_executable=resolved_executable)
            return
        else:
            pass

        # Each direction has one child end and one parent end. The child receives
        # only its request-reader and response-writer through STARTUPINFOEX.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_pipe = kernel32.CreatePipe
        create_pipe.argtypes = [
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p, ctypes.c_uint32,
        ]
        create_pipe.restype = ctypes.c_int
        set_handle_information = kernel32.SetHandleInformation
        set_handle_information.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
        set_handle_information.restype = ctypes.c_int
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [ctypes.c_void_p]
        close_handle.restype = ctypes.c_int
        request_read_value = ctypes.c_void_p()
        request_write_value = ctypes.c_void_p()
        response_read_value = ctypes.c_void_p()
        response_write_value = ctypes.c_void_p()
        first_pipe_ok: int = int(create_pipe(
            ctypes.byref(request_read_value), ctypes.byref(request_write_value), None, 0,
        ))
        if first_pipe_ok == 0:
            raise OSError(ctypes.get_last_error(), "Cannot create external worker pipes")
        else:
            child_request_handle: int = int(request_read_value.value)
            request_write: int = int(request_write_value.value)
        second_pipe_ok: int = int(create_pipe(
            ctypes.byref(response_read_value), ctypes.byref(response_write_value), None, 0,
        ))
        if second_pipe_ok == 0:
            close_handle(ctypes.c_void_p(child_request_handle))
            close_handle(ctypes.c_void_p(request_write))
            raise OSError(ctypes.get_last_error(), "Cannot create external worker pipes")
        else:
            response_read: int = int(response_read_value.value)
            child_response_handle: int = int(response_write_value.value)
        if (set_handle_information(
                ctypes.c_void_p(child_request_handle), 1, 1,
        ) == 0 or set_handle_information(
                ctypes.c_void_p(child_response_handle), 1, 1,
        ) == 0):
            close_handle(ctypes.c_void_p(child_request_handle))
            close_handle(ctypes.c_void_p(request_write))
            close_handle(ctypes.c_void_p(response_read))
            close_handle(ctypes.c_void_p(child_response_handle))
            raise OSError(ctypes.get_last_error(), "Cannot mark external worker handles")
        else:
            pass
        startup_info: subprocess.STARTUPINFO = subprocess.STARTUPINFO()
        startup_info.lpAttributeList = {
            "handle_list": [
                child_request_handle,
                child_response_handle,
            ],
        }
        child_arguments: list[str] = [
            str(resolved_executable),
            str(child_request_handle),
            str(child_response_handle),
        ]
        try:
            process: subprocess.Popen[bytes] = subprocess.Popen(
                child_arguments,
                shell=False,
                close_fds=True,
                startupinfo=startup_info,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except BaseException:
            close_handle(ctypes.c_void_p(child_request_handle))
            close_handle(ctypes.c_void_p(request_write))
            close_handle(ctypes.c_void_p(response_read))
            close_handle(ctypes.c_void_p(child_response_handle))
            raise
        close_handle(ctypes.c_void_p(child_request_handle))
        close_handle(ctypes.c_void_p(child_response_handle))
        self._request_write = request_write
        self._response_read = response_read
        self._process = process

    def _start_posix(self, resolved_executable: Path) -> None:
        """Launch one Linux worker with two inherited pipe descriptors.

        :param resolved_executable: Verified absolute worker executable.
        :return: None.
        """
        request_read: int
        request_write: int
        request_read, request_write = os.pipe()
        response_read: int
        response_write: int
        try:
            response_read, response_write = os.pipe()
        except OSError:
            os.close(request_read)
            os.close(request_write)
            raise
        child_arguments: list[str] = [
            str(resolved_executable),
            str(request_read),
            str(response_write),
        ]
        try:
            process: subprocess.Popen[bytes] = subprocess.Popen(
                child_arguments,
                shell=False,
                close_fds=True,
                pass_fds=(request_read, response_write),
            )
        except BaseException:
            os.close(request_read)
            os.close(request_write)
            os.close(response_read)
            os.close(response_write)
            raise
        os.close(request_read)
        os.close(response_write)
        os.set_blocking(request_write, False)
        os.set_blocking(response_read, False)
        self._request_write = request_write
        self._response_read = response_read
        self._process = process

    def _request_posix(self, frame: bytes, timeout: float) -> bytes:
        """Exchange one bounded frame through Linux pipe descriptors.

        :param frame: Complete request frame.
        :param timeout: Overall write and response deadline in seconds.
        :return: Complete response frame.
        """
        request_write: int | None = self._request_write
        response_read: int | None = self._response_read
        process: subprocess.Popen[bytes] | None = self._process
        if request_write is None or response_read is None or process is None:
            raise RuntimeError("External native worker is unavailable")
        else:
            deadline: float = time.monotonic() + timeout

        # Nonblocking parent descriptors keep delivery and collection inside
        # one deadline even when vendor code stops responding.
        written: int = 0
        while written < len(frame):
            remaining: float = deadline - time.monotonic()
            if remaining <= 0.0:
                self.close()
                raise TimeoutError("External native worker request timed out")
            else:
                ready_write: list[int] = select.select(
                    list(), [request_write], list(), remaining
                )[1]
            if len(ready_write) == 0:
                self.close()
                raise TimeoutError("External native worker request timed out")
            else:
                try:
                    write_count: int = os.write(
                        request_write,
                        frame[written:min(len(frame), written + 1024 * 1024)],
                    )
                except (BrokenPipeError, OSError) as ex:
                    self.close()
                    raise RuntimeError("External native worker request pipe closed") from ex
            if write_count <= 0:
                self.close()
                raise RuntimeError("External native worker request pipe closed")
            else:
                written += write_count

        response: bytearray = bytearray()
        required: int = 8
        while len(response) < required:
            remaining = deadline - time.monotonic()
            if process.poll() is not None:
                self.close()
                raise RuntimeError("External native worker exited without a complete response")
            elif remaining <= 0.0:
                self.close()
                raise TimeoutError("External native worker response timed out")
            else:
                ready_read: list[int] = select.select(
                    [response_read], list(), list(), remaining
                )[0]
            if len(ready_read) == 0:
                self.close()
                raise TimeoutError("External native worker response timed out")
            else:
                read_size: int = min(required - len(response), 1024 * 1024)
                try:
                    chunk: bytes = os.read(response_read, read_size)
                except (BlockingIOError, OSError) as ex:
                    self.close()
                    raise RuntimeError("External native worker response pipe failed") from ex
            if len(chunk) == 0:
                self.close()
                raise RuntimeError("External native worker ended mid-frame")
            else:
                response.extend(chunk)
                if len(response) == 8:
                    body_length: int = int.from_bytes(
                        response,
                        byteorder="little",
                        signed=False,
                    )
                    if body_length < 24 or body_length > self._limits.maximum_frame_bytes:
                        self.close()
                        raise ValueError("External native worker response length is invalid")
                    else:
                        required = 8 + body_length
        return bytes(response)

    def request(self, frame: bytes, timeout_seconds: float | None = None) -> bytes:
        """Write one framed request and read one complete bounded response.

        :param frame: Complete protocol frame including its uint64 outer length.
        :param timeout_seconds: Optional finite response deadline override.
        :return: Complete response frame including its outer length.
        """
        if len(frame) < 32 or len(frame) > self._limits.maximum_frame_bytes + 8:
            raise ValueError("External native worker request is outside the frame limit")
        else:
            pass
        request_write: int | None = self._request_write
        response_read: int | None = self._response_read
        process: subprocess.Popen[bytes] | None = self._process
        if request_write is None or response_read is None or process is None or self._closed:
            raise RuntimeError("External native worker is unavailable")
        else:
            pass
        timeout: float = self._limits.response_timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        if not math.isfinite(timeout) or timeout <= 0.0 or timeout > 60.0:
            raise ValueError("External native worker timeout must be finite in (0, 60]")
        else:
            pass
        if os.name != "nt":
            return self._request_posix(frame=frame, timeout=timeout)
        else:
            pass

        # Win32 may accept only part of a frame; every byte is delivered before
        # waiting so the child observes the same single in-flight message.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        write_file = kernel32.WriteFile
        write_file.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p,
        ]
        write_file.restype = ctypes.c_int
        written: int = 0
        while written < len(frame):
            write_buffer = ctypes.create_string_buffer(frame[written:])
            write_count = ctypes.c_uint32(0)
            write_ok: int = int(write_file(
                ctypes.c_void_p(request_write),
                ctypes.byref(write_buffer),
                len(frame) - written,
                ctypes.byref(write_count),
                None,
            ))
            if write_ok == 0 or write_count.value == 0:
                self.close()
                raise RuntimeError("External native worker request pipe closed")
            else:
                written += int(write_count.value)

        # PeekNamedPipe supplies a bounded deadline without creating a reader
        # thread that could outlive the process owner after a timeout.
        peek_named_pipe = kernel32.PeekNamedPipe
        peek_named_pipe.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p,
        ]
        peek_named_pipe.restype = ctypes.c_int
        read_file = kernel32.ReadFile
        read_file.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p,
        ]
        read_file.restype = ctypes.c_int
        deadline: float = time.monotonic() + timeout
        response: bytearray = bytearray()
        required: int = 8
        while len(response) < required:
            available = ctypes.c_uint32(0)
            peek_ok: int = int(peek_named_pipe(
                ctypes.c_void_p(response_read),
                None,
                0,
                None,
                ctypes.byref(available),
                None,
            ))
            if peek_ok == 0:
                win32_error: int = int(ctypes.get_last_error())
                self.close()
                raise RuntimeError(
                    f"External native worker response pipe failed "
                    f"(Win32 {win32_error}, exit {self._exit_code})"
                )
            else:
                pass
            if available.value > 0:
                read_size: int = min(int(available.value), required - len(response))
                read_buffer = ctypes.create_string_buffer(read_size)
                read_count = ctypes.c_uint32(0)
                read_ok: int = int(read_file(
                    ctypes.c_void_p(response_read),
                    ctypes.byref(read_buffer),
                    read_size,
                    ctypes.byref(read_count),
                    None,
                ))
                if read_ok == 0 or read_count.value == 0:
                    self.close()
                    raise RuntimeError("External native worker ended mid-frame")
                else:
                    response.extend(read_buffer.raw[:int(read_count.value)])
                    if len(response) == 8:
                        body_length: int = int.from_bytes(response, byteorder="little", signed=False)
                        if body_length < 24 or body_length > self._limits.maximum_frame_bytes:
                            self.close()
                            raise ValueError("External native worker response length is invalid")
                        else:
                            required = 8 + body_length
            else:
                if process.poll() is not None:
                    self.close()
                    raise RuntimeError("External native worker exited without a complete response")
                elif time.monotonic() >= deadline:
                    self.close()
                    raise TimeoutError("External native worker response timed out")
                else:
                    time.sleep(0.001)
        return bytes(response)

    def _close_posix(self) -> None:
        """Close Linux descriptors and prove worker termination before unstaging.

        :return: None.
        """
        request_write: int | None = self._request_write
        if request_write is not None:
            os.close(request_write)
            self._request_write = None
        else:
            pass

        # Closing the request pipe asks the worker to finish naturally. Escalate
        # only after the configured finite waits so vendor code cannot leak.
        process: subprocess.Popen[bytes] | None = self._process
        if process is not None:
            try:
                process.wait(timeout=self._limits.graceful_join_timeout_seconds)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=self._limits.terminate_join_timeout_seconds)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=self._limits.kill_join_timeout_seconds)
            self._exit_code = process.returncode
            if self._exit_code is None:
                raise RuntimeError("External native worker death could not be proven; staging retained")
            else:
                self._process = None
        else:
            pass

        response_read: int | None = self._response_read
        if response_read is not None:
            os.close(response_read)
            self._response_read = None
        else:
            pass
        self._staging.close()
        self._closed = True

    def close(self) -> None:
        """Close pipes, wait through bounded escalation, then release staging.

        :return: None.
        """
        if self._closed:
            pass
        else:
            if os.name != "nt":
                self._close_posix()
                return
            else:
                pass
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [ctypes.c_void_p]
            close_handle.restype = ctypes.c_int
            request_write: int | None = self._request_write
            if request_write is not None:
                close_handle(ctypes.c_void_p(request_write))
                self._request_write = None
            else:
                pass
            process: subprocess.Popen[bytes] | None = self._process
            if process is not None:
                try:
                    process.wait(timeout=self._limits.graceful_join_timeout_seconds)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=self._limits.terminate_join_timeout_seconds)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=self._limits.kill_join_timeout_seconds)
                self._exit_code = process.returncode
                if self._exit_code is None:
                    raise RuntimeError("External native worker death could not be proven; staging retained")
                else:
                    self._process = None
            else:
                pass
            response_read: int | None = self._response_read
            if response_read is not None:
                close_handle(ctypes.c_void_p(response_read))
                self._response_read = None
            else:
                pass
            self._staging.close()
            self._closed = True


class BoundedChildOutputCapture:
    """Capture child stdout/stderr around one native call with finite retention."""

    __slots__ = (
        "_maximum_bytes", "_stdout_file", "_stderr_file", "_stdout_saved", "_stderr_saved",
        "stdout", "stderr", "stdout_truncated", "stderr_truncated",
    )

    def __init__(self, maximum_bytes: int = 1024 * 1024) -> None:
        """Prepare bounded child output capture.

        :param maximum_bytes: Maximum retained bytes per stream.
        :return: None.
        """
        if maximum_bytes <= 0:
            raise ValueError("Child output capture limit must be positive")
        else:
            pass
        self._maximum_bytes: int = maximum_bytes
        self._stdout_file: BinaryIO | None = None
        self._stderr_file: BinaryIO | None = None
        self._stdout_saved: int | None = None
        self._stderr_saved: int | None = None
        self.stdout: str = ""
        self.stderr: str = ""
        self.stdout_truncated: bool = False
        self.stderr_truncated: bool = False

    def __enter__(self) -> "BoundedChildOutputCapture":
        """Redirect process file descriptors one and two to private files.

        :return: Active capture owner.
        """
        self._stdout_file = tempfile.TemporaryFile(mode="w+b")
        self._stderr_file = tempfile.TemporaryFile(mode="w+b")
        self._stdout_saved = os.dup(1)
        self._stderr_saved = os.dup(2)
        os.dup2(self._stdout_file.fileno(), 1)
        os.dup2(self._stderr_file.fileno(), 2)
        return self

    def __exit__(self,
                 exc_tpe: type[BaseException] | None,
                 exc_value: BaseException | None,
                 traceback_value: TracebackType | None) -> None:
        """Restore descriptors and retain bounded decoded output.

        :param exc_tpe: Raised exception type, when present.
        :param exc_value: Raised exception, when present.
        :param traceback_value: Raised exception traceback, when present.
        :return: None.
        """
        try:
            process_library: ctypes.CDLL = ctypes.CDLL(None)
            process_library.fflush(None)
        except (AttributeError, OSError):
            pass
        if self._stdout_saved is not None and self._stderr_saved is not None:
            os.dup2(self._stdout_saved, 1)
            os.dup2(self._stderr_saved, 2)
            os.close(self._stdout_saved)
            os.close(self._stderr_saved)
        else:
            pass
        stdout_file: BinaryIO | None = self._stdout_file
        stderr_file: BinaryIO | None = self._stderr_file
        if stdout_file is None or stderr_file is None:
            raise RuntimeError("Child output capture files are unavailable")
        else:
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout_bytes: bytes = stdout_file.read(self._maximum_bytes + 1)
            stderr_bytes: bytes = stderr_file.read(self._maximum_bytes + 1)
            stdout_file.close()
            stderr_file.close()
        self.stdout_truncated = len(stdout_bytes) > self._maximum_bytes
        self.stderr_truncated = len(stderr_bytes) > self._maximum_bytes
        self.stdout = stdout_bytes[:self._maximum_bytes].decode("utf-8", errors="replace")
        self.stderr = stderr_bytes[:self._maximum_bytes].decode("utf-8", errors="replace")
