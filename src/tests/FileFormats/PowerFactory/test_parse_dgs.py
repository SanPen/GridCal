# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

import pytest
from pathlib import Path
import pandas as pd
import numpy as np
from types import SimpleNamespace

import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_objects import ElmGenstat, ElmSind, ElmLne, ElmLnesec
from VeraGridEngine.IO.dgs.dgs_to_veragrid import _add_elmgenstat_devices, _apply_elmtow_tower_coupling, convert_dgs_to_line
from VeraGridEngine.enumerations import (DeviceType, GeneratorControlMode, ShuntConnectionType,
                                         StaticGeneratorControlMode, ConverterControlType)
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.Simulations.PowerFlow3ph.Formulations.positive_sequence_control import PositiveSequenceControl
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.IO.dgs.veragrid_to_dgs import circuit_to_dgs


@pytest.mark.parametrize("parallel_count", (1, 2))
@pytest.mark.parametrize(
    "category,control_mode,use_vsc,out_of_service,expected_device",
    (("Wind", "constv", False, False, DeviceType.GeneratorDevice),
     ("Wind", "constv", False, True, DeviceType.GeneratorDevice),
     ("Other", "constv", False, False, DeviceType.GeneratorDevice),
     ("Wind", "constq", False, False, DeviceType.StaticGeneratorDevice),
     ("Wind", "constq", True, False, DeviceType.VscDevice),
     ("Wind", "constv", True, False, DeviceType.VscDevice),
     ("Storage", "vdroop", False, False, DeviceType.StaticGeneratorDevice),
     ("Storage", "vdroop", False, True, DeviceType.StaticGeneratorDevice),
     ("Storage", "vdroop", True, False, DeviceType.VscDevice),
     ("Storage", "vdroop", True, True, DeviceType.VscDevice),
     ("Storage", "constq", False, False, DeviceType.BatteryDevice),
     ("Storage", "constq", True, False, DeviceType.BatteryDevice)),
)
def test_dgs_static_generator_voltage_control_mapping(
        category: str, control_mode: str, use_vsc: bool, out_of_service: bool,
        expected_device: DeviceType, parallel_count: int,
) -> None:
    """Preserve PV and storage droop while respecting explicit VSC selection.

    :param category: Technology label in the DGS element.
    :param control_mode: Native PowerFactory voltage/reactive-power mode.
    :param use_vsc: Explicit converter import option.
    :param out_of_service: Source element availability.
    :param expected_device: Expected VeraGrid device category.
    :param parallel_count: Number of units represented by the source element.
    :return: None.
    """
    # Exercise real DGS objects and existing converters, with synthetic public data.
    dgs_grid: DgsCircuit = DgsCircuit()
    source: ElmGenstat = ElmGenstat()
    source.ID = "wind-generator"
    source.loc_name = "Wind generator"
    source.cCategory = category
    source.av_mode = control_mode
    source.outserv = int(out_of_service)
    source.ngnum = parallel_count
    source.pgini = 19.2
    source.qgini = 2.5
    source.sgn = 50.0
    source.usetp = 1.01
    source.ddroop, source.usp_min, source.usp_max = 2.5, 0.92, 1.08
    source.phtech, source.nneutral = 1, 0
    source.r0, source.x0, source.r2, source.x2 = 0.01, 0.08, 0.02, 0.10
    dgs_grid.elmgenstats.append(source)
    grid: dev.MultiCircuit = dev.MultiCircuit()
    bus: dev.Bus = grid.add_bus(dev.Bus(name="Terminal", Vnom=33.0))
    _add_elmgenstat_devices(
        dgs_grid=dgs_grid, grid=grid,
        stacubic_dict=dict(((source.ID, list((0,))),)),
        use_vsc_for_injections=use_vsc, logger=Logger(),
        cubics_by_objid=dict(), bus_by_term_id=dict(),
    )

    # Only the requested representation is created, including parallel units and state.
    devices: list[dev.Generator | dev.StaticGenerator | dev.VSC] = list(
        grid.get_elements_by_type(device_type=expected_device)
    )
    assert len(devices) == parallel_count
    assert (len(grid.generators) + len(grid.static_generators) + len(grid.vsc_devices)
            + len(grid.batteries)) == parallel_count
    assert len(grid.buses) == 1 + (parallel_count if expected_device == DeviceType.VscDevice else 0)
    assert len(set(device.idtag for device in devices)) == parallel_count
    device: dev.Generator | dev.StaticGenerator | dev.VSC
    for device in devices:
        assert device.active == (not out_of_service)
        if isinstance(device, dev.Battery):
            assert device.bus is bus
            assert device.P == source.pgini and device.Q == source.qgini
            assert device.control_mode == GeneratorControlMode.Q
        elif isinstance(device, dev.Generator):
            assert device.bus is bus
            assert device.P == source.pgini and device.Snom == source.sgn
            assert device.control_mode == GeneratorControlMode.V
            assert device.Vset == source.usetp
        elif isinstance(device, dev.StaticGenerator):
            assert device.bus is bus
            assert device.P == source.pgini and device.Q == source.qgini
            if category == 'Storage' and control_mode == 'vdroop':
                assert device.control_mode == StaticGeneratorControlMode.QVDroop
                assert device.Snom == source.sgn and device.Vset == source.usetp
                assert device.droop == source.ddroop
                assert device.Vset_min == source.usp_min and device.Vset_max == source.usp_max
                assert device.conn == ShuntConnectionType.GroundedStar
                np.testing.assert_allclose((device.R0, device.X0, device.R2, device.X2),
                    np.array((source.r0, source.x0, source.r2, source.x2)) * grid.Sbase / source.sgn)
            else:
                assert device.control_mode == StaticGeneratorControlMode.PQ
        else:
            assert device.bus_to is bus
            assert device.bus_from.is_dc
            if control_mode == 'vdroop':
                assert device.control1 == ConverterControlType.Pac
                assert device.control2 == ConverterControlType.Q_droop
                assert device.control1_val == -source.pgini and device.control2_val == -source.qgini
                assert device.control2_val_droop == source.ddroop
                assert device.control2_droop_val == source.usetp
                assert device.control2_droop_val_min == source.usp_min
                assert device.control2_droop_val_max == source.usp_max
            else:
                pass


@pytest.mark.parametrize("Sbase,parallel_count", ((100.0, 1), (25.0, 2)))
@pytest.mark.parametrize("technology,neutral,connection",
                         ((0, 0, ShuntConnectionType.FloatingStar),
                          (1, 0, ShuntConnectionType.GroundedStar),
                          (1, 1, ShuntConnectionType.NeutralStar),
                          (1, 2, ShuntConnectionType.NeutralStar),
                          (1, None, None), (None, None, None), (2, 0, None)))
def test_dgs_generator_sequence_connection_and_bases(
        tmp_path: Path, Sbase: float, parallel_count: int, technology: int | None,
        neutral: int | None, connection: ShuntConnectionType | None,
) -> None:
    """Respect the exported return path and each parallel machine's power base.

    :param tmp_path: Isolated DGS round-trip directory.
    :param Sbase: Network power base in MVA.
    :param parallel_count: Number of identical machines exported in one element.
    :param technology: PowerFactory phase technology, or an absent export field.
    :param neutral: PowerFactory neutral connection, or an absent export field.
    :param connection: Expected physical connection, or missing/unsupported source data.
    :return: None.
    """
    source: ElmGenstat = ElmGenstat()
    source.ID = "sequence-generator"
    source.loc_name = "Sequence generator"
    source.cCategory = "Wind"
    source.av_mode = "constv"
    source.phtech = technology
    source.nneutral = neutral
    source.sgn = 50.0
    source.ngnum = parallel_count
    source.r0, source.x0 = 0.0, 0.10
    source.r2, source.x2 = 0.01, 0.15
    exported: DgsCircuit = DgsCircuit()
    exported.elmgenstats.append(source)
    path: Path = tmp_path / "generator_sequences.dgs"
    exported.write_dgs(path=str(path))
    imported: DgsCircuit = DgsCircuit()
    imported.parse_dgs(path=str(path))
    assert imported.elmgenstats[0].phtech == technology
    assert imported.elmgenstats[0].nneutral == neutral
    assert imported.elmgenstats[0].r0 == 0.0

    grid: dev.MultiCircuit = dev.MultiCircuit(Sbase=Sbase)
    grid.add_bus(dev.Bus(name="Terminal", Vnom=33.0))
    logger: Logger = Logger()
    _add_elmgenstat_devices(
        dgs_grid=imported, grid=grid,
        stacubic_dict=dict(((source.ID, list((0,))),)),
        use_vsc_for_injections=False, logger=logger,
        cubics_by_objid=dict(), bus_by_term_id=dict(),
    )
    assert len(grid.generators) == parallel_count
    gen: dev.Generator
    for gen in grid.generators:
        if connection is not None:
            assert gen.conn == connection
            assert complex(gen.R2, gen.X2) == pytest.approx(complex(0.01, 0.15) * Sbase / 50.0)
            # A blocked connection retains its data without activating a return path.
            assert complex(gen.R0, gen.X0) == pytest.approx(0.10j * Sbase / 50.0)
        else:
            assert len(logger.entries) > 0
    numerical: NumericalCircuit = compile_numerical_circuit_at(circuit=grid, fill_three_phase=True)
    if connection is None or connection == ShuntConnectionType.NeutralStar:
        # Invalid source data or an explicit neutral must never become an implicit ground.
        with pytest.raises(ValueError, match='finite and nonzero|explicit neutral'):
            PositiveSequenceControl(numerical, np.arange(4))
    else:
        controls: PositiveSequenceControl = PositiveSequenceControl(numerical, np.arange(4))
        assert len(controls.bus_idx) == 1


@pytest.mark.parametrize("r0,x0,r2,x2,sgn,valid_zero,valid_negative",
                         ((None, None, None, None, 50.0, False, False),
                          (0.0, None, None, 0.15, 50.0, False, False),
                          (0.0, 0.0, 0.0, 0.0, 50.0, False, False),
                          (np.nan, 0.1, 0.01, np.inf, 50.0, False, False),
                          (0.0, 0.1, 0.01, 0.15, 0.0, False, False),
                          (0.0, 0.1, None, None, 50.0, True, False),
                          (None, None, 0.01, 0.15, 50.0, False, True)))
def test_dgs_missing_or_invalid_generator_sequences(
        r0: float | None, x0: float | None, r2: float | None, x2: float | None,
        sgn: float, valid_zero: bool, valid_negative: bool,
) -> None:
    """Report missing data and reject an incomplete U1 model before solving.

    :param r0: Optional zero-sequence resistance.
    :param x0: Optional zero-sequence reactance.
    :param r2: Optional negative-sequence resistance.
    :param x2: Optional negative-sequence reactance.
    :param sgn: Machine base in MVA.
    :param valid_zero: Whether usable Z0 data were exported.
    :param valid_negative: Whether usable Z2 data were exported.
    :return: None.
    """
    source: ElmGenstat = ElmGenstat()
    source.ID = "incomplete-generator"
    source.av_mode = "constv"
    source.phtech, source.nneutral = 1, 0
    source.sgn = sgn
    source.r0, source.x0, source.r2, source.x2 = r0, x0, r2, x2
    dgs_grid: DgsCircuit = DgsCircuit()
    dgs_grid.elmgenstats.append(source)
    grid: dev.MultiCircuit = dev.MultiCircuit()
    grid.add_bus(dev.Bus(name="Terminal", Vnom=33.0))
    logger: Logger = Logger()
    _add_elmgenstat_devices(
        dgs_grid=dgs_grid, grid=grid,
        stacubic_dict=dict(((source.ID, list((0,))),)),
        use_vsc_for_injections=False, logger=logger,
        cubics_by_objid=dict(), bus_by_term_id=dict(),
    )
    gen: dev.Generator = grid.generators[0]
    assert bool(abs(complex(gen.R0, gen.X0)) >= 1e-12) == valid_zero
    assert bool(abs(complex(gen.R2, gen.X2)) >= 1e-12) == valid_negative
    assert len(logger.entries) > 0
    numerical: NumericalCircuit = compile_numerical_circuit_at(circuit=grid, fill_three_phase=True)
    with pytest.raises(ValueError, match='finite and nonzero'):
        PositiveSequenceControl(numerical, np.arange(4))


def test_elm_sind_writer_preserves_resistance_envelope(
        tmp_path: Path,
) -> None:
    """Preserve legacy and enriched ``ElmSind.s:Rin`` table semantics.

    :param tmp_path: Isolated directory for generated DGS files.
    :return: None.
    """
    legacy_circuit: DgsCircuit = DgsCircuit()
    legacy_element: ElmSind = ElmSind()
    legacy_element.ID = "legacy-series-impedance"
    legacy_circuit.elmsinds.append(legacy_element)
    legacy_path: Path = tmp_path / "legacy_elm_sind.dgs"
    legacy_circuit.write_dgs(path=str(legacy_path))
    legacy_text: str = legacy_path.read_text(encoding="utf-8")
    assert "s:Rin(r)" not in legacy_text

    legacy_roundtrip: DgsCircuit = DgsCircuit()
    legacy_roundtrip.parse_dgs(path=str(legacy_path))
    assert len(legacy_roundtrip.elmsinds) == 1
    assert not legacy_roundtrip.elmsinds[0].initial_resistance_column_declared
    assert legacy_roundtrip.elmsinds[0].Rin is None

    enriched_circuit: DgsCircuit = DgsCircuit()
    enriched_element: ElmSind = ElmSind()
    enriched_element.ID = "enriched-series-impedance"
    enriched_element.Rin = 99999.0
    enriched_element.initial_resistance_column_declared = True
    enriched_circuit.elmsinds.append(enriched_element)
    enriched_path: Path = tmp_path / "enriched_elm_sind.dgs"
    enriched_circuit.write_dgs(path=str(enriched_path))
    enriched_text: str = enriched_path.read_text(encoding="utf-8")
    assert "s:Rin(r)" in enriched_text

    enriched_roundtrip: DgsCircuit = DgsCircuit()
    enriched_roundtrip.parse_dgs(path=str(enriched_path))
    assert len(enriched_roundtrip.elmsinds) == 1
    assert enriched_roundtrip.elmsinds[0].initial_resistance_column_declared
    assert enriched_roundtrip.elmsinds[0].Rin == 99999.0

    mixed_circuit: DgsCircuit = DgsCircuit()
    mixed_legacy_element: ElmSind = ElmSind()
    mixed_legacy_element.ID = "mixed-legacy-series-impedance"
    mixed_enriched_element: ElmSind = ElmSind()
    mixed_enriched_element.ID = "mixed-enriched-series-impedance"
    mixed_enriched_element.Rin = 99999.0
    mixed_enriched_element.initial_resistance_column_declared = True
    mixed_circuit.elmsinds.append(mixed_legacy_element)
    mixed_circuit.elmsinds.append(mixed_enriched_element)
    mixed_path: Path = tmp_path / "mixed_elm_sind.dgs"
    with pytest.raises(ValueError):
        mixed_circuit.write_dgs(path=str(mixed_path))
    assert not mixed_path.exists()

def test_dgs_ieee_grids() -> None:
    """Validate DGS IEEE grids against their tracked power-flow results."""
    files: list[tuple[str, str]] = [
        ('IEEE14_test.dgs', 'IEEE 14 bus.sav.xlsx'),
        ('IEEE30_test.dgs', 'IEEE 30 bus.sav.xlsx'),
        ('IEEE118_v2_test.dgs', 'IEEE 118 Bus.sav.xlsx'),
    ]

    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    solver_types: tuple[SolverType, ...] = (
        SolverType.NR,
        SolverType.IWAMOTO,
        SolverType.LM,
        SolverType.FASTDECOUPLED,
        SolverType.PowellDogLeg,
        SolverType.HELM,
    )
    solver_type: SolverType
    for solver_type in solver_types:

        options: PowerFlowOptions = PowerFlowOptions(
            solver_type,
            verbose=0,
            control_q=False,
            retry_with_other_methods=False,
        )

        f1: str
        f2: str
        for f1, f2 in files:
            fname: Path = data_dir / "grids" / "DGS" / f1
            main_circuit: dev.MultiCircuit = FileOpen(str(fname)).open()
            power_flow: PowerFlowDriver = PowerFlowDriver(main_circuit, options)
            power_flow.run()

            results_file: Path = data_dir / "results" / f2
            df_v: pd.DataFrame = pd.read_excel(
                results_file,
                sheet_name='Vabs',
                index_col=0,
            )
            df_p: pd.DataFrame = pd.read_excel(
                results_file,
                sheet_name='Pbranch',
                index_col=0,
            )

            v_gc: np.ndarray = np.abs(power_flow.results.voltage)
            v_psse: np.ndarray = df_v.values[:, 0]
            p_gc: np.ndarray = power_flow.results.Sf.real
            p_psse: np.ndarray = df_p.values[:, 0]

            v_ok: bool = bool(np.allclose(v_gc, v_psse, atol=1e-4))
            flow_ok: bool = bool(np.allclose(p_gc, p_psse, atol=1e-2))

            assert v_ok
            assert flow_ok

        print(solver_type, 'ok')

def test_roundtrip_raw_to_dgs_to_dgs_ieee_grids(tmp_path: Path) -> None:
    """Compare power-flow results before and after a RAW-to-DGS roundtrip.

    :param tmp_path: Isolated pytest directory for generated DGS exports.
    :return: None.
    """
    files: list[tuple[str, str]] = [
        ('IEEE 14 bus.raw', 'IEEE 14 bus.sav.xlsx'),
        ('IEEE 30 bus.raw', 'IEEE 30 bus.sav.xlsx'),
        ('IEEE 118 Bus v2.raw', 'IEEE 118 Bus.sav.xlsx'),
    ]
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    out_dir: Path = tmp_path / "dgs_roundtrip"
    out_dir.mkdir()
    solver_types: tuple[SolverType, ...] = (
        SolverType.NR,
        SolverType.IWAMOTO,
        SolverType.LM,
        SolverType.FASTDECOUPLED,
        SolverType.PowellDogLeg,
        SolverType.HELM,
    )
    solver_type: SolverType
    for solver_type in solver_types:

        options: PowerFlowOptions = PowerFlowOptions(
            solver_type,
            verbose=0,
            control_q=False,
            retry_with_other_methods=False,
        )

        f1: str
        unused_result_file: str
        for f1, unused_result_file in files:
            raw_path: Path = data_dir / "grids" / "RAW" / f1
            main_circuit: dev.MultiCircuit = FileOpen(str(raw_path)).open()

            pf1: PowerFlowDriver = PowerFlowDriver(main_circuit, options)
            pf1.run()

            v1: np.ndarray = np.abs(pf1.results.voltage)
            p1: np.ndarray = pf1.results.Sf.real

            # export to dgs (same logic as FileHandler.save_dgs)
            dgs_path: Path = out_dir / f1.replace(
                '.raw',
                f'__{solver_type.name}.dgs',
            )
            dgs: DgsCircuit = circuit_to_dgs(grid=main_circuit)
            dgs.write_dgs(path=str(dgs_path))

            # import the same dgs and run again
            rt_circuit: dev.MultiCircuit = FileOpen(str(dgs_path)).open()

            pf2: PowerFlowDriver = PowerFlowDriver(rt_circuit, options)
            pf2.run()

            v2: np.ndarray = np.abs(pf2.results.voltage)
            p2: np.ndarray = pf2.results.Sf.real

            v_ok: bool = bool(np.allclose(v1, v2, atol=1e-4))
            flow_ok: bool = bool(np.allclose(p1, p2, atol=1e-2))
            assert v_ok
            assert flow_ok

        print(solver_type, 'ok')


def test_circuit_to_dgs_uses_profile_values_when_t_idx_is_provided() -> None:
    """DGS export must use profile values when ``t_idx`` is provided."""

    grid: dev.MultiCircuit = dev.MultiCircuit(name="profile-export")

    bus_1: dev.Bus = dev.Bus(name="B1", Vnom=110.0, active=True)
    bus_2: dev.Bus = dev.Bus(name="B2", Vnom=110.0, active=True)
    bus_1.active_prof = np.array([True, False])
    grid.add_bus(bus_1)
    grid.add_bus(bus_2)

    load: dev.Load = dev.Load(name="LD1", P=10.0, Q=2.0, active=True)
    load.P_prof = np.array([12.0, 22.0])
    load.Q_prof = np.array([3.0, 5.0])
    load.active_prof = np.array([True, False])
    grid.add_load(bus=bus_1, api_obj=load)

    line: dev.Line = dev.Line(
        bus_from=bus_1,
        bus_to=bus_2,
        name="L12",
        r=0.01,
        x=0.05,
        b=0.001,
        rate=100.0,
        active=True,
    )
    line.rate_prof = np.array([120.0, 220.0])
    line.active_prof = np.array([True, False])
    grid.add_line(line)

    switch: dev.Switch = dev.Switch(
        bus_from=bus_1,
        bus_to=bus_2,
        name="SW12",
        rate=80.0,
        active=True,
        rated_current=0.0,
    )
    switch.rate_prof = np.array([90.0, 180.0])
    switch.active_prof = np.array([True, False])
    grid.add_switch(switch)

    snapshot_export = circuit_to_dgs(grid=grid, t_idx=None)
    profile_export = circuit_to_dgs(grid=grid, t_idx=1)

    snapshot_line_current: float = 100.0 / (np.sqrt(3.0) * 110.0)
    profile_line_current: float = 220.0 / (np.sqrt(3.0) * 110.0)
    snapshot_switch_current: float = 80.0 / (np.sqrt(3.0) * 110.0)
    profile_switch_current: float = 180.0 / (np.sqrt(3.0) * 110.0)

    assert snapshot_export.elmterms[0].outserv == 0
    assert profile_export.elmterms[0].outserv == 1

    assert snapshot_export.elmlods[0].plini == 10.0
    assert profile_export.elmlods[0].plini == 22.0
    assert snapshot_export.elmlods[0].qlini == 2.0
    assert profile_export.elmlods[0].qlini == 5.0
    assert snapshot_export.elmlods[0].outserv == 0
    assert profile_export.elmlods[0].outserv == 1

    assert np.isclose(snapshot_export.typlnes[0].InomAir, snapshot_line_current)
    assert np.isclose(profile_export.typlnes[0].InomAir, profile_line_current)
    assert snapshot_export.elmlnes[0].outserv == 0
    assert profile_export.elmlnes[0].outserv == 1

    assert np.isclose(snapshot_export.typswitches[0].InomA, snapshot_switch_current)
    assert np.isclose(profile_export.typswitches[0].InomA, profile_switch_current)
    assert snapshot_export.elmcoups[0].on_off == 1
    assert profile_export.elmcoups[0].on_off == 0


@pytest.mark.skip(reason="Faulty implementation")
def test_dgs_tower_coupling_logs_non_empty_message_for_blank_value_error() -> None:
    class FakeLine:
        def __init__(self) -> None:
            self.name = "L1"

        def set_circuit_idx(self, val: int, obj) -> None:
            pass

        def apply_template(self, obj, Sbase: float, freq: float, logger: Logger) -> None:
            raise ValueError()

    logger = Logger()
    # TODO: this must be a DgsCircuit
    dgs_grid = SimpleNamespace(
        elmtows=[
            SimpleNamespace(
                outserv=0,
                pGeo=["tower-1"],
                loc_name="Tower 1",
                ID="tower-id",
                plines=["line-1"],
            )
        ]
    )

    _apply_elmtow_tower_coupling(
        dgs_grid=dgs_grid,
        line_by_dgs_id={"line-1": [FakeLine()]},
        overhead_line_type_dict={"tower-1": SimpleNamespace(n_circuits=1)},
        baseMVA=100.0,
        frequency=50.0,
        logger=logger,
    )

    assert len(logger.entries) == 1
    assert logger.entries[0].msg == "Failed to apply tower template."


def test_dgs_shared_tower_type_creates_phase_layout_variants() -> None:
    grid = FileOpen(os.path.join("data", "grids", "DGS", "IEEE13_NoCables.dgs")).open()
    line_by_name = {line.name: line for line in grid.lines}

    assert line_by_name["LOHL632-645"].template.name == "LineConfig603-604_CBN"
    assert line_by_name["LOHL645-646"].template.name == "LineConfig603-604_CBN"
    assert line_by_name["LOHL671-684"].template.name == "LineConfig603-604_ACN"
    assert line_by_name["LOHL632-645"].template is not line_by_name["LOHL671-684"].template

    expected_by_line = {
        "LOHL632-645": [True, False, True, True],
        "LOHL645-646": [True, False, True, True],
        "LOHL671-684": [True, True, False, True],
    }
    for line_name, expected_phases in expected_by_line.items():
        line = line_by_name[line_name]
        declared_phases = [line.ys.phN, line.ys.phA, line.ys.phB, line.ys.phC]
        matrix_phases = np.any(np.abs(line.ys.values) > 1e-12, axis=0)
        assert declared_phases == expected_phases
        assert np.array_equal(matrix_phases, expected_phases)


@pytest.mark.parametrize("use_capacitance", (False, True))
@pytest.mark.parametrize("frequency", (50.0, 60.0))
@pytest.mark.parametrize("base_power", (100.0, 25.0))
def test_dgs_sequence_sections_preserve_parameter_contract(
        use_capacitance: bool, frequency: float, base_power: float,
) -> None:
    """Preserve each imported section parameter when the sequence tuple grows.

    :param use_capacitance: Select Cnf/Cnf0 instead of B/B0 source inputs.
    :param frequency: Frequency used to convert capacitance, in Hz.
    :param base_power: Three-phase system power base in MVA.
    :return: None.
    """
    # Different section types expose shifted zero-sequence and rating positions;
    # positive and zero conductances deliberately differ from every other field.
    first_template: dev.SequenceLineType = dev.SequenceLineType(
        name="First section", Imax=0.7,
        R=0.08, X=0.16, B=2.4, G=1.3,
        R0=0.24, X0=0.48, B0=0.9, G0=0.4,
        CnF=7.0, CnF0=3.0, use_conductance=use_capacitance,
    )
    second_template: dev.SequenceLineType = dev.SequenceLineType(
        name="Second section", Imax=0.4,
        R=0.12, X=0.27, B=3.6, G=2.1,
        R0=0.36, X0=0.81, B0=1.5, G0=0.8,
        CnF=11.0, CnF0=5.0, use_conductance=use_capacitance,
    )
    first_section: ElmLnesec = ElmLnesec()
    first_section.ID = "first-section"
    first_section.typ_id = "first-type"
    first_section.index = 1.0
    first_section.dline = 0.5
    first_section.fline = 0.8
    second_section: ElmLnesec = ElmLnesec()
    second_section.ID = "second-section"
    second_section.typ_id = "second-type"
    second_section.index = 2.0
    second_section.dline = 2.0
    second_section.fline = 0.6
    source: ElmLne = ElmLne()
    source.ID = "sectioned-line"
    source.loc_name = "Sectioned line"
    source.dline = 2.5
    source.fline = 0.9
    voltage: float = 33.0
    buses: list[dev.Bus] = list((
        dev.Bus(name="From", Vnom=voltage),
        dev.Bus(name="To", Vnom=voltage),
    ))
    terminal_indices: dict[str, list[int]] = dict((
        (source.ID, list((0, 1))),
    ))
    sequence_templates: dict[str, dev.SequenceLineType] = dict((
        (first_section.typ_id, first_template),
        (second_section.typ_id, second_template),
    ))
    sections_by_line: dict[str, list[ElmLnesec]] = dict((
        (source.ID, list((second_section, first_section))),
    ))

    # Exercise the real converter with reverse source ordering. No parallel
    # import representation is needed to obtain the canonical Line instance.
    converted: dev.Line | dev.DcLine = convert_dgs_to_line(
        lne=source, buses=buses, stacubic_dict=terminal_indices,
        sequence_templates_dict=sequence_templates,
        dc_cable_type_dict=dict(), source_line_type_dict=dict(),
        overhead_line_type_dict=dict(), underground_line_type_dict=dict(),
        line_type_by_line_id=dict(), line_sections_by_line_id=sections_by_line,
        tower_template_by_line_id=dict(), freq=frequency, baseMVA=base_power,
        logger=Logger(), cubics_by_objid=dict(), bus_by_term_id=dict(), phase_map=dict(),
    )
    assert isinstance(converted, dev.Line)
    assert not converted.reducible

    # Compute the physical oracle directly, without get_values/apply_template.
    # Series Ohms sum, while total charging Siemens use the selected input mode.
    impedance_base: float = voltage * voltage / base_power
    susceptance: float
    zero_susceptance: float
    if use_capacitance:
        susceptance = 2.0 * np.pi * frequency * (7.0 * 0.5 + 11.0 * 2.0) * 1.0e-9
        zero_susceptance = 2.0 * np.pi * frequency * (3.0 * 0.5 + 5.0 * 2.0) * 1.0e-9
    else:
        susceptance = (2.4 * 0.5 + 3.6 * 2.0) * 1.0e-6
        zero_susceptance = (0.9 * 0.5 + 1.5 * 2.0) * 1.0e-6
    expected: np.ndarray = np.array((
        (0.08 * 0.5 + 0.12 * 2.0) / impedance_base,
        (0.16 * 0.5 + 0.27 * 2.0) / impedance_base,
        susceptance * impedance_base,
        (0.24 * 0.5 + 0.36 * 2.0) / impedance_base,
        (0.48 * 0.5 + 0.81 * 2.0) / impedance_base,
        zero_susceptance * impedance_base,
        min(0.7 * 0.8, 0.4 * 0.6) * voltage * np.sqrt(3.0) * 0.9,
    ))
    np.testing.assert_allclose(
        (converted.R, converted.X, converted.B,
         converted.R0, converted.X0, converted.B0, converted.rate),
        expected, rtol=1.0e-10, atol=1.0e-12,
    )
    # Section G/G0 aggregation is pre-existing import debt outside this API fix.
    # Changing tuple positions must neither invent that policy nor retain a shift.
    assert converted.G == 0.0 and converted.G0 == 0.0
