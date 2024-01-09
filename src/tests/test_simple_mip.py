# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import numpy as np
from GridCalEngine.Utils.MIP.SimpleMip import LpModel, LpExp, LpCst, LpVar


def test_linear_formulation():

    prob = LpModel()

    A = prob._add_variable(name="A")
    B = prob._add_variable(name="B")

    r1 = A + B <= 10
    assert r1.linear_expression.terms[A] == 1
    assert r1.linear_expression.terms[B] == 1
    assert r1.coefficient == 10

    r2 = 2 * A + B <= 10
    assert r2.linear_expression.terms[A] == 2
    assert r2.linear_expression.terms[B] == 1
    assert r2.coefficient == 10

    r3 = A + 3 * B <= 10
    assert r3.linear_expression.terms[A] == 1
    assert r3.linear_expression.terms[B] == 3
    assert r3.coefficient == 10

    r4 = 2 * A + 3 * B <= 10
    assert r4.linear_expression.terms[A] == 2
    assert r4.linear_expression.terms[B] == 3
    assert r4.coefficient == 10

    r5 = 2 * A + 3 * B + 5
    assert r5.terms[A] == 2
    assert r5.terms[B] == 3
    assert r5.offset == 5

    r6 = 2 * A + 3 * B == 40
    assert r6.linear_expression.terms[A] == 2
    assert r6.linear_expression.terms[B] == 3
    assert r6.coefficient == 40

    r7 = 2 * A + 3 * B - 8 <= 20
    assert r7.linear_expression.terms[A] == 2
    assert r7.linear_expression.terms[B] == 3
    assert r7.coefficient == 28

    r8 = 2 * A + 3 * B + 3 == 40
    assert r8.linear_expression.terms[A] == 2
    assert r8.linear_expression.terms[B] == 3
    assert r8.coefficient == 37

    r9 = 2 * A + 3 * A + 3
    assert r9.terms[A] == 5
    assert r9.offset == 3

    r10 = 2 * A - 3 * A + 6 * B - 3
    assert r10.terms[A] == -1
    assert r10.terms[B] == 6
    assert r10.offset == -3

    r11 = 2 * A - 3 * A + 0 * B - 3
    assert r11.terms[A] == -1
    assert B not in r11.terms
    assert r11.offset == -3

    r11 *= 0
    assert len(r11.terms) == 0
    assert r11.offset == 0

    r12 = 0 * A
    assert r12 == 0

    r13 = prob.sum([r9, r10])
    assert r13.terms[A] == 4
    assert r13.terms[B] == 6
    assert r13.offset == 0

    r14 = A == r5
    assert isinstance(r14, LpCst)
    assert r14.terms[A] == -1
    assert r14.terms[B] == -3
    assert r14.coefficient == 5


def test_lp_simple2():
    prob = LpModel()

    A = prob._add_variable(lb=1, name="A")
    B = prob._add_variable(lb=1, name="B")

    prob.maximize(A + B)

    prob.add_cst(A + B <= 4)
    prob.add_cst(A + B >= 2)

    prob.solve()

    assert prob.is_optimal()
    assert prob.get_objective_value() == 4

    prob.minimize(A + B + 1)
    prob.solve()

    assert prob.is_optimal()
    assert prob.get_objective_value() == 3


def test_lp_simple3():
    prob = LpModel()

    XR = prob.add_var(name="XR")
    XE = prob.add_var(name="XE")

    prob.maximize(5 * XR + 7 * XE)

    prob.add_cst(3 * XR + 4 * XE <= 650)
    prob.add_cst(2 * XR + 3 * XE <= 500)
    prob.solve()

    assert prob.is_optimal()
    assert np.isclose(prob.get_objective_value(), 1137.5)
    assert np.isclose(prob.get_value(XR), 0)
    assert np.isclose(prob.get_value(XE), 162.5)


def test_lp_simple4():
    prob = LpModel()

    X = prob.add_vars(name="X", size=4)
    S = prob.add_vars(name="S", size=5)

    prob.maximize(2 * X[3] + S[4])

    prob.add_cst(X[0] + S[0] == 100)
    prob.add_cst(S[0] - 0.5 * X[0] - X[1] - S[1] == 0)
    prob.add_cst(2 * X[0] + S[1] - 0.5 * X[1] - X[2] - S[2] == 0)
    prob.add_cst(2 * X[1] + S[2] - 0.5 * X[2] - X[3] - S[3] == 0)
    prob.add_cst(2 * X[2] + S[3] - 0.5 * X[3] - S[4] == 0)

    prob.solve()

    assert prob.is_optimal()
    assert np.isclose(prob.get_objective_value(), 208.13008130081298)
    assert np.allclose(prob.get_array_value(X), np.array([27.642277, 58.536587, 26.016260, 104.065041]))
    assert np.allclose(prob.get_array_value(S), np.array([72.357727, 0.0, 0.0, 0.0, 0.0]))
