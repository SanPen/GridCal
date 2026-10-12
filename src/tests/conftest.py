from __future__ import annotations

import os
import secrets
import shutil
import stat
import sys
import warnings
from pathlib import Path
from typing import Any

import pytest


_ORIGINAL_CWD: Path | None = None
_TESTS_ROOT: Path = Path(__file__).resolve().parent
_TEST_STATE_ROOT: Path = Path("/tmp/veragrid-pytest")


class _AutomaticBaseTempOwner:
    """
    Own one automatically selected Windows pytest base temporary directory.

    The owner retains the exact parent, generated name and resulting path so
    cleanup never has to reconstruct a target from mutable process state.
    """

    __slots__ = ("base_temp_path", "_directory_name", "_parent_path")

    def __init__(self, repository_root: Path) -> None:
        """
        Allocate a unique short base temporary path on the repository volume.

        :param repository_root: Absolute pytest repository root used to select
                               the storage volume.
        :return: None.
        """
        # Keep compiler and fixture paths short while selecting the same volume
        # as the repository rather than inheriting a user-profile temp drive.
        repository_anchor: Path = Path(repository_root.anchor)
        self._parent_path: Path = repository_anchor / "tmp" / "veragrid-pytest"
        self._parent_path.mkdir(parents=True, exist_ok=True)

        # A PID identifies the process and the nonce prevents reuse if a PID is
        # recycled or two owners are constructed during one process lifetime.
        process_id: int = os.getpid()
        nonce: str = secrets.token_hex(4)
        self._directory_name: str = f"pytest-{process_id}-{nonce}"
        self.base_temp_path: Path = self._parent_path / self._directory_name

    def cleanup(self) -> None:
        """
        Remove only the exact automatically owned directory after a normal run.

        Reparse points and unexpected path shapes are preserved so cleanup
        cannot cross the repository-volume boundary through a junction.

        :return: None.
        """
        # The stored target must still be the expected nonce-qualified direct
        # child before any recursive operation is considered.
        expected_name: bool = self.base_temp_path.name == self._directory_name
        expected_parent: bool = self.base_temp_path.parent == self._parent_path
        if expected_name and expected_parent:
            path_status: os.stat_result | None
            try:
                path_status = os.lstat(self.base_temp_path)
            except FileNotFoundError:
                path_status = None
            except OSError as exception:
                warnings.warn(
                    f"Could not inspect owned pytest basetemp {self.base_temp_path}: {exception}",
                    RuntimeWarning,
                    stacklevel=2,
                )
                path_status = None

            if path_status is None:
                pass
            else:
                # Windows junctions expose the reparse attribute through
                # lstat; they must never be followed by recursive cleanup.
                is_reparse_point: bool = bool(
                    path_status.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
                )
                if is_reparse_point:
                    warnings.warn(
                        f"Preserving reparse-point pytest basetemp {self.base_temp_path}",
                        RuntimeWarning,
                        stacklevel=2,
                    )
                else:
                    try:
                        shutil.rmtree(self.base_temp_path)
                    except OSError as exception:
                        warnings.warn(
                            f"Could not remove owned pytest basetemp {self.base_temp_path}: {exception}",
                            RuntimeWarning,
                            stacklevel=2,
                        )
                    else:
                        pass
        else:
            warnings.warn(
                f"Preserving unexpected pytest basetemp target {self.base_temp_path}",
                RuntimeWarning,
                stacklevel=2,
            )


def pytest_configure(config: pytest.Config) -> None:
    """
    Configure process-wide test settings before test modules import Qt.

    :param config: Pytest configuration object.
    :return: None.
    """
    if "QT_QPA_PLATFORM" in os.environ:
        pass
    else:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    _TEST_STATE_ROOT.mkdir(parents=True, exist_ok=True)

    # Process-wide temporary-path policy belongs to the root test owner. An
    # explicit caller path remains authoritative and receives no VeraGrid cleanup.
    if sys.platform.startswith("win") and config.option.basetemp is None:
        automatic_owner: _AutomaticBaseTempOwner = _AutomaticBaseTempOwner(
            repository_root=Path(config.rootpath).resolve()
        )
        config.option.basetemp = str(automatic_owner.base_temp_path)
        config.add_cleanup(automatic_owner.cleanup)
    else:
        pass

    if "VERAGRID_EMT_INIT_CACHE_DIR" in os.environ:
        pass
    else:
        emt_cache_dir: Path = _TEST_STATE_ROOT / "emt_reduced_initialization"
        emt_cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ["VERAGRID_EMT_INIT_CACHE_DIR"] = str(emt_cache_dir)


class _AttributeOverrideManager:
    """
    Deterministic attribute override manager for tests.

    The manager applies explicit ``setattr`` overrides and restores all mutated
    attributes in LIFO order when the fixture finalizes.
    """

    __slots__ = ("_restore_stack",)

    def __init__(self) -> None:
        """
        Build one empty override manager.

        :return: None.
        """
        self._restore_stack: list[tuple[object, str, bool, Any]] = list()

    def setattr(self, target: object, name: str, value: Any) -> None:
        """
        Override one attribute by object reference.

        :param target: Object instance/class/module.
        :param name: Attribute name.
        :param value: Replacement value.
        :return: None.
        """
        has_attr: bool = hasattr(target, name)
        old_value: Any = getattr(target, name, None)
        self._restore_stack.append((target, name, has_attr, old_value))
        setattr(target, name, value)

    def restore_all(self) -> None:
        """
        Restore every overridden attribute in reverse application order.

        :return: None.
        """
        while len(self._restore_stack) > 0:
            obj, attr_name, has_attr, old_value = self._restore_stack.pop()
            if has_attr:
                setattr(obj, attr_name, old_value)
            else:
                if hasattr(obj, attr_name):
                    delattr(obj, attr_name)
                else:
                    pass


@pytest.fixture
def override_attrs() -> _AttributeOverrideManager:
    """
    Provide deterministic runtime attribute overrides for test seams.

    :return: Override manager.
    """
    manager: _AttributeOverrideManager = _AttributeOverrideManager()
    try:
        yield manager
    finally:
        manager.restore_all()


def pytest_sessionstart(session: object) -> None:
    """
    Run the test session from ``src/tests`` so shared ``data/...`` fixtures resolve.

    PyCharm folder runs commonly start with the selected test folder as the
    working directory, while a large part of the legacy integration suite still
    addresses the common fixture tree through relative paths such as
    ``data/grids/...``. Normalizing the session cwd keeps those tests runnable
    both from the full suite and from individual folders.

    :param session: Pytest session object.
    :return: None.
    """
    global _ORIGINAL_CWD

    _unused_session: object = session
    _ORIGINAL_CWD = Path.cwd()
    os.chdir(_TESTS_ROOT)


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    """
    Restore the original working directory after the test session finishes.

    :param session: Pytest session object.
    :param exitstatus: Pytest exit status code.
    :return: None.
    """
    global _ORIGINAL_CWD

    _unused_session: object = session
    _unused_exitstatus: int = int(exitstatus)

    if _ORIGINAL_CWD is None:
        pass
    else:
        os.chdir(_ORIGINAL_CWD)
