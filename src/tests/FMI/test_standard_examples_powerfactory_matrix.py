"""Focused offline gates for the named PowerFactory standard-example lane."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import struct
import zipfile
from xml.etree import ElementTree

import numpy as np
import pytest

from examples.fmi.veragrid_standard_examples.diagnose_powerfactory_cominc import (
    classify_native_exit,
    read_bootstrap_identity,
)
from examples.fmi.veragrid_standard_examples.run_powerfactory_matrix import (
    PowerFactoryCell,
    PowerFactoryRunJob,
    build_powerfactory_initialization_derivative,
    configure_standard_cell,
    create_named_event_profile,
    inspect_pe_timestamp_normalized_binary,
    load_catalog_cells,
    main as worker_main,
    parse_named_values,
    prepare_powerfactory_compatibility_cells,
    run_powerfactory_cell_worker,
    write_release_checkpoint,
)
from examples.fmi.veragrid_standard_examples.supervise_powerfactory_matrix import (
    main as supervisor_main,
    validate_release_checkpoint,
    write_matrix_release_checkpoint,
)
from examples.fmi.veragrid_standard_examples.validate_powerfactory_matrix import (
    canonicalize_named_trace,
    load_numeric_csv,
    select_reference_lattice,
    validate_version_consistency,
    write_powerfactory_validator_view,
)
from examples.fmi.veragrid_standard_examples import validate_powerfactory_matrix


def test_catalog_selection() -> None:
    """Require exactly twelve original PowerFactory-applicable catalog hashes.

    :return: None.
    """
    root: Path = (
        Path(__file__).resolve().parents[3]
        / "examples"
        / "fmi"
        / "veragrid_standard_examples"
        / "published"
        / "win64"
    )
    cells = load_catalog_cells(root)
    assert len(cells) == 12
    assert set(cell.version for cell in cells) == {"2.0", "3.0"}
    assert set(cell.family for cell in cells) == {"GENSAL", "TGOV1", "ESDC2A"}


def test_named_port_permutations() -> None:
    """Accept valid order changes and reject missing or duplicate names.

    :return: None.
    """
    expected: tuple[str, ...] = ("Id", "Iq", "Efd", "Pm")
    assert parse_named_values("Efd,Id,Iq,Pm", expected) == ("Efd", "Id", "Iq", "Pm")
    with pytest.raises(ValueError):
        parse_named_values("Efd,Id,Id,Pm", expected)
    with pytest.raises(ValueError):
        parse_named_values("Efd,Id,Iq", expected)


def test_event_row_canonicalization() -> None:
    """Gate named inputs on every tick and reject rogue event phases.

    :return: None.
    """
    dtype: np.dtype = np.dtype([("time", np.float64), ("u", np.float64), ("y", np.float64)])
    schedule_dtype: np.dtype = np.dtype([("time", np.float64), ("u", np.float64)])
    schedule: np.ndarray = np.array([(0.0, 1.0), (0.002, 1.0), (0.002, 2.0), (0.004, 2.0)], dtype=schedule_dtype)
    good: np.ndarray = np.array([(0.0, 1.0, 0.0), (0.001, 1.0, 0.0), (0.002, 1.0, 0.0), (0.002, 2.0, 0.0), (0.003, 2.0, 1.0), (0.004, 2.0, 1.0)], dtype=dtype)
    canonical: np.ndarray = canonicalize_named_trace(good, schedule, ("u",), ("y",), 0.004)
    assert canonical.size == 5
    assert float(canonical[2]["u"]) == 2.0
    rogue: np.ndarray = good.copy()
    rogue[2]["u"] = 1.5
    with pytest.raises(ValueError):
        canonicalize_named_trace(rogue, schedule, ("u",), ("y",), 0.004)
    duplicate: np.ndarray = np.insert(good, 1, good[1])
    with pytest.raises(ValueError):
        canonicalize_named_trace(duplicate, schedule, ("u",), ("y",), 0.004)
    drift: np.ndarray = good.copy()
    drift[4]["u"] = 2.1
    with pytest.raises(ValueError):
        canonicalize_named_trace(drift, schedule, ("u",), ("y",), 0.004)

    # Simultaneous multi-input changes must apply as one complete vector.
    vector_dtype: np.dtype = np.dtype([("time", np.float64), ("u", np.float64), ("v", np.float64), ("y", np.float64)])
    vector_schedule_dtype: np.dtype = np.dtype([("time", np.float64), ("u", np.float64), ("v", np.float64)])
    vector_schedule: np.ndarray = np.array([(0.0, 1.0, 3.0), (0.002, 1.0, 3.0), (0.002, 2.0, 4.0), (0.004, 2.0, 4.0)], dtype=vector_schedule_dtype)
    vector_trace: np.ndarray = np.array([(0.0, 1.0, 3.0, 0.0), (0.001, 1.0, 3.0, 0.0), (0.002, 2.0, 4.0, 0.0), (0.003, 2.0, 4.0, 1.0), (0.004, 2.0, 4.0, 1.0)], dtype=vector_dtype)
    vector_canonical: np.ndarray = canonicalize_named_trace(vector_trace, vector_schedule, ("u", "v"), ("y",), 0.004)
    assert float(vector_canonical[2]["u"]) == 2.0
    assert float(vector_canonical[2]["v"]) == 4.0
    mixed_vector: np.ndarray = vector_trace.copy()
    mixed_vector[2]["v"] = 3.0
    with pytest.raises(ValueError, match="neither the required new vector"):
        canonicalize_named_trace(mixed_vector, vector_schedule, ("u", "v"), ("y",), 0.004)

    # Only the observed ESDC2A UPss event at 1.1 s may move exactly one tick.
    delayed_dtype: np.dtype = np.dtype([("time", np.float64), ("UPssPu_ESDC2A", np.float64), ("v", np.float64), ("y", np.float64)])
    delayed_schedule_dtype: np.dtype = np.dtype([("time", np.float64), ("UPssPu_ESDC2A", np.float64), ("v", np.float64)])
    delayed_schedule: np.ndarray = np.array([(0.0, 0.02, 5.0), (1.1, 0.02, 5.0), (1.1, 0.0, 5.0), (1.101, 0.0, 5.0)], dtype=delayed_schedule_dtype)
    delayed_trace: np.ndarray = np.zeros(1102, dtype=delayed_dtype)
    delayed_tick: int
    for delayed_tick in range(delayed_trace.size):
        delayed_trace[delayed_tick]["time"] = delayed_tick / 1000.0
        delayed_trace[delayed_tick]["UPssPu_ESDC2A"] = 0.02 if delayed_tick <= 1100 else 0.0
        delayed_trace[delayed_tick]["v"] = 5.0
    delayed_canonical: np.ndarray = canonicalize_named_trace(delayed_trace, delayed_schedule, ("UPssPu_ESDC2A", "v"), ("y",), 1.101)
    assert float(delayed_canonical[1100]["UPssPu_ESDC2A"]) == 0.02
    assert float(delayed_canonical[1101]["UPssPu_ESDC2A"]) == 0.0

    generic_delayed: np.ndarray = np.array([(0.0, 1.0, 0.0), (0.001, 1.0, 0.0), (0.002, 1.0, 0.0), (0.003, 2.0, 1.0), (0.004, 2.0, 1.0)], dtype=dtype)
    with pytest.raises(ValueError, match="exact allowed delayed tuple"):
        canonicalize_named_trace(generic_delayed, schedule, ("u",), ("y",), 0.004)
    partial_successor: np.ndarray = delayed_trace.copy()
    partial_successor[1101]["v"] = 6.0
    with pytest.raises(ValueError, match="complete new vector"):
        canonicalize_named_trace(partial_successor, delayed_schedule, ("UPssPu_ESDC2A", "v"), ("y",), 1.101)
    longer_delay: np.ndarray = np.zeros(1103, dtype=delayed_dtype)
    for delayed_tick in range(longer_delay.size):
        longer_delay[delayed_tick]["time"] = delayed_tick / 1000.0
        longer_delay[delayed_tick]["UPssPu_ESDC2A"] = 0.02 if delayed_tick <= 1101 else 0.0
        longer_delay[delayed_tick]["v"] = 5.0
    longer_schedule: np.ndarray = np.array([(0.0, 0.02, 5.0), (1.1, 0.02, 5.0), (1.1, 0.0, 5.0), (1.102, 0.0, 5.0)], dtype=delayed_schedule_dtype)
    with pytest.raises(ValueError, match="complete new vector"):
        canonicalize_named_trace(longer_delay, longer_schedule, ("UPssPu_ESDC2A", "v"), ("y",), 1.102)
    adjacent_schedule: np.ndarray = np.array([(0.0, 0.02, 5.0), (1.1, 0.02, 5.0), (1.1, 0.0, 5.0), (1.101, 0.0, 5.0), (1.101, 0.0, 6.0)], dtype=delayed_schedule_dtype)
    adjacent_trace: np.ndarray = delayed_trace.copy()
    adjacent_trace[1101]["v"] = 6.0
    with pytest.raises(ValueError, match="adjacent event"):
        canonicalize_named_trace(adjacent_trace, adjacent_schedule, ("UPssPu_ESDC2A", "v"), ("y",), 1.101)
    final_schedule: np.ndarray = np.array([(0.0, 0.02, 5.0), (1.1, 0.02, 5.0), (1.1, 0.0, 5.0)], dtype=delayed_schedule_dtype)
    with pytest.raises(ValueError, match="exact allowed delayed tuple"):
        canonicalize_named_trace(delayed_trace[:1101], final_schedule, ("UPssPu_ESDC2A", "v"), ("y",), 1.1)
    reversed_trace: np.ndarray = np.insert(good, 4, good[2])
    with pytest.raises(ValueError, match="intermediate or reversed"):
        canonicalize_named_trace(reversed_trace, schedule, ("u",), ("y",), 0.004)


def test_reference_lattice_selection() -> None:
    """Select exact tenth samples and reject a shifted reference grid.

    :return: None.
    """
    dtype: np.dtype = np.dtype([("time", np.float64), ("y", np.float64)])
    canonical: np.ndarray = np.array([(index / 1000.0, float(index)) for index in range(21)], dtype=dtype)
    reference: np.ndarray = np.array([(0.0, 0.0), (0.01, 10.0), (0.02, 20.0)], dtype=dtype)
    selected: np.ndarray = select_reference_lattice(canonical, reference)
    assert np.array_equal(selected["y"], reference["y"])
    shifted: np.ndarray = reference.copy()
    shifted[1]["time"] = 0.011
    with pytest.raises(ValueError):
        select_reference_lattice(canonical, shifted)


def test_version_consistency(tmp_path: Path) -> None:
    """Gate FMI 2/3 on all common samples, including the initial one.

    :param tmp_path: Pytest-owned temporary directory.
    :return: None.
    """
    first: Path = tmp_path / "fmi2.csv"
    second: Path = tmp_path / "fmi3.csv"
    path: Path
    values: tuple[float, ...]
    for path, values in ((first, (0.0, 1.0)), (second, (0.001, 1.001))):
        with path.open("x", encoding="utf-8", newline="") as stream:
            writer: csv.writer = csv.writer(stream)
            writer.writerow(("time", "ref_y", "pf_y", "abs_y"))
            writer.writerow((0.0, 0.0, values[0], values[0]))
            writer.writerow((0.01, 1.0, values[1], abs(values[1] - 1.0)))
    receipt: dict[str, object] = validate_version_consistency(first, second, ("y",))
    assert receipt["status"] == "PASS"


def test_t0_event_initialization_contract() -> None:
    """Require empty inputInitFmu and explicit t=0 events for every input.

    :return: None.
    """
    configure_source: str = inspect.getsource(configure_standard_cell)
    event_source: str = inspect.getsource(create_named_event_profile)
    assert 'set_owned_attribute(model, "inputInitFmu"' not in configure_source
    assert 'model.GetAttribute("inputInitFmu")' in configure_source
    assert 'len(readback_value) == 0' in configure_source
    assert 'for input_name in cell.input_names' in event_source
    assert 'float(schedule[0][input_name]), 0.0, "initial"' in event_source
    assert 'set_owned_attribute(event, "outserv", 0' in event_source


def test_powerfactory_validator_view(tmp_path: Path) -> None:
    """Permit only the auditable zero-time input rewrite in a separate CSV.

    :param tmp_path: Pytest-owned temporary directory.
    :return: None.
    """
    raw_path: Path = tmp_path / "raw.csv"
    schedule_path: Path = tmp_path / "schedule.csv"
    view_path: Path = tmp_path / "views" / "view.csv"
    with raw_path.open("x", encoding="utf-8", newline="") as stream:
        writer: csv.writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("time", "u", "y"))
        tick_index: int
        for tick_index in range(2001):
            writer.writerow((format(tick_index / 1000.0, ".17g"), 0.0 if tick_index == 0 else 1.0, float(tick_index)))
    with schedule_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("time", "u"))
        writer.writerow((0.0, 1.0))
        writer.writerow((2.0, 1.0))
    raw_hash: str = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    receipt: dict[str, object] = write_powerfactory_validator_view(raw_path, schedule_path, ("u",), ("y",), 2.0, 201, view_path)
    view: np.ndarray = load_numeric_csv(view_path)
    raw: np.ndarray = load_numeric_csv(raw_path)
    assert receipt["raw_sha256"] == raw_hash
    assert receipt["input_lattice_tick_count"] == 2001
    assert receipt["actual_input_lattice_tick_count"] == 2001
    assert receipt["expected_input_lattice_tick_count"] == 2001
    assert receipt["authenticated_output_reference_sample_count"] == 201
    assert receipt["delayed_input_transition_count"] == 0
    assert receipt["numerical_difference_count"] == 1
    assert float(view[0]["u"]) == 1.0
    assert np.array_equal(raw["y"], view["y"])
    assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == raw_hash
    invalid_raw_path: Path = tmp_path / "invalid-raw.csv"
    invalid_raw_path.write_bytes(raw_path.read_bytes())
    invalid_rows: list[str] = invalid_raw_path.read_text(encoding="utf-8").splitlines()
    invalid_rows[2] = "0.001,0,1"
    invalid_raw_path.write_text("\n".join(invalid_rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        write_powerfactory_validator_view(invalid_raw_path, schedule_path, ("u",), ("y",), 2.0, 201, tmp_path / "invalid-view.csv")

    # ESDC2A owns a shorter authenticated horizon and therefore exactly 1501
    # input ticks; this is valid rather than an incomplete 2.0 s execution.
    short_raw_path: Path = tmp_path / "short-raw.csv"
    short_schedule_path: Path = tmp_path / "short-schedule.csv"
    short_view_path: Path = tmp_path / "views" / "short-view.csv"
    with short_raw_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("time", "u", "y"))
        for tick_index in range(1501):
            writer.writerow((format(tick_index / 1000.0, ".17g"), 0.0 if tick_index == 0 else 1.0, float(tick_index)))
    with short_schedule_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("time", "u"))
        writer.writerow((0.0, 1.0))
        writer.writerow((1.5, 1.0))
    short_receipt: dict[str, object] = write_powerfactory_validator_view(
        short_raw_path,
        short_schedule_path,
        ("u",),
        ("y",),
        1.5,
        151,
        short_view_path,
    )
    assert short_receipt["actual_input_lattice_tick_count"] == 1501
    assert short_receipt["expected_input_lattice_tick_count"] == 1501
    assert short_receipt["authenticated_output_reference_sample_count"] == 151

    off_by_one_path: Path = tmp_path / "off-by-one.csv"
    off_by_one_path.write_text("\n".join(raw_path.read_text(encoding="utf-8").splitlines()[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected tick count"):
        write_powerfactory_validator_view(off_by_one_path, schedule_path, ("u",), ("y",), 2.0, 201, tmp_path / "off-by-one-view.csv")
    with pytest.raises(ValueError, match="not on the 1 ms lattice"):
        write_powerfactory_validator_view(raw_path, schedule_path, ("u",), ("y",), 1.5005, 151, tmp_path / "nonintegral-view.csv")


def test_supervisor_checkpoint(tmp_path: Path) -> None:
    """Reject an incomplete or forged release checkpoint.

    :param tmp_path: Pytest-owned temporary directory.
    :return: None.
    """
    cell: PowerFactoryCell = PowerFactoryCell("GENSAL", "2.0", "cs", "VGGENSAL_FMI20_CS", tmp_path / "cell.fmu", "0" * 64, ("u",), ("y",), tmp_path / "in.csv", tmp_path / "ref.csv", 2.0)
    job: PowerFactoryRunJob = PowerFactoryRunJob(0, "00_VGGENSAL_FMI20_CS_h_0p001000000", cell, 0.001)
    checkpoint: dict[str, object] = {"schema_version": "1.0", "record_kind": "powerfactory_standard_child_checkpoint", "sealed_dossier_sha256": "4b3aa0ccd496daa7cfbcc3b2d80639724ee0d0255b4b2e2a6763dc5894e57edc", "run_nonce": "0" * 64, "worker_pid": 99, "job_id": job.job_id, "job_index": job.job_index, "observations": {"cells": list()}, "artifacts": list(), "status": "READY_FOR_PARENT_ACK"}
    (tmp_path / "child-checkpoint.json").write_text(json.dumps(checkpoint), encoding="utf-8")
    with pytest.raises((ValueError, FileNotFoundError)):
        validate_release_checkpoint(tmp_path, "0" * 64, 99, job)
    atomic_dir: Path = tmp_path / "atomic"
    atomic_dir.mkdir()
    observations: dict[str, object] = {"cells": [{"status": "PASS", "raw_csv": "raw.csv", "raw_sha256": "1" * 64}], "cleanup": {"status": "PASS"}}
    (atomic_dir / "observations.json").write_text(json.dumps(observations), encoding="utf-8")
    durable_checkpoint: dict[str, object] = write_release_checkpoint(atomic_dir, observations, "1" * 64, 101, job)
    assert durable_checkpoint["status"] == "READY_FOR_PARENT_ACK"
    assert (atomic_dir / "child-checkpoint.json").is_file()
    assert not (atomic_dir / ("child-checkpoint.json.tmp-" + "1" * 64)).exists()
    validated: dict[str, object] = validate_release_checkpoint(atomic_dir, "1" * 64, 101, job)
    assert validated == observations
    failed_dir: Path = tmp_path / "failed"
    failed_dir.mkdir()
    failed_observations: dict[str, object] = {"cells": [{"status": "FAIL"}], "cleanup": {"status": "PASS"}}
    (failed_dir / "observations.json").write_text(json.dumps(failed_observations), encoding="utf-8")
    write_release_checkpoint(failed_dir, failed_observations, "2" * 64, 102, job)
    with pytest.raises(ValueError):
        validate_release_checkpoint(failed_dir, "2" * 64, 102, job)
    checkpoint_source: str = inspect.getsource(write_release_checkpoint)
    worker_source: str = inspect.getsource(worker_main)
    assert checkpoint_source.index("stream.flush()") < checkpoint_source.index("os.fsync") < checkpoint_source.index("os.replace")
    supervisor_capture_index: int = worker_source.index("supervised_worker: bool = run_nonce is not None and job is not None")
    nonce_generation_index: int = worker_source.index("nonce: str = secrets.token_hex(32) if run_nonce is None else run_nonce")
    checkpoint_call_index: int = worker_source.rindex("write_release_checkpoint")
    success_gate_index: int = worker_source.index('if supervised_worker and cleanup.get("status", None) == "PASS" and execution_complete', checkpoint_call_index)
    isolated_exit_index: int = worker_source.index("os._exit(0)", success_gate_index)
    ordinary_release_index: int = worker_source.index("application = cast", isolated_exit_index)
    assert supervisor_capture_index < nonce_generation_index < checkpoint_call_index
    assert checkpoint_call_index < success_gate_index < isolated_exit_index < ordinary_release_index


def test_powerfactory_me_sensitivity_validator_views() -> None:
    """Require every sensitivity comparison to consume authenticated views.

    :return: None.
    """
    source: str = inspect.getsource(validate_powerfactory_matrix.main)
    assert "if len(view_receipts) == 24" in source
    assert "coarse_view: dict[str, object] = view_receipts" in source
    assert "fine_view: dict[str, object] = view_receipts" in source
    assert "load_numeric_csv(execution_dir / str(coarse[\"raw_csv\"]))" not in source
    assert "load_numeric_csv(execution_dir / str(finer_matches[0][\"raw_csv\"]))" not in source


def test_powerfactory_compatibility_derivative_contract(tmp_path: Path) -> None:
    """Bind deterministic source regeneration and the existing derivative owner.

    :return: None.
    """
    source: str = inspect.getsource(prepare_powerfactory_compatibility_cells)
    assert "guid=token" in source
    assert "for pass_index in range(2)" in source
    assert "candidate_members == canonical_members" in source
    assert 'debug_snapshot_members: tuple[str, ...]' in source
    assert '"resources/export_model.json"' in source
    assert '"resources/snapshot.json"' in source
    assert "len(debug_snapshot_receipts) == 4" in source
    assert '"status": "RAW_PROVENANCE_ONLY"' in source
    assert "normalize_export_model" not in source
    assert "Regenerated FMI 3 deterministic non-binary member differs" in source
    assert "build_powerfactory_compatibility_fmu" in source
    assert "len(build_receipts) == 6" in source
    assert "len(initialization_receipts) == 4" in source
    assert "build_powerfactory_initialization_derivative" in source
    initialization_source: str = inspect.getsource(build_powerfactory_initialization_derivative)
    assert "comparison_source_node.tag == comparison_derived_node.tag" in initialization_source
    assert "comparison_source_node.text == comparison_derived_node.text" in initialization_source
    assert "comparison_source_node.tail == comparison_derived_node.tail" in initialization_source
    assert "len(comparison_source_node) == len(comparison_derived_node)" in initialization_source
    assert "expected_attributes == comparison_derived_node.attrib" in initialization_source
    assert "Initialization derivative changed XML outside an authorized start coordinate" in initialization_source
    catalog_root: Path = (
        Path(__file__).resolve().parents[3]
        / "examples"
        / "fmi"
        / "veragrid_standard_examples"
        / "published"
        / "win64"
    )
    catalog_cells: tuple[PowerFactoryCell, ...] = load_catalog_cells(catalog_root)
    tgov_fmi_two_rows: list[PowerFactoryCell] = [
        cell for cell in catalog_cells if cell.model_name == "VGTGOV1_FMI20_CS"
    ]
    tgov_fmi_three_rows: list[PowerFactoryCell] = [
        cell for cell in catalog_cells if cell.model_name == "VGTGOV1_FMI30_CS"
    ]
    esdc_fmi_two_rows: list[PowerFactoryCell] = [
        cell for cell in catalog_cells if cell.model_name == "VGESDC2A_FMI20_CS"
    ]
    esdc_fmi_three_rows: list[PowerFactoryCell] = [
        cell for cell in catalog_cells if cell.model_name == "VGESDC2A_FMI30_CS"
    ]
    gensal_rows: list[PowerFactoryCell] = [
        cell for cell in catalog_cells if cell.model_name == "VGGENSAL_FMI20_CS"
    ]
    assert len(tgov_fmi_two_rows) == 1
    assert len(tgov_fmi_three_rows) == 1
    assert len(esdc_fmi_two_rows) == 1
    assert len(esdc_fmi_three_rows) == 1
    assert len(gensal_rows) == 1
    tgov_fmi_two: PowerFactoryCell = tgov_fmi_two_rows[0]
    fmi_two_path: Path
    fmi_two_receipt: dict[str, object]
    fmi_two_path, fmi_two_receipt = build_powerfactory_initialization_derivative(
        tgov_fmi_two,
        tgov_fmi_two.fmu_path,
        tmp_path / "fmi-two",
    )
    assert fmi_two_receipt["changed_input_count"] == 2
    assert fmi_two_receipt["source_member_differences_from_canonical"] == tuple()
    assert fmi_two_receipt["derived_member_differences_from_canonical"] == ("modelDescription.xml",)
    with zipfile.ZipFile(tgov_fmi_two.fmu_path, "r") as canonical_fmi_two_archive:
        with zipfile.ZipFile(fmi_two_path, "r") as derived_fmi_two_archive:
            assert tuple(sorted(canonical_fmi_two_archive.namelist())) == tuple(sorted(derived_fmi_two_archive.namelist()))
            unchanged_name: str
            for unchanged_name in canonical_fmi_two_archive.namelist():
                if unchanged_name == "modelDescription.xml":
                    pass
                else:
                    assert canonical_fmi_two_archive.read(unchanged_name) == derived_fmi_two_archive.read(unchanged_name)
            derived_fmi_two_xml: ElementTree.Element = ElementTree.fromstring(derived_fmi_two_archive.read("modelDescription.xml"))
    fmi_two_starts: dict[str, float] = dict()
    fmi_two_variable: ElementTree.Element
    for fmi_two_variable in derived_fmi_two_xml.findall("./ModelVariables/ScalarVariable"):
        if fmi_two_variable.attrib.get("name", "") in tgov_fmi_two.input_names and len(fmi_two_variable) == 1:
            fmi_two_starts[str(fmi_two_variable.attrib["name"])] = float(fmi_two_variable[0].attrib["start"])
        else:
            pass
    assert fmi_two_starts == {"OmegaPu_TGOV1": 1.0, "PRefPu_TGOV1": 0.5}
    esdc_fmi_two: PowerFactoryCell = esdc_fmi_two_rows[0]
    esdc_fmi_two_path: Path
    esdc_fmi_two_receipt: dict[str, object]
    esdc_fmi_two_path, esdc_fmi_two_receipt = build_powerfactory_initialization_derivative(
        esdc_fmi_two,
        esdc_fmi_two.fmu_path,
        tmp_path / "esdc-fmi-two",
    )
    assert esdc_fmi_two_path.is_file()
    assert esdc_fmi_two_receipt["changed_input_count"] == 2
    assert esdc_fmi_two_receipt["derived_member_differences_from_canonical"] == ("modelDescription.xml",)
    missing_input_cell: PowerFactoryCell = PowerFactoryCell(
        tgov_fmi_two.family,
        tgov_fmi_two.version,
        tgov_fmi_two.interface,
        tgov_fmi_two.model_name,
        tgov_fmi_two.fmu_path,
        tgov_fmi_two.fmu_sha256,
        ("OmegaPu_TGOV1",),
        tgov_fmi_two.output_names,
        tgov_fmi_two.schedule_path,
        tgov_fmi_two.reference_path,
        tgov_fmi_two.stop_time,
    )
    with pytest.raises(ValueError, match="missing, reordered or extended"):
        build_powerfactory_initialization_derivative(
            missing_input_cell,
            missing_input_cell.fmu_path,
            tmp_path / "missing-input",
        )
    extra_input_cell: PowerFactoryCell = PowerFactoryCell(
        tgov_fmi_two.family,
        tgov_fmi_two.version,
        tgov_fmi_two.interface,
        tgov_fmi_two.model_name,
        tgov_fmi_two.fmu_path,
        tgov_fmi_two.fmu_sha256,
        ("OmegaPu_TGOV1", "PRefPu_TGOV1", "UnexpectedPu_TGOV1"),
        tgov_fmi_two.output_names,
        tgov_fmi_two.schedule_path,
        tgov_fmi_two.reference_path,
        tgov_fmi_two.stop_time,
    )
    reordered_input_cell: PowerFactoryCell = PowerFactoryCell(
        tgov_fmi_two.family,
        tgov_fmi_two.version,
        tgov_fmi_two.interface,
        tgov_fmi_two.model_name,
        tgov_fmi_two.fmu_path,
        tgov_fmi_two.fmu_sha256,
        ("PRefPu_TGOV1", "OmegaPu_TGOV1"),
        tgov_fmi_two.output_names,
        tgov_fmi_two.schedule_path,
        tgov_fmi_two.reference_path,
        tgov_fmi_two.stop_time,
    )
    with pytest.raises(ValueError, match="missing, reordered or extended"):
        build_powerfactory_initialization_derivative(extra_input_cell, extra_input_cell.fmu_path, tmp_path / "extra-input")
    with pytest.raises(ValueError, match="missing, reordered or extended"):
        build_powerfactory_initialization_derivative(reordered_input_cell, reordered_input_cell.fmu_path, tmp_path / "reordered-input")
    altered_schedule_path: Path = tmp_path / "altered-initial-row.csv"
    altered_schedule_text: str = tgov_fmi_two.schedule_path.read_text(encoding="utf-8").replace(
        "0.0,1.0,0.5",
        "0.0,0.99,0.5",
        1,
    )
    altered_schedule_path.write_text(altered_schedule_text, encoding="utf-8", newline="")
    altered_schedule_cell: PowerFactoryCell = PowerFactoryCell(
        tgov_fmi_two.family,
        tgov_fmi_two.version,
        tgov_fmi_two.interface,
        tgov_fmi_two.model_name,
        tgov_fmi_two.fmu_path,
        tgov_fmi_two.fmu_sha256,
        tgov_fmi_two.input_names,
        tgov_fmi_two.output_names,
        altered_schedule_path,
        tgov_fmi_two.reference_path,
        tgov_fmi_two.stop_time,
    )
    with pytest.raises(ValueError, match="schedule identity changed"):
        build_powerfactory_initialization_derivative(altered_schedule_cell, altered_schedule_cell.fmu_path, tmp_path / "altered-row-zero")
    with pytest.raises(ValueError, match="limited to four reviewed CS cells"):
        build_powerfactory_initialization_derivative(
            gensal_rows[0],
            gensal_rows[0].fmu_path,
            tmp_path / "wrong-cell",
        )
    tgov_fmi_three: PowerFactoryCell = tgov_fmi_three_rows[0]
    callback_source: Path = tmp_path / "fmi-three-callback.fmu"
    with zipfile.ZipFile(tgov_fmi_three.fmu_path, "r") as canonical_fmi_three_archive:
        with zipfile.ZipFile(callback_source, "x") as callback_archive:
            callback_info: zipfile.ZipInfo
            for callback_info in canonical_fmi_three_archive.infolist():
                callback_bytes: bytes = canonical_fmi_three_archive.read(callback_info.filename)
                if callback_info.filename.endswith(".dll"):
                    changed_binary: bytearray = bytearray(callback_bytes)
                    changed_binary[-1] = changed_binary[-1] ^ 1
                    callback_bytes = bytes(changed_binary)
                else:
                    pass
                callback_archive.writestr(callback_info, callback_bytes)
    fmi_three_path: Path
    fmi_three_receipt: dict[str, object]
    fmi_three_path, fmi_three_receipt = build_powerfactory_initialization_derivative(
        tgov_fmi_three,
        callback_source,
        tmp_path / "fmi-three",
    )
    assert fmi_three_path.is_file()
    assert fmi_three_receipt["changed_input_count"] == 2
    assert len(fmi_three_receipt["derived_member_differences_from_canonical"]) == 2
    fmi_two_binary_drift: Path = tmp_path / "fmi-two-binary-drift.fmu"
    with zipfile.ZipFile(tgov_fmi_two.fmu_path, "r") as canonical_fmi_two_archive:
        with zipfile.ZipFile(fmi_two_binary_drift, "x") as fmi_two_drift_archive:
            fmi_two_drift_info: zipfile.ZipInfo
            for fmi_two_drift_info in canonical_fmi_two_archive.infolist():
                fmi_two_drift_bytes: bytes = canonical_fmi_two_archive.read(fmi_two_drift_info.filename)
                if fmi_two_drift_info.filename.endswith(".dll"):
                    changed_fmi_two_binary: bytearray = bytearray(fmi_two_drift_bytes)
                    changed_fmi_two_binary[-1] = changed_fmi_two_binary[-1] ^ 1
                    fmi_two_drift_bytes = bytes(changed_fmi_two_binary)
                else:
                    pass
                fmi_two_drift_archive.writestr(fmi_two_drift_info, fmi_two_drift_bytes)
    with pytest.raises(ValueError, match="prior derivative contract"):
        build_powerfactory_initialization_derivative(tgov_fmi_two, fmi_two_binary_drift, tmp_path / "fmi-two-binary-rejected")
    esdc_fmi_three: PowerFactoryCell = esdc_fmi_three_rows[0]
    esdc_callback_source: Path = tmp_path / "esdc-fmi-three-callback.fmu"
    with zipfile.ZipFile(esdc_fmi_three.fmu_path, "r") as canonical_esdc_fmi_three_archive:
        with zipfile.ZipFile(esdc_callback_source, "x") as esdc_callback_archive:
            esdc_callback_info: zipfile.ZipInfo
            for esdc_callback_info in canonical_esdc_fmi_three_archive.infolist():
                esdc_callback_bytes: bytes = canonical_esdc_fmi_three_archive.read(esdc_callback_info.filename)
                if esdc_callback_info.filename.endswith(".dll"):
                    changed_esdc_binary: bytearray = bytearray(esdc_callback_bytes)
                    changed_esdc_binary[-1] = changed_esdc_binary[-1] ^ 1
                    esdc_callback_bytes = bytes(changed_esdc_binary)
                else:
                    pass
                esdc_callback_archive.writestr(esdc_callback_info, esdc_callback_bytes)
    esdc_fmi_three_path: Path
    esdc_fmi_three_receipt: dict[str, object]
    esdc_fmi_three_path, esdc_fmi_three_receipt = build_powerfactory_initialization_derivative(
        esdc_fmi_three,
        esdc_callback_source,
        tmp_path / "esdc-fmi-three",
    )
    assert esdc_fmi_three_path.is_file()
    assert esdc_fmi_three_receipt["changed_input_count"] == 2
    total_changed_inputs: int = int(fmi_two_receipt["changed_input_count"]) + int(esdc_fmi_two_receipt["changed_input_count"]) + int(fmi_three_receipt["changed_input_count"]) + int(esdc_fmi_three_receipt["changed_input_count"])
    assert total_changed_inputs == 8
    drift_source: Path = tmp_path / "fmi-three-resource-drift.fmu"
    with zipfile.ZipFile(callback_source, "r") as callback_archive:
        with zipfile.ZipFile(drift_source, "x") as drift_archive:
            drift_info: zipfile.ZipInfo
            for drift_info in callback_archive.infolist():
                drift_bytes: bytes = callback_archive.read(drift_info.filename)
                if drift_info.filename == "documentation/SOURCE.md":
                    drift_bytes = drift_bytes + b"\nunauthorized drift\n"
                else:
                    pass
                drift_archive.writestr(drift_info, drift_bytes)
    with pytest.raises(ValueError, match="prior derivative contract"):
        build_powerfactory_initialization_derivative(
            tgov_fmi_three,
            drift_source,
            tmp_path / "resource-drift",
        )
    duplicated_xml_source: Path = tmp_path / "fmi-three-duplicated-xml-coordinate.fmu"
    with zipfile.ZipFile(callback_source, "r") as callback_archive:
        with zipfile.ZipFile(duplicated_xml_source, "x") as duplicated_xml_archive:
            duplicated_xml_info: zipfile.ZipInfo
            for duplicated_xml_info in callback_archive.infolist():
                duplicated_xml_bytes: bytes = callback_archive.read(duplicated_xml_info.filename)
                if duplicated_xml_info.filename == "modelDescription.xml":
                    original_duplicated_xml_bytes: bytes = duplicated_xml_bytes
                    duplicated_xml_bytes = duplicated_xml_bytes.replace(
                        b"<Float64 name=\"OmegaPu_TGOV1\"",
                        b"<Float64 name=\"DuplicatedPu_TGOV1\" start=\"0\"/><Float64 name=\"OmegaPu_TGOV1\"",
                        1,
                    )
                    assert duplicated_xml_bytes != original_duplicated_xml_bytes
                else:
                    pass
                duplicated_xml_archive.writestr(duplicated_xml_info, duplicated_xml_bytes)
    with pytest.raises(ValueError, match="prior derivative contract"):
        build_powerfactory_initialization_derivative(
            tgov_fmi_three,
            duplicated_xml_source,
            tmp_path / "duplicated-xml-rejected",
        )
    extra_xml_source: Path = tmp_path / "fmi-three-extra-xml-attribute.fmu"
    with zipfile.ZipFile(callback_source, "r") as callback_archive:
        with zipfile.ZipFile(extra_xml_source, "x") as extra_xml_archive:
            extra_xml_info: zipfile.ZipInfo
            for extra_xml_info in callback_archive.infolist():
                extra_xml_bytes: bytes = callback_archive.read(extra_xml_info.filename)
                if extra_xml_info.filename == "modelDescription.xml":
                    extra_xml_root: ElementTree.Element = ElementTree.fromstring(extra_xml_bytes)
                    extra_xml_root.set("unauthorizedPowerFactoryAttribute", "1")
                    extra_xml_bytes = ElementTree.tostring(extra_xml_root, encoding="utf-8", xml_declaration=True)
                else:
                    pass
                extra_xml_archive.writestr(extra_xml_info, extra_xml_bytes)
    with pytest.raises(ValueError, match="prior derivative contract"):
        build_powerfactory_initialization_derivative(
            tgov_fmi_three,
            extra_xml_source,
            tmp_path / "extra-xml-rejected",
        )
    pe: bytearray = bytearray(512)
    pe[0:2] = b"MZ"
    struct.pack_into("<I", pe, 0x3C, 64)
    pe[64:68] = b"PE\x00\x00"
    struct.pack_into("<H", pe, 68 + 2, 1)
    struct.pack_into("<I", pe, 68 + 4, 1234)
    struct.pack_into("<H", pe, 68 + 16, 240)
    struct.pack_into("<H", pe, 88, 0x20B)
    struct.pack_into("<I", pe, 88 + 108, 7)
    struct.pack_into("<II", pe, 88 + 112 + 6 * 8, 0x1000, 28)
    section_offset: int = 88 + 240
    struct.pack_into("<IIII", pe, section_offset + 8, 128, 0x1000, 128, 384)
    struct.pack_into("<I", pe, 384 + 4, 1234)
    normalized: bytes
    receipt: dict[str, object]
    normalized, receipt = inspect_pe_timestamp_normalized_binary(bytes(pe))
    assert receipt["timestamp_ranges"] == [{"offset": 72, "length": 4, "value": 1234}, {"offset": 388, "length": 4, "value": 1234}]
    assert normalized[72:76] == b"\x00" * 4
    assert normalized[388:392] == b"\x00" * 4
    truncated: bytes = bytes(pe[:70])
    with pytest.raises(ValueError):
        inspect_pe_timestamp_normalized_binary(truncated)
    bad_signature: bytearray = bytearray(pe)
    bad_signature[64:68] = b"NOPE"
    with pytest.raises(ValueError):
        inspect_pe_timestamp_normalized_binary(bytes(bad_signature))
    bad_magic: bytearray = bytearray(pe)
    struct.pack_into("<H", bad_magic, 88, 0)
    with pytest.raises(ValueError):
        inspect_pe_timestamp_normalized_binary(bytes(bad_magic))
    invalid_rva: bytearray = bytearray(pe)
    struct.pack_into("<I", invalid_rva, 88 + 112 + 6 * 8, 0x9000)
    with pytest.raises(ValueError):
        inspect_pe_timestamp_normalized_binary(bytes(invalid_rva))
    ambiguous_rva: bytearray = bytearray(pe)
    struct.pack_into("<H", ambiguous_rva, 68 + 2, 2)
    second_section_offset: int = section_offset + 40
    struct.pack_into("<IIII", ambiguous_rva, second_section_offset + 8, 128, 0x1000, 128, 384)
    with pytest.raises(ValueError):
        inspect_pe_timestamp_normalized_binary(bytes(ambiguous_rva))
    invalid_debug_size: bytearray = bytearray(pe)
    struct.pack_into("<I", invalid_debug_size, 88 + 112 + 6 * 8 + 4, 27)
    with pytest.raises(ValueError):
        inspect_pe_timestamp_normalized_binary(bytes(invalid_debug_size))
    assert "len(candidate_binary) == len(canonical_binary)" in source
    assert "set(differences).issubset(allowed_offsets)" in source
    assert "regenerated_binary_hashes[0] == regenerated_binary_hashes[1]" in source


def test_isolated_worker_matrix_contract() -> None:
    """Require one child, checkpoint, ACK and marker per fixed job.

    :return: None.
    """
    worker_source: str = inspect.getsource(run_powerfactory_cell_worker)
    supervisor_source: str = inspect.getsource(supervisor_main)
    master_source: str = inspect.getsource(write_matrix_release_checkpoint)
    assert "return main(arguments, run_nonce, job)" in worker_source
    assert "if len(jobs) == 24" in supervisor_source
    assert "parent-checkpoint-ack.json" in supervisor_source
    assert "worker-ack-validated.json" in supervisor_source
    assert "worker_exit_value == 0" in supervisor_source
    assert "len(child_records) == 24" in supervisor_source
    assert "powerfactory_standard_matrix_checkpoint" in master_source


def test_cominc_diagnostic_contract(tmp_path: Path) -> None:
    """Require nonce-bound project identity and the exact standard FMU hash.

    :param tmp_path: Pytest-owned evidence directory.
    :return: None.
    """
    nonce: str = "a" * 64
    project_name: str = "VG_StandardMatrix_" + nonce[:12]
    journal_path: Path = tmp_path / "mutation-journal.jsonl"
    record: dict[str, object] = {
        "operation": "BOOTSTRAP_CREATE_PROJECT",
        "parent_full_name": "\\andre.IntUser",
        "parent_class": "IntUser",
        "name": project_name,
        "grid_name": "StandardMatrixGrid",
        "verified_absent": True,
    }
    journal_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    actual_name: str
    actual_full_name: str
    actual_name, actual_full_name = read_bootstrap_identity(journal_path, nonce)
    assert actual_name == project_name
    assert actual_full_name == "\\andre.IntUser\\" + project_name + ".IntPrj"
    catalog_root: Path = (
        Path(__file__).resolve().parents[3]
        / "examples"
        / "fmi"
        / "veragrid_standard_examples"
        / "published"
        / "win64"
    )
    matching_hashes: tuple[str, ...] = tuple(
        cell.fmu_sha256
        for cell in load_catalog_cells(catalog_root)
        if cell.family == "GENSAL" and cell.version == "2.0" and cell.interface == "cs"
    )
    assert matching_hashes == ("58d4f4377be92d96d13a06425700d7b082307bc0694993520e1bfd789a886916",)
    with pytest.raises(ValueError):
        read_bootstrap_identity(journal_path, "b" * 64)


def test_native_exit_attribution() -> None:
    """Do not classify an ordinary worker return as a native crash.

    :return: None.
    """
    binding: Path = Path(r"C:\Program Files\DIgSILENT\PowerFactory 2025 SP4\Python\3.11\powerfactory.pyd")
    result: dict[str, object] = classify_native_exit(1234, datetime.now(timezone.utc), binding, 0)
    assert result == {"status": "NOT_APPLICABLE", "worker_exit_code": 0}
