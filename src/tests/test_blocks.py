# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math
import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin
from VeraGridEngine.Utils.Symbolic.block import Block

def test_block_save_to_disk():
    """
       Checks the serialization to disk and recovery from disk of several blocks.
       :return: Nothing if ok, fails if not
       """

    # build Block to test
    # ----------------------------------------------------------------------------------------------------------------------
    # Line
    # ----------------------------------------------------------------------------------------------------------------------
    Qline_from = Var("Qline_from")
    Qline_to = Var("Qline_to")
    Pline_from = Var("Pline_from")
    Pline_to = Var("Pline_to")
    Vline_from = Var("Vline_from")
    Vline_to = Var("Vline_to")
    dline_from = Var("dline_from")
    dline_to = Var("dline_to")

    g = Const(5)
    b = Const(-12)
    bsh = Const(0.03)

    line_block = Block(
        algebraic_eqs=[
            Pline_from - ((Vline_from ** 2 * g) - g * Vline_from * Vline_to * cos(
                dline_from - dline_to) + b * Vline_from * Vline_to * cos(dline_from - dline_to + np.pi / 2)),
            Qline_from - (Vline_from ** 2 * (-bsh / 2 - b) - g * Vline_from * Vline_to * sin(
                dline_from - dline_to) + b * Vline_from * Vline_to * sin(dline_from - dline_to + np.pi / 2)),
            Pline_to - ((Vline_to ** 2 * g) - g * Vline_to * Vline_from * cos(
                dline_to - dline_from) + b * Vline_to * Vline_from * cos(dline_to - dline_from + np.pi / 2)),
            Qline_to - (Vline_to ** 2 * (-bsh / 2 - b) - g * Vline_to * Vline_from * sin(
                dline_to - dline_from) + b * Vline_to * Vline_from * sin(dline_to - dline_from + np.pi / 2)),
        ],
        algebraic_vars=[dline_from, Vline_from, dline_to, Vline_to],
        parameters=[]
    )

    # ----------------------------------------------------------------------------------------------------------------------
    # Load
    # ----------------------------------------------------------------------------------------------------------------------

    Ql = Var("Ql")
    Pl = Var("Pl")

    coeff_alfa = Const(1.8)
    Pl0 = Var('Pl0')
    Ql0 = Const(0.1)
    coeff_beta = Const(8.0)

    load_block = Block(
        algebraic_eqs=[
            Pl - Pl0,
            Ql - Ql0
        ],
        algebraic_vars=[Ql, Pl],
        parameters=[Pl0]
    )

    # ----------------------------------------------------------------------------------------------------------------------
    # Generator
    # ----------------------------------------------------------------------------------------------------------------------

    delta = Var("delta")
    omega = Var("omega")
    psid = Var("psid")
    psiq = Var("psiq")
    i_d = Var("i_d")
    i_q = Var("i_q")
    v_d = Var("v_d")
    v_q = Var("v_q")
    t_e = Var("t_e")
    p_g = Var("P_e")
    Q_g = Var("Q_e")
    Vg = Var("Vg")
    dg = Var("dg")
    tm = Var("tm")
    et = Var("et")

    pi = Const(math.pi)
    fn = Const(50)
    # tm = Const(0.1)
    M = Const(1.0)
    D = Const(100)
    ra = Const(0.3)
    xd = Const(0.86138701)
    vf = Const(1.081099313)

    Kp = Const(1.0)
    Ki = Const(10.0)
    Kw = Const(10.0)

    generator_block = Block(
        state_eqs=[
            # delta - (2 * pi * fn) * (omega - 1),
            # omega - (-tm / M + t_e / M - D / M * (omega - 1))
            (2 * pi * fn) * (omega - 1),  # dδ/dt
            (tm - t_e - D * (omega - 1)) / M,  # dω/dt
            -Kp * et - Ki * et - Kw * (omega - 1)  # det/dt
        ],
        state_vars=[delta, omega, et],
        algebraic_eqs=[
            et - (tm - t_e),
            psid - (-ra * i_q + v_q),
            psiq - (-ra * i_d + v_d),
            i_d - (psid + xd * i_d - vf),
            i_q - (psiq + xd * i_q),
            v_d - (Vg * sin(delta - dg)),
            v_q - (Vg * cos(delta - dg)),
            t_e - (psid * i_q - psiq * i_d),
            (v_d * i_d + v_q * i_q) - p_g,
            (v_q * i_d - v_d * i_q) - Q_g
        ],
        algebraic_vars=[tm, psid, psiq, i_d, i_q, v_d, v_q, t_e, p_g, Q_g],
        parameters=[]
    )

    # ----------------------------------------------------------------------------------------------------------------------
    # Buses
    # ----------------------------------------------------------------------------------------------------------------------

    bus1_block = Block(
        algebraic_eqs=[
            p_g - Pline_from,
            Q_g - Qline_from,
            Vg - Vline_from,
            dg - dline_from
        ],
        algebraic_vars=[Pline_from, Qline_from, Vg, dg]
    )

    bus2_block = Block(
        algebraic_eqs=[
            Pl + Pline_to,
            Ql + Qline_to,
        ],
        algebraic_vars=[Pline_to, Qline_to]
    )

    # ----------------------------------------------------------------------------------------------------------------------
    # System
    # ----------------------------------------------------------------------------------------------------------------------

    sys = Block(
        children=[line_block, load_block, generator_block, bus1_block, bus2_block],
        in_vars=[]
    )

    blocks_to_test = [line_block, load_block, bus1_block, bus2_block, generator_block]

    for blk in blocks_to_test:

        saved_block = blk.to_dict()
        reconstructed_block = Block.parse(saved_block)

        if reconstructed_block != saved_block:
            print('block save to disk test for {} failed'.format(blk))

        assert reconstructed_block == blk

    print('test block save to disk ok')

