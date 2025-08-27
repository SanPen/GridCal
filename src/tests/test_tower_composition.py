# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
import VeraGridEngine.api as gce


def test_acha():
    """

    # 3 conductors
    bundle = 0.46  # [m]
    Rdc = 0.1363  # [Ohm/km]
    r_ext = 10.5e-3  # [m]
    r_int = 4.5e-3  # [m]

    Ya = 27.5
    Yb = 27.5
    Yc = 27.5

    Xa = -12.65
    Xb = 0
    Xc = 12.65

    # Overhead line parameters (Single circuit tower with an overhead earth wire)

    :return:
    """
    tower = gce.OverheadLineType(name="Tower")

    wire = gce.Wire(name="Panther 30/7 ACSR",
                    diameter=21.0,
                    diameter_internal=9.0,
                    is_tube=True,
                    r=0.1363,
                    max_current=1)

    tower.add_wire_relationship(wire=wire, xpos=-12.65 - 0.23, ypos=27.5 + 0.23, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=-12.65 + 0.23, ypos=27.5 + 0.23, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=-12.65 - 0.23, ypos=27.5 - 0.23, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=-12.65 + 0.23, ypos=27.5 - 0.23, phase=1)

    tower.add_wire_relationship(wire=wire, xpos=0 - 0.23, ypos=27.5 + 0.23, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=0 + 0.23, ypos=27.5 + 0.23, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=0 - 0.23, ypos=27.5 - 0.23, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=0 + 0.23, ypos=27.5 - 0.23, phase=2)

    tower.add_wire_relationship(wire=wire, xpos=12.65 - 0.23, ypos=27.5 + 0.23, phase=3)
    tower.add_wire_relationship(wire=wire, xpos=12.65 + 0.23, ypos=27.5 + 0.23, phase=3)
    tower.add_wire_relationship(wire=wire, xpos=12.65 - 0.23, ypos=27.5 - 0.23, phase=3)
    tower.add_wire_relationship(wire=wire, xpos=12.65 + 0.23, ypos=27.5 - 0.23, phase=3)

    tower.compute()

    R1, X1, B1, I_kA = tower.get_sequence_values(circuit_idx=0, seq=1)
    R0, X0, B0, I_kA = tower.get_sequence_values(circuit_idx=0, seq=0)
    print(f"R0: {R0}, X0: {X0}")
    print(f"R1: {R1}, X1: {X1}")

    Z = tower.z_abcn
    print("Z [ohm/km] =\n", Z)

    Ysh = tower.y_abcn * 1e6  # pass from S/km to uS/km
    print("Y [uS/km] =\n", Ysh)

    Z_expected = np.array([[0.08034301 + 0.53832056j, 0.04625667 + 0.27333481j, 0.04622869 + 0.22981391j],
                           [0.04624575 + 0.27333481j, 0.08034882 + 0.53830903j, 0.04625667 + 0.27333481j],
                           [0.04618743 + 0.22981395j, 0.04624575 + 0.27333481j, 0.08034301 + 0.53832056j]])

    # in [uS/km]
    Ysh_expected = np.array([[0. + 3.35962813j, 0. - 0.80958316j, 0. - 0.30514186j],
                             [0. - 0.80958316j, 0. + 3.52714236j, 0. - 0.80958316j],
                             [0. - 0.30514186j, 0. - 0.80958316j, 0. + 3.35962813j]])

    assert np.allclose(Z, Z_expected, atol=1e-4)
    assert np.allclose(Ysh, Ysh_expected)


def test_rating():
    """
    test according to:
    https://gobiernoabierto.navarra.es/sites/default/files/7._proyecto_laat_400_kv_sc_set_labradas_set_la_serna_compressed.pdf
    Single circuit, 400 kV
    Duplex wire
    :return:
    """

    # PRYSALAC: Media y Alta Tensión Líneas Aéreas de Energía
    # Cuerda desnuda de
    # Aluminio AceroPRYSALAC
    # Distribución y Transmisión
    # wire = gce.Wire(name="CURLEW", diameter=3.162/100.0, r=0.0542, max_current=1.047, material="ACSR")
    wire = gce.Wire(
        name="485-AL1/63-ST1A",
        code="LA 545 CARDINAL",
        diameter=30.42,
        r=0.0587,  # 0.0571
        max_current=0.89786,
        material="ACSR")

    tower = gce.OverheadLineType(name="400 kV single circuit duplex")
    tower.Vnom = 400
    tower.earth_resistivity = 200

    # duplex wires A
    tower.add_wire_relationship(wire=wire, xpos=-9.8, ypos=22.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=-10.2, ypos=22.5, phase=1)

    # duplex wires B
    tower.add_wire_relationship(wire=wire, xpos=-0.2, ypos=26.1, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=0.2, ypos=26.1, phase=2)

    # duplex wires C
    tower.add_wire_relationship(wire=wire, xpos=9.8, ypos=22.5, phase=3)
    tower.add_wire_relationship(wire=wire, xpos=10.2, ypos=22.5, phase=3)

    tower.compute()

    expected_rate = 1.8  # kA

    bus1 = gce.Bus(name="Bus 1", Vnom=400)
    bus2 = gce.Bus(name="Bus 2", Vnom=400)
    line = gce.Line(name="Line", bus_from=bus1, bus_to=bus2, length=0.5)

    line.apply_template(tower, 100, 50)

    assert np.isclose(tower.Imax[0], expected_rate, atol=0.1)
    assert np.isclose(line.R, 9.1744e-6, atol=1e-6)
    assert np.isclose(line.X, 0.0001031, atol=1e-6)
    assert np.isclose(line.B, 0.0027729, atol=1e-6)


def test_ratings_with_neutral():
    """
    overhead_quadruple_circuit_triplex_400_kv
    Quadruple circuit, 400 kV
    Triplex wire
    :return:
    """

    # PRYSALAC: Media y Alta TensiónLíneas Aéreas de Energía
    # Cuerda desnuda de
    # Aluminio AceroPRYSALAC
    # Distribución y Transmisión
    # wire = gce.Wire(name="CURLEW", gmr=3.162/100.0/2, r=0.0542, max_current=1.047, material="ACSR")

    tower = gce.OverheadLineType(name="400 kV quadruple circuit triplex")
    tower.Vnom = 400
    tower.earth_resistivity = 200

    wire = gce.Wire(
        name="402-AL1/52-ST1A",
        code="LA 455 CONDOR",
        diameter=27.72,
        r=0.0718,
        max_current=0.799,
        material="ACSR"
    )

    neutral_wire = gce.Wire(
        name="OPGW 25kA 17.10",
        code="OPGW",
        diameter=17.1,
        r=0.373,
        max_current=25,
        is_tube=True,
        diameter_internal=9.7,
        material="ACS"
    )

    # triplex wires A1
    tower.add_wire_relationship(wire=wire, xpos=-13 - 0.2, ypos=22, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=-13 + 0.2, ypos=22, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=-13, ypos=22 - 0.34, phase=1)

    # triplex wires B1
    tower.add_wire_relationship(wire=wire, xpos=-13 - 0.2, ypos=29, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=-13 + 0.2, ypos=29, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=-13, ypos=29 - 0.34, phase=2)

    # triplex wires C1
    tower.add_wire_relationship(wire=wire, xpos=-13 - 0.2, ypos=36, phase=3)
    tower.add_wire_relationship(wire=wire, xpos=-13 + 0.2, ypos=36, phase=3)
    tower.add_wire_relationship(wire=wire, xpos=-13, ypos=36 - 0.34, phase=3)

    # triplex wires A2
    tower.add_wire_relationship(wire=wire, xpos=-7 - 0.2, ypos=22, phase=4)
    tower.add_wire_relationship(wire=wire, xpos=-7 + 0.2, ypos=22, phase=4)
    tower.add_wire_relationship(wire=wire, xpos=-7, ypos=22 - 0.34, phase=4)

    # triplex wires B2
    tower.add_wire_relationship(wire=wire, xpos=-7 - 0.2, ypos=29, phase=5)
    tower.add_wire_relationship(wire=wire, xpos=-7 + 0.2, ypos=29, phase=5)
    tower.add_wire_relationship(wire=wire, xpos=-7, ypos=29 - 0.34, phase=5)

    # triplex wires C2
    tower.add_wire_relationship(wire=wire, xpos=-7 - 0.2, ypos=36, phase=6)
    tower.add_wire_relationship(wire=wire, xpos=-7 + 0.2, ypos=36, phase=6)
    tower.add_wire_relationship(wire=wire, xpos=-7, ypos=36 - 0.34, phase=6)

    # triplex wires A3
    tower.add_wire_relationship(wire=wire, xpos=7 - 0.2, ypos=22, phase=7)
    tower.add_wire_relationship(wire=wire, xpos=7 + 0.2, ypos=22, phase=7)
    tower.add_wire_relationship(wire=wire, xpos=7, ypos=22 - 0.34, phase=7)

    # triplex wires B3
    tower.add_wire_relationship(wire=wire, xpos=7 - 0.2, ypos=29, phase=8)
    tower.add_wire_relationship(wire=wire, xpos=7 + 0.2, ypos=29, phase=8)
    tower.add_wire_relationship(wire=wire, xpos=7, ypos=29 - 0.34, phase=8)

    # triplex wires C3
    tower.add_wire_relationship(wire=wire, xpos=7 - 0.2, ypos=36, phase=9)
    tower.add_wire_relationship(wire=wire, xpos=7 + 0.2, ypos=36, phase=9)
    tower.add_wire_relationship(wire=wire, xpos=7, ypos=36 - 0.34, phase=9)

    # triplex wires A4
    tower.add_wire_relationship(wire=wire, xpos=13 - 0.2, ypos=22, phase=10)
    tower.add_wire_relationship(wire=wire, xpos=13 + 0.2, ypos=22, phase=10)
    tower.add_wire_relationship(wire=wire, xpos=13, ypos=22 - 0.34, phase=10)

    # triplex wires B4
    tower.add_wire_relationship(wire=wire, xpos=13 - 0.2, ypos=29, phase=11)
    tower.add_wire_relationship(wire=wire, xpos=13 + 0.2, ypos=29, phase=11)
    tower.add_wire_relationship(wire=wire, xpos=13, ypos=29 - 0.34, phase=11)

    # triplex wires C4
    tower.add_wire_relationship(wire=wire, xpos=13 - 0.2, ypos=36, phase=12)
    tower.add_wire_relationship(wire=wire, xpos=13 + 0.2, ypos=36, phase=12)
    tower.add_wire_relationship(wire=wire, xpos=13, ypos=36 - 0.34, phase=12)

    # neutral/optic
    tower.add_wire_relationship(wire=neutral_wire, xpos=-6, ypos=41, phase=0)
    tower.add_wire_relationship(wire=neutral_wire, xpos=6, ypos=41, phase=0)

    tower.compute()

    # test_ratings_with_neutral
    assert len(tower.Imax) == 4
    assert tower.Imax[1] == tower.Imax[0]
    assert tower.Imax[2] == tower.Imax[0]
    assert tower.Imax[3] == tower.Imax[0]