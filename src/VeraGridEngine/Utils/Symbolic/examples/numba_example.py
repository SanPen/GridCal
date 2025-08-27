# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import numpy as np
from VeraGridEngine.Utils.Symbolic.symbolic import (Var, sin, exp, compile_numba_function,
                                                    find_vars_order, compile_numba_functions, get_jacobian)

x, y, x2 = Var("x"), Var("y"), Var("x")
expr = sin(x) * exp(y) + x2 ** 2

f_fast = compile_numba_function(expr, sorting_vars=[x, y, x2])

# Argument order is in the docstring:
# print(f_fast.__doc__)  → "Positional order: v0 → x, v1 → y, v2 → x"
print(f_fast(1.0, 2.0, 3.0))  # x=1, y=2, x2=3

# -------------------------------------------------------------------------------

x, y, x2 = Var("x"), Var("y"), Var("x")
eqs = [sin(x) + y,
       x2 ** 2 + exp(y) * x]

order = find_vars_order(eqs)  # deterministic list of Var objects
f_fast = compile_numba_functions(eqs)  # always returns *one* object

print(order)  # [x, y, x2]
print(f_fast.__doc__)  # shows v0→x, v1→y, v2→x
print(f_fast(1, 2, 3))  # (sin 1 + 2, 9 + e²)

# -------------------------------------------------------------------------------

x, y, z = Var('x'), Var('y'), Var('z')
eqs = [sin(x) + y * z,
       x ** 2 + exp(z) * x,
       sin(x) + y * z]  # note repeated eq
vars_ = [x, y, z]

jac_fn, (rows, cols) = get_jacobian(eqs, vars_)
print("Pattern:", list(zip(rows, cols)))

vals = np.array([1.0, 2.0, 0.5])  # x, y, z
J = jac_fn(vals)  # 3×3 sparse CSC
print(J.toarray())
