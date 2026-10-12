from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import numpy as np
import pytest
from scipy.sparse import csc_matrix

from VeraGridEngine.DataStructures.active_branch_data import ActiveBranchData
from VeraGridEngine.DataStructures.battery_data import BatteryData
from VeraGridEngine.DataStructures.branch_parent_data import BranchParentData
from VeraGridEngine.DataStructures.bus_data import BusData
from VeraGridEngine.DataStructures.fluid_node_data import FluidNodeData
from VeraGridEngine.DataStructures.fluid_p2x_data import FluidP2XData
from VeraGridEngine.DataStructures.fluid_path_data import FluidPathData
from VeraGridEngine.DataStructures.fluid_pump_data import FluidPumpData
from VeraGridEngine.DataStructures.fluid_turbine_data import FluidTurbineData
from VeraGridEngine.DataStructures.generator_data import GeneratorData
from VeraGridEngine.DataStructures.hvdc_data import HvdcData
from VeraGridEngine.DataStructures.load_data import LoadData
from VeraGridEngine.DataStructures.numerical_circuit import DataStructType, NumericalCircuit
from VeraGridEngine.DataStructures.passive_branch_data import PassiveBranchData
from VeraGridEngine.DataStructures.shunt_data import ShuntData
from VeraGridEngine.DataStructures.vsc_data import VscData
from VeraGridEngine.Utils.Sparse.sparse_array import SparseObjectArray


TEST_ELM_IDX = np.array([0, 2], dtype=int)
TEST_BUS_IDX = np.array([1, 3, 4], dtype=int)
TEST_BUS_MAP = np.array([-1, 0, -1, 1, 2], dtype=int)
DATA_STRUCTURES_DIR = Path(__file__).resolve().parents[2] / "VeraGridEngine" / "DataStructures"
SKIP = object()


def _repeat(values: list[int], size: int, dtype: np.dtype) -> np.ndarray:
    return np.resize(np.array(values, dtype=dtype), size).astype(dtype, copy=False)


def _fill_array(name: str, array: np.ndarray, obj) -> np.ndarray:
    if array.size == 0:
        return array.copy()

    if name == "original_idx":
        return np.arange(array.shape[0], dtype=array.dtype)

    if array.dtype == object:
        return np.array([f"{name}_{i}" for i in range(array.size)], dtype=object).reshape(array.shape)

    kind = array.dtype.kind
    shape = array.shape
    size = array.size

    if kind == "b":
        return (np.arange(size) % 2).astype(bool).reshape(shape)

    if kind in ("i", "u"):
        targets = {
            "bus_idx": getattr(obj, "nbus", 1),
            "controllable_bus_idx": getattr(obj, "nbus", 1),
            "tap_controlled_buses": getattr(obj, "nbus", 1),
            "F": getattr(obj, "nbus", 1),
            "T": getattr(obj, "nbus", 1),
            "F_dcn": getattr(obj, "nbus", 1),
            "control1_bus_idx": getattr(obj, "nbus", 1),
            "control2_bus_idx": getattr(obj, "nbus", 1),
            "control1_branch_idx": getattr(obj, "nelm", 1),
            "control2_branch_idx": getattr(obj, "nelm", 1),
            "source_idx": max(getattr(obj, "nelm", 1), 1),
            "target_idx": max(getattr(obj, "nelm", 1), 1),
            "plant_idx": max(getattr(obj, "nelm", 1), 1),
            "generator_idx": max(getattr(obj, "nelm", 1), 1),
        }
        if name in targets:
            return (np.arange(size) % max(targets[name], 1)).astype(array.dtype).reshape(shape)
        return (np.arange(size) + 1).astype(array.dtype).reshape(shape)

    if kind == "f":
        return (np.arange(size).reshape(shape) + 0.25).astype(array.dtype)

    if kind == "c":
        base = np.arange(size).reshape(shape)
        return (base + 1.0 + 1.0j * (base + 2.0)).astype(array.dtype)

    raise TypeError(f"Unsupported array type for {name}: {array.dtype}")


def _fill_sparse(name: str, sparse: SparseObjectArray) -> SparseObjectArray:
    filled = SparseObjectArray(n=sparse.size())
    if filled.size() > 0:
        filled[0] = f"{name}_0"
    if filled.size() > 2:
        filled[2] = f"{name}_2"
    return filled


def _customize_indices(obj) -> None:
    def set_values(name: str, values: list[int]) -> None:
        if not hasattr(obj, name):
            return
        array = getattr(obj, name)
        if isinstance(array, np.ndarray) and array.ndim == 1 and array.size:
            setattr(obj, name, _repeat(values, array.size, array.dtype))

    set_values("bus_idx", [1, 2, 4, 3])
    set_values("controllable_bus_idx", [-1, 4, 1, 3])
    set_values("tap_controlled_buses", [0, 4, 1, 0])
    set_values("F", [1, 3, 4, 1])
    set_values("T", [3, 4, 1, 4])
    set_values("control1_bus_idx", [-1, 4, 1, 3])
    set_values("control2_bus_idx", [4, -1, 1, 3])
    set_values("control1_branch_idx", [-1, 2, 1, 0])
    set_values("control2_branch_idx", [3, -1, 0, 1])
    set_values("source_idx", [0, 1, 0, 1])
    set_values("target_idx", [1, 0, 1, 0])
    set_values("plant_idx", [0, 1, 0, 1])
    set_values("generator_idx", [1, 0, 1, 0])


def _attribute_names(obj) -> list[str]:
    """Return instance attribute names for slotted and regular objects."""
    names: list[str] = list()

    for cls in type(obj).__mro__:
        slots = cls.__dict__.get("__slots__", tuple())
        if isinstance(slots, str):
            names.append(slots)
        else:
            names.extend(slots)

    if any("__dict__" in cls.__dict__ for cls in type(obj).__mro__):
        names.extend(vars(obj).keys())

    available_names: list[str] = list()
    for name in dict.fromkeys(names):
        try:
            getattr(obj, name)
            available_names.append(name)
        except AttributeError:
            pass

    return available_names


def _populate_data_object(obj):
    for name in _attribute_names(obj):
        value = getattr(obj, name)
        if isinstance(value, np.ndarray):
            setattr(obj, name, _fill_array(name, value, obj))
        elif isinstance(value, SparseObjectArray):
            setattr(obj, name, _fill_sparse(name, value))
        elif isinstance(value, dict):
            setattr(obj, name, {})

    if hasattr(obj, "names"):
        obj.names = np.array([f"{type(obj).__name__}_name_{i}" for i in range(len(obj.names))], dtype=object)
    if hasattr(obj, "idtag"):
        obj.idtag = np.array([f"{type(obj).__name__}_idtag_{i}" for i in range(len(obj.idtag))], dtype=object)
    if hasattr(obj, "name_to_idx"):
        obj.name_to_idx = {str(name): i for i, name in enumerate(obj.names)}

    _customize_indices(obj)
    return obj


def _build_numerical_circuit() -> NumericalCircuit:
    circuit = NumericalCircuit(
        nbus=5,
        nbr=4,
        nhvdc=4,
        nvsc=4,
        nload=4,
        ngen=4,
        nbatt=4,
        nshunt=4,
        nfluidnode=3,
        nfluidturbine=3,
        nfluidpump=3,
        nfluidp2x=3,
        nfluidpath=3,
        sbase=123.0,
        t_idx=7,
    )

    for name in _attribute_names(circuit):
        value = getattr(circuit, name)
        if _is_data_structure_instance(value):
            setattr(circuit, name, _populate_data_object(value))

    circuit._NumericalCircuit__bus_map_arr = np.array([2, 0, 4, 1, 3], dtype=int)
    circuit._NumericalCircuit__topology_performed = True
    circuit.structs_idtag_dict = {
        "branch-0": (DataStructType.BRANCHDATA, 0),
        "bus-1": (DataStructType.BUSDATA, 1),
    }
    return circuit


def _copy_builders() -> dict[str, callable]:
    return {
        "ActiveBranchData": lambda: _populate_data_object(ActiveBranchData(nelm=4, nbus=5)),
        "BatteryData": lambda: _populate_data_object(BatteryData(nelm=4, nbus=5)),
        "BranchParentData": lambda: _populate_data_object(BranchParentData(nelm=4, nbus=5)),
        "BusData": lambda: _populate_data_object(BusData(nbus=5)),
        "FluidNodeData": lambda: _populate_data_object(FluidNodeData(nelm=3)),
        "FluidP2XData": lambda: _populate_data_object(FluidP2XData(nelm=3)),
        "FluidPathData": lambda: _populate_data_object(FluidPathData(nelm=3)),
        "FluidPumpData": lambda: _populate_data_object(FluidPumpData(nelm=3)),
        "FluidTurbineData": lambda: _populate_data_object(FluidTurbineData(nelm=3)),
        "GeneratorData": lambda: _populate_data_object(GeneratorData(nelm=4, nbus=5)),
        "HvdcData": lambda: _populate_data_object(HvdcData(nelm=4, nbus=5)),
        "LoadData": lambda: _populate_data_object(LoadData(nelm=4, nbus=5)),
        "NumericalCircuit": _build_numerical_circuit,
        "PassiveBranchData": lambda: _populate_data_object(PassiveBranchData(nelm=4, nbus=5)),
        "ShuntData": lambda: _populate_data_object(ShuntData(nelm=4, nbus=5)),
        "VscData": lambda: _populate_data_object(VscData(nelm=4, nbus=5)),
    }


def _slice_builders() -> dict[str, callable]:
    return {
        "ActiveBranchData": lambda: _populate_data_object(ActiveBranchData(nelm=4, nbus=5)),
        "BatteryData": lambda: _populate_data_object(BatteryData(nelm=4, nbus=5)),
        "BranchParentData": lambda: _populate_data_object(BranchParentData(nelm=4, nbus=5)),
        "BusData": lambda: _populate_data_object(BusData(nbus=5)),
        "GeneratorData": lambda: _populate_data_object(GeneratorData(nelm=4, nbus=5)),
        "HvdcData": lambda: _populate_data_object(HvdcData(nelm=4, nbus=5)),
        "LoadData": lambda: _populate_data_object(LoadData(nelm=4, nbus=5)),
        "PassiveBranchData": lambda: _populate_data_object(PassiveBranchData(nelm=4, nbus=5)),
        "ShuntData": lambda: _populate_data_object(ShuntData(nelm=4, nbus=5)),
        "VscData": lambda: _populate_data_object(VscData(nelm=4, nbus=5)),
    }


COPY_BUILDERS = _copy_builders()
SLICE_BUILDERS = _slice_builders()


def _discover_data_structure_classes(method_name: str) -> set[str]:
    classes: set[str] = set()
    for module_path in DATA_STRUCTURES_DIR.glob("*.py"):
        if module_path.name == "__init__.py":
            continue
        module = importlib.import_module(f"VeraGridEngine.DataStructures.{module_path.stem}")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            if callable(getattr(cls, method_name, None)):
                classes.add(cls.__name__)
    return classes


def _is_data_structure_instance(value) -> bool:
    return value.__class__.__module__.startswith("VeraGridEngine.DataStructures")


def _assert_value_equal(expected, actual, name: str) -> None:
    if isinstance(expected, csc_matrix):
        assert isinstance(actual, csc_matrix), name
        assert actual.shape == expected.shape, name
        assert (actual != expected).nnz == 0, name
        return
    else:
        pass
    if isinstance(expected, np.ndarray):
        assert isinstance(actual, np.ndarray), name
        assert np.array_equal(actual, expected), name
        return

    if isinstance(expected, SparseObjectArray):
        assert isinstance(actual, SparseObjectArray), name
        assert actual == expected, name
        return

    if _is_data_structure_instance(expected):
        _assert_deep_copy(expected, actual)
        return

    assert actual == expected, name


def _assert_deep_copy(source, copied) -> None:
    assert type(copied) is type(source)

    for name in _attribute_names(source):
        value = getattr(source, name)
        assert hasattr(copied, name), name
        copied_value = getattr(copied, name)
        _assert_value_equal(value, copied_value, name)

        if isinstance(value, np.ndarray):
            assert copied_value is not value, name
        elif isinstance(value, csc_matrix):
            assert not np.shares_memory(copied_value.data, value.data), name
        elif isinstance(value, SparseObjectArray):
            assert copied_value is not value, name
            assert copied_value.get_map() is not value.get_map(), name
        elif isinstance(value, dict):
            assert copied_value is not value, name
        elif _is_data_structure_instance(value):
            assert copied_value is not value, name


def _expected_slice_value(source, name: str, value, *, bus_only: bool):
    if name == 'Ycoupling3':
        terminal_indices: np.ndarray = (4 * TEST_ELM_IDX[:, None] + np.arange(4)).ravel()
        terminal_indices = np.r_[terminal_indices, 4 * source.nelm + terminal_indices]
        return value[terminal_indices, :][:, terminal_indices].tocsc()
    else:
        pass
    if isinstance(value, np.ndarray):
        if bus_only:
            if name == "original_idx":
                return TEST_BUS_IDX
            if value.shape and value.shape[0] == source.nbus:
                return value[TEST_BUS_IDX]
            return SKIP

        if name == "original_idx":
            return TEST_ELM_IDX

        if name in {"F", "T", "bus_idx"}:
            return TEST_BUS_MAP[value[TEST_ELM_IDX]]

        if name in {"controllable_bus_idx", "control1_bus_idx", "control2_bus_idx"}:
            expected = value[TEST_ELM_IDX].copy()
            mask = expected > -1
            expected[mask] = TEST_BUS_MAP[expected[mask]]
            return expected

        if name == "tap_controlled_buses":
            expected = value[TEST_ELM_IDX].copy()
            mask = expected != 0
            expected[mask] = TEST_BUS_MAP[expected[mask]]
            return expected

        if value.shape and value.shape[0] == source.nelm:
            return value[TEST_ELM_IDX]

        if value.shape and value.shape[0] == source.nelm * 4:
            elm_idx_4 = ((TEST_ELM_IDX * 4)[:, np.newaxis] + np.arange(4)).flatten()
            return value[elm_idx_4]

        if value.shape and value.shape[0] == source.nelm * 3:
            elm_idx_3 = ((TEST_ELM_IDX * 3)[:, np.newaxis] + np.arange(3)).flatten()
            return value[elm_idx_3]

        return SKIP

    if isinstance(value, SparseObjectArray):
        return value.slice(TEST_ELM_IDX) if not bus_only else SKIP

    if isinstance(value, dict):
        if name == "name_to_idx" and not bus_only:
            return {str(name): i for i, name in enumerate(source.names[TEST_ELM_IDX])}
        return SKIP

    if name == "nelm":
        return len(TEST_ELM_IDX)
    if name == "nbus":
        return len(TEST_BUS_IDX)

    return value


def _assert_slice_matches_source(source, sliced, *, bus_only: bool) -> None:
    assert type(sliced) is type(source)

    for name in _attribute_names(source):
        value = getattr(source, name)
        assert hasattr(sliced, name), name
        expected = _expected_slice_value(source, name, value, bus_only=bus_only)
        if expected is SKIP:
            continue
        _assert_value_equal(expected, getattr(sliced, name), name)


def test_copy_builders_cover_all_data_structure_classes() -> None:
    assert set(COPY_BUILDERS) == _discover_data_structure_classes("copy")


def test_slice_builders_cover_all_sliceable_data_structure_classes() -> None:
    assert set(SLICE_BUILDERS) == _discover_data_structure_classes("slice")


@pytest.mark.parametrize("class_name", sorted(COPY_BUILDERS))
def test_data_structure_copy_roundtrip(class_name: str) -> None:
    source = COPY_BUILDERS[class_name]()
    copied = source.copy()
    _assert_deep_copy(source, copied)


@pytest.mark.parametrize("class_name", sorted(SLICE_BUILDERS))
def test_data_structure_slice_roundtrip(class_name: str) -> None:
    source = SLICE_BUILDERS[class_name]()

    if isinstance(source, BusData):
        sliced = source.slice(TEST_BUS_IDX)
        _assert_slice_matches_source(source, sliced, bus_only=True)
        return

    slice_signature = inspect.signature(source.slice)
    if len(slice_signature.parameters) == 4:
        result = source.slice(TEST_ELM_IDX, TEST_BUS_IDX, TEST_BUS_MAP, None)
    else:
        result = source.slice(TEST_ELM_IDX, TEST_BUS_IDX, TEST_BUS_MAP)
    if isinstance(result, tuple):
        sliced, returned_map = result
        assert np.array_equal(returned_map, TEST_BUS_MAP)
    else:
        sliced = result

    _assert_slice_matches_source(source, sliced, bus_only=False)
