from __future__ import annotations

from pathlib import Path
import zipfile

import numpy as np
import pytest
from fmpy import simulate_fmu

from VeraGridEngine.enumerations import FmiVersion, InterfaceType
from VeraGridEngine.IO.fmu.interface import export_model_as_fmu
from VeraGridEngine.IO.fmu.CosimulationInterface.build import host_build_capable
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var
from VeraGridEngine.IO.fmu.config import ExportConfig
from VeraGridEngine.IO.fmu.CosimulationInterface.export_ir import build_export_model
from VeraGridEngine.IO.fmu.model import flatten_block
from VeraGridEngine.IO.fmu.archive import package_fmu, prepare_fmu_staging_dir
from VeraGridEngine.IO.fmu.logic import build_co_simulation_logic_entries
from VeraGridEngine.IO.fmu.model import build_model_snapshot, reconstruct_block
from VeraGridEngine.IO.fmu.CosimulationInterface.xml_writer import emit_model_description
from VeraGridEngine.IO.fmu.config import ExportConfig as MeExportConfig


def build_simple_block() -> Block:
    x = Var("x")
    dx = Var("dx", base_var=x)
    y = Var("y")
    u = Var("u")
    p = Var("p")
    mode = Var("mode")

    child = Block(
        state_vars=[x],
        state_eqs=[-x + u + p],
        algebraic_vars=[y],
        algebraic_eqs=[y - x],
        diff_vars=[dx],
        parameters={p: Const(2.0)},
        init_values={x: Const(1.0), y: Const(1.0)},
        init_eqs={y: x},
        event_dict={mode: Const(1.0)},
        in_vars=[u],
        out_vars=[y],
    )
    return Block(children=[child], name="SimpleModel")


def test_snapshot_roundtrip_and_flatten() -> None:
    block = build_simple_block()
    snapshot = build_model_snapshot(block)
    restored = reconstruct_block(snapshot)
    flat = flatten_block(restored)

    assert len(flat.children) == 0
    assert len(flat.state_vars) == 1
    assert len(flat.algebraic_vars) == 1
    assert len(flat.diff_vars) == 1
    assert len(flat.in_vars) == 1
    assert len(flat.out_vars) == 1
    assert flat.parameters
    assert flat.event_dict


def test_export_ir_and_xml_generation(tmp_path: Path) -> None:
    block = build_simple_block()
    snapshot = build_model_snapshot(block)
    flat = flatten_block(block)
    cfg = ExportConfig(model_name="SimpleModel", output_path=tmp_path / "simple.fmu", compile_binary=False)
    logic_entries = build_co_simulation_logic_entries(flat)
    export_model = build_export_model(flat, cfg, snapshot, logic_entries)
    xml_text = emit_model_description(export_model)

    assert export_model.counts["states"] == 1
    assert export_model.counts["algebraics"] == 1
    assert export_model.counts["inputs"] == 1
    assert export_model.counts["outputs"] == 1
    assert 'modelName="SimpleModel"' in xml_text
    assert "<CoSimulation" in xml_text
    assert 'name="y"' in xml_text


def test_packager_creates_fmu_zip(tmp_path: Path) -> None:
    staging = prepare_fmu_staging_dir(tmp_path / "staging")
    (staging / "modelDescription.xml").write_text("<xml />", encoding="utf-8")
    (staging / "resources" / "manifest.json").write_text("{}", encoding="utf-8")
    output = package_fmu(staging, tmp_path / "demo.fmu")

    assert output.exists()
    with zipfile.ZipFile(output) as archive:
        assert "modelDescription.xml" in archive.namelist()
        assert "resources/manifest.json" in archive.namelist()


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_cs_export_failure_removes_owned_build_root(tmp_path: Path) -> None:
    """Remove the automatic CS build root when packaging fails.

    :param tmp_path: Isolated exporter output directory supplied by pytest.
    :return: None.
    """

    blocked_output_path: Path = tmp_path / "blocked_cs.fmu"
    blocked_output_path.mkdir()
    cfg: ExportConfig = ExportConfig(
        model_name="CleanupCsModel",
        output_path=blocked_output_path,
        compile_binary=True,
        keep_build_dir=False,
    )

    with pytest.raises(OSError):
        export_model_as_fmu(model=build_simple_block(), cfg=cfg)

    automatic_build_roots: tuple[Path, ...] = tuple(
        tmp_path.glob("veragrid_fmu_build_*")
    )
    assert automatic_build_roots == tuple()


@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_me_export_failure_removes_owned_build_root(tmp_path: Path) -> None:
    """Remove the automatic ME build root when packaging fails.

    :param tmp_path: Isolated exporter output directory supplied by pytest.
    :return: None.
    """

    blocked_output_path: Path = tmp_path / "blocked_me.fmu"
    blocked_output_path.mkdir()
    cfg: MeExportConfig = MeExportConfig(
        interface_type=InterfaceType.MODEL_EXCHANGE,
        model_name="CleanupMeModel",
        output_path=blocked_output_path,
        compile_binary=True,
        keep_build_dir=False,
    )

    with pytest.raises(OSError):
        export_model_as_fmu(model=build_simple_block(), cfg=cfg)

    automatic_build_roots: tuple[Path, ...] = tuple(
        tmp_path.glob("veragrid_fmu_me_build_*")
    )
    assert automatic_build_roots == tuple()


@pytest.mark.parametrize(
    "fmi_version",
    (
        FmiVersion.FMI_1_0,
        FmiVersion.FMI_2_0,
        FmiVersion.FMI_3_0,
    ),
)
@pytest.mark.skipif(not host_build_capable(), reason="No usable host build toolchain available")
def test_me_export_accepts_exact_continuous_state_start_values(
    tmp_path: Path,
    fmi_version: FmiVersion,
) -> None:
    """Apply an exact ME state start through each version's real setter.

    :param tmp_path: Isolated export and simulation directory supplied by pytest.
    :param fmi_version: FMI standard version selected for the compiled FMU.
    :return: None.
    """

    # The declared default is deliberately different from the importer-provided
    # value so the trajectory proves that the generated setter accepted the write.
    state: Var = Var("x")
    derivative: Var = Var("dx", base_var=state)
    source_block: Block = Block(
        state_vars=list((state,)),
        state_eqs=list((Const(1.0),)),
        diff_vars=list((derivative,)),
        init_values=dict(((state, Const(0.0)),)),
        out_vars=list((state,)),
        name="ExactStateStart",
    )
    model_identifier: str = "ExactStateStart" + fmi_version.value.replace(".", "")
    archive_path: Path = export_model_as_fmu(
        model=source_block,
        cfg=MeExportConfig(
            interface_type=InterfaceType.MODEL_EXCHANGE,
            model_name=model_identifier,
            output_path=tmp_path / (model_identifier + ".fmu"),
            fixed_step=1.0e-3,
            fmi_version=fmi_version,
        ),
    )

    # FMPy follows the same importer sequence observed in Simulink: it writes the
    # exact state through fmiSetReal/fmi2SetReal/fmi3SetFloat64 before initialize.
    result: np.ndarray = simulate_fmu(
        filename=str(archive_path),
        start_time=0.0,
        stop_time=2.0e-3,
        step_size=1.0e-3,
        output_interval=1.0e-3,
        output=("x",),
        start_values=dict(x=2.0),
    )
    expected_times: np.ndarray = np.array((0.0, 1.0e-3, 2.0e-3), dtype=float)
    np.testing.assert_allclose(result["time"], expected_times, rtol=0.0, atol=1.0e-15)
    np.testing.assert_allclose(result["x"][0], 2.0, rtol=0.0, atol=1.0e-12)
    np.testing.assert_allclose(
        result["x"],
        2.0 + result["time"],
        rtol=0.0,
        atol=1.0e-8,
    )
