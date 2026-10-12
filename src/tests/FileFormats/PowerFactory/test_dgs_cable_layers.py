# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from pathlib import Path

import numpy as np
import pytest

import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.dgs.dgs_circuit import parse_header
from VeraGridEngine.IO.dgs.dgs_objects import ElmLne, TypCab
from VeraGridEngine.IO.dgs.dgs_to_veragrid import convert_dgs_to_line
from VeraGridEngine.IO.file_open import FileOpen


@pytest.mark.parametrize(
    'armour_flag,layer_flag,expected_warning',
    (
        ('0', '0', ''),
        ('1', '0', 'Active cable armour is not modelled'),
        ('0', '1', 'Active cable armour is not modelled'),
        ('*', '0', ''),
        ('0', '*', ''),
        ('*', '*', 'Cable armour flags are missing'),
    ),
)
def test_dgs_cable_layer_flags_preserve_two_layer_branch(
        tmp_path: Path,
        armour_flag: str,
        layer_flag: str,
        expected_warning: str,
) -> None:
    """Warn from existence flags without dropping the cable branch.

    :param tmp_path: Isolated directory for the modified DGS fixture.
    :param armour_flag: PowerFactory ``has_arm`` value or missing placeholder.
    :param layer_flag: PowerFactory ``cHasEl:2`` value or missing placeholder.
    :param expected_warning: Warning prefix, empty for known absent armour.
    :return: None.
    """
    fixture: Path = (
        Path(__file__).resolve().parents[2]
        / 'data' / 'grids' / 'DGS' / 'UnbalancedNetworkModel_Cables_606_v7.dgs'
    )
    rows: list[str] = fixture.read_text(encoding='utf-8').splitlines()
    header_map: dict[str, int] = dict()
    row_index: int
    row: str
    for row_index, row in enumerate(rows):
        if row.startswith('$$TypCab;'):
            _, header_map = parse_header(line=row)
        elif ';250 AA CN;' in row:
            # Change only existence flags; inactive third-layer material data
            # stays nonzero, as in an ordinary PowerFactory export.
            fields: list[str] = row.split(';')
            fields[header_map['has_arm']] = armour_flag
            fields[header_map['cHasEl:2']] = layer_flag
            rows[row_index] = ';'.join(fields)
        else:
            pass
    assert len(header_map) > 0
    modified_path: Path = tmp_path / 'cable_layers.dgs'
    modified_path.write_text('\n'.join(rows), encoding='utf-8')
    importer: FileOpen = FileOpen(file_name=str(modified_path))
    circuit: dev.MultiCircuit = importer.open()
    line: dev.Line = next(item for item in circuit.lines if item.name == 'LC692-675')

    # Unsupported armour must never turn the physical cable into a zero-Z link.
    assert line.active
    assert not line.reducible
    assert isinstance(line.template, dev.UndergroundLineType)
    np.testing.assert_allclose(
        line.template.z_primitive[0, 0],
        0.2822073966824634 + 0.9089254735303836j,
        rtol=0.0,
        atol=1.0e-7,
    )
    cable_warnings: list[str] = list(
        entry.msg for entry in importer.logger.entries
        if entry.device == '250 AA CN' and entry.device_class == 'TypCab'
    )
    if expected_warning:
        assert len(cable_warnings) == 1
        assert cable_warnings[0].startswith(expected_warning)
    else:
        assert len(cable_warnings) == 0


def test_dgs_missing_armour_columns_remain_unknown() -> None:
    """Do not mistake an old DGS definition for an explicit no-armour flag.

    :return: None.
    """
    _, header_map = parse_header(line='$$TypCab;FID(a:40);loc_name(a:80)')
    cable: TypCab = TypCab.parse_line(line='1;Legacy cable', header_map=header_map)
    assert cable.has_arm is None
    assert cable.cHasEl_2 is None


def test_dgs_scalar_zero_sequence_link_remains_reducible() -> None:
    """Keep historical reduction for non-physical zero-impedance links.

    :return: None.
    """
    # Build the smallest declarative DGS line that resolves to a sequence
    # template, so the converter owns the classification under test.
    source_line: ElmLne = ElmLne()
    source_line.ID = 'scalar-zero-line'
    source_line.loc_name = 'Scalar zero link'
    source_line.typ_id = 'scalar-zero-type'
    source_line.dline = 1.0
    buses: list[dev.Bus] = list((
        dev.Bus(name='From', Vnom=10.0),
        dev.Bus(name='To', Vnom=10.0),
    ))
    sequence_template: dev.SequenceLineType = dev.SequenceLineType(
        name='Scalar zero type',
        R=0.0,
        X=0.0,
        B=0.0,
        R0=0.0,
        X0=0.0,
        B0=0.0,
    )
    terminal_indices: dict[str, list[int]] = dict((
        ('scalar-zero-line', list((0, 1))),
    ))
    sequence_templates: dict[str, dev.SequenceLineType] = dict((
        ('scalar-zero-type', sequence_template),
    ))

    # Empty optional mappings make the sequence template the only valid owner;
    # the resulting scalar-zero branch must therefore preserve legacy reduction.
    converted_line: dev.Line | dev.DcLine = convert_dgs_to_line(
        lne=source_line,
        buses=buses,
        stacubic_dict=terminal_indices,
        sequence_templates_dict=sequence_templates,
        dc_cable_type_dict=dict(),
        source_line_type_dict=dict(),
        overhead_line_type_dict=dict(),
        underground_line_type_dict=dict(),
        line_type_by_line_id=dict(),
        line_sections_by_line_id=dict(),
        tower_template_by_line_id=dict(),
        freq=50.0,
        baseMVA=100.0,
        logger=Logger(),
        cubics_by_objid=dict(),
        bus_by_term_id=dict(),
        phase_map=dict(),
    )

    assert isinstance(converted_line, dev.Line)
    assert isinstance(converted_line.template, dev.SequenceLineType)
    assert converted_line.reducible
